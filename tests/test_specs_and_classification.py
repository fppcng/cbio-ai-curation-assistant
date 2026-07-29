from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime
from unittest.mock import Mock, patch

import pandas as pd
import requests

from cbio_curation_assistant import cbioportal_spec, spec_fetcher, spec_match
from cbio_curation_assistant.cbioportal import classification, specification_sources
from cbio_curation_assistant.cbioportal.specs import (
    EMBEDDED_SPEC_VERSION,
    SPECS,
    SPEC_BY_KEY,
    verify_embedded_specifications,
)


class EmbeddedSpecTest(unittest.TestCase):
    def test_embedded_specs_have_unique_keys_and_lookup_entries(self) -> None:
        keys = [spec.key for spec in SPECS]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(set(keys), set(SPEC_BY_KEY))
        for spec in SPECS:
            self.assertTrue(spec.target_file)
            self.assertIs(SPEC_BY_KEY[spec.key], spec)

    def test_embedded_spec_version_and_provenance_are_recorded(self) -> None:
        provenance = verify_embedded_specifications()
        result = specification_sources.get_embedded_spec()

        self.assertEqual(provenance.specification_version, EMBEDDED_SPEC_VERSION)
        self.assertEqual(result["version"], EMBEDDED_SPEC_VERSION)
        self.assertEqual(result["provenance"], provenance.to_dict())
        self.assertIsNone(provenance.upstream_revision)
        self.assertIn("review", provenance.promotion_policy.lower())

    def test_embedded_version_selection_rejects_unavailable_versions(self) -> None:
        selected = specification_sources.get_embedded_spec(
            version=EMBEDDED_SPEC_VERSION
        )
        self.assertEqual(selected["version"], EMBEDDED_SPEC_VERSION)

        with self.assertRaisesRegex(ValueError, "is unavailable"):
            specification_sources.get_embedded_spec(version="999.0.0")

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

    def test_live_refresh_uses_response_and_memory_cache(self) -> None:
        response = Mock()
        response.text = "## Clinical Patient Attributes\n`PATIENT_ID` (Required)\n"
        response.content = response.text.encode("utf-8")
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
            first = specification_sources.refresh_live_spec()
            second = specification_sources.refresh_live_spec()

        self.assertEqual(first["source"], "live")
        self.assertEqual(second["source"], "live")
        self.assertTrue(first["version"].startswith("sha256:"))
        self.assertTrue(first["fetched_at"].endswith("Z"))
        datetime.fromisoformat(first["fetched_at"].replace("Z", "+00:00"))
        get.assert_called_once()

    def test_live_refresh_reports_failure_without_changing_source(self) -> None:
        specification_sources.clear_cache()
        with patch.object(
            specification_sources.requests,
            "get",
            side_effect=requests.ConnectionError("offline"),
        ):
            result = specification_sources.refresh_live_spec()

        self.assertEqual(result["source"], "live")
        self.assertEqual(result["specs"], [])
        self.assertIsNone(result["version"])
        self.assertIn("offline", result["error"])

    def test_failed_live_comparison_does_not_report_false_differences(self) -> None:
        specification_sources.clear_cache()
        with patch.object(
            specification_sources.requests,
            "get",
            side_effect=requests.ConnectionError("offline"),
        ):
            comparison = specification_sources.compare_live_specifications()

        self.assertFalse(comparison.has_changes)
        self.assertEqual(comparison.differences, ())
        self.assertIn("offline", comparison.error)

    def test_live_comparison_reports_changed_fields(self) -> None:
        live_specs = list(SPECS)
        live_specs[0] = replace(
            live_specs[0],
            required=[*live_specs[0].required, "new_required_column"],
        )

        comparison = specification_sources.compare_specifications(
            live_specs,
            live_version="sha256:fixture",
            live_fetched_at="2026-07-29T12:00:00Z",
        )

        self.assertTrue(comparison.has_changes)
        self.assertEqual(comparison.embedded_version, EMBEDDED_SPEC_VERSION)
        self.assertEqual(len(comparison.differences), 1)
        self.assertEqual(
            comparison.differences[0].format_key,
            live_specs[0].key,
        )
        self.assertEqual(comparison.differences[0].changed_fields, ("required",))


class SheetClassificationTest(unittest.TestCase):
    def classify(self, frame: pd.DataFrame) -> classification.ClassificationResult:
        return classification.classify_sheet(
            frame,
            SPECS,
            spec_source="embedded",
            spec_fetched_at="fixture",
            spec_version=EMBEDDED_SPEC_VERSION,
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
        self.assertEqual(result.spec_version, EMBEDDED_SPEC_VERSION)

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
        with patch.object(
            specification_sources.requests,
            "get",
            side_effect=AssertionError("normal classification attempted network access"),
        ) as get:
            result = spec_match.classify_sheet(frame)

        self.assertEqual(result.format_key, "CLINICAL_SAMPLE")
        self.assertEqual(result.spec_source, "embedded")
        self.assertEqual(result.spec_version, EMBEDDED_SPEC_VERSION)
        get.assert_not_called()

    def test_legacy_classifier_rejects_implicit_live_refresh(self) -> None:
        with self.assertRaisesRegex(ValueError, "no longer refreshes"):
            spec_match.classify_sheet(pd.DataFrame(), force_refresh=True)


if __name__ == "__main__":
    unittest.main()
