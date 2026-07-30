"""Shared models and errors for the PubMed Central integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class DownloadedSupplement:
    path: str
    filename: str
    source_url: str


@dataclass(frozen=True)
class ResolvedStudyIdentifier:
    input_identifier: str
    identifier_type: Literal["PMID", "PMCID"]
    normalized_identifier: str
    pmcid: str

    @property
    def pmid(self) -> str | None:
        return (
            self.normalized_identifier
            if self.identifier_type == "PMID"
            else None
        )

    def to_dict(self) -> dict[str, str | None]:
        return {
            "input_identifier": self.input_identifier,
            "identifier_type": self.identifier_type,
            "normalized_identifier": self.normalized_identifier,
            "pmid": self.pmid,
            "pmcid": self.pmcid,
        }


@dataclass(frozen=True)
class PMCErrorClassification:
    category: str
    retryable: bool
    status_code: int | None = None


class PMCRequestError(RuntimeError):
    def __init__(
        self,
        operation: str,
        classification: PMCErrorClassification,
        detail: str,
    ) -> None:
        self.operation = operation
        self.category = classification.category
        self.retryable = classification.retryable
        self.status_code = classification.status_code
        self.detail = detail
        super().__init__(f"{operation} failed [{self.category}]: {detail}")


def format_pmc_error(error: PMCRequestError) -> str:
    """Render a stable human-readable detail for agent-facing errors."""
    if error.status_code is not None:
        return f"{error.category} (HTTP {error.status_code}): {error.detail}"
    return f"{error.category}: {error.detail}"


__all__ = [
    "DownloadedSupplement",
    "format_pmc_error",
    "PMCErrorClassification",
    "PMCRequestError",
    "ResolvedStudyIdentifier",
]
