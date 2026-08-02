"""Typed Clinical Data Dictionary mapping reports and decisions."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from cbio_curation_assistant.cbioportal.clinical_dictionary import (
    DEFAULT_LIMIT,
    DEFAULT_MINIMUM_SCORE,
    ClinicalDictionaryMatch,
)
from cbio_curation_assistant.cbioportal.clinical_mapping.parsing import (
    optional_string,
    require_nonempty_string,
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
VALID_DECISION_STATUSES: frozenset[str] = frozenset(("standard", "custom", "excluded"))


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
            column_header=require_nonempty_string(
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
            raise ValueError(f"{context} override {field!r} value must be a string.")
        return cls(
            value=value,
            reason=require_nonempty_string(
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
            column_header=require_nonempty_string(
                values.get("column_header"),
                field="column_header",
                context=context,
            ),
            display_name=require_nonempty_string(
                values.get("display_name"),
                field="display_name",
                context=context,
            ),
            description=require_nonempty_string(
                values.get("description"),
                field="description",
                context=context,
            ),
            datatype=require_nonempty_string(
                values.get("datatype"),
                field="datatype",
                context=context,
            ),
            priority=require_nonempty_string(
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
        return {field: str(getattr(self, field)) for field in CLINICAL_METADATA_FIELDS}

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
                    f"{context}: invalid target files: {', '.join(invalid_targets)}."
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
                raise ValueError(f"{context}: custom_attribute must be an object.")
            custom_attribute = ClinicalCustomAttribute.from_dict(
                raw_custom,
                context=f"{context} custom_attribute",
            )

        return cls(
            status=status,
            reason=require_nonempty_string(
                values.get("reason"),
                field="reason",
                context=context,
            ),
            selected_column_header=optional_string(
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
            id=require_nonempty_string(
                values.get("id", f"query_{index}"),
                field="id",
                context=f"Mapping {index}",
            ),
            source=ClinicalMappingSource(
                file=optional_string(
                    raw_source.get("file"),
                    field="file",
                    context=f"{context} source",
                ),
                sheet=optional_string(
                    raw_source.get("sheet"),
                    field="sheet",
                    context=f"{context} source",
                ),
                column=optional_string(
                    raw_source.get("column"),
                    field="column",
                    context=f"{context} source",
                ),
            ),
            search_query=optional_string(
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
            raise ValueError(
                "Clinical dictionary report candidate_limit must be an integer."
            )
        if not isinstance(minimum_score, int | float):
            raise ValueError(
                "Clinical dictionary report minimum_score must be numeric."
            )
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


__all__ = [
    "CLINICAL_METADATA_FIELDS",
    "REPORT_SCHEMA_VERSION",
    "ClinicalCustomAttribute",
    "ClinicalMappingCandidate",
    "ClinicalMappingDecision",
    "ClinicalMappingRecord",
    "ClinicalMappingReport",
    "ClinicalMappingSource",
    "ClinicalMetadataOverride",
]
