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
        --workspace CBIO_ASSISTANT_REPO_ROOT/studies/PMC1234567/curated \
        --genome-build GRCh37
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Annotate the canonical minimal MAF in a study workspace."
    )
    parser.add_argument(
        "--workspace",
        required=True,
        type=Path,
        help="Study curated directory mounted read/write into the container.",
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


def emit(payload: dict[str, Any]) -> None:
    """Print exactly one JSON payload for Hermes."""
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def data_lines(path: Path) -> Iterable[str]:
    """Yield non-empty, non-comment MAF lines."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            yield line


def inspect_maf(path: Path, require_status: bool) -> dict[str, Any]:
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

    return {
        "columns": fieldnames,
        "records": total,
        "successful_annotations": successful,
        "failed_annotations": failed,
        "annotation_status_counts": status_counts,
    }


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


def remove_existing(paths: Iterable[Path], force: bool) -> None:
    """Reject or remove existing outputs."""
    existing = [path for path in paths if path.exists()]

    if existing and not force:
        joined = ", ".join(str(path) for path in existing)
        raise PipelineError(
            f"Output already exists: {joined}. Use --force to overwrite."
        )

    for path in existing:
        if path.is_dir():
            raise PipelineError(f"Expected a file but found a directory: {path}")
        path.unlink()


def canonical_paths(workspace: Path) -> dict[str, Path]:
    """Return the canonical mutation file layout inside the workspace."""
    return {
        "input": workspace / MINIMAL_MAF_FILENAME,
        "output": workspace / OUTPUT_MAF_FILENAME,
        "error_report": workspace / ERROR_REPORT_FILENAME,
        "log": workspace / LOG_FILENAME,
    }


def main() -> int:
    args = parse_args()

    try:
        workspace = args.workspace.expanduser().resolve()
        if not workspace.is_dir():
            raise PipelineError(f"Workspace does not exist: {workspace}")

        paths = canonical_paths(workspace)
        input_path = paths["input"]
        output_path = paths["output"]
        error_path = paths["error_report"]
        log_path = paths["log"]

        remove_existing([output_path, error_path, log_path], force=args.force)

        input_summary = inspect_maf(input_path, require_status=False)
        check_docker(args.image)

        relative_input = input_path.relative_to(workspace).as_posix()
        relative_output = output_path.relative_to(workspace).as_posix()
        relative_error = error_path.relative_to(workspace).as_posix()

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
                f"{workspace}:/wd",
                args.image,
                "java",
                "-jar",
                "annotationPipeline.jar",
                "--filename",
                f"/wd/{relative_input}",
                "--output-filename",
                f"/wd/{relative_output}",
                "--error-report-location",
                f"/wd/{relative_error}",
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
            log_path.write_text(
                (exc.stdout or "") + "\n" + (exc.stderr or ""),
                encoding="utf-8",
            )
            raise PipelineError(
                f"Genome Nexus timed out after {args.timeout} seconds."
            ) from exc

        combined_log = (
            "COMMAND\n"
            + " ".join(command)
            + "\n\nSTDOUT\n"
            + completed.stdout
            + "\n\nSTDERR\n"
            + completed.stderr
        )
        log_path.write_text(combined_log, encoding="utf-8")

        # Do not trust the process return code alone. Some pipeline-level
        # failures may still leave a successful container exit or partial file.
        if completed.returncode != 0:
            raise PipelineError(
                "Genome Nexus container failed with exit code "
                f"{completed.returncode}. See log: {log_path}"
            )

        output_summary = inspect_maf(output_path, require_status=True)

        count_mismatch = (
            input_summary["records"] != output_summary["records"]
        )
        has_failed_annotations = output_summary["failed_annotations"] > 0

        status = (
            "partial_success"
            if count_mismatch or has_failed_annotations
            else "success"
        )

        result = {
            "status": status,
            "genome_build": args.genome_build,
            "docker_image": args.image,
            "workspace": str(workspace),
            "input_file": str(input_path),
            "output_file": str(output_path),
            "error_report": str(error_path),
            "log_file": str(log_path),
            "input_records": input_summary["records"],
            "output_records": output_summary["records"],
            "successful_annotations": output_summary[
                "successful_annotations"
            ],
            "failed_annotations": output_summary["failed_annotations"],
            "annotation_status_counts": output_summary[
                "annotation_status_counts"
            ],
            "record_count_mismatch": count_mismatch,
        }
        emit(result)

        return 0 if status == "success" else 2

    except PipelineError as exc:
        emit({"status": "error", "error": str(exc)})
        return 1
    except Exception as exc:  # Defensive boundary for agent-facing execution.
        emit(
            {
                "status": "error",
                "error": f"Unexpected error: {type(exc).__name__}: {exc}",
            }
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
