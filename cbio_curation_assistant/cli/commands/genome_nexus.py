"""Command adapter for the package-owned Genome Nexus workflow."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from cbio_curation_assistant.cli.result import (
    CommandResult,
    command_error,
    command_result,
)
from cbio_curation_assistant.workflows.mutation_annotation import (
    DEFAULT_IMAGE,
    run_genome_nexus_annotation,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbio-curation genome-nexus",
        description="Annotate the canonical minimal MAF in a study workspace.",
    )
    parser.add_argument(
        "--study-id",
        required=True,
        help="Canonical study workspace key used to resolve the curated workspace.",
    )
    parser.add_argument(
        "--genome-build",
        required=True,
        choices=("GRCh37", "GRCh38"),
        help="Reference assembly. It must be explicitly known.",
    )
    parser.add_argument(
        "--image",
        default=os.environ.get("GENOME_NEXUS_DOCKER_IMAGE", DEFAULT_IMAGE),
        help="Docker image or pinned image digest.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Maximum execution time in seconds. Default: 1800.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing canonical Genome Nexus outputs.",
    )
    return parser


def run(argv: Sequence[str]) -> CommandResult[object]:
    """Parse arguments and translate the workflow state into a command result."""
    args = _build_parser().parse_args(argv)
    annotation = run_genome_nexus_annotation(
        study_id=args.study_id,
        genome_build=args.genome_build,
        image=args.image,
        timeout=args.timeout,
        force=args.force,
    )
    if annotation.status == "error":
        return command_error(
            "genome-nexus",
            annotation.error or "Genome Nexus annotation failed.",
            result=annotation.result,
            warnings=annotation.warnings,
        )
    return command_result(
        "genome-nexus",
        status=annotation.status,
        result=annotation.result,
        warnings=annotation.warnings,
    )


__all__ = ["run"]
