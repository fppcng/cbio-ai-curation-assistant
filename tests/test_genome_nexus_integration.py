from __future__ import annotations

import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cbio_curation_assistant.integrations import genome_nexus


class GenomeNexusIntegrationTest(unittest.TestCase):
    @staticmethod
    def write_fixture_jar(path: Path) -> None:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "BOOT-INF/classes/maven.properties",
                "app.version=1.0.7\n",
            )

    def test_grch38_command_selects_endpoint_and_canonical_files(self) -> None:
        command = genome_nexus.build_annotation_command(
            Path("/study/attempt"),
            genome_build="GRCh38",
            image="fixture-image",
        )

        self.assertIn("GENOMENEXUS_BASE=https://grch38.genomenexus.org", command)
        self.assertIn("/study/attempt:/wd", command)
        self.assertIn("/wd/minimal_mutations.maf", command)
        self.assertIn("/wd/data_mutations.txt", command)
        self.assertIn("/wd/annotations_errors.txt", command)

    def test_docker_preflight_inspects_only_the_local_image(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with (
            patch.object(genome_nexus.shutil, "which", return_value="/usr/bin/docker"),
            patch.object(
                genome_nexus.subprocess,
                "run",
                return_value=completed,
            ) as run,
        ):
            genome_nexus.check_docker_image("fixture-image")

        run.assert_called_once_with(
            ["docker", "image", "inspect", "fixture-image"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_process_timeout_preserves_captured_output(self) -> None:
        timeout = subprocess.TimeoutExpired(
            cmd=["docker", "run"],
            timeout=1,
            output=b"partial stdout",
            stderr=b"partial stderr",
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(
                genome_nexus.subprocess,
                "run",
                side_effect=timeout,
            ):
                result = genome_nexus.run_annotation_container(
                    tmp_dir,
                    genome_build="GRCh37",
                    image="fixture-image",
                    timeout=1,
                )

        self.assertTrue(result.timed_out)
        self.assertIsNone(result.returncode)
        self.assertEqual(result.stdout, "partial stdout")
        self.assertEqual(result.stderr, "partial stderr")

    def test_java_command_uses_direct_absolute_paths(self) -> None:
        command = genome_nexus.build_java_annotation_command(
            Path("/study/attempt"),
            java_binary="/usr/bin/java",
            jar_path=Path("/tools/annotationPipeline.jar"),
        )

        self.assertEqual(
            command[:3], ("/usr/bin/java", "-jar", "/tools/annotationPipeline.jar")
        )
        self.assertIn("/study/attempt/minimal_mutations.maf", command)
        self.assertIn("/study/attempt/data_mutations.txt", command)
        self.assertIn("/study/attempt/annotations_errors.txt", command)

    def test_java_environment_selects_grch38_without_mutating_source(self) -> None:
        source = {
            "KEEP": "value",
            "GENOMENEXUS_BASE": "https://unexpected.example",
        }

        grch38 = genome_nexus.build_java_environment("GRCh38", base_environment=source)
        grch37 = genome_nexus.build_java_environment("GRCh37", base_environment=source)

        self.assertEqual(grch38["GENOMENEXUS_BASE"], genome_nexus.GRCH38_BASE_URL)
        self.assertNotIn("GENOMENEXUS_BASE", grch37)
        self.assertEqual(source["GENOMENEXUS_BASE"], "https://unexpected.example")

    def test_java_preflight_validates_version_checksum_and_metadata(self) -> None:
        completed = SimpleNamespace(
            returncode=0,
            stdout="",
            stderr='openjdk version "21.0.11" 2026-04-21\n',
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            jar_path = Path(tmp_dir) / "annotationPipeline.jar"
            self.write_fixture_jar(jar_path)
            checksum = genome_nexus.sha256_file(jar_path)
            source_lock = genome_nexus.GenomeNexusSourceLock(
                source_repository="https://example.test/upstream.git",
                source_ref="v1.0.7",
                source_commit="commit",
                jar_sha256=checksum,
                java_major=21,
            )
            with (
                patch.object(
                    genome_nexus.shutil,
                    "which",
                    return_value="/usr/bin/java",
                ),
                patch.object(
                    genome_nexus.subprocess,
                    "run",
                    return_value=completed,
                ) as run,
            ):
                runtime = genome_nexus.check_java_runner(
                    java_binary="java",
                    jar_path=jar_path,
                    source_lock=source_lock,
                )

        self.assertEqual(runtime.runner, "java")
        self.assertEqual(runtime.java_binary, "/usr/bin/java")
        self.assertEqual(runtime.jar_sha256, checksum)
        self.assertEqual(runtime.pipeline_version, "1.0.7")
        self.assertEqual(runtime.source_commit, "commit")
        run.assert_called_once_with(
            ["/usr/bin/java", "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_java_preflight_rejects_unpinned_jar(self) -> None:
        completed = SimpleNamespace(
            returncode=0,
            stdout="",
            stderr='openjdk version "21.0.11" 2026-04-21\n',
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            jar_path = Path(tmp_dir) / "annotationPipeline.jar"
            self.write_fixture_jar(jar_path)
            source_lock = genome_nexus.GenomeNexusSourceLock(
                source_repository="https://example.test/upstream.git",
                source_ref="v1.0.7",
                source_commit="commit",
                jar_sha256="0" * 64,
                java_major=21,
            )
            with (
                patch.object(
                    genome_nexus.shutil,
                    "which",
                    return_value="/usr/bin/java",
                ),
                patch.object(
                    genome_nexus.subprocess,
                    "run",
                    return_value=completed,
                ),
                self.assertRaisesRegex(
                    genome_nexus.GenomeNexusIntegrationError,
                    "checksum mismatch",
                ),
            ):
                genome_nexus.check_java_runner(
                    java_binary="java",
                    jar_path=jar_path,
                    source_lock=source_lock,
                )

    def test_parse_java_major_supports_modern_and_legacy_versions(self) -> None:
        self.assertEqual(genome_nexus.parse_java_major('openjdk version "21.0.11"'), 21)
        self.assertEqual(genome_nexus.parse_java_major('java version "1.8.0_402"'), 8)

    def test_reads_remote_version_from_annotated_maf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "data_mutations.txt"
            output.write_text(
                "#genome_nexus_version: 2.2.2\n"
                "#isoform: mskcc\n"
                "Chromosome\tAnnotation_Status\n",
                encoding="utf-8",
            )

            version = genome_nexus.read_genome_nexus_version(output)

        self.assertEqual(version, "2.2.2")


if __name__ == "__main__":
    unittest.main()
