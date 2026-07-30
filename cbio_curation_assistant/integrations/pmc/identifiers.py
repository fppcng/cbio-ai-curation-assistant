"""Normalization and resolution of PubMed publication identifiers."""

from __future__ import annotations

import re
from collections.abc import Callable

from cbio_curation_assistant.integrations.pmc.models import (
    ResolvedStudyIdentifier,
)


def detect_pubmed_identifier_type(identifier: str) -> str | None:
    value = (identifier or "").strip()
    if re.fullmatch(r"PMC\d+", value, flags=re.IGNORECASE):
        return "PMCID"
    if re.fullmatch(r"PMID\d+", value, flags=re.IGNORECASE):
        return "PMID"
    return None


def normalize_pmcid(value: str) -> str:
    """Return a PMCID in PMC123456 format."""
    raw = value.strip()
    if not raw:
        raise ValueError("PMCID is empty.")

    match = re.search(r"(?:PMC)?(\d+)", raw, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not parse PMCID from '{value}'.")

    return f"PMC{match.group(1)}"


def pmcid_numeric(pmcid: str) -> str:
    return normalize_pmcid(pmcid).replace("PMC", "")


def resolve_study_identifier_to_pmcid(
    identifier: str,
    *,
    pmid_resolver: Callable[[str], str] | None = None,
) -> ResolvedStudyIdentifier:
    """Resolve a user-supplied PMID or PMCID to a normalized PMCID."""
    value = (identifier or "").strip()
    identifier_type = detect_pubmed_identifier_type(value)
    if identifier_type == "PMCID":
        normalized_identifier = normalize_pmcid(value)
        return ResolvedStudyIdentifier(
            input_identifier=value,
            identifier_type=identifier_type,
            normalized_identifier=normalized_identifier,
            pmcid=normalized_identifier,
        )
    if identifier_type == "PMID":
        normalized_identifier = re.sub(r"\D", "", value)
        if pmid_resolver is None:
            from cbio_curation_assistant.integrations.pmc.client import (
                pmid_to_pmcid,
            )

            pmid_resolver = pmid_to_pmcid
        return ResolvedStudyIdentifier(
            input_identifier=value,
            identifier_type=identifier_type,
            normalized_identifier=normalized_identifier,
            pmcid=pmid_resolver(normalized_identifier),
        )
    raise ValueError(
        "Identifier must be a numeric PMID or a PMCID such as PMC123456."
    )


__all__ = [
    "detect_pubmed_identifier_type",
    "normalize_pmcid",
    "pmcid_numeric",
    "resolve_study_identifier_to_pmcid",
]
