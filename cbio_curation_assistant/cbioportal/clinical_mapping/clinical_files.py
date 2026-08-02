"""Parse canonical cBioPortal clinical file headers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cbio_curation_assistant.cbioportal.clinical_mapping.models import (
    CLINICAL_METADATA_FIELDS,
)


@dataclass(frozen=True, slots=True)
class ClinicalAttributeMetadata:
    """The four cBioPortal metadata values for one clinical column."""

    display_name: str
    description: str
    datatype: str
    priority: str

    def to_dict(self) -> dict[str, str]:
        return {field: str(getattr(self, field)) for field in CLINICAL_METADATA_FIELDS}


@dataclass(frozen=True, slots=True)
class ClinicalHeader:
    """Parsed five-row header from one clinical data file."""

    attributes: Mapping[str, ClinicalAttributeMetadata]


def read_clinical_header(path: Path) -> ClinicalHeader:
    """Parse and validate the five-row cBioPortal clinical header."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 5:
        raise ValueError(f"Clinical file has fewer than five header rows: {path}")
    for row_index in range(4):
        if not lines[row_index].startswith("#"):
            raise ValueError(
                f"Clinical metadata row {row_index + 1} must start with '#': {path}"
            )

    metadata_rows = [lines[index][1:].split("\t") for index in range(4)]
    headers = lines[4].split("\t")
    for row_index, row in enumerate(metadata_rows, start=1):
        if len(row) != len(headers):
            raise ValueError(
                f"Clinical metadata row {row_index} has {len(row)} values but "
                f"row 5 has {len(headers)} columns: {path}"
            )
    if len(headers) != len(set(headers)):
        raise ValueError(f"Clinical file contains duplicate column headers: {path}")

    return ClinicalHeader(
        attributes={
            header: ClinicalAttributeMetadata(
                **{
                    field: metadata_rows[index][column_index]
                    for index, field in enumerate(CLINICAL_METADATA_FIELDS)
                }
            )
            for column_index, header in enumerate(headers)
        }
    )


__all__ = ["ClinicalAttributeMetadata", "ClinicalHeader", "read_clinical_header"]
