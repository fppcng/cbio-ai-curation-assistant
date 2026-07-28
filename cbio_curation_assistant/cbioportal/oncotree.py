"""Load, search, and inspect the packaged OncoTree hierarchy snapshot."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any


DEFAULT_LIMIT = 10
ONCOTREE_RESOURCE_PACKAGE = "cbio_curation_assistant.resources.oncotree"
ONCOTREE_SNAPSHOT_NAME = "oncotree_snapshot.tsv"
ONCOTREE_PROVENANCE_NAME = "provenance.json"
CODE_PATTERN = re.compile(r"^(?P<name>.*?)\s*\((?P<code>[A-Za-z0-9_]+)\)\s*$")
MISSING_VALUES = {"", "NA", "N/A", "NAN", "NULL", "NONE", "UNKNOWN"}
SEARCH_FIELDS = (
    "ONCOTREE_CODE",
    "CANCER_TYPE_DETAILED",
    "CANCER_TYPE",
    "HISTOLOGY",
    "TUMOR_TYPE",
    "SAMPLE_TYPE",
    "PRIMARY_SITE",
    "METASTATIC_SITE",
)
METADATA_COLUMN_COUNT = 5


@dataclass(frozen=True, slots=True)
class OncotreeCandidate:
    """Normalized candidate parsed from the OncoTree hierarchy."""

    oncotree_code: str
    cancer_type: str
    cancer_type_detailed: str
    tissue: str
    color: str
    nci_codes: str
    umls_codes: str
    path: tuple[str, ...]
    source_row: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "oncotree_code": self.oncotree_code,
            "cancer_type": self.cancer_type,
            "cancer_type_detailed": self.cancer_type_detailed,
            "tissue": self.tissue,
            "color": self.color,
            "nci_codes": self.nci_codes,
            "umls_codes": self.umls_codes,
            "path": list(self.path),
            "source_row": self.source_row,
        }


@dataclass(frozen=True, slots=True)
class OncotreeMatch:
    """Candidate plus the score assigned for one query."""

    candidate: OncotreeCandidate
    score: float

    @property
    def oncotree_code(self) -> str:
        return self.candidate.oncotree_code

    def to_dict(self) -> dict[str, Any]:
        return {**self.candidate.to_dict(), "score": self.score}


@dataclass(frozen=True, slots=True)
class ClinicalValueSuggestion:
    source_column: str
    source_value: str
    matches: tuple[OncotreeMatch, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_column": self.source_column,
            "source_value": self.source_value,
            "matches": [match.to_dict() for match in self.matches],
        }


@dataclass(frozen=True, slots=True)
class ClinicalOncotreeInspection:
    clinical_file: Path
    row_count: int
    missing_standard_columns: tuple[str, ...]
    available_search_columns: tuple[str, ...]
    suggestions: tuple[ClinicalValueSuggestion, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "clinical_file": str(self.clinical_file),
            "row_count": self.row_count,
            "missing_standard_columns": list(self.missing_standard_columns),
            "available_search_columns": list(self.available_search_columns),
            "suggestions": [
                suggestion.to_dict() for suggestion in self.suggestions
            ],
        }


@dataclass(frozen=True, slots=True)
class OncotreeSearchResult:
    query_results: tuple[OncotreeMatch, ...] | None = None
    clinical_inspection: ClinicalOncotreeInspection | None = None

    def __post_init__(self) -> None:
        if self.query_results is None and self.clinical_inspection is None:
            raise ValueError("An OncoTree result requires a query or clinical inspection.")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.query_results is not None:
            result["query_results"] = [
                match.to_dict() for match in self.query_results
            ]
        if self.clinical_inspection is not None:
            result["clinical_inspection"] = self.clinical_inspection.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class OncotreeProvenance:
    schema_version: int
    dataset: str
    filename: str
    source: str
    upstream_project_url: str
    license: str
    upstream_release: str | None
    upstream_retrieved_at: str | None
    repository_introduced_at: str
    sha256: str
    transformations: tuple[str, ...]
    provenance_notes: str

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> OncotreeProvenance:
        return cls(
            schema_version=int(values["schema_version"]),
            dataset=str(values["dataset"]),
            filename=str(values["filename"]),
            source=str(values["source"]),
            upstream_project_url=str(values["upstream_project_url"]),
            license=str(values["license"]),
            upstream_release=(
                str(values["upstream_release"])
                if values.get("upstream_release") is not None
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
            provenance_notes=str(values["provenance_notes"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dataset": self.dataset,
            "filename": self.filename,
            "source": self.source,
            "upstream_project_url": self.upstream_project_url,
            "license": self.license,
            "upstream_release": self.upstream_release,
            "upstream_retrieved_at": self.upstream_retrieved_at,
            "repository_introduced_at": self.repository_introduced_at,
            "sha256": self.sha256,
            "transformations": list(self.transformations),
            "provenance_notes": self.provenance_notes,
        }


def _snapshot_resource() -> Traversable:
    return files(ONCOTREE_RESOURCE_PACKAGE).joinpath(ONCOTREE_SNAPSHOT_NAME)


def _provenance_resource() -> Traversable:
    return files(ONCOTREE_RESOURCE_PACKAGE).joinpath(ONCOTREE_PROVENANCE_NAME)


def load_oncotree_provenance() -> OncotreeProvenance:
    """Load the metadata accompanying the packaged hierarchy snapshot."""
    values = json.loads(_provenance_resource().read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError("Packaged OncoTree provenance must be a JSON object.")
    return OncotreeProvenance.from_dict(values)


def verify_packaged_oncotree_snapshot() -> OncotreeProvenance:
    """Verify that the packaged snapshot matches its recorded checksum."""
    provenance = load_oncotree_provenance()
    if provenance.filename != ONCOTREE_SNAPSHOT_NAME:
        raise ValueError(
            "Packaged OncoTree provenance references "
            f"{provenance.filename!r}, expected {ONCOTREE_SNAPSHOT_NAME!r}."
        )
    actual_checksum = hashlib.sha256(_snapshot_resource().read_bytes()).hexdigest()
    if actual_checksum != provenance.sha256:
        raise ValueError(
            "Packaged OncoTree snapshot checksum does not match provenance: "
            f"expected {provenance.sha256}, got {actual_checksum}."
        )
    return provenance


def normalize_text(value: str) -> str:
    """Normalize matching text by collapsing punctuation and whitespace."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().lower()
    return re.sub(r"\s+", " ", normalized)


