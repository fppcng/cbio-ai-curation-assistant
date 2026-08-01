"""Command-line adapter for the package-owned curation-report workflow."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from cbio_curation_assistant.command_result import (
    command_error,
    emit_command_result,
)
from cbio_curation_assistant.llm import resolve_optional_llm_config
from cbio_curation_assistant.workflows.curation_report import (
    run_curation_report_for_study,
)


logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbio-curation curation-report",
        description=(
            "Generate a cBioPortal curation report PDF and JSON from the "
            "canonical article and supplementary files in a study workspace."
        ),
    )
    parser.add_argument(
        "--study-id",
        required=True,
        help="Canonical study workspace key used to resolve report inputs.",
    )
    return parser


def run_curation_report_command(argv: Sequence[str]) -> int:
    """Parse arguments, invoke the report workflow, and emit its result."""
    args = _build_parser().parse_args(argv)
    try:
        result = run_curation_report_for_study(
            args.study_id,
            llm_config=resolve_optional_llm_config(),
        )
    except Exception as exc:
        logger.error("%s", exc)
        emit_command_result(command_error("curation-report", exc))
        return 1

    emit_command_result(result.agent_report)
    return 0


__all__ = ["run_curation_report_command"]
