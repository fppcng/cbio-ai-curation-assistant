"""Create and load study workspaces."""

from __future__ import annotations

from pathlib import Path

from cbio_curation_assistant.workspace.configuration import (
    MANIFEST_FILENAME,
    STUDIES_DIRECTORY_NAME,
    WorkspaceConfigurationError,
    normalize_study_id,
)
from cbio_curation_assistant.workspace.layout import StudyWorkspace
from cbio_curation_assistant.workspace.manifest import (
    load_workspace_manifest,
    write_workspace_manifest,
)


def create_workspace_directories(workspace: StudyWorkspace) -> None:
    """Create the complete standard workspace structure."""
    for directory in workspace.directories():
        directory.mkdir(parents=True, exist_ok=True)


def initialize_workspace(workspace: StudyWorkspace) -> Path:
    """Create directories and preserve an existing valid manifest."""
    create_workspace_directories(workspace)
    if workspace.manifest_path.exists():
        load_workspace_manifest(workspace)
        return workspace.manifest_path.resolve()
    return write_workspace_manifest(workspace)


def load_workspace(
    study_id: str,
    *,
    assistant_home: str | Path | None = None,
) -> StudyWorkspace:
    """Load an initialized workspace by study identifier."""
    workspace = StudyWorkspace.from_study_id(
        study_id,
        assistant_home=assistant_home,
    )
    load_workspace_manifest(workspace)
    return workspace


def load_workspace_from_manifest(manifest_path: str | Path) -> StudyWorkspace:
    """Load an initialized workspace from its canonical manifest path."""
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

    workspace = StudyWorkspace(
        assistant_home=study_root.parent.parent,
        study_id=normalize_study_id(study_root.name),
    )
    load_workspace_manifest(workspace)
    return workspace


__all__ = [
    "create_workspace_directories",
    "initialize_workspace",
    "load_workspace",
    "load_workspace_from_manifest",
]
