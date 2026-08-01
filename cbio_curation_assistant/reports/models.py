"""Typed data used to construct curation reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReportBreakdownRow:
    file: str
    sheet: str
    cbio_format: str
    curability: str
    priority: str
    confidence: float
    verdict: str
    required_present: tuple[str, ...] = ()
    required_missing: tuple[str, ...] = ()
    optional_present: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "sheet": self.sheet,
            "cbio_format": self.cbio_format,
            "curability": self.curability,
            "priority": self.priority,
            "confidence": self.confidence,
            "verdict": self.verdict,
            "req_present": list(self.required_present),
            "req_missing": list(self.required_missing),
            "opt_present": list(self.optional_present),
        }


@dataclass(frozen=True, slots=True)
class CurationSummary:
    study_id: str
    cancer_type: str
    num_samples: str | int
    reference_genome: str
    files_analysed: int
    sheets_analysed: int
    high_priority: int
    medium_priority: int
    not_loadable: int
    file_breakdown: tuple[ReportBreakdownRow, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "cancer_type": self.cancer_type,
            "num_samples": self.num_samples,
            "reference_genome": self.reference_genome,
            "files_analysed": self.files_analysed,
            "sheets_analysed": self.sheets_analysed,
            "high_priority": self.high_priority,
            "medium_priority": self.medium_priority,
            "not_loadable": self.not_loadable,
            "file_breakdown": [row.to_dict() for row in self.file_breakdown],
        }


__all__ = ["CurationSummary", "ReportBreakdownRow"]
