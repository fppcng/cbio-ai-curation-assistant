from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cbio_curation_assistant.workspace import StudyWorkspace
from tests.curation_report.abstractor_report_regression_support import (
    NO_LLM_WARNING,
    SYNTHETIC_ARTICLE_PATH,
    SYNTHETIC_METADATA_PATH,
    load_report_generator_module,
)


class AbstractorReportRegressionTest(unittest.TestCase):
    def test_synthetic_jats_metadata_matches_sanitized_fixture(self) -> None:
        expected_metadata = json.loads(
            SYNTHETIC_METADATA_PATH.read_text(encoding="utf-8")
        )
        report_generator = load_report_generator_module()

        with tempfile.TemporaryDirectory(
            prefix="abstractor_regression_"
        ) as tmp_dir:
            root = Path(tmp_dir)
            workspace = StudyWorkspace.from_study_id(
                "synthetic-publication",
                assistant_home=root,
            )
            workspace.initialize()
            workspace.article_xml_path.write_bytes(
                SYNTHETIC_ARTICLE_PATH.read_bytes()
            )
            supplement_path = workspace.supplementary_dir / "samples.csv"
            supplement_path.write_text(
                "PATIENT_ID,SAMPLE_ID\nP1,S1\n",
                encoding="utf-8",
            )
            output_json_path = workspace.reports_dir / "report.json"
            output_pdf_path = workspace.reports_dir / "report.pdf"

            with mock.patch.object(
                report_generator,
                "resolve_optional_hermes_llm_config",
                return_value=None,
            ):
                result = report_generator.run_curation_orchestrator(
                    paper_xml_path=str(workspace.article_xml_path),
                    supplementary_paths=[supplement_path],
                    study_workspace=workspace,
                    output_json_path=str(output_json_path),
                    output_pdf_path=str(output_pdf_path),
                )

            persisted_report = json.loads(
                output_json_path.read_text(encoding="utf-8")
            )

        self.assertEqual(result.metadata.to_dict(), expected_metadata)
        self.assertEqual(result.warnings, (NO_LLM_WARNING,))
        self.assertEqual(result.inputs.paper_source.kind, "xml")
        self.assertFalse(result.llm.enabled)
        self.assertEqual(
            persisted_report["study_overview"]["corresponding_authors"],
            "Smith Ada, curator@example.org",
        )
        self.assertNotIn("[redacted-email]", json.dumps(persisted_report))


if __name__ == "__main__":
    unittest.main()
