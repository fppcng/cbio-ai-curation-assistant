"""Genome Nexus mutation-annotation workflow and typed results."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeAlias

from cbio_curation_assistant.cbioportal.mutations import (
    MafInspection,
    MafValidationError,
    inspect_maf,
)
from cbio_curation_assistant.command_result import CommandStatus
from cbio_curation_assistant.integrations import genome_nexus
from cbio_curation_assistant.workspace import StudyWorkspace


GenomeBuild: TypeAlias = Literal["GRCh37", "GRCh38"]
LOG_FILENAME = "genome_nexus.log"

# Public aliases retained here for callers that already consume the workflow
# module's file-layout contract.
DEFAULT_IMAGE = genome_nexus.DEFAULT_IMAGE
MINIMAL_MAF_FILENAME = genome_nexus.MINIMAL_MAF_FILENAME
OUTPUT_MAF_FILENAME = genome_nexus.OUTPUT_MAF_FILENAME
ERROR_REPORT_FILENAME = genome_nexus.ERROR_REPORT_FILENAME


class PipelineError(RuntimeError):
    """Expected annotation failure with a user-readable message."""


@dataclass(frozen=True, slots=True)
class GenomeNexusAttemptArtifacts:
    attempt_directory: Path
    candidate_output_file: Path | None = None
    candidate_error_report: Path | None = None
    attempt_log_file: Path | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "attempt_directory": str(self.attempt_directory),
            "candidate_output_file": (
                str(self.candidate_output_file)
                if self.candidate_output_file is not None
                else None
            ),
            "candidate_error_report": (
                str(self.candidate_error_report)
                if self.candidate_error_report is not None
                else None
            ),
            "attempt_log_file": (
                str(self.attempt_log_file)
                if self.attempt_log_file is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class GenomeNexusResult:
    genome_build: GenomeBuild
    docker_image: str
    workspace: Path
    input_file: Path
    input_records: int
    output_records: int
    successful_annotations: int
    failed_annotations: int
    annotation_status_counts: dict[str, int]
    record_count_mismatch: bool
    output_file: Path | None = None
    error_report: Path | None = None
    log_file: Path | None = None
    attempt: GenomeNexusAttemptArtifacts | None = None
    canonical_output_file: Path | None = None
    canonical_outputs_preserved: bool | None = None

    def __post_init__(self) -> None:
        canonical_outputs = (self.output_file, self.error_report, self.log_file)
        if self.attempt is not None and any(canonical_outputs):
            raise ValueError(
                "A candidate Genome Nexus result cannot also contain promoted outputs."
            )
        if self.attempt is None and not all(canonical_outputs):
            raise ValueError(
                "A promoted Genome Nexus result requires output, error-report, and log paths."
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "genome_build": self.genome_build,
            "docker_image": self.docker_image,
            "workspace": str(self.workspace),
            "input_file": str(self.input_file),
            "input_records": self.input_records,
            "output_records": self.output_records,
            "successful_annotations": self.successful_annotations,
            "failed_annotations": self.failed_annotations,
            "annotation_status_counts": dict(self.annotation_status_counts),
            "record_count_mismatch": self.record_count_mismatch,
        }
        if self.attempt is not None:
            payload.update(self.attempt.to_dict())
            payload.update(
                {
                    "canonical_output_file": (
                        str(self.canonical_output_file)
                        if self.canonical_output_file is not None
                        else None
                    ),
                    "canonical_outputs_preserved": self.canonical_outputs_preserved,
                }
            )
        else:
            payload.update(
                {
                    "output_file": str(self.output_file) if self.output_file else None,
                    "error_report": (
                        str(self.error_report) if self.error_report else None
                    ),
                    "log_file": str(self.log_file) if self.log_file else None,
                }
            )
        return payload


@dataclass(frozen=True, slots=True)
class GenomeNexusRun:
    """Typed workflow outcome before conversion to the command envelope."""

    status: CommandStatus
    result: GenomeNexusResult | GenomeNexusAttemptArtifacts | None = None
    warnings: tuple[str, ...] = ()
    error: BaseException | None = None

    def __post_init__(self) -> None:
        if self.status == "error" and self.error is None:
            raise ValueError("An error workflow outcome requires an exception.")
        if self.status != "error" and self.error is not None:
            raise ValueError("Only an error workflow outcome may contain an exception.")
        if self.status != "error" and not isinstance(self.result, GenomeNexusResult):
            raise ValueError("A successful workflow outcome requires a typed result.")


def canonical_paths(workspace: str | Path) -> dict[str, Path]:
    """Return the canonical mutation file layout inside a workspace directory."""
    workspace_path = Path(workspace)
    return {
        "input": workspace_path / MINIMAL_MAF_FILENAME,
        "output": workspace_path / OUTPUT_MAF_FILENAME,
        "error_report": workspace_path / ERROR_REPORT_FILENAME,
        "log": workspace_path / LOG_FILENAME,
    }


def resolve_workspace(
    study_id: str,
    *,
    assistant_home: str | Path | None = None,
) -> Path:
    """Resolve the canonical curated directory for an initialized study."""
    return StudyWorkspace.load(study_id, assistant_home=assistant_home).curated_dir


def check_existing_outputs(paths: Iterable[Path], *, force: bool) -> None:
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


def create_attempt_directory(workspace: str | Path) -> Path:
    """Create a persistent directory for one isolated annotation attempt."""
    workspace_path = Path(workspace)
    attempts_root = workspace_path.parent / "validation" / "attempts"
    attempts_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="genome_nexus_", dir=attempts_root))


def promote_attempt_outputs(
    attempt_paths: dict[str, Path],
    canonical_output_paths: dict[str, Path],
    attempt_dir: Path,
) -> None:
    """Promote validated outputs, restoring previous files on any failure."""
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


def _attempt_artifacts(
    attempt_dir: Path | None,
) -> GenomeNexusAttemptArtifacts | None:
    if attempt_dir is None:
        return None
    paths = canonical_paths(attempt_dir)
    return GenomeNexusAttemptArtifacts(
        attempt_directory=attempt_dir,
        candidate_output_file=paths["output"] if paths["output"].is_file() else None,
        candidate_error_report=(
            paths["error_report"] if paths["error_report"].is_file() else None
        ),
        attempt_log_file=paths["log"] if paths["log"].is_file() else None,
    )


def _write_execution_log(
    log_path: Path,
    execution: genome_nexus.GenomeNexusExecution,
) -> None:
    if execution.timed_out:
        content = execution.stdout + "\n" + execution.stderr
    else:
        content = (
            "COMMAND\n"
            + " ".join(execution.command)
            + "\n\nSTDOUT\n"
            + execution.stdout
            + "\n\nSTDERR\n"
            + execution.stderr
        )
    log_path.write_text(content, encoding="utf-8")


def run_genome_nexus_annotation(
    *,
    study_id: str,
    genome_build: GenomeBuild,
    image: str = DEFAULT_IMAGE,
    timeout: int = 1800,
    force: bool = False,
    assistant_home: str | Path | None = None,
) -> GenomeNexusRun:
    """Annotate a study's canonical minimal MAF through Genome Nexus."""
    attempt_dir: Path | None = None

    try:
        if timeout <= 0:
            raise PipelineError("Timeout must be greater than zero seconds.")
        if genome_build not in ("GRCh37", "GRCh38"):
            raise PipelineError(f"Unsupported genome build: {genome_build}")

        workspace = resolve_workspace(
            study_id,
            assistant_home=assistant_home,
        ).resolve()
        if not workspace.is_dir():
            raise PipelineError(f"Workspace does not exist: {workspace}")

        paths = canonical_paths(workspace)
        input_path = paths["input"]
        input_summary = inspect_maf(input_path, require_status=False)
        check_existing_outputs(
            (paths["output"], paths["error_report"], paths["log"]),
            force=force,
        )
        genome_nexus.check_docker_image(image)

        attempt_dir = create_attempt_directory(workspace)
        attempt_paths = canonical_paths(attempt_dir)
        shutil.copy2(input_path, attempt_paths["input"])

        execution = genome_nexus.run_annotation_container(
            attempt_dir,
            genome_build=genome_build,
            image=image,
            timeout=timeout,
        )
        _write_execution_log(attempt_paths["log"], execution)

        if execution.timed_out:
            raise PipelineError(
                f"Genome Nexus timed out after {timeout} seconds."
            )
        if execution.returncode != 0:
            raise PipelineError(
                "Genome Nexus container failed with exit code "
                f"{execution.returncode}. See log: {attempt_paths['log']}"
            )

        output_summary = inspect_maf(attempt_paths["output"], require_status=True)
        count_mismatch = input_summary.records != output_summary.records
        has_failed_annotations = output_summary.failed_annotations > 0

        warnings: list[str] = []
        if count_mismatch:
            warnings.append(
                "Genome Nexus output record count does not match the input record count."
            )
        if has_failed_annotations:
            warnings.append(
                f"Genome Nexus reported {output_summary.failed_annotations} "
                "failed annotations."
            )

        if count_mismatch or has_failed_annotations:
            result = GenomeNexusResult(
                genome_build=genome_build,
                docker_image=image,
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
            return GenomeNexusRun(
                status="partial_success",
                result=result,
                warnings=tuple(warnings),
            )

        if not attempt_paths["error_report"].exists():
            attempt_paths["error_report"].write_text("", encoding="utf-8")
        promote_attempt_outputs(attempt_paths, paths, attempt_dir)
        shutil.rmtree(attempt_dir)
        attempt_dir = None

        return GenomeNexusRun(
            status="success",
            result=GenomeNexusResult(
                genome_build=genome_build,
                docker_image=image,
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
            ),
        )
    except (MafValidationError, genome_nexus.GenomeNexusIntegrationError) as exc:
        return GenomeNexusRun(
            status="error",
            result=_attempt_artifacts(attempt_dir),
            error=PipelineError(str(exc)),
        )
    except Exception as exc:
        return GenomeNexusRun(
            status="error",
            result=_attempt_artifacts(attempt_dir),
            error=exc,
        )


__all__ = [
    "DEFAULT_IMAGE",
    "ERROR_REPORT_FILENAME",
    "GenomeBuild",
    "GenomeNexusAttemptArtifacts",
    "GenomeNexusResult",
    "GenomeNexusRun",
    "LOG_FILENAME",
    "MINIMAL_MAF_FILENAME",
    "MafInspection",
    "OUTPUT_MAF_FILENAME",
    "PipelineError",
    "canonical_paths",
    "check_existing_outputs",
    "create_attempt_directory",
    "inspect_maf",
    "promote_attempt_outputs",
    "resolve_workspace",
    "run_genome_nexus_annotation",
]
