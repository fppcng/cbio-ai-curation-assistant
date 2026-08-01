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

from cbio_curation_assistant import curation_report_cli, study_download_cli
from cbio_curation_assistant.integrations.pmc import PMCErrorClassification
from cbio_curation_assistant.supplements.models import SupplementaryClassification
from cbio_curation_assistant.workspace import StudyWorkspace
from cbio_curation_assistant.workflows import (
    curation_report as curation_report_workflow,
)
from cbio_curation_assistant.workflows import study_download as study_download_workflow
from tests.script_loader import load_script_module


GENOME_NEXUS_SCRIPT = (
    "hermes_skills/curator-mutation-data-file-creation/scripts/run_genome_nexus.py"
)


class StudyDownloadWorkflowTest(unittest.TestCase):
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
                    study_download_workflow,
                    "_resolve_download_identifier",
                    return_value=study_download_workflow.ResolvedStudyIdentifier(
                        input_identifier="PMC123",
                        identifier_type="PMCID",
                        normalized_identifier="PMC123",
                        pmcid="PMC123",
                    ),
                ),
                patch.object(
                    study_download_workflow,
                    "_ensure_xml",
                    side_effect=ensure_xml,
                ),
                patch.object(
                    study_download_workflow,
                    "_ensure_supplementary_files",
                    side_effect=ensure_supplements,
                ),
                patch.object(
                    study_download_workflow,
                    "_ensure_article_pdf",
                    return_value=(None, False),
                ),
            ):
                result = study_download_workflow.run_study_download(
                    identifier="PMC123",
                    identifier_type="pmcid",
                    assistant_home=home,
                )

            workspace = StudyWorkspace.load("pmc123", assistant_home=home)
            persisted = json.loads(
                workspace.download_manifest_path.read_text(encoding="utf-8")
            )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.study_id, "pmc123")
        self.assertEqual(len(result.supplementary.files), 1)
        self.assertEqual(persisted, result.to_manifest_dict())

    def test_main_renders_pmc_errors_as_json(self) -> None:
        error = study_download_cli.PMCRequestError(
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
            patch.object(study_download_cli, "_build_parser") as parser,
            patch.object(
                study_download_cli,
                "run_study_download",
                side_effect=error,
            ),
            contextlib.redirect_stdout(stdout),
        ):
            parser.return_value.parse_args.return_value = args
            code = study_download_cli.run_study_download_command([])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["command"], "study-download")
        self.assertIn("HTTP 404", payload["error"]["message"])

    def test_main_returns_three_for_partial_success(self) -> None:
        download_result = SimpleNamespace(
            status="partial_success",
            warnings=("article PDF was unavailable",),
            to_dict=lambda: {"study_id": "pmc123"},
        )
        stdout = io.StringIO()
        args = argparse.Namespace(
            identifier="PMC123",
            identifier_type="pmcid",
            log_level="INFO",
        )
        with (
            patch.object(study_download_cli, "_build_parser") as parser,
            patch.object(
                study_download_cli,
                "run_study_download",
                return_value=download_result,
            ),
            contextlib.redirect_stdout(stdout),
        ):
            parser.return_value.parse_args.return_value = args
            code = study_download_cli.run_study_download_command([])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 3)
        self.assertEqual(payload["status"], "partial_success")
        self.assertEqual(payload["result"]["study_id"], "pmc123")
        self.assertEqual(payload["warnings"], ["article PDF was unavailable"])


