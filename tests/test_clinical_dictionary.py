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


def _attribute(
    column_header: str,
    display_name: str,
    description: str,
    *,
    datatype: str = "STRING",
    attribute_type: str = "PATIENT",
    priority: str = "1",
) -> dict[str, str]:
    return {
        "column_header": column_header,
        "display_name": display_name,
        "description": description,
        "datatype": datatype,
        "attribute_type": attribute_type,
        "priority": priority,
    }


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

    def test_search_uses_source_meaning_without_a_preselected_header(self) -> None:
        dictionary = [
            ClinicalDictionaryAttribute(
                **_attribute(
                    "AGE_YRS",
                    "Age (yrs)",
                    "Age at diagnosis in years",
                    datatype="NUMBER",
                )
            ),
            ClinicalDictionaryAttribute(
                **_attribute(
                    "SMOKING_STATUS",
                    "Smoking Status",
                    "Patient smoking history",
                )
            ),
        ]

        candidates = search_clinical_dictionary(
            source_column_name="smoking history",
            dictionary=dictionary,
            limit=2,
            minimum_score=0,
        )

        self.assertEqual(candidates[0].column_header, "SMOKING_STATUS")
        self.assertLess(candidates[0].score, 1.0)

    def test_optional_search_query_can_expand_an_abbreviated_source_header(
        self,
    ) -> None:
        dictionary = [
            ClinicalDictionaryAttribute(
                **_attribute(
                    "IMMUNOHISTOCHEMISTRY",
                    "Immunohistochemistry",
                    "Immunohistochemistry findings",
                    attribute_type="SAMPLE",
                )
            ),
            ClinicalDictionaryAttribute(
                **_attribute(
                    "IHC_SCORE",
                    "Immune Health Composite Score",
                    "Composite immune health score",
                )
            ),
        ]

        candidates = search_clinical_dictionary(
            source_column_name="IHC",
            search_query="immunohistochemistry findings",
            dictionary=dictionary,
            limit=2,
            minimum_score=0,
        )

        self.assertEqual(candidates[0].column_header, "IMMUNOHISTOCHEMISTRY")
        self.assertEqual(candidates[0].attribute.attribute_type, "SAMPLE")


class ClinicalDictionaryCliTest(unittest.TestCase):
    def test_single_search_json_contains_a_report_skeleton(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            dictionary_path = Path(tmp_dir) / "dictionary.json"
            dictionary_path.write_text(
                json.dumps(
                    [
                        _attribute(
                            "AGE_YRS",
                            "Age (yrs)",
                            "Age at diagnosis in years",
                            datatype="NUMBER",
                        )
                    ]
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli.main(
                    [
                        "clinical-dictionary",
                        "search",
                        "--source-column",
                        "patient age",
                        "--search-query",
                        "age at diagnosis in years",
                        "--dictionary",
                        str(dictionary_path),
                        "--json",
                    ]
                )

        payload = json.loads(stdout.getvalue())
        report = payload["result"]["report"]
        self.assertEqual(code, 0)
        self.assertEqual(payload["command"], "clinical-dictionary.search")
        self.assertEqual(report["query_count"], 1)
        self.assertEqual(report["candidate_limit"], 5)
        self.assertEqual(
            report["mappings"][0]["candidates"][0]["column_header"],
            "AGE_YRS",
        )
        self.assertIsNone(report["mappings"][0]["decision"])

    def test_batch_search_persists_one_mapping_per_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            dictionary_path = root / "dictionary.json"
            input_path = root / "queries.json"
            output_path = root / "mapping.json"
            dictionary_path.write_text(
                json.dumps(
                    [
                        _attribute(
                            "AGE_YRS",
                            "Age (yrs)",
                            "Age at diagnosis in years",
                            datatype="NUMBER",
                        ),
                        _attribute("SEX", "Sex", "Sex of the patient"),
                    ]
                ),
                encoding="utf-8",
            )
            input_path.write_text(
                json.dumps(
                    {
                        "study_id": "synthetic-study",
                        "queries": [
                            {
                                "id": "age",
                                "source_column": "Age",
                                "search_query": "age at diagnosis",
                            },
                            {
                                "id": "sex",
                                "source_column": "Gender",
                                "search_query": "patient sex",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                code = cli.main(
                    [
                        "clinical-dictionary",
                        "search",
                        "--input",
                        str(input_path),
                        "--dictionary",
                        str(dictionary_path),
                        "--output",
                        str(output_path),
                        "--json",
                    ]
                )
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(report["study_id"], "synthetic-study")
        self.assertEqual(
            [mapping["id"] for mapping in report["mappings"]],
            ["age", "sex"],
        )

    def test_validate_uses_the_structured_success_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            dictionary_path = root / "dictionary.json"
            report_path = root / "mapping.json"
            sample_path = root / "data_clinical_sample.txt"
            dictionary_path.write_text(
                json.dumps(
                    [
                        _attribute(
                            "SAMPLE_ID",
                            "Sample Identifier",
                            "A unique sample identifier.",
                            attribute_type="SAMPLE",
                        )
                    ]
                ),
                encoding="utf-8",
            )
            report_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "mappings": [
                            {
                                "id": "sample_id",
                                "candidates": [{"column_header": "SAMPLE_ID"}],
                                "decision": {
                                    "status": "standard",
                                    "selected_column_header": "SAMPLE_ID",
                                    "reason": "Required sample identifier.",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            sample_path.write_text(
                "#Sample Identifier\n"
                "#A unique sample identifier.\n"
                "#STRING\n"
                "#1\n"
                "SAMPLE_ID\n"
                "S1\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli.main(
                    [
                        "clinical-dictionary",
                        "validate",
                        "--report",
                        str(report_path),
                        "--sample-file",
                        str(sample_path),
                        "--dictionary",
                        str(dictionary_path),
                        "--json",
                    ]
                )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["command"], "clinical-dictionary.validate")
        self.assertEqual(payload["status"], "success")

    def test_operational_failure_uses_structured_error_envelope(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(
                [
                    "clinical-dictionary",
                    "search",
                    "--source-column",
                    "age",
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
