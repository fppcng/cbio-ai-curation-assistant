#!/usr/bin/env python3
"""Run Genome Nexus Annotation Pipeline through Docker for a study workspace.

The script is intended to be called by a Hermes skill. It:
- expects canonical mutation filenames inside the study workspace;
- validates the minimum cBioPortal MAF columns;
- runs the pinned Genome Nexus Docker image;
- saves the container logs;
- verifies the generated MAF and Annotation_Status values;
- prints one machine-readable JSON object to stdout.

Example:
    python run_genome_nexus.py \
        --study-id <study_id> \
        --genome-build GRCh37
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

import _repo_bootstrap  # noqa: F401
from cbio_curation_assistant.command_result import (
    CommandResult,
    command_error,
    command_result,
    emit_command_result,
    exit_code_for_status,
)
from cbio_curation_assistant.workspace import StudyWorkspace
from cbio_curation_assistant.workflows.mutation_annotation import (
    GenomeNexusAttemptArtifacts,
    GenomeNexusResult,
    MafInspection,
)


DEFAULT_IMAGE = (
    "genomenexus/gn-annotation-pipeline@"
    "sha256:294705a9a80b27ec85a32ccd84e5b664170b2d2a5f60dda44fdb9b9815145858"
)
MINIMAL_MAF_FILENAME = "minimal_mutations.maf"
OUTPUT_MAF_FILENAME = "data_mutations.txt"
ERROR_REPORT_FILENAME = "annotations_errors.txt"
LOG_FILENAME = "genome_nexus.log"
REQUIRED_COLUMNS = {
    "Chromosome",
    "Start_Position",
    "End_Position",
    "Reference_Allele",
    "Tumor_Seq_Allele2",
    "Tumor_Sample_Barcode",
}


class PipelineError(RuntimeError):
    """Expected pipeline failure with a user-readable message."""


def subprocess_text(value: str | bytes | None) -> str:
    """Normalize subprocess output, including bytes attached to timeout errors."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Annotate the canonical minimal MAF in a study workspace."
    )
    parser.add_argument(
        "--study-id",
        required=True,
        help="Canonical study workspace key used to resolve the curated workspace.",
    )
    parser.add_argument(
        "--genome-build",
        required=True,
        choices=("GRCh37", "GRCh38"),
        help="Reference assembly. It must be explicitly known.",
    )
    parser.add_argument(
        "--image",
        default=os.environ.get("GENOME_NEXUS_DOCKER_IMAGE", DEFAULT_IMAGE),
        help="Docker image or pinned image digest.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Maximum execution time in seconds. Default: 1800.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing canonical Genome Nexus outputs.",
    )
    return parser.parse_args()


def emit(payload: CommandResult[Any]) -> None:
    """Print exactly one JSON payload for Hermes."""
    emit_command_result(payload)


