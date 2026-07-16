"""
Generate a cBioPortal curation report from a local paper PDF or XML file and local supplementary files.

Example
-------
    python hermes_skills/abstractor-curation-report-generation/scripts/abstractor_report_generator.py \
        --paper-xml /path/to/article.xml \
        --supp /path/to/supp_dir
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Sequence

_REPO_ROOT_ENV = "CBIO_ASSISTANT_REPO_ROOT"


def _get_repo_root() -> Path:
    raw_repo_root = os.environ.get(_REPO_ROOT_ENV)
    if not raw_repo_root:
        raise RuntimeError(
            f"Missing required environment variable {_REPO_ROOT_ENV}. "
            "Make sure Hermes loaded its environment before running this script."
        )

    repo_root = Path(raw_repo_root).expanduser().resolve()
    if not repo_root.is_dir():
        raise RuntimeError(
            f"{_REPO_ROOT_ENV} does not point to an existing directory: {repo_root}"
        )

    return repo_root


_REPO_ROOT = _get_repo_root()
_MODULE_ROOT = _REPO_ROOT / "cbio_abstractor"
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from cbioportal_curator import _analyse_supplementary_files, _extract_metadata_llm, _extract_pdf_text  # noqa: E402
from cli_shared import extract_xml_metadata_with_llm  # noqa: E402
from config import LLMConfig, PROVIDER_SPECS, get_provider_default_config, get_provider_names  # noqa: E402
from pdf_report import (  # noqa: E402
    build_curation_report_json,
    save_curation_report_pdf,
)
from pmc_supplement_fetcher import SUPPORTED_SUPPLEMENT_EXTENSIONS  # noqa: E402

logger = logging.getLogger(__name__)

_LLM_DISCOVERY_ORDER = ("LiteLLM", "OpenAI", "Anthropic")
_REPORTS_DIRNAME = "reports"
_DEFAULT_REPORT_SUFFIX = "abstractor_report"


def _load_llm_env_value(env_name: str | None, default: str = "") -> str:
    if not env_name:
        return default
    return os.environ.get(env_name, "").strip() or default


def _build_skill_llm_config(
    provider: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
) -> LLMConfig:
    defaults = get_provider_default_config(
        provider,
        value_loader=lambda env_name, default="": _load_llm_env_value(env_name, default),
    )
    spec = PROVIDER_SPECS[provider]
    resolved_api_mode = defaults.api_mode if api_mode is None else (api_mode or "").strip().lower()
    return LLMConfig(
        provider=provider,
        api_key=(defaults.api_key if api_key is None else api_key).strip(),
        model=(defaults.model if model is None else model).strip() or defaults.model,
        base_url=(defaults.base_url if base_url is None else base_url).strip(),
        api_mode=resolved_api_mode or spec.default_api_mode,
    )


def _is_complete_llm_config(config: LLMConfig) -> bool:
    spec = PROVIDER_SPECS[config.provider]
    if spec.requires_api_key and not config.api_key:
        return False
    if config.provider == "LiteLLM" and not config.base_url:
        return False
    return bool(config.model)


def _require_complete_llm_config(config: LLMConfig) -> None:
    spec = PROVIDER_SPECS[config.provider]
    if config.provider == "LiteLLM" and not config.base_url:
        raise ValueError(f"Please set {spec.base_url_env} in the Hermes environment or pass --base-url.")
    if spec.requires_api_key and not config.api_key:
        raise ValueError(f"Please set {spec.api_key_env} in the Hermes environment or pass --api-key.")
    if not config.model:
        raise ValueError(f"Please choose a model for {config.provider}.")


def _auto_select_llm_provider() -> str | None:
    available_providers = set(get_provider_names())
    for provider in _LLM_DISCOVERY_ORDER:
        if provider not in available_providers:
            continue
        config = _build_skill_llm_config(provider)
        if _is_complete_llm_config(config):
            return provider
    return None


def _resolve_skill_llm_config(
    *,
    provider: str | None,
    api_key: str | None,
    model: str | None,
    base_url: str | None,
    api_mode: str | None,
) -> LLMConfig | None:
    has_explicit_overrides = any(value is not None for value in (provider, api_key, model, base_url, api_mode))
    resolved_provider = provider or _auto_select_llm_provider()

    if resolved_provider is None:
        if has_explicit_overrides:
            raise ValueError(
                "No complete LLM configuration was found in the Hermes environment. "
                "Pass --provider with a complete override."
            )
        return None

    config = _build_skill_llm_config(
        resolved_provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )

    if has_explicit_overrides:
        _require_complete_llm_config(config)
        return config

    if provider is None:
        logger.info("Auto-selected LLM provider from environment: %s", resolved_provider)

    return config if _is_complete_llm_config(config) else None


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
    breakdown = _build_report_breakdown(records)
    return {
        "study_id": meta.get("study_id_suggestion") or "—",
        "cancer_type": meta.get("cancer_type") or "—",
        "num_samples": meta.get("num_samples") or "—",
        "reference_genome": meta.get("reference_genome") or "—",
        "files_analysed": len(supp_paths),
        "sheets_analysed": len(records),
        "high_priority": _count_records_by_value(records, "priority", "HIGH"),
        "medium_priority": _count_records_by_value(records, "priority", "MEDIUM"),
        "not_loadable": _count_records_by_value(records, "curability", "NO"),
        "file_breakdown": breakdown,
    }


def _count_records_by_value(
    records: Sequence[dict[str, Any]],
    field_name: str,
    expected_value: str,
) -> int:
    expected = expected_value.upper()
    return sum(
        1
        for row in records
        if str(row.get(field_name, "") or "").strip().upper() == expected
    )


def _build_report_breakdown(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    pdf_rows_by_file: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in records:
        file_name = str(row.get("file", "") or "")
        if file_name.lower().endswith(".pdf"):
            pdf_rows_by_file[file_name].append(row)

    manual_pdf_rows_by_file = {
        file_name: [row for row in rows if str(row.get("curability", "")).upper() == "NO"]
        for file_name, rows in pdf_rows_by_file.items()
    }
    aggregated_pdf_files = {
        file_name for file_name, rows in manual_pdf_rows_by_file.items() if rows
    }

    breakdown: list[dict[str, Any]] = []
    emitted_pdf_files: set[str] = set()
    for row in records:
        file_name = str(row.get("file", "—") or "—")
        is_manual_pdf_row = str(row.get("curability", "")).upper() == "NO"
        if file_name in aggregated_pdf_files and is_manual_pdf_row:
            if file_name in emitted_pdf_files:
                continue
            breakdown.append(_build_aggregated_pdf_breakdown_row(manual_pdf_rows_by_file[file_name]))
            emitted_pdf_files.add(file_name)
            continue
        breakdown.append(_build_breakdown_row(row))

    return breakdown


def _build_breakdown_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
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


def _build_aggregated_pdf_breakdown_row(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    first_row = rows[0]
    return {
        "file": first_row.get("file", "—"),
        "sheet": f"PDF (aggregated {len(rows)} sections)",
        "cbio_format": "Not directly loadable",
        "curability": "NO",
        "priority": "N/A",
        "confidence": max(float(row.get("confidence", 0) or 0) for row in rows),
        "verdict": (
            f"Aggregated {len(rows)} PDF sections that require manual intervention."
            if len(rows) > 1
            else first_row.get("verdict", "")
        ),
        "req_present": _merge_breakdown_values(rows, "required_present"),
        "req_missing": _merge_breakdown_values(rows, "required_missing"),
        "opt_present": _merge_breakdown_values(rows, "optional_present"),
    }


def _merge_breakdown_values(rows: Sequence[dict[str, Any]], key: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for value in row.get(key, []) or []:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            values.append(text)
    return values


def _extract_pdf_metadata(
    paper_pdf_path: str,
    llm_config: LLMConfig | None,
    warnings: list[str],
) -> dict[str, Any]:
    pdf_text = _extract_pdf_text(paper_pdf_path)
    if not pdf_text.strip():
        warnings.append("Could not extract text from the PDF. Metadata fields will be blank.")
        return {}

    if llm_config is None:
        warnings.append("No LLM configuration is available. PDF metadata fields will be blank.")
        return {}

    try:
        return _extract_metadata_llm(pdf_text, llm_config, temperature=0.2)
    except Exception as exc:
        logger.exception("PDF metadata extraction failed for %s", paper_pdf_path)
        warnings.append(f"Metadata extraction failed: {exc}")
        return {}


def _build_report_stem(
    meta: dict[str, Any],
    summary: dict[str, Any],
    study_root: Path | None,
) -> str:
    study_id = str(meta.get("study_id_suggestion") or "").strip()
    if not study_id or study_id == "—":
        study_id = str(summary.get("study_id") or "").strip()
    if not study_id or study_id == "—":
        study_id = study_root.name if study_root is not None else "cbioportal_curation"

    stem = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in study_id).strip("._")
    return f"{stem or 'cbioportal_curation'}_{_DEFAULT_REPORT_SUFFIX}"


def _build_report_pdf_filename(
    meta: dict[str, Any],
    summary: dict[str, Any],
    study_root: Path | None,
) -> str:
    return _build_report_stem(meta, summary, study_root) + ".pdf"


def _build_report_json_filename(
    meta: dict[str, Any],
    summary: dict[str, Any],
    study_root: Path | None,
) -> str:
    return _build_report_stem(meta, summary, study_root) + ".json"


def _infer_study_root(paths: Sequence[str | Path]) -> Path | None:
    study_roots: set[Path] = set()

    for raw_path in paths:
        candidate = Path(raw_path).expanduser().resolve()
        for ancestor in (candidate, *candidate.parents):
            if ancestor.parent.name == "studies":
                study_roots.add(ancestor)
                break

    if len(study_roots) == 1:
        return next(iter(study_roots))
    return None


def _resolve_output_pdf_path(
    output_pdf_path: str | None,
    output_dir: str | None,
    study_root: Path | None,
    meta: dict[str, Any],
    summary: dict[str, Any],
) -> str | None:
    if output_pdf_path:
        return str(Path(output_pdf_path).expanduser().resolve())
    if output_dir:
        directory = Path(output_dir).expanduser().resolve()
        return str(directory / _build_report_pdf_filename(meta, summary, study_root))
    if study_root is not None:
        return str((study_root / _REPORTS_DIRNAME / _build_report_pdf_filename(meta, summary, study_root)).resolve())
    return None


def _resolve_output_json_path(
    output_json_path: str | None,
    output_pdf_path: str | None,
    output_dir: str | None,
    study_root: Path | None,
    meta: dict[str, Any],
    summary: dict[str, Any],
) -> str | None:
    if output_json_path:
        return str(Path(output_json_path).expanduser().resolve())
    if output_pdf_path:
        return str(Path(output_pdf_path).with_suffix(".json").resolve())
    if output_dir:
        directory = Path(output_dir).expanduser().resolve()
        return str((directory / _build_report_json_filename(meta, summary, study_root)).resolve())
    if study_root is not None:
        return str((study_root / _REPORTS_DIRNAME / _build_report_json_filename(meta, summary, study_root)).resolve())
    return None


def _write_json(path: str | Path, payload: dict[str, Any]) -> str:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + os.linesep, encoding="utf-8")
    return str(destination)


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
    output_json_path: str | None = None,
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

    resolved_llm_config = llm_config or _resolve_skill_llm_config(
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

    study_root = _infer_study_root([paper_path, *supp_paths])

    records = _analyse_supplementary_files(supp_paths)
    summary = _build_summary(meta, records, supp_paths)

    resolved_output_pdf_path = _resolve_output_pdf_path(output_pdf_path, output_dir, study_root, meta, summary)
    resolved_output_json_path = _resolve_output_json_path(
        output_json_path=output_json_path,
        output_pdf_path=resolved_output_pdf_path if generate_pdf else None,
        output_dir=output_dir,
        study_root=study_root,
        meta=meta,
        summary=summary,
    )

    pdf_path: str | None = None
    if generate_pdf:
        pdf_path = save_curation_report_pdf(meta, summary, resolved_output_pdf_path)

    report = build_curation_report_json(meta, summary)
    report_json_path = _write_json(resolved_output_json_path, report) if resolved_output_json_path else None

    return {
        "report": report,
        "meta": meta,
        "records": records,
        "summary": summary,
        "pdf_path": pdf_path,
        "report_json_path": report_json_path,
        "study_root": str(study_root) if study_root is not None else None,
        "warnings": warnings,
        "inputs": inputs,
        "llm": {
            "enabled": resolved_llm_config is not None,
            "provider": resolved_llm_config.provider if resolved_llm_config else None,
            "model": resolved_llm_config.model if resolved_llm_config else None,
            "api_mode": resolved_llm_config.api_mode if resolved_llm_config else None,
            "base_url": resolved_llm_config.base_url if resolved_llm_config else None,
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
        help=(
            "LLM provider. When omitted, the script auto-selects the first complete provider "
            "from the Hermes environment in this order: LiteLLM, OpenAI, Anthropic."
        ),
    )
    parser.add_argument("--api-key", help="Override the provider API key.")
    parser.add_argument("--model", help="Override the provider model.")
    parser.add_argument("--base-url", help="Override the provider base URL.")
    parser.add_argument("--api-mode", help="Override the provider API mode.")

    parser.add_argument(
        "--output-pdf",
        help=(
            "Full output path for the generated PDF report. When omitted, the script prefers "
            "studies/<PMCID>/reports/<study_id>_abstractor_report.pdf if it can infer a unique study root."
        ),
    )
    parser.add_argument(
        "--output-dir",
        help="Directory where the PDF and JSON reports should be created if --output-pdf is not set.",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF report generation.",
    )
    parser.add_argument(
        "--output-json",
        help=(
            "Optional file path where the cBioPortal curation report JSON will be written. "
            "When omitted, the script persists JSON automatically as <study_id>_abstractor_report.json "
            "when an output PDF path, output directory, or unique study root is available."
        ),
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
            output_json_path=args.output_json,
        )
    except Exception as exc:
        logger.error("%s", exc)
        return 1

    rendered = json.dumps(result["report"], indent=2, ensure_ascii=False)
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
