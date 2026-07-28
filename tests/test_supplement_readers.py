from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from docx import Document
from reportlab.pdfgen import canvas

from cbio_curation_assistant import cbioportal_curator as curator
from cbio_curation_assistant.spec_match import ClassificationResult


def classification_result(format_key: str = "CLINICAL_SAMPLE") -> ClassificationResult:
    return ClassificationResult(
        format_key=format_key,
        target_file="data_clinical_sample.txt",
        confidence=70.0,
        required_present=["patient_id", "sample_id"],
        required_missing=[],
        optional_present=[],
        detected_as_aliases={},
        all_scores=[],
        is_matrix=False,
        notes="",
        verdict="CLINICAL_SAMPLE",
        spec_source="embedded",
        spec_fetched_at="fixture",
    )


class SupplementReaderTest(unittest.TestCase):
    def test_csv_tsv_and_text_files_are_read_as_single_sheets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            fixtures = {
                "table.csv": "sample,value\nS1,1\n",
                "table.tsv": "sample\tvalue\nS1\t1\n",
                "table.txt": "sample|value\nS1|1\n",
            }
            for filename, content in fixtures.items():
                with self.subTest(filename=filename):
                    path = root / filename
                    path.write_text(content, encoding="utf-8")
                    sheets = curator._read_file_as_sheets(str(path))

                    self.assertEqual(list(sheets), ["Sheet1"])
                    self.assertEqual(sheets["Sheet1"].shape, (2, 2))

    def test_excel_reader_ignores_empty_sheets_and_blank_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "tables.xlsx"
            with pd.ExcelWriter(path) as writer:
                pd.DataFrame([[None, None], ["sample", "value"], ["S1", 1]]).to_excel(
                    writer,
                    sheet_name="Data",
                    index=False,
                    header=False,
                )
                pd.DataFrame().to_excel(writer, sheet_name="Empty", index=False)

            sheets = curator._read_file_as_sheets(str(path))

            self.assertEqual(list(sheets), ["Data"])
            self.assertEqual(sheets["Data"].shape, (2, 2))

    def test_docx_reader_exposes_tables_and_paragraphs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "supplement.docx"
            document = Document()
            document.add_paragraph("Study notes")
            table = document.add_table(rows=2, cols=2)
            table.cell(0, 0).text = "sample"
            table.cell(0, 1).text = "value"
            table.cell(1, 0).text = "S1"
            table.cell(1, 1).text = "1"
            document.save(path)

            sheets = curator._read_file_as_sheets(str(path))

            self.assertEqual(set(sheets), {"Table_1", "Text"})
            self.assertEqual(sheets["Table_1"].shape, (2, 2))
            self.assertEqual(sheets["Text"].iloc[0, 0], "Study notes")

    def test_pdf_reader_falls_back_to_extracted_text_when_no_table_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "supplement.pdf"
            pdf = canvas.Canvas(str(path))
            pdf.drawString(72, 720, "Sample S1 has a reported alteration")
            pdf.save()

            sheets = curator._read_file_as_sheets(str(path))

            self.assertIn("Text", sheets)
            rendered = " ".join(str(value) for value in sheets["Text"].iloc[:, 0])
            self.assertIn("Sample S1", rendered)

    def test_unknown_extension_uses_tabular_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "table.data"
            path.write_text("sample\tvalue\nS1\t1\n", encoding="utf-8")

            sheets = curator._read_file_as_sheets(str(path))

            self.assertEqual(list(sheets), ["Sheet1"])
            self.assertEqual(sheets["Sheet1"].shape, (2, 2))

    def test_supplement_analysis_returns_classification_records(self) -> None:
        dataframe = pd.DataFrame([["PATIENT_ID", "SAMPLE_ID"], ["P1", "S1"]])
        with (
            patch.object(curator, "_read_file_as_sheets", return_value={"Clinical": dataframe}),
            patch.object(curator, "classify_sheet", return_value=classification_result()),
        ):
            records = curator._analyse_supplementary_files(["/tmp/source.xlsx"])

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["file"], "source.xlsx")
        self.assertEqual(records[0]["sheet"], "Clinical")
        self.assertEqual(records[0]["classification"], "CLINICAL_SAMPLE")
        self.assertEqual(records[0]["curability"], "YES")

    def test_supplement_analysis_turns_reader_errors_into_not_loadable_records(self) -> None:
        with patch.object(
            curator,
            "_read_file_as_sheets",
            side_effect=ValueError("cannot parse"),
        ):
            records = curator._analyse_supplementary_files(["/tmp/broken.xlsx"])

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["classification"], "NOT_LOADABLE")
        self.assertEqual(records[0]["confidence"], 0)
        self.assertIn("cannot parse", records[0]["verdict"])


if __name__ == "__main__":
    unittest.main()
