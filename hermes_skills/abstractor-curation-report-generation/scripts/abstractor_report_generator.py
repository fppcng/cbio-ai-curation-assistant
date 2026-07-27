"""
Generate a cBioPortal curation report from a local paper PDF or XML file and local supplementary files.

Example
-------
    python hermes_skills/abstractor-curation-report-generation/scripts/abstractor_report_generator.py \
        --study-id <study_id>
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import os
from pathlib import Path
from typing import Any, Sequence

from cbio_curation_assistant.cbioportal_curator import _analyse_supplementary_files, _extract_metadata_llm, _extract_pdf_text
from cbio_curation_assistant.cli_shared import extract_xml_metadata_with_llm
from cbio_curation_assistant.config import LLMConfig
from cbio_curation_assistant.hermes_llm import resolve_optional_hermes_llm_config
from cbio_curation_assistant.pdf_report import (
    build_curation_report_json,
    save_curation_report_pdf,
)
from cbio_curation_assistant.pmc_supplement_fetcher import SUPPORTED_SUPPLEMENT_EXTENSIONS
from cbio_curation_assistant.workspace import InvalidStudyIdError, StudyWorkspace, WorkspaceConfigurationError

logger = logging.getLogger(__name__)

_DEFAULT_REPORT_SUFFIX = "abstractor_report"
_AGENT_REPORT_SCHEMA_VERSION = 1


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


def _resolve_study_inputs(study_id: str) -> tuple[StudyWorkspace, str | None, str | None, list[str]]:
    workspace = StudyWorkspace.load(study_id)
    paper_xml_path = workspace.article_xml_path if workspace.article_xml_path.is_file() else None
    paper_pdf_path = workspace.article_pdf_path if workspace.article_pdf_path.is_file() else None

    if paper_xml_path is None and paper_pdf_path is None:
        raise FileNotFoundError(
            "No canonical article source was found in the study workspace. "
            f"Expected {workspace.article_xml_path} or {workspace.article_pdf_path}."
        )

    supplementary_paths = _expand_supplementary_paths([workspace.supplementary_dir], recursive=True)
    return (
        workspace,
        str(paper_pdf_path.resolve()) if paper_pdf_path is not None else None,
        str(paper_xml_path.resolve()) if paper_xml_path is not None else None,
        supplementary_paths,
    )


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
        warnings.append("No Hermes LLM configuration is available. PDF metadata fields will be blank.")
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
    study_workspace: StudyWorkspace | None,
) -> str:
    study_id = str(meta.get("study_id_suggestion") or "").strip()
    if not study_id or study_id == "—":
        study_id = str(summary.get("study_id") or "").strip()
    if not study_id or study_id == "—":
        study_id = study_workspace.study_id if study_workspace is not None else "cbioportal_curation"

    stem = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in study_id).strip("._")
    return f"{stem or 'cbioportal_curation'}_{_DEFAULT_REPORT_SUFFIX}"


def _build_report_pdf_filename(
    meta: dict[str, Any],
    summary: dict[str, Any],
    study_workspace: StudyWorkspace | None,
) -> str:
    return _build_report_stem(meta, summary, study_workspace) + ".pdf"


def _build_report_json_filename(
    meta: dict[str, Any],
    summary: dict[str, Any],
    study_workspace: StudyWorkspace | None,
) -> str:
    return _build_report_stem(meta, summary, study_workspace) + ".json"


def _infer_study_workspace(paths: Sequence[str | Path]) -> StudyWorkspace | None:
    study_workspaces: dict[Path, StudyWorkspace] = {}

    for raw_path in paths:
        candidate = Path(raw_path).expanduser().resolve()
        for ancestor in (candidate, *candidate.parents):
            if ancestor.parent.name != "studies":
                continue
            try:
                workspace = StudyWorkspace.load(
                    ancestor.name,
                    assistant_home=ancestor.parent.parent,
                )
            except (InvalidStudyIdError, WorkspaceConfigurationError):
                continue
            if workspace.contains(candidate):
                study_workspaces[workspace.root] = workspace
                break

    if len(study_workspaces) == 1:
        return next(iter(study_workspaces.values()))
    return None


def _resolve_output_pdf_path(
    output_pdf_path: str | None,
    output_dir: str | None,
    study_workspace: StudyWorkspace | None,
    meta: dict[str, Any],
    summary: dict[str, Any],
) -> str | None:
    if output_pdf_path:
        return str(Path(output_pdf_path).expanduser().resolve())
    if output_dir:
        directory = Path(output_dir).expanduser().resolve()
        return str((directory / _build_report_pdf_filename(meta, summary, study_workspace)).resolve())
    if study_workspace is not None:
        return str((study_workspace.reports_dir / _build_report_pdf_filename(meta, summary, study_workspace)).resolve())
    return None


def _resolve_output_json_path(
    output_json_path: str | None,
    output_pdf_path: str | None,
    output_dir: str | None,
    study_workspace: StudyWorkspace | None,
    meta: dict[str, Any],
    summary: dict[str, Any],
) -> str | None:
    if output_json_path:
        return str(Path(output_json_path).expanduser().resolve())
    if output_pdf_path:
        return str(Path(output_pdf_path).with_suffix(".json").resolve())
    if output_dir:
        directory = Path(output_dir).expanduser().resolve()
        return str((directory / _build_report_json_filename(meta, summary, study_workspace)).resolve())
    if study_workspace is not None:
        return str((study_workspace.reports_dir / _build_report_json_filename(meta, summary, study_workspace)).resolve())
    return None


def _write_json(path: str | Path, payload: dict[str, Any]) -> str:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + os.linesep, encoding="utf-8")
    return str(destination)


def _resolve_agent_report_path(
    output_json_path: str | None,
    output_dir: str | None,
    study_workspace: StudyWorkspace | None,
) -> str | None:
    if output_json_path:
        report_path = Path(output_json_path).expanduser().resolve()
        return str(report_path.with_name(f"{report_path.stem}_agent_report.json"))
    if output_dir:
        return str((Path(output_dir).expanduser().resolve() / "curation_report_agent.json").resolve())
    if study_workspace is not None:
        return str(study_workspace.curation_report_agent_path.resolve())
    return None


def _build_agent_report(
    *,
    study_workspace: StudyWorkspace | None,
    inputs: dict[str, Any],
    warnings: Sequence[str],
    resolved_llm_config: LLMConfig | None,
    pdf_path: str | None,
    report_json_path: str | None,
    agent_report_json_path: str | None,
) -> dict[str, Any]:
    supplementary_paths = [str(Path(path).expanduser().resolve()) for path in inputs.get("supplementary_paths", [])]
    return {
        "schema_version": _AGENT_REPORT_SCHEMA_VERSION,
        "status": "success",
        "success": True,
        "study_id": study_workspace.study_id if study_workspace is not None else None,
        "paper_source": {
            "type": inputs.get("paper_source_type"),
            "path": inputs.get("paper_source_value"),
        },
        "supplementary_files": {
            "count": len(supplementary_paths),
            "paths": supplementary_paths,
        },
        "llm_metadata_extraction": {
            "enabled": resolved_llm_config is not None,
            "provider": resolved_llm_config.provider if resolved_llm_config else None,
            "model": resolved_llm_config.model if resolved_llm_config else None,
            "api_mode": resolved_llm_config.api_mode if resolved_llm_config else None,
            "base_url": resolved_llm_config.base_url if resolved_llm_config else None,
        },
        "outputs": {
            "pdf": pdf_path,
            "curation_report_json": report_json_path,
            "agent_report_json": agent_report_json_path,
        },
        "warnings": list(warnings),
    }


def run_curation_orchestrator(
    *,
    paper_pdf_path: str | None = None,
    paper_xml_path: str | None = None,
    supplementary_paths: Sequence[str | Path] | None = None,
    study_workspace: StudyWorkspace | None = None,
    llm_config: LLMConfig | None = None,
    recursive_supplementary_search: bool = False,
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

    resolved_llm_config = llm_config or resolve_optional_hermes_llm_config()

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
            missing_llm_warning="No Hermes LLM configuration is available. Using structured XML metadata only.",
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

    if study_workspace is None:
        study_workspace = _infer_study_workspace([paper_path, *supp_paths])

    records = _analyse_supplementary_files(supp_paths)
    summary = _build_summary(meta, records, supp_paths)

    resolved_output_pdf_path = _resolve_output_pdf_path(output_pdf_path, output_dir, study_workspace, meta, summary)
    resolved_output_json_path = _resolve_output_json_path(
        output_json_path=output_json_path,
        output_pdf_path=resolved_output_pdf_path,
        output_dir=output_dir,
        study_workspace=study_workspace,
        meta=meta,
        summary=summary,
    )

    pdf_path = save_curation_report_pdf(meta, summary, resolved_output_pdf_path)

    report = build_curation_report_json(meta, summary)
    report_json_path = _write_json(resolved_output_json_path, report) if resolved_output_json_path else None
    resolved_agent_report_path = _resolve_agent_report_path(output_json_path, output_dir, study_workspace)
    agent_report = _build_agent_report(
        study_workspace=study_workspace,
        inputs=inputs,
        warnings=warnings,
        resolved_llm_config=resolved_llm_config,
        pdf_path=pdf_path,
        report_json_path=report_json_path,
        agent_report_json_path=resolved_agent_report_path,
    )
    agent_report_json_path = _write_json(resolved_agent_report_path, agent_report) if resolved_agent_report_path else None
    agent_report["outputs"]["agent_report_json"] = agent_report_json_path

    return {
        "report": report,
        "agent_report": agent_report,
        "meta": meta,
        "records": records,
        "summary": summary,
        "pdf_path": pdf_path,
        "report_json_path": report_json_path,
        "agent_report_json_path": agent_report_json_path,
        "study_root": str(study_workspace.root) if study_workspace is not None else None,
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
        description=(
            "Generate a cBioPortal curation report PDF and JSON from the canonical article "
            "and supplementary files in a study workspace. LLM metadata enrichment is resolved "
            "from the Hermes environment."
        ),
    )

    parser.add_argument(
        "--study-id",
        required=True,
        help="Canonical study workspace key used to resolve the study workspace.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        study_workspace, paper_pdf_path, paper_xml_path, supplementary_paths = _resolve_study_inputs(args.study_id)
        result = run_curation_orchestrator(
            paper_pdf_path=paper_pdf_path,
            paper_xml_path=paper_xml_path,
            supplementary_paths=supplementary_paths,
            study_workspace=study_workspace,
        )
    except Exception as exc:
        logger.error("%s", exc)
        return 1

    rendered = json.dumps(result["agent_report"], indent=2, ensure_ascii=False)
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
