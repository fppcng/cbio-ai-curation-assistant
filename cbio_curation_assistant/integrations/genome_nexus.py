"""Execution adapters for the Genome Nexus annotation pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Final, Literal, TypeAlias


RunnerName: TypeAlias = Literal["java", "docker"]
GenomeBuild: TypeAlias = Literal["GRCh37", "GRCh38"]

DEFAULT_RUNNER: Final[RunnerName] = "java"
DEFAULT_JAVA_BINARY: Final[str] = "java"
DEFAULT_JAR_RELATIVE_PATH: Final[Path] = Path(
    ".local-tools/genome-nexus/annotationPipeline.jar"
)
DEFAULT_IMAGE: Final[str] = (
    "genomenexus/gn-annotation-pipeline@"
    "sha256:294705a9a80b27ec85a32ccd84e5b664170b2d2a5f60dda44fdb9b9815145858"
)
GRCH37_BASE_URL: Final[str] = "https://www.genomenexus.org"
GRCH38_BASE_URL: Final[str] = "https://grch38.genomenexus.org"
SOURCE_LOCK_FILENAME: Final[str] = "genome_nexus_source.json"
MINIMAL_MAF_FILENAME: Final[str] = "minimal_mutations.maf"
OUTPUT_MAF_FILENAME: Final[str] = "data_mutations.txt"
ERROR_REPORT_FILENAME: Final[str] = "annotations_errors.txt"


class GenomeNexusIntegrationError(RuntimeError):
    """Raised when the configured Genome Nexus runner cannot be used."""


@dataclass(frozen=True, slots=True)
class GenomeNexusSourceLock:
    source_repository: str
    source_ref: str
    source_commit: str
    jar_sha256: str
    java_major: int


@dataclass(frozen=True, slots=True)
class GenomeNexusRuntime:
    runner: RunnerName
    genome_nexus_base_url: str
    docker_image: str | None = None
    java_binary: str | None = None
    java_version: str | None = None
    jar_path: Path | None = None
    jar_sha256: str | None = None
    pipeline_version: str | None = None
    source_commit: str | None = None


@dataclass(frozen=True, slots=True)
class GenomeNexusExecution:
    """Captured outcome of one Genome Nexus process."""

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


def load_source_lock() -> GenomeNexusSourceLock:
    """Load the package-owned Genome Nexus source and artifact lock."""
    resource = files("cbio_curation_assistant.resources").joinpath(SOURCE_LOCK_FILENAME)
    payload = json.loads(resource.read_text(encoding="utf-8"))
    return GenomeNexusSourceLock(
        source_repository=str(payload["source_repository"]),
        source_ref=str(payload["source_ref"]),
        source_commit=str(payload["source_commit"]),
        jar_sha256=str(payload["jar_sha256"]),
        java_major=int(payload["java_major"]),
    )


def sha256_file(path: str | Path) -> str:
    """Calculate a lowercase SHA-256 digest without loading the file at once."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_pipeline_version(jar_path: str | Path) -> str:
    """Read the build version embedded in the executable Spring Boot JAR."""
    try:
        with zipfile.ZipFile(jar_path) as archive:
            candidates = sorted(
                name
                for name in archive.namelist()
                if name.endswith("/maven.properties") or name == "maven.properties"
            )
            for name in candidates:
                for line in archive.read(name).decode("utf-8").splitlines():
                    key, separator, value = line.partition("=")
                    if separator and key.strip() == "app.version":
                        return value.strip()
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
        raise GenomeNexusIntegrationError(
            f"Could not inspect Genome Nexus JAR metadata: {jar_path}. {exc}"
        ) from exc
    raise GenomeNexusIntegrationError(
        f"Genome Nexus JAR does not contain an app.version: {jar_path}"
    )


def read_genome_nexus_version(output_path: str | Path) -> str | None:
    """Read the remote Genome Nexus version recorded in an annotated MAF."""
    try:
        with Path(output_path).open("r", encoding="utf-8-sig") as output:
            for line in output:
                if not line.startswith("#"):
                    break
                key, separator, value = line[1:].partition(":")
                if separator and key.strip() == "genome_nexus_version":
                    normalized = value.strip()
                    return normalized or None
    except OSError as exc:
        raise GenomeNexusIntegrationError(
            f"Could not inspect Genome Nexus output metadata: {output_path}. {exc}"
        ) from exc
    return None


