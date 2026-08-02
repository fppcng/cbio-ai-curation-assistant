"""Build agent-facing workspace discovery data."""

from __future__ import annotations

from typing import Any

from cbio_curation_assistant.workspace.layout import StudyWorkspace
from cbio_curation_assistant.workspace.manifest import load_workspace_manifest


def build_workspace_discovery(workspace: StudyWorkspace) -> dict[str, Any]:
    """Return absolute workspace paths and artifact availability."""
    load_workspace_manifest(workspace)
    return {
        "study_id": workspace.study_id,
        "workspace": {
            "root": str(workspace.root.resolve()),
            "source": str(workspace.source_dir.resolve()),
            "article": str(workspace.article_dir.resolve()),
            "supplementary": str(workspace.supplementary_dir.resolve()),
            "curated": str(workspace.curated_dir.resolve()),
            "reports": str(workspace.reports_dir.resolve()),
        },
        "manifests": {
            "study": str(workspace.manifest_path.resolve()),
            "download": str(workspace.download_manifest_path.resolve()),
        },
        "artifacts": {
            "article_xml": str(workspace.article_xml_path.resolve()),
            "article_pdf": str(workspace.article_pdf_path.resolve()),
            "curation_report_agent": str(
                workspace.curation_report_agent_path.resolve()
            ),
        },
        "availability": {
            "download_manifest": workspace.download_manifest_path.is_file(),
            "article_xml": workspace.article_xml_path.is_file(),
            "article_pdf": workspace.article_pdf_path.is_file(),
            "curation_report_agent": workspace.curation_report_agent_path.is_file(),
        },
    }


__all__ = ["build_workspace_discovery"]
