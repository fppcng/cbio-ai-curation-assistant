"""Discover canonical curation-report inputs and their workspace."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from cbio_curation_assistant.supplements.readers.discovery import (
    discover_supplementary_files,
)
from cbio_curation_assistant.workspace.configuration import (
    InvalidStudyIdError,
    WorkspaceConfigurationError,
)
from cbio_curation_assistant.workspace.layout import StudyWorkspace
from cbio_curation_assistant.workspace.lifecycle import load_workspace
from cbio_curation_assistant.workflows.curation_report.models import (
    CurationReportInputs,
    PaperSource,
)


def discover_curation_report_inputs(
    workspace: StudyWorkspace,
) -> tuple[CurationReportInputs, tuple[str, ...]]:
    """Resolve canonical report inputs, preferring structured XML over PDF."""
    xml_exists = workspace.article_xml_path.is_file()
    pdf_exists = workspace.article_pdf_path.is_file()
    if xml_exists:
        paper_source = PaperSource(
            kind="xml",
            path=workspace.article_xml_path.resolve(),
        )
    elif pdf_exists:
        paper_source = PaperSource(
            kind="pdf",
            path=workspace.article_pdf_path.resolve(),
        )
    else:
        raise FileNotFoundError(
            "No canonical article source was found in the study workspace. "
            f"Expected {workspace.article_xml_path} or "
            f"{workspace.article_pdf_path}."
        )

    warnings: tuple[str, ...] = ()
    if xml_exists and pdf_exists:
        warnings = (
            "Both canonical article XML and PDF are available; using XML "
            "as the structured metadata source.",
        )

    supplementary_paths = discover_supplementary_files(
        [workspace.supplementary_dir],
        recursive=True,
    )
    return (
        CurationReportInputs(
            paper_source=paper_source,
            supplementary_paths=supplementary_paths,
            supplementary_selection="workspace_recursive",
        ),
        warnings,
    )


def infer_study_workspace(
    paths: Sequence[str | Path],
) -> StudyWorkspace | None:
    """Infer one initialized workspace containing all supplied paths."""
    study_workspaces: dict[Path, StudyWorkspace] = {}
    for raw_path in paths:
        candidate = Path(raw_path).expanduser().resolve()
        for ancestor in (candidate, *candidate.parents):
            if ancestor.parent.name != "studies":
                continue
            try:
                workspace = load_workspace(
                    ancestor.name,
                    assistant_home=ancestor.parent.parent,
                )
            except (InvalidStudyIdError, WorkspaceConfigurationError):
                continue
            if workspace.contains(candidate):
                study_workspaces[workspace.root] = workspace
                break
    if len(study_workspaces) == 1:
        return next(iter(study_workspaces.values()))
    return None


__all__ = ["discover_curation_report_inputs", "infer_study_workspace"]