def tokenize(value: str) -> set[str]:
    return set(normalize_text(value).split())


def split_oncotree_label(value: str) -> tuple[str, str]:
    match = CODE_PATTERN.match(value.strip())
    if not match:
        return value.strip(), ""
    return match.group("name").strip(), match.group("code").strip().upper()


def is_missing(value: str) -> bool:
    return value.strip().upper() in MISSING_VALUES


def clean_cell(value: str | None) -> str:
    return "" if value is None else value.strip()


def load_oncotree_candidates(
    oncotree_source: Path | Traversable,
) -> list[OncotreeCandidate]:
    """Load unique candidates from a path or package resource."""
    candidates_by_code: dict[str, OncotreeCandidate] = {}

    with oncotree_source.open("r", encoding="utf-8", newline="") as file_handle:
        reader = csv.reader(file_handle, delimiter="\t")
        next(reader, None)

        for source_row, row in enumerate(reader, start=2):
            if len(row) < METADATA_COLUMN_COUNT + 1:
                continue

            hierarchy = [
                clean_cell(value) for value in row[:-METADATA_COLUMN_COUNT]
            ]
            hierarchy = [value for value in hierarchy if value]
            if not hierarchy:
                continue

            tissue_name, _ = split_oncotree_label(hierarchy[0])
            cancer_type = clean_cell(row[-5])
            color = clean_cell(row[-4])
            nci_codes = clean_cell(row[-3])
            umls_codes = clean_cell(row[-2])

            for level_value in hierarchy:
                detailed_name, code = split_oncotree_label(level_value)
                if not code:
                    continue

                candidate = OncotreeCandidate(
                    oncotree_code=code,
                    cancer_type=cancer_type or detailed_name,
                    cancer_type_detailed=detailed_name,
                    tissue=tissue_name,
                    color=color,
                    nci_codes=nci_codes,
                    umls_codes=umls_codes,
                    path=tuple(
                        split_oncotree_label(value)[0] for value in hierarchy
                    ),
                    source_row=source_row,
                )
                existing = candidates_by_code.get(code)
                if existing is None or len(candidate.path) < len(existing.path):
                    candidates_by_code[code] = candidate

    return sorted(candidates_by_code.values(), key=lambda item: item.oncotree_code)


