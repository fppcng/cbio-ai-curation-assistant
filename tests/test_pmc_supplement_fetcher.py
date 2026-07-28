from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from cbio_curation_assistant import pmc_supplement_fetcher as pmc


class PmcIdentifierTest(unittest.TestCase):
    def test_identifier_type_detection_is_explicit(self) -> None:
        self.assertEqual(pmc.detect_pubmed_identifier_type("pmc123"), "PMCID")
        self.assertEqual(pmc.detect_pubmed_identifier_type("PMID456"), "PMID")
        self.assertIsNone(pmc.detect_pubmed_identifier_type("456"))
        self.assertIsNone(pmc.detect_pubmed_identifier_type("PMC-123"))

    def test_normalize_pmcid_accepts_common_forms(self) -> None:
        self.assertEqual(pmc.normalize_pmcid("pmc123"), "PMC123")
        self.assertEqual(pmc.normalize_pmcid("123"), "PMC123")
        self.assertEqual(pmc.normalize_pmcid("prefix PMC123 suffix"), "PMC123")

    def test_normalize_pmcid_rejects_empty_and_non_numeric_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty"):
            pmc.normalize_pmcid("")
        with self.assertRaisesRegex(ValueError, "Could not parse"):
            pmc.normalize_pmcid("PMC")

    def test_resolve_pmcid_does_not_use_the_converter(self) -> None:
        with patch.object(pmc, "pmid_to_pmcid") as converter:
            resolved = pmc.resolve_study_identifier_to_pmcid("PMC123")

        converter.assert_not_called()
        self.assertEqual(resolved.identifier_type, "PMCID")
        self.assertEqual(resolved.normalized_identifier, "PMC123")
        self.assertEqual(resolved.pmcid, "PMC123")

    def test_resolve_pmid_uses_the_converter(self) -> None:
        with patch.object(pmc, "pmid_to_pmcid", return_value="PMC789") as converter:
            resolved = pmc.resolve_study_identifier_to_pmcid("PMID456")

        converter.assert_called_once_with("456")
        self.assertEqual(resolved.identifier_type, "PMID")
        self.assertEqual(resolved.normalized_identifier, "456")
        self.assertEqual(resolved.pmcid, "PMC789")


class PmcErrorAndRetryTest(unittest.TestCase):
    def http_error(self, status_code: int) -> requests.HTTPError:
        response = requests.Response()
        response.status_code = status_code
        return requests.HTTPError(f"HTTP {status_code}", response=response)

    def test_http_errors_are_classified_by_status(self) -> None:
        cases = {
            429: ("rate_limited", True),
            503: ("transient_remote_error", True),
            404: ("remote_not_found", False),
            400: ("remote_http_error", False),
        }
        for status_code, expected in cases.items():
            with self.subTest(status_code=status_code):
                classification = pmc._classify_pmc_error(self.http_error(status_code))
                self.assertEqual(
                    (classification.category, classification.retryable),
                    expected,
                )
                self.assertEqual(classification.status_code, status_code)

    def test_value_errors_receive_specific_categories(self) -> None:
        cases = {
            "No PMCID found for PMID 1": ("unresolved_identifier", False),
            "PMC returned an HTML page": ("pmc_challenge", True),
            "PMID must contain digits.": ("invalid_identifier", False),
            "other invalid value": ("invalid_response", False),
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                classification = pmc._classify_pmc_error(ValueError(message))
                self.assertEqual(
                    (classification.category, classification.retryable),
                    expected,
                )

    def test_retry_repeats_retryable_failures_with_linear_backoff(self) -> None:
        request = Mock(
            side_effect=[
                requests.Timeout("first"),
                requests.Timeout("second"),
                "ok",
            ]
        )
        with patch.object(pmc.time, "sleep") as sleep:
            result = pmc._run_with_pmc_retry(
                operation="test",
                request_fn=request,
                attempts=3,
                base_delay_seconds=0.5,
            )

        self.assertEqual(result, "ok")
        self.assertEqual(request.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.5, 1.0])

    def test_retry_stops_immediately_for_non_retryable_failure(self) -> None:
        request = Mock(side_effect=ValueError("PMID must contain digits."))
        with patch.object(pmc.time, "sleep") as sleep:
            with self.assertRaises(pmc.PMCRequestError) as raised:
                pmc._run_with_pmc_retry(
                    operation="test",
                    request_fn=request,
                    attempts=3,
                    base_delay_seconds=0,
                )

        self.assertEqual(raised.exception.category, "invalid_identifier")
        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()


