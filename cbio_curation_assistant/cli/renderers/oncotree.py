"""Human-readable rendering for OncoTree commands."""

from __future__ import annotations

from cbio_curation_assistant.cbioportal.oncotree import (
    ClinicalOncotreeInspection,
    OncotreeMatch,
)


def print_query_report(query: str, matches: tuple[OncotreeMatch, ...]) -> None:
    print("OncoTree candidate search")
    print("=========================")
    print(f"Query: {query}")
    print()
    if not matches:
        print("No candidates found above the minimum score.")
        return
    for index, match in enumerate(matches, start=1):
        candidate = match.candidate
        print(
            f"{index}. {candidate.oncotree_code} "
            f"({match.score}) - {candidate.cancer_type_detailed}"
        )
        print(f"   CANCER_TYPE: {candidate.cancer_type}")
        print(f"   CANCER_TYPE_DETAILED: {candidate.cancer_type_detailed}")
        print(f"   Tissue: {candidate.tissue}")
        print(f"   Path: {' > '.join(candidate.path)}")


def print_clinical_report(inspection: ClinicalOncotreeInspection) -> None:
    print("Clinical sample OncoTree inspection")
    print("===================================")
    print(f"Clinical file: {inspection.clinical_file}")
    print(f"Rows: {inspection.row_count}")
    print(
        "Missing standard columns: "
        f"{', '.join(inspection.missing_standard_columns) or 'none'}"
    )
    print(
        "Available search columns: "
        f"{', '.join(inspection.available_search_columns) or 'none'}"
    )
    print()
    if not inspection.suggestions:
        print("No source values were available for OncoTree suggestions.")
        return
    for suggestion in inspection.suggestions:
        print(f"{suggestion.source_column}={suggestion.source_value}")
        if not suggestion.matches:
            print("   No confident matches.")
            continue
        for match in suggestion.matches:
            candidate = match.candidate
            print(
                f"   {candidate.oncotree_code} ({match.score}) - "
                f"{candidate.cancer_type} / {candidate.cancer_type_detailed}"
            )


__all__ = ["print_clinical_report", "print_query_report"]
