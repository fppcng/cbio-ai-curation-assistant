"""Command-line adapter for package-owned clinical dictionary search."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from cbio_curation_assistant.cbioportal.clinical_dictionary import (
    DEFAULT_LIMIT,
    DEFAULT_MINIMUM_SCORE,
    ClinicalDictionaryMatch,
    load_clinical_dictionary,
    load_default_clinical_dictionary,
    search_clinical_dictionary,
)
from cbio_curation_assistant.command_result import (
    command_result,
    emit_command_result,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbio-curation clinical-dictionary",
        description=(
            "Search the packaged Clinical Data Dictionary for possible standard "
            "cBioPortal clinical attributes. This tool returns candidates only "
            "and does not decide the mapping."
        ),
    )
    parser.add_argument(
        "-s",
        "--source-column",
        required=True,
        help="Original column name from the source data.",
    )
    parser.add_argument(
        "-c",
        "--considered-column",
        required=True,
        help="Column name Codex is considering using.",
    )
    parser.add_argument(
        "-d",
        "--dictionary",
        type=Path,
        help="Optional path to a custom Clinical Data Dictionary JSON file.",
    )
    parser.add_argument(
        "-l",
        "--limit",
        default=DEFAULT_LIMIT,
        type=int,
        help="Maximum number of candidates to return.",
    )
    parser.add_argument(
        "-m",
        "--minimum-score",
        default=DEFAULT_MINIMUM_SCORE,
        type=float,
        help="Minimum similarity score for returned candidates.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print candidates as JSON instead of a readable text report.",
    )
    return parser


def _print_text_report(
    original_column_name: str,
    considered_column_name: str,
    matches: list[ClinicalDictionaryMatch],
) -> None:
    print("Clinical Data Dictionary candidate search")
    print("========================================")
    print(f"Source column: {original_column_name}")
    print(f"Considered column: {considered_column_name}")
    print()

    if not matches:
        print("No candidates found above the minimum score.")
        return

    for index, match in enumerate(matches, start=1):
        attribute = match.attribute
        print(f"{index}. {attribute.column_header} (score={match.score})")
        print(f"   Display name: {attribute.display_name}")
        print(f"   Description: {attribute.description}")
        print(f"   Datatype: {attribute.datatype}")
        print(f"   Attribute type: {attribute.attribute_type}")
        print(f"   Priority: {attribute.priority}")


def run_clinical_dictionary_command(argv: Sequence[str]) -> int:
    """Run the direct package command while preserving its CLI contract."""
    args = _build_parser().parse_args(argv)
    dictionary = (
        load_clinical_dictionary(args.dictionary)
        if args.dictionary is not None
        else load_default_clinical_dictionary()
    )
    matches = search_clinical_dictionary(
        original_column_name=args.source_column,
        considered_column_name=args.considered_column,
        dictionary=dictionary,
        limit=args.limit,
        minimum_score=args.minimum_score,
    )

    if args.json:
        emit_command_result(
            command_result(
                "clinical-dictionary",
                status="success",
                result=matches,
            )
        )
    else:
        _print_text_report(
            args.source_column,
            args.considered_column,
            matches,
        )
    return 0


__all__ = ["run_clinical_dictionary_command"]
