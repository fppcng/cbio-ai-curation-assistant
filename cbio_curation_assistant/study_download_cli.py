"""Command-line adapter for the package-owned study-download workflow."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from cbio_curation_assistant.command_result import (
    command_error,
    command_result,
    emit_command_result,
    exit_code_for_status,
)
from cbio_curation_assistant.integrations.pmc import (
    PMCRequestError,
    format_pmc_error,
)
from cbio_curation_assistant.workflows.study_download import run_study_download


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbio-curation study-download",
        description=(
            "Download article XML/PDF and supplementary files from PMC into "
            "the canonical study source workspace resolved from "
            "$CBIO_CURATION_ASSISTANT_HOME."
        ),
    )
    parser.add_argument(
        "--identifier",
        required=True,
        help=(
            "User-supplied publication identifier value, for example "
            "8432745 or PMC8432745."
        ),
    )
    parser.add_argument(
        "--identifier-type",
        required=True,
        choices=["pmid", "pmcid"],
        help="Interpret --identifier explicitly as a PMID or PMCID.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser


def run_study_download_command(argv: Sequence[str]) -> int:
    """Parse CLI arguments, invoke the workflow, and emit its result envelope."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        result = run_study_download(
            identifier=args.identifier,
            identifier_type=args.identifier_type,
        )
    except PMCRequestError as exc:
        emit_command_result(command_error("study-download", format_pmc_error(exc)))
        return 1
    except Exception as exc:
        emit_command_result(command_error("study-download", exc))
        return 1

    response = command_result(
        "study-download",
        status=result.status,
        result=result,
        warnings=result.warnings,
    )
    emit_command_result(response)
    return exit_code_for_status(response.status)


__all__ = ["run_study_download_command"]