def parse_java_major(version_output: str) -> int:
    """Extract a Java major version from standard ``java -version`` output."""
    match = re.search(r'version\s+"(?P<version>\d+(?:\.\d+)*)', version_output)
    if match is None:
        raise GenomeNexusIntegrationError(
            f"Could not determine Java version from: {version_output.strip()!r}"
        )
    components = match.group("version").split(".")
    return int(components[1] if components[0] == "1" else components[0])


def genome_nexus_base_url(genome_build: GenomeBuild) -> str:
    if genome_build == "GRCh37":
        return GRCH37_BASE_URL
    if genome_build == "GRCh38":
        return GRCH38_BASE_URL
    raise GenomeNexusIntegrationError(f"Unsupported genome build: {genome_build}")


def check_java_runner(
    *,
    java_binary: str,
    jar_path: str | Path,
    source_lock: GenomeNexusSourceLock | None = None,
) -> GenomeNexusRuntime:
    """Validate Java and the pinned pipeline artifact before modifying a study."""
    resolved_java = shutil.which(java_binary)
    if resolved_java is None:
        raise GenomeNexusIntegrationError(
            f"Genome Nexus Java executable was not found on PATH: {java_binary}"
        )

    resolved_jar = Path(jar_path).expanduser().resolve()
    if not resolved_jar.is_file():
        raise GenomeNexusIntegrationError(
            f"Genome Nexus JAR was not found: {resolved_jar}"
        )

    completed = subprocess.run(
        [resolved_java, "-version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    version_output = (completed.stderr or completed.stdout).strip()
    if completed.returncode != 0:
        raise GenomeNexusIntegrationError(
            f"Could not execute the configured Java runtime. Details: {version_output}"
        )
    java_major = parse_java_major(version_output)

    lock = source_lock or load_source_lock()
    if java_major < lock.java_major:
        raise GenomeNexusIntegrationError(
            "Genome Nexus requires Java "
            f"{lock.java_major} or newer; found Java {java_major}."
        )

    jar_sha256 = sha256_file(resolved_jar)
    if lock.jar_sha256 and jar_sha256 != lock.jar_sha256:
        raise GenomeNexusIntegrationError(
            "Genome Nexus JAR checksum mismatch. "
            f"Expected {lock.jar_sha256}, found {jar_sha256}."
        )

    return GenomeNexusRuntime(
        runner="java",
        genome_nexus_base_url=GRCH37_BASE_URL,
        java_binary=resolved_java,
        java_version=version_output.splitlines()[0] if version_output else None,
        jar_path=resolved_jar,
        jar_sha256=jar_sha256,
        pipeline_version=read_pipeline_version(resolved_jar),
        source_commit=lock.source_commit,
    )


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


def prepare_runtime(
    *,
    runner: RunnerName,
    genome_build: GenomeBuild,
    image: str = DEFAULT_IMAGE,
    java_binary: str = DEFAULT_JAVA_BINARY,
    jar_path: str | Path | None = None,
    source_lock: GenomeNexusSourceLock | None = None,
) -> GenomeNexusRuntime:
    """Preflight one explicitly selected execution runtime."""
    base_url = genome_nexus_base_url(genome_build)
    if runner == "docker":
        check_docker_image(image)
        return GenomeNexusRuntime(
            runner="docker",
            docker_image=image,
            genome_nexus_base_url=base_url,
        )
    if runner == "java":
        if jar_path is None:
            raise GenomeNexusIntegrationError(
                "GENOME_NEXUS_JAR_PATH is required for the Java runner."
            )
        checked = check_java_runner(
            java_binary=java_binary,
            jar_path=jar_path,
            source_lock=source_lock,
        )
        return GenomeNexusRuntime(
            runner=checked.runner,
            genome_nexus_base_url=base_url,
            java_binary=checked.java_binary,
            java_version=checked.java_version,
            jar_path=checked.jar_path,
            jar_sha256=checked.jar_sha256,
            pipeline_version=checked.pipeline_version,
            source_commit=checked.source_commit,
        )
    raise GenomeNexusIntegrationError(f"Unsupported Genome Nexus runner: {runner}")


def build_annotation_command(
    attempt_directory: str | Path,
    *,
    genome_build: GenomeBuild,
    image: str,
) -> tuple[str, ...]:
    """Build the legacy Docker command for one annotation attempt."""
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
        command.extend(["-e", f"GENOMENEXUS_BASE={GRCH38_BASE_URL}"])
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


def build_java_annotation_command(
    attempt_directory: str | Path,
    *,
    java_binary: str,
    jar_path: str | Path,
) -> tuple[str, ...]:
    """Build a direct Java command using canonical attempt filenames."""
    attempt_dir = Path(attempt_directory).expanduser().resolve()
    return (
        java_binary,
        "-jar",
        str(Path(jar_path).expanduser().resolve()),
        "--filename",
        str(attempt_dir / MINIMAL_MAF_FILENAME),
        "--output-filename",
        str(attempt_dir / OUTPUT_MAF_FILENAME),
        "--error-report-location",
        str(attempt_dir / ERROR_REPORT_FILENAME),
        "--isoform-override",
        "mskcc",
        "--output-format",
        "extended",
        "--add-original-genomic-location",
        "--note-column",
    )


def build_java_environment(
    genome_build: GenomeBuild,
    *,
    base_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the subprocess environment without mutating the parent process."""
    environment = dict(os.environ if base_environment is None else base_environment)
    if genome_build == "GRCh38":
        environment["GENOMENEXUS_BASE"] = GRCH38_BASE_URL
    else:
        environment.pop("GENOMENEXUS_BASE", None)
    return environment


def _run_command(
    command: tuple[str, ...],
    *,
    timeout: int,
    environment: Mapping[str, str] | None = None,
) -> GenomeNexusExecution:
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=(dict(environment) if environment is not None else None),
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


def run_annotation_container(
    attempt_directory: str | Path,
    *,
    genome_build: GenomeBuild,
    image: str,
    timeout: int,
) -> GenomeNexusExecution:
    """Execute Genome Nexus through the legacy Docker runner."""
    return _run_command(
        build_annotation_command(
            attempt_directory,
            genome_build=genome_build,
            image=image,
        ),
        timeout=timeout,
    )


def run_annotation_with_java(
    attempt_directory: str | Path,
    *,
    genome_build: GenomeBuild,
    runtime: GenomeNexusRuntime,
    timeout: int,
) -> GenomeNexusExecution:
    """Execute Genome Nexus directly with the preflighted Java runtime."""
    if runtime.java_binary is None or runtime.jar_path is None:
        raise GenomeNexusIntegrationError(
            "Java runner metadata is incomplete after preflight."
        )
    command = build_java_annotation_command(
        attempt_directory,
        java_binary=runtime.java_binary,
        jar_path=runtime.jar_path,
    )
    return _run_command(
        command,
        timeout=timeout,
        environment=build_java_environment(genome_build),
    )


def run_annotation(
    attempt_directory: str | Path,
    *,
    genome_build: GenomeBuild,
    runtime: GenomeNexusRuntime,
    timeout: int,
) -> GenomeNexusExecution:
    """Dispatch annotation through one explicitly preflighted runtime."""
    if runtime.runner == "java":
        return run_annotation_with_java(
            attempt_directory,
            genome_build=genome_build,
            runtime=runtime,
            timeout=timeout,
        )
    if runtime.runner == "docker":
        if runtime.docker_image is None:
            raise GenomeNexusIntegrationError(
                "Docker runner metadata is incomplete after preflight."
            )
        return run_annotation_container(
            attempt_directory,
            genome_build=genome_build,
            image=runtime.docker_image,
            timeout=timeout,
        )
    raise GenomeNexusIntegrationError(
        f"Unsupported Genome Nexus runner: {runtime.runner}"
    )


__all__ = [
    "DEFAULT_IMAGE",
    "DEFAULT_JAR_RELATIVE_PATH",
    "DEFAULT_JAVA_BINARY",
    "DEFAULT_RUNNER",
    "ERROR_REPORT_FILENAME",
    "GRCH37_BASE_URL",
    "GRCH38_BASE_URL",
    "GenomeNexusExecution",
    "GenomeNexusIntegrationError",
    "GenomeNexusRuntime",
    "GenomeNexusSourceLock",
    "MINIMAL_MAF_FILENAME",
    "OUTPUT_MAF_FILENAME",
    "RunnerName",
    "build_annotation_command",
    "build_java_annotation_command",
    "build_java_environment",
    "check_docker_image",
    "check_java_runner",
    "genome_nexus_base_url",
    "load_source_lock",
    "parse_java_major",
    "prepare_runtime",
    "read_genome_nexus_version",
    "read_pipeline_version",
    "run_annotation",
    "run_annotation_container",
    "run_annotation_with_java",
    "sha256_file",
    "subprocess_text",
]
