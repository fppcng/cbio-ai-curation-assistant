"""Reader results and errors shared across supplementary formats."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pandas as pd


class SupplementaryReaderError(Exception):
    """Base exception for supplementary discovery and parsing failures."""


class UnsupportedSupplementaryFormatError(
    SupplementaryReaderError,
    ValueError,
):
    """Raised when a caller explicitly requests an unsupported file."""


class EmptySupplementaryFileError(SupplementaryReaderError, ValueError):
    """Raised when a supported file contains no readable content."""


class SupplementaryParseError(SupplementaryReaderError, ValueError):
    """Raised when a supported file cannot be parsed."""


class MissingReaderDependencyError(SupplementaryReaderError, ImportError):
    """Raised when a format-specific Python dependency cannot be imported."""

    def __init__(
        self,
        *,
        format_name: str,
        dependency: str,
        detail: str | None = None,
    ) -> None:
        self.format_name = format_name
        self.dependency = dependency
        self.detail = detail
        message = f"{format_name} supplementary files require {dependency}."
        if detail:
            message = f"{message} Import failed: {detail}"
        super().__init__(message)


class MissingExternalReaderError(SupplementaryReaderError, RuntimeError):
    """Raised when a required external document converter is unavailable."""


@dataclass(frozen=True, slots=True)
class ReaderDependencyIssue:
    """One missing or broken dependency required by discovered file formats."""

    extension: str
    dependency: str
    detail: str


class SupplementaryReaderPreflightError(SupplementaryReaderError, RuntimeError):
    """Raised when discovered supplements cannot all be read in this environment."""

    def __init__(self, issues: Sequence[ReaderDependencyIssue]) -> None:
        self.issues = tuple(issues)
        lines = [
            f"{issue.extension}: {issue.dependency} ({issue.detail})"
            for issue in self.issues
        ]
        super().__init__(
            "Supplementary reader preflight failed:\n- " + "\n- ".join(lines)
        )


@dataclass(frozen=True, slots=True)
class SupplementaryReadResult:
    """Readable sheets from one supplement plus non-fatal parse warnings."""

    path: Path
    sheets: dict[str, pd.DataFrame]
    warnings: tuple[str, ...] = ()


__all__ = [
    "EmptySupplementaryFileError",
    "MissingExternalReaderError",
    "MissingReaderDependencyError",
    "ReaderDependencyIssue",
    "SupplementaryParseError",
    "SupplementaryReadResult",
    "SupplementaryReaderError",
    "SupplementaryReaderPreflightError",
    "UnsupportedSupplementaryFormatError",
]
