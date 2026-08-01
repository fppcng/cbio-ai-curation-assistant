"""Command adapter for Clinical Data Dictionary search and validation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from cbio_curation_assistant.cbioportal.clinical_dictionary import (
    DEFAULT_LIMIT,
    DEFAULT_MINIMUM_SCORE,
    ClinicalDictionaryAttribute,
    load_clinical_dictionary,
    load_default_clinical_dictionary,
)
from cbio_curation_assistant.cbioportal.clinical_mapping import (
    ClinicalMappingQuery,
    ClinicalMappingReport,
    build_clinical_mapping_report,
    parse_clinical_mapping_queries,
    read_clinical_header,
    validate_clinical_mapping_report,
)
from cbio_curation_assistant.cli.json_io import load_json_object, write_json_object
from cbio_curation_assistant.cli.renderers.clinical_dictionary import (
    print_search_report,
    print_validation_result,
)
from cbio_curation_assistant.cli.result import (
    CommandOutcome,
    EXIT_ERROR,
    EXIT_SUCCESS,
    command_result,
)


def _add_dictionary_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-d",
        "--dictionary",
        type=Path,
        help="Optional path to a custom Clinical Data Dictionary JSON file.",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbio-curation clinical-dictionary",
        description=(
            "Search and validate mappings against the Clinical Data Dictionary."
        ),
    )
    subparsers = parser.add_subparsers(
        dest="clinical_dictionary_command",
        required=True,
    )

    search_parser = subparsers.add_parser(
        "search",
        description=(
            "Return neutral dictionary candidates for source clinical columns. "
            "The optional search query must describe source meaning, not a "
            "preselected cBioPortal header."
        ),
    )
    search_input = search_parser.add_mutually_exclusive_group(required=True)
    search_input.add_argument(
        "-s",
        "--source-column",
        help="Original column name from the source data.",
    )
    search_input.add_argument(
        "-i",
        "--input",
        type=Path,
        help="JSON file containing a queries list for batch search.",
    )
    search_parser.add_argument(
        "-q",
        "--search-query",
        help="Optional source-derived reformulation used to improve retrieval.",
    )
    search_parser.add_argument(
        "--source-file",
        help="Optional source filename recorded in a single-query report.",
    )
    search_parser.add_argument(
        "--source-sheet",
        help="Optional source sheet recorded in a single-query report.",
    )
    search_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional path where the bare mapping report is written.",
    )
    search_parser.add_argument(
        "-l",
        "--limit",
        default=DEFAULT_LIMIT,
        type=int,
        help="Maximum number of candidates per source column.",
    )
    search_parser.add_argument(
        "-m",
        "--minimum-score",
        default=DEFAULT_MINIMUM_SCORE,
        type=float,
        help="Minimum ranking score for returned candidates.",
    )
    search_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the mapping report in the shared JSON envelope.",
    )
    _add_dictionary_argument(search_parser)

    validate_parser = subparsers.add_parser(
        "validate",
        description=(
            "Validate mapping decisions and canonical metadata against generated "
            "clinical files."
        ),
    )
    validate_parser.add_argument("--report", required=True, type=Path)
    validate_parser.add_argument("--sample-file", required=True, type=Path)
    validate_parser.add_argument("--patient-file", type=Path)
    validate_parser.add_argument(
        "--json",
        action="store_true",
        help="Print validation results in the shared JSON envelope.",
    )
    _add_dictionary_argument(validate_parser)
    return parser


def _load_dictionary(
    dictionary_path: Path | None,
) -> list[ClinicalDictionaryAttribute]:
    return (
        load_clinical_dictionary(dictionary_path)
        if dictionary_path is not None
        else load_default_clinical_dictionary()
    )


def _load_batch_queries(
    input_path: Path,
) -> tuple[str | None, tuple[ClinicalMappingQuery, ...]]:
    payload = load_json_object(
        input_path,
        description="Clinical dictionary batch input",
    )
    return parse_clinical_mapping_queries(payload)


def _single_query(
    args: argparse.Namespace,
) -> tuple[None, tuple[ClinicalMappingQuery, ...]]:
    return None, (
        ClinicalMappingQuery(
            id="query_1",
            source_file=args.source_file,
            source_sheet=args.source_sheet,
            source_column=args.source_column,
            search_query=args.search_query,
        ),
    )


def _run_search(args: argparse.Namespace) -> CommandOutcome:
    study_id, queries = (
        _load_batch_queries(args.input)
        if args.input is not None
        else _single_query(args)
    )
    report = build_clinical_mapping_report(
        study_id=study_id,
        queries=queries,
        dictionary=_load_dictionary(args.dictionary),
        limit=args.limit,
        minimum_score=args.minimum_score,
    )
    if args.output is not None:
        write_json_object(args.output, report.to_dict())

    if args.json:
        return command_result(
            "clinical-dictionary.search",
            status="success",
            result={
                "report_path": (
                    str(args.output.resolve()) if args.output is not None else None
                ),
                "report": report,
            },
        )
    print_search_report(report, args.output)
    return EXIT_SUCCESS


def _run_validate(args: argparse.Namespace) -> CommandOutcome:
    report = ClinicalMappingReport.from_dict(
        load_json_object(
            args.report,
            description="Clinical dictionary mapping report",
        )
    )
    clinical_headers = {"sample": read_clinical_header(args.sample_file)}
    if args.patient_file is not None:
        clinical_headers["patient"] = read_clinical_header(args.patient_file)

    result = validate_clinical_mapping_report(
        report,
        dictionary=_load_dictionary(args.dictionary),
        clinical_headers=clinical_headers,
    )
    if args.json:
        return command_result(
            "clinical-dictionary.validate",
            status="success" if result.valid else "error",
            result=result,
            error=(
                None
                if result.valid
                else {
                    "type": "ClinicalDictionaryValidationError",
                    "message": "Clinical dictionary mapping validation failed.",
                }
            ),
        )
    print_validation_result(result)
    return EXIT_SUCCESS if result.valid else EXIT_ERROR


def run(argv: Sequence[str]) -> CommandOutcome:
    """Dispatch Clinical Data Dictionary search and validation."""
    args = _build_parser().parse_args(argv)
    if args.clinical_dictionary_command == "search":
        return _run_search(args)
    if args.clinical_dictionary_command == "validate":
        return _run_validate(args)
    raise ValueError(
        f"Unsupported clinical dictionary command: {args.clinical_dictionary_command}"
    )


__all__ = ["run"]
