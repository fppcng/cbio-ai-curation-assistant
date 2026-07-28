"""Typed inputs and results for mutation annotation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class MafInspection:
    columns: tuple[str, ...]
    records: int
    successful_annotations: int
    failed_annotations: int
    annotation_status_counts: dict[str, int]


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
    genome_build: str
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
                    "error_report": str(self.error_report) if self.error_report else None,
                    "log_file": str(self.log_file) if self.log_file else None,
                }
            )
        return payload
