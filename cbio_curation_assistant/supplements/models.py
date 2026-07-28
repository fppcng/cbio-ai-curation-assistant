"""Typed results produced while classifying supplementary files."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class SupplementaryClassification:
    """Classification of one sheet, table, or document section."""

    file: str
    sheet: str
    classification: str
    cbio_target_file: str | None
    curability: str
    priority: str
    confidence: float
    verdict: str
    required_present: tuple[str, ...] = ()
    required_missing: tuple[str, ...] = ()
    optional_present: tuple[str, ...] = ()
    load_error: str | None = None

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> SupplementaryClassification:
        """Convert a legacy classification mapping at an integration boundary."""
        return cls(
            file=str(values.get("file", "")),
            sheet=str(values.get("sheet", "")),
            classification=str(values.get("classification", "NOT_LOADABLE")),
            cbio_target_file=(
                str(values["cbio_target_file"])
                if values.get("cbio_target_file") not in (None, "N/A")
                else None
            ),
            curability=str(values.get("curability", "NO")),
            priority=str(values.get("priority", "N/A")),
            confidence=float(values.get("confidence", 0) or 0),
            verdict=str(values.get("verdict", "")),
            required_present=tuple(values.get("required_present", ()) or ()),
            required_missing=tuple(values.get("required_missing", ()) or ()),
            optional_present=tuple(values.get("optional_present", ()) or ()),
            load_error=(
                str(values["load_error"])
                if values.get("load_error") is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize with the field names used by existing report JSON."""
        return {
            "file": self.file,
            "sheet": self.sheet,
            "classification": self.classification,
            "cbio_target_file": self.cbio_target_file or "N/A",
            "curability": self.curability,
            "priority": self.priority,
            "confidence": self.confidence,
            "verdict": self.verdict,
            "required_present": list(self.required_present),
            "required_missing": list(self.required_missing),
            "optional_present": list(self.optional_present),
        }
