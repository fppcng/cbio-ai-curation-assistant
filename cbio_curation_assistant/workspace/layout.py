"""Canonical study workspace paths and path-safety operations.

This module is the single source of truth for study-specific filesystem paths.
Skills and scripts should use ``StudyWorkspace`` instead of constructing paths
manually.

Expected layout::

    <CBIO_CURATION_ASSISTANT_HOME>/
    └── studies/
        └── <study_id>/
            ├── source/
            │   ├── download_manifest.json
            │   ├── article/
            │   └── supplementary/
            ├── curated/
            ├── reports/
            └── study_manifest.json
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cbio_curation_assistant.workspace.configuration import (
    DOWNLOAD_MANIFEST_FILENAME,
    MANIFEST_FILENAME,
    STUDIES_DIRECTORY_NAME,
    WorkspaceConfigurationError,
    normalize_study_id,
    resolve_assistant_home,
)


@dataclass(frozen=True, slots=True)
class StudyWorkspace:
    """Filesystem contract for one cBioPortal study."""

    assistant_home: Path
    study_id: str

    @classmethod
    def from_study_id(
        cls,
        study_id: str,
        *,
        assistant_home: str | Path | None = None,
    ) -> "StudyWorkspace":
        """Build a workspace from a study workspace key."""
        return cls(
            assistant_home=resolve_assistant_home(assistant_home),
            study_id=normalize_study_id(study_id),
        )

    @property
    def studies_root(self) -> Path:
        return self.assistant_home / STUDIES_DIRECTORY_NAME

    @property
    def root(self) -> Path:
        return self.studies_root / self.study_id

    @property
    def source_dir(self) -> Path:
        return self.root / "source"

    @property
    def download_manifest_path(self) -> Path:
        return self.source_dir / DOWNLOAD_MANIFEST_FILENAME

    @property
    def article_dir(self) -> Path:
        return self.source_dir / "article"

    @property
    def article_xml_path(self) -> Path:
        return self.article_dir / "article.xml"

    @property
    def article_pdf_path(self) -> Path:
        return self.article_dir / "article.pdf"

    @property
    def supplementary_dir(self) -> Path:
        return self.source_dir / "supplementary"

    @property
    def curated_dir(self) -> Path:
        return self.root / "curated"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def curation_report_agent_path(self) -> Path:
        return self.reports_dir / "curation_report_agent.json"

    @property
    def manifest_path(self) -> Path:
        return self.root / MANIFEST_FILENAME

    def directories(self) -> tuple[Path, ...]:
        """Return all standard directories in creation order."""
        return (
            self.studies_root,
            self.root,
            self.source_dir,
            self.article_dir,
            self.supplementary_dir,
            self.curated_dir,
            self.reports_dir,
        )

    def contains(self, path: str | Path) -> bool:
        """Return whether a path is located inside this study workspace."""
        candidate = Path(path).expanduser().resolve()
        try:
            candidate.relative_to(self.root.resolve())
        except ValueError:
            return False
        return True

    def require_inside_workspace(self, path: str | Path) -> Path:
        """Resolve a path and reject it if it escapes the study workspace."""
        candidate = Path(path).expanduser().resolve()

        if not self.contains(candidate):
            raise WorkspaceConfigurationError(
                f"Path is outside study workspace {self.root}: {candidate}"
            )

        return candidate

    def relative_to_root(self, path: str | Path) -> str:
        """Return a portable POSIX path relative to the study root."""
        candidate = self.require_inside_workspace(path)
        return candidate.relative_to(self.root.resolve()).as_posix()

    def resolve_relative_path(self, relative_path: str | Path) -> Path:
        """Resolve a manifest path relative to the study root safely."""
        relative = Path(relative_path)

        if relative.is_absolute():
            raise WorkspaceConfigurationError(
                f"Expected a relative study path, got: {relative}"
            )

        return self.require_inside_workspace(self.root / relative)


__all__ = ["StudyWorkspace"]
