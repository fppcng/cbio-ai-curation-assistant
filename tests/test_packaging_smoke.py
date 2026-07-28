from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from cbio_curation_assistant.workspace import ENV_VAR_NAME, StudyWorkspace


REPO_ROOT = Path(__file__).resolve().parents[1]


class InstalledWheelSmokeTest(unittest.TestCase):
    def test_built_wheel_contains_package_and_runs_workspace_command(self) -> None:
        uv = shutil.which("uv")
        if uv is None:
            self.skipTest("uv is required for the installed-wheel smoke test")

        with tempfile.TemporaryDirectory(prefix="wheel_smoke_") as tmp_dir:
            root = Path(tmp_dir)
            source = root / "source"
            source.mkdir()
            shutil.copy2(REPO_ROOT / "pyproject.toml", source / "pyproject.toml")
            shutil.copytree(
                REPO_ROOT / "cbio_curation_assistant",
                source / "cbio_curation_assistant",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            wheel_dir = root / "dist"
            wheel_dir.mkdir()
            build = subprocess.run(
                [
                    uv,
                    "build",
                    "--wheel",
                    "--offline",
                    "--out-dir",
                    str(wheel_dir),
                    ".",
                ],
                cwd=source,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(build.returncode, 0, build.stderr or build.stdout)

            wheels = list(wheel_dir.glob("*.whl"))
            self.assertEqual(len(wheels), 1)
            wheel = wheels[0]
            with zipfile.ZipFile(wheel) as archive:
                names = archive.namelist()
            self.assertIn("cbio_curation_assistant/cli.py", names)
            self.assertFalse(
                any(name.startswith("hermes_skills/") for name in names),
                "Hermes skills are currently excluded from the wheel",
            )

            environment_dir = root / "environment"
            create_environment = subprocess.run(
                [uv, "venv", "--offline", str(environment_dir)],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(
                create_environment.returncode,
                0,
                create_environment.stderr or create_environment.stdout,
            )
            python = environment_dir / "bin" / "python"
            install = subprocess.run(
                [
                    uv,
                    "pip",
                    "install",
                    "--offline",
                    "--python",
                    str(python),
                    "--no-deps",
                    str(wheel),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(install.returncode, 0, install.stderr or install.stdout)

            workspace_home = root / "assistant-home"
            workspace = StudyWorkspace.from_study_id(
                "PMC123",
                assistant_home=workspace_home,
            )
            workspace.initialize()
            environment = os.environ.copy()
            environment[ENV_VAR_NAME] = str(workspace_home)
            command = environment_dir / "bin" / "cbio-curation"
            completed = subprocess.run(
                [
                    str(command),
                    "workspace",
                    "describe",
                    "--study-id",
                    "pmc123",
                ],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["study_id"], "pmc123")


if __name__ == "__main__":
    unittest.main()
