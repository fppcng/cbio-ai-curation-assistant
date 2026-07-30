"""PMC payload validation, downloading, and supplement collection."""

from __future__ import annotations

import http.cookiejar
import os
import re
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

import requests

from cbio_curation_assistant.integrations.pmc.archives import (
    extract_supported_files,
    is_archive,
    is_supported_file,
)
from cbio_curation_assistant.integrations.pmc.client import (
    HTTP_HEADERS,
    NCBI_TIMEOUT_SECONDS,
    classify_pmc_error,
    fetch_pmc_article_html,
    fetch_pmc_xml,
    lookup_oa_package_url,
)
from cbio_curation_assistant.integrations.pmc.discovery import (
    discover_supplement_urls,
)
from cbio_curation_assistant.integrations.pmc.identifiers import (
    normalize_pmcid,
)
from cbio_curation_assistant.integrations.pmc.models import (
    DownloadedSupplement,
)
from cbio_curation_assistant.integrations.pmc.proof_of_work import (
    parse_proof_of_work_challenge,
    set_proof_of_work_cookie,
    solve_proof_of_work_nonce,
)
from cbio_curation_assistant.supplements.formats import (
    ARCHIVE_EXTENSIONS,
    SUPPORTED_SUPPLEMENT_EXTENSIONS,
)


PMC_DOWNLOAD_RETRY_ATTEMPTS = 3
PMC_DOWNLOAD_RETRY_BASE_DELAY_SECONDS = 1.0


def filename_extension(name: str) -> str:
    lower = name.lower()
    for compound_suffix in (".tar.gz", ".tar.bz2", ".tar.xz"):
        if lower.endswith(compound_suffix):
            return compound_suffix
    return Path(lower).suffix.lower()


def looks_like_html_payload(content: bytes) -> bool:
    prefix = content[:4096].lstrip().lower()
    return (
        prefix.startswith(b"<!doctype html")
        or prefix.startswith(b"<html")
        or prefix.startswith(b"<head")
        or prefix.startswith(b"<body")
        or b"<title>preparing to download" in prefix
        or b"pow_challenge" in prefix
    )


def validate_downloaded_content(
    filename: str,
    content_type: str,
    content: bytes,
) -> None:
    if not content:
        raise ValueError(f"Downloaded content for {filename} was empty.")

    normalized_content_type = (content_type or "").lower()
    if (
        "text/html" in normalized_content_type
        or looks_like_html_payload(content)
    ):
        raise ValueError(f"PMC returned an HTML page instead of {filename}.")

    extension = filename_extension(filename)
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise ValueError(
            f"Downloaded content for {filename} was not a PDF."
        )
    if (
        extension in {".zip", ".docx", ".xlsx"}
        and not content.startswith(b"PK")
    ):
        raise ValueError(
            f"Downloaded content for {filename} was not a ZIP-based document."
        )
    if (
        extension in {".gz", ".tgz", ".tar.gz"}
        and not content.startswith(b"\x1f\x8b")
    ):
        raise ValueError(
            f"Downloaded content for {filename} was not a gzip archive."
        )
    if extension == ".bz2" and not content.startswith(b"BZh"):
        raise ValueError(
            f"Downloaded content for {filename} was not a bzip2 archive."
        )
    if (
        extension in {".xz", ".tar.xz"}
        and not content.startswith(b"\xfd7zXZ\x00")
    ):
        raise ValueError(
            f"Downloaded content for {filename} was not an xz archive."
        )


def safe_filename(filename: str, fallback: str) -> str:
    name = unquote(filename or "").strip()
    name = os.path.basename(name)
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return name or fallback


def filename_from_headers(
    url: str,
    disposition: str,
    index: int,
) -> str:
    match = re.search(
        r'filename="?([^";]+)"?',
        disposition,
        flags=re.IGNORECASE,
    )
    if match:
        return safe_filename(match.group(1), f"supplement_{index}")

    parsed_name = os.path.basename(urlparse(url).path)
    return safe_filename(parsed_name, f"supplement_{index}")


def filename_from_response(
    url: str,
    response: requests.Response,
    index: int,
) -> str:
    return filename_from_headers(
        url,
        response.headers.get("content-disposition", ""),
        index,
    )


def download_with_proof_of_work(
    url: str,
    output_dir: Path,
    index: int,
) -> Path:
    cookie_jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    request = Request(url, headers=HTTP_HEADERS)

    try:
        response = opener.open(request, timeout=NCBI_TIMEOUT_SECONDS)
    except HTTPError as exc:
        response = exc

    content = response.read()
    content_type = response.headers.get("content-type", "").lower()
    filename = filename_from_headers(
        url,
        response.headers.get("content-disposition", ""),
        index,
    )

    if "text/html" in content_type:
        html = content.decode("utf-8", errors="replace")
        proof = parse_proof_of_work_challenge(html)
        if proof:
            challenge, difficulty, cookie_name, cookie_path = proof
            nonce = solve_proof_of_work_nonce(challenge, difficulty)
            set_proof_of_work_cookie(
                cookie_jar,
                url,
                cookie_name,
                f"{challenge},{nonce}",
                cookie_path,
            )

            response = opener.open(
                Request(url, headers=HTTP_HEADERS),
                timeout=NCBI_TIMEOUT_SECONDS,
            )
            content = response.read()
            content_type = response.headers.get(
                "content-type",
                "",
            ).lower()
            filename = filename_from_headers(
                url,
                response.headers.get("content-disposition", ""),
                index,
            )

    validate_downloaded_content(filename, content_type, content)

    path = output_dir / filename
    if path.exists():
        stem = path.stem
        suffix = path.suffix
        path = output_dir / f"{stem}_{index}{suffix}"
    path.write_bytes(content)
    return path


