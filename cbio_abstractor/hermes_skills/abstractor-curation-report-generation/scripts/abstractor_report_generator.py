"""
Generate a cBioPortal curation report from a local paper PDF or XML file and local supplementary files.

Example
-------
    python cbio_abstractor/hermes_skills/abstractor-curation-report-generation/scripts/abstractor_report_generator.py           --paper-xml /path/to/article.xml           --supp /path/to/supp_dir
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Sequence

_MODULE_ROOT = Path(__file__).resolve().parents[3]
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from cbioportal_curator import _analyse_supplementary_files, _extract_metadata_llm, _extract_pdf_text  # noqa: E402
from cli_shared import build_required_llm_config, extract_xml_metadata_with_llm  # noqa: E402
from config import LLMConfig, get_provider_names  # noqa: E402
from pdf_report import (  # noqa: E402
    build_curation_report_filename,
    build_curation_report_json,
    save_curation_report_pdf,
)
from pmc_supplement_fetcher import SUPPORTED_SUPPLEMENT_EXTENSIONS  # noqa: E402

logger = logging.getLogger(__name__)


def _is_supported_supplementary_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_SUPPLEMENT_EXTENSIONS


def _expand_supplementary_paths(
    paths: Sequence[str | Path],
    *,
    recursive: bool = False,
) -> list[str]:
    resolved_paths: list[str] = []
    seen: set[str] = set()

    for raw_path in paths:
        candidate = Path(raw_path).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"Supplementary path not found: {candidate}")

        if candidate.is_file():
            if not _is_supported_supplementary_file(candidate):
                raise ValueError(f"Unsupported supplementary file type: {candidate}")
            value = str(candidate)
            if value not in seen:
                seen.add(value)
                resolved_paths.append(value)
            continue

        if not candidate.is_dir():
            raise ValueError(f"Unsupported supplementary path: {candidate}")

        iterator = candidate.rglob("*") if recursive else candidate.iterdir()
        matching_files = sorted(
            path.resolve()
            for path in iterator
            if _is_supported_supplementary_file(path)
        )
        for path in matching_files:
            value = str(path)
            if value not in seen:
                seen.add(value)
                resolved_paths.append(value)

    if not resolved_paths:
        raise ValueError("No supported supplementary files were found.")

    return resolved_paths


def _build_summary(meta: dict[str, Any], records: list[dict[str, Any]], supp_paths: Sequence[str]) -> dict[str, Any]:
    return {
        "study_id": meta.get("study_id_suggestion") or "—",
        "cancer_type": meta.get("cancer_type") or "—",
        "num_samples": meta.get("num_samples") or "—",
        "reference_genome": meta.get("reference_genome") or "—",
        "files_analysed": len(supp_paths),
        "sheets_analysed": len(records),
        "high_priority": sum(1 for row in records if row.get("priority") == "HIGH"),
        "medium_priority": sum(1 for row in records if row.get("priority") == "MEDIUM"),
        "not_loadable": sum(1 for row in records if row.get("curability") == "NO"),
        "file_breakdown": [
            {
                "file": row.get("file", "—"),
                "sheet": row.get("sheet", "—"),
                "cbio_format": row.get("cbio_target_file", "—"),
                "curability": row.get("curability", "NO"),
                "priority": row.get("priority", "N/A"),
                "confidence": row.get("confidence", 0),
                "verdict": row.get("verdict", ""),
                "req_present": row.get("required_present", []),
                "req_missing": row.get("required_missing", []),
                "opt_present": row.get("optional_present", []),
            }
            for row in records
        ],
    }


def _extract_pdf_metadata(
    paper_pdf_path: str,
    llm_config: LLMConfig,
    warnings: list[str],
) -> dict[str, Any]:
    pdf_text = _extract_pdf_text(paper_pdf_path)
    if not pdf_text.strip():
        warnings.append("Could not extract text from the PDF. Metadata fields will be blank.")
        return {}

    try:
        return _extract_metadata_llm(pdf_text, llm_config, temperature=0.2)
    except Exception as exc:
        logger.exception("PDF metadata extraction failed for %s", paper_pdf_path)
        warnings.append(f"Metadata extraction failed: {exc}")
        return {}


def _resolve_output_pdf_path(
    output_pdf_path: str | None,
    output_dir: str | None,
    meta: dict[str, Any],
    summary: dict[str, Any],
) -> str | None:
    if output_pdf_path:
        return str(Path(output_pdf_path).expanduser().resolve())
    if output_dir:
        directory = Path(output_dir).expanduser().resolve()
        return str(directory / build_curation_report_filename(meta, summary))
    return None


def run_curation_orchestrator(
    *,
    paper_pdf_path: str | None = None,
    paper_xml_path: str | None = None,
    supplementary_paths: Sequence[str | Path] | None = None,
    llm_config: LLMConfig | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
    recursive_supplementary_search: bool = False,
    generate_pdf: bool = True,
    output_pdf_path: str | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """
    Run the local curation report workflow.

    Exactly one local paper source is supported:
    - `paper_pdf_path` + `supplementary_paths`
    - `paper_xml_path` + `supplementary_paths`
    """
    selected_sources = [
        bool(paper_pdf_path),
        bool(paper_xml_path),
    ]
    if sum(selected_sources) != 1:
        raise ValueError("Provide exactly one of: paper_pdf_path or paper_xml_path.")

    resolved_llm_config = llm_config or build_required_llm_config(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )

    warnings: list[str] = []
    meta: dict[str, Any]
    inputs: dict[str, Any]
    supp_paths = _expand_supplementary_paths(
        supplementary_paths or [],
        recursive=recursive_supplementary_search,
    )

    if paper_pdf_path:
        paper_path = str(Path(paper_pdf_path).expanduser().resolve())
        if not Path(paper_path).is_file():
            raise FileNotFoundError(f"Paper PDF not found: {paper_path}")
        meta = _extract_pdf_metadata(paper_path, resolved_llm_config, warnings)
        inputs = {
            "paper_pdf_path": paper_path,
            "paper_xml_path": None,
            "paper_source_type": "pdf",
            "paper_source_value": paper_path,
            "supplementary_paths": supp_paths,
        }
    else:
        paper_path = str(Path(paper_xml_path or "").expanduser().resolve())
        if not Path(paper_path).is_file():
            raise FileNotFoundError(f"Paper XML not found: {paper_path}")
        meta = extract_xml_metadata_with_llm(
            paper_path,
            resolved_llm_config,
            warnings,
            logger=logger,
            missing_text_warning="Could not extract text from the XML. Using structured XML metadata only.",
            missing_llm_warning="No LLM configuration is available. Using structured XML metadata only.",
            completion_failure_warning=(
                "XML metadata completion returned unexpected format. Continuing with structured XML metadata only."
            ),
        )
        inputs = {
            "paper_pdf_path": None,
            "paper_xml_path": paper_path,
            "paper_source_type": "xml",
            "paper_source_value": paper_path,
            "supplementary_paths": supp_paths,
        }

    records = _analyse_supplementary_files(supp_paths)
    summary = _build_summary(meta, records, supp_paths)

    pdf_path: str | None = None
    if generate_pdf:
        resolved_output_pdf_path = _resolve_output_pdf_path(output_pdf_path, output_dir, meta, summary)
        pdf_path = save_curation_report_pdf(meta, summary, resolved_output_pdf_path)

    report = build_curation_report_json(meta, summary)

    return {
        "report": report,
        "meta": meta,
        "records": records,
        "summary": summary,
        "pdf_path": pdf_path,
        "warnings": warnings,
        "inputs": inputs,
        "llm": {
            "provider": resolved_llm_config.provider,
            "model": resolved_llm_config.model,
            "api_mode": resolved_llm_config.api_mode,
            "base_url": resolved_llm_config.base_url,
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a cBioPortal curation report from local paper and supplementary files.",
    )

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--paper-pdf", help="Path to the main paper PDF.")
    source_group.add_argument("--paper-xml", help="Path to the main paper XML/NXML.")

    parser.add_argument(
        "--supp",
        nargs="+",
        required=True,
        help="Supplementary file paths or directories.",
    )
    parser.add_argument(
        "--recursive-supp",
        action="store_true",
        help="When a supplementary path is a directory, search it recursively.",
    )

    parser.add_argument(
        "--provider",
        choices=list(get_provider_names()),
        help="LLM provider. Defaults to the first configured provider, otherwise OpenAI.",
    )
    parser.add_argument("--api-key", help="Override the provider API key.")
    parser.add_argument("--model", help="Override the provider model.")
    parser.add_argument("--base-url", help="Override the provider base URL.")
    parser.add_argument("--api-mode", help="Override the provider API mode.")

    parser.add_argument(
        "--output-pdf",
        help="Full output path for the generated PDF report.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory where the PDF report should be created if --output-pdf is not set.",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF report generation.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional file path where the cBioPortal curation report JSON will be written.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        result = run_curation_orchestrator(
            paper_pdf_path=args.paper_pdf,
            paper_xml_path=args.paper_xml,
            supplementary_paths=args.supp,
            provider=args.provider,
            api_key=args.api_key,
            model=args.model,
            base_url=args.base_url,
            api_mode=args.api_mode,
            recursive_supplementary_search=args.recursive_supp,
            generate_pdf=not args.no_pdf,
            output_pdf_path=args.output_pdf,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        logger.error("%s", exc)
        return 1

    rendered = json.dumps(result["report"], indent=2, ensure_ascii=False)
    if args.output_json:
        output_json_path = Path(args.output_json).expanduser().resolve()
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(rendered + os.linesep, encoding="utf-8")

    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
