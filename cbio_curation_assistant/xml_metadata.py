from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


METADATA_DEFAULTS = {
    "study_title": None,
    "cancer_type": None,
    "cancer_type_full": None,
    "num_samples": None,
    "num_patients": None,
    "reference_genome": None,
    "sequencing_types": [],
    "pmid": None,
    "doi": None,
    "first_author_surname": None,
    "year": None,
    "journal": None,
    "study_id_suggestion": None,
    "description": None,
    "key_findings": [],
    "primary_site": None,
    "cohort_description": None,
    "meta_description": None,
    "data_repositories": [],
    "corresponding_authors": None,
}


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _xml_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    text_parts = [text.strip() for text in element.itertext() if text.strip()]
    return re.sub(r"\s+", " ", " ".join(text_parts)).strip()


def _first_xml_text(root: ET.Element, local_names: tuple[str, ...]) -> str:
    for local_name in local_names:
        for element in root.iter():
            if _xml_local_name(element.tag) != local_name:
                continue
            text = _xml_text(element)
            if text:
                return text
    return ""


def _first_child(element: ET.Element | None, local_name: str) -> ET.Element | None:
    if element is None:
        return None
    for child in element:
        if _xml_local_name(child.tag) == local_name:
            return child
    return None


def _first_descendant(element: ET.Element | None, local_name: str) -> ET.Element | None:
    if element is None:
        return None
    for child in element.iter():
        if _xml_local_name(child.tag) == local_name:
            return child
    return None


def _article_root(root: ET.Element) -> ET.Element:
    if _xml_local_name(root.tag) == "article":
        return root
    for element in root.iter():
        if _xml_local_name(element.tag) == "article":
            return element
    return root


def _article_meta(article: ET.Element) -> ET.Element | None:
    front = _first_child(article, "front")
    return _first_child(front, "article-meta")


def _journal_meta(article: ET.Element) -> ET.Element | None:
    front = _first_child(article, "front")
    return _first_child(front, "journal-meta")


def _xml_article_ids(root: ET.Element) -> dict[str, str]:
    ids: dict[str, str] = {}
    for element in root.iter():
        if _xml_local_name(element.tag) != "article-id":
            continue
        id_type = (
            element.attrib.get("pub-id-type")
            or element.attrib.get("article-id-type")
            or ""
        ).lower()
        text = _xml_text(element).rstrip(".,;")
        if id_type and text:
            ids[id_type] = text
    return ids


def _xml_journal_title(root: ET.Element) -> str:
    journal_title = _first_descendant(root, "journal-title")
    if journal_title is not None:
        return _xml_text(journal_title)

    for journal_id in root.iter():
        if _xml_local_name(journal_id.tag) != "journal-id":
            continue
        if journal_id.attrib.get("journal-id-type") in {"nlm-ta", "iso-abbrev"}:
            return _xml_text(journal_id)

    return _first_xml_text(root, ("journal-id",))


def _xml_publication_year(root: ET.Element) -> str:
    for pub_date in root.iter():
        if _xml_local_name(pub_date.tag) != "pub-date":
            continue
        for child in pub_date:
            if _xml_local_name(child.tag) == "year":
                year = _xml_text(child)
                if year:
                    return year
    return _first_xml_text(root, ("year",))


def _xml_first_author_surname(root: ET.Element) -> str:
    for contrib in root.iter():
        if _xml_local_name(contrib.tag) != "contrib":
            continue
        contrib_type = contrib.attrib.get("contrib-type", "")
        if contrib_type and contrib_type != "author":
            continue
        for child in contrib.iter():
            if _xml_local_name(child.tag) == "surname":
                surname = _xml_text(child)
                if surname:
                    return surname
    return ""


def _xml_corresponding_authors(root: ET.Element) -> str:
    values: list[str] = []
    for contrib in root.iter():
        if _xml_local_name(contrib.tag) != "contrib":
            continue
        is_corresp = contrib.attrib.get("corresp", "").lower() in {"yes", "true"}
        emails = [
            _xml_text(child)
            for child in contrib.iter()
            if _xml_local_name(child.tag) == "email" and _xml_text(child)
        ]
        if not is_corresp and not emails:
            continue
        names = [
            _xml_text(child)
            for child in contrib.iter()
            if _xml_local_name(child.tag) == "name" and _xml_text(child)
        ]
        value = ", ".join(names + emails)
        if value and value not in values:
            values.append(value)

    for corresp in root.iter():
        if _xml_local_name(corresp.tag) != "corresp":
            continue
        text = _xml_text(corresp)
        if text and text not in values:
            values.append(text)

    return "; ".join(values)


