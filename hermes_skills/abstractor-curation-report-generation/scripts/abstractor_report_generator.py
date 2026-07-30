"""
Generate a cBioPortal curation report from a local paper PDF or XML file and local supplementary files.

Example
-------
    python hermes_skills/abstractor-curation-report-generation/scripts/abstractor_report_generator.py \
        --study-id <study_id>
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import os
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from cbio_curation_assistant.command_result import (
    CommandResult,
    command_error,
    command_result,
    emit_command_result,
)
from cbio_curation_assistant.cbioportal_curator import analyse_supplementary_files
from cbio_curation_assistant.hermes_llm import resolve_optional_hermes_llm_config
from cbio_curation_assistant.llm import LLMConfig
from cbio_curation_assistant.pdf_report import (
    build_curation_report_json,
    save_curation_report_pdf,
)
from cbio_curation_assistant.publications import (
    PublicationMetadata,
    extract_pdf_metadata_with_llm,
    extract_xml_metadata_with_llm,
)
from cbio_curation_assistant.supplements.models import SupplementaryClassification
from cbio_curation_assistant.supplements.readers import (
    discover_supplementary_files,
    require_supplementary_reader_dependencies,
)
from cbio_curation_assistant.workspace import InvalidStudyIdError, StudyWorkspace, WorkspaceConfigurationError
from cbio_curation_assistant.workflows.curation_report import (
    AgentReportData,
    CurationReportInputs,
    CurationReportOutputs,
    CurationReportRun,
    CurationSummary,
    LlmMetadataExtraction,
    PaperSource,
    ReportBreakdownRow,
)

logger = logging.getLogger(__name__)

_DEFAULT_REPORT_SUFFIX = "abstractor_report"


def _resolve_study_inputs(study_id: str) -> tuple[StudyWorkspace, str | None, str | None, list[str]]:
    workspace = StudyWorkspace.load(study_id)
    paper_xml_path = workspace.article_xml_path if workspace.article_xml_path.is_file() else None
    paper_pdf_path = workspace.article_pdf_path if workspace.article_pdf_path.is_file() else None

    if paper_xml_path is None and paper_pdf_path is None:
        raise FileNotFoundError(
            "No canonical article source was found in the study workspace. "
            f"Expected {workspace.article_xml_path} or {workspace.article_pdf_path}."
        )

    supplementary_paths = [
        str(path)
        for path in discover_supplementary_files(
            [workspace.supplementary_dir],
            recursive=True,
        )
    ]
    return (
        workspace,
        str(paper_pdf_path.resolve()) if paper_pdf_path is not None else None,
        str(paper_xml_path.resolve()) if paper_xml_path is not None else None,
        supplementary_paths,
    )


def _build_summary(
    meta: PublicationMetadata,
    records: Sequence[SupplementaryClassification],
    supp_paths: Sequence[str],
) -> CurationSummary:
    breakdown = _build_report_breakdown(records)
    return CurationSummary(
        study_id=meta.study_id_suggestion or "—",
        cancer_type=meta.cancer_type or "—",
        num_samples=meta.num_samples or "—",
        reference_genome=meta.reference_genome or "—",
        files_analysed=len(supp_paths),
        sheets_analysed=len(records),
        high_priority=sum(row.priority.upper() == "HIGH" for row in records),
        medium_priority=sum(row.priority.upper() == "MEDIUM" for row in records),
        not_loadable=sum(row.curability.upper() == "NO" for row in records),
        file_breakdown=breakdown,
    )


def _build_report_breakdown(
    records: Sequence[SupplementaryClassification],
) -> tuple[ReportBreakdownRow, ...]:
    pdf_rows_by_file: dict[str, list[SupplementaryClassification]] = collections.defaultdict(list)
    for row in records:
        file_name = row.file
        if file_name.lower().endswith(".pdf"):
            pdf_rows_by_file[file_name].append(row)

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
        file_name = row.file or "—"
        is_manual_pdf_row = row.curability.upper() == "NO"
        if file_name in aggregated_pdf_files and is_manual_pdf_row:
            if file_name in emitted_pdf_files:
                continue
            breakdown.append(_build_aggregated_pdf_breakdown_row(manual_pdf_rows_by_file[file_name]))
            emitted_pdf_files.add(file_name)
            continue
        breakdown.append(_build_breakdown_row(row))

    return tuple(breakdown)


def _build_breakdown_row(row: SupplementaryClassification) -> ReportBreakdownRow:
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


def _merge_breakdown_values(
    rows: Sequence[SupplementaryClassification],
    key: Literal["required_present", "required_missing", "optional_present"],
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


def _build_report_stem(
    meta: PublicationMetadata,
    summary: CurationSummary,
    study_workspace: StudyWorkspace | None,
) -> str:
    study_id = str(meta.study_id_suggestion or "").strip()
    if not study_id or study_id == "—":
        study_id = str(summary.study_id or "").strip()
    if not study_id or study_id == "—":
        study_id = study_workspace.study_id if study_workspace is not None else "cbioportal_curation"

    stem = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in study_id).strip("._")
    return f"{stem or 'cbioportal_curation'}_{_DEFAULT_REPORT_SUFFIX}"


def _build_report_pdf_filename(
    meta: PublicationMetadata,
    summary: CurationSummary,
    study_workspace: StudyWorkspace | None,
) -> str:
    return _build_report_stem(meta, summary, study_workspace) + ".pdf"


def _build_report_json_filename(
    meta: PublicationMetadata,
    summary: CurationSummary,
    study_workspace: StudyWorkspace | None,
) -> str:
    return _build_report_stem(meta, summary, study_workspace) + ".json"


def _infer_study_workspace(paths: Sequence[str | Path]) -> StudyWorkspace | None:
    study_workspaces: dict[Path, StudyWorkspace] = {}

    for raw_path in paths:
        candidate = Path(raw_path).expanduser().resolve()
        for ancestor in (candidate, *candidate.parents):
            if ancestor.parent.name != "studies":
                continue
            try:
                workspace = StudyWorkspace.load(
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


def _resolve_output_pdf_path(
    output_pdf_path: str | None,
    output_dir: str | None,
    study_workspace: StudyWorkspace | None,
    meta: PublicationMetadata,
    summary: CurationSummary,
) -> str | None:
    if output_pdf_path:
        return str(Path(output_pdf_path).expanduser().resolve())
    if output_dir:
        directory = Path(output_dir).expanduser().resolve()
        return str((directory / _build_report_pdf_filename(meta, summary, study_workspace)).resolve())
    if study_workspace is not None:
        return str((study_workspace.reports_dir / _build_report_pdf_filename(meta, summary, study_workspace)).resolve())
    return None


def _resolve_output_json_path(
    output_json_path: str | None,
    output_pdf_path: str | None,
    output_dir: str | None,
    study_workspace: StudyWorkspace | None,
    meta: PublicationMetadata,
    summary: CurationSummary,
) -> str | None:
    if output_json_path:
        return str(Path(output_json_path).expanduser().resolve())
    if output_pdf_path:
        return str(Path(output_pdf_path).with_suffix(".json").resolve())
    if output_dir:
        directory = Path(output_dir).expanduser().resolve()
        return str((directory / _build_report_json_filename(meta, summary, study_workspace)).resolve())
    if study_workspace is not None:
        return str((study_workspace.reports_dir / _build_report_json_filename(meta, summary, study_workspace)).resolve())
    return None


def _write_json(
    path: str | Path,
    payload: Mapping[str, Any] | CommandResult[Any],
) -> str:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = payload.to_dict() if isinstance(payload, CommandResult) else dict(payload)
    destination.write_text(
        json.dumps(rendered, indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    return str(destination)


def _resolve_agent_report_path(
    output_json_path: str | None,
    output_dir: str | None,
    study_workspace: StudyWorkspace | None,
) -> str | None:
    if output_json_path:
        report_path = Path(output_json_path).expanduser().resolve()
        return str(report_path.with_name(f"{report_path.stem}_agent_report.json"))
    if output_dir:
        return str((Path(output_dir).expanduser().resolve() / "curation_report_agent.json").resolve())
    if study_workspace is not None:
        return str(study_workspace.curation_report_agent_path.resolve())
    return None


def _build_agent_report(
    *,
    study_workspace: StudyWorkspace | None,
    inputs: CurationReportInputs,
    warnings: Sequence[str],
    llm: LlmMetadataExtraction,
    outputs: CurationReportOutputs,
) -> CommandResult[AgentReportData]:
    result = AgentReportData(
        study_id=study_workspace.study_id if study_workspace is not None else None,
        paper_source=inputs.paper_source,
        supplementary_paths=inputs.supplementary_paths,
        llm_metadata_extraction=llm,
        outputs=outputs,
    )
    return command_result(
        "curation-report",
        status="success",
        result=result,
        warnings=warnings,
    )


def run_curation_orchestrator(
    *,
    paper_pdf_path: str | None = None,
    paper_xml_path: str | None = None,
    supplementary_paths: Sequence[str | Path] | None = None,
    study_workspace: StudyWorkspace | None = None,
    llm_config: LLMConfig | None = None,
    recursive_supplementary_search: bool = False,
    output_pdf_path: str | None = None,
    output_dir: str | None = None,
    output_json_path: str | None = None,
) -> CurationReportRun:
    """
    Run the local curation report workflow.

    Exactly one local paper source is supported:
    - `paper_pdf_path` + `supplementary_paths`
    - `paper_xml_path` + `supplementary_paths`
    """
    selected_sources = [
        bool(paper_pdf_path),
        bool(paper_xml_path),
    ]
    if sum(selected_sources) != 1:
        raise ValueError("Provide exactly one of: paper_pdf_path or paper_xml_path.")

    warnings: list[str] = []
    meta: PublicationMetadata
    supp_paths = [
        str(path)
        for path in discover_supplementary_files(
            supplementary_paths or [],
            recursive=recursive_supplementary_search,
        )
    ]
    require_supplementary_reader_dependencies(supp_paths)
    resolved_llm_config = llm_config or resolve_optional_hermes_llm_config()

    if paper_pdf_path:
        paper_path = Path(paper_pdf_path).expanduser().resolve()
        if not paper_path.is_file():
            raise FileNotFoundError(f"Paper PDF not found: {paper_path}")
        meta = extract_pdf_metadata_with_llm(
            paper_path,
            resolved_llm_config,
            warnings,
            logger=logger,
        )
        paper_source = PaperSource(kind="pdf", path=paper_path)
    else:
        paper_path = Path(paper_xml_path or "").expanduser().resolve()
        if not paper_path.is_file():
            raise FileNotFoundError(f"Paper XML not found: {paper_path}")
        extracted_meta = extract_xml_metadata_with_llm(
            paper_path,
            resolved_llm_config,
            warnings,
            logger=logger,
            missing_text_warning="Could not extract text from the XML. Using structured XML metadata only.",
            missing_llm_warning="No Hermes LLM configuration is available. Using structured XML metadata only.",
            completion_failure_warning=(
                "XML metadata completion returned unexpected format. Continuing with structured XML metadata only."
            ),
        )
        meta = PublicationMetadata.from_mapping(extracted_meta)
        paper_source = PaperSource(kind="xml", path=paper_path)

    inputs = CurationReportInputs(
        paper_source=paper_source,
        supplementary_paths=tuple(Path(path) for path in supp_paths),
    )

    if study_workspace is None:
        study_workspace = _infer_study_workspace([paper_path, *supp_paths])

    raw_records = analyse_supplementary_files(supp_paths, warnings=warnings)
    records = tuple(
        record
        if isinstance(record, SupplementaryClassification)
        else SupplementaryClassification.from_mapping(record)
        for record in raw_records
    )
    summary = _build_summary(meta, records, supp_paths)

    resolved_output_pdf_path = _resolve_output_pdf_path(output_pdf_path, output_dir, study_workspace, meta, summary)
    resolved_output_json_path = _resolve_output_json_path(
        output_json_path=output_json_path,
        output_pdf_path=resolved_output_pdf_path,
        output_dir=output_dir,
        study_workspace=study_workspace,
        meta=meta,
        summary=summary,
    )

    meta_payload = meta.to_dict()
    summary_payload = summary.to_dict()
    pdf_path = save_curation_report_pdf(
        meta_payload,
        summary_payload,
        resolved_output_pdf_path,
    )

    report = build_curation_report_json(meta_payload, summary_payload)
    report_json_path = _write_json(resolved_output_json_path, report) if resolved_output_json_path else None
    resolved_agent_report_path = _resolve_agent_report_path(output_json_path, output_dir, study_workspace)
    llm = LlmMetadataExtraction(
        enabled=resolved_llm_config is not None,
        provider=resolved_llm_config.provider if resolved_llm_config else None,
        model=resolved_llm_config.model if resolved_llm_config else None,
        api_mode=resolved_llm_config.api_mode if resolved_llm_config else None,
        base_url=resolved_llm_config.base_url if resolved_llm_config else None,
    )
    outputs = CurationReportOutputs(
        pdf=Path(pdf_path) if pdf_path else None,
        curation_report_json=(Path(report_json_path) if report_json_path else None),
        agent_report_json=(
            Path(resolved_agent_report_path) if resolved_agent_report_path else None
        ),
    )
    agent_report = _build_agent_report(
        study_workspace=study_workspace,
        inputs=inputs,
        warnings=warnings,
        llm=llm,
        outputs=outputs,
    )
    if resolved_agent_report_path:
        _write_json(resolved_agent_report_path, agent_report)

    return CurationReportRun(
        report=report,
        agent_report=agent_report,
        metadata=meta,
        classifications=records,
        summary=summary,
        outputs=outputs,
        study_root=(study_workspace.root if study_workspace is not None else None),
        warnings=tuple(warnings),
        inputs=inputs,
        llm=llm,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a cBioPortal curation report PDF and JSON from the canonical article "
            "and supplementary files in a study workspace. LLM metadata enrichment is resolved "
            "from the Hermes environment."
        ),
    )

    parser.add_argument(
        "--study-id",
        required=True,
        help="Canonical study workspace key used to resolve the study workspace.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        study_workspace, paper_pdf_path, paper_xml_path, supplementary_paths = _resolve_study_inputs(args.study_id)
        result = run_curation_orchestrator(
            paper_pdf_path=paper_pdf_path,
            paper_xml_path=paper_xml_path,
            supplementary_paths=supplementary_paths,
            study_workspace=study_workspace,
        )
    except Exception as exc:
        logger.error("%s", exc)
        emit_command_result(command_error("curation-report", exc))
        return 1

    emit_command_result(result.agent_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
