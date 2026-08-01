from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from cbio_curation_assistant.publications.models import PublicationMetadata
from cbio_curation_assistant.reports import (
    CurationSummary,
    ReportBreakdownRow,
    build_curation_report_filename,
    build_curation_report_json,
    build_curation_report_pdf,
    save_curation_report_pdf,
)
from cbio_curation_assistant.publications import extract_xml_metadata_with_llm
from cbio_curation_assistant.reports.presentation import build_publication


META = {
    "study_title": "Fixture Study",
    "cancer_type": "luad",
    "cancer_type_full": "Lung Adenocarcinoma",
    "num_samples": 2,
    "num_patients": 2,
    "reference_genome": "hg38",
    "sequencing_types": ["WES"],
    "pmid": "12345678",
    "doi": "10.1000/example",
    "first_author_surname": "Smith",
    "year": "2024",
    "journal": "Fixture Journal",
    "study_id_suggestion": "luad_smith_2024",
    "description": "Fixture description.",
    "key_findings": ["Finding"],
    "primary_site": "Lung",
    "cohort_description": "Two patients.",
    "meta_description": "Fixture description.",
    "data_repositories": ["GSE123456"],
    "corresponding_authors": "Ada Smith",
}

SUMMARY = {
    "study_id": "luad_smith_2024",
    "cancer_type": "luad",
    "num_samples": 2,
    "reference_genome": "hg38",
    "files_analysed": 1,
    "sheets_analysed": 1,
    "high_priority": 1,
    "medium_priority": 0,
    "not_loadable": 0,
    "file_breakdown": [
        {
            "file": "table.csv",
            "sheet": "Sheet1",
            "classification": "CLINICAL_SAMPLE",
            "cbio_target_file": "data_clinical_sample.txt",
            "curability": "YES",
            "priority": "HIGH",
            "confidence": 70,
            "verdict": "fixture",
            "required_present": ["patient_id", "sample_id"],
            "required_missing": [],
            "optional_present": [],
        }
    ],
}

TYPED_META = PublicationMetadata.from_mapping(META)
TYPED_SUMMARY = CurationSummary(
    study_id="luad_smith_2024",
    cancer_type="luad",
    num_samples=2,
    reference_genome="hg38",
    files_analysed=1,
    sheets_analysed=1,
    high_priority=1,
    medium_priority=0,
    not_loadable=0,
    file_breakdown=(
        ReportBreakdownRow(
            file="table.csv",
            sheet="Sheet1",
            cbio_format="data_clinical_sample.txt",
            curability="YES",
            priority="HIGH",
            confidence=70,
            verdict="fixture",
            required_present=("patient_id", "sample_id"),
        ),
    ),
)


class ReportBuilderTest(unittest.TestCase):
    def test_json_report_has_stable_top_level_sections(self) -> None:
        report = build_curation_report_json(TYPED_META, TYPED_SUMMARY)

        self.assertEqual(
            set(report),
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
        self.assertEqual(report["study_title"], "Fixture Study")
        self.assertEqual(
            report["supplementary_file_analysis"]["high_priority"],
            1,
        )

    def test_json_report_uses_pdf_presentation_vocabulary(self) -> None:
        expected_labels = {
            "YES": "Yes",
            "PARTIAL": "Partly curatable",
            "NO": "Needs manual intervention",
        }

        for curability, expected_label in expected_labels.items():
            with self.subTest(curability=curability):
                row = replace(
                    TYPED_SUMMARY.file_breakdown[0],
                    curability=curability,
                )
                report = build_curation_report_json(
                    TYPED_META,
                    replace(TYPED_SUMMARY, file_breakdown=(row,)),
                )
                breakdown = report["supplementary_file_analysis"]["file_breakdown"][0]

                self.assertEqual(breakdown["loadable"], expected_label)
                self.assertEqual(
                    breakdown["cbioportal_format"],
                    "data_clinical_sample.txt",
                )

        self.assertEqual(build_publication(META), "Fixture Journal 2024")

    def test_pdf_builder_returns_pdf_bytes_and_save_persists_them(self) -> None:
        rendered = build_curation_report_pdf(META, SUMMARY)
        self.assertTrue(rendered.startswith(b"%PDF-"))

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "report.pdf"
            saved = save_curation_report_pdf(META, SUMMARY, output)

            self.assertEqual(saved, str(output.resolve()))
            self.assertTrue(output.read_bytes().startswith(b"%PDF-"))

    def test_report_filename_uses_sanitized_study_identity(self) -> None:
        filename = build_curation_report_filename(META, SUMMARY)
        self.assertEqual(filename, "luad_smith_2024_curation_report.pdf")

    def test_xml_metadata_without_llm_keeps_structured_values_and_warns(self) -> None:
        xml = """
        <article>
          <front>
            <journal-meta><journal-title>Journal</journal-title></journal-meta>
            <article-meta>
              <title-group><article-title>Title</article-title></title-group>
              <contrib-group>
                <contrib contrib-type="author"><name><surname>Smith</surname></name></contrib>
              </contrib-group>
              <pub-date><year>2024</year></pub-date>
            </article-meta>
          </front>
          <body><p>Body</p></body>
        </article>
        """
        warnings: list[str] = []

        metadata = extract_xml_metadata_with_llm(
            xml,
            None,
            warnings,
            missing_text_warning="XML text unavailable",
            missing_llm_warning="LLM unavailable",
            completion_failure_warning="LLM completion failed",
        )

        self.assertEqual(metadata["study_title"], "Title")
        self.assertEqual(metadata["study_id_suggestion"], "study_smith_2024")
        self.assertEqual(warnings, ["LLM unavailable"])


if __name__ == "__main__":
    unittest.main()
