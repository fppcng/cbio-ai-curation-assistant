from __future__ import annotations

import json
import os
import shutil
import subprocess
import sysconfig
import tempfile
import unittest
import zipfile
from pathlib import Path

from cbio_curation_assistant.workspace.configuration import ENV_VAR_NAME
from cbio_curation_assistant.workspace.layout import StudyWorkspace
from cbio_curation_assistant.workspace.lifecycle import initialize_workspace


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
            for module_path in (
                "cbio_curation_assistant/cli/__init__.py",
                "cbio_curation_assistant/cli/environment.py",
                "cbio_curation_assistant/cli/json_io.py",
                "cbio_curation_assistant/cli/main.py",
                "cbio_curation_assistant/cli/result.py",
                "cbio_curation_assistant/cli/commands/clinical_dictionary.py",
                "cbio_curation_assistant/cli/commands/curation_report.py",
                "cbio_curation_assistant/cli/commands/genome_nexus.py",
                "cbio_curation_assistant/cli/commands/oncotree_search.py",
                "cbio_curation_assistant/cli/commands/study_download.py",
                "cbio_curation_assistant/cli/commands/validate_study.py",
                "cbio_curation_assistant/cli/commands/workspace.py",
                "cbio_curation_assistant/cli/renderers/clinical_dictionary.py",
                "cbio_curation_assistant/cli/renderers/oncotree.py",
                "cbio_curation_assistant/cbioportal/classification.py",
                "cbio_curation_assistant/cbioportal/clinical_mapping/__init__.py",
                "cbio_curation_assistant/cbioportal/clinical_mapping/clinical_files.py",
                "cbio_curation_assistant/cbioportal/clinical_mapping/models.py",
                "cbio_curation_assistant/cbioportal/clinical_mapping/parsing.py",
                "cbio_curation_assistant/cbioportal/clinical_mapping/queries.py",
                "cbio_curation_assistant/cbioportal/clinical_mapping/report_builder.py",
                "cbio_curation_assistant/cbioportal/clinical_mapping/validation.py",
                "cbio_curation_assistant/cbioportal/specification_sources.py",
                "cbio_curation_assistant/cbioportal/specs.py",
                "cbio_curation_assistant/integrations/genome_nexus.py",
                "cbio_curation_assistant/integrations/pmc/__init__.py",
                "cbio_curation_assistant/integrations/pmc/archives.py",
                "cbio_curation_assistant/integrations/pmc/client.py",
                "cbio_curation_assistant/integrations/pmc/discovery.py",
                "cbio_curation_assistant/integrations/pmc/downloads.py",
                "cbio_curation_assistant/integrations/pmc/identifiers.py",
                "cbio_curation_assistant/integrations/pmc/models.py",
                "cbio_curation_assistant/integrations/pmc/proof_of_work.py",
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
                "cbio_curation_assistant/reports/__init__.py",
                "cbio_curation_assistant/reports/curation.py",
                "cbio_curation_assistant/reports/models.py",
                "cbio_curation_assistant/reports/pdf/__init__.py",
                "cbio_curation_assistant/reports/pdf/document.py",
                "cbio_curation_assistant/reports/pdf/layout.py",
                "cbio_curation_assistant/reports/pdf/output.py",
                "cbio_curation_assistant/reports/pdf/overview.py",
                "cbio_curation_assistant/reports/pdf/study_metadata.py",
                "cbio_curation_assistant/reports/pdf/supplementary.py",
                "cbio_curation_assistant/reports/presentation.py",
                "cbio_curation_assistant/supplements/formats.py",
                "cbio_curation_assistant/supplements/readers/__init__.py",
                "cbio_curation_assistant/supplements/readers/contracts.py",
                "cbio_curation_assistant/supplements/readers/dependencies.py",
                "cbio_curation_assistant/supplements/readers/discovery.py",
                "cbio_curation_assistant/supplements/readers/dispatch.py",
                "cbio_curation_assistant/supplements/readers/pdf.py",
                "cbio_curation_assistant/supplements/readers/tabular.py",
                "cbio_curation_assistant/supplements/readers/word.py",
                "cbio_curation_assistant/workflows/study_download.py",
                "cbio_curation_assistant/workflows/curation_report/__init__.py",
                "cbio_curation_assistant/workflows/curation_report/artifacts.py",
                "cbio_curation_assistant/workflows/curation_report/discovery.py",
                "cbio_curation_assistant/workflows/curation_report/metadata.py",
                "cbio_curation_assistant/workflows/curation_report/models.py",
                "cbio_curation_assistant/workflows/curation_report/runner.py",
                "cbio_curation_assistant/workflows/mutation_annotation.py",
                "cbio_curation_assistant/cbioportal/mutations.py",
                "cbio_curation_assistant/workspace/__init__.py",
                "cbio_curation_assistant/workspace/configuration.py",
                "cbio_curation_assistant/workspace/discovery.py",
                "cbio_curation_assistant/workspace/layout.py",
                "cbio_curation_assistant/workspace/lifecycle.py",
                "cbio_curation_assistant/workspace/manifest.py",
            ):
                with self.subTest(module_path=module_path):
                    self.assertIn(module_path, names)
            for obsolete_module_path in (
                "cbio_curation_assistant/cbioportal_spec.py",
                "cbio_curation_assistant/cli.py",
                "cbio_curation_assistant/cli_shared.py",
                "cbio_curation_assistant/clinical_dictionary_cli.py",
                "cbio_curation_assistant/config.py",
                "cbio_curation_assistant/curation_report_cli.py",
                "cbio_curation_assistant/genome_nexus_cli.py",
                "cbio_curation_assistant/hermes_llm.py",
                "cbio_curation_assistant/llm_client.py",
                "cbio_curation_assistant/metadata_merge.py",
                "cbio_curation_assistant/oncotree_cli.py",
                "cbio_curation_assistant/pdf_metadata_regex.py",
                "cbio_curation_assistant/pmc_supplement_fetcher.py",
                "cbio_curation_assistant/spec_fetcher.py",
                "cbio_curation_assistant/spec_match.py",
                "cbio_curation_assistant/study_download_cli.py",
                "cbio_curation_assistant/xml_metadata.py",
                "cbio_curation_assistant/command_result.py",
                "cbio_curation_assistant/cbioportal/clinical_mapping.py",
                "cbio_curation_assistant/reports/pdf.py",
                "cbio_curation_assistant/supplements/readers.py",
                "cbio_curation_assistant/workflows/curation_report.py",
                "cbio_curation_assistant/workspace.py",
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

            no_facades = subprocess.run(
                [
                    str(python),
                    "-c",
                    (
                        "import cbio_curation_assistant.workspace as workspace; "
                        "import cbio_curation_assistant.cbioportal.clinical_mapping "
                        "as clinical_mapping; "
                        "import cbio_curation_assistant.workflows.curation_report "
                        "as curation_report; "
                        "import cbio_curation_assistant.supplements.readers as readers; "
                        "import cbio_curation_assistant.reports.pdf as report_pdf; "
                        "assert not hasattr(workspace, 'StudyWorkspace'); "
                        "assert not hasattr(clinical_mapping, 'ClinicalMappingReport'); "
                        "assert not hasattr(curation_report, 'run_curation_report'); "
                        "assert not hasattr(readers, 'read_supplementary_file'); "
                        "assert not hasattr(report_pdf, 'build_curation_report_pdf')"
                    ),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                no_facades.returncode,
                0,
                no_facades.stderr or no_facades.stdout,
            )

            command = environment_dir / "bin" / "cbio-curation"
            help_environment = os.environ.copy()
            help_environment["PYTHONPATH"] = sysconfig.get_paths()["purelib"]
            study_download_help = subprocess.run(
                [str(command), "study-download", "--help"],
                cwd=root,
                env=help_environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                study_download_help.returncode,
                0,
                study_download_help.stderr,
            )
            self.assertIn(
                "cbio-curation study-download",
                study_download_help.stdout,
            )

            curation_report_help = subprocess.run(
                [str(command), "curation-report", "--help"],
                cwd=root,
                env=help_environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                curation_report_help.returncode,
                0,
                curation_report_help.stderr,
            )
            self.assertIn(
                "cbio-curation curation-report",
                curation_report_help.stdout,
            )

            genome_nexus_help = subprocess.run(
                [str(command), "genome-nexus", "--help"],
                cwd=root,
                env=help_environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                genome_nexus_help.returncode,
                0,
                genome_nexus_help.stderr,
            )
            self.assertIn(
                "cbio-curation genome-nexus",
                genome_nexus_help.stdout,
            )

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
            initialize_workspace(workspace)
            environment = os.environ.copy()
            environment[ENV_VAR_NAME] = str(workspace_home)
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
