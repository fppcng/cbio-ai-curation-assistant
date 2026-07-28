from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from cbio_curation_assistant import cli
from cbio_curation_assistant.cbioportal.oncotree import (
    OncotreeCandidate,
    OncotreeSearchResult,
    inspect_clinical_sample,
    load_default_oncotree_candidates,
    load_oncotree_candidates,
    load_oncotree_provenance,
    score_candidate,
    search_oncotree,
    verify_packaged_oncotree_snapshot,
)


def _luad_candidate() -> OncotreeCandidate:
    return OncotreeCandidate(
        oncotree_code="LUAD",
        cancer_type="Non-Small Cell Lung Cancer",
        cancer_type_detailed="Lung Adenocarcinoma",
        tissue="Lung",
        color="#000000",
        nci_codes="",
        umls_codes="",
        path=("Lung", "Non-Small Cell Lung Cancer", "Lung Adenocarcinoma"),
        source_row=1,
    )


class OncotreeLookupTest(unittest.TestCase):
    def test_packaged_snapshot_loads_unique_candidates(self) -> None:
        candidates = load_default_oncotree_candidates()

        self.assertGreater(len(candidates), 100)
        codes = [candidate.oncotree_code for candidate in candidates]
        self.assertEqual(len(codes), len(set(codes)))

    def test_provenance_identifies_and_verifies_the_snapshot(self) -> None:
        provenance = verify_packaged_oncotree_snapshot()

        self.assertEqual(provenance, load_oncotree_provenance())
        self.assertEqual(provenance.filename, "oncotree_snapshot.tsv")
        self.assertEqual(
            provenance.sha256,
            "d1902387241d6f965e27e6008aaab9cee9e663883922adf5d8421579db6f1d82",
        )
        self.assertEqual(
            provenance.upstream_project_url,
            "https://github.com/cBioPortal/oncotree",
        )
        self.assertEqual(provenance.license, "CC-BY-4.0")
        self.assertIsNone(provenance.upstream_release)
        self.assertIn("not recorded", provenance.provenance_notes)

    def test_exact_code_match_scores_one(self) -> None:
        candidate = _luad_candidate()

        self.assertEqual(score_candidate("luad", candidate), 1.0)
        results = search_oncotree("LUAD", [candidate], 10, 0.0)
        self.assertEqual(results[0].oncotree_code, "LUAD")
        self.assertEqual(results[0].score, 1.0)
        self.assertEqual(results[0].to_dict()["path"], list(candidate.path))

    def test_custom_table_path_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            table = Path(tmp_dir) / "custom.tsv"
            table.write_text(
                "level_1\tmetamaintype\tmetacolor\tmetanci\tmetaumls\thistory\n"
                "Lung (LUNG)\tLung Cancer\tBlue\tC1\tU1\t\n",
                encoding="utf-8",
            )
            candidates = load_oncotree_candidates(table)

        self.assertEqual([candidate.oncotree_code for candidate in candidates], ["LUNG"])

    def test_clinical_inspection_reports_missing_columns_and_suggestions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "data_clinical_sample.txt"
            path.write_text(
                "#comment\nSAMPLE_ID\tCANCER_TYPE_DETAILED\n"
                "S1\tLung Adenocarcinoma\n",
                encoding="utf-8",
            )
            inspection = inspect_clinical_sample(path, [_luad_candidate()], limit=10)

        self.assertEqual(inspection.row_count, 1)
        self.assertEqual(
            inspection.missing_standard_columns,
            ("ONCOTREE_CODE", "CANCER_TYPE"),
        )
        self.assertEqual(
            inspection.suggestions[0].matches[0].oncotree_code,
            "LUAD",
        )

    def test_empty_search_result_is_not_a_valid_workflow_state(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires a query"):
            OncotreeSearchResult()

    def test_direct_package_cli_output_is_machine_readable(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(
                ["oncotree-search", "--query", "LUAD", "--limit", "1", "--json"]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(len(payload["result"]["query_results"]), 1)
        self.assertEqual(
            payload["result"]["query_results"][0]["oncotree_code"],
            "LUAD",
        )


if __name__ == "__main__":
    unittest.main()
