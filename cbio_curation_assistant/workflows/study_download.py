"""Typed inputs and results for the study-download workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from cbio_curation_assistant.command_result import CommandStatus
from cbio_curation_assistant.integrations.pmc import ResolvedStudyIdentifier


@dataclass(frozen=True, slots=True)
class DownloadedArtifact:
    """Snapshot of one expected downloaded artifact."""

    path: Path
    relative_path: str
    present: bool
    reused: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "relative_path": self.relative_path,
            "present": self.present,
            "reused": self.reused,
        }


@dataclass(frozen=True, slots=True)
class DownloadWorkspacePaths:
    assistant_home: Path
    study_root: Path
    source_dir: Path
    study_manifest: Path
    download_manifest: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "assistant_home": str(self.assistant_home),
            "study_root": str(self.study_root),
            "source_dir": str(self.source_dir),
            "study_manifest": str(self.study_manifest),
            "download_manifest": str(self.download_manifest),
        }


@dataclass(frozen=True, slots=True)
class SupplementaryArtifacts:
    directory: Path
    relative_directory: str
    present: bool
    reused: bool
    files: tuple[DownloadedArtifact, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "directory": str(self.directory),
            "relative_directory": self.relative_directory,
            "present": self.present,
            "reused": self.reused,
            "count": len(self.files),
            "files": [artifact.to_dict() for artifact in self.files],
        }


@dataclass(frozen=True, slots=True)
class ArtifactReuse:
    xml: bool
    supplementary: bool
    article_pdf: bool

    def to_dict(self) -> dict[str, bool]:
        return {
            "xml": self.xml,
            "supplementary": self.supplementary,
            "article_pdf": self.article_pdf,
        }


@dataclass(frozen=True, slots=True)
class StudyDownloadResult:
    """Workflow result and persisted download-manifest source."""

    schema_version: int
    study_id: str
    study_manifest: str
    download_manifest: str
    workspace: DownloadWorkspacePaths
    managed_paths: Mapping[str, str]
    resolved_identifier: ResolvedStudyIdentifier
    xml: DownloadedArtifact
    article_pdf: DownloadedArtifact
    supplementary: SupplementaryArtifacts
    reused: ArtifactReuse
    warnings: tuple[str, ...] = ()

    @property
    def status(self) -> CommandStatus:
        return "partial_success" if self.warnings else "success"

    def _resolved_identifier_dict(self) -> dict[str, str | None]:
        return self.resolved_identifier.to_dict()

    def to_command_data(self) -> dict[str, Any]:
        """Return command data without envelope or persistence-only fields."""
        return {
            "manifest_version": self.schema_version,
            "study_id": self.study_id,
            "study_manifest": self.study_manifest,
            "download_manifest": self.download_manifest,
            "workspace": self.workspace.to_dict(),
            "managed_paths": dict(self.managed_paths),
            "resolved_identifier": self._resolved_identifier_dict(),
            "artifacts": {
                "xml_path": self.xml.relative_path,
                "article_pdf_path": (
                    self.article_pdf.relative_path if self.article_pdf.present else None
                ),
                "supplementary_paths": [
                    artifact.relative_path for artifact in self.supplementary.files
                ],
                "xml_present": self.xml.present,
                "article_pdf_present": self.article_pdf.present,
                "supplementary_count": len(self.supplementary.files),
            },
            "artifact_details": {
                "xml": self.xml.to_dict(),
                "article_pdf": self.article_pdf.to_dict(),
                "supplementary": self.supplementary.to_dict(),
            },
            "reused": self.reused.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize when nested under the shared command envelope."""
        return self.to_command_data()

    def to_manifest_dict(self) -> dict[str, Any]:
        """Serialize the stable persisted download-manifest schema."""
        return {
            "schema_version": self.schema_version,
            **self.to_command_data(),
            "status": self.status,
            "success": self.status == "success",
            "warnings": list(self.warnings),
        }
