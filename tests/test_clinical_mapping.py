from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cbio_curation_assistant.cbioportal.clinical_dictionary import (
    ClinicalDictionaryAttribute,
)
from cbio_curation_assistant.cbioportal.clinical_mapping.clinical_files import (
    read_clinical_header,
)
from cbio_curation_assistant.cbioportal.clinical_mapping.models import (
    ClinicalMappingReport,
)
from cbio_curation_assistant.cbioportal.clinical_mapping.queries import (
    parse_clinical_mapping_queries,
)
from cbio_curation_assistant.cbioportal.clinical_mapping.report_builder import (
    build_clinical_mapping_report,
)
from cbio_curation_assistant.cbioportal.clinical_mapping.validation import (
    validate_clinical_mapping_report,
)


def _attribute(
    column_header: str,
    display_name: str,
    description: str,
    *,
    datatype: str = "STRING",
    attribute_type: str = "PATIENT",
    priority: str = "1",
) -> ClinicalDictionaryAttribute:
    return ClinicalDictionaryAttribute(
        column_header=column_header,
        display_name=display_name,
        description=description,
        datatype=datatype,
        attribute_type=attribute_type,
        priority=priority,
    )


def _write_clinical_file(
    path: Path, columns: list[ClinicalDictionaryAttribute]
) -> None:
    metadata_fields = ("display_name", "description", "datatype", "priority")
    rows = [
        "#" + "\t".join(str(getattr(column, field)) for column in columns)
        for field in metadata_fields
    ]
    rows.append("\t".join(column.column_header for column in columns))
    rows.append("\t".join(f"value_{index}" for index in range(len(columns))))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


class ClinicalMappingReportTest(unittest.TestCase):
    def test_batch_queries_build_an_unresolved_versioned_report(self) -> None:
        study_id, queries = parse_clinical_mapping_queries(
            {
                "study_id": "synthetic-study",
                "queries": [
                    {
                        "id": "age",
                        "source_file": "supplement.xlsx",
                        "source_sheet": "Patients",
                        "source_column": "Age",
                        "search_query": "age at diagnosis",
                    }
                ],
            }
        )
        dictionary = [
            _attribute(
                "AGE_AT_DIAGNOSIS",
                "Age at Diagnosis",
                "Age at diagnosis in years.",
                datatype="NUMBER",
            )
        ]

        report = build_clinical_mapping_report(
            study_id=study_id,
            queries=queries,
            dictionary=dictionary,
        )
        serialized = report.to_dict()

        self.assertEqual(serialized["schema_version"], 1)
        self.assertEqual(serialized["query_count"], 1)
        self.assertEqual(serialized["candidate_limit"], 5)
        self.assertEqual(
            serialized["mappings"][0]["candidates"][0]["column_header"],
            "AGE_AT_DIAGNOSIS",
        )
        self.assertIsNone(serialized["mappings"][0]["decision"])

    def test_duplicate_batch_query_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "ids must be unique"):
            parse_clinical_mapping_queries(
                {
                    "queries": [
                        {"id": "same", "source_column": "Age"},
                        {"id": "same", "source_column": "Sex"},
                    ]
                }
            )


