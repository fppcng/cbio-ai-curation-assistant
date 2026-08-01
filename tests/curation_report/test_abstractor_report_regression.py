from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cbio_curation_assistant.workspace import StudyWorkspace
from cbio_curation_assistant.workflows import curation_report
from tests.curation_report.abstractor_report_regression_support import (
    NO_LLM_WARNING,
    SYNTHETIC_ARTICLE_PATH,
    SYNTHETIC_METADATA_PATH,
)


class AbstractorReportRegressionTest(unittest.TestCase):
    def test_synthetic_jats_metadata_matches_sanitized_fixture(self) -> None:
        expected_metadata = json.loads(
            SYNTHETIC_METADATA_PATH.read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory(prefix="abstractor_regression_") as tmp_dir:
            root = Path(tmp_dir)
            workspace = StudyWorkspace.from_study_id(
                "synthetic-publication",
                assistant_home=root,
            )
            workspace.initialize()
            workspace.article_xml_path.write_bytes(SYNTHETIC_ARTICLE_PATH.read_bytes())
            supplement_path = workspace.supplementary_dir / "samples.csv"
            supplement_path.write_text(
                "PATIENT_ID,SAMPLE_ID\nP1,S1\n",
                encoding="utf-8",
            )
            output_json_path = workspace.reports_dir / "report.json"
            output_pdf_path = workspace.reports_dir / "report.pdf"

            result = curation_report.run_curation_report(
                curation_report.CurationReportInputs(
                    paper_source=curation_report.PaperSource(
                        kind="xml",
                        path=workspace.article_xml_path,
                    ),
                    supplementary_paths=(supplement_path,),
                ),
                study_workspace=workspace,
                output_json_path=str(output_json_path),
                output_pdf_path=str(output_pdf_path),
            )

            persisted_report = json.loads(output_json_path.read_text(encoding="utf-8"))

        self.assertEqual(result.metadata.to_dict(), expected_metadata)
        self.assertEqual(result.warnings, (NO_LLM_WARNING,))
        self.assertEqual(result.inputs.paper_source.kind, "xml")
        self.assertFalse(result.llm.enabled)
        self.assertEqual(
            persisted_report["study_overview"]["corresponding_authors"],
            "Smith Ada, curator@example.org",
        )
        self.assertNotIn("[redacted-email]", json.dumps(persisted_report))


class CurationReportInputDiscoveryTest(unittest.TestCase):
    def test_xml_precedes_pdf_and_supplements_are_discovered_recursively(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="report_discovery_") as tmp_dir:
            workspace = StudyWorkspace.from_study_id(
                "pmc123",
                assistant_home=Path(tmp_dir),
            )
            workspace.initialize()
            workspace.article_xml_path.write_text(
                "<article />",
                encoding="utf-8",
            )
            workspace.article_pdf_path.write_bytes(b"%PDF-1.4\n")
            nested = workspace.supplementary_dir / "nested"
            nested.mkdir()
            supplement = nested / "table.csv"
            supplement.write_text("SAMPLE_ID\nS1\n", encoding="utf-8")
            (nested / "notes.unsupported").write_text(
                "ignored",
                encoding="utf-8",
            )

            inputs, warnings = curation_report.discover_curation_report_inputs(
                workspace
            )

        self.assertEqual(inputs.paper_source.kind, "xml")
        self.assertEqual(inputs.paper_source.path, workspace.article_xml_path)
        self.assertEqual(inputs.supplementary_paths, (supplement,))
        self.assertEqual(
            inputs.supplementary_selection,
            "workspace_recursive",
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("using XML", warnings[0])

    def test_pdf_is_used_when_xml_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="report_discovery_") as tmp_dir:
            workspace = StudyWorkspace.from_study_id(
                "pmc123",
                assistant_home=Path(tmp_dir),
            )
            workspace.initialize()
            workspace.article_pdf_path.write_bytes(b"%PDF-1.4\n")
            (workspace.supplementary_dir / "table.csv").write_text(
                "SAMPLE_ID\nS1\n",
                encoding="utf-8",
            )

            inputs, warnings = curation_report.discover_curation_report_inputs(
                workspace
            )

        self.assertEqual(inputs.paper_source.kind, "pdf")
        self.assertEqual(warnings, ())

    def test_missing_canonical_article_is_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="report_discovery_") as tmp_dir:
            workspace = StudyWorkspace.from_study_id(
                "pmc123",
                assistant_home=Path(tmp_dir),
            )
            workspace.initialize()

            with self.assertRaisesRegex(
                FileNotFoundError,
                "No canonical article source",
            ):
                curation_report.discover_curation_report_inputs(workspace)


if __name__ == "__main__":
    unittest.main()
