from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cbio_curation_assistant.workspace import (
    InvalidStudyIdError,
    StudyWorkspace,
    WorkspaceConfigurationError,
    normalize_study_id,
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
            workspace.create()

            for directory in workspace.directories():
                self.assertTrue(directory.is_dir(), directory)

    def test_manifest_round_trip_and_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = StudyWorkspace.from_study_id("PMC1", assistant_home=tmp_dir)
            manifest_path = workspace.initialize()
            loaded = StudyWorkspace.from_manifest(manifest_path)

            self.assertEqual(loaded, workspace)
            self.assertEqual(loaded.load_manifest(), workspace.manifest_payload())

    def test_manifest_must_be_valid_json_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = StudyWorkspace.from_study_id("PMC1", assistant_home=tmp_dir)
            workspace.create()

            workspace.manifest_path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceConfigurationError, "not valid JSON"):
                workspace.load_manifest()

            workspace.manifest_path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceConfigurationError, "JSON object"):
                workspace.load_manifest()

    def test_manifest_rejects_version_and_study_id_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = StudyWorkspace.from_study_id("PMC1", assistant_home=tmp_dir)
            workspace.initialize()
            payload = workspace.manifest_payload()

            payload["manifest_version"] = 999
            workspace.manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceConfigurationError, "Unsupported"):
                workspace.load_manifest()

            payload = workspace.manifest_payload()
            payload["study_id"] = "pmc2"
            workspace.manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceConfigurationError, "mismatch"):
                workspace.load_manifest()

    def test_paths_cannot_escape_the_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = StudyWorkspace.from_study_id("PMC1", assistant_home=tmp_dir)
            workspace.create()
            outside = Path(tmp_dir) / "outside.txt"

            self.assertFalse(workspace.contains(outside))
            with self.assertRaisesRegex(WorkspaceConfigurationError, "outside"):
                workspace.require_inside_workspace(outside)
            with self.assertRaisesRegex(WorkspaceConfigurationError, "outside"):
                workspace.resolve_relative_path("../outside.txt")

    def test_discovery_payload_reports_current_artifact_availability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = StudyWorkspace.from_study_id("PMC1", assistant_home=tmp_dir)
            workspace.initialize()
            workspace.article_pdf_path.write_bytes(b"%PDF-")

            payload = workspace.discovery_payload()

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
