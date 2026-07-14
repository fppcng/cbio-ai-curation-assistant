"""
pmc_supplement_fetcher.py
-------------------------
Download supplementary files from PubMed Central by PMCID or PMID.

PMID input is converted to PMCID using the NCBI idconv utility. Supplementary
links are read from the PMC article XML and downloaded into a caller-provided
directory. Archive files are expanded and supported curation files are returned.
"""

from __future__ import annotations

import json
import os
import re
import hashlib
import http.cookiejar
from html.parser import HTMLParser
import tarfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
import xml.etree.ElementTree as ET

import requests


SUPPORTED_SUPPLEMENT_EXTENSIONS = {
    ".xlsx", ".xls", ".csv", ".tsv", ".txt", ".tab", ".maf", ".doc", ".docx", ".pdf",
}
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz"}
NCBI_TIMEOUT_SECONDS = 30
NCBI_TOOL_NAME = "cBioAbstractor"
NCBI_CONTACT_EMAIL = os.getenv("NCBI_EMAIL", "cBioAbstractor@example.com")
HTTP_HEADERS = {
    "User-Agent": "cBioAbstractor/1.0 (supplementary-file-curation)",
    "Accept": "*/*",
}
POW_MAX_ITERATIONS = 20_000_000
PMC_REQUEST_RETRY_ATTEMPTS = 3
PMC_REQUEST_RETRY_BASE_DELAY_SECONDS = 1.0
PMC_DOWNLOAD_RETRY_ATTEMPTS = 3
PMC_DOWNLOAD_RETRY_BASE_DELAY_SECONDS = 1.0


@dataclass
class DownloadedSupplement:
    path: str
    filename: str
    source_url: str


@dataclass(frozen=True)
class ResolvedStudyIdentifier:
    input_identifier: str
    identifier_type: str
    normalized_identifier: str
    pmcid: str


@dataclass(frozen=True)
class PMCErrorClassification:
    category: str
    retryable: bool
    status_code: int | None = None


class PMCRequestError(RuntimeError):
    def __init__(
        self,
        operation: str,
        classification: PMCErrorClassification,
        detail: str,
    ) -> None:
        self.operation = operation
        self.category = classification.category
        self.retryable = classification.retryable
        self.status_code = classification.status_code
        self.detail = detail
        super().__init__(f"{operation} failed [{self.category}]: {detail}")


def _http_status_code_from_error(exc: Exception) -> int | None:
    if isinstance(exc, PMCRequestError):
        return exc.status_code
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        return response.status_code if response is not None else None
    if isinstance(exc, HTTPError):
        return exc.code
    return None


def _classify_pmc_error(exc: Exception) -> PMCErrorClassification:
    if isinstance(exc, PMCRequestError):
        return PMCErrorClassification(
            category=exc.category,
            retryable=exc.retryable,
            status_code=exc.status_code,
        )

    status_code = _http_status_code_from_error(exc)
    if status_code == 429:
        return PMCErrorClassification(category="rate_limited", retryable=True, status_code=status_code)
    if status_code in {403, 500, 502, 503, 504}:
        return PMCErrorClassification(category="transient_remote_error", retryable=True, status_code=status_code)
    if status_code == 404:
        return PMCErrorClassification(category="remote_not_found", retryable=False, status_code=status_code)
    if status_code is not None:
        return PMCErrorClassification(category="remote_http_error", retryable=False, status_code=status_code)

    if isinstance(exc, (requests.Timeout, requests.ConnectionError, TimeoutError, URLError)):
        return PMCErrorClassification(category="transient_network_error", retryable=True)
    if isinstance(exc, ET.ParseError):
        return PMCErrorClassification(category="response_parse_error", retryable=False)
    if isinstance(exc, ValueError):
        message = str(exc)
        if "No PMCID found for PMID" in message:
            return PMCErrorClassification(category="unresolved_identifier", retryable=False)
        if (
            "proof-of-work challenge" in message
            or "Preparing to download" in message
            or "PMC returned an HTML" in message
        ):
            return PMCErrorClassification(category="pmc_challenge", retryable=True)
        if "PMC XML was not returned" in message:
            return PMCErrorClassification(category="unexpected_response", retryable=True)
        if (
            "PMID must contain digits." in message
            or "PMCID is empty." in message
            or "Could not parse PMCID" in message
            or "Identifier must be a numeric PMID" in message
        ):
            return PMCErrorClassification(category="invalid_identifier", retryable=False)
        return PMCErrorClassification(category="invalid_response", retryable=False)
    if isinstance(exc, requests.RequestException):
        return PMCErrorClassification(category="remote_request_error", retryable=False)
    return PMCErrorClassification(category="unexpected_error", retryable=False)


