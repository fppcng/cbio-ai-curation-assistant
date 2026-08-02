"""Parse Clinical Data Dictionary mapping queries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cbio_curation_assistant.cbioportal.clinical_mapping.parsing import (
    optional_string,
    require_nonempty_string,
)


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
            id=require_nonempty_string(
                values.get("id", f"query_{index}"),
                field="id",
                context=context,
            ),
            source_column=require_nonempty_string(
                values.get("source_column"),
                field="source_column",
                context=context,
            ),
            search_query=optional_string(
                values.get("search_query"),
                field="search_query",
                context=context,
            ),
            source_file=optional_string(
                values.get("source_file"),
                field="source_file",
                context=context,
            ),
            source_sheet=optional_string(
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


__all__ = ["ClinicalMappingQuery", "parse_clinical_mapping_queries"]
