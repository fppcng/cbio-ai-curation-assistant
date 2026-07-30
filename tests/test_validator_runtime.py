from __future__ import annotations

import os
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from cbio_curation_assistant import cli


class ValidatorRuntimeTest(unittest.TestCase):
    def _validator_checkout(self, root: Path) -> tuple[Path, Path]:
        validator_root = root / "cbioportal_core_validator"
        script_path = validator_root / "scripts/importer/validateData.py"
        script_path.parent.mkdir(parents=True)
        (validator_root / "pyproject.toml").write_text(
            "[project]\nname = 'validator'\nversion = '0'\n",
            encoding="utf-8",
        )
        script_path.write_text("", encoding="utf-8")
        return validator_root, script_path

    def test_validate_study_runs_the_locked_isolated_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            validator_root, script_path = self._validator_checkout(root)
            with (
                patch.object(cli, "_assistant_home", return_value=root),
                patch.object(cli.shutil, "which", return_value="/usr/bin/uv"),
                patch.dict(os.environ, {"VIRTUAL_ENV": "/main/.venv"}),
                patch.object(
                    cli.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 3),
                ) as run,
            ):
                code = cli._run_validate_study(
                    [
                        "--study-id",
                        "PMC1",
                        "--relaxed-clinical-definitions",
                        "--strict-maf-checks",
                    ]
                )

            validation_dir = root / "studies/pmc1/validation"
            run.assert_called_once_with(
                [
                    "/usr/bin/uv",
                    "run",
                    "--project",
                    str(validator_root),
                    "--frozen",
                    "--python",
                    cli.sys.executable,
                    "python",
                    str(script_path),
                    "-s",
                    str(root / "studies/pmc1/curated"),
                    "-html",
                    str(validation_dir / "validator_report.html"),
                    "-json",
                    str(validation_dir / "validator_report.json"),
                    "-n",
                    "-v",
                    "--relaxed_clinical_definitions",
                    "--strict_maf_checks",
                ],
                cwd=validator_root,
                env=ANY,
                check=False,
            )
            environment = run.call_args.kwargs["env"]
            self.assertNotIn("VIRTUAL_ENV", environment)

        self.assertEqual(code, 3)

    def test_validate_study_requires_uv_without_creating_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._validator_checkout(root)
            with (
                patch.object(cli, "_assistant_home", return_value=root),
                patch.object(cli.shutil, "which", return_value=None),
                self.assertRaisesRegex(RuntimeError, "uv executable is required"),
            ):
                cli._run_validate_study(["--study-id", "pmc1"])

            self.assertFalse((root / "studies/pmc1/validation").exists())

    def test_validator_project_matches_legacy_requirements(self) -> None:
        root = Path(__file__).resolve().parents[1]
        validator_root = root / "cbioportal_core_validator"
        project = tomllib.loads(
            (validator_root / "pyproject.toml").read_text(encoding="utf-8")
        )
        project_requirements = {
            requirement.lower()
            for requirement in project["project"]["dependencies"]
        }
        legacy_requirements = {
            requirement.lower()
            for requirement in (
                validator_root / "requirements.txt"
            ).read_text(encoding="utf-8").splitlines()
            if requirement.strip()
        }

        self.assertEqual(project_requirements, legacy_requirements)

    def test_validate_study_requires_the_isolated_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            with (
                patch.object(cli, "_assistant_home", return_value=root),
                self.assertRaisesRegex(
                    FileNotFoundError,
                    "validator project not found",
                ),
            ):
                cli._run_validate_study(["--study-id", "pmc1"])

            self.assertFalse((root / "studies/pmc1/validation").exists())


if __name__ == "__main__":
    unittest.main()
