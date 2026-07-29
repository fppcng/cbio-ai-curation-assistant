"""
Shared helpers used by the modern curation report generator.

This module is intentionally limited to the code paths exercised by
`hermes_skills/abstractor-curation-report-generation/scripts/abstractor_report_generator.py`:

1. Extract text from the paper PDF.
2. Extract study metadata with the LLM prompt plus regex fallback.
3. Read supplementary files into sheet-like DataFrames.
4. Classify each sheet into a cBioPortal-oriented record consumed by the report.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from cbio_curation_assistant.cbioportal import specification_sources
from cbio_curation_assistant.cbioportal.classification import (
    ClassificationResult,
    classify_sheet,
)
from cbio_curation_assistant.config import LLMConfig
from cbio_curation_assistant.llm_client import call_llm_with_retry, parse_llm_json
from cbio_curation_assistant.pdf_metadata_regex import (
    extract_metadata_regex as _extract_metadata_regex,
)
from cbio_curation_assistant.supplements.models import SupplementaryClassification
from cbio_curation_assistant.supplements.readers import read_supplementary_file

CURABILITY = {
    "CLINICAL_PATIENT": ("YES", "HIGH"),
    "CLINICAL_SAMPLE": ("YES", "HIGH"),
    "MUTATION_MAF": ("PARTIAL", "HIGH"),
    "STRUCTURAL_VARIANT": ("YES", "HIGH"),
    "DISCRETE_CNA": ("PARTIAL", "MEDIUM"),
    "CONTINUOUS_CNA": ("PARTIAL", "MEDIUM"),
    "SEGMENTED": ("PARTIAL", "MEDIUM"),
    "EXPRESSION": ("PARTIAL", "MEDIUM"),
    "METHYLATION": ("PARTIAL", "LOW"),
    "MUTSIG": ("PARTIAL", "MEDIUM"),
    "GISTIC": ("PARTIAL", "MEDIUM"),
    "GENERIC_ASSAY": ("PARTIAL", "LOW"),
    "NOT_LOADABLE": ("NO", "N/A"),
}

SYSTEM_PROMPT_CURATOR = """
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


def extract_pdf_text(pdf_path: str, max_pages: int = 12) -> str:
    """Extract text from the leading pages of a paper PDF with pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    pages = reader.pages[:max_pages]
    return "\n".join(page.extract_text() or "" for page in pages)


def _extract_metadata_llm(pdf_text: str, llm_config: LLMConfig, temperature: float) -> dict[str, Any]:
    _ = temperature
    raw = call_llm_with_retry(
        config=llm_config,
        system=SYSTEM_PROMPT_CURATOR,
        user_content=pdf_text[:12000],
        max_tokens=2000,
    ).strip()
    try:
        llm_data = parse_llm_json(raw)
    except Exception as exc:
        logging.warning("LLM JSON parse failed (%s); using regex fallback.", exc)
        llm_data = {}

    fallback = _extract_metadata_regex(pdf_text)
    merged = {**fallback}
    for key, value in llm_data.items():
        if value and value not in ("?", "...", "Unknown", "mixed", "study_2024", ""):
            merged[key] = value
    return merged


def _build_report_record(
    cr: ClassificationResult,
    *,
    file_name: str,
    sheet_name: str,
) -> SupplementaryClassification:
    curability, priority = CURABILITY.get(cr.format_key, ("NO", "N/A"))
    return SupplementaryClassification(
        file=file_name,
        sheet=sheet_name,
        classification=cr.format_key,
        cbio_target_file=cr.target_file,
        curability=curability,
        priority=priority,
        confidence=cr.confidence,
        verdict=cr.verdict,
        required_present=tuple(cr.required_present),
        required_missing=tuple(cr.required_missing),
        optional_present=tuple(cr.optional_present),
    )


def _build_failed_supplementary_record(
    file_name: str,
    sheet_name: str,
    error: Exception,
) -> SupplementaryClassification:
    return SupplementaryClassification(
        file=file_name,
        sheet=sheet_name,
        classification="NOT_LOADABLE",
        cbio_target_file=None,
        curability="NO",
        priority="N/A",
        confidence=0,
        verdict=f"Parse error: {error}",
        load_error=str(error),
    )


def analyse_supplementary_files(
    supp_paths: Sequence[str | Path],
    *,
    warnings: list[str] | None = None,
) -> list[SupplementaryClassification]:
    """Inspect each sheet in each supplementary file and return report records."""
    records: list[SupplementaryClassification] = []
    specification_result: dict[str, Any] | None = None
    for path in supp_paths:
        file_name = Path(path).name
        try:
            read_result = read_supplementary_file(path)
        except Exception as exc:
            records.append(_build_failed_supplementary_record(file_name, "-", exc))
            continue

        for warning in read_result.warnings:
            message = f"{file_name}: {warning}"
            logging.warning("%s", message)
            if warnings is not None:
                warnings.append(message)

        for sheet_name, df in read_result.sheets.items():
            try:
                if specification_result is None:
                    specification_result = specification_sources.get_embedded_spec()
                record = _build_report_record(
                    classify_sheet(
                        df,
                        specification_result["specs"],
                        spec_source=specification_result["source"],
                        spec_fetched_at=specification_result.get(
                            "fetched_at", "unknown"
                        ),
                        spec_version=specification_result.get("version", "unknown"),
                    ),
                    file_name=file_name,
                    sheet_name=sheet_name,
                )
            except Exception as exc:
                records.append(_build_failed_supplementary_record(file_name, sheet_name, exc))
                continue

            records.append(record)

    return records


def _read_file_as_sheets(path: str) -> dict[str, Any]:
    """Compatibility wrapper; use supplements.readers.read_supplementary_file."""
    return read_supplementary_file(path).sheets


_analyse_supplementary_files = analyse_supplementary_files
_extract_pdf_text = extract_pdf_text


__all__ = [
    "SYSTEM_PROMPT_CURATOR",
    "analyse_supplementary_files",
    "extract_pdf_text",
    "_analyse_supplementary_files",
    "_extract_metadata_llm",
    "_extract_pdf_text",
    "_read_file_as_sheets",
]
