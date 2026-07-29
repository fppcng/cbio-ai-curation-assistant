from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import pandas as pd
import requests

from cbio_curation_assistant import cbioportal_spec, spec_fetcher, spec_match
from cbio_curation_assistant.cbioportal import classification, specification_sources
from cbio_curation_assistant.cbioportal.specs import SPECS, SPEC_BY_KEY


class EmbeddedSpecTest(unittest.TestCase):
    def test_embedded_specs_have_unique_keys_and_lookup_entries(self) -> None:
        keys = [spec.key for spec in SPECS]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(set(keys), set(SPEC_BY_KEY))
        for spec in SPECS:
            self.assertTrue(spec.target_file)
            self.assertIs(SPEC_BY_KEY[spec.key], spec)

    def test_live_markdown_parser_updates_known_sections_and_keeps_fallbacks(self) -> None:
        markdown = """
## Clinical Patient Attributes
`PATIENT_ID` (Required)
`OS_MONTHS` (Optional)

## Mutation Data
`Hugo_Symbol` (Required)
`Tumor_Sample_Barcode` (Required)
"""
        parsed = specification_sources.parse_upstream_specifications(markdown)
        by_key = {spec.key: spec for spec in parsed}

        self.assertEqual(by_key["CLINICAL_PATIENT"].required, ["patient_id"])
        self.assertEqual(by_key["CLINICAL_PATIENT"].optional, ["os_months"])
        self.assertIn("MUTATION_MAF", by_key)
        self.assertEqual(set(by_key), {spec.key for spec in SPECS})

    def test_fetch_spec_uses_live_response_and_memory_cache(self) -> None:
        response = Mock()
        response.text = "## Clinical Patient Attributes\n`PATIENT_ID` (Required)\n"
        response.raise_for_status.return_value = None

        specification_sources.clear_cache()
        with (
            patch.object(specification_sources.requests, "get", return_value=response) as get,
            patch.object(
                specification_sources,
                "parse_upstream_specifications",
                return_value=list(SPECS),
            ),
        ):
            first = specification_sources.fetch_spec()
            second = specification_sources.fetch_spec()

        self.assertEqual(first["source"], "live")
        self.assertEqual(second["source"], "live")
        get.assert_called_once()

    def test_fetch_spec_falls_back_when_network_fails(self) -> None:
        specification_sources.clear_cache()
        with patch.object(
            specification_sources.requests,
            "get",
            side_effect=requests.ConnectionError("offline"),
        ):
            result = specification_sources.fetch_spec()

        self.assertEqual(result["source"], "embedded")
        self.assertEqual(result["specs"], SPECS)
        self.assertIn("offline", result["error"])


class SheetClassificationTest(unittest.TestCase):
    def classify(self, frame: pd.DataFrame) -> classification.ClassificationResult:
        return classification.classify_sheet(
            frame,
            SPECS,
            spec_source="embedded",
            spec_fetched_at="fixture",
        )

    def test_alias_headers_classify_as_clinical_sample(self) -> None:
        frame = pd.DataFrame(
            [["case id", "specimen id", "primary site"], ["P1", "S1", "Lung"]]
        )
        result = self.classify(frame)

        self.assertEqual(result.format_key, "CLINICAL_SAMPLE")
        self.assertEqual(result.target_file, "data_clinical_sample.txt")
        self.assertEqual(result.detected_as_aliases["patient_id"], "case id")
        self.assertEqual(result.detected_as_aliases["sample_id"], "specimen id")
        self.assertEqual(result.spec_source, "embedded")

    def test_mutation_headers_classify_as_maf(self) -> None:
        frame = pd.DataFrame(
            [
                [
                    "Hugo_Symbol",
                    "Tumor_Sample_Barcode",
                    "Chromosome",
                    "Start_Position",
                    "End_Position",
                    "Reference_Allele",
                    "Tumor_Seq_Allele2",
                ],
                ["TP53", "S1", "17", "1", "1", "A", "T"],
            ]
        )
        result = self.classify(frame)

        self.assertEqual(result.format_key, "MUTATION_MAF")
        self.assertEqual(result.required_missing, [])
        self.assertGreaterEqual(result.confidence, 70)

    def test_unstructured_sheet_is_not_loadable(self) -> None:
        frame = pd.DataFrame([["methods and acknowledgements"], ["no tabular schema"]])
        result = self.classify(frame)

        self.assertEqual(result.format_key, "NOT_LOADABLE")
        self.assertEqual(result.confidence, 0)
        self.assertIn("below", result.notes)

    def test_matrix_detection_requires_string_ids_and_numeric_values(self) -> None:
        matrix = pd.DataFrame(
            [["Hugo_Symbol", "S1", "S2"], ["TP53", 1.0, 2.0], ["EGFR", 3.0, 4.0]]
        )
        non_matrix = pd.DataFrame([["sample", "value"], ["S1", "text"]])

        self.assertTrue(classification._looks_like_matrix(matrix))
        self.assertFalse(classification._looks_like_matrix(non_matrix))


class CompatibilityModuleTest(unittest.TestCase):
    def test_legacy_public_imports_and_convenience_classifier_remain_available(
        self,
    ) -> None:
        self.assertIs(cbioportal_spec.SPECS, SPECS)
        self.assertIs(spec_fetcher.fetch_spec, specification_sources.fetch_spec)

        frame = pd.DataFrame(
            [["PATIENT_ID", "SAMPLE_ID", "primary site"], ["P1", "S1", "Lung"]]
        )
        fetch_result = {
            "specs": list(SPECS),
            "source": "embedded",
            "fetched_at": "fixture",
            "url": None,
            "error": None,
        }
        with patch.object(spec_match, "fetch_spec", return_value=fetch_result):
            result = spec_match.classify_sheet(frame)

        self.assertEqual(result.format_key, "CLINICAL_SAMPLE")
        self.assertEqual(result.spec_source, "embedded")


if __name__ == "__main__":
    unittest.main()