def data_lines(path: Path) -> Iterable[str]:
    """Yield non-empty, non-comment MAF lines."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            yield line


def inspect_maf(path: Path, require_status: bool) -> MafInspection:
    """Validate a tab-delimited MAF and return row/status counts."""
    if not path.is_file():
        raise PipelineError(f"MAF file does not exist: {path}")
    if path.stat().st_size == 0:
        raise PipelineError(f"MAF file is empty: {path}")

    reader = csv.DictReader(data_lines(path), delimiter="\t")

    if not reader.fieldnames:
        raise PipelineError(f"No MAF header found in: {path}")

    fieldnames = [name.strip() for name in reader.fieldnames if name is not None]
    missing = sorted(REQUIRED_COLUMNS - set(fieldnames))

    if missing:
        raise PipelineError(
            f"MAF is missing required columns: {', '.join(missing)}"
        )

    if require_status and "Annotation_Status" not in fieldnames:
        raise PipelineError(
            "Genome Nexus output does not contain Annotation_Status."
        )

    total = 0
    successful = 0
    failed = 0
    status_counts: dict[str, int] = {}

    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise PipelineError(
                f"Row {row_number} contains more cells than the header."
            )

        total += 1

        if require_status:
            status = (row.get("Annotation_Status") or "").strip().upper()
            normalized_status = status or "EMPTY"
            status_counts[normalized_status] = (
                status_counts.get(normalized_status, 0) + 1
            )

            if status == "SUCCESS":
                successful += 1
            else:
                failed += 1

    if total == 0:
        raise PipelineError(f"MAF contains no mutation records: {path}")

    return MafInspection(
        columns=tuple(fieldnames),
        records=total,
        successful_annotations=successful,
        failed_annotations=failed,
        annotation_status_counts=status_counts,
    )


def check_docker(image: str) -> None:
    """Check Docker CLI, daemon access, and local image availability."""
    if shutil.which("docker") is None:
        raise PipelineError("Docker CLI was not found in PATH.")

    completed = subprocess.run(
        ["docker", "image", "inspect", image],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise PipelineError(
            "Genome Nexus Docker image is not available locally or Docker "
            f"is not accessible. Image: {image}. Details: {detail}"
        )


def check_existing_outputs(paths: Iterable[Path], force: bool) -> None:
    """Validate overwrite policy without modifying existing outputs."""
    existing = [path for path in paths if path.exists()]

    for path in existing:
        if path.is_dir():
            raise PipelineError(f"Expected a file but found a directory: {path}")

    if existing and not force:
        joined = ", ".join(str(path) for path in existing)
        raise PipelineError(
            f"Output already exists: {joined}. Use --force to overwrite."
        )

def canonical_paths(workspace: Path) -> dict[str, Path]:
    """Return the canonical mutation file layout inside the workspace."""
    return {
        "input": workspace / MINIMAL_MAF_FILENAME,
        "output": workspace / OUTPUT_MAF_FILENAME,
        "error_report": workspace / ERROR_REPORT_FILENAME,
        "log": workspace / LOG_FILENAME,
    }


def resolve_workspace(study_id: str) -> Path:
    return StudyWorkspace.load(study_id).curated_dir


def create_attempt_directory(workspace: Path) -> Path:
    """Create a persistent directory for one isolated annotation attempt."""
    attempts_root = workspace.parent / "validation" / "attempts"
    attempts_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="genome_nexus_", dir=attempts_root))


def promote_attempt_outputs(
    attempt_paths: dict[str, Path],
    canonical_output_paths: dict[str, Path],
    attempt_dir: Path,
) -> None:
    """Promote validated outputs, restoring previous files if promotion fails."""
    keys = ("output", "error_report", "log")
    backup_dir = attempt_dir / "previous_outputs"
    backup_dir.mkdir()
    backups: dict[str, Path] = {}
    promoted: list[str] = []

    try:
        for key in keys:
            target = canonical_output_paths[key]
            if target.exists():
                backup = backup_dir / target.name
                os.replace(target, backup)
                backups[key] = backup

        for key in keys:
            source = attempt_paths[key]
            target = canonical_output_paths[key]
            os.replace(source, target)
            promoted.append(key)
    except Exception:
        for key in reversed(promoted):
            target = canonical_output_paths[key]
            source = attempt_paths[key]
            if target.exists():
                os.replace(target, source)
        for key, backup in backups.items():
            if backup.exists():
                os.replace(backup, canonical_output_paths[key])
        if backup_dir.exists() and not any(backup_dir.iterdir()):
            backup_dir.rmdir()
        raise

    shutil.rmtree(backup_dir)


def _attempt_error_result(
    attempt_dir: Path | None,
) -> GenomeNexusAttemptArtifacts | None:
    if attempt_dir is None:
        return None
    attempt_paths = canonical_paths(attempt_dir)
    return GenomeNexusAttemptArtifacts(
        attempt_directory=attempt_dir,
        candidate_output_file=(
            attempt_paths["output"] if attempt_paths["output"].is_file() else None
        ),
        candidate_error_report=(
            attempt_paths["error_report"]
            if attempt_paths["error_report"].is_file()
            else None
        ),
        attempt_log_file=(
            attempt_paths["log"] if attempt_paths["log"].is_file() else None
        ),
    )


def main() -> int:
    args = parse_args()
    attempt_dir: Path | None = None

    try:
        if args.timeout <= 0:
            raise PipelineError("Timeout must be greater than zero seconds.")

        workspace = resolve_workspace(args.study_id).resolve()
        if not workspace.is_dir():
            raise PipelineError(f"Workspace does not exist: {workspace}")

        paths = canonical_paths(workspace)
        input_path = paths["input"]
        input_summary = inspect_maf(input_path, require_status=False)
        check_existing_outputs(
            [paths["output"], paths["error_report"], paths["log"]],
            force=args.force,
        )
        check_docker(args.image)

        attempt_dir = create_attempt_directory(workspace)
        attempt_paths = canonical_paths(attempt_dir)
        shutil.copy2(input_path, attempt_paths["input"])

        command = [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
        ]

        if args.genome_build == "GRCh38":
            command.extend(
                [
                    "-e",
                    "GENOMENEXUS_BASE=https://grch38.genomenexus.org",
                ]
            )

        command.extend(
            [
                "-v",
                f"{attempt_dir}:/wd",
                args.image,
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

        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=args.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            attempt_paths["log"].write_text(
                subprocess_text(exc.stdout) + "\n" + subprocess_text(exc.stderr),
                encoding="utf-8",
            )
            raise PipelineError(
                f"Genome Nexus timed out after {args.timeout} seconds."
            ) from exc

        combined_log = (
            "COMMAND\n"
            + " ".join(command)
            + "\n\nSTDOUT\n"
            + subprocess_text(completed.stdout)
            + "\n\nSTDERR\n"
            + subprocess_text(completed.stderr)
        )
        attempt_paths["log"].write_text(combined_log, encoding="utf-8")

        # Do not trust the process return code alone. Some pipeline-level
        # failures may still leave a successful container exit or partial file.
        if completed.returncode != 0:
            raise PipelineError(
                "Genome Nexus container failed with exit code "
                f"{completed.returncode}. See log: {attempt_paths['log']}"
            )

        output_summary = inspect_maf(attempt_paths["output"], require_status=True)

        count_mismatch = (
            input_summary.records != output_summary.records
        )
        has_failed_annotations = output_summary.failed_annotations > 0

        status = (
            "partial_success"
            if count_mismatch or has_failed_annotations
            else "success"
        )

        warnings: list[str] = []
        if count_mismatch:
            warnings.append(
                "Genome Nexus output record count does not match the input record count."
            )
        if has_failed_annotations:
            warnings.append(
                f"Genome Nexus reported {output_summary.failed_annotations} failed annotations."
            )

        if status == "partial_success":
            result = GenomeNexusResult(
                genome_build=args.genome_build,
                docker_image=args.image,
                workspace=workspace,
                input_file=input_path,
                input_records=input_summary.records,
                output_records=output_summary.records,
                successful_annotations=output_summary.successful_annotations,
                failed_annotations=output_summary.failed_annotations,
                annotation_status_counts=output_summary.annotation_status_counts,
                record_count_mismatch=count_mismatch,
                attempt=GenomeNexusAttemptArtifacts(
                    attempt_directory=attempt_dir,
                    candidate_output_file=attempt_paths["output"],
                    candidate_error_report=(
                        attempt_paths["error_report"]
                        if attempt_paths["error_report"].is_file()
                        else None
                    ),
                    attempt_log_file=attempt_paths["log"],
                ),
                canonical_output_file=(
                    paths["output"] if paths["output"].is_file() else None
                ),
                canonical_outputs_preserved=any(
                    path.exists()
                    for path in (paths["output"], paths["error_report"], paths["log"])
                ),
            )
            response = command_result(
                "genome-nexus",
                status="partial_success",
                result=result,
                warnings=warnings,
            )
            emit(response)
            return exit_code_for_status("partial_success")

        if not attempt_paths["error_report"].exists():
            attempt_paths["error_report"].write_text("", encoding="utf-8")
        promote_attempt_outputs(attempt_paths, paths, attempt_dir)
        shutil.rmtree(attempt_dir)
        attempt_dir = None
        result = GenomeNexusResult(
            genome_build=args.genome_build,
            docker_image=args.image,
            workspace=workspace,
            input_file=input_path,
            input_records=input_summary.records,
            output_records=output_summary.records,
            successful_annotations=output_summary.successful_annotations,
            failed_annotations=output_summary.failed_annotations,
            annotation_status_counts=output_summary.annotation_status_counts,
            record_count_mismatch=count_mismatch,
            output_file=paths["output"],
            error_report=paths["error_report"],
            log_file=paths["log"],
        )
        response = command_result(
            "genome-nexus",
            status="success",
            result=result,
        )
        emit(response)
        return exit_code_for_status("success")

    except PipelineError as exc:
        emit(
            command_error(
                "genome-nexus",
                exc,
                result=_attempt_error_result(attempt_dir),
            )
        )
        return 1
    except Exception as exc:  # Defensive boundary for agent-facing execution.
        emit(
            command_error(
                "genome-nexus",
                exc,
                result=_attempt_error_result(attempt_dir),
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
