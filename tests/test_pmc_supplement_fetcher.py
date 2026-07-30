from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from cbio_curation_assistant import pmc_supplement_fetcher as pmc
from cbio_curation_assistant.integrations import pmc as public_pmc
from cbio_curation_assistant.integrations.pmc import archives as pmc_archives
from cbio_curation_assistant.integrations.pmc import client as pmc_client
from cbio_curation_assistant.integrations.pmc import downloads as pmc_downloads
from cbio_curation_assistant.integrations.pmc import (
    proof_of_work as pmc_proof_of_work,
)


class PmcPublicApiTest(unittest.TestCase):
    def test_legacy_facade_reexports_public_models_and_identifier_helpers(
        self,
    ) -> None:
        self.assertIs(pmc.PMCRequestError, public_pmc.PMCRequestError)
        self.assertIs(
            pmc.ResolvedStudyIdentifier,
            public_pmc.ResolvedStudyIdentifier,
        )
        self.assertIs(pmc.normalize_pmcid, public_pmc.normalize_pmcid)
        self.assertIs(
            pmc.download_pmc_supplements,
            public_pmc.download_pmc_supplements,
        )

    def test_public_identifier_resolution_accepts_an_injected_pmid_resolver(
        self,
    ) -> None:
        converter = Mock(return_value="PMC789")

        resolved = public_pmc.resolve_study_identifier_to_pmcid(
            "PMID456",
            pmid_resolver=converter,
        )

        converter.assert_called_once_with("456")
        self.assertEqual(resolved.to_dict()["pmcid"], "PMC789")

    def test_public_discovery_api_matches_the_legacy_facade(self) -> None:
        xml = """
        <article xmlns:xlink="http://www.w3.org/1999/xlink">
          <supplementary-material xlink:href="table.xlsx" />
        </article>
        """

        self.assertEqual(
            public_pmc.discover_supplement_urls(
                "PMC123",
                xml_text=xml,
            ),
            pmc._discover_supplement_urls(
                "PMC123",
                xml_text=xml,
            ),
        )


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
                classification = pmc_client.classify_pmc_error(
                    self.http_error(status_code)
                )
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
                classification = pmc_client.classify_pmc_error(
                    ValueError(message)
                )
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
        with patch.object(pmc_client.time, "sleep") as sleep:
            result = pmc_client.run_with_pmc_retry(
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
        with patch.object(pmc_client.time, "sleep") as sleep:
            with self.assertRaises(pmc.PMCRequestError) as raised:
                pmc_client.run_with_pmc_retry(
                    operation="test",
                    request_fn=request,
                    attempts=3,
                    base_delay_seconds=0,
                )

        self.assertEqual(raised.exception.category, "invalid_identifier")
        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()


class PmcTransportAndDiscoveryTest(unittest.TestCase):
    def test_xml_discovery_preserves_link_resolution_and_order(self) -> None:
        xml = """
        <article xmlns:xlink="http://www.w3.org/1999/xlink">
          <supplementary-material xlink:href="table.xlsx" />
          <supplementary-material>
            <media xlink:href="supp/nested.csv" />
            <graphic xlink:href="/articles/PMC123/bin/root.tsv" />
            <inline-supplementary-material
              xlink:href="https://example.org/absolute.txt"
            />
          </supplementary-material>
        </article>
        """

        self.assertEqual(
            public_pmc.discover_supplement_urls_from_xml("PMC123", xml),
            [
                "https://pmc.ncbi.nlm.nih.gov/articles/instance/123/bin/table.xlsx",
                "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/supp/nested.csv",
                "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/bin/root.tsv",
                "https://example.org/absolute.txt",
            ],
        )

    def test_html_discovery_filters_links_and_preserves_first_occurrence(self) -> None:
        html = """
        <html><body>
          <a href="/articles/instance/123/bin/table.xlsx">Table</a>
          <a href="/articles/instance/123/bin/table.xlsx">Duplicate</a>
          <a data-ga-action="click_feat_suppl" href="files/notes.txt">Notes</a>
          <a href="/articles/instance/999/bin/other.csv">Other article</a>
          <a data-ga-action="click_feat_suppl" href="files/readme.md">Unsupported</a>
        </body></html>
        """

        self.assertEqual(
            public_pmc.discover_supplement_urls_from_html("PMC123", html),
            [
                "https://pmc.ncbi.nlm.nih.gov/articles/instance/123/bin/table.xlsx",
                "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/files/notes.txt",
            ],
        )

    def test_article_pdf_discovery_accepts_article_and_root_pdf_paths(self) -> None:
        article_html = (
            '<a href="/articles/PMC123/pdf/paper.pdf">PDF</a>'
            '<a href="/pdf/fallback.pdf">Fallback</a>'
        )
        fallback_html = '<a href="/pdf/fallback.pdf">Fallback</a>'

        self.assertEqual(
            public_pmc.discover_article_pdf_url("PMC123", article_html),
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/pdf/paper.pdf",
        )
        self.assertEqual(
            public_pmc.discover_article_pdf_url("PMC123", fallback_html),
            "https://pmc.ncbi.nlm.nih.gov/pdf/fallback.pdf",
        )
        self.assertIsNone(
            public_pmc.discover_article_pdf_url(
                "PMC123",
                '<a href="/articles/PMC999/pdf/other.pdf">Other</a>',
            )
        )

    def test_xml_fetch_retries_an_unexpected_payload_with_the_same_error(self) -> None:
        response = Mock(text="<html>not an article</html>")
        response.raise_for_status.return_value = None

        with (
            patch.object(
                pmc_client.requests,
                "get",
                return_value=response,
            ) as get,
            patch.object(pmc_client.time, "sleep") as sleep,
        ):
            with self.assertRaises(pmc.PMCRequestError) as raised:
                pmc_client.fetch_pmc_xml("PMC123")

        self.assertEqual(raised.exception.category, "unexpected_response")
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(get.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1.0, 2.0])


