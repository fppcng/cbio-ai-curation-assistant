from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from cbio_curation_assistant import cli
from cbio_curation_assistant.cbioportal.clinical_dictionary import (
    ClinicalDictionaryAttribute,
    load_clinical_dictionary,
    load_clinical_dictionary_provenance,
    load_default_clinical_dictionary,
    search_clinical_dictionary,
    verify_packaged_clinical_dictionary,
)


class ClinicalDictionaryLookupTest(unittest.TestCase):
    def test_dictionary_loader_requires_a_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "invalid.json"
            path.write_text('{"not": "a list"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be a list"):
                load_clinical_dictionary(path)

    def test_packaged_dictionary_and_provenance_are_verified(self) -> None:
        provenance = verify_packaged_clinical_dictionary()
        dictionary = load_default_clinical_dictionary()

        self.assertEqual(provenance, load_clinical_dictionary_provenance())
        self.assertEqual(
            provenance.filename,
            "clinical_dictionary_snapshot.json",
        )
        self.assertEqual(
            provenance.sha256,
            "fea855b3d0370c45a936751187f74d8ea3d5941dc485ecb98b2c355f38c530ad",
        )
        self.assertEqual(
            provenance.upstream_service_url,
            "https://cdd.cbioportal.mskcc.org/swagger-ui.html",
        )
        self.assertIsNone(provenance.upstream_version)
        self.assertIsNone(provenance.upstream_retrieved_at)
        self.assertIn("not record", provenance.provenance_notes)
        self.assertGreater(len(dictionary), 1000)

    def test_exact_considered_header_ranks_first(self) -> None:
        dictionary = [
            ClinicalDictionaryAttribute(
                column_header="OS_MONTHS",
                display_name="Overall Survival",
                description="Overall survival in months",
                datatype="NUMBER",
                attribute_type="PATIENT",
                priority="1",
            ),
            ClinicalDictionaryAttribute(
                column_header="PFS_MONTHS",
                display_name="Progression Free Survival",
                description="Progression-free survival in months",
                datatype="NUMBER",
                attribute_type="PATIENT",
                priority="1",
            ),
        ]

        candidates = search_clinical_dictionary(
            original_column_name="survival",
            considered_column_name="OS_MONTHS",
            dictionary=dictionary,
            limit=10,
            minimum_score=0,
        )

        self.assertEqual(candidates[0].column_header, "OS_MONTHS")
        self.assertEqual(candidates[0].score, 1.0)
        self.assertEqual(candidates[0].to_dict()["attribute_type"], "PATIENT")
        self.assertEqual(
            search_clinical_dictionary(
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
                "clinical-dictionary",
                "--source-column",
                "patient age",
                "--considered-column",
                "AGE",
                "--dictionary",
                str(dictionary_path),
                "--json",
            ]
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli.main(argv)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["result"][0]["column_header"], "AGE")
        self.assertEqual(payload["result"][0]["score"], 1.0)

    def test_operational_failure_uses_structured_error_envelope(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(
                [
                    "clinical-dictionary",
                    "--source-column",
                    "age",
                    "--considered-column",
                    "AGE",
                    "--dictionary",
                    "/does/not/exist.json",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["command"], "clinical-dictionary")
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["type"], "FileNotFoundError")


if __name__ == "__main__":
    unittest.main()
