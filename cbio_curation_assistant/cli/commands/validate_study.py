"""Command adapter for the isolated cBioPortal validator runtime."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence

from cbio_curation_assistant.cli.environment import assistant_home
from cbio_curation_assistant.workspace import StudyWorkspace


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbio-curation validate-study",
        description=(
            "Validate a canonical study curated directory with the bundled "
            "cBioPortal validator."
        ),
    )
    parser.add_argument(
        "--study-id",
        required=True,
        help=(
            "Canonical study workspace key under "
            "$CBIO_CURATION_ASSISTANT_HOME/studies/."
        ),
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


def run(argv: Sequence[str]) -> int:
    """Run the validator while preserving its independent output and exit code."""
    args = _build_parser().parse_args(argv)
    home = assistant_home()
    workspace = StudyWorkspace.from_study_id(args.study_id, assistant_home=home)
    validator_root = home / "cbioportal_core_validator"
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


__all__ = ["run"]
