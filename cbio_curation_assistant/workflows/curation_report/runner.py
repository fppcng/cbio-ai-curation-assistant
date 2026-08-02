"""Orchestrate curation-report generation."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from cbio_curation_assistant.llm import LLMConfig
from cbio_curation_assistant.reports.curation import (
    analyse_supplementary_files,
    build_curation_report_json,
    build_curation_summary,
)
from cbio_curation_assistant.reports.pdf.output import save_curation_report_pdf
from cbio_curation_assistant.supplements.readers.dependencies import (
    require_supplementary_reader_dependencies,
)
from cbio_curation_assistant.supplements.readers.discovery import (
    discover_supplementary_files,
)
from cbio_curation_assistant.workspace.layout import StudyWorkspace
from cbio_curation_assistant.workspace.lifecycle import load_workspace
from cbio_curation_assistant.workflows.curation_report.artifacts import (
    resolve_agent_report_path,
    resolve_output_json_path,
    resolve_output_pdf_path,
    write_report_json,
)
from cbio_curation_assistant.workflows.curation_report.discovery import (
    discover_curation_report_inputs,
    infer_study_workspace,
)
from cbio_curation_assistant.workflows.curation_report.metadata import (
    build_llm_details,
    extract_metadata,
)
from cbio_curation_assistant.workflows.curation_report.models import (
    AgentReportData,
    CurationReportInputs,
    CurationReportOutputs,
    CurationReportRun,
    LlmMetadataExtraction,
    PaperSource,
)


def _build_agent_report(
    *,
    workspace: StudyWorkspace | None,
    inputs: CurationReportInputs,
    llm: LlmMetadataExtraction,
    outputs: CurationReportOutputs,
) -> AgentReportData:
    return AgentReportData(
        study_id=workspace.study_id if workspace is not None else None,
        paper_source=inputs.paper_source,
        supplementary_paths=inputs.supplementary_paths,
        llm_metadata_extraction=llm,
        outputs=outputs,
    )


def run_curation_report(
    inputs: CurationReportInputs,
    *,
    study_workspace: StudyWorkspace | None = None,
    llm_config: LLMConfig | None = None,
    output_pdf_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    output_json_path: str | Path | None = None,
    initial_warnings: Sequence[str] = (),
) -> CurationReportRun:
    """Generate report artifacts from one resolved paper source and supplements."""
    paper_source = PaperSource(
        kind=inputs.paper_source.kind,
        path=inputs.paper_source.path.expanduser().resolve(),
    )
    supplementary_paths = discover_supplementary_files(
        inputs.supplementary_paths,
        recursive=False,
    )
    resolved_inputs = CurationReportInputs(
        paper_source=paper_source,
        supplementary_paths=supplementary_paths,
        supplementary_selection=inputs.supplementary_selection,
    )
    require_supplementary_reader_dependencies(supplementary_paths)

    warnings = list(initial_warnings)
    metadata = extract_metadata(paper_source, llm_config, warnings)
    if study_workspace is None:
        study_workspace = infer_study_workspace(
            [paper_source.path, *supplementary_paths]
        )

    classifications = analyse_supplementary_files(
        supplementary_paths,
        warnings=warnings,
    )
    summary = build_curation_summary(
        metadata,
        classifications,
        supplementary_paths,
    )
    resolved_pdf_path = resolve_output_pdf_path(
        output_pdf_path,
        output_dir,
        study_workspace,
        metadata,
        summary,
    )
    resolved_json_path = resolve_output_json_path(
        output_json_path,
        resolved_pdf_path,
        output_dir,
        study_workspace,
        metadata,
        summary,
    )
    saved_pdf_path = save_curation_report_pdf(
        metadata.to_dict(),
        summary.to_dict(),
        resolved_pdf_path,
    )
    report = build_curation_report_json(metadata, summary)
    saved_json_path = (
        write_report_json(resolved_json_path, report)
        if resolved_json_path is not None
        else None
    )
    agent_report_path = resolve_agent_report_path(
        output_json_path,
        output_dir,
        study_workspace,
    )
    llm = build_llm_details(llm_config)
    outputs = CurationReportOutputs(
        pdf=Path(saved_pdf_path),
        curation_report_json=saved_json_path,
        agent_report_json=agent_report_path,
    )
    agent_report = _build_agent_report(
        workspace=study_workspace,
        inputs=resolved_inputs,
        llm=llm,
        outputs=outputs,
    )

    return CurationReportRun(
        report=report,
        agent_report=agent_report,
        metadata=metadata,
        classifications=classifications,
        summary=summary,
        outputs=outputs,
        study_root=(study_workspace.root if study_workspace is not None else None),
        warnings=tuple(warnings),
        inputs=resolved_inputs,
        llm=llm,
    )


def run_curation_report_for_study(
    study_id: str,
    *,
    llm_config: LLMConfig | None = None,
) -> CurationReportRun:
    """Discover canonical workspace inputs and generate its curation report."""
    workspace = load_workspace(study_id)
    inputs, discovery_warnings = discover_curation_report_inputs(workspace)
    return run_curation_report(
        inputs,
        study_workspace=workspace,
        llm_config=llm_config,
        initial_warnings=discovery_warnings,
    )


__all__ = [
    "run_curation_report",
    "run_curation_report_for_study",
]
