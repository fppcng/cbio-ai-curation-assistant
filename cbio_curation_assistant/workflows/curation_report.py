"""Package-owned curation-report discovery and orchestration."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from cbio_curation_assistant.llm import LLMConfig
from cbio_curation_assistant.publications import (
    PublicationMetadata,
    extract_pdf_metadata_with_llm,
    extract_xml_metadata_with_llm,
)
from cbio_curation_assistant.reports import (
    CurationSummary,
    analyse_supplementary_files,
    build_curation_report_json,
    build_curation_summary,
    save_curation_report_pdf,
)
from cbio_curation_assistant.supplements.models import SupplementaryClassification
from cbio_curation_assistant.supplements.readers import (
    discover_supplementary_files,
    require_supplementary_reader_dependencies,
)
from cbio_curation_assistant.workspace import (
    InvalidStudyIdError,
    StudyWorkspace,
    WorkspaceConfigurationError,
)


logger = logging.getLogger(__name__)

_DEFAULT_REPORT_SUFFIX = "abstractor_report"

SupplementarySelection = Literal["explicit", "workspace_recursive"]


@dataclass(frozen=True, slots=True)
class PaperSource:
    kind: Literal["pdf", "xml"]
    path: Path


@dataclass(frozen=True, slots=True)
class CurationReportInputs:
    paper_source: PaperSource
    supplementary_paths: tuple[Path, ...]
    supplementary_selection: SupplementarySelection = "explicit"

    def to_dict(self) -> dict[str, Any]:
        """Serialize resolved inputs for diagnostics and review tooling."""
        is_pdf = self.paper_source.kind == "pdf"
        return {
            "paper_pdf_path": str(self.paper_source.path) if is_pdf else None,
            "paper_xml_path": str(self.paper_source.path) if not is_pdf else None,
            "paper_source_type": self.paper_source.kind,
            "paper_source_value": str(self.paper_source.path),
            "supplementary_paths": [str(path) for path in self.supplementary_paths],
            "supplementary_selection": self.supplementary_selection,
        }


@dataclass(frozen=True, slots=True)
class LlmMetadataExtraction:
    enabled: bool
    provider: str | None = None
    model: str | None = None
    api_mode: str | None = None
    base_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "api_mode": self.api_mode,
            "base_url": self.base_url,
        }


@dataclass(frozen=True, slots=True)
class CurationReportOutputs:
    pdf: Path | None
    curation_report_json: Path | None
    agent_report_json: Path | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "pdf": str(self.pdf) if self.pdf is not None else None,
            "curation_report_json": (
                str(self.curation_report_json)
                if self.curation_report_json is not None
                else None
            ),
            "agent_report_json": (
                str(self.agent_report_json)
                if self.agent_report_json is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class AgentReportData:
    study_id: str | None
    paper_source: PaperSource
    supplementary_paths: tuple[Path, ...]
    llm_metadata_extraction: LlmMetadataExtraction
    outputs: CurationReportOutputs

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "paper_source": {
                "type": self.paper_source.kind,
                "path": str(self.paper_source.path),
            },
            "supplementary_files": {
                "count": len(self.supplementary_paths),
                "paths": [str(path) for path in self.supplementary_paths],
            },
            "llm_metadata_extraction": self.llm_metadata_extraction.to_dict(),
            "outputs": self.outputs.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class CurationReportRun:
    report: Mapping[str, Any]
    agent_report: AgentReportData
    metadata: PublicationMetadata
    classifications: tuple[SupplementaryClassification, ...]
    summary: CurationSummary
    outputs: CurationReportOutputs
    study_root: Path | None
    warnings: tuple[str, ...]
    inputs: CurationReportInputs
    llm: LlmMetadataExtraction

    def to_dict(self) -> dict[str, Any]:
        """Serialize the workflow result for diagnostics and review tooling."""
        output_paths = self.outputs.to_dict()
        return {
            "report": dict(self.report),
            "agent_report": self.agent_report.to_dict(),
            "meta": self.metadata.to_dict(),
            "records": [record.to_dict() for record in self.classifications],
            "summary": self.summary.to_dict(),
            "pdf_path": output_paths["pdf"],
            "report_json_path": output_paths["curation_report_json"],
            "agent_report_json_path": output_paths["agent_report_json"],
            "study_root": (
                str(self.study_root) if self.study_root is not None else None
            ),
            "warnings": list(self.warnings),
            "inputs": self.inputs.to_dict(),
            "llm": self.llm.to_dict(),
        }


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


def _infer_study_workspace(
    paths: Sequence[str | Path],
) -> StudyWorkspace | None:
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


def _resolve_output_pdf_path(
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


def _resolve_output_json_path(
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


def _resolve_agent_report_path(
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


def _write_json(
    path: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    return destination


def _extract_metadata(
    paper_source: PaperSource,
    llm_config: LLMConfig | None,
    warnings: list[str],
) -> PublicationMetadata:
    paper_path = paper_source.path.expanduser().resolve()
    if not paper_path.is_file():
        source_name = paper_source.kind.upper()
        raise FileNotFoundError(f"Paper {source_name} not found: {paper_path}")
    if paper_source.kind == "pdf":
        return extract_pdf_metadata_with_llm(
            paper_path,
            llm_config,
            warnings,
            logger=logger,
        )
    extracted = extract_xml_metadata_with_llm(
        paper_path,
        llm_config,
        warnings,
        logger=logger,
        missing_text_warning=(
            "Could not extract text from the XML. Using structured XML metadata only."
        ),
        missing_llm_warning=(
            "No Hermes LLM configuration is available. "
            "Using structured XML metadata only."
        ),
        completion_failure_warning=(
            "XML metadata completion returned unexpected format. "
            "Continuing with structured XML metadata only."
        ),
    )
    return PublicationMetadata.from_mapping(extracted)


def _build_llm_details(
    llm_config: LLMConfig | None,
) -> LlmMetadataExtraction:
    return LlmMetadataExtraction(
        enabled=llm_config is not None,
        provider=llm_config.provider if llm_config else None,
        model=llm_config.model if llm_config else None,
        api_mode=llm_config.api_mode if llm_config else None,
        base_url=llm_config.base_url if llm_config else None,
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
    metadata = _extract_metadata(paper_source, llm_config, warnings)
    if study_workspace is None:
        study_workspace = _infer_study_workspace(
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
    resolved_pdf_path = _resolve_output_pdf_path(
        output_pdf_path,
        output_dir,
        study_workspace,
        metadata,
        summary,
    )
    resolved_json_path = _resolve_output_json_path(
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
        _write_json(resolved_json_path, report)
        if resolved_json_path is not None
        else None
    )
    agent_report_path = _resolve_agent_report_path(
        output_json_path,
        output_dir,
        study_workspace,
    )
    llm = _build_llm_details(llm_config)
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
    workspace = StudyWorkspace.load(study_id)
    inputs, discovery_warnings = discover_curation_report_inputs(workspace)
    return run_curation_report(
        inputs,
        study_workspace=workspace,
        llm_config=llm_config,
        initial_warnings=discovery_warnings,
    )


__all__ = [
    "AgentReportData",
    "CurationReportInputs",
    "CurationReportOutputs",
    "CurationReportRun",
    "LlmMetadataExtraction",
    "PaperSource",
    "SupplementarySelection",
    "discover_curation_report_inputs",
    "run_curation_report",
    "run_curation_report_for_study",
]
