from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cbio_curation_assistant.hermes_llm import resolve_optional_hermes_llm_config
from tests.curation_report.abstractor_report_regression_support import (
    ARTIFACTS_ROOT,
    GOLD_REPORT_PATH,
    NO_LLM_WARNING,
    STUDY_ID,
    STUDY_ROOT,
    build_artifact_paths,
    build_timestamp_label,
    load_gold_report,
    load_report_generator_module,
    project_deterministic_report_fields,
    run_report_generation,
)


class AbstractorReportRegressionTest(unittest.TestCase):
    def test_pmc8317046_deterministic_fields_match_gold(self) -> None:
        self.assertTrue(STUDY_ROOT.is_dir(), f"Study workspace is missing: {STUDY_ROOT}")
        self.assertTrue(GOLD_REPORT_PATH.is_file(), f"Gold report is missing: {GOLD_REPORT_PATH}")

        report_generator = load_report_generator_module()

        with tempfile.TemporaryDirectory(prefix="abstractor_regression_") as tmp_dir:
            output_json_path = Path(tmp_dir) / "pmc8317046_regression_report.json"
            output_pdf_path = Path(tmp_dir) / "pmc8317046_regression_report.pdf"
            result, generated_report = run_report_generation(
                report_generator=report_generator,
                study_id=STUDY_ID,
                output_json_path=output_json_path,
                output_pdf_path=output_pdf_path,
                use_llm=False,
                embedded_spec_tag="report-regression-deterministic",
            )

            self.assertEqual(result.inputs.paper_source.kind, "xml")
            self.assertFalse(result.llm.enabled)
            self.assertEqual(result.warnings, (NO_LLM_WARNING,))
            agent_report_path = output_json_path.with_name("pmc8317046_regression_report_agent_report.json")
            self.assertEqual(result.outputs.curation_report_json, output_json_path.resolve())
            self.assertEqual(result.outputs.pdf, output_pdf_path.resolve())
            self.assertEqual(result.outputs.agent_report_json, agent_report_path.resolve())
            self.assertTrue(output_json_path.is_file())
            self.assertTrue(output_pdf_path.is_file())
            self.assertTrue(agent_report_path.is_file())
            self.assertEqual(result.agent_report.schema_version, 1)
            self.assertEqual(result.agent_report.status, "success")
            self.assertEqual(result.agent_report.result.paper_source.kind, "xml")
            self.assertEqual(result.agent_report.warnings, (NO_LLM_WARNING,))

        gold_report = load_gold_report()

        self.maxDiff = None
        self.assertEqual(
            project_deterministic_report_fields(generated_report),
            project_deterministic_report_fields(gold_report),
        )

    def test_pmc8317046_llm_review_run_generates_artifacts_under_tests(self) -> None:
        self.assertTrue(STUDY_ROOT.is_dir(), f"Study workspace is missing: {STUDY_ROOT}")
        self.assertTrue(GOLD_REPORT_PATH.is_file(), f"Gold report is missing: {GOLD_REPORT_PATH}")

        report_generator = load_report_generator_module()
        llm_config = resolve_optional_hermes_llm_config()
        if llm_config is None:
            self.skipTest("No complete Hermes LLM configuration is available in the current environment.")

        timestamp_label = f"review_{build_timestamp_label()}"
        _, output_json_path, output_pdf_path = build_artifact_paths(
            STUDY_ID,
            mode="llm",
            timestamp_label=timestamp_label,
        )
        result, generated_report = run_report_generation(
            report_generator=report_generator,
            study_id=STUDY_ID,
            output_json_path=output_json_path,
            output_pdf_path=output_pdf_path,
            use_llm=True,
            embedded_spec_tag="report-regression-llm",
        )

        self.assertEqual(result.inputs.paper_source.kind, "xml")
        self.assertTrue(result.llm.enabled)
        self.assertEqual(result.llm.provider, llm_config.provider)
        self.assertEqual(result.llm.model, llm_config.model)
        agent_report_path = output_json_path.with_name(f"{output_json_path.stem}_agent_report.json")
        self.assertEqual(result.outputs.curation_report_json, output_json_path.resolve())
        self.assertEqual(result.outputs.pdf, output_pdf_path.resolve())
        self.assertEqual(result.outputs.agent_report_json, agent_report_path.resolve())
        self.assertTrue(output_json_path.is_file())
        self.assertTrue(output_pdf_path.is_file())
        self.assertTrue(agent_report_path.is_file())
        self.assertTrue(output_json_path.resolve().is_relative_to(ARTIFACTS_ROOT.resolve()))
        self.assertTrue(output_pdf_path.resolve().is_relative_to(ARTIFACTS_ROOT.resolve()))
        self.assertIn(f"/{timestamp_label}/", output_json_path.resolve().as_posix())
        self.assertNotIn(NO_LLM_WARNING, result.warnings)
        self.assertEqual(
            set(generated_report),
            {
                "report_title",
                "study_title",
                "citation",
                "study_overview",
                "supplementary_file_analysis",
                "per_sheet_classification_detail",
                "suggested_study_metadata",
            },
        )

        gold_report = load_gold_report()
        self.maxDiff = None
        self.assertEqual(
            project_deterministic_report_fields(generated_report),
            project_deterministic_report_fields(gold_report),
        )


if __name__ == "__main__":
    unittest.main()