class PmcDownloadSafetyTest(unittest.TestCase):
    def test_proof_of_work_parser_and_solver_preserve_challenge_contract(
        self,
    ) -> None:
        html = """
        <script>
        POW_CHALLENGE = "fixture";
        POW_DIFFICULTY = "1";
        POW_COOKIE_NAME = "pmc-pow";
        POW_COOKIE_PATH = "/articles/";
        </script>
        """

        parsed = pmc_proof_of_work.parse_proof_of_work_challenge(html)

        self.assertEqual(
            parsed,
            ("fixture", 1, "pmc-pow", "/articles/"),
        )
        nonce = pmc_proof_of_work.solve_proof_of_work_nonce("fixture", 1)
        self.assertTrue(
            hashlib.sha256(f"fixture{nonce}".encode("utf-8"))
            .hexdigest()
            .startswith("0")
        )

    def test_pmc_download_retries_retryable_errors_with_linear_backoff(
        self,
    ) -> None:
        expected = Path("/tmp/downloaded.csv")
        with (
            patch.object(
                pmc_downloads,
                "download_file_once",
                side_effect=[
                    requests.Timeout("first"),
                    requests.Timeout("second"),
                    expected,
                ],
            ) as download_once,
            patch.object(pmc_downloads.time, "sleep") as sleep,
        ):
            result = pmc_downloads.download_file(
                "https://pmc.ncbi.nlm.nih.gov/file.csv",
                Path("/tmp"),
                1,
            )

        self.assertEqual(result, expected)
        self.assertEqual(download_once.call_count, 3)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            [1.0, 2.0],
        )

    def test_pmc_request_failure_falls_back_to_pow_transport(self) -> None:
        expected = Path("/tmp/downloaded.csv")
        with (
            patch.object(
                pmc_downloads.requests,
                "get",
                side_effect=requests.ConnectionError("blocked"),
            ),
            patch.object(
                pmc_downloads,
                "download_with_proof_of_work",
                return_value=expected,
            ) as pow_download,
        ):
            result = pmc_downloads.download_file_once(
                "https://pmc.ncbi.nlm.nih.gov/file.csv",
                Path("/tmp"),
                1,
            )

        self.assertEqual(result, expected)
        pow_download.assert_called_once()

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
                    public_pmc.validate_downloaded_content(
                        filename,
                        content_type,
                        content,
                    )

    def test_downloaded_content_accepts_known_signatures(self) -> None:
        public_pmc.validate_downloaded_content(
            "file.pdf",
            "application/pdf",
            b"%PDF-1.7",
        )
        public_pmc.validate_downloaded_content(
            "file.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"PK\x03\x04",
        )
        public_pmc.validate_downloaded_content(
            "file.tar.gz",
            "application/gzip",
            b"\x1f\x8bdata",
        )

    def test_safe_filename_removes_directories_and_unsafe_characters(self) -> None:
        self.assertEqual(
            pmc_downloads.safe_filename(
                "../../unsafe<script>.xlsx",
                "fallback",
            ),
            "unsafe_script_.xlsx",
        )
        self.assertEqual(
            pmc_downloads.safe_filename("", "fallback"),
            "fallback",
        )

    def test_safe_extract_path_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            self.assertEqual(
                pmc_archives.safe_extract_path(base, "nested/file.tsv"),
                base / "nested" / "file.tsv",
            )
            with self.assertRaisesRegex(ValueError, "escapes"):
                pmc_archives.safe_extract_path(base, "../outside.tsv")

    def test_zip_extraction_returns_only_supported_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            archive = root / "supplements.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("nested/table.csv", "a,b\n1,2\n")
                handle.writestr("nested/readme.md", "ignore")

            extracted = public_pmc.extract_supported_files(archive, root)

            self.assertEqual([path.name for path in extracted], ["table.csv"])
            self.assertEqual(extracted[0].read_text(encoding="utf-8"), "a,b\n1,2\n")

    def test_zip_extraction_rejects_traversal_members(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("../outside.csv", "a,b\n")

            with self.assertRaisesRegex(ValueError, "escapes"):
                public_pmc.extract_supported_files(archive, root)

    def test_supplement_discovery_deduplicates_xml_and_html_links(self) -> None:
        xml = """
        <article xmlns:xlink="http://www.w3.org/1999/xlink">
          <supplementary-material xlink:href="supp/table.xlsx" />
        </article>
        """
        html = '<a href="supp/table.xlsx">Supplementary table</a>'

        urls = public_pmc.discover_supplement_urls(
            "PMC123",
            xml_text=xml,
            article_html=html,
        )

        self.assertEqual(
            urls,
            ["https://pmc.ncbi.nlm.nih.gov/articles/PMC123/supp/table.xlsx"],
        )

    def test_download_reports_failure_when_no_supported_files_are_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch.object(
                    pmc_downloads,
                    "download_oa_package_files",
                    return_value=[],
                ),
                patch.object(
                    pmc_downloads,
                    "fetch_pmc_xml",
                    return_value="<article />",
                ),
                patch.object(
                    pmc_downloads,
                    "fetch_pmc_article_html",
                    return_value="<html />",
                ),
            ):
                with self.assertRaisesRegex(ValueError, "No supported supplementary"):
                    public_pmc.download_pmc_supplements(
                        "PMC123",
                        "PMCID",
                        tmp_dir,
                    )

    def test_download_returns_successful_files_when_other_urls_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            downloaded_path = Path(tmp_dir) / "table.csv"
            downloaded_path.write_text("sample,value\nS1,1\n", encoding="utf-8")
            with (
                patch.object(
                    pmc_downloads,
                    "download_oa_package_files",
                    return_value=[],
                ),
                patch.object(
                    pmc_downloads,
                    "fetch_pmc_xml",
                    return_value="<article />",
                ),
                patch.object(
                    pmc_downloads,
                    "fetch_pmc_article_html",
                    return_value="<html />",
                ),
                patch.object(
                    pmc_downloads,
                    "discover_supplement_urls",
                    return_value=["https://example.org/good.csv", "https://example.org/bad.csv"],
                ),
                patch.object(
                    pmc_downloads,
                    "download_file",
                    side_effect=[downloaded_path, ValueError("download failed")],
                ),
            ):
                pmcid, downloaded = public_pmc.download_pmc_supplements(
                    "PMC123",
                    "PMCID",
                    tmp_dir,
                )

        self.assertEqual(pmcid, "PMC123")
        self.assertEqual(len(downloaded), 1)
        self.assertEqual(downloaded[0].filename, "table.csv")


if __name__ == "__main__":
    unittest.main()
