from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cbio_curation_assistant.integrations import genome_nexus


class GenomeNexusIntegrationTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
