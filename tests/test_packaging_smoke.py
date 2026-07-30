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
            for module_path in (
                "cbio_curation_assistant/cbioportal/classification.py",
                "cbio_curation_assistant/cbioportal/specification_sources.py",
                "cbio_curation_assistant/cbioportal/specs.py",
                "cbio_curation_assistant/cbioportal_spec.py",
                "cbio_curation_assistant/integrations/pmc/__init__.py",
                "cbio_curation_assistant/integrations/pmc/client.py",
                "cbio_curation_assistant/integrations/pmc/discovery.py",
                "cbio_curation_assistant/integrations/pmc/identifiers.py",
                "cbio_curation_assistant/integrations/pmc/models.py",
                "cbio_curation_assistant/llm/__init__.py",
                "cbio_curation_assistant/llm/client.py",
                "cbio_curation_assistant/llm/models.py",
                "cbio_curation_assistant/llm/parsing.py",
                "cbio_curation_assistant/llm/providers.py",
                "cbio_curation_assistant/llm/settings.py",
                "cbio_curation_assistant/publications/completion.py",
                "cbio_curation_assistant/publications/metadata.py",
                "cbio_curation_assistant/publications/models.py",
                "cbio_curation_assistant/publications/pdf.py",
                "cbio_curation_assistant/publications/xml.py",
                "cbio_curation_assistant/spec_fetcher.py",
                "cbio_curation_assistant/spec_match.py",
                "cbio_curation_assistant/supplements/formats.py",
                "cbio_curation_assistant/supplements/readers.py",
            ):
                with self.subTest(module_path=module_path):
                    self.assertIn(module_path, names)
            for obsolete_module_path in (
                "cbio_curation_assistant/cli_shared.py",
                "cbio_curation_assistant/metadata_merge.py",
                "cbio_curation_assistant/pdf_metadata_regex.py",
                "cbio_curation_assistant/xml_metadata.py",
            ):
                with self.subTest(obsolete_module_path=obsolete_module_path):
                    self.assertNotIn(obsolete_module_path, names)
            self.assertIn(
                "cbio_curation_assistant/resources/cbioportal/specification_provenance.json",
                names,
            )
            self.assertIn(
                "cbio_curation_assistant/resources/clinical/clinical_dictionary_snapshot.json",
                names,
            )
            self.assertIn(
                "cbio_curation_assistant/resources/clinical/provenance.json",
                names,
            )
            self.assertIn(
                "cbio_curation_assistant/resources/oncotree/oncotree_snapshot.tsv",
                names,
            )
            self.assertIn(
                "cbio_curation_assistant/resources/oncotree/provenance.json",
                names,
            )
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

            llm_import = subprocess.run(
                [
                    str(python),
                    "-c",
                    (
                        "from cbio_curation_assistant.llm import "
                        "build_llm_config, parse_llm_json; "
                        "build_llm_config('OpenAI', "
                        "environment={'OPENAI_API_KEY': 'fixture'}); "
                        "parse_llm_json('{\"installed\": true}')"
                    ),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                llm_import.returncode,
                0,
                llm_import.stderr or llm_import.stdout,
            )

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
            self.assertEqual(payload["result"]["study_id"], "pmc123")

            oncotree = subprocess.run(
                [
                    str(command),
                    "oncotree-search",
                    "--query",
                    "LUAD",
                    "--limit",
                    "1",
                    "--json",
                ],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(oncotree.returncode, 0, oncotree.stderr)
            oncotree_payload = json.loads(oncotree.stdout)
            self.assertEqual(oncotree_payload["status"], "success")
            self.assertEqual(
                oncotree_payload["result"]["query_results"][0]["oncotree_code"],
                "LUAD",
            )

            clinical_dictionary = subprocess.run(
                [
                    str(command),
                    "clinical-dictionary",
                    "search",
                    "--source-column",
                    "patient age",
                    "--search-query",
                    "age at diagnosis",
                    "--limit",
                    "1",
                    "--json",
                ],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                clinical_dictionary.returncode,
                0,
                clinical_dictionary.stderr,
            )
            dictionary_payload = json.loads(clinical_dictionary.stdout)
            self.assertEqual(dictionary_payload["status"], "success")
            self.assertEqual(
                dictionary_payload["result"]["report"]["mappings"][0]["candidates"][0][
                    "column_header"
                ],
                "AGE_AT_DIAGNOSIS",
            )


if __name__ == "__main__":
    unittest.main()
