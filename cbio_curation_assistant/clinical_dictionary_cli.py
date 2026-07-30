"""Command-line adapter for Clinical Data Dictionary search and validation."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from cbio_curation_assistant.cbioportal.clinical_dictionary import (
    DEFAULT_LIMIT,
    DEFAULT_MINIMUM_SCORE,
    ClinicalDictionaryAttribute,
    load_clinical_dictionary,
    load_default_clinical_dictionary,
    search_clinical_dictionary,
)
from cbio_curation_assistant.command_result import (
    EXIT_ERROR,
    EXIT_SUCCESS,
    command_result,
    emit_command_result,
)


REPORT_SCHEMA_VERSION = 1
VALID_TARGET_FILES = frozenset(("patient", "sample"))
CLINICAL_METADATA_FIELDS = (
    "display_name",
    "description",
    "datatype",
    "priority",
)
VALID_DATATYPES = frozenset(("STRING", "NUMBER", "BOOLEAN"))
CUSTOM_HEADER_PATTERN = re.compile(r"^[A-Z0-9_]+$")


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
        description="Search and validate mappings against the Clinical Data Dictionary.",
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


def _require_nonempty_string(
    value: Any,
    *,
    field: str,
    context: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} requires non-empty string field {field!r}.")
    return value.strip()


def _load_batch_queries(input_path: Path) -> tuple[str | None, list[dict[str, Any]]]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Clinical dictionary batch input must be a JSON object.")
    queries = payload.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError(
            "Clinical dictionary batch input requires a non-empty queries list."
        )
    if not all(isinstance(query, dict) for query in queries):
        raise ValueError("Every clinical dictionary query must be a JSON object.")
    study_id = payload.get("study_id")
    if study_id is not None and not isinstance(study_id, str):
        raise ValueError("Batch input study_id must be a string when provided.")
    return study_id, queries


def _single_query(args: argparse.Namespace) -> tuple[str | None, list[dict[str, Any]]]:
    return None, [
        {
            "id": "query_1",
            "source_file": args.source_file,
            "source_sheet": args.source_sheet,
            "source_column": args.source_column,
            "search_query": args.search_query,
        }
    ]


def _build_mapping_record(
    query: Mapping[str, Any],
    *,
    index: int,
    dictionary: list[ClinicalDictionaryAttribute],
    limit: int,
    minimum_score: float,
) -> dict[str, Any]:
    context = f"Query {index}"
    source_column = _require_nonempty_string(
        query.get("source_column"),
        field="source_column",
        context=context,
    )
    search_query_value = query.get("search_query")
    if search_query_value is not None and not isinstance(search_query_value, str):
        raise ValueError(f"{context} search_query must be a string when provided.")
    search_query = search_query_value.strip() if search_query_value else None

    query_id = query.get("id", f"query_{index}")
    query_id = _require_nonempty_string(query_id, field="id", context=context)
    matches = search_clinical_dictionary(
        source_column_name=source_column,
        search_query=search_query,
        dictionary=dictionary,
        limit=limit,
        minimum_score=minimum_score,
    )
    return {
        "id": query_id,
        "source": {
            "file": query.get("source_file"),
            "sheet": query.get("source_sheet"),
            "column": source_column,
        },
        "search_query": search_query,
        "candidates": [match.to_dict() for match in matches],
        "decision": None,
    }


def _build_search_report(
    *,
    study_id: str | None,
    queries: list[dict[str, Any]],
    dictionary: list[ClinicalDictionaryAttribute],
    limit: int,
    minimum_score: float,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("--limit must be at least 1.")
    if not 0 <= minimum_score <= 1:
        raise ValueError("--minimum-score must be between 0 and 1.")

    mappings = [
        _build_mapping_record(
            query,
            index=index,
            dictionary=dictionary,
            limit=limit,
            minimum_score=minimum_score,
        )
        for index, query in enumerate(queries, start=1)
    ]
    mapping_ids = [mapping["id"] for mapping in mappings]
    if len(mapping_ids) != len(set(mapping_ids)):
        raise ValueError("Clinical dictionary query ids must be unique.")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "study_id": study_id,
        "query_count": len(mappings),
        "candidate_limit": limit,
        "minimum_score": minimum_score,
        "mappings": mappings,
    }


def _write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _print_search_report(report: Mapping[str, Any], output_path: Path | None) -> None:
    print(f"Clinical dictionary queries: {report['query_count']}")
    if output_path is not None:
        print(f"Mapping report: {output_path.resolve()}")
    for mapping in report["mappings"]:
        print()
        print(f"{mapping['id']}: {mapping['source']['column']}")
        for index, candidate in enumerate(mapping["candidates"], start=1):
            print(
                f"  {index}. {candidate['column_header']} "
                f"(score={candidate['score']}, "
                f"type={candidate['attribute_type']})"
            )


def _run_search(args: argparse.Namespace) -> int:
    dictionary = _load_dictionary(args.dictionary)
    study_id, queries = (
        _load_batch_queries(args.input)
        if args.input is not None
        else _single_query(args)
    )
    report = _build_search_report(
        study_id=study_id,
        queries=queries,
        dictionary=dictionary,
        limit=args.limit,
        minimum_score=args.minimum_score,
    )
    if args.output is not None:
        _write_report(args.output, report)

    result = {
        "report_path": str(args.output.resolve()) if args.output is not None else None,
        "report": report,
    }
    if args.json:
        emit_command_result(
            command_result(
                "clinical-dictionary.search",
                status="success",
                result=result,
            )
        )
    else:
        _print_search_report(report, args.output)
    return EXIT_SUCCESS


def _read_clinical_header(path: Path) -> dict[str, dict[str, str]]:
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

    return {
        header: {
            field: metadata_rows[index][column_index]
            for index, field in enumerate(CLINICAL_METADATA_FIELDS)
        }
        for column_index, header in enumerate(headers)
    }


def _decision_target_files(
    decision: Mapping[str, Any],
    *,
    default: str | None,
    context: str,
    errors: list[str],
) -> list[str]:
    raw_targets = decision.get("target_files")
    if raw_targets is None:
        targets = [default] if default is not None else []
    elif isinstance(raw_targets, list) and all(
        isinstance(target, str) for target in raw_targets
    ):
        targets = list(dict.fromkeys(raw_targets))
    else:
        errors.append(f"{context}: target_files must be a list of strings.")
        return []

    if not targets:
        errors.append(f"{context}: no target file was specified or inferred.")
    invalid_targets = sorted(set(targets) - VALID_TARGET_FILES)
    if invalid_targets:
        errors.append(f"{context}: invalid target files: {', '.join(invalid_targets)}.")
    return [target for target in targets if target in VALID_TARGET_FILES]


def _expected_standard_metadata(
    attribute: ClinicalDictionaryAttribute,
    decision: Mapping[str, Any],
    *,
    context: str,
    errors: list[str],
) -> dict[str, str]:
    expected = {
        field: str(getattr(attribute, field)) for field in CLINICAL_METADATA_FIELDS
    }
    overrides = decision.get("metadata_overrides", {})
    if not isinstance(overrides, dict):
        errors.append(f"{context}: metadata_overrides must be an object.")
        return expected

    for field, override in overrides.items():
        if field not in CLINICAL_METADATA_FIELDS:
            errors.append(f"{context}: unsupported metadata override {field!r}.")
            continue
        if not isinstance(override, dict):
            errors.append(f"{context}: override {field!r} must be an object.")
            continue
        value = override.get("value")
        reason = override.get("reason")
        if (
            not isinstance(value, str)
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            errors.append(
                f"{context}: override {field!r} requires string value and reason."
            )
            continue
        expected[field] = value
    return expected


def _custom_attribute(
    decision: Mapping[str, Any],
    *,
    context: str,
    errors: list[str],
) -> tuple[str | None, dict[str, str]]:
    attribute = decision.get("custom_attribute")
    if not isinstance(attribute, dict):
        errors.append(f"{context}: custom decision requires custom_attribute.")
        return None, {}

    rendered: dict[str, str] = {}
    for field in ("column_header", *CLINICAL_METADATA_FIELDS):
        value = attribute.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{context}: custom_attribute requires non-empty {field!r}.")
            continue
        rendered[field] = value.strip()

    header = rendered.get("column_header")
    if header is not None and CUSTOM_HEADER_PATTERN.fullmatch(header) is None:
        errors.append(
            f"{context}: custom column_header must contain only A-Z, 0-9, and '_'."
        )
    datatype = rendered.get("datatype")
    if datatype is not None and datatype not in VALID_DATATYPES:
        errors.append(
            f"{context}: custom datatype must be one of "
            f"{', '.join(sorted(VALID_DATATYPES))}."
        )
    return header, {
        field: rendered[field]
        for field in CLINICAL_METADATA_FIELDS
        if field in rendered
    }


def _validate_mapping_report(
    report: Mapping[str, Any],
    *,
    dictionary: list[ClinicalDictionaryAttribute],
    clinical_headers: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> dict[str, Any]:
    errors: list[str] = []
    mappings = report.get("mappings")
    if not isinstance(mappings, list):
        raise ValueError("Clinical dictionary report requires a mappings list.")

    dictionary_by_header = {
        attribute.column_header: attribute for attribute in dictionary
    }
    expected_outputs: dict[tuple[str, str], tuple[dict[str, str], str]] = {}
    decision_counts = {"standard": 0, "custom": 0, "excluded": 0}

    for index, mapping in enumerate(mappings, start=1):
        context = f"Mapping {index}"
        if not isinstance(mapping, dict):
            errors.append(f"{context}: mapping must be an object.")
            continue
        mapping_id = mapping.get("id")
        if isinstance(mapping_id, str) and mapping_id.strip():
            context = f"Mapping {mapping_id!r}"

        decision = mapping.get("decision")
        if not isinstance(decision, dict):
            errors.append(f"{context}: decision has not been completed.")
            continue
        status = decision.get("status")
        if status not in decision_counts:
            errors.append(f"{context}: status must be standard, custom, or excluded.")
            continue
        decision_counts[status] += 1
        reason = decision.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{context}: decision requires a non-empty reason.")

        if status == "excluded":
            continue

        if status == "standard":
            selected_header = decision.get("selected_column_header")
            if not isinstance(selected_header, str) or not selected_header:
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
            candidates = mapping.get("candidates")
            candidate_headers = (
                {
                    candidate.get("column_header")
                    for candidate in candidates
                    if isinstance(candidate, dict)
                }
                if isinstance(candidates, list)
                else set()
            )
            if selected_header not in candidate_headers:
                errors.append(
                    f"{context}: selected attribute {selected_header!r} was not "
                    "among the recorded candidates."
                )

            default_target = attribute.attribute_type.lower()
            targets = _decision_target_files(
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
            metadata = _expected_standard_metadata(
                attribute,
                decision,
                context=context,
                errors=errors,
            )
            output_header = selected_header
        else:
            output_header, metadata = _custom_attribute(
                decision,
                context=context,
                errors=errors,
            )
            targets = _decision_target_files(
                decision,
                default=None,
                context=context,
                errors=errors,
            )
            if output_header is None:
                continue

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
        for target, headers in clinical_headers.items()
        for header in headers
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
        actual_metadata = clinical_headers[target][header]
        for field in CLINICAL_METADATA_FIELDS:
            expected_value = expected_metadata.get(field)
            actual_value = actual_metadata.get(field)
            if expected_value != actual_value:
                errors.append(
                    f"{context}: {target} column {header!r} has {field} "
                    f"{actual_value!r}; expected {expected_value!r}."
                )

    return {
        "valid": not errors,
        "mapping_count": len(mappings),
        "decision_counts": decision_counts,
        "clinical_column_count": len(actual_outputs),
        "errors": errors,
    }


def _print_validation_result(result: Mapping[str, Any]) -> None:
    print(f"Clinical dictionary mapping valid: {result['valid']}")
    print(f"Mappings: {result['mapping_count']}")
    print(f"Clinical columns: {result['clinical_column_count']}")
    for error in result["errors"]:
        print(f"- {error}")


def _run_validate(args: argparse.Namespace) -> int:
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("Clinical dictionary mapping report must be a JSON object.")
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported clinical dictionary report schema_version: "
            f"{report.get('schema_version')!r}"
        )

    clinical_headers: dict[str, Mapping[str, Mapping[str, str]]] = {
        "sample": _read_clinical_header(args.sample_file),
    }
    if args.patient_file is not None:
        clinical_headers["patient"] = _read_clinical_header(args.patient_file)

    result = _validate_mapping_report(
        report,
        dictionary=_load_dictionary(args.dictionary),
        clinical_headers=clinical_headers,
    )
    if args.json:
        status = "success" if result["valid"] else "error"
        emit_command_result(
            command_result(
                "clinical-dictionary.validate",
                status=status,
                result=result,
                error=(
                    None
                    if result["valid"]
                    else {
                        "type": "ClinicalDictionaryValidationError",
                        "message": "Clinical dictionary mapping validation failed.",
                    }
                ),
            )
        )
    else:
        _print_validation_result(result)
    return EXIT_SUCCESS if result["valid"] else EXIT_ERROR


def run_clinical_dictionary_command(argv: Sequence[str]) -> int:
    """Dispatch Clinical Data Dictionary search and validation."""
    args = _build_parser().parse_args(argv)
    if args.clinical_dictionary_command == "search":
        return _run_search(args)
    if args.clinical_dictionary_command == "validate":
        return _run_validate(args)
    raise ValueError(
        f"Unsupported clinical dictionary command: {args.clinical_dictionary_command}"
    )


__all__ = ["run_clinical_dictionary_command"]
