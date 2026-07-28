from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cbio_curation_assistant import cli
from cbio_curation_assistant.workspace import (
    ENV_VAR_NAME,
    StudyWorkspace,
    get_study_workspace,
)


def invoke_cli(argv: list[str], env: dict[str, str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with patch.dict(os.environ, env, clear=True):
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = cli.main(argv)
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
    return code, stdout.getvalue(), stderr.getvalue()


class WorkspaceDescribeCliTest(unittest.TestCase):
    def create_workspace(self, home: Path, study_id: str = "PMC6753053") -> StudyWorkspace:
        workspace = StudyWorkspace.from_study_id(study_id, assistant_home=home)
        workspace.initialize()
        return workspace

    def describe(self, home: Path, study_id: str) -> tuple[int, str, str]:
        return invoke_cli(
            ["workspace", "describe", "--study-id", study_id],
            {ENV_VAR_NAME: str(home)},
        )

    def test_workspace_describe_success_outputs_only_valid_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workspace_describe_") as tmp_dir:
            home = Path(tmp_dir)
            workspace = self.create_workspace(home)

            code, stdout, stderr = self.describe(home, workspace.study_id)

            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(stdout, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["command"], "workspace.describe")
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["warnings"], [])
            self.assertIsNone(payload["error"])
            self.assertEqual(payload["result"]["study_id"], workspace.study_id)

    def test_workspace_describe_reports_absolute_canonical_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workspace_describe_") as tmp_dir:
            home = Path(tmp_dir)
            workspace = self.create_workspace(home)

            code, stdout, stderr = self.describe(home, workspace.study_id)
            payload = json.loads(stdout)
            result = payload["result"]

            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            self.assertEqual(result["workspace"]["root"], str(workspace.root.resolve()))
            self.assertEqual(result["workspace"]["source"], str(workspace.source_dir.resolve()))
            self.assertEqual(result["workspace"]["article"], str(workspace.article_dir.resolve()))
            self.assertEqual(result["workspace"]["supplementary"], str(workspace.supplementary_dir.resolve()))
            self.assertEqual(result["workspace"]["curated"], str(workspace.curated_dir.resolve()))
            self.assertEqual(result["workspace"]["reports"], str(workspace.reports_dir.resolve()))
            self.assertEqual(result["manifests"]["study"], str(workspace.manifest_path.resolve()))
            self.assertEqual(result["manifests"]["download"], str(workspace.download_manifest_path.resolve()))
            self.assertEqual(result["artifacts"]["article_xml"], str(workspace.article_xml_path.resolve()))
            self.assertEqual(result["artifacts"]["article_pdf"], str(workspace.article_pdf_path.resolve()))
            self.assertEqual(
                result["artifacts"]["curation_report_agent"],
                str(workspace.curation_report_agent_path.resolve()),
            )

            for section in ("workspace", "manifests", "artifacts"):
                for value in result[section].values():
                    self.assertTrue(Path(value).is_absolute(), value)

    def test_workspace_describe_reports_optional_artifact_availability(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workspace_describe_") as tmp_dir:
            home = Path(tmp_dir)
            workspace = self.create_workspace(home)
            workspace.article_xml_path.write_text("<article />", encoding="utf-8")
            workspace.download_manifest_path.write_text("{}\n", encoding="utf-8")

            code, stdout, stderr = self.describe(home, workspace.study_id)
            payload = json.loads(stdout)
            result = payload["result"]

            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            self.assertTrue(result["availability"]["download_manifest"])
            self.assertTrue(result["availability"]["article_xml"])
            self.assertFalse(result["availability"]["article_pdf"])
            self.assertFalse(result["availability"]["curation_report_agent"])

    def test_invalid_study_id_returns_structured_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workspace_describe_") as tmp_dir:
            code, stdout, stderr = self.describe(Path(tmp_dir), "../bad")

            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["status"], "error")
            self.assertIn("Study ID", payload["error"]["message"])

    def test_missing_assistant_home_returns_structured_error(self) -> None:
        code, stdout, stderr = invoke_cli(
            ["workspace", "describe", "--study-id", "pmc6753053"],
            {},
        )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertIn(ENV_VAR_NAME, payload["error"]["message"])

    def test_missing_study_manifest_returns_nonzero_and_does_not_create_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workspace_describe_") as tmp_dir:
            home = Path(tmp_dir)
            study_id = "pmc6753053"
            study_root = home / "studies" / study_id

            code, stdout, stderr = self.describe(home, study_id)

            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertIn("Study manifest does not exist", payload["error"]["message"])
            self.assertFalse(study_root.exists())

    def test_workspace_describe_does_not_modify_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workspace_describe_") as tmp_dir:
            home = Path(tmp_dir)
            workspace = self.create_workspace(home)
            before_content = workspace.manifest_path.read_text(encoding="utf-8")
            before_mtime_ns = workspace.manifest_path.stat().st_mtime_ns

            code, stdout, stderr = self.describe(home, workspace.study_id)

            self.assertEqual(code, 0)
            self.assertNotEqual(stdout, "")
            self.assertEqual(stderr, "")
            self.assertEqual(workspace.manifest_path.read_text(encoding="utf-8"), before_content)
            self.assertEqual(workspace.manifest_path.stat().st_mtime_ns, before_mtime_ns)

    def test_noncanonical_managed_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workspace_describe_") as tmp_dir:
            home = Path(tmp_dir)
            workspace = self.create_workspace(home)
            payload = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
            payload["managed_paths"]["article_dir"] = "curated"
            workspace.manifest_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            code, stdout, stderr = self.describe(home, workspace.study_id)

            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertIn("noncanonical managed paths", payload["error"]["message"])

    def test_repeated_workspace_initialization_preserves_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workspace_describe_") as tmp_dir:
            home = Path(tmp_dir)
            workspace = self.create_workspace(home)
            payload = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
            payload["preserved"] = "keep"
            workspace.manifest_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            before = workspace.manifest_path.read_text(encoding="utf-8")

            get_study_workspace(workspace.study_id, assistant_home=home, create=True)

            self.assertEqual(workspace.manifest_path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
