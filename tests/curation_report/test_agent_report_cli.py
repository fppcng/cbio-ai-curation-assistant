from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cbio_curation_assistant.workspace import ENV_VAR_NAME, StudyWorkspace
from tests.curation_report.abstractor_report_regression_support import load_report_generator_module


class AgentReportCliTest(unittest.TestCase):
    def test_cli_prints_and_writes_deterministic_agent_report(self) -> None:
        report_generator = load_report_generator_module()

        with tempfile.TemporaryDirectory(prefix="agent_report_cli_") as tmp_dir:
            home = Path(tmp_dir)
            workspace = StudyWorkspace.from_study_id("pmc1234567", assistant_home=home)
            workspace.initialize()
            workspace.article_xml_path.write_text("<article />", encoding="utf-8")
            supplementary_path = workspace.supplementary_dir / "table.xlsx"
            supplementary_path.write_bytes(b"placeholder")

            def fake_save_pdf(meta, summary, output_pdf_path):
                destination = Path(output_pdf_path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.4\n")
                return str(destination.resolve())

            stdout = io.StringIO()
            with mock.patch.dict(os.environ, {ENV_VAR_NAME: str(home)}, clear=False):
                with mock.patch.object(report_generator, "resolve_optional_hermes_llm_config", return_value=None):
                    with mock.patch.object(
                        report_generator,
                        "extract_xml_metadata_with_llm",
                        return_value={"study_id_suggestion": workspace.study_id},
                    ):
                        with mock.patch.object(
                            report_generator,
                            "_analyse_supplementary_files",
                            return_value=[
                                {
                                    "file": supplementary_path.name,
                                    "sheet": "Sheet1",
                                    "curability": "YES",
                                    "priority": "HIGH",
                                }
                            ],
                        ):
                            with mock.patch.object(report_generator, "save_curation_report_pdf", side_effect=fake_save_pdf):
                                with mock.patch.object(
                                    report_generator,
                                    "build_curation_report_json",
                                    return_value={"report_title": "Test report"},
                                ):
                                    with contextlib.redirect_stdout(stdout):
                                        code = report_generator.main(["--study-id", workspace.study_id])

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["status"], "success")
            self.assertTrue(payload["success"])
            self.assertEqual(payload["study_id"], workspace.study_id)
            self.assertEqual(payload["paper_source"]["type"], "xml")
            self.assertEqual(payload["paper_source"]["path"], str(workspace.article_xml_path.resolve()))
            self.assertEqual(payload["supplementary_files"]["count"], 1)
            self.assertEqual(payload["supplementary_files"]["paths"], [str(supplementary_path.resolve())])
            self.assertFalse(payload["llm_metadata_extraction"]["enabled"])
            self.assertEqual(payload["warnings"], [])
            self.assertEqual(payload["outputs"]["agent_report_json"], str(workspace.curation_report_agent_path.resolve()))
            self.assertTrue(workspace.curation_report_agent_path.is_file())
            self.assertEqual(
                json.loads(workspace.curation_report_agent_path.read_text(encoding="utf-8")),
                payload,
            )


if __name__ == "__main__":
    unittest.main()
