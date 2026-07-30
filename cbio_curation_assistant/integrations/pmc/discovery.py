"""Pure discovery of PMC supplement and article PDF links."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from cbio_curation_assistant.integrations.pmc.identifiers import (
    normalize_pmcid,
    pmcid_numeric,
)
from cbio_curation_assistant.supplements.formats import (
    ARCHIVE_EXTENSIONS,
    SUPPORTED_SUPPLEMENT_EXTENSIONS,
)


def _xlink_href(element: ET.Element) -> str:
    return (
        element.attrib.get("{http://www.w3.org/1999/xlink}href")
        or element.attrib.get("href")
        or ""
    ).strip()


def discover_supplement_urls_from_xml(
    pmcid: str,
    xml_text: str,
) -> list[str]:
    root = ET.fromstring(xml_text)
    urls: list[str] = []
    normalized_pmcid = normalize_pmcid(pmcid)
    base_article_url = (
        f"https://pmc.ncbi.nlm.nih.gov/articles/{normalized_pmcid}/"
    )
    base_site_url = "https://pmc.ncbi.nlm.nih.gov"
    base_instance_bin_url = (
        "https://pmc.ncbi.nlm.nih.gov/articles/instance/"
        f"{pmcid_numeric(normalized_pmcid)}/bin/"
    )

    for supplement in root.iter():
        if not supplement.tag.endswith("supplementary-material"):
            continue

        candidate_hrefs = []
        direct_href = _xlink_href(supplement)
        if direct_href:
            candidate_hrefs.append(direct_href)

        for child in supplement.iter():
            if child.tag.endswith(
                ("media", "graphic", "inline-supplementary-material")
            ):
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

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return
        attr_map = {
            key.lower(): (value or "").strip()
            for key, value in attrs
        }
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


def discover_supplement_urls_from_html(
    pmcid: str,
    html_text: str,
) -> list[str]:
    normalized_pmcid = normalize_pmcid(pmcid)
    instance_prefix = (
        f"/articles/instance/{pmcid_numeric(normalized_pmcid)}/bin/"
    )
    article_base_url = (
        f"https://pmc.ncbi.nlm.nih.gov/articles/{normalized_pmcid}/"
    )
    urls: list[str] = []

    for link in _article_html_links(html_text):
        href = link.get("href", "")
        data_ga_action = link.get("data-ga-action", "").lower()
        if not href:
            continue

        href_path = urlparse(href).path or href
        suffix = _filename_extension(href_path)
        if suffix not in (
            SUPPORTED_SUPPLEMENT_EXTENSIONS | ARCHIVE_EXTENSIONS
        ):
            continue
        if (
            instance_prefix not in href_path
            and data_ga_action != "click_feat_suppl"
        ):
            continue

        urls.append(urljoin(article_base_url, href))

    return _dedupe_preserve_order(urls)


def discover_supplement_urls(
    pmcid: str,
    *,
    xml_text: str | None = None,
    article_html: str | None = None,
) -> list[str]:
    discovered: list[str] = []
    if xml_text:
        discovered.extend(
            discover_supplement_urls_from_xml(pmcid, xml_text)
        )
    if article_html:
        discovered.extend(
            discover_supplement_urls_from_html(pmcid, article_html)
        )
    return _dedupe_preserve_order(discovered)


def discover_article_pdf_url(
    pmcid: str,
    html_text: str,
) -> str | None:
    normalized_pmcid = normalize_pmcid(pmcid)
    article_base_url = (
        f"https://pmc.ncbi.nlm.nih.gov/articles/{normalized_pmcid}/"
    )

    for link in _article_html_links(html_text):
        href = link.get("href", "")
        if not href:
            continue

        href_path = (urlparse(href).path or href).lower()
        if not href_path.endswith(".pdf"):
            continue
        if (
            f"/articles/{normalized_pmcid.lower()}/pdf/" in href_path
            or href_path.startswith("/pdf/")
        ):
            return urljoin(article_base_url, href)
    return None


__all__ = [
    "discover_article_pdf_url",
    "discover_supplement_urls",
    "discover_supplement_urls_from_html",
    "discover_supplement_urls_from_xml",
]
