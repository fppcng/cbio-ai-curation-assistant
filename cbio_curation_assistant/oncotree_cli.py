"""Command-line adapter for package-owned OncoTree search."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from cbio_curation_assistant.cbioportal.oncotree import (
    DEFAULT_LIMIT,
    ClinicalOncotreeInspection,
    OncotreeMatch,
    OncotreeSearchResult,
    inspect_clinical_sample,
    load_default_oncotree_candidates,
    load_oncotree_candidates,
    search_oncotree,
)
from cbio_curation_assistant.command_result import (
    command_result,
    emit_command_result,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbio-curation oncotree-search",
        description=(
            "Search the packaged OncoTree snapshot for candidates used to define "
            "ONCOTREE_CODE, CANCER_TYPE, and CANCER_TYPE_DETAILED."
        ),
    )
    parser.add_argument(
        "-q",
        "--query",
        help="Cancer type, histology, tissue, or OncoTree code to search.",
    )
    parser.add_argument(
        "-c",
        "--clinical-file",
        type=Path,
        help="Optional data_clinical_sample.txt file to inspect.",
    )
    parser.add_argument(
        "-o",
        "--oncotree-table",
        type=Path,
        help="Optional custom OncoTree hierarchy table.",
    )
    parser.add_argument(
        "-l",
        "--limit",
        default=DEFAULT_LIMIT,
        type=int,
        help="Maximum number of candidates or example values to return.",
    )
    parser.add_argument(
        "-m",
        "--minimum-score",
        default=0.25,
        type=float,
        help="Minimum similarity score for direct query results.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print output as JSON instead of a readable text report.",
    )
    return parser


def _print_query_report(query: str, matches: tuple[OncotreeMatch, ...]) -> None:
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


def _print_clinical_report(inspection: ClinicalOncotreeInspection) -> None:
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


def run_oncotree_search_command(argv: Sequence[str]) -> int:
    """Run the direct package command while preserving its public contract."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.query and not args.clinical_file:
        parser.error("Provide --query, --clinical-file, or both.")

    candidates = (
        load_oncotree_candidates(args.oncotree_table)
        if args.oncotree_table is not None
        else load_default_oncotree_candidates()
    )
    query_results = (
        tuple(
            search_oncotree(
                query=args.query,
                candidates=candidates,
                limit=args.limit,
                minimum_score=args.minimum_score,
            )
        )
        if args.query
        else None
    )
    clinical_inspection = (
        inspect_clinical_sample(
            clinical_file=args.clinical_file,
            candidates=candidates,
            limit=args.limit,
        )
        if args.clinical_file
        else None
    )
    result = OncotreeSearchResult(
        query_results=query_results,
        clinical_inspection=clinical_inspection,
    )

    if args.json:
        emit_command_result(
            command_result(
                "oncotree-search",
                status="success",
                result=result,
            )
        )
        return 0

    if args.query and query_results is not None:
        _print_query_report(args.query, query_results)
        if clinical_inspection is not None:
            print()
    if clinical_inspection is not None:
        _print_clinical_report(clinical_inspection)
    return 0


__all__ = ["run_oncotree_search_command"]
