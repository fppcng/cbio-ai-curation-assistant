from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.script_loader import REPO_ROOT, load_script_module


ONCOTREE_SCRIPT = (
    "hermes_skills/curator-oncotree-consultation/scripts/search_oncotree_code.py"
)
CLINICAL_DICTIONARY_SCRIPT = (
    "hermes_skills/curator-clinical-files-creation/scripts/"
    "consult_clinical_dictionary.py"
)


class OncotreeLookupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tool = load_script_module("oncotree_characterization", ONCOTREE_SCRIPT)

    def test_bundled_table_loads_unique_candidates(self) -> None:
        candidates = self.tool.load_oncotree_candidates(
            REPO_ROOT
            / "hermes_skills/curator-oncotree-consultation/scripts/"
            "oncotree_latest_table.txt"
        )

        self.assertGreater(len(candidates), 100)
        codes = [candidate.oncotree_code for candidate in candidates]
        self.assertEqual(len(codes), len(set(codes)))

    def test_exact_code_match_scores_one(self) -> None:
        candidate = self.tool.OncotreeCandidate(
            oncotree_code="LUAD",
            cancer_type="Non-Small Cell Lung Cancer",
            cancer_type_detailed="Lung Adenocarcinoma",
            tissue="Lung",
            color="#000000",
            nci_codes="",
            umls_codes="",
            path=["Lung", "Non-Small Cell Lung Cancer", "Lung Adenocarcinoma"],
            source_row=1,
        )

        self.assertEqual(self.tool.score_candidate("luad", candidate), 1.0)
        results = self.tool.search_oncotree("LUAD", [candidate], 10, 0.0)
        self.assertEqual(results[0]["oncotree_code"], "LUAD")
        self.assertEqual(results[0]["score"], 1.0)

    def test_clinical_inspection_reports_missing_columns_and_suggestions(self) -> None:
        candidate = self.tool.OncotreeCandidate(
            oncotree_code="LUAD",
            cancer_type="Non-Small Cell Lung Cancer",
            cancer_type_detailed="Lung Adenocarcinoma",
            tissue="Lung",
            color="",
            nci_codes="",
            umls_codes="",
            path=["Lung", "Lung Adenocarcinoma"],
            source_row=1,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "data_clinical_sample.txt"
            path.write_text(
                "#comment\nSAMPLE_ID\tCANCER_TYPE_DETAILED\n"
                "S1\tLung Adenocarcinoma\n",
                encoding="utf-8",
            )

            summary = self.tool.inspect_clinical_sample(path, [candidate], limit=10)

        self.assertEqual(summary["row_count"], 1)
        self.assertEqual(
            summary["missing_standard_columns"],
            ["ONCOTREE_CODE", "CANCER_TYPE"],
        )
        self.assertEqual(summary["suggestions"][0]["matches"][0]["oncotree_code"], "LUAD")

    def test_json_cli_output_is_machine_readable(self) -> None:
        stdout = io.StringIO()
        argv = [
            "search_oncotree_code.py",
            "--query",
            "LUAD",
            "--limit",
            "1",
            "--json",
        ]
        with patch.object(sys, "argv", argv):
            with contextlib.redirect_stdout(stdout):
                code = self.tool.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["query_results"]), 1)
        self.assertEqual(payload["query_results"][0]["oncotree_code"], "LUAD")


class ClinicalDictionaryLookupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tool = load_script_module(
            "clinical_dictionary_characterization",
            CLINICAL_DICTIONARY_SCRIPT,
        )

    def test_dictionary_loader_requires_a_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "invalid.json"
            path.write_text('{"not": "a list"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be a list"):
                self.tool.load_dictionary(path)

    def test_exact_considered_header_ranks_first(self) -> None:
        dictionary = [
            {
                "column_header": "OS_MONTHS",
                "display_name": "Overall Survival",
                "description": "Overall survival in months",
                "datatype": "NUMBER",
                "attribute_type": "PATIENT",
                "priority": "1",
            },
            {
                "column_header": "PFS_MONTHS",
                "display_name": "Progression Free Survival",
                "description": "Progression-free survival in months",
                "datatype": "NUMBER",
                "attribute_type": "PATIENT",
                "priority": "1",
            },
        ]

        candidates = self.tool.search_candidates(
            original_column_name="survival",
            considered_column_name="OS_MONTHS",
            dictionary=dictionary,
            limit=10,
            minimum_score=0,
        )

        self.assertEqual(candidates[0]["column_header"], "OS_MONTHS")
        self.assertEqual(candidates[0]["score"], 1.0)
        self.assertEqual(
            self.tool.search_candidates(
                original_column_name="unrelated",
                considered_column_name="unknown",
                dictionary=dictionary,
                limit=10,
                minimum_score=1.1,
            ),
            [],
        )

    def test_json_cli_output_is_a_candidate_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            dictionary_path = Path(tmp_dir) / "dictionary.json"
            dictionary_path.write_text(
                json.dumps(
                    [
                        {
                            "column_header": "AGE",
                            "display_name": "Age",
                            "description": "Age at diagnosis",
                            "datatype": "NUMBER",
                            "attribute_type": "PATIENT",
                            "priority": "1",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            argv = [
                "consult_clinical_dictionary.py",
                "--source-column",
                "patient age",
                "--considered-column",
                "AGE",
                "--dictionary",
                str(dictionary_path),
                "--json",
            ]
            stdout = io.StringIO()
            with patch.object(sys, "argv", argv):
                with contextlib.redirect_stdout(stdout):
                    code = self.tool.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload[0]["column_header"], "AGE")
        self.assertEqual(payload[0]["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
