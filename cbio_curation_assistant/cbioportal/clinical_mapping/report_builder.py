"""Build auditable Clinical Data Dictionary mapping reports."""

from __future__ import annotations

from collections.abc import Sequence

from cbio_curation_assistant.cbioportal.clinical_dictionary import (
    DEFAULT_LIMIT,
    DEFAULT_MINIMUM_SCORE,
    ClinicalDictionaryAttribute,
    search_clinical_dictionary,
)
from cbio_curation_assistant.cbioportal.clinical_mapping.models import (
    ClinicalMappingCandidate,
    ClinicalMappingRecord,
    ClinicalMappingReport,
    ClinicalMappingSource,
)
from cbio_curation_assistant.cbioportal.clinical_mapping.queries import (
    ClinicalMappingQuery,
)


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
                    ClinicalMappingCandidate.from_match(match) for match in matches
                ),
            )
        )
    return ClinicalMappingReport(
        study_id=study_id,
        candidate_limit=limit,
        minimum_score=minimum_score,
        mappings=tuple(mappings),
    )


__all__ = ["build_clinical_mapping_report"]
