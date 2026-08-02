"""Resolve and persist curation-report artifacts."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cbio_curation_assistant.publications.models import PublicationMetadata
from cbio_curation_assistant.reports.models import CurationSummary
from cbio_curation_assistant.workspace.layout import StudyWorkspace


_DEFAULT_REPORT_SUFFIX = "abstractor_report"


def _build_report_stem(
    metadata: PublicationMetadata,
    summary: CurationSummary,
    workspace: StudyWorkspace | None,
) -> str:
    study_id = str(metadata.study_id_suggestion or "").strip()
    if not study_id or study_id == "—":
        study_id = str(summary.study_id or "").strip()
    if not study_id or study_id == "—":
        study_id = (
            workspace.study_id if workspace is not None else "cbioportal_curation"
        )
    stem = "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in study_id
    ).strip("._")
    return f"{stem or 'cbioportal_curation'}_{_DEFAULT_REPORT_SUFFIX}"


def resolve_output_pdf_path(
    output_pdf_path: str | Path | None,
    output_dir: str | Path | None,
    workspace: StudyWorkspace | None,
    metadata: PublicationMetadata,
    summary: CurationSummary,
) -> Path | None:
    if output_pdf_path:
        return Path(output_pdf_path).expanduser().resolve()
    filename = _build_report_stem(metadata, summary, workspace) + ".pdf"
    if output_dir:
        return (Path(output_dir).expanduser().resolve() / filename).resolve()
    if workspace is not None:
        return (workspace.reports_dir / filename).resolve()
    return None


def resolve_output_json_path(
    output_json_path: str | Path | None,
    output_pdf_path: Path | None,
    output_dir: str | Path | None,
    workspace: StudyWorkspace | None,
    metadata: PublicationMetadata,
    summary: CurationSummary,
) -> Path | None:
    if output_json_path:
        return Path(output_json_path).expanduser().resolve()
    if output_pdf_path:
        return output_pdf_path.with_suffix(".json").resolve()
    filename = _build_report_stem(metadata, summary, workspace) + ".json"
    if output_dir:
        return (Path(output_dir).expanduser().resolve() / filename).resolve()
    if workspace is not None:
        return (workspace.reports_dir / filename).resolve()
    return None


def resolve_agent_report_path(
    output_json_path: str | Path | None,
    output_dir: str | Path | None,
    workspace: StudyWorkspace | None,
) -> Path | None:
    if output_json_path:
        report_path = Path(output_json_path).expanduser().resolve()
        return report_path.with_name(f"{report_path.stem}_agent_report.json")
    if output_dir:
        return (
            Path(output_dir).expanduser().resolve() / "curation_report_agent.json"
        ).resolve()
    if workspace is not None:
        return workspace.curation_report_agent_path.resolve()
    return None


def write_report_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    return destination


__all__ = [
    "resolve_agent_report_path",
    "resolve_output_json_path",
    "resolve_output_pdf_path",
    "write_report_json",
]
