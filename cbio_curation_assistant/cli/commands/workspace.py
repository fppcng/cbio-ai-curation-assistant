"""Command adapter for canonical workspace discovery."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from cbio_curation_assistant.cli.environment import assistant_home
from cbio_curation_assistant.cli.result import CommandResult, command_result
from cbio_curation_assistant.workspace import get_study_workspace


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbio-curation workspace",
        description="Inspect canonical study workspaces.",
    )
    subparsers = parser.add_subparsers(dest="workspace_command", required=True)
    describe_parser = subparsers.add_parser(
        "describe",
        help="Print canonical workspace paths as JSON.",
        description="Print canonical workspace paths as machine-readable JSON.",
    )
    describe_parser.add_argument(
        "--study-id",
        required=True,
        help=(
            "Canonical study workspace key under "
            "$CBIO_CURATION_ASSISTANT_HOME/studies/."
        ),
    )
    return parser


def run(argv: Sequence[str]) -> CommandResult[object]:
    """Describe a canonical workspace."""
    args = _build_parser().parse_args(argv)
    if args.workspace_command != "describe":
        raise ValueError(f"Unsupported workspace command: {args.workspace_command}")
    workspace = get_study_workspace(
        args.study_id,
        assistant_home=assistant_home(),
        require_manifest=True,
    )
    return command_result(
        "workspace.describe",
        status="success",
        result=workspace.discovery_payload(),
    )


__all__ = ["run"]
