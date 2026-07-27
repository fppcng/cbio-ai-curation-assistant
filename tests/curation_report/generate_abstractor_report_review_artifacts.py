from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cbio_curation_assistant.hermes_llm import resolve_optional_hermes_llm_config
from tests.curation_report.abstractor_report_regression_support import (
    NO_LLM_WARNING,
    STUDY_ID,
    build_artifact_paths,
    build_timestamp_label,
    load_report_generator_module,
    run_report_generation,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate curation report review artifacts under tests/curation_report/_artifacts using pipeline code."
        )
    )
    parser.add_argument("--study-id", default=STUDY_ID, help="Study workspace key.")
    parser.add_argument(
        "--mode",
        choices=("llm", "deterministic"),
        default="llm",
        help="Use a configured LLM or force deterministic no-LLM mode.",
    )
    parser.add_argument(
        "--timestamp-label",
        help="Optional timestamp label for the artifact directory. Defaults to current UTC time.",
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Optional base directory for artifacts. Defaults to tests/curation_report/_artifacts/<study_id>/<mode>/<timestamp>/"
        ),
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    report_generator = load_report_generator_module()
    study_id = args.study_id.strip().lower()
    mode = args.mode
    timestamp_label = args.timestamp_label or build_timestamp_label()
    base_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None

    if mode == "llm":
        llm_config = resolve_optional_hermes_llm_config()
        if llm_config is None:
            raise SystemExit(
                "No complete Hermes LLM configuration is available. Configure a provider in the environment or use --mode deterministic."
            )
    else:
        llm_config = None

    artifact_dir, output_json_path, output_pdf_path = build_artifact_paths(
        study_id,
        mode=mode,
        timestamp_label=timestamp_label,
        base_dir=base_dir,
    )
    result, _ = run_report_generation(
        report_generator=report_generator,
        study_id=study_id,
        output_json_path=output_json_path,
        output_pdf_path=output_pdf_path,
        use_llm=(mode == "llm"),
        embedded_spec_tag=f"review-run-{mode}",
    )

    payload = {
        "study_id": study_id,
        "mode": mode,
        "artifact_dir": str(artifact_dir.resolve()),
        "paper_source_type": result["inputs"]["paper_source_type"],
        "warnings": result["warnings"],
        "llm": result["llm"],
        "pdf_path": result["pdf_path"],
        "report_json_path": result["report_json_path"],
    }
    if mode == "deterministic":
        payload["expected_no_llm_warning"] = NO_LLM_WARNING
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
