"""Build, persist, and validate canonical workspace manifests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Final

from cbio_curation_assistant.workspace.configuration import (
    ENV_VAR_NAME,
    MANIFEST_FILENAME,
    STUDIES_DIRECTORY_NAME,
    WORKSPACE_MANIFEST_VERSION,
    WorkspaceConfigurationError,
    normalize_study_id,
)
from cbio_curation_assistant.workspace.layout import StudyWorkspace


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


def workspace_manifest_paths(workspace: StudyWorkspace) -> dict[str, str]:
    """Return the standard portable paths for a study manifest."""
    return {
        "study_root": ".",
        "study_manifest": workspace.relative_to_root(workspace.manifest_path),
        "source_dir": workspace.relative_to_root(workspace.source_dir),
        "download_manifest": workspace.relative_to_root(
            workspace.download_manifest_path
        ),
        "article_dir": workspace.relative_to_root(workspace.article_dir),
        "article_xml": workspace.relative_to_root(workspace.article_xml_path),
        "article_pdf": workspace.relative_to_root(workspace.article_pdf_path),
        "supplementary_dir": workspace.relative_to_root(workspace.supplementary_dir),
        "curated_dir": workspace.relative_to_root(workspace.curated_dir),
        "reports_dir": workspace.relative_to_root(workspace.reports_dir),
    }


def build_manifest_payload(workspace: StudyWorkspace) -> dict[str, Any]:
    """Return the persistent workspace manifest payload."""
    return {
        "manifest_version": WORKSPACE_MANIFEST_VERSION,
        "study_id": workspace.study_id,
        "assistant_home_env_var": ENV_VAR_NAME,
        "studies_directory": STUDIES_DIRECTORY_NAME,
        "manifest_filename": MANIFEST_FILENAME,
        "managed_paths": workspace_manifest_paths(workspace),
    }


def write_workspace_manifest(workspace: StudyWorkspace) -> Path:
    """Persist the canonical study manifest on disk."""
    workspace.manifest_path.write_text(
        json.dumps(build_manifest_payload(workspace), indent=2, ensure_ascii=False)
        + os.linesep,
        encoding="utf-8",
    )
    return workspace.manifest_path.resolve()


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkspaceConfigurationError(
            f"Workspace manifest is not valid JSON: {path}"
        ) from exc


def load_workspace_manifest(workspace: StudyWorkspace) -> dict[str, Any]:
    """Load and validate the canonical study manifest."""
    manifest_path = workspace.manifest_path.resolve()
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
    if normalize_study_id(manifest_study_id) != workspace.study_id:
        raise WorkspaceConfigurationError(
            f"Workspace manifest study_id mismatch in {manifest_path}: "
            f"expected {workspace.study_id!r}, found {manifest_study_id!r}"
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

    canonical_paths = workspace_manifest_paths(workspace)
    noncanonical_paths = {
        key: managed_paths.get(key)
        for key, canonical_value in canonical_paths.items()
        if managed_paths.get(key) != canonical_value
    }
    if noncanonical_paths:
        raise WorkspaceConfigurationError(
            "Workspace manifest contains noncanonical managed paths "
            f"{sorted(noncanonical_paths)}: {manifest_path}"
        )

    for key, value in managed_paths.items():
        if not isinstance(value, str) or not value.strip():
            raise WorkspaceConfigurationError(
                f"Workspace manifest path {key!r} must be a non-empty string: "
                f"{manifest_path}"
            )
        if key != "study_root":
            workspace.resolve_relative_path(value)
    return payload


__all__ = [
    "build_manifest_payload",
    "load_workspace_manifest",
    "workspace_manifest_paths",
    "write_workspace_manifest",
]
