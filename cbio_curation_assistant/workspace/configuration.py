"""Workspace configuration, constants, and identifier validation."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Final


ENV_VAR_NAME: Final[str] = "CBIO_CURATION_ASSISTANT_HOME"
STUDIES_DIRECTORY_NAME: Final[str] = "studies"
MANIFEST_FILENAME: Final[str] = "study_manifest.json"
DOWNLOAD_MANIFEST_FILENAME: Final[str] = "download_manifest.json"
WORKSPACE_MANIFEST_VERSION: Final[int] = 1

_STUDY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class WorkspaceError(RuntimeError):
    """Base exception for study workspace errors."""


class InvalidStudyIdError(WorkspaceError, ValueError):
    """Raised when a study workspace key is unsafe or malformed."""


class WorkspaceConfigurationError(WorkspaceError):
    """Raised when the assistant home directory is not configured correctly."""


def normalize_study_id(study_id: str) -> str:
    """Validate and normalize a filesystem-safe study workspace key."""
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
    """Resolve the explicit or environment-configured assistant home."""
    configured_home = assistant_home or os.environ.get(ENV_VAR_NAME)
    if not configured_home:
        raise WorkspaceConfigurationError(
            f"{ENV_VAR_NAME} is not set and no assistant_home was provided."
        )
    return Path(configured_home).expanduser().resolve()


__all__ = [
    "DOWNLOAD_MANIFEST_FILENAME",
    "ENV_VAR_NAME",
    "InvalidStudyIdError",
    "MANIFEST_FILENAME",
    "STUDIES_DIRECTORY_NAME",
    "WORKSPACE_MANIFEST_VERSION",
    "WorkspaceConfigurationError",
    "WorkspaceError",
    "normalize_study_id",
    "resolve_assistant_home",
]
