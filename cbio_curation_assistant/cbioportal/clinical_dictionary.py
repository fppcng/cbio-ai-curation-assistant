"""Load and search the packaged MSK Clinical Data Dictionary snapshot."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any


DEFAULT_LIMIT = 5
DEFAULT_MINIMUM_SCORE = 0.2
TOKEN_MATCH_WEIGHT = 0.55
STRING_MATCH_WEIGHT = 0.45
CLINICAL_DICTIONARY_RESOURCE_PACKAGE = "cbio_curation_assistant.resources.clinical"
CLINICAL_DICTIONARY_SNAPSHOT_NAME = "clinical_dictionary_snapshot.json"
CLINICAL_DICTIONARY_PROVENANCE_NAME = "provenance.json"


@dataclass(frozen=True, slots=True)
class ClinicalDictionaryAttribute:
    """One standard clinical attribute from the packaged dictionary."""

    column_header: str
    display_name: str
    description: str
    datatype: str
    attribute_type: str
    priority: str

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ClinicalDictionaryAttribute:
        return cls(
            column_header=str(values.get("column_header", "")),
            display_name=str(values.get("display_name", "")),
            description=str(values.get("description", "")),
            datatype=str(values.get("datatype", "")),
            attribute_type=str(values.get("attribute_type", "")),
            priority=str(values.get("priority", "")),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "column_header": self.column_header,
            "display_name": self.display_name,
            "description": self.description,
            "datatype": self.datatype,
            "attribute_type": self.attribute_type,
            "priority": self.priority,
        }


@dataclass(frozen=True, slots=True)
class ClinicalDictionaryMatch:
    """A dictionary attribute and its score for one proposed mapping."""

    attribute: ClinicalDictionaryAttribute
    score: float

    @property
    def column_header(self) -> str:
        return self.attribute.column_header

    def to_dict(self) -> dict[str, str | float]:
        return {"score": self.score, **self.attribute.to_dict()}


@dataclass(frozen=True, slots=True)
class ClinicalDictionaryProvenance:
    """Recorded origin and integrity metadata for the packaged snapshot."""

    schema_version: int
    dataset: str
    filename: str
    source: str
    upstream_service_url: str
    upstream_version: str | None
    upstream_retrieved_at: str | None
    repository_introduced_at: str
    sha256: str
    transformations: tuple[str, ...]
    license: str | None
    provenance_notes: str

    @classmethod
    def from_dict(
        cls,
        values: dict[str, Any],
    ) -> ClinicalDictionaryProvenance:
        return cls(
            schema_version=int(values["schema_version"]),
            dataset=str(values["dataset"]),
            filename=str(values["filename"]),
            source=str(values["source"]),
            upstream_service_url=str(values["upstream_service_url"]),
            upstream_version=(
                str(values["upstream_version"])
                if values.get("upstream_version") is not None
                else None
            ),
            upstream_retrieved_at=(
                str(values["upstream_retrieved_at"])
                if values.get("upstream_retrieved_at") is not None
                else None
            ),
            repository_introduced_at=str(values["repository_introduced_at"]),
            sha256=str(values["sha256"]),
            transformations=tuple(str(item) for item in values["transformations"]),
            license=(
                str(values["license"]) if values.get("license") is not None else None
            ),
            provenance_notes=str(values["provenance_notes"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dataset": self.dataset,
            "filename": self.filename,
            "source": self.source,
            "upstream_service_url": self.upstream_service_url,
            "upstream_version": self.upstream_version,
            "upstream_retrieved_at": self.upstream_retrieved_at,
            "repository_introduced_at": self.repository_introduced_at,
            "sha256": self.sha256,
            "transformations": list(self.transformations),
            "license": self.license,
            "provenance_notes": self.provenance_notes,
        }


def _snapshot_resource() -> Traversable:
    return files(CLINICAL_DICTIONARY_RESOURCE_PACKAGE).joinpath(
        CLINICAL_DICTIONARY_SNAPSHOT_NAME
    )


def _provenance_resource() -> Traversable:
    return files(CLINICAL_DICTIONARY_RESOURCE_PACKAGE).joinpath(
        CLINICAL_DICTIONARY_PROVENANCE_NAME
    )


def load_clinical_dictionary_provenance() -> ClinicalDictionaryProvenance:
    """Load metadata accompanying the packaged dictionary snapshot."""
    values = json.loads(_provenance_resource().read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError(
            "Packaged Clinical Data Dictionary provenance must be a JSON object."
        )
    return ClinicalDictionaryProvenance.from_dict(values)


def verify_packaged_clinical_dictionary() -> ClinicalDictionaryProvenance:
    """Verify that the packaged snapshot matches its recorded checksum."""
    provenance = load_clinical_dictionary_provenance()
    if provenance.filename != CLINICAL_DICTIONARY_SNAPSHOT_NAME:
        raise ValueError(
            "Packaged Clinical Data Dictionary provenance references "
            f"{provenance.filename!r}, expected "
            f"{CLINICAL_DICTIONARY_SNAPSHOT_NAME!r}."
        )
    actual_checksum = hashlib.sha256(_snapshot_resource().read_bytes()).hexdigest()
    if actual_checksum != provenance.sha256:
        raise ValueError(
            "Packaged Clinical Data Dictionary checksum does not match "
            f"provenance: expected {provenance.sha256}, got {actual_checksum}."
        )
    return provenance


def _normalize_text(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().lower()
    return re.sub(r"\s+", " ", normalized)


def _tokenize(value: str) -> set[str]:
    return set(_normalize_text(value).split())


def load_clinical_dictionary(
    dictionary_source: Path | Traversable,
) -> list[ClinicalDictionaryAttribute]:
    """Load dictionary attributes from a filesystem or package resource."""
    with dictionary_source.open("r", encoding="utf-8") as file_handle:
        values = json.load(file_handle)

    if not isinstance(values, list):
        raise ValueError("Clinical Data Dictionary JSON must be a list of objects.")

    return [
        ClinicalDictionaryAttribute.from_dict(value)
        for value in values
        if isinstance(value, dict)
    ]


def load_default_clinical_dictionary() -> list[ClinicalDictionaryAttribute]:
    """Verify and load the dictionary snapshot distributed with the package."""
    verify_packaged_clinical_dictionary()
    return load_clinical_dictionary(_snapshot_resource())


def _attribute_search_text(attribute: ClinicalDictionaryAttribute) -> str:
    return " ".join(
        (
            attribute.column_header,
            attribute.display_name,
            attribute.description,
        )
    )


def _score_query_text(
    query_text: str,
    candidate: ClinicalDictionaryAttribute,
) -> float:
    """Score one neutral source-derived query against a dictionary attribute."""
    normalized_query = _normalize_text(query_text)
    if not normalized_query:
        return 0.0

    candidate_text = _attribute_search_text(candidate)
    query_tokens = _tokenize(query_text)
    candidate_tokens = _tokenize(candidate_text)
    token_score = len(query_tokens & candidate_tokens) / len(query_tokens)

    candidate_fields = (
        candidate.column_header,
        candidate.display_name,
        candidate.description,
    )
    string_score = max(
        SequenceMatcher(
            None,
            normalized_query,
            _normalize_text(candidate_field),
        ).ratio()
        for candidate_field in candidate_fields
    )
    return (TOKEN_MATCH_WEIGHT * token_score) + (STRING_MATCH_WEIGHT * string_score)


def score_clinical_dictionary_candidate(
    source_column_name: str,
    candidate: ClinicalDictionaryAttribute,
    search_query: str | None = None,
) -> float:
    """Score an attribute using the source header and optional neutral query.

    ``search_query`` is a source-derived reformulation, not a proposed
    cBioPortal header. When present, it replaces the source header as the
    retrieval query so an abbreviation cannot dominate its clarified meaning.
    The original source header remains available in the mapping report.
    """
    query_text = search_query if search_query else source_column_name
    return _score_query_text(query_text, candidate)


def search_clinical_dictionary(
    source_column_name: str,
    dictionary: list[ClinicalDictionaryAttribute],
    search_query: str | None = None,
    limit: int = DEFAULT_LIMIT,
    minimum_score: float = DEFAULT_MINIMUM_SCORE,
) -> list[ClinicalDictionaryMatch]:
    """Return ranked standard-attribute candidates for a source column."""
    matches = [
        ClinicalDictionaryMatch(attribute=attribute, score=round(score, 4))
        for attribute in dictionary
        if (
            score := score_clinical_dictionary_candidate(
                source_column_name=source_column_name,
                candidate=attribute,
                search_query=search_query,
            )
        )
        >= minimum_score
    ]
    return sorted(
        matches,
        key=lambda match: (match.score, match.column_header),
        reverse=True,
    )[:limit]


__all__ = [
    "ClinicalDictionaryAttribute",
    "ClinicalDictionaryMatch",
    "ClinicalDictionaryProvenance",
    "load_clinical_dictionary",
    "load_clinical_dictionary_provenance",
    "load_default_clinical_dictionary",
    "score_clinical_dictionary_candidate",
    "search_clinical_dictionary",
    "verify_packaged_clinical_dictionary",
]
