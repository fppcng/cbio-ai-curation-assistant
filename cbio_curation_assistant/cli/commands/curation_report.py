"""Command adapter for the package-owned curation-report workflow."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from cbio_curation_assistant.cli.result import (
    CommandResult,
    command_result,
    render_command_result,
)
from cbio_curation_assistant.llm import resolve_optional_llm_config
from cbio_curation_assistant.workflows.curation_report import (
    run_curation_report_for_study,
)


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


def run(argv: Sequence[str]) -> CommandResult[object]:
    """Parse arguments, invoke the report workflow, and return its result."""
    args = _build_parser().parse_args(argv)
    result = run_curation_report_for_study(
        args.study_id,
        llm_config=resolve_optional_llm_config(),
    )
    response = command_result(
        "curation-report",
        status="success",
        result=result.agent_report,
        warnings=result.warnings,
    )
    agent_report_path = result.outputs.agent_report_json
    if agent_report_path is not None:
        agent_report_path.parent.mkdir(parents=True, exist_ok=True)
        agent_report_path.write_text(
            render_command_result(response) + os.linesep,
            encoding="utf-8",
        )
    return response


__all__ = ["run"]