def _parse_xml_root(xml_source: str | bytes | Path) -> ET.Element:
    
    if isinstance(xml_source, bytes):
        return ET.fromstring(xml_source)

    if isinstance(xml_source, Path):
        return ET.parse(xml_source).getroot()

    source = str(xml_source)
    if source.lstrip().startswith("<"):
        return ET.fromstring(source)
    return ET.parse(source).getroot()


def _xml_article_title(article_meta: ET.Element | None) -> str:
    title_group = _first_child(article_meta, "title-group")
    article_title = _first_child(title_group, "article-title")
    return _xml_text(article_title)


def _xml_abstract(article_meta: ET.Element | None) -> str:
    abstract = _first_child(article_meta, "abstract")
    return _xml_text(abstract)


def _xml_body(article: ET.Element) -> str:
    body = _first_child(article, "body")
    return _xml_text(body)


def _first_sentence(text: str) -> str:
    if not text:
        return ""
    head, separator, _tail = text.partition(". ")
    return f"{head}." if separator else text


def extract_xml_text(xml_source: str | bytes | Path) -> str:
    """
    Extract readable article text from a PMC/JATS-like XML document.

    Accepts XML text, bytes, or a filesystem path. The returned text is useful
    for inspection/debugging and is scoped to the first article in the XML.
    """
    root = _parse_xml_root(xml_source)
    article = _article_root(root)
    sections: list[str] = []
    preferred_tags = {
        "article-title",
        "abstract",
        "kwd-group",
        "body",
        "back",
    }

    for element in article.iter():
        if _xml_local_name(element.tag) not in preferred_tags:
            continue
        text = _xml_text(element)
        if text and text not in sections:
            sections.append(text)

    if not sections:
        sections.append(_xml_text(root))

    return "\n".join(sections)


def extract_xml_llm_text(xml_source: str | bytes | Path) -> str:
    """
    Extract clean article text for LLM completion from JATS XML.

    Includes only title, abstract, and body from the first article. It excludes
    back matter/references to avoid contaminating metadata extraction.
    """
    root = _parse_xml_root(xml_source)
    article = _article_root(root)
    article_meta = _article_meta(article)

    sections = [
        ("Title", _xml_article_title(article_meta)),
        ("Abstract", _xml_abstract(article_meta)),
        ("Body", _xml_body(article)),
    ]
    return "\n\n".join(
        f"{label}\n{text}"
        for label, text in sections
        if text
    )


def extract_metadata_from_xml(xml_source: str | bytes | Path) -> dict:
    """
    Extract study metadata from PMC/JATS XML without using PDF text or an LLM.

    Only structured JATS fields are used. Values that are not represented as
    dedicated article metadata in JATS are left blank/default for now.
    """
    root = _parse_xml_root(xml_source)
    article = _article_root(root)
    article_meta = _article_meta(article)
    journal_meta = _journal_meta(article)
    article_scope = article_meta if article_meta is not None else article
    journal_scope = journal_meta if journal_meta is not None else article
    meta = dict(METADATA_DEFAULTS)

    abstract = _xml_abstract(article_meta)
    description = _first_sentence(abstract)
    article_ids = _xml_article_ids(article_scope)
    structured = {
        "study_title": _xml_article_title(article_meta),
        "journal": _xml_journal_title(journal_scope),
        "year": _xml_publication_year(article_scope),
        "pmid": article_ids.get("pmid", ""),
        "doi": article_ids.get("doi", ""),
        "first_author_surname": _xml_first_author_surname(article_scope),
        "description": description,
        "meta_description": description[:200],
        "corresponding_authors": _xml_corresponding_authors(article_scope),
    }

    for key, value in structured.items():
        if value:
            meta[key] = value

    author = meta.get("first_author_surname", "")
    year = meta.get("year", "")
    cancer_t = meta.get("cancer_type")
    if cancer_t and author and year:
        study_id = f"{cancer_t}_{author.lower()}_{year}"
    elif author and year:
        study_id = f"study_{author.lower()}_{year}"
    else:
        study_id = ""
    if study_id:
        meta["study_id_suggestion"] = re.sub(r"[^a-z0-9_]", "_", study_id).strip("_")

    return meta
