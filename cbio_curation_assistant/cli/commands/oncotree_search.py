"""Command adapter for package-owned OncoTree search."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from cbio_curation_assistant.cbioportal.oncotree import (
    DEFAULT_LIMIT,
    OncotreeSearchResult,
    inspect_clinical_sample,
    load_default_oncotree_candidates,
    load_oncotree_candidates,
    search_oncotree,
)
from cbio_curation_assistant.cli.renderers.oncotree import (
    print_clinical_report,
    print_query_report,
)
from cbio_curation_assistant.cli.result import (
    CommandOutcome,
    EXIT_SUCCESS,
    command_result,
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


def run(argv: Sequence[str]) -> CommandOutcome:
    """Run the package command while preserving its public output contract."""
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
        return command_result(
            "oncotree-search",
            status="success",
            result=result,
        )
    if args.query and query_results is not None:
        print_query_report(args.query, query_results)
        if clinical_inspection is not None:
            print()
    if clinical_inspection is not None:
        print_clinical_report(clinical_inspection)
    return EXIT_SUCCESS


__all__ = ["run"]
