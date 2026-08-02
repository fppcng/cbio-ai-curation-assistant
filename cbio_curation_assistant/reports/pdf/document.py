"""Assemble the curation-report PDF document."""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate

from cbio_curation_assistant.reports.pdf.layout import (
    build_report_layout,
    draw_footer,
)
from cbio_curation_assistant.reports.pdf.overview import build_overview_elements
from cbio_curation_assistant.reports.pdf.study_metadata import (
    build_study_metadata_elements,
)
from cbio_curation_assistant.reports.pdf.supplementary import (
    build_supplementary_elements,
)


def build_curation_report_pdf(
    meta: dict[str, Any],
    summary: dict[str, Any],
) -> bytes:
    """Render the complete curation report as PDF bytes."""
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="cBioPortal Curation Report",
        author="cBioAbstractor",
    )
    layout = build_report_layout()
    elements = [
        *build_overview_elements(meta, summary, layout),
        *build_supplementary_elements(summary, layout),
        *build_study_metadata_elements(meta, summary, layout),
    ]
    document.build(
        elements,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer,
    )
    return buffer.getvalue()


__all__ = ["build_curation_report_pdf"]
