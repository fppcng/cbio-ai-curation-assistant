"""Name and persist curation-report PDFs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from cbio_curation_assistant.reports.pdf.document import build_curation_report_pdf


def build_curation_report_filename(
    meta: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    raw_name = (
        summary.get("study_id")
        or meta.get("study_id_suggestion")
        or meta.get("study_title")
        or "cbioportal_curation_report"
    )
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", str(raw_name).strip()).strip("._")
    stem = slug or "cbioportal_curation_report"
    return f"{stem}_curation_report.pdf"


def save_curation_report_pdf(
    meta: dict[str, Any],
    summary: dict[str, Any],
    output_path: str | Path | None = None,
) -> str:
    destination = (
        Path(output_path)
        if output_path
        else Path(build_curation_report_filename(meta, summary))
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(build_curation_report_pdf(meta, summary))
    return str(destination)


__all__ = ["build_curation_report_filename", "save_curation_report_pdf"]
