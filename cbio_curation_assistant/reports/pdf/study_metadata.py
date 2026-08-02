"""Build the suggested-study-metadata PDF section."""

from __future__ import annotations

from typing import Any

from cbio_curation_assistant.reports.pdf.layout import ReportLayout


def build_study_metadata_elements(
    meta: dict[str, Any],
    summary: dict[str, Any],
    layout: ReportLayout,
) -> list[Any]:
    p = layout.paragraph
    rows = [
        [p("Field", "BodySmall"), p("Value", "BodySmall")],
        [
            p("cancer_study_identifier", "BodySmall"),
            p(summary.get("study_id") or "—", "BodySmall"),
        ],
        [p("name", "BodySmall"), p(meta.get("study_title") or "—", "BodySmall")],
        [
            p("description", "BodySmall"),
            p(
                meta.get("meta_description") or meta.get("description") or "—",
                "BodySmall",
            ),
        ],
        [
            p("cancer_type", "BodySmall"),
            p(meta.get("cancer_type") or "—", "BodySmall"),
        ],
        [
            p("short_name", "BodySmall"),
            p(meta.get("study_id_suggestion") or "—", "BodySmall"),
        ],
        [p("pmid", "BodySmall"), p(meta.get("pmid") or "—", "BodySmall")],
        [p("groups", "BodySmall"), p("PUBLIC", "BodySmall")],
    ]
    return [
        *layout.section("Suggested Study Metadata"),
        layout.metric_table(rows, [180, 550]),
    ]


__all__ = ["build_study_metadata_elements"]