def _wrap_pmc_error(operation: str, exc: Exception) -> PMCRequestError:
    if isinstance(exc, PMCRequestError):
        return exc
    return PMCRequestError(
        operation=operation,
        classification=_classify_pmc_error(exc),
        detail=str(exc),
    )


def _run_with_pmc_retry(
    *,
    operation: str,
    request_fn,
    attempts: int = PMC_REQUEST_RETRY_ATTEMPTS,
    base_delay_seconds: float = PMC_REQUEST_RETRY_BASE_DELAY_SECONDS,
):
    last_error: PMCRequestError | None = None
    for attempt in range(1, attempts + 1):
        try:
            return request_fn()
        except Exception as exc:
            last_error = _wrap_pmc_error(operation, exc)
            if attempt >= attempts or not last_error.retryable:
                raise last_error from exc
            time.sleep(base_delay_seconds * attempt)

    assert last_error is not None
    raise last_error


def detect_pubmed_identifier_type(identifier: str) -> str | None:
    value = (identifier or "").strip()
    if re.fullmatch(r"PMC\d+", value, flags=re.IGNORECASE):
        return "PMCID"
    if re.fullmatch(r"\d+", value):
        return "PMID"
    return None


def resolve_study_identifier_to_pmcid(identifier: str) -> ResolvedStudyIdentifier:
    """Resolve a user-supplied PMID or PMCID to a normalized PMCID."""
    value = (identifier or "").strip()
    identifier_type = detect_pubmed_identifier_type(value)
    if identifier_type == "PMCID":
        normalized_identifier = normalize_pmcid(value)
        return ResolvedStudyIdentifier(
            input_identifier=value,
            identifier_type=identifier_type,
            normalized_identifier=normalized_identifier,
            pmcid=normalized_identifier,
        )
    if identifier_type == "PMID":
        normalized_identifier = re.sub(r"\D", "", value)
        return ResolvedStudyIdentifier(
            input_identifier=value,
            identifier_type=identifier_type,
            normalized_identifier=normalized_identifier,
            pmcid=pmid_to_pmcid(normalized_identifier),
        )
    raise ValueError("Identifier must be a numeric PMID or a PMCID such as PMC123456.")


