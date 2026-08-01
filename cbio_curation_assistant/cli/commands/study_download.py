"""Command adapter for the package-owned study-download workflow."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from cbio_curation_assistant.cli.result import CommandResult, command_result
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


def run(argv: Sequence[str]) -> CommandResult[object]:
    """Parse arguments and return the workflow result without emitting it."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )
    result = run_study_download(
        identifier=args.identifier,
        identifier_type=args.identifier_type,
    )
    return command_result(
        "study-download",
        status=result.status,
        result=result,
        warnings=result.warnings,
    )


def normalize_error(error: Exception) -> Exception | str:
    """Preserve the public diagnostic format for PMC transport failures."""
    if isinstance(error, PMCRequestError):
        return format_pmc_error(error)
    return error


__all__ = ["normalize_error", "run"]
