"""Optional LLM completion layered over deterministic publication extraction."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from cbio_curation_assistant.llm import LLMConfig, complete_text, parse_llm_json
from cbio_curation_assistant.publications.metadata import (
    merge_missing_metadata_fields,
)
from cbio_curation_assistant.publications.models import PublicationMetadata
from cbio_curation_assistant.publications.pdf import (
    extract_metadata_regex,
    extract_pdf_text,
)
from cbio_curation_assistant.publications.xml import (
    extract_metadata_from_xml,
    extract_xml_llm_text,
)


PUBLICATION_METADATA_PROMPT = """
You are an expert bioinformatics data curator specialising in the cBioPortal
platform (https://docs.cbioportal.org/file-formats/).

When given text extracted from a cancer genomics paper, extract the following
study metadata and return it as a JSON object with exactly these keys:

{
  "study_title": "...",
  "cancer_type": "...",           // short abbreviation e.g. brca, gist, luad
  "cancer_type_full": "...",      // e.g. Breast Invasive Carcinoma
  "num_samples": "...",           // integer or string
  "num_patients": "...",          // integer or string
  "reference_genome": "...",      // hg19 or hg38
  "sequencing_types": ["..."],    // e.g. ["WES","WGS","WTS"]
  "pmid": "...",                  // PubMed ID if mentioned
  "doi": "...",                   // DOI string
  "first_author_surname": "...",
  "year": "...",
  "journal": "...",
  "study_id_suggestion": "...",   // snake_case e.g. gist_xie_2024
  "description": "...",           // one sentence
  "key_findings": ["..."],        // up to 5 bullet points
  "primary_site": "...",          // anatomical site e.g. "Stomach and small intestine"
  "cohort_description": "...",    // one sentence describing the cohort composition
  "meta_description": "...",      // concise description for meta_study.txt (200 chars max)
  "data_repositories": ["..."],   // GEO/GDC/SRA accession strings mentioned in paper
  "corresponding_authors": "..."  // name and email of corresponding authors if mentioned
}

Return ONLY the JSON — no markdown fences, no extra text.
"""


def complete_pdf_metadata(
    pdf_text: str,
    llm_config: LLMConfig,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Complete regex-derived PDF metadata with an LLM response."""
    _ = temperature
    raw = complete_text(
        config=llm_config,
        system=PUBLICATION_METADATA_PROMPT,
        user_content=pdf_text[:12000],
        max_tokens=2000,
    ).strip()
    try:
        llm_data = parse_llm_json(raw)
    except Exception as exc:
        logging.warning("LLM JSON parse failed (%s); using regex fallback.", exc)
        llm_data = {}

    merged = extract_metadata_regex(pdf_text)
    for key, value in llm_data.items():
        if value and value not in ("?", "...", "Unknown", "mixed", "study_2024", ""):
            merged[key] = value
    return merged


def extract_pdf_metadata_with_llm(
    pdf_source: str | Path,
    llm_config: LLMConfig | None,
    warnings: list[str],
    *,
    logger: logging.Logger | None = None,
) -> PublicationMetadata:
    """Extract report metadata from PDF text using the existing LLM contract."""
    pdf_text = extract_pdf_text(pdf_source)
    if not pdf_text.strip():
        warnings.append(
            "Could not extract text from the PDF. Metadata fields will be blank."
        )
        return PublicationMetadata()

    if llm_config is None:
        warnings.append(
            "No Hermes LLM configuration is available. "
            "PDF metadata fields will be blank."
        )
        return PublicationMetadata()

    try:
        return PublicationMetadata.from_mapping(
            complete_pdf_metadata(pdf_text, llm_config, temperature=0.2)
        )
    except Exception as exc:
        (logger or logging.getLogger(__name__)).exception(
            "PDF metadata extraction failed for %s",
            pdf_source,
        )
        warnings.append(f"Metadata extraction failed: {exc}")
        return PublicationMetadata()


def extract_xml_metadata_with_llm(
    xml_source: str | Path,
    llm_config: LLMConfig | None,
    warnings: list[str],
    *,
    logger: logging.Logger | None = None,
    missing_text_warning: str,
    missing_llm_warning: str,
    completion_failure_warning: str,
) -> dict[str, Any]:
    """Complete only metadata fields missing from structured JATS extraction."""
    metadata = extract_metadata_from_xml(xml_source)
    llm_text = extract_xml_llm_text(xml_source)

    if not llm_text.strip():
        warnings.append(missing_text_warning)
        return metadata

    if llm_config is None:
        warnings.append(missing_llm_warning)
        return metadata

    active_logger = logger or logging.getLogger(__name__)
    raw_metadata = ""
    try:
        raw_metadata = complete_text(
            config=llm_config,
            system=PUBLICATION_METADATA_PROMPT,
            user_content=llm_text[:40000],
            max_tokens=2000,
        )
        return merge_missing_metadata_fields(
            metadata,
            parse_llm_json(raw_metadata),
        )
    except Exception:
        active_logger.exception(
            "XML metadata completion failed: "
            "provider=%s model=%s api_mode=%s base_url=%s raw_meta=%r",
            llm_config.provider,
            llm_config.model,
            llm_config.api_mode,
            llm_config.base_url,
            raw_metadata[:2000],
        )
        warnings.append(completion_failure_warning)
        return metadata


__all__ = [
    "PUBLICATION_METADATA_PROMPT",
    "complete_pdf_metadata",
    "extract_pdf_metadata_with_llm",
    "extract_xml_metadata_with_llm",
]