class ClinicalMappingValidationTest(unittest.TestCase):
    def test_canonical_metadata_and_patient_id_sample_exception_are_valid(self) -> None:
        patient_id = _attribute(
            "PATIENT_ID",
            "Patient Identifier",
            "Identifier to uniquely specify a patient.",
        )
        sample_id = _attribute(
            "SAMPLE_ID",
            "Sample Identifier",
            "A unique sample identifier.",
            attribute_type="SAMPLE",
        )
        report = ClinicalMappingReport.from_dict(
            {
                "schema_version": 1,
                "mappings": [
                    {
                        "id": "patient_id",
                        "candidates": [{"column_header": "PATIENT_ID"}],
                        "decision": {
                            "status": "standard",
                            "selected_column_header": "PATIENT_ID",
                            "target_files": ["patient", "sample"],
                            "reason": "Required patient identifier.",
                        },
                    },
                    {
                        "id": "sample_id",
                        "candidates": [{"column_header": "SAMPLE_ID"}],
                        "decision": {
                            "status": "standard",
                            "selected_column_header": "SAMPLE_ID",
                            "reason": "Required sample identifier.",
                        },
                    },
                ],
            }
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            patient_path = root / "data_clinical_patient.txt"
            sample_path = root / "data_clinical_sample.txt"
            _write_clinical_file(patient_path, [patient_id])
            _write_clinical_file(sample_path, [patient_id, sample_id])

            result = validate_clinical_mapping_report(
                report,
                dictionary=[patient_id, sample_id],
                clinical_headers={
                    "patient": read_clinical_header(patient_path),
                    "sample": read_clinical_header(sample_path),
                },
            )

        self.assertTrue(result.valid)
        self.assertEqual(result.clinical_column_count, 3)
        self.assertEqual(result.errors, ())

    def test_custom_attribute_and_documented_override_are_valid(self) -> None:
        cancer_type = _attribute(
            "CANCER_TYPE",
            "Cancer Type",
            "OncoTree cancer type.",
            attribute_type="SAMPLE",
            priority="2000",
        )
        report = ClinicalMappingReport.from_dict(
            {
                "schema_version": 1,
                "mappings": [
                    {
                        "id": "cancer_type",
                        "candidates": [{"column_header": "CANCER_TYPE"}],
                        "decision": {
                            "status": "standard",
                            "selected_column_header": "CANCER_TYPE",
                            "reason": "Standard cancer type.",
                            "metadata_overrides": {
                                "priority": {
                                    "value": "3000",
                                    "reason": "Study-view priority.",
                                }
                            },
                        },
                    },
                    {
                        "id": "lesions",
                        "candidates": [],
                        "decision": {
                            "status": "custom",
                            "target_files": ["sample"],
                            "reason": "No standard lossless mapping.",
                            "custom_attribute": {
                                "column_header": "LESION_COMPONENTS",
                                "display_name": "Lesion Components",
                                "description": "Components in the lesion.",
                                "datatype": "STRING",
                                "priority": "1",
                            },
                        },
                    },
                    {
                        "id": "unused",
                        "candidates": [],
                        "decision": {
                            "status": "excluded",
                            "reason": "Administrative note.",
                        },
                    },
                ],
            }
        )
        output_columns = [
            _attribute(
                "CANCER_TYPE",
                "Cancer Type",
                "OncoTree cancer type.",
                attribute_type="SAMPLE",
                priority="3000",
            ),
            _attribute(
                "LESION_COMPONENTS",
                "Lesion Components",
                "Components in the lesion.",
                attribute_type="SAMPLE",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            sample_path = Path(tmp_dir) / "data_clinical_sample.txt"
            _write_clinical_file(sample_path, output_columns)
            result = validate_clinical_mapping_report(
                report,
                dictionary=[cancer_type],
                clinical_headers={"sample": read_clinical_header(sample_path)},
            )

        self.assertTrue(result.valid)
        self.assertEqual(
            result.decision_counts,
            {"standard": 1, "custom": 1, "excluded": 1},
        )

    def test_wrong_placement_and_unmapped_columns_are_reported(self) -> None:
        ihc = _attribute(
            "IMMUNOHISTOCHEMISTRY",
            "Immunohistochemistry",
            "Immunohistochemistry findings.",
            attribute_type="SAMPLE",
        )
        sample_id = _attribute(
            "SAMPLE_ID",
            "Sample Identifier",
            "A unique sample identifier.",
            attribute_type="SAMPLE",
        )
        report = ClinicalMappingReport.from_dict(
            {
                "schema_version": 1,
                "mappings": [
                    {
                        "id": "ihc",
                        "candidates": [{"column_header": "IMMUNOHISTOCHEMISTRY"}],
                        "decision": {
                            "status": "standard",
                            "selected_column_header": "IMMUNOHISTOCHEMISTRY",
                            "target_files": ["patient"],
                            "reason": "IHC findings.",
                        },
                    }
                ],
            }
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            sample_path = Path(tmp_dir) / "data_clinical_sample.txt"
            _write_clinical_file(sample_path, [sample_id])
            result = validate_clinical_mapping_report(
                report,
                dictionary=[ihc],
                clinical_headers={"sample": read_clinical_header(sample_path)},
            )

        rendered_errors = "\n".join(result.errors)
        self.assertFalse(result.valid)
        self.assertIn("belongs in sample, not patient", rendered_errors)
        self.assertIn("'SAMPLE_ID' has no mapping decision", rendered_errors)


if __name__ == "__main__":
    unittest.main()
