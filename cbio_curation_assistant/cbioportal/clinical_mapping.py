"""Build and validate auditable Clinical Data Dictionary mapping reports."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeAlias

from cbio_curation_assistant.cbioportal.clinical_dictionary import (
    DEFAULT_LIMIT,
    DEFAULT_MINIMUM_SCORE,
    ClinicalDictionaryAttribute,
    ClinicalDictionaryMatch,
    search_clinical_dictionary,
)


REPORT_SCHEMA_VERSION = 1
CLINICAL_METADATA_FIELDS = (
    "display_name",
    "description",
    "datatype",
    "priority",
)
VALID_DATATYPES = frozenset(("STRING", "NUMBER", "BOOLEAN"))
CUSTOM_HEADER_PATTERN = re.compile(r"^[A-Z0-9_]+$")

ClinicalTarget: TypeAlias = Literal["patient", "sample"]
DecisionStatus: TypeAlias = Literal["standard", "custom", "excluded"]
VALID_TARGET_FILES: frozenset[str] = frozenset(("patient", "sample"))
VALID_DECISION_STATUSES: frozenset[str] = frozenset(
    ("standard", "custom", "excluded")
)


def _require_nonempty_string(
    value: Any,
    *,
    field: str,
    context: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} requires non-empty string field {field!r}.")
    return value.strip()


def _optional_string(value: Any, *, field: str, context: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{context} {field} must be a string when provided.")
    return value.strip() or None


@dataclass(frozen=True, slots=True)
class ClinicalMappingQuery:
    """One source-derived dictionary search request."""

    id: str
    source_column: str
    search_query: str | None = None
    source_file: str | None = None
    source_sheet: str | None = None

    @classmethod
    def from_dict(
        cls,
        values: Mapping[str, Any],
        *,
        index: int,
    ) -> ClinicalMappingQuery:
        context = f"Query {index}"
        return cls(
            id=_require_nonempty_string(
                values.get("id", f"query_{index}"),
                field="id",
                context=context,
            ),
            source_column=_require_nonempty_string(
                values.get("source_column"),
                field="source_column",
                context=context,
            ),
            search_query=_optional_string(
                values.get("search_query"),
                field="search_query",
                context=context,
            ),
            source_file=_optional_string(
                values.get("source_file"),
                field="source_file",
                context=context,
            ),
            source_sheet=_optional_string(
                values.get("source_sheet"),
                field="source_sheet",
                context=context,
            ),
        )


def parse_clinical_mapping_queries(
    payload: Mapping[str, Any],
) -> tuple[str | None, tuple[ClinicalMappingQuery, ...]]:
    """Parse and validate batch-search input."""
    raw_queries = payload.get("queries")
    if not isinstance(raw_queries, list) or not raw_queries:
        raise ValueError(
            "Clinical dictionary batch input requires a non-empty queries list."
        )
    if not all(isinstance(query, dict) for query in raw_queries):
        raise ValueError("Every clinical dictionary query must be a JSON object.")

    study_id = payload.get("study_id")
    if study_id is not None and not isinstance(study_id, str):
        raise ValueError("Batch input study_id must be a string when provided.")
    queries = tuple(
        ClinicalMappingQuery.from_dict(query, index=index)
        for index, query in enumerate(raw_queries, start=1)
    )
    query_ids = [query.id for query in queries]
    if len(query_ids) != len(set(query_ids)):
        raise ValueError("Clinical dictionary query ids must be unique.")
    return study_id, queries


@dataclass(frozen=True, slots=True)
class ClinicalMappingSource:
    """Source provenance retained for one mapping decision."""

    file: str | None
    sheet: str | None
    column: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "file": self.file,
            "sheet": self.sheet,
            "column": self.column,
        }


@dataclass(frozen=True, slots=True)
class ClinicalMappingCandidate:
    """One recorded dictionary candidate."""

    column_header: str
    score: float | None = None
    display_name: str = ""
    description: str = ""
    datatype: str = ""
    attribute_type: str = ""
    priority: str = ""

    @classmethod
    def from_match(
        cls,
        match: ClinicalDictionaryMatch,
    ) -> ClinicalMappingCandidate:
        attribute = match.attribute
        return cls(
            column_header=attribute.column_header,
            score=match.score,
            display_name=attribute.display_name,
            description=attribute.description,
            datatype=attribute.datatype,
            attribute_type=attribute.attribute_type,
            priority=attribute.priority,
        )

    @classmethod
    def from_dict(
        cls,
        values: Mapping[str, Any],
        *,
        context: str,
    ) -> ClinicalMappingCandidate:
        score_value = values.get("score")
        if score_value is not None and not isinstance(score_value, int | float):
            raise ValueError(f"{context} candidate score must be numeric.")
        return cls(
            column_header=_require_nonempty_string(
                values.get("column_header"),
                field="column_header",
                context=f"{context} candidate",
            ),
            score=float(score_value) if score_value is not None else None,
            display_name=str(values.get("display_name", "")),
            description=str(values.get("description", "")),
            datatype=str(values.get("datatype", "")),
            attribute_type=str(values.get("attribute_type", "")),
            priority=str(values.get("priority", "")),
        )

    def to_dict(self) -> dict[str, str | float | None]:
        return {
            "score": self.score,
            "column_header": self.column_header,
            "display_name": self.display_name,
            "description": self.description,
            "datatype": self.datatype,
            "attribute_type": self.attribute_type,
            "priority": self.priority,
        }


@dataclass(frozen=True, slots=True)
class ClinicalMetadataOverride:
    """One justified deviation from dictionary metadata."""

    value: str
    reason: str

    @classmethod
    def from_dict(
        cls,
        values: Mapping[str, Any],
        *,
        field: str,
        context: str,
    ) -> ClinicalMetadataOverride:
        value = values.get("value")
        if not isinstance(value, str):
            raise ValueError(
                f"{context} override {field!r} value must be a string."
            )
        return cls(
            value=value,
            reason=_require_nonempty_string(
                values.get("reason"),
                field="reason",
                context=f"{context} override {field!r}",
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class ClinicalCustomAttribute:
    """Canonical header metadata for a justified custom attribute."""

    column_header: str
    display_name: str
    description: str
    datatype: str
    priority: str

    @classmethod
    def from_dict(
        cls,
        values: Mapping[str, Any],
        *,
        context: str,
    ) -> ClinicalCustomAttribute:
        attribute = cls(
            column_header=_require_nonempty_string(
                values.get("column_header"),
                field="column_header",
                context=context,
            ),
            display_name=_require_nonempty_string(
                values.get("display_name"),
                field="display_name",
                context=context,
            ),
            description=_require_nonempty_string(
                values.get("description"),
                field="description",
                context=context,
            ),
            datatype=_require_nonempty_string(
                values.get("datatype"),
                field="datatype",
                context=context,
            ),
            priority=_require_nonempty_string(
                values.get("priority"),
                field="priority",
                context=context,
            ),
        )
        if CUSTOM_HEADER_PATTERN.fullmatch(attribute.column_header) is None:
            raise ValueError(
                f"{context} column_header must contain only A-Z, 0-9, and '_'."
            )
        if attribute.datatype not in VALID_DATATYPES:
            raise ValueError(
                f"{context} datatype must be one of "
                f"{', '.join(sorted(VALID_DATATYPES))}."
            )
        return attribute

    def metadata(self) -> dict[str, str]:
        return {
            field: str(getattr(self, field))
            for field in CLINICAL_METADATA_FIELDS
        }

    def to_dict(self) -> dict[str, str]:
        return {
            "column_header": self.column_header,
            **self.metadata(),
        }


@dataclass(frozen=True, slots=True)
class ClinicalMappingDecision:
    """Hermes decision for one source field."""

    status: DecisionStatus
    reason: str
    selected_column_header: str | None = None
    target_files: tuple[ClinicalTarget, ...] | None = None
    custom_attribute: ClinicalCustomAttribute | None = None
    metadata_overrides: Mapping[str, ClinicalMetadataOverride] | None = None

    @classmethod
    def from_dict(
        cls,
        values: Mapping[str, Any],
        *,
        context: str,
    ) -> ClinicalMappingDecision:
        raw_status = values.get("status")
        if raw_status not in VALID_DECISION_STATUSES:
            raise ValueError(
                f"{context}: status must be standard, custom, or excluded."
            )
        status: DecisionStatus = raw_status

        raw_targets = values.get("target_files")
        targets: tuple[ClinicalTarget, ...] | None = None
        if raw_targets is not None:
            if not isinstance(raw_targets, list) or not all(
                isinstance(target, str) for target in raw_targets
            ):
                raise ValueError(f"{context}: target_files must be a list of strings.")
            invalid_targets = sorted(set(raw_targets) - VALID_TARGET_FILES)
            if invalid_targets:
                raise ValueError(
                    f"{context}: invalid target files: "
                    f"{', '.join(invalid_targets)}."
                )
            targets = tuple(dict.fromkeys(raw_targets))

        raw_overrides = values.get("metadata_overrides")
        overrides: dict[str, ClinicalMetadataOverride] | None = None
        if raw_overrides is not None:
            if not isinstance(raw_overrides, dict):
                raise ValueError(f"{context}: metadata_overrides must be an object.")
            overrides = {}
            for field, raw_override in raw_overrides.items():
                if field not in CLINICAL_METADATA_FIELDS:
                    raise ValueError(
                        f"{context}: unsupported metadata override {field!r}."
                    )
                if not isinstance(raw_override, dict):
                    raise ValueError(
                        f"{context}: override {field!r} must be an object."
                    )
                overrides[field] = ClinicalMetadataOverride.from_dict(
                    raw_override,
                    field=field,
                    context=context,
                )

        raw_custom = values.get("custom_attribute")
        custom_attribute: ClinicalCustomAttribute | None = None
        if raw_custom is not None:
            if not isinstance(raw_custom, dict):
                raise ValueError(
                    f"{context}: custom_attribute must be an object."
                )
            custom_attribute = ClinicalCustomAttribute.from_dict(
                raw_custom,
                context=f"{context} custom_attribute",
            )

        return cls(
            status=status,
            reason=_require_nonempty_string(
                values.get("reason"),
                field="reason",
                context=context,
            ),
            selected_column_header=_optional_string(
                values.get("selected_column_header"),
                field="selected_column_header",
                context=context,
            ),
            target_files=targets,
            custom_attribute=custom_attribute,
            metadata_overrides=overrides,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status,
            "reason": self.reason,
        }
        if self.selected_column_header is not None:
            result["selected_column_header"] = self.selected_column_header
        if self.target_files is not None:
            result["target_files"] = list(self.target_files)
        if self.custom_attribute is not None:
            result["custom_attribute"] = self.custom_attribute.to_dict()
        if self.metadata_overrides is not None:
            result["metadata_overrides"] = {
                field: override.to_dict()
                for field, override in self.metadata_overrides.items()
            }
        return result


@dataclass(frozen=True, slots=True)
class ClinicalMappingRecord:
    """Candidates and decision for one source query."""

    id: str
    source: ClinicalMappingSource
    search_query: str | None
    candidates: tuple[ClinicalMappingCandidate, ...]
    decision: ClinicalMappingDecision | None = None

    @classmethod
    def from_dict(
        cls,
        values: Mapping[str, Any],
        *,
        index: int,
    ) -> ClinicalMappingRecord:
        context = f"Mapping {values.get('id', index)!r}"
        raw_source = values.get("source", {})
        if not isinstance(raw_source, dict):
            raise ValueError(f"{context}: source must be an object.")
        raw_candidates = values.get("candidates", [])
        if not isinstance(raw_candidates, list) or not all(
            isinstance(candidate, dict) for candidate in raw_candidates
        ):
            raise ValueError(f"{context}: candidates must be a list of objects.")
        raw_decision = values.get("decision")
        if raw_decision is not None and not isinstance(raw_decision, dict):
            raise ValueError(f"{context}: decision must be an object or null.")
        return cls(
            id=_require_nonempty_string(
                values.get("id", f"query_{index}"),
                field="id",
                context=f"Mapping {index}",
            ),
            source=ClinicalMappingSource(
                file=_optional_string(
                    raw_source.get("file"),
                    field="file",
                    context=f"{context} source",
                ),
                sheet=_optional_string(
                    raw_source.get("sheet"),
                    field="sheet",
                    context=f"{context} source",
                ),
                column=_optional_string(
                    raw_source.get("column"),
                    field="column",
                    context=f"{context} source",
                ),
            ),
            search_query=_optional_string(
                values.get("search_query"),
                field="search_query",
                context=context,
            ),
            candidates=tuple(
                ClinicalMappingCandidate.from_dict(
                    candidate,
                    context=context,
                )
                for candidate in raw_candidates
            ),
            decision=(
                ClinicalMappingDecision.from_dict(
                    raw_decision,
                    context=context,
                )
                if raw_decision is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source.to_dict(),
            "search_query": self.search_query,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "decision": self.decision.to_dict() if self.decision is not None else None,
        }


@dataclass(frozen=True, slots=True)
class ClinicalMappingReport:
    """Versioned candidate and decision report."""

    study_id: str | None
    candidate_limit: int
    minimum_score: float
    mappings: tuple[ClinicalMappingRecord, ...]
    schema_version: int = REPORT_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> ClinicalMappingReport:
        schema_version = values.get("schema_version")
        if schema_version != REPORT_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported clinical dictionary report schema_version: "
                f"{schema_version!r}"
            )
        raw_mappings = values.get("mappings")
        if not isinstance(raw_mappings, list):
            raise ValueError("Clinical dictionary report requires a mappings list.")
        if not all(isinstance(mapping, dict) for mapping in raw_mappings):
            raise ValueError("Every clinical dictionary mapping must be an object.")
        study_id = values.get("study_id")
        if study_id is not None and not isinstance(study_id, str):
            raise ValueError("Clinical dictionary report study_id must be a string.")
        candidate_limit = values.get("candidate_limit", DEFAULT_LIMIT)
        minimum_score = values.get("minimum_score", DEFAULT_MINIMUM_SCORE)
        if not isinstance(candidate_limit, int):
            raise ValueError("Clinical dictionary report candidate_limit must be an integer.")
        if not isinstance(minimum_score, int | float):
            raise ValueError("Clinical dictionary report minimum_score must be numeric.")
        return cls(
            study_id=study_id,
            candidate_limit=candidate_limit,
            minimum_score=float(minimum_score),
            mappings=tuple(
                ClinicalMappingRecord.from_dict(mapping, index=index)
                for index, mapping in enumerate(raw_mappings, start=1)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "study_id": self.study_id,
            "query_count": len(self.mappings),
            "candidate_limit": self.candidate_limit,
            "minimum_score": self.minimum_score,
            "mappings": [mapping.to_dict() for mapping in self.mappings],
        }


def build_clinical_mapping_report(
    *,
    study_id: str | None,
    queries: Sequence[ClinicalMappingQuery],
    dictionary: list[ClinicalDictionaryAttribute],
    limit: int = DEFAULT_LIMIT,
    minimum_score: float = DEFAULT_MINIMUM_SCORE,
) -> ClinicalMappingReport:
    """Search all queries and return a report awaiting Hermes decisions."""
    if limit < 1:
        raise ValueError("--limit must be at least 1.")
    if not 0 <= minimum_score <= 1:
        raise ValueError("--minimum-score must be between 0 and 1.")
    query_ids = [query.id for query in queries]
    if len(query_ids) != len(set(query_ids)):
        raise ValueError("Clinical dictionary query ids must be unique.")

    mappings = []
    for query in queries:
        matches = search_clinical_dictionary(
            source_column_name=query.source_column,
            search_query=query.search_query,
            dictionary=dictionary,
            limit=limit,
            minimum_score=minimum_score,
        )
        mappings.append(
            ClinicalMappingRecord(
                id=query.id,
                source=ClinicalMappingSource(
                    file=query.source_file,
                    sheet=query.source_sheet,
                    column=query.source_column,
                ),
                search_query=query.search_query,
                candidates=tuple(
                    ClinicalMappingCandidate.from_match(match)
                    for match in matches
                ),
            )
        )
    return ClinicalMappingReport(
        study_id=study_id,
        candidate_limit=limit,
        minimum_score=minimum_score,
        mappings=tuple(mappings),
    )


@dataclass(frozen=True, slots=True)
class ClinicalAttributeMetadata:
    """The four cBioPortal metadata values for one clinical column."""

    display_name: str
    description: str
    datatype: str
    priority: str

    def to_dict(self) -> dict[str, str]:
        return {
            field: str(getattr(self, field))
            for field in CLINICAL_METADATA_FIELDS
        }


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


@dataclass(frozen=True, slots=True)
class ClinicalMappingValidationResult:
    """Deterministic comparison of mapping decisions and clinical headers."""

    valid: bool
    mapping_count: int
    decision_counts: Mapping[str, int]
    clinical_column_count: int
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "mapping_count": self.mapping_count,
            "decision_counts": dict(self.decision_counts),
            "clinical_column_count": self.clinical_column_count,
            "errors": list(self.errors),
        }


def _decision_targets(
    decision: ClinicalMappingDecision,
    *,
    default: str | None,
    context: str,
    errors: list[str],
) -> tuple[str, ...]:
    targets = decision.target_files
    if targets is None:
        targets = (default,) if default is not None else ()
    if not targets:
        errors.append(f"{context}: no target file was specified or inferred.")
    return targets


def _standard_metadata(
    attribute: ClinicalDictionaryAttribute,
    decision: ClinicalMappingDecision,
) -> dict[str, str]:
    expected = {
        field: str(getattr(attribute, field))
        for field in CLINICAL_METADATA_FIELDS
    }
    for field, override in (decision.metadata_overrides or {}).items():
        expected[field] = override.value
    return expected


def validate_clinical_mapping_report(
    report: ClinicalMappingReport,
    *,
    dictionary: Sequence[ClinicalDictionaryAttribute],
    clinical_headers: Mapping[ClinicalTarget, ClinicalHeader],
) -> ClinicalMappingValidationResult:
    """Validate decisions, placement, coverage, and canonical header metadata."""
    errors: list[str] = []
    dictionary_by_header = {
        attribute.column_header: attribute for attribute in dictionary
    }
    expected_outputs: dict[tuple[str, str], tuple[dict[str, str], str]] = {}
    decision_counts = {"standard": 0, "custom": 0, "excluded": 0}

    for index, mapping in enumerate(report.mappings, start=1):
        context = f"Mapping {mapping.id!r}" if mapping.id else f"Mapping {index}"
        decision = mapping.decision
        if decision is None:
            errors.append(f"{context}: decision has not been completed.")
            continue
        decision_counts[decision.status] += 1
        if decision.status == "excluded":
            continue

        if decision.status == "standard":
            selected_header = decision.selected_column_header
            if selected_header is None:
                errors.append(
                    f"{context}: standard decision requires selected_column_header."
                )
                continue
            attribute = dictionary_by_header.get(selected_header)
            if attribute is None:
                errors.append(
                    f"{context}: {selected_header!r} is not in the dictionary."
                )
                continue
            if selected_header not in {
                candidate.column_header for candidate in mapping.candidates
            }:
                errors.append(
                    f"{context}: selected attribute {selected_header!r} was not "
                    "among the recorded candidates."
                )

            default_target = attribute.attribute_type.lower()
            targets = _decision_targets(
                decision,
                default=default_target,
                context=context,
                errors=errors,
            )
            for target in targets:
                if target != default_target and not (
                    selected_header == "PATIENT_ID" and target == "sample"
                ):
                    errors.append(
                        f"{context}: dictionary attribute {selected_header!r} "
                        f"belongs in {default_target}, not {target}."
                    )
            metadata = _standard_metadata(attribute, decision)
            output_header = selected_header
        else:
            custom_attribute = decision.custom_attribute
            if custom_attribute is None:
                errors.append(
                    f"{context}: custom decision requires custom_attribute."
                )
                continue
            targets = _decision_targets(
                decision,
                default=None,
                context=context,
                errors=errors,
            )
            metadata = custom_attribute.metadata()
            output_header = custom_attribute.column_header

        for target in targets:
            output_key = (target, output_header)
            if output_key in expected_outputs:
                errors.append(
                    f"{context}: duplicate mapping for {target} column "
                    f"{output_header!r}."
                )
                continue
            expected_outputs[output_key] = (metadata, context)

    actual_outputs = {
        (target, header)
        for target, clinical_header in clinical_headers.items()
        for header in clinical_header.attributes
    }
    expected_output_keys = set(expected_outputs)
    for target, header in sorted(actual_outputs - expected_output_keys):
        errors.append(f"Clinical {target} column {header!r} has no mapping decision.")
    for target, header in sorted(expected_output_keys - actual_outputs):
        errors.append(
            f"Mapping decision expects missing clinical {target} column {header!r}."
        )

    for output_key in sorted(actual_outputs & expected_output_keys):
        target, header = output_key
        expected_metadata, context = expected_outputs[output_key]
        actual_metadata = clinical_headers[target].attributes[header].to_dict()
        for field in CLINICAL_METADATA_FIELDS:
            expected_value = expected_metadata.get(field)
            actual_value = actual_metadata.get(field)
            if expected_value != actual_value:
                errors.append(
                    f"{context}: {target} column {header!r} has {field} "
                    f"{actual_value!r}; expected {expected_value!r}."
                )

    return ClinicalMappingValidationResult(
        valid=not errors,
        mapping_count=len(report.mappings),
        decision_counts=decision_counts,
        clinical_column_count=len(actual_outputs),
        errors=tuple(errors),
    )


__all__ = [
    "CLINICAL_METADATA_FIELDS",
    "REPORT_SCHEMA_VERSION",
    "ClinicalAttributeMetadata",
    "ClinicalCustomAttribute",
    "ClinicalHeader",
    "ClinicalMappingCandidate",
    "ClinicalMappingDecision",
    "ClinicalMappingQuery",
    "ClinicalMappingRecord",
    "ClinicalMappingReport",
    "ClinicalMappingSource",
    "ClinicalMappingValidationResult",
    "ClinicalMetadataOverride",
    "build_clinical_mapping_report",
    "parse_clinical_mapping_queries",
    "read_clinical_header",
    "validate_clinical_mapping_report",
]
