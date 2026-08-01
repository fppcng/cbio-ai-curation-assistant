"""Stable package-level command line interface for cBioPortal curation helpers."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from cbio_curation_assistant.command_result import (
    command_error,
    command_result,
    emit_command_result,
)
from cbio_curation_assistant.clinical_dictionary_cli import (
    run_clinical_dictionary_command,
)
from cbio_curation_assistant.oncotree_cli import run_oncotree_search_command
from cbio_curation_assistant.workspace import (
    ENV_VAR_NAME,
    StudyWorkspace,
    WorkspaceError,
    get_study_workspace,
    resolve_assistant_home,
)


_DIRECT_COMMANDS = (
    "clinical-dictionary",
    "curation-report",
    "genome-nexus",
    "oncotree-search",
    "study-download",
    "validate-study",
    "workspace",
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbio-curation",
        description="Run cBioPortal AI curation workflows through a stable package CLI.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=sorted(_DIRECT_COMMANDS),
        help="Workflow command to run.",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to the selected workflow command.",
    )
    return parser


def _assistant_home() -> Path:
    return resolve_assistant_home(os.environ.get(ENV_VAR_NAME))


def _build_validate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbio-curation validate-study",
        description="Validate a canonical study curated directory with the bundled cBioPortal validator.",
    )
    parser.add_argument(
        "--study-id",
        required=True,
        help="Canonical study workspace key under $CBIO_CURATION_ASSISTANT_HOME/studies/.",
    )
    parser.add_argument(
        "--relaxed-clinical-definitions",
        action="store_true",
        help="Enable the cBioPortal validator relaxed clinical definitions mode.",
    )
    parser.add_argument(
        "--strict-maf-checks",
        action="store_true",
        help="Enable strict MAF checks in the cBioPortal validator.",
    )
    return parser


def _run_validate_study(script_args: Sequence[str]) -> int:
    args = _build_validate_parser().parse_args(script_args)
    assistant_home = _assistant_home()
    workspace = StudyWorkspace.from_study_id(
        args.study_id,
        assistant_home=assistant_home,
    )
    validator_root = assistant_home / "cbioportal_core_validator"
    validator_project = validator_root / "pyproject.toml"
    script_path = validator_root / "scripts/importer/validateData.py"
    if not validator_project.is_file():
        raise FileNotFoundError(
            f"cBioPortal validator project not found: {validator_project}"
        )
    if not script_path.is_file():
        raise FileNotFoundError(f"cBioPortal validator not found: {script_path}")

    uv_executable = shutil.which("uv")
    if uv_executable is None:
        raise RuntimeError(
            "The uv executable is required to run the isolated cBioPortal "
            "validator environment."
        )

    validation_dir = workspace.root / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    validator_args = [
        "-s",
        str(workspace.curated_dir),
        "-html",
        str(validation_dir / "validator_report.html"),
        "-json",
        str(validation_dir / "validator_report.json"),
        "-n",
        "-v",
    ]
    if args.relaxed_clinical_definitions:
        validator_args.append("--relaxed_clinical_definitions")
    if args.strict_maf_checks:
        validator_args.append("--strict_maf_checks")

    validator_environment = os.environ.copy()
    validator_environment.pop("VIRTUAL_ENV", None)
    completed = subprocess.run(
        [
            uv_executable,
            "run",
            "--project",
            str(validator_root),
            "--frozen",
            "--python",
            sys.executable,
            "python",
            str(script_path),
            *validator_args,
        ],
        cwd=validator_root,
        env=validator_environment,
        check=False,
    )
    return completed.returncode


def _build_workspace_parser() -> argparse.ArgumentParser:
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
        help="Canonical study workspace key under $CBIO_CURATION_ASSISTANT_HOME/studies/.",
    )
    return parser


def _run_workspace_describe(study_id: str) -> int:
    workspace = get_study_workspace(
        study_id,
        assistant_home=_assistant_home(),
        require_manifest=True,
    )
    discovery = workspace.discovery_payload()
    emit_command_result(
        command_result(
            "workspace.describe",
            status="success",
            result=discovery,
        )
    )
    return 0


def _run_workspace(script_args: Sequence[str]) -> int:
    args = _build_workspace_parser().parse_args(script_args)
    if args.workspace_command == "describe":
        return _run_workspace_describe(args.study_id)
    raise ValueError(f"Unsupported workspace command: {args.workspace_command}")


def _run_study_download(script_args: Sequence[str]) -> int:
    from cbio_curation_assistant.study_download_cli import (
        run_study_download_command,
    )

    return run_study_download_command(script_args)


def _run_curation_report(script_args: Sequence[str]) -> int:
    from cbio_curation_assistant.curation_report_cli import (
        run_curation_report_command,
    )

    return run_curation_report_command(script_args)


def _run_genome_nexus(script_args: Sequence[str]) -> int:
    from cbio_curation_assistant.genome_nexus_cli import (
        run_genome_nexus_command,
    )

    return run_genome_nexus_command(script_args)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 2

    try:
        if args.command == "validate-study":
            return _run_validate_study(args.args)
        if args.command == "workspace":
            return _run_workspace(args.args)
        if args.command == "study-download":
            return _run_study_download(args.args)
        if args.command == "curation-report":
            return _run_curation_report(args.args)
        if args.command == "genome-nexus":
            return _run_genome_nexus(args.args)
        if args.command == "clinical-dictionary":
            return run_clinical_dictionary_command(args.args)
        if args.command == "oncotree-search":
            return run_oncotree_search_command(args.args)
        raise ValueError(f"Unsupported command: {args.command}")
    except WorkspaceError as exc:
        emit_command_result(command_error(args.command, exc))
        return 1
    except Exception as exc:
        emit_command_result(command_error(args.command, exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
