from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch

from cbio_curation_assistant import cli
from cbio_curation_assistant.cli.main import CommandSpec


class CliDispatchTest(unittest.TestCase):
    def test_no_command_prints_help_and_returns_two(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main([])

        self.assertEqual(code, 2)
        self.assertIn("usage: cbio-curation", stdout.getvalue())

    def test_study_download_uses_direct_package_dispatch(self) -> None:
        download = Mock(return_value=7)
        with patch.object(CommandSpec, "load", return_value=download):
            code = cli.main(
                [
                    "study-download",
                    "--identifier",
                    "PMC123",
                    "--identifier-type",
                    "pmcid",
                ]
            )

        self.assertEqual(code, 7)
        download.assert_called_once_with(
            ["--identifier", "PMC123", "--identifier-type", "pmcid"]
        )

    def test_curation_report_uses_direct_package_dispatch(self) -> None:
        report = Mock(return_value=7)
        with patch.object(CommandSpec, "load", return_value=report):
            code = cli.main(["curation-report", "--study-id", "pmc123"])

        self.assertEqual(code, 7)
        report.assert_called_once_with(["--study-id", "pmc123"])

    def test_genome_nexus_uses_direct_package_dispatch(self) -> None:
        annotation = Mock(return_value=7)
        with patch.object(CommandSpec, "load", return_value=annotation):
            code = cli.main(
                [
                    "genome-nexus",
                    "--study-id",
                    "pmc123",
                    "--genome-build",
                    "GRCh37",
                ]
            )

        self.assertEqual(code, 7)
        annotation.assert_called_once_with(
            ["--study-id", "pmc123", "--genome-build", "GRCh37"]
        )

    def test_validate_command_uses_dedicated_dispatch(self) -> None:
        validate = Mock(return_value=3)
        with patch.object(CommandSpec, "load", return_value=validate):
            code = cli.main(["validate-study", "--study-id", "pmc1"])

        self.assertEqual(code, 3)
        validate.assert_called_once_with(["--study-id", "pmc1"])

    def test_workspace_command_uses_dedicated_dispatch(self) -> None:
        workspace = Mock(return_value=0)
        with patch.object(CommandSpec, "load", return_value=workspace):
            code = cli.main(["workspace", "describe", "--study-id", "pmc1"])

        self.assertEqual(code, 0)
        workspace.assert_called_once_with(["describe", "--study-id", "pmc1"])

    def test_unexpected_command_failure_is_rendered_as_json(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        failed = Mock(side_effect=RuntimeError("broken"))
        with patch.object(CommandSpec, "load", return_value=failed):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cli.main(["study-download"])

        self.assertEqual(code, 1)
        self.assertEqual(stderr.getvalue(), "")
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["command"], "study-download")
        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["error"],
            {"type": "RuntimeError", "message": "broken"},
        )

    def test_command_argument_errors_keep_argparse_contract(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            cli.main(["workspace"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("cbio-curation workspace", stderr.getvalue())

    def test_oncotree_search_uses_direct_package_dispatch(self) -> None:
        run = Mock(return_value=7)
        with patch.object(CommandSpec, "load", return_value=run):
            code = cli.main(["oncotree-search", "--query", "LUAD", "--json"])

        self.assertEqual(code, 7)
        run.assert_called_once_with(["--query", "LUAD", "--json"])

    def test_clinical_dictionary_uses_direct_package_dispatch(self) -> None:
        run = Mock(return_value=7)
        with patch.object(CommandSpec, "load", return_value=run):
            code = cli.main(
                [
                    "clinical-dictionary",
                    "search",
                    "--source-column",
                    "survival",
                    "--search-query",
                    "overall survival months",
                    "--json",
                ]
            )

        self.assertEqual(code, 7)
        run.assert_called_once_with(
            [
                "search",
                "--source-column",
                "survival",
                "--search-query",
                "overall survival months",
                "--json",
            ]
        )


if __name__ == "__main__":
    unittest.main()