def normalize_pmcid(value: str) -> str:
    """Return a PMCID in PMC123456 format."""
    raw = value.strip()
    if not raw:
        raise ValueError("PMCID is empty.")

    match = re.search(r"(?:PMC)?(\d+)", raw, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not parse PMCID from '{value}'.")

    return f"PMC{match.group(1)}"


def pmid_to_pmcid(pmid: str) -> str:
    """Convert PMID to PMCID using the PMC ID Converter API."""
    clean_pmid = re.sub(r"\D", "", pmid or "")
    if not clean_pmid:
        raise ValueError("PMID must contain digits.")

    def _request_id_converter() -> str:
        params = urlencode({
            "ids": clean_pmid,
            "idtype": "pmid",
            "format": "json",
            "tool": NCBI_TOOL_NAME,
            "email": NCBI_CONTACT_EMAIL,
        })
        request = Request(
            f"https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/?{params}",
            headers=HTTP_HEADERS,
        )
        with urlopen(request, timeout=NCBI_TIMEOUT_SECONDS) as response:
            payload = response.read().decode("utf-8")

        response_payload = json.loads(payload)
        records = response_payload.get("records") or []
        if not records or not records[0].get("pmcid"):
            raise ValueError(f"No PMCID found for PMID {clean_pmid}.")

        return normalize_pmcid(records[0]["pmcid"])

    return _run_with_pmc_retry(
        operation=f"PMID to PMCID resolution for PMID {clean_pmid}",
        request_fn=_request_id_converter,
    )


def _pmcid_numeric(pmcid: str) -> str:
    return normalize_pmcid(pmcid).replace("PMC", "")


def _fetch_pmc_xml(pmcid: str) -> str:
    normalized_pmcid = normalize_pmcid(pmcid)

    def _request_xml() -> str:
        response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pmc", "id": _pmcid_numeric(normalized_pmcid), "retmode": "xml"},
            headers=HTTP_HEADERS,
            timeout=NCBI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        if "<article" not in response.text and "<pmc-articleset" not in response.text:
            raise ValueError(f"PMC XML was not returned for {normalized_pmcid}.")
        return response.text

    return _run_with_pmc_retry(
        operation=f"PMC XML fetch for {normalized_pmcid}",
        request_fn=_request_xml,
    )


def _fetch_pmc_article_html(pmcid: str) -> str:
    normalized_pmcid = normalize_pmcid(pmcid)

    def _request_article_html() -> str:
        response = requests.get(
            f"https://pmc.ncbi.nlm.nih.gov/articles/{normalized_pmcid}/",
            headers=HTTP_HEADERS,
            timeout=NCBI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        if "<html" not in response.text.lower():
            raise ValueError(f"PMC article HTML was not returned for {normalized_pmcid}.")
        return response.text

    return _run_with_pmc_retry(
        operation=f"PMC article HTML fetch for {normalized_pmcid}",
        request_fn=_request_article_html,
    )


def _oa_package_url(pmcid: str) -> str | None:
    normalized_pmcid = normalize_pmcid(pmcid)

    def _request_oa_package_url() -> str | None:
        response = requests.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi",
            params={"id": normalized_pmcid},
            headers=HTTP_HEADERS,
            timeout=NCBI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        for link in root.iter("link"):
            if link.attrib.get("format") == "tgz" and link.attrib.get("href"):
                href = link.attrib["href"]
                return href.replace("ftp://ftp.ncbi.nlm.nih.gov", "https://ftp.ncbi.nlm.nih.gov")
        return None

    return _run_with_pmc_retry(
        operation=f"PMC OA package lookup for {normalized_pmcid}",
        request_fn=_request_oa_package_url,
    )


def _download_oa_package(pmcid: str, output_dir: Path) -> list[Path]:
    package_url = _oa_package_url(pmcid)
    if not package_url:
        return []

    package_path = _download_url(package_url, output_dir, 0)
    extracted = _extract_supported_files(package_path, output_dir)
    return [
        path
        for path in extracted
        if path.name.lower() != f"{normalize_pmcid(pmcid).lower()}.pdf"
    ]


def _xlink_href(element: ET.Element) -> str:
    return (
        element.attrib.get("{http://www.w3.org/1999/xlink}href")
        or element.attrib.get("href")
        or ""
    ).strip()


def _supplement_urls(pmcid: str, xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    urls: list[str] = []
    base_article_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{normalize_pmcid(pmcid)}/"
    base_site_url = "https://pmc.ncbi.nlm.nih.gov"
    base_instance_bin_url = (
        f"https://pmc.ncbi.nlm.nih.gov/articles/instance/{_pmcid_numeric(pmcid)}/bin/"
    )

    for supp in root.iter():
        if not supp.tag.endswith("supplementary-material"):
            continue

        candidate_hrefs = []
        direct_href = _xlink_href(supp)
        if direct_href:
            candidate_hrefs.append(direct_href)

        for child in supp.iter():
            if child.tag.endswith(("media", "graphic", "inline-supplementary-material")):
                href = _xlink_href(child)
                if href:
                    candidate_hrefs.append(href)

        for href in candidate_hrefs:
            if not href:
                continue
            if href.startswith(("http://", "https://")):
                url = href
            elif href.startswith("/"):
                url = urljoin(base_site_url, href)
            elif "/" in href:
                url = urljoin(base_article_url, href)
            else:
                url = urljoin(base_instance_bin_url, href)
            if url not in urls:
                urls.append(url)

    return urls


class _PMCArticleLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {key.lower(): (value or "").strip() for key, value in attrs}
        href = attr_map.get("href", "")
        if not href:
            return
        self.links.append(attr_map)


def _article_html_links(html_text: str) -> list[dict[str, str]]:
    parser = _PMCArticleLinkParser()
    parser.feed(html_text)
    return parser.links


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _filename_extension(name: str) -> str:
    lower = name.lower()
    for compound_suffix in (".tar.gz", ".tar.bz2", ".tar.xz"):
        if lower.endswith(compound_suffix):
            return compound_suffix
    return Path(lower).suffix.lower()


def _supplement_urls_from_article_html(pmcid: str, html_text: str) -> list[str]:
    normalized_pmcid = normalize_pmcid(pmcid)
    instance_prefix = f"/articles/instance/{_pmcid_numeric(normalized_pmcid)}/bin/"
    article_base_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{normalized_pmcid}/"
    urls: list[str] = []

    for link in _article_html_links(html_text):
        href = link.get("href", "")
        data_ga_action = link.get("data-ga-action", "").lower()
        if not href:
            continue

        href_path = urlparse(href).path or href
        suffix = _filename_extension(href_path)
        if suffix not in (SUPPORTED_SUPPLEMENT_EXTENSIONS | ARCHIVE_EXTENSIONS):
            continue
        if instance_prefix not in href_path and data_ga_action != "click_feat_suppl":
            continue

        urls.append(urljoin(article_base_url, href))

    return _dedupe_preserve_order(urls)


def _discover_supplement_urls(
    pmcid: str,
    *,
    xml_text: str | None = None,
    article_html: str | None = None,
) -> list[str]:
    discovered: list[str] = []
    if xml_text:
        discovered.extend(_supplement_urls(pmcid, xml_text))
    if article_html:
        discovered.extend(_supplement_urls_from_article_html(pmcid, article_html))
    return _dedupe_preserve_order(discovered)


def _article_pdf_url_from_article_html(pmcid: str, html_text: str) -> str | None:
    normalized_pmcid = normalize_pmcid(pmcid)
    article_base_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{normalized_pmcid}/"

    for link in _article_html_links(html_text):
        href = link.get("href", "")
        if not href:
            continue

        href_path = (urlparse(href).path or href).lower()
        if not href_path.endswith('.pdf'):
            continue
        if f"/articles/{normalized_pmcid.lower()}/pdf/" in href_path or href_path.startswith('/pdf/'):
            return urljoin(article_base_url, href)
    return None


def _looks_like_html_payload(content: bytes) -> bool:
    prefix = content[:4096].lstrip().lower()
    return (
        prefix.startswith(b"<!doctype html")
        or prefix.startswith(b"<html")
        or prefix.startswith(b"<head")
        or prefix.startswith(b"<body")
        or b"<title>preparing to download" in prefix
        or b"pow_challenge" in prefix
    )


def _validate_downloaded_content(filename: str, content_type: str, content: bytes) -> None:
    if not content:
        raise ValueError(f"Downloaded content for {filename} was empty.")

    normalized_content_type = (content_type or "").lower()
    if "text/html" in normalized_content_type or _looks_like_html_payload(content):
        raise ValueError(f"PMC returned an HTML page instead of {filename}.")

    extension = _filename_extension(filename)
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise ValueError(f"Downloaded content for {filename} was not a PDF.")
    if extension in {".zip", ".docx", ".xlsx"} and not content.startswith(b"PK"):
        raise ValueError(f"Downloaded content for {filename} was not a ZIP-based document.")
    if extension in {".gz", ".tgz", ".tar.gz"} and not content.startswith(b"\x1f\x8b"):
        raise ValueError(f"Downloaded content for {filename} was not a gzip archive.")
    if extension == ".bz2" and not content.startswith(b"BZh"):
        raise ValueError(f"Downloaded content for {filename} was not a bzip2 archive.")
    if extension in {".xz", ".tar.xz"} and not content.startswith(b"\xfd7zXZ\x00"):
        raise ValueError(f"Downloaded content for {filename} was not an xz archive.")


def _safe_filename(filename: str, fallback: str) -> str:
    name = unquote(filename or "").strip()
    name = os.path.basename(name)
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return name or fallback


def _filename_from_headers(url: str, disposition: str, index: int) -> str:
    match = re.search(r'filename="?([^";]+)"?', disposition, flags=re.IGNORECASE)
    if match:
        return _safe_filename(match.group(1), f"supplement_{index}")

    parsed_name = os.path.basename(urlparse(url).path)
    return _safe_filename(parsed_name, f"supplement_{index}")


def _filename_from_response(url: str, response: requests.Response, index: int) -> str:
    return _filename_from_headers(url, response.headers.get("content-disposition", ""), index)


def _extension(path: Path) -> str:
    if path.name.lower().endswith(".tar.gz"):
        return ".tar.gz"
    return path.suffix.lower()


def _is_supported_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_SUPPLEMENT_EXTENSIONS


def _is_archive(path: Path) -> bool:
    lower = path.name.lower()
    return (
        lower.endswith((".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz"))
        or path.suffix.lower() in ARCHIVE_EXTENSIONS
    )


def _parse_pow_challenge(html: str) -> tuple[str, int, str, str] | None:
    challenge = re.search(r'POW_CHALLENGE\s*=\s*"([^"]+)"', html)
    difficulty = re.search(r'POW_DIFFICULTY\s*=\s*"([^"]+)"', html)
    cookie_name = re.search(r'POW_COOKIE_NAME\s*=\s*"([^"]+)"', html)
    cookie_path = re.search(r'POW_COOKIE_PATH\s*=\s*"([^"]+)"', html)
    if not challenge or not difficulty or not cookie_name:
        return None
    return (
        challenge.group(1),
        int(difficulty.group(1)),
        cookie_name.group(1),
        cookie_path.group(1) if cookie_path else "/",
    )


def _solve_pow_nonce(challenge: str, difficulty: int) -> int:
    prefix = "0" * difficulty
    for nonce in range(POW_MAX_ITERATIONS):
        digest = hashlib.sha256(f"{challenge}{nonce}".encode("utf-8")).hexdigest()
        if digest.startswith(prefix):
            return nonce
    raise ValueError("PMC proof-of-work challenge was not solved within the iteration limit.")


def _set_cookie(cookie_jar: http.cookiejar.CookieJar, url: str, name: str, value: str, path: str) -> None:
    domain = urlparse(url).hostname or "pmc.ncbi.nlm.nih.gov"
    cookie = http.cookiejar.Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=False,
        domain_initial_dot=False,
        path=path or "/",
        path_specified=True,
        secure=False,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )
    cookie_jar.set_cookie(cookie)


def _download_url_with_urllib_pow(url: str, output_dir: Path, index: int) -> Path:
    cookie_jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    request = Request(url, headers=HTTP_HEADERS)

    try:
        response = opener.open(request, timeout=NCBI_TIMEOUT_SECONDS)
    except HTTPError as exc:
        response = exc

    content = response.read()
    content_type = response.headers.get("content-type", "").lower()
    filename = _filename_from_headers(url, response.headers.get("content-disposition", ""), index)

    if "text/html" in content_type:
        html = content.decode("utf-8", errors="replace")
        pow_parts = _parse_pow_challenge(html)
        if pow_parts:
            challenge, difficulty, cookie_name, cookie_path = pow_parts
            nonce = _solve_pow_nonce(challenge, difficulty)
            _set_cookie(cookie_jar, url, cookie_name, f"{challenge},{nonce}", cookie_path)

            response = opener.open(Request(url, headers=HTTP_HEADERS), timeout=NCBI_TIMEOUT_SECONDS)
            content = response.read()
            content_type = response.headers.get("content-type", "").lower()
            filename = _filename_from_headers(url, response.headers.get("content-disposition", ""), index)

    _validate_downloaded_content(filename, content_type, content)

    path = output_dir / filename
    if path.exists():
        stem = path.stem
        suffix = path.suffix
        path = output_dir / f"{stem}_{index}{suffix}"
    path.write_bytes(content)
    return path


def _is_pmc_download_host(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    return hostname in {"pmc.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov", "ftp.ncbi.nlm.nih.gov"}


def _is_retryable_pmc_download_error(exc: Exception) -> bool:
    return _classify_pmc_error(exc).retryable


def _download_url_once(url: str, output_dir: Path, index: int) -> Path:
    try:
        response = requests.get(url, headers=HTTP_HEADERS, timeout=NCBI_TIMEOUT_SECONDS)
        response.raise_for_status()
    except Exception:
        if _is_pmc_download_host(url):
            return _download_url_with_urllib_pow(url, output_dir, index)
        raise

    content_type = response.headers.get("content-type", "").lower()
    filename = _filename_from_response(url, response, index)
    if "text/html" in content_type and Path(filename).suffix.lower() in (
        SUPPORTED_SUPPLEMENT_EXTENSIONS | ARCHIVE_EXTENSIONS
    ):
        if _is_pmc_download_host(url):
            return _download_url_with_urllib_pow(url, output_dir, index)
        raise ValueError(f"PMC returned an HTML challenge page instead of {filename}.")

    _validate_downloaded_content(filename, content_type, response.content)

    path = output_dir / filename
    if path.exists():
        stem = path.stem
        suffix = path.suffix
        path = output_dir / f"{stem}_{index}{suffix}"
    path.write_bytes(response.content)
    return path


def _download_url(url: str, output_dir: Path, index: int) -> Path:
    if not _is_pmc_download_host(url):
        return _download_url_once(url, output_dir, index)

    last_exc: Exception | None = None
    for attempt in range(1, PMC_DOWNLOAD_RETRY_ATTEMPTS + 1):
        try:
            return _download_url_once(url, output_dir, index)
        except Exception as exc:
            last_exc = exc
            if attempt >= PMC_DOWNLOAD_RETRY_ATTEMPTS or not _is_retryable_pmc_download_error(exc):
                raise
            time.sleep(PMC_DOWNLOAD_RETRY_BASE_DELAY_SECONDS * attempt)

    assert last_exc is not None
    raise last_exc


def _safe_extract_path(base_dir: Path, member_name: str) -> Path:
    base_dir = base_dir.resolve()
    target = (base_dir / member_name).resolve()
    try:
        target.relative_to(base_dir)
    except ValueError:
        raise ValueError(f"Archive member escapes extraction directory: {member_name}")
    return target


def _extract_supported_files(archive_path: Path, output_dir: Path) -> list[Path]:
    extract_dir = output_dir / f"{archive_path.stem}_extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                target = _safe_extract_path(extract_dir, info.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as source, open(target, "wb") as dest:
                    dest.write(source.read())
                if _is_supported_file(target):
                    extracted.append(target)
        return extracted

    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path) as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                target = _safe_extract_path(extract_dir, member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                source = tf.extractfile(member)
                if source is None:
                    continue
                with source, open(target, "wb") as dest:
                    dest.write(source.read())
                if _is_supported_file(target):
                    extracted.append(target)
        return extracted

    return []


def download_pmc_supplements(
    identifier: str,
    identifier_type: str,
    output_dir: str,
) -> tuple[str, list[DownloadedSupplement]]:
    """
    Download PMC supplementary files.

    Returns (pmcid, downloaded_files). The returned file list contains only
    formats supported by the downstream curation parser.
    """
    if identifier_type == "PMID":
        pmcid = pmid_to_pmcid(identifier)
    elif identifier_type == "PMCID":
        pmcid = normalize_pmcid(identifier)
    else:
        raise ValueError("identifier_type must be 'PMID' or 'PMCID'.")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded_paths: list[tuple[Path, str]] = []
    download_errors: list[str] = []

    try:
        for path in _download_oa_package(pmcid, out_dir):
            downloaded_paths.append((path, "PMC OA package"))
    except Exception as exc:
        download_errors.append(f"PMC OA package: {exc}")

    xml_text = ""
    article_html = ""

    try:
        xml_text = _fetch_pmc_xml(pmcid)
    except Exception as exc:
        download_errors.append(f"PMC XML: {exc}")

    try:
        article_html = _fetch_pmc_article_html(pmcid)
    except Exception as exc:
        download_errors.append(f"PMC article HTML: {exc}")

    urls = _discover_supplement_urls(
        pmcid,
        xml_text=xml_text or None,
        article_html=article_html or None,
    )

    for index, url in enumerate(urls, start=1):
        try:
            path = _download_url(url, out_dir, index)
        except Exception as exc:
            download_errors.append(f"{url}: {exc}")
            continue

        paths_to_add: list[Path]
        if _is_archive(path):
            paths_to_add = _extract_supported_files(path, out_dir)
        elif _is_supported_file(path):
            paths_to_add = [path]
        else:
            paths_to_add = []

        for candidate in paths_to_add:
            downloaded_paths.append((candidate, url))

    seen: set[tuple[str, int]] = set()
    downloaded: list[DownloadedSupplement] = []
    for path, source_url in downloaded_paths:
        try:
            signature = (path.name.lower(), path.stat().st_size)
        except OSError:
            continue
        if signature in seen:
            continue
        seen.add(signature)
        downloaded.append(
            DownloadedSupplement(
                path=str(path),
                filename=path.name,
                source_url=source_url,
            )
        )

    if not downloaded:
        detail = ""
        if download_errors:
            detail = " Download attempts failed; first error: " + download_errors[0]
        raise ValueError(
            f"No supported supplementary files could be downloaded for {pmcid}. "
            "Supported formats are .xlsx, .csv, .tsv, .txt, .maf, .docx, and .pdf."
            f"{detail}"
        )

    return pmcid, downloaded