def is_pmc_download_host(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    return hostname in {
        "pmc.ncbi.nlm.nih.gov",
        "www.ncbi.nlm.nih.gov",
        "ftp.ncbi.nlm.nih.gov",
    }


def is_retryable_pmc_download_error(exc: Exception) -> bool:
    return classify_pmc_error(exc).retryable


def download_file_once(
    url: str,
    output_dir: Path,
    index: int,
) -> Path:
    try:
        response = requests.get(
            url,
            headers=HTTP_HEADERS,
            timeout=NCBI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except Exception:
        if is_pmc_download_host(url):
            return download_with_proof_of_work(url, output_dir, index)
        raise

    content_type = response.headers.get("content-type", "").lower()
    filename = filename_from_response(url, response, index)
    if (
        "text/html" in content_type
        and Path(filename).suffix.lower()
        in (SUPPORTED_SUPPLEMENT_EXTENSIONS | ARCHIVE_EXTENSIONS)
    ):
        if is_pmc_download_host(url):
            return download_with_proof_of_work(url, output_dir, index)
        raise ValueError(
            f"PMC returned an HTML challenge page instead of {filename}."
        )

    validate_downloaded_content(
        filename,
        content_type,
        response.content,
    )

    path = output_dir / filename
    if path.exists():
        stem = path.stem
        suffix = path.suffix
        path = output_dir / f"{stem}_{index}{suffix}"
    path.write_bytes(response.content)
    return path


def download_file(url: str, output_dir: Path, index: int) -> Path:
    if not is_pmc_download_host(url):
        return download_file_once(url, output_dir, index)

    last_exc: Exception | None = None
    for attempt in range(1, PMC_DOWNLOAD_RETRY_ATTEMPTS + 1):
        try:
            return download_file_once(url, output_dir, index)
        except Exception as exc:
            last_exc = exc
            if (
                attempt >= PMC_DOWNLOAD_RETRY_ATTEMPTS
                or not is_retryable_pmc_download_error(exc)
            ):
                raise
            time.sleep(PMC_DOWNLOAD_RETRY_BASE_DELAY_SECONDS * attempt)

    assert last_exc is not None
    raise last_exc


def download_oa_package_files(
    pmcid: str,
    output_dir: Path,
) -> list[Path]:
    package_url = lookup_oa_package_url(pmcid)
    if not package_url:
        return []

    package_path = download_file(package_url, output_dir, 0)
    extracted = extract_supported_files(package_path, output_dir)
    return [
        path
        for path in extracted
        if path.name.lower() != f"{normalize_pmcid(pmcid).lower()}.pdf"
    ]


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
    from cbio_curation_assistant.integrations.pmc.client import pmid_to_pmcid

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
        for path in download_oa_package_files(pmcid, out_dir):
            downloaded_paths.append((path, "PMC OA package"))
    except Exception as exc:
        download_errors.append(f"PMC OA package: {exc}")

    xml_text = ""
    article_html = ""

    try:
        xml_text = fetch_pmc_xml(pmcid)
    except Exception as exc:
        download_errors.append(f"PMC XML: {exc}")

    try:
        article_html = fetch_pmc_article_html(pmcid)
    except Exception as exc:
        download_errors.append(f"PMC article HTML: {exc}")

    urls = discover_supplement_urls(
        pmcid,
        xml_text=xml_text or None,
        article_html=article_html or None,
    )

    for index, url in enumerate(urls, start=1):
        try:
            path = download_file(url, out_dir, index)
        except Exception as exc:
            download_errors.append(f"{url}: {exc}")
            continue

        if is_archive(path):
            paths_to_add = extract_supported_files(path, out_dir)
        elif is_supported_file(path):
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
            detail = (
                " Download attempts failed; first error: "
                + download_errors[0]
            )
        raise ValueError(
            f"No supported supplementary files could be downloaded for {pmcid}. "
            "Supported formats are .xlsx, .csv, .tsv, .txt, .maf, .docx, and .pdf."
            f"{detail}"
        )

    return pmcid, downloaded


__all__ = [
    "PMC_DOWNLOAD_RETRY_ATTEMPTS",
    "PMC_DOWNLOAD_RETRY_BASE_DELAY_SECONDS",
    "download_file",
    "download_oa_package_files",
    "download_pmc_supplements",
    "validate_downloaded_content",
]
