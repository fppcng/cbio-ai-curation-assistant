"""Build the title and study-overview PDF sections."""

from __future__ import annotations

from typing import Any

from reportlab.platypus import Paragraph, Spacer

from cbio_curation_assistant.reports.pdf.layout import (
    ReportLayout,
    join_values,
    safe_paragraph_text,
)
from cbio_curation_assistant.reports.presentation import build_publication


def build_overview_elements(
    meta: dict[str, Any],
    summary: dict[str, Any],
    layout: ReportLayout,
) -> list[Any]:
    p = layout.paragraph
    elements: list[Any] = []
    study_title = meta.get("study_title") or summary.get("study_id") or "Untitled study"
    publication = build_publication(meta)
    citation_bits = [
        publication,
        f"DOI: {meta.get('doi')}" if meta.get("doi") else "",
        f"PMID: {meta.get('pmid')}" if meta.get("pmid") else "",
    ]
    citation = " | ".join(bit for bit in citation_bits if bit)

    elements.append(
        Paragraph("cBioAbstractor Curation Report", layout.styles["ReportTitle"])
    )
    elements.append(
        Paragraph(safe_paragraph_text(study_title), layout.styles["Heading2"])
    )
    if citation:
        elements.append(
            Paragraph(safe_paragraph_text(citation), layout.styles["LabelSmall"])
        )
    elements.append(Spacer(1, 8))
    elements.extend(layout.section("Study Overview"))

    overview_rows = [[p("Field", "BodySmall"), p("Value", "BodySmall")]]
    key_findings = meta.get("key_findings") or []
    overview_fields = [
        ("Study title", meta.get("study_title")),
        (
            "Study ID suggestion",
            meta.get("study_id_suggestion") or summary.get("study_id"),
        ),
        ("Cancer type", meta.get("cancer_type") or summary.get("cancer_type")),
        ("Cancer type full", meta.get("cancer_type_full")),
        ("Number of samples", meta.get("num_samples") or summary.get("num_samples")),
        ("Number of patients", meta.get("num_patients")),
        (
            "Reference genome",
            meta.get("reference_genome") or summary.get("reference_genome"),
        ),
        ("Sequencing types", join_values(meta.get("sequencing_types"))),
        ("PMID", meta.get("pmid")),
        ("DOI", meta.get("doi")),
        ("First author surname", meta.get("first_author_surname")),
        ("Year", meta.get("year")),
        ("Journal", meta.get("journal")),
        ("Publication", publication),
        ("Description", meta.get("description")),
        ("Meta description", meta.get("meta_description")),
        ("Primary site", meta.get("primary_site")),
        ("Cohort description", meta.get("cohort_description")),
        ("Data repositories", join_values(meta.get("data_repositories"))),
        ("Corresponding author(s)", meta.get("corresponding_authors")),
        (
            "Key findings",
            "\n".join(f"- {item}" for item in key_findings) if key_findings else "—",
        ),
    ]
    for label, value in overview_fields:
        overview_rows.append([p(label, "BodySmall"), p(value, "BodySmall")])
    elements.append(layout.metric_table(overview_rows, [150, 580]))
    elements.append(Spacer(1, 8))
    return elements


__all__ = ["build_overview_elements"]
