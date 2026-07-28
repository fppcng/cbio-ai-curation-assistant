from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from cbio_curation_assistant.config import LLMConfig
from cbio_curation_assistant.pmc_supplement_fetcher import PMCErrorClassification
from cbio_curation_assistant.workspace import StudyWorkspace
from tests.script_loader import load_script_module


DOWNLOAD_SCRIPT = (
    "hermes_skills/abstractor-study-download/scripts/abstractor_study_download.py"
)
REPORT_SCRIPT = (
    "hermes_skills/abstractor-curation-report-generation/scripts/"
    "abstractor_report_generator.py"
)
GENOME_NEXUS_SCRIPT = (
    "hermes_skills/curator-mutation-data-file-creation/scripts/run_genome_nexus.py"
)


class StudyDownloadWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = load_script_module(
            "study_download_characterization",
            DOWNLOAD_SCRIPT,
        )

    def test_successful_download_initializes_workspace_and_persists_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            home = Path(tmp_dir)

            def ensure_xml(path: Path, pmcid: str) -> tuple[Path, bool]:
                path.write_text("<article />", encoding="utf-8")
                return path, False

            def ensure_supplements(
                pmcid: str,
                supplementary_dir: Path,
                warnings: list[str],
            ) -> tuple[list[Path], bool]:
                path = supplementary_dir / "table.csv"
                path.write_text("sample,value\nS1,1\n", encoding="utf-8")
                return [path], False

            with (
                patch.object(
                    self.workflow,
                    "_resolve_download_identifier",
                    return_value=self.workflow.ResolvedStudyIdentifier(
                        input_identifier="PMC123",
                        identifier_type="PMCID",
                        normalized_identifier="PMC123",
                        pmcid="PMC123",
                    ),
                ),
                patch.object(self.workflow, "_ensure_xml", side_effect=ensure_xml),
                patch.object(
                    self.workflow,
                    "_ensure_supplementary_files",
                    side_effect=ensure_supplements,
                ),
                patch.object(
                    self.workflow,
                    "_ensure_article_pdf",
                    return_value=(None, False),
                ),
            ):
                result = self.workflow.run_study_download(
                    identifier="PMC123",
                    identifier_type="pmcid",
                    assistant_home=home,
                )

            workspace = StudyWorkspace.load("pmc123", assistant_home=home)
            persisted = json.loads(
                workspace.download_manifest_path.read_text(encoding="utf-8")
            )

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["success"])
        self.assertEqual(result["study_id"], "pmc123")
        self.assertEqual(result["artifacts"]["supplementary_count"], 1)
        self.assertEqual(persisted, result)

    def test_main_renders_pmc_errors_as_json(self) -> None:
        error = self.workflow.PMCRequestError(
            operation="download",
            classification=PMCErrorClassification(
                category="remote_not_found",
                retryable=False,
                status_code=404,
            ),
            detail="missing",
        )
        stdout = io.StringIO()
        args = argparse.Namespace(
            identifier="PMC123",
            identifier_type="pmcid",
            log_level="INFO",
        )
        with (
            patch.object(self.workflow, "_build_parser") as parser,
            patch.object(self.workflow, "run_study_download", side_effect=error),
            contextlib.redirect_stdout(stdout),
        ):
            parser.return_value.parse_args.return_value = args
            code = self.workflow.main([])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "error")
        self.assertFalse(payload["success"])
        self.assertIn("HTTP 404", payload["error"])


class CurationReportWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = load_script_module(
            "curation_report_characterization",
            REPORT_SCRIPT,
        )

    def test_orchestrator_builds_outputs_from_local_xml_and_supplements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            xml_path = root / "article.xml"
            xml_path.write_text("<article><body><p>text</p></body></article>", encoding="utf-8")
            supplement = root / "table.csv"
            supplement.write_text("sample,value\nS1,1\n", encoding="utf-8")
            output_pdf = root / "report.pdf"
            output_json = root / "report.json"
            metadata = {
                "study_title": "Fixture Study",
                "cancer_type": "luad",
                "num_samples": "1",
                "reference_genome": "hg38",
                "study_id_suggestion": "luad_fixture_2024",
            }
            records = [
                {
                    "file": "table.csv",
                    "sheet": "Sheet1",
                    "classification": "CLINICAL_SAMPLE",
                    "cbio_target_file": "data_clinical_sample.txt",
                    "curability": "YES",
                    "priority": "HIGH",
                    "confidence": 70,
                    "verdict": "fixture",
                    "required_present": ["sample_id"],
                    "required_missing": [],
                    "optional_present": [],
                }
            ]

            def save_pdf(meta: dict, summary: dict, path: str) -> str:
                Path(path).write_bytes(b"%PDF-fixture")
                return str(Path(path).resolve())

            with (
                patch.object(
                    self.workflow,
                    "resolve_optional_hermes_llm_config",
                    return_value=None,
                ),
                patch.object(
                    self.workflow,
                    "extract_xml_metadata_with_llm",
                    return_value=metadata,
                ),
                patch.object(
                    self.workflow,
                    "_analyse_supplementary_files",
                    return_value=records,
                ),
                patch.object(
                    self.workflow,
                    "save_curation_report_pdf",
                    side_effect=save_pdf,
                ),
                patch.object(
                    self.workflow,
                    "build_curation_report_json",
                    return_value={"report_title": "Fixture"},
                ),
            ):
                result = self.workflow.run_curation_orchestrator(
                    paper_xml_path=str(xml_path),
                    supplementary_paths=[supplement],
                    output_pdf_path=str(output_pdf),
                    output_json_path=str(output_json),
                )

            persisted = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(result["inputs"]["paper_source_type"], "xml")
        self.assertEqual(result["summary"]["files_analysed"], 1)
        self.assertEqual(result["summary"]["high_priority"], 1)
        self.assertEqual(persisted, {"report_title": "Fixture"})
        self.assertTrue(Path(result["pdf_path"]).is_absolute())

    def test_report_main_returns_one_without_structured_error_output(self) -> None:
        stdout = io.StringIO()
        with (
            patch.object(
                self.workflow,
                "_resolve_study_inputs",
                side_effect=FileNotFoundError("missing"),
            ),
            patch.object(self.workflow.logger, "error") as error_log,
            contextlib.redirect_stdout(stdout),
        ):
            code = self.workflow.main(["--study-id", "pmc123"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        error_log.assert_called_once()
        self.assertEqual(error_log.call_args.args[0], "%s")
        self.assertEqual(str(error_log.call_args.args[1]), "missing")


class GenomeNexusWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = load_script_module(
            "genome_nexus_characterization",
            GENOME_NEXUS_SCRIPT,
        )

    @staticmethod
    def maf_text(*, include_status: bool = False, status: str = "SUCCESS") -> str:
        columns = [
            "Chromosome",
            "Start_Position",
            "End_Position",
            "Reference_Allele",
            "Tumor_Seq_Allele2",
            "Tumor_Sample_Barcode",
        ]
        values = ["17", "1", "1", "A", "T", "S1"]
        if include_status:
            columns.append("Annotation_Status")
            values.append(status)
        return "\t".join(columns) + "\n" + "\t".join(values) + "\n"

    def test_maf_inspection_counts_successful_and_failed_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "data_mutations.txt"
            path.write_text(
                self.maf_text(include_status=True, status="FAILED")
                + "17\t2\t2\tG\tC\tS2\tSUCCESS\n",
                encoding="utf-8",
            )
            summary = self.workflow.inspect_maf(path, require_status=True)

        self.assertEqual(summary["records"], 2)
        self.assertEqual(summary["successful_annotations"], 1)
        self.assertEqual(summary["failed_annotations"], 1)
        self.assertEqual(
            summary["annotation_status_counts"],
            {"FAILED": 1, "SUCCESS": 1},
        )

    def test_maf_inspection_rejects_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "minimal.maf"
            path.write_text("Chromosome\tStart_Position\n17\t1\n", encoding="utf-8")
            with self.assertRaisesRegex(self.workflow.PipelineError, "missing required"):
                self.workflow.inspect_maf(path, require_status=False)

    def test_main_emits_structured_error_json(self) -> None:
        args = SimpleNamespace(
            study_id="missing",
            genome_build="GRCh37",
            image="image",
            timeout=1,
            force=False,
        )
        stdout = io.StringIO()
        with (
            patch.object(self.workflow, "parse_args", return_value=args),
            patch.object(
                self.workflow,
                "resolve_workspace",
                side_effect=self.workflow.PipelineError("missing workspace"),
            ),
            contextlib.redirect_stdout(stdout),
        ):
            code = self.workflow.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload, {"status": "error", "error": "missing workspace"})

    def test_main_emits_success_json_for_valid_mocked_pipeline_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            input_path = workspace / self.workflow.MINIMAL_MAF_FILENAME
            output_path = workspace / self.workflow.OUTPUT_MAF_FILENAME
            input_path.write_text(self.maf_text(), encoding="utf-8")
            args = SimpleNamespace(
                study_id="pmc123",
                genome_build="GRCh37",
                image="image",
                timeout=1,
                force=False,
            )

            def run_pipeline(*args: object, **kwargs: object) -> SimpleNamespace:
                output_path.write_text(
                    self.maf_text(include_status=True),
                    encoding="utf-8",
                )
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            stdout = io.StringIO()
            with (
                patch.object(self.workflow, "parse_args", return_value=args),
                patch.object(self.workflow, "resolve_workspace", return_value=workspace),
                patch.object(self.workflow, "check_docker"),
                patch.object(
                    self.workflow.subprocess,
                    "run",
                    side_effect=run_pipeline,
                ),
                contextlib.redirect_stdout(stdout),
            ):
                code = self.workflow.main()

            payload = json.loads(stdout.getvalue())

        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["input_records"], 1)
        self.assertEqual(payload["successful_annotations"], 1)

    def test_main_reports_partial_success_for_record_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            input_path = workspace / self.workflow.MINIMAL_MAF_FILENAME
            output_path = workspace / self.workflow.OUTPUT_MAF_FILENAME
            input_path.write_text(self.maf_text(), encoding="utf-8")
            args = SimpleNamespace(
                study_id="pmc123",
                genome_build="GRCh37",
                image="image",
                timeout=1,
                force=False,
            )

            def run_pipeline(*args: object, **kwargs: object) -> SimpleNamespace:
                output_path.write_text(
                    self.maf_text(include_status=True)
                    + "17\t2\t2\tG\tC\tS2\tSUCCESS\n",
                    encoding="utf-8",
                )
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            stdout = io.StringIO()
            with (
                patch.object(self.workflow, "parse_args", return_value=args),
                patch.object(self.workflow, "resolve_workspace", return_value=workspace),
                patch.object(self.workflow, "check_docker"),
                patch.object(self.workflow.subprocess, "run", side_effect=run_pipeline),
                contextlib.redirect_stdout(stdout),
            ):
                code = self.workflow.main()

            payload = json.loads(stdout.getvalue())

        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "partial_success")
        self.assertTrue(payload["record_count_mismatch"])


if __name__ == "__main__":
    unittest.main()
