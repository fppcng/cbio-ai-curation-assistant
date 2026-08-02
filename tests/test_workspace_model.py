from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cbio_curation_assistant.workspace.configuration import (
    InvalidStudyIdError,
    WorkspaceConfigurationError,
    normalize_study_id,
)
from cbio_curation_assistant.workspace.discovery import build_workspace_discovery
from cbio_curation_assistant.workspace.layout import StudyWorkspace
from cbio_curation_assistant.workspace.lifecycle import (
    create_workspace_directories,
    initialize_workspace,
    load_workspace_from_manifest,
)
from cbio_curation_assistant.workspace.manifest import (
    build_manifest_payload,
    load_workspace_manifest,
)


class WorkspaceModelTest(unittest.TestCase):
    def test_study_id_is_trimmed_lowercased_and_restricted(self) -> None:
        self.assertEqual(normalize_study_id(" PMC.123_A-1 "), "pmc.123_a-1")
        for value in ("", ".", "..", "../study", "study/name", "white space"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidStudyIdError):
                    normalize_study_id(value)

    def test_create_builds_the_canonical_directory_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = StudyWorkspace.from_study_id("PMC1", assistant_home=tmp_dir)
            create_workspace_directories(workspace)

            for directory in workspace.directories():
                self.assertTrue(directory.is_dir(), directory)

    def test_manifest_round_trip_and_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = StudyWorkspace.from_study_id("PMC1", assistant_home=tmp_dir)
            manifest_path = initialize_workspace(workspace)
            loaded = load_workspace_from_manifest(manifest_path)

            self.assertEqual(loaded, workspace)
            self.assertEqual(
                load_workspace_manifest(loaded),
                build_manifest_payload(workspace),
            )

    def test_manifest_must_be_valid_json_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = StudyWorkspace.from_study_id("PMC1", assistant_home=tmp_dir)
            create_workspace_directories(workspace)

            workspace.manifest_path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceConfigurationError, "not valid JSON"):
                load_workspace_manifest(workspace)

            workspace.manifest_path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceConfigurationError, "JSON object"):
                load_workspace_manifest(workspace)

    def test_manifest_rejects_version_and_study_id_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = StudyWorkspace.from_study_id("PMC1", assistant_home=tmp_dir)
            initialize_workspace(workspace)
            payload = build_manifest_payload(workspace)

            payload["manifest_version"] = 999
            workspace.manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceConfigurationError, "Unsupported"):
                load_workspace_manifest(workspace)

            payload = build_manifest_payload(workspace)
            payload["study_id"] = "pmc2"
            workspace.manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceConfigurationError, "mismatch"):
                load_workspace_manifest(workspace)

    def test_paths_cannot_escape_the_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = StudyWorkspace.from_study_id("PMC1", assistant_home=tmp_dir)
            create_workspace_directories(workspace)
            outside = Path(tmp_dir) / "outside.txt"

            self.assertFalse(workspace.contains(outside))
            with self.assertRaisesRegex(WorkspaceConfigurationError, "outside"):
                workspace.require_inside_workspace(outside)
            with self.assertRaisesRegex(WorkspaceConfigurationError, "outside"):
                workspace.resolve_relative_path("../outside.txt")

    def test_discovery_payload_reports_current_artifact_availability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = StudyWorkspace.from_study_id("PMC1", assistant_home=tmp_dir)
            initialize_workspace(workspace)
            workspace.article_pdf_path.write_bytes(b"%PDF-")

            payload = build_workspace_discovery(workspace)

            self.assertNotIn("schema_version", payload)
            self.assertNotIn("status", payload)
            self.assertTrue(payload["availability"]["article_pdf"])
            self.assertFalse(payload["availability"]["article_xml"])
            self.assertEqual(
                payload["artifacts"]["article_pdf"],
                str(workspace.article_pdf_path.resolve()),
            )


if __name__ == "__main__":
    unittest.main()
