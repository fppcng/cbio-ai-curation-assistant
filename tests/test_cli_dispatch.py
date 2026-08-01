from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from cbio_curation_assistant import cli


class CliDispatchTest(unittest.TestCase):
    def test_no_command_prints_help_and_returns_two(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main([])

        self.assertEqual(code, 2)
        self.assertIn("usage: cbio-curation", stdout.getvalue())

    def test_each_script_command_forwards_remaining_arguments(self) -> None:
        for command in cli._SCRIPT_COMMANDS:
            with self.subTest(command=command):
                with patch.object(cli, "_run_script", return_value=7) as run_script:
                    code = cli.main([command, "--example", "value"])

                self.assertEqual(code, 7)
                run_script.assert_called_once_with(command, ["--example", "value"])

    def test_study_download_uses_direct_package_dispatch(self) -> None:
        self.assertNotIn("study-download", cli._SCRIPT_COMMANDS)
        with patch.object(cli, "_run_study_download", return_value=7) as download:
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
        self.assertNotIn("curation-report", cli._SCRIPT_COMMANDS)
        with patch.object(cli, "_run_curation_report", return_value=7) as report:
            code = cli.main(["curation-report", "--study-id", "pmc123"])

        self.assertEqual(code, 7)
        report.assert_called_once_with(["--study-id", "pmc123"])

    def test_validate_command_uses_dedicated_dispatch(self) -> None:
        with patch.object(cli, "_run_validate_study", return_value=3) as validate:
            code = cli.main(["validate-study", "--study-id", "pmc1"])

        self.assertEqual(code, 3)
        validate.assert_called_once_with(["--study-id", "pmc1"])

    def test_workspace_command_uses_dedicated_dispatch(self) -> None:
        with patch.object(cli, "_run_workspace", return_value=0) as workspace:
            code = cli.main(["workspace", "describe", "--study-id", "pmc1"])

        self.assertEqual(code, 0)
        workspace.assert_called_once_with(["describe", "--study-id", "pmc1"])

    def test_unexpected_command_failure_is_rendered_as_json(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(
            cli,
            "_run_study_download",
            side_effect=RuntimeError("broken"),
        ):
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

    def test_oncotree_search_uses_direct_package_dispatch(self) -> None:
        self.assertNotIn("oncotree-search", cli._SCRIPT_COMMANDS)
        with patch.object(
            cli,
            "run_oncotree_search_command",
            return_value=7,
        ) as run:
            code = cli.main(["oncotree-search", "--query", "LUAD", "--json"])

        self.assertEqual(code, 7)
        run.assert_called_once_with(["--query", "LUAD", "--json"])

    def test_clinical_dictionary_uses_direct_package_dispatch(self) -> None:
        self.assertNotIn("clinical-dictionary", cli._SCRIPT_COMMANDS)
        with patch.object(
            cli,
            "run_clinical_dictionary_command",
            return_value=7,
        ) as run:
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