def load_default_oncotree_candidates() -> list[OncotreeCandidate]:
    """Verify and load the hierarchy snapshot distributed with the package."""
    verify_packaged_oncotree_snapshot()
    return load_oncotree_candidates(_snapshot_resource())


def candidate_search_text(candidate: OncotreeCandidate) -> str:
    return " ".join(
        (
            candidate.oncotree_code,
            candidate.cancer_type,
            candidate.cancer_type_detailed,
            candidate.tissue,
            " ".join(candidate.path),
        )
    )


def score_candidate(query: str, candidate: OncotreeCandidate) -> float:
    """Score one candidate against a code or descriptive query."""
    query_clean = query.strip()
    if query_clean.upper() == candidate.oncotree_code:
        return 1.0

    candidate_text = candidate_search_text(candidate)
    query_tokens = tokenize(query_clean)
    candidate_tokens = tokenize(candidate_text)
    token_score = 0.0
    if query_tokens:
        token_score = len(query_tokens & candidate_tokens) / len(query_tokens)

    name_score = SequenceMatcher(
        None,
        normalize_text(query_clean),
        normalize_text(candidate.cancer_type_detailed),
    ).ratio()
    text_score = SequenceMatcher(
        None,
        normalize_text(query_clean),
        normalize_text(candidate_text),
    ).ratio()
    return max(token_score, name_score, text_score)


def search_oncotree(
    query: str,
    candidates: list[OncotreeCandidate],
    limit: int,
    minimum_score: float,
) -> list[OncotreeMatch]:
    """Return ranked candidates using the existing deterministic scoring."""
    matches = [
        OncotreeMatch(candidate=candidate, score=round(score, 4))
        for candidate in candidates
        if (score := score_candidate(query, candidate)) >= minimum_score
    ]
    return sorted(
        matches,
        key=lambda match: (match.score, match.oncotree_code),
        reverse=True,
    )[:limit]


def read_clinical_sample(
    clinical_file: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    """Read a cBioPortal clinical sample table."""
    with clinical_file.open("r", encoding="utf-8", newline="") as file_handle:
        reader = csv.reader(file_handle, delimiter="\t")
        header: list[str] | None = None
        rows: list[dict[str, str]] = []
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            if header is None:
                header = row
                continue
            rows.append(dict(zip(header, row, strict=False)))

    if header is None:
        raise ValueError(f"No clinical sample header found in {clinical_file}.")
    return header, rows


def inspect_clinical_sample(
    clinical_file: Path,
    candidates: list[OncotreeCandidate],
    limit: int,
) -> ClinicalOncotreeInspection:
    """Inspect standard columns and suggest mappings for clinical values."""
    header, rows = read_clinical_sample(clinical_file)
    existing_columns = set(header)
    missing_standard_columns = tuple(
        column
        for column in ("ONCOTREE_CODE", "CANCER_TYPE", "CANCER_TYPE_DETAILED")
        if column not in existing_columns
    )
    available_search_columns = tuple(
        column for column in SEARCH_FIELDS if column in existing_columns
    )

    suggestions: list[ClinicalValueSuggestion] = []
    for column in SEARCH_FIELDS:
        if column not in existing_columns:
            continue
        values = {
            row.get(column, "").strip()
            for row in rows
            if not is_missing(row.get(column, ""))
        }
        for value in sorted(values)[:limit]:
            suggestions.append(
                ClinicalValueSuggestion(
                    source_column=column,
                    source_value=value,
                    matches=tuple(
                        search_oncotree(
                            query=value,
                            candidates=candidates,
                            limit=3,
                            minimum_score=0.4,
                        )
                    ),
                )
            )

    return ClinicalOncotreeInspection(
        clinical_file=clinical_file,
        row_count=len(rows),
        missing_standard_columns=missing_standard_columns,
        available_search_columns=available_search_columns,
        suggestions=tuple(suggestions),
    )


__all__ = [
    "ClinicalOncotreeInspection",
    "ClinicalValueSuggestion",
    "OncotreeCandidate",
    "OncotreeMatch",
    "OncotreeProvenance",
    "OncotreeSearchResult",
    "candidate_search_text",
    "clean_cell",
    "inspect_clinical_sample",
    "is_missing",
    "load_default_oncotree_candidates",
    "load_oncotree_candidates",
    "load_oncotree_provenance",
    "normalize_text",
    "read_clinical_sample",
    "score_candidate",
    "search_oncotree",
    "split_oncotree_label",
    "tokenize",
    "verify_packaged_oncotree_snapshot",
]