class PmcDownloadSafetyTest(unittest.TestCase):
    def test_downloaded_content_rejects_empty_html_and_invalid_signatures(self) -> None:
        cases = (
            ("file.txt", "text/plain", b"", "empty"),
            ("file.txt", "text/html", b"<html>blocked</html>", "HTML"),
            ("file.pdf", "application/pdf", b"not pdf", "not a PDF"),
            ("file.xlsx", "application/octet-stream", b"not zip", "ZIP-based"),
            ("file.tar.gz", "application/gzip", b"not gzip", "gzip"),
        )
        for filename, content_type, content, message in cases:
            with self.subTest(filename=filename):
                with self.assertRaisesRegex(ValueError, message):
                    pmc._validate_downloaded_content(filename, content_type, content)

    def test_downloaded_content_accepts_known_signatures(self) -> None:
        pmc._validate_downloaded_content("file.pdf", "application/pdf", b"%PDF-1.7")
        pmc._validate_downloaded_content(
            "file.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"PK\x03\x04",
        )
        pmc._validate_downloaded_content(
            "file.tar.gz",
            "application/gzip",
            b"\x1f\x8bdata",
        )

    def test_safe_filename_removes_directories_and_unsafe_characters(self) -> None:
        self.assertEqual(
            pmc._safe_filename("../../unsafe<script>.xlsx", "fallback"),
            "unsafe_script_.xlsx",
        )
        self.assertEqual(pmc._safe_filename("", "fallback"), "fallback")

    def test_safe_extract_path_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            self.assertEqual(
                pmc._safe_extract_path(base, "nested/file.tsv"),
                base / "nested" / "file.tsv",
            )
            with self.assertRaisesRegex(ValueError, "escapes"):
                pmc._safe_extract_path(base, "../outside.tsv")

    def test_zip_extraction_returns_only_supported_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            archive = root / "supplements.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("nested/table.csv", "a,b\n1,2\n")
                handle.writestr("nested/readme.md", "ignore")

            extracted = pmc._extract_supported_files(archive, root)

            self.assertEqual([path.name for path in extracted], ["table.csv"])
            self.assertEqual(extracted[0].read_text(encoding="utf-8"), "a,b\n1,2\n")

    def test_zip_extraction_rejects_traversal_members(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("../outside.csv", "a,b\n")

            with self.assertRaisesRegex(ValueError, "escapes"):
                pmc._extract_supported_files(archive, root)

    def test_supplement_discovery_deduplicates_xml_and_html_links(self) -> None:
        xml = """
        <article xmlns:xlink="http://www.w3.org/1999/xlink">
          <supplementary-material xlink:href="supp/table.xlsx" />
        </article>
        """
        html = '<a href="supp/table.xlsx">Supplementary table</a>'

        urls = pmc._discover_supplement_urls("PMC123", xml_text=xml, article_html=html)

        self.assertEqual(
            urls,
            ["https://pmc.ncbi.nlm.nih.gov/articles/PMC123/supp/table.xlsx"],
        )

    def test_download_reports_failure_when_no_supported_files_are_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch.object(pmc, "_download_oa_package", return_value=[]),
                patch.object(pmc, "_fetch_pmc_xml", return_value="<article />"),
                patch.object(pmc, "_fetch_pmc_article_html", return_value="<html />"),
            ):
                with self.assertRaisesRegex(ValueError, "No supported supplementary"):
                    pmc.download_pmc_supplements("PMC123", "PMCID", tmp_dir)

    def test_download_returns_successful_files_when_other_urls_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            downloaded_path = Path(tmp_dir) / "table.csv"
            downloaded_path.write_text("sample,value\nS1,1\n", encoding="utf-8")
            with (
                patch.object(pmc, "_download_oa_package", return_value=[]),
                patch.object(pmc, "_fetch_pmc_xml", return_value="<article />"),
                patch.object(pmc, "_fetch_pmc_article_html", return_value="<html />"),
                patch.object(
                    pmc,
                    "_discover_supplement_urls",
                    return_value=["https://example.org/good.csv", "https://example.org/bad.csv"],
                ),
                patch.object(
                    pmc,
                    "_download_url",
                    side_effect=[downloaded_path, ValueError("download failed")],
                ),
            ):
                pmcid, downloaded = pmc.download_pmc_supplements(
                    "PMC123",
                    "PMCID",
                    tmp_dir,
                )

        self.assertEqual(pmcid, "PMC123")
        self.assertEqual(len(downloaded), 1)
        self.assertEqual(downloaded[0].filename, "table.csv")


if __name__ == "__main__":
    unittest.main()
