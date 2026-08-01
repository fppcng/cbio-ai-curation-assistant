"""Construct curation-report data from publication and supplement results."""

from __future__ import annotations

import collections
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from cbio_curation_assistant.cbioportal import specification_sources
from cbio_curation_assistant.cbioportal.classification import (
    ClassificationResult,
    classify_sheet,
)
from cbio_curation_assistant.publications.models import PublicationMetadata
from cbio_curation_assistant.reports.models import (
    CurationSummary,
    ReportBreakdownRow,
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


def _build_report_record(
    classification: ClassificationResult,
    *,
    file_name: str,
    sheet_name: str,
) -> SupplementaryClassification:
    curability, priority = CURABILITY.get(
        classification.format_key,
        ("NO", "N/A"),
    )
    return SupplementaryClassification(
        file=file_name,
        sheet=sheet_name,
        classification=classification.format_key,
        cbio_target_file=classification.target_file,
        curability=curability,
        priority=priority,
        confidence=classification.confidence,
        verdict=classification.verdict,
        required_present=tuple(classification.required_present),
        required_missing=tuple(classification.required_missing),
        optional_present=tuple(classification.optional_present),
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
    supplementary_paths: Sequence[str | Path],
    *,
    warnings: list[str] | None = None,
) -> tuple[SupplementaryClassification, ...]:
    """Read and classify each sheet in the selected supplementary files."""
    records: list[SupplementaryClassification] = []
    specification_result = None
    for path in supplementary_paths:
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

        for sheet_name, dataframe in read_result.sheets.items():
            try:
                if specification_result is None:
                    specification_result = specification_sources.get_embedded_spec()
                record = _build_report_record(
                    classify_sheet(
                        dataframe,
                        specification_result["specs"],
                        spec_source=specification_result["source"],
                        spec_fetched_at=specification_result.get(
                            "fetched_at",
                            "unknown",
                        ),
                        spec_version=specification_result.get(
                            "version",
                            "unknown",
                        ),
                    ),
                    file_name=file_name,
                    sheet_name=sheet_name,
                )
            except Exception as exc:
                records.append(
                    _build_failed_supplementary_record(
                        file_name,
                        sheet_name,
                        exc,
                    )
                )
                continue
            records.append(record)

    return tuple(records)


def _build_breakdown_row(
    row: SupplementaryClassification,
) -> ReportBreakdownRow:
    return ReportBreakdownRow(
        file=row.file or "—",
        sheet=row.sheet or "—",
        cbio_format=row.cbio_target_file or "—",
        curability=row.curability,
        priority=row.priority,
        confidence=row.confidence,
        verdict=row.verdict,
        required_present=row.required_present,
        required_missing=row.required_missing,
        optional_present=row.optional_present,
    )


def _merge_breakdown_values(
    rows: Sequence[SupplementaryClassification],
    key: Literal[
        "required_present",
        "required_missing",
        "optional_present",
    ],
) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for value in getattr(row, key):
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            values.append(text)
    return tuple(values)


def _build_aggregated_pdf_breakdown_row(
    rows: Sequence[SupplementaryClassification],
) -> ReportBreakdownRow:
    first_row = rows[0]
    return ReportBreakdownRow(
        file=first_row.file or "—",
        sheet=f"PDF (aggregated {len(rows)} sections)",
        cbio_format="Not directly loadable",
        curability="NO",
        priority="N/A",
        confidence=max(row.confidence for row in rows),
        verdict=(
            f"Aggregated {len(rows)} PDF sections that require manual intervention."
            if len(rows) > 1
            else first_row.verdict
        ),
        required_present=_merge_breakdown_values(rows, "required_present"),
        required_missing=_merge_breakdown_values(rows, "required_missing"),
        optional_present=_merge_breakdown_values(rows, "optional_present"),
    )


def _build_report_breakdown(
    records: Sequence[SupplementaryClassification],
) -> tuple[ReportBreakdownRow, ...]:
    pdf_rows_by_file: dict[str, list[SupplementaryClassification]] = (
        collections.defaultdict(list)
    )
    for row in records:
        if row.file.lower().endswith(".pdf"):
            pdf_rows_by_file[row.file].append(row)

    manual_pdf_rows_by_file = {
        file_name: [row for row in rows if row.curability.upper() == "NO"]
        for file_name, rows in pdf_rows_by_file.items()
    }
    aggregated_pdf_files = {
        file_name for file_name, rows in manual_pdf_rows_by_file.items() if rows
    }

    breakdown: list[ReportBreakdownRow] = []
    emitted_pdf_files: set[str] = set()
    for row in records:
        is_manual_pdf_row = row.curability.upper() == "NO"
        if row.file in aggregated_pdf_files and is_manual_pdf_row:
            if row.file in emitted_pdf_files:
                continue
            breakdown.append(
                _build_aggregated_pdf_breakdown_row(manual_pdf_rows_by_file[row.file])
            )
            emitted_pdf_files.add(row.file)
            continue
        breakdown.append(_build_breakdown_row(row))
    return tuple(breakdown)


def build_curation_summary(
    metadata: PublicationMetadata,
    records: Sequence[SupplementaryClassification],
    supplementary_paths: Sequence[str | Path],
) -> CurationSummary:
    """Build the stable summary consumed by JSON and PDF report renderers."""
    return CurationSummary(
        study_id=metadata.study_id_suggestion or "—",
        cancer_type=metadata.cancer_type or "—",
        num_samples=metadata.num_samples or "—",
        reference_genome=metadata.reference_genome or "—",
        files_analysed=len(supplementary_paths),
        sheets_analysed=len(records),
        high_priority=sum(row.priority.upper() == "HIGH" for row in records),
        medium_priority=sum(row.priority.upper() == "MEDIUM" for row in records),
        not_loadable=sum(row.curability.upper() == "NO" for row in records),
        file_breakdown=_build_report_breakdown(records),
    )


def _format_curability(value: str) -> str:
    normalized = str(value or "").strip().upper()
    return {
        "YES": "Yes",
        "PARTIAL": "Partially",
        "NO": "No",
    }.get(normalized, normalized.title() or "Unknown")


def _format_label(value: str) -> str:
    text = str(value or "").strip().replace("_", " ")
    return text.title() if text else "Unknown"


def _build_publication(metadata: Mapping[str, Any]) -> str:
    return " ".join(
        str(item).strip()
        for item in [metadata.get("journal", ""), metadata.get("year", "")]
        if str(item).strip()
    )


def build_curation_report_json(
    metadata: PublicationMetadata,
    summary: CurationSummary,
) -> dict[str, Any]:
    """Construct the stable JSON-compatible curation-report document."""
    meta = metadata.to_dict()
    summary_data = summary.to_dict()
    study_title = (
        meta.get("study_title") or summary_data.get("study_id") or "Untitled study"
    )
    publication = _build_publication(meta)
    citation_bits = [
        publication,
        f"DOI: {meta.get('doi')}" if meta.get("doi") else "",
        f"PMID: {meta.get('pmid')}" if meta.get("pmid") else "",
    ]
    citation = " | ".join(bit for bit in citation_bits if bit) or None
    key_findings = [
        str(item).strip()
        for item in (meta.get("key_findings") or [])
        if str(item).strip()
    ]
    breakdown = summary_data.get("file_breakdown", []) or []

    return {
        "report_title": "cBioAbstractor Curation Report",
        "study_title": study_title,
        "citation": citation,
        "study_overview": {
            "study_title": meta.get("study_title"),
            "study_id_suggestion": meta.get("study_id_suggestion")
            or summary_data.get("study_id"),
            "cancer_type": meta.get("cancer_type") or summary_data.get("cancer_type"),
            "cancer_type_full": meta.get("cancer_type_full"),
            "num_samples": meta.get("num_samples") or summary_data.get("num_samples"),
            "num_patients": meta.get("num_patients"),
            "reference_genome": meta.get("reference_genome")
            or summary_data.get("reference_genome"),
            "sequencing_types": meta.get("sequencing_types") or [],
            "pmid": meta.get("pmid"),
            "doi": meta.get("doi"),
            "first_author_surname": meta.get("first_author_surname"),
            "year": meta.get("year"),
            "journal": meta.get("journal"),
            "publication": publication or None,
            "description": meta.get("description"),
            "meta_description": meta.get("meta_description"),
            "primary_site": meta.get("primary_site"),
            "cohort_description": meta.get("cohort_description"),
            "data_repositories": meta.get("data_repositories") or [],
            "corresponding_authors": meta.get("corresponding_authors"),
            "key_findings": key_findings,
        },
        "supplementary_file_analysis": {
            "high_priority": summary_data.get("high_priority", 0),
            "medium_priority": summary_data.get("medium_priority", 0),
            "needs_manual_intervention": summary_data.get("not_loadable", 0),
            "file_breakdown": [
                {
                    "file": row.get("file"),
                    "sheet": row.get("sheet"),
                    "cbioportal_format": _format_label(
                        str(row.get("cbio_format", "—"))
                    ),
                    "confidence_percent": round(float(row.get("confidence", 0) or 0)),
                    "loadable": _format_curability(str(row.get("curability", ""))),
                    "priority": row.get("priority") or None,
                    "columns_present": row.get("req_present", []) or [],
                    "columns_missing": row.get("req_missing", []) or [],
                }
                for row in breakdown
            ],
        },
        "per_sheet_classification_detail": [
            {
                "file": row.get("file"),
                "sheet": row.get("sheet"),
                "format": _format_label(str(row.get("cbio_format", "—"))),
                "confidence_percent": round(float(row.get("confidence", 0) or 0)),
                "loadable": _format_curability(str(row.get("curability", "—"))),
                "priority": row.get("priority") or None,
                "assessment": row.get("verdict") or None,
                "required_columns_found": row.get("req_present", []) or [],
                "required_columns_missing": row.get("req_missing", []) or [],
                "optional_columns_found": row.get("opt_present", []) or [],
            }
            for row in breakdown
        ],
        "suggested_study_metadata": {
            "cancer_study_identifier": summary_data.get("study_id"),
            "name": meta.get("study_title"),
            "description": meta.get("meta_description") or meta.get("description"),
            "cancer_type": meta.get("cancer_type"),
            "short_name": meta.get("study_id_suggestion"),
            "pmid": meta.get("pmid"),
            "groups": "PUBLIC",
        },
    }


__all__ = [
    "CURABILITY",
    "analyse_supplementary_files",
    "build_curation_report_json",
    "build_curation_summary",
]
