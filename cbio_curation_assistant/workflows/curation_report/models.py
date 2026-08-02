"""Typed inputs and results for the curation-report workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from cbio_curation_assistant.publications.models import PublicationMetadata
from cbio_curation_assistant.reports.models import CurationSummary
from cbio_curation_assistant.supplements.models import SupplementaryClassification


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


__all__ = [
    "AgentReportData",
    "CurationReportInputs",
    "CurationReportOutputs",
    "CurationReportRun",
    "LlmMetadataExtraction",
    "PaperSource",
    "SupplementarySelection",
]
