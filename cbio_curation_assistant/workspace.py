"""Centralized study workspace layout for the cBioPortal AI Curation Assistant.

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

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final


ENV_VAR_NAME: Final[str] = "CBIO_CURATION_ASSISTANT_HOME"
STUDIES_DIRECTORY_NAME: Final[str] = "studies"
MANIFEST_FILENAME: Final[str] = "study_manifest.json"
DOWNLOAD_MANIFEST_FILENAME: Final[str] = "download_manifest.json"
WORKSPACE_MANIFEST_VERSION: Final[int] = 1

_STUDY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REQUIRED_MANAGED_PATH_KEYS: Final[frozenset[str]] = frozenset(
    {
        "study_root",
        "study_manifest",
        "source_dir",
        "download_manifest",
        "article_dir",
        "article_xml",
        "article_pdf",
        "supplementary_dir",
        "curated_dir",
        "reports_dir",
    }
)


class WorkspaceError(RuntimeError):
    """Base exception for study workspace errors."""


class InvalidStudyIdError(WorkspaceError, ValueError):
    """Raised when a study workspace key is unsafe or malformed."""


class WorkspaceConfigurationError(WorkspaceError):
    """Raised when the assistant home directory is not configured correctly."""


def normalize_study_id(study_id: str) -> str:
    """Validate and normalize a study workspace key.

    The identifier is used as a directory name, so path separators, parent
    directory references, whitespace-only values, and other unsafe characters
    are rejected.

    Args:
        study_id: Filesystem-safe workspace key for the study.

    Returns:
        A lowercase, filesystem-safe identifier.

    Raises:
        InvalidStudyIdError: If the identifier is empty or unsafe.
    """
    normalized = study_id.strip().lower()

    if not normalized:
        raise InvalidStudyIdError("Study ID cannot be empty.")

    if normalized in {".", ".."} or not _STUDY_ID_PATTERN.fullmatch(normalized):
        raise InvalidStudyIdError(
            "Study ID may contain only letters, numbers, dots, underscores, "
            f"and hyphens: {study_id!r}"
        )

    return normalized


def resolve_assistant_home(assistant_home: str | Path | None = None) -> Path:
    """Resolve the curation assistant home directory.

    An explicit value takes precedence over the
    ``CBIO_CURATION_ASSISTANT_HOME`` environment variable.

    Args:
        assistant_home: Optional explicit repository/workspace root.

    Returns:
        An absolute, normalized path.

    Raises:
        WorkspaceConfigurationError: If no root is configured.
    """
    configured_home = assistant_home or os.environ.get(ENV_VAR_NAME)

    if not configured_home:
        raise WorkspaceConfigurationError(
            f"{ENV_VAR_NAME} is not set and no assistant_home was provided."
        )

    return Path(configured_home).expanduser().resolve()


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkspaceConfigurationError(
            f"Workspace manifest is not valid JSON: {path}"
        ) from exc


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

    @classmethod
    def load(
        cls,
        study_id: str,
        *,
        assistant_home: str | Path | None = None,
    ) -> "StudyWorkspace":
        """Load an initialized workspace from disk using its study workspace key."""
        workspace = cls.from_study_id(study_id, assistant_home=assistant_home)
        workspace.load_manifest()
        return workspace

    @classmethod
    def from_manifest(cls, manifest_path: str | Path) -> "StudyWorkspace":
        """Load an initialized workspace from its study manifest path."""
        resolved_manifest = Path(manifest_path).expanduser().resolve()

        if resolved_manifest.name != MANIFEST_FILENAME:
            raise WorkspaceConfigurationError(
                f"Expected manifest filename {MANIFEST_FILENAME!r}, "
                f"got {resolved_manifest.name!r}."
            )

        study_root = resolved_manifest.parent

        if study_root.parent.name != STUDIES_DIRECTORY_NAME:
            raise WorkspaceConfigurationError(
                "Manifest is not located inside a standard studies/<study_id>/ workspace."
            )

        workspace = cls(
            assistant_home=study_root.parent.parent,
            study_id=normalize_study_id(study_root.name),
        )
        workspace.load_manifest()
        return workspace

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

    def create(self) -> None:
        """Create the complete standard workspace structure."""
        for directory in self.directories():
            directory.mkdir(parents=True, exist_ok=True)

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

    def as_manifest_paths(self) -> dict[str, str]:
        """Return the standard portable paths for a study manifest."""
        return {
            "study_root": ".",
            "study_manifest": self.relative_to_root(self.manifest_path),
            "source_dir": self.relative_to_root(self.source_dir),
            "download_manifest": self.relative_to_root(self.download_manifest_path),
            "article_dir": self.relative_to_root(self.article_dir),
            "article_xml": self.relative_to_root(self.article_xml_path),
            "article_pdf": self.relative_to_root(self.article_pdf_path),
            "supplementary_dir": self.relative_to_root(self.supplementary_dir),
            "curated_dir": self.relative_to_root(self.curated_dir),
            "reports_dir": self.relative_to_root(self.reports_dir),
        }

    def manifest_payload(self) -> dict[str, Any]:
        """Return the persistent workspace manifest payload."""
        return {
            "manifest_version": WORKSPACE_MANIFEST_VERSION,
            "study_id": self.study_id,
            "assistant_home_env_var": ENV_VAR_NAME,
            "studies_directory": STUDIES_DIRECTORY_NAME,
            "manifest_filename": MANIFEST_FILENAME,
            "managed_paths": self.as_manifest_paths(),
        }

    def write_manifest(self) -> Path:
        """Persist the canonical study manifest on disk."""
        self.create()
        self.manifest_path.write_text(
            json.dumps(self.manifest_payload(), indent=2, ensure_ascii=False) + os.linesep,
            encoding="utf-8",
        )
        return self.manifest_path.resolve()

    def load_manifest(self) -> dict[str, Any]:
        """Load and validate the canonical study manifest."""
        manifest_path = self.manifest_path.resolve()
        if not manifest_path.is_file():
            raise WorkspaceConfigurationError(
                f"Study manifest does not exist: {manifest_path}"
            )

        payload = _read_json_file(manifest_path)
        if not isinstance(payload, dict):
            raise WorkspaceConfigurationError(
                f"Workspace manifest must contain a JSON object: {manifest_path}"
            )

        if payload.get("manifest_version") != WORKSPACE_MANIFEST_VERSION:
            raise WorkspaceConfigurationError(
                f"Unsupported workspace manifest version in {manifest_path}: "
                f"{payload.get('manifest_version')!r}"
            )

        manifest_study_id = payload.get("study_id")
        if not isinstance(manifest_study_id, str):
            raise WorkspaceConfigurationError(
                f"Workspace manifest is missing string field 'study_id': {manifest_path}"
            )
        if normalize_study_id(manifest_study_id) != self.study_id:
            raise WorkspaceConfigurationError(
                f"Workspace manifest study_id mismatch in {manifest_path}: "
                f"expected {self.study_id!r}, found {manifest_study_id!r}"
            )

        managed_paths = payload.get("managed_paths")
        if not isinstance(managed_paths, dict):
            raise WorkspaceConfigurationError(
                f"Workspace manifest is missing object field 'managed_paths': {manifest_path}"
            )

        missing_keys = sorted(_REQUIRED_MANAGED_PATH_KEYS - set(managed_paths))
        if missing_keys:
            raise WorkspaceConfigurationError(
                f"Workspace manifest is missing managed paths {missing_keys}: {manifest_path}"
            )

        if managed_paths.get("study_root") != ".":
            raise WorkspaceConfigurationError(
                f"Workspace manifest must map 'study_root' to '.': {manifest_path}"
            )

        for key, value in managed_paths.items():
            if not isinstance(value, str) or not value.strip():
                raise WorkspaceConfigurationError(
                    f"Workspace manifest path {key!r} must be a non-empty string: {manifest_path}"
                )
            if key == "study_root":
                continue
            self.resolve_relative_path(value)

        return payload


def get_study_workspace(
    study_id: str,
    *,
    assistant_home: str | Path | None = None,
    create: bool = False,
    require_manifest: bool = False,
) -> StudyWorkspace:
    """Resolve a study workspace, optionally initializing or validating it."""
    workspace = StudyWorkspace.from_study_id(
        study_id,
        assistant_home=assistant_home,
    )

    if create:
        workspace.write_manifest()

    if require_manifest:
        workspace.load_manifest()

    return workspace
