from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.script_loader import load_script_module


CLINICAL_DICTIONARY_SCRIPT = (
    "hermes_skills/curator-clinical-files-creation/scripts/"
    "consult_clinical_dictionary.py"
)


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
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["result"][0]["column_header"], "AGE")
        self.assertEqual(payload["result"][0]["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
