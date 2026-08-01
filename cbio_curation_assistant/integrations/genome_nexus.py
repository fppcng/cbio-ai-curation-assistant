"""Docker integration for the Genome Nexus annotation pipeline."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal


DEFAULT_IMAGE: Final[str] = (
    "genomenexus/gn-annotation-pipeline@"
    "sha256:294705a9a80b27ec85a32ccd84e5b664170b2d2a5f60dda44fdb9b9815145858"
)
MINIMAL_MAF_FILENAME: Final[str] = "minimal_mutations.maf"
OUTPUT_MAF_FILENAME: Final[str] = "data_mutations.txt"
ERROR_REPORT_FILENAME: Final[str] = "annotations_errors.txt"


class GenomeNexusIntegrationError(RuntimeError):
    """Raised when the local Docker integration cannot be used."""


@dataclass(frozen=True, slots=True)
class GenomeNexusExecution:
    """Captured outcome of one Genome Nexus container process."""

    command: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


def subprocess_text(value: str | bytes | None) -> str:
    """Normalize captured subprocess output, including timeout bytes."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def check_docker_image(image: str) -> None:
    """Check Docker CLI, daemon access, and local image availability."""
    if shutil.which("docker") is None:
        raise GenomeNexusIntegrationError("Docker CLI was not found in PATH.")

    completed = subprocess.run(
        ["docker", "image", "inspect", image],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise GenomeNexusIntegrationError(
            "Genome Nexus Docker image is not available locally or Docker "
            f"is not accessible. Image: {image}. Details: {detail}"
        )


def build_annotation_command(
    attempt_directory: str | Path,
    *,
    genome_build: Literal["GRCh37", "GRCh38"],
    image: str,
) -> tuple[str, ...]:
    """Build the deterministic Docker command for one annotation attempt."""
    attempt_dir = Path(attempt_directory)
    command = [
        "docker",
        "run",
        "--rm",
        "--pull=never",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
    ]
    if genome_build == "GRCh38":
        command.extend(
            ["-e", "GENOMENEXUS_BASE=https://grch38.genomenexus.org"]
        )
    command.extend(
        [
            "-v",
            f"{attempt_dir}:/wd",
            image,
            "java",
            "-jar",
            "annotationPipeline.jar",
            "--filename",
            f"/wd/{MINIMAL_MAF_FILENAME}",
            "--output-filename",
            f"/wd/{OUTPUT_MAF_FILENAME}",
            "--error-report-location",
            f"/wd/{ERROR_REPORT_FILENAME}",
            "--isoform-override",
            "mskcc",
            "--output-format",
            "extended",
            "--add-original-genomic-location",
            "--note-column",
        ]
    )
    return tuple(command)


def run_annotation_container(
    attempt_directory: str | Path,
    *,
    genome_build: Literal["GRCh37", "GRCh38"],
    image: str,
    timeout: int,
) -> GenomeNexusExecution:
    """Execute Genome Nexus through Docker and capture all process output."""
    command = build_annotation_command(
        attempt_directory,
        genome_build=genome_build,
        image=image,
    )
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return GenomeNexusExecution(
            command=command,
            returncode=None,
            stdout=subprocess_text(exc.stdout),
            stderr=subprocess_text(exc.stderr),
            timed_out=True,
        )

    return GenomeNexusExecution(
        command=command,
        returncode=completed.returncode,
        stdout=subprocess_text(completed.stdout),
        stderr=subprocess_text(completed.stderr),
    )


__all__ = [
    "DEFAULT_IMAGE",
    "ERROR_REPORT_FILENAME",
    "GenomeNexusExecution",
    "GenomeNexusIntegrationError",
    "MINIMAL_MAF_FILENAME",
    "OUTPUT_MAF_FILENAME",
    "build_annotation_command",
    "check_docker_image",
    "run_annotation_container",
    "subprocess_text",
]
