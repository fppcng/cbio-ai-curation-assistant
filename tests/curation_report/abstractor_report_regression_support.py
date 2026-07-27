from __future__ import annotations

import importlib.util
import json
import os
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cbio_curation_assistant.cbioportal_spec import SPECS
import cbio_curation_assistant.spec_match as spec_match


STUDY_ID = "pmc8317046"
STUDY_ROOT = REPO_ROOT / "studies" / STUDY_ID
GOLD_REPORT_PATH = STUDY_ROOT / "reports" / "chc_icc_xue_2019_abstractor_report.json"
GENERATOR_PATH = (
    REPO_ROOT
    / "hermes_skills"
    / "abstractor-curation-report-generation"
    / "scripts"
    / "abstractor_report_generator.py"
)
ARTIFACTS_ROOT = REPO_ROOT / "tests" / "curation_report" / "_artifacts"
NO_LLM_WARNING = "No Hermes LLM configuration is available. Using structured XML metadata only."


def load_report_generator_module():
    script_dir = str(GENERATOR_PATH.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    spec = importlib.util.spec_from_file_location(
        "abstractor_report_generator_regression",
        GENERATOR_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load report generator module from {GENERATOR_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_embedded_spec_result(tag: str) -> dict:
    return {
        "specs": list(SPECS),
        "source": "embedded",
        "fetched_at": tag,
        "url": None,
        "error": None,
    }


def project_deterministic_report_fields(report: dict) -> dict:
    overview = report["study_overview"]
    supplementary = report["supplementary_file_analysis"]
    detail_rows = report["per_sheet_classification_detail"]
    suggested = report["suggested_study_metadata"]

    return {
        "report_title": report["report_title"],
        "study_title": report["study_title"],
        "citation": report["citation"],
        "study_overview": {
            "study_title": overview["study_title"],
            "pmid": overview["pmid"],
            "doi": overview["doi"],
            "first_author_surname": overview["first_author_surname"],
            "year": overview["year"],
            "journal": overview["journal"],
            "publication": overview["publication"],
            "description": overview["description"],
            "meta_description": overview["meta_description"],
            "data_repositories": overview["data_repositories"],
            "corresponding_authors": overview["corresponding_authors"],
        },
        "supplementary_file_analysis": {
            "high_priority": supplementary["high_priority"],
            "medium_priority": supplementary["medium_priority"],
            "needs_manual_intervention": supplementary["needs_manual_intervention"],
            "file_breakdown": [
                {
                    "file": row["file"],
                    "sheet": row["sheet"],
                    "cbioportal_format": row["cbioportal_format"],
                    "loadable": row["loadable"],
                    "priority": row["priority"],
                    "columns_present": row["columns_present"],
                }
                for row in supplementary["file_breakdown"]
            ],
        },
        "per_sheet_classification_detail": [
            {
                "file": row["file"],
                "sheet": row["sheet"],
                "format": row["format"],
                "loadable": row["loadable"],
                "priority": row["priority"],
                "required_columns_found": row["required_columns_found"],
            }
            for row in detail_rows
        ],
        "suggested_study_metadata": {
            "name": suggested["name"],
            "description": suggested["description"],
            "pmid": suggested["pmid"],
            "groups": suggested["groups"],
        },
    }


def load_gold_report() -> dict:
    return json.loads(GOLD_REPORT_PATH.read_text(encoding="utf-8"))


def build_timestamp_label() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def build_artifact_paths(
    study_id: str,
    *,
    mode: str,
    timestamp_label: str | None = None,
    base_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    resolved_study_id = study_id.strip().lower()
    timestamp = timestamp_label or build_timestamp_label()
    artifact_root = base_dir or ARTIFACTS_ROOT
    artifact_dir = artifact_root / resolved_study_id / mode / timestamp
    file_stem = (
        f"{resolved_study_id}_embedded_llm_review_report"
        if mode == "llm"
        else f"{resolved_study_id}_embedded_no_llm_regression_report"
    )
    return (
        artifact_dir,
        artifact_dir / f"{file_stem}.json",
        artifact_dir / f"{file_stem}.pdf",
    )


def run_report_generation(
    *,
    report_generator,
    study_id: str,
    output_json_path: Path,
    output_pdf_path: Path | None,
    use_llm: bool,
    embedded_spec_tag: str,
) -> tuple[dict, dict]:
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    if output_pdf_path is not None:
        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        with mock.patch.dict(os.environ, {"CBIO_CURATION_ASSISTANT_HOME": str(REPO_ROOT)}, clear=False):
            with mock.patch.object(
                spec_match,
                "fetch_spec",
                return_value=build_embedded_spec_result(embedded_spec_tag),
            ):
                if use_llm:
                    workspace, paper_pdf_path, paper_xml_path, supplementary_paths = (
                        report_generator._resolve_study_inputs(study_id)
                    )
                    result = report_generator.run_curation_orchestrator(
                        paper_pdf_path=paper_pdf_path,
                        paper_xml_path=paper_xml_path,
                        supplementary_paths=supplementary_paths,
                        study_workspace=workspace,
                        output_pdf_path=str(output_pdf_path) if output_pdf_path is not None else None,
                        output_json_path=str(output_json_path),
                    )
                else:
                    with mock.patch.object(report_generator, "resolve_optional_hermes_llm_config", return_value=None):
                        workspace, paper_pdf_path, paper_xml_path, supplementary_paths = (
                            report_generator._resolve_study_inputs(study_id)
                        )
                        result = report_generator.run_curation_orchestrator(
                            paper_pdf_path=paper_pdf_path,
                            paper_xml_path=paper_xml_path,
                            supplementary_paths=supplementary_paths,
                            study_workspace=workspace,
                            output_pdf_path=str(output_pdf_path) if output_pdf_path is not None else None,
                            output_json_path=str(output_json_path),
                        )

    generated_report = json.loads(output_json_path.read_text(encoding="utf-8"))
    return result, generated_report