class CurationReportWorkflowTest(unittest.TestCase):
    def test_orchestrator_builds_outputs_from_local_xml_and_supplements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            xml_path = root / "article.xml"
            xml_path.write_text(
                "<article><body><p>text</p></body></article>", encoding="utf-8"
            )
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
            records = (
                SupplementaryClassification(
                    file="table.csv",
                    sheet="Sheet1",
                    classification="CLINICAL_SAMPLE",
                    cbio_target_file="data_clinical_sample.txt",
                    curability="YES",
                    priority="HIGH",
                    confidence=70,
                    verdict="fixture",
                    required_present=("sample_id",),
                ),
            )

            def save_pdf(meta: dict, summary: dict, path: str) -> str:
                Path(path).write_bytes(b"%PDF-fixture")
                return str(Path(path).resolve())

            with (
                patch.object(
                    curation_report_workflow,
                    "extract_xml_metadata_with_llm",
                    return_value=metadata,
                ),
                patch.object(
                    curation_report_workflow,
                    "analyse_supplementary_files",
                    return_value=records,
                ),
                patch.object(
                    curation_report_workflow,
                    "save_curation_report_pdf",
                    side_effect=save_pdf,
                ),
                patch.object(
                    curation_report_workflow,
                    "build_curation_report_json",
                    return_value={"report_title": "Fixture"},
                ),
            ):
                result = curation_report_workflow.run_curation_report(
                    curation_report_workflow.CurationReportInputs(
                        paper_source=curation_report_workflow.PaperSource(
                            kind="xml",
                            path=xml_path,
                        ),
                        supplementary_paths=(supplement,),
                    ),
                    output_pdf_path=str(output_pdf),
                    output_json_path=str(output_json),
                )

            persisted = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(result.inputs.paper_source.kind, "xml")
        self.assertEqual(result.summary.files_analysed, 1)
        self.assertEqual(result.summary.high_priority, 1)
        self.assertEqual(persisted, {"report_title": "Fixture"})
        self.assertTrue(result.outputs.pdf.is_absolute())

    def test_report_main_returns_structured_error_output(self) -> None:
        stdout = io.StringIO()
        with (
            patch.object(
                curation_report_cli,
                "run_curation_report_for_study",
                side_effect=FileNotFoundError("missing"),
            ),
            patch.object(
                curation_report_cli, "resolve_optional_llm_config", return_value=None
            ),
            patch.object(curation_report_cli.logger, "error") as error_log,
            contextlib.redirect_stdout(stdout),
        ):
            code = curation_report_cli.run_curation_report_command(
                ["--study-id", "pmc123"]
            )

        self.assertEqual(code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["command"], "curation-report")
        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["error"],
            {"type": "FileNotFoundError", "message": "missing"},
        )
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

        self.assertEqual(summary.records, 2)
        self.assertEqual(summary.successful_annotations, 1)
        self.assertEqual(summary.failed_annotations, 1)
        self.assertEqual(
            summary.annotation_status_counts,
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
        self.assertEqual(payload["command"], "genome-nexus")
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["message"], "missing workspace")
        self.assertIsNone(payload["result"])

    def test_main_emits_success_json_for_valid_mocked_pipeline_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            input_path = workspace / self.workflow.MINIMAL_MAF_FILENAME
            attempt_dir = workspace / "attempt"
            input_path.write_text(self.maf_text(), encoding="utf-8")
            args = SimpleNamespace(
                study_id="pmc123",
                genome_build="GRCh37",
                image="image",
                timeout=1,
                force=False,
            )

            def run_pipeline(*args: object, **kwargs: object) -> SimpleNamespace:
                (attempt_dir / self.workflow.OUTPUT_MAF_FILENAME).write_text(
                    self.maf_text(include_status=True),
                    encoding="utf-8",
                )
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            def create_attempt(*args: object, **kwargs: object) -> Path:
                attempt_dir.mkdir()
                return attempt_dir

            stdout = io.StringIO()
            with (
                patch.object(self.workflow, "parse_args", return_value=args),
                patch.object(self.workflow, "resolve_workspace", return_value=workspace),
                patch.object(self.workflow, "check_docker"),
                patch.object(
                    self.workflow,
                    "create_attempt_directory",
                    side_effect=create_attempt,
                ),
                patch.object(
                    self.workflow.subprocess,
                    "run",
                    side_effect=run_pipeline,
                ),
                contextlib.redirect_stdout(stdout),
            ):
                code = self.workflow.main()

            payload = json.loads(stdout.getvalue())
            canonical_output_exists = (
                workspace / self.workflow.OUTPUT_MAF_FILENAME
            ).is_file()
            attempt_exists = attempt_dir.exists()

        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["result"]["input_records"], 1)
        self.assertEqual(payload["result"]["successful_annotations"], 1)
        self.assertTrue(canonical_output_exists)
        self.assertFalse(attempt_exists)

    def test_main_reports_partial_success_for_record_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            input_path = workspace / self.workflow.MINIMAL_MAF_FILENAME
            attempt_dir = workspace / "attempt"
            input_path.write_text(self.maf_text(), encoding="utf-8")
            args = SimpleNamespace(
                study_id="pmc123",
                genome_build="GRCh37",
                image="image",
                timeout=1,
                force=False,
            )

            def run_pipeline(*args: object, **kwargs: object) -> SimpleNamespace:
                (attempt_dir / self.workflow.OUTPUT_MAF_FILENAME).write_text(
                    self.maf_text(include_status=True)
                    + "17\t2\t2\tG\tC\tS2\tSUCCESS\n",
                    encoding="utf-8",
                )
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            def create_attempt(*args: object, **kwargs: object) -> Path:
                attempt_dir.mkdir()
                return attempt_dir

            stdout = io.StringIO()
            with (
                patch.object(self.workflow, "parse_args", return_value=args),
                patch.object(self.workflow, "resolve_workspace", return_value=workspace),
                patch.object(self.workflow, "check_docker"),
                patch.object(
                    self.workflow,
                    "create_attempt_directory",
                    side_effect=create_attempt,
                ),
                patch.object(self.workflow.subprocess, "run", side_effect=run_pipeline),
                contextlib.redirect_stdout(stdout),
            ):
                code = self.workflow.main()

            payload = json.loads(stdout.getvalue())
            candidate_exists = (
                attempt_dir / self.workflow.OUTPUT_MAF_FILENAME
            ).is_file()
            canonical_output_exists = (
                workspace / self.workflow.OUTPUT_MAF_FILENAME
            ).exists()

        self.assertEqual(code, 3)
        self.assertEqual(payload["status"], "partial_success")
        self.assertTrue(payload["result"]["record_count_mismatch"])
        self.assertEqual(payload["result"]["attempt_directory"], str(attempt_dir))
        self.assertTrue(candidate_exists)
        self.assertFalse(canonical_output_exists)

    def test_force_preflight_failure_preserves_existing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            input_path = workspace / self.workflow.MINIMAL_MAF_FILENAME
            output_path = workspace / self.workflow.OUTPUT_MAF_FILENAME
            input_path.write_text(self.maf_text(), encoding="utf-8")
            output_path.write_text("previous output\n", encoding="utf-8")
            args = SimpleNamespace(
                study_id="pmc123",
                genome_build="GRCh37",
                image="image",
                timeout=1,
                force=True,
            )

            stdout = io.StringIO()
            with (
                patch.object(self.workflow, "parse_args", return_value=args),
                patch.object(self.workflow, "resolve_workspace", return_value=workspace),
                patch.object(
                    self.workflow,
                    "check_docker",
                    side_effect=self.workflow.PipelineError("docker unavailable"),
                ),
                patch.object(self.workflow, "create_attempt_directory") as create_attempt,
                contextlib.redirect_stdout(stdout),
            ):
                code = self.workflow.main()

            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 1)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(output_path.read_text(encoding="utf-8"), "previous output\n")
            create_attempt.assert_not_called()

    def test_partial_force_run_preserves_existing_canonical_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            attempt_dir = workspace / "attempt"
            input_path = workspace / self.workflow.MINIMAL_MAF_FILENAME
            output_path = workspace / self.workflow.OUTPUT_MAF_FILENAME
            input_path.write_text(self.maf_text(), encoding="utf-8")
            output_path.write_text("previous output\n", encoding="utf-8")
            args = SimpleNamespace(
                study_id="pmc123",
                genome_build="GRCh37",
                image="image",
                timeout=1,
                force=True,
            )

            def create_attempt(*args: object, **kwargs: object) -> Path:
                attempt_dir.mkdir()
                return attempt_dir

            def run_pipeline(*args: object, **kwargs: object) -> SimpleNamespace:
                (attempt_dir / self.workflow.OUTPUT_MAF_FILENAME).write_text(
                    self.maf_text(include_status=True, status="FAILED"),
                    encoding="utf-8",
                )
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            stdout = io.StringIO()
            with (
                patch.object(self.workflow, "parse_args", return_value=args),
                patch.object(self.workflow, "resolve_workspace", return_value=workspace),
                patch.object(self.workflow, "check_docker"),
                patch.object(
                    self.workflow,
                    "create_attempt_directory",
                    side_effect=create_attempt,
                ),
                patch.object(self.workflow.subprocess, "run", side_effect=run_pipeline),
                contextlib.redirect_stdout(stdout),
            ):
                code = self.workflow.main()

            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 3)
            self.assertEqual(payload["status"], "partial_success")
            self.assertEqual(output_path.read_text(encoding="utf-8"), "previous output\n")
            self.assertTrue(payload["result"]["canonical_outputs_preserved"])
            self.assertTrue((attempt_dir / self.workflow.OUTPUT_MAF_FILENAME).is_file())

    def test_failed_promotion_rolls_back_all_canonical_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            workspace = root / "curated"
            attempt_dir = root / "validation" / "attempts" / "attempt"
            workspace.mkdir()
            attempt_dir.mkdir(parents=True)
            canonical = self.workflow.canonical_paths(workspace)
            candidates = self.workflow.canonical_paths(attempt_dir)

            for key in ("output", "error_report", "log"):
                canonical[key].write_text(f"old {key}\n", encoding="utf-8")
                candidates[key].write_text(f"new {key}\n", encoding="utf-8")

            real_replace = self.workflow.os.replace
            failed_once = False

            def fail_during_promotion(source: object, target: object) -> None:
                nonlocal failed_once
                if Path(source) == candidates["error_report"] and not failed_once:
                    failed_once = True
                    raise OSError("promotion failed")
                real_replace(source, target)

            with patch.object(
                self.workflow.os,
                "replace",
                side_effect=fail_during_promotion,
            ):
                with self.assertRaisesRegex(OSError, "promotion failed"):
                    self.workflow.promote_attempt_outputs(
                        candidates,
                        canonical,
                        attempt_dir,
                    )

            for key in ("output", "error_report", "log"):
                self.assertEqual(
                    canonical[key].read_text(encoding="utf-8"),
                    f"old {key}\n",
                )
                self.assertEqual(
                    candidates[key].read_text(encoding="utf-8"),
                    f"new {key}\n",
                )


if __name__ == "__main__":
    unittest.main()
