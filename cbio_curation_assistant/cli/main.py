"""Top-level dispatcher and error boundary for ``cbio-curation``."""

from __future__ import annotations

import argparse
import importlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cbio_curation_assistant.cli.result import (
    CommandOutcome,
    CommandResult,
    command_error,
    emit_command_result,
    exit_code_for_status,
)


@dataclass(frozen=True, slots=True)
class CommandSpec:
    module: str
    runner: str = "run"
    error_normalizer: str | None = None

    def load(self) -> Callable[[Sequence[str]], CommandOutcome]:
        command_module = importlib.import_module(self.module)
        return getattr(command_module, self.runner)

    def normalize_error(self, error: Exception) -> Exception | str:
        if self.error_normalizer is None:
            return error
        command_module = importlib.import_module(self.module)
        normalizer = getattr(command_module, self.error_normalizer)
        return normalizer(error)


_COMMANDS = {
    "clinical-dictionary": CommandSpec(
        "cbio_curation_assistant.cli.commands.clinical_dictionary"
    ),
    "curation-report": CommandSpec(
        "cbio_curation_assistant.cli.commands.curation_report"
    ),
    "genome-nexus": CommandSpec(
        "cbio_curation_assistant.cli.commands.genome_nexus"
    ),
    "oncotree-search": CommandSpec(
        "cbio_curation_assistant.cli.commands.oncotree_search"
    ),
    "study-download": CommandSpec(
        "cbio_curation_assistant.cli.commands.study_download",
        error_normalizer="normalize_error",
    ),
    "validate-study": CommandSpec(
        "cbio_curation_assistant.cli.commands.validate_study"
    ),
    "workspace": CommandSpec("cbio_curation_assistant.cli.commands.workspace"),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbio-curation",
        description=(
            "Run cBioPortal AI curation workflows through a stable package CLI."
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=sorted(_COMMANDS),
        help="Workflow command to run.",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to the selected workflow command.",
    )
    return parser


def _finish(outcome: CommandOutcome) -> int:
    if isinstance(outcome, CommandResult):
        emit_command_result(outcome)
        return exit_code_for_status(outcome.status)
    if isinstance(outcome, int):
        return outcome
    raise TypeError(f"Unsupported command outcome: {type(outcome).__name__}")


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch one command through the CLI's single operational error boundary."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 2

    try:
        command = _COMMANDS[args.command]
        outcome = command.load()(args.args)
        return _finish(outcome)
    except Exception as exc:
        normalized_error = _COMMANDS[args.command].normalize_error(exc)
        emit_command_result(command_error(args.command, normalized_error))
        return 1


__all__ = ["main"]
