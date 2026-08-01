"""Reusable parsing and validation for cBioPortal mutation MAF files."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final


REQUIRED_MAF_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "Chromosome",
        "Start_Position",
        "End_Position",
        "Reference_Allele",
        "Tumor_Seq_Allele2",
        "Tumor_Sample_Barcode",
    }
)


class MafValidationError(RuntimeError):
    """Raised when a mutation MAF does not satisfy the required contract."""


@dataclass(frozen=True, slots=True)
class MafInspection:
    """Header, record, and annotation-status counts from one mutation MAF."""

    columns: tuple[str, ...]
    records: int
    successful_annotations: int
    failed_annotations: int
    annotation_status_counts: dict[str, int]


def _data_lines(path: Path) -> Iterator[str]:
    """Yield non-empty, non-comment MAF lines."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            yield line


def inspect_maf(path: str | Path, *, require_status: bool) -> MafInspection:
    """Validate a tab-delimited mutation MAF and return its row counts."""
    maf_path = Path(path)
    if not maf_path.is_file():
        raise MafValidationError(f"MAF file does not exist: {maf_path}")
    if maf_path.stat().st_size == 0:
        raise MafValidationError(f"MAF file is empty: {maf_path}")

    reader = csv.DictReader(_data_lines(maf_path), delimiter="\t")
    if not reader.fieldnames:
        raise MafValidationError(f"No MAF header found in: {maf_path}")

    fieldnames = tuple(
        name.strip() for name in reader.fieldnames if name is not None
    )
    missing = sorted(REQUIRED_MAF_COLUMNS - set(fieldnames))
    if missing:
        raise MafValidationError(
            f"MAF is missing required columns: {', '.join(missing)}"
        )

    if require_status and "Annotation_Status" not in fieldnames:
        raise MafValidationError(
            "Genome Nexus output does not contain Annotation_Status."
        )

    total = 0
    successful = 0
    failed = 0
    status_counts: dict[str, int] = {}

    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise MafValidationError(
                f"Row {row_number} contains more cells than the header."
            )

        total += 1
        if require_status:
            status = (row.get("Annotation_Status") or "").strip().upper()
            normalized_status = status or "EMPTY"
            status_counts[normalized_status] = status_counts.get(normalized_status, 0) + 1
            if status == "SUCCESS":
                successful += 1
            else:
                failed += 1

    if total == 0:
        raise MafValidationError(f"MAF contains no mutation records: {maf_path}")

    return MafInspection(
        columns=fieldnames,
        records=total,
        successful_annotations=successful,
        failed_annotations=failed,
        annotation_status_counts=status_counts,
    )


__all__ = [
    "MafInspection",
    "MafValidationError",
    "REQUIRED_MAF_COLUMNS",
    "inspect_maf",
]
