from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from cbioportal_curator import (
    _analyse_supplementary_files,
    _extract_metadata_llm,
    _extract_metadata_regex,
    _extract_pdf_text,
    SYSTEM_PROMPT_CURATOR,
    extract_metadata_from_xml,
    extract_xml_llm_text,
)
from config import LLMConfig, PROVIDER_SPECS, get_provider_default_config, get_provider_names
from llm_client import call_llm_with_retry, parse_llm_json
from metadata_merge import merge_missing_metadata_fields
from pdf_report import save_curation_report_pdf

logger = logging.getLogger(__name__)
_HERE = Path(__file__).resolve().parent
_DOTENV_VALUES = {
    key: str(value).strip()
    for key, value in dotenv_values(_HERE / ".env").items()
    if key and value is not None
}


def _default_meta(pdf_path: str | Path) -> dict[str, Any]:
    return {
        "study_title": Path(pdf_path).stem,
        "cancer_type": "mixed",
        "cancer_type_full": "Mixed Cancer Type",
        "num_samples": "",
        "num_patients": "",
        "study_id_suggestion": "study_upload",
        "description": "",
        "meta_description": "",
        "reference_genome": "hg19",
        "sequencing_types": [],
        "pmid": "",
        "doi": "",
        "year": "",
        "journal": "",
        "first_author_surname": "",
        "key_findings": [],
        "primary_site": "",
        "cohort_description": "",
        "data_repositories": [],
        "corresponding_authors": "",
    }


def build_curation_summary(meta: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "study_id": meta.get("study_id_suggestion") or "—",
        "cancer_type": meta.get("cancer_type") or "—",
        "num_samples": meta.get("num_samples") or "—",
        "reference_genome": meta.get("reference_genome") or "—",
        "files_analysed": len({str(row.get("file", "")) for row in records if row.get("file")}),
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


def _resolve_llm_config(
    *,
    llm_config: LLMConfig | None,
    provider: str | None,
    api_key: str | None,
    model: str | None,
    base_url: str | None,
    api_mode: str | None,
) -> LLMConfig | None:
    if llm_config is not None:
        return llm_config
    resolved_provider = provider or _auto_resolve_llm_provider()
    if not resolved_provider:
        return None
    if provider is None:
        logger.info("Auto-selected LLM provider from repo .env/environment: %s", resolved_provider)
    return _build_hermes_llm_config(
        resolved_provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )


def _load_hermes_value(env_name: str | None, default: str = "") -> str:
    if not env_name:
        return default
    repo_value = _DOTENV_VALUES.get(env_name, "").strip()
    if repo_value:
        return repo_value
    return os.environ.get(env_name, "").strip() or default


def _build_hermes_llm_config(
    provider: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
) -> LLMConfig:
    default = get_provider_default_config(provider, value_loader=_load_hermes_value)
    spec = PROVIDER_SPECS[provider]
    resolved_api_mode = (default.api_mode if api_mode is None else (api_mode or "").strip().lower())
    return LLMConfig(
        provider=provider,
        api_key=(default.api_key if api_key is None else api_key).strip(),
        model=(default.model if model is None else model).strip() or default.model,
        base_url=(default.base_url if base_url is None else base_url).strip(),
        api_mode=resolved_api_mode or spec.default_api_mode,
    )


def _is_usable_llm_config(config: LLMConfig) -> bool:
    spec = PROVIDER_SPECS[config.provider]
    if spec.requires_api_key and not config.api_key:
        return False
    if not config.model:
        return False
    if config.provider == "LiteLLM" and not config.base_url:
        return False
    return True


def _auto_resolve_llm_provider() -> str | None:
    for provider_name in get_provider_names():
        config = get_provider_default_config(provider_name, value_loader=_load_hermes_value)
        if _is_usable_llm_config(config):
            return provider_name
    return None


def _resolve_paper_source(
    paper_pdf_path: str | Path | None,
    paper_xml_path: str | Path | None,
) -> tuple[Path, str]:
    pdf_path: Path | None = None
    xml_path: Path | None = None

    if paper_pdf_path is not None:
        candidate = Path(paper_pdf_path).expanduser().resolve()
        if candidate.suffix.lower() in {".xml", ".nxml"} and paper_xml_path is None:
            xml_path = candidate
        else:
            pdf_path = candidate

    if paper_xml_path is not None:
        xml_path = Path(paper_xml_path).expanduser().resolve()

    if pdf_path and xml_path:
        raise ValueError("Provide either paper_pdf_path or paper_xml_path, not both.")
    if pdf_path is not None:
        return pdf_path, "pdf"
    if xml_path is not None:
        return xml_path, "xml"
    raise ValueError("A paper source is required. Provide paper_pdf_path or paper_xml_path.")


def _extract_pdf_metadata(
    paper_path: Path,
    resolved_llm_config: LLMConfig | None,
    temperature: float,
    warnings: list[str],
) -> dict[str, Any]:
    meta = _default_meta(paper_path)
    pdf_text = _extract_pdf_text(str(paper_path))
    if not pdf_text.strip():
        warnings.append("Could not extract text from the paper PDF; metadata fields were left blank.")
        return meta

    try:
        if resolved_llm_config is not None:
            return _extract_metadata_llm(pdf_text, resolved_llm_config, temperature)

        warnings.append(
            "No LLM configuration was provided; metadata was extracted with the regex fallback only."
        )
        return _extract_metadata_regex(pdf_text)
    except Exception as exc:
        logger.warning("Metadata extraction failed for %s: %s", paper_path, exc)
        warnings.append(f"Metadata extraction failed: {exc}")
        try:
            warnings.append("Used regex fallback metadata extraction after LLM failure.")
            return _extract_metadata_regex(pdf_text)
        except Exception as fallback_exc:
            logger.warning("Regex metadata fallback failed for %s: %s", paper_path, fallback_exc)
            warnings.append(f"Regex metadata fallback failed: {fallback_exc}")
            return meta


def _extract_xml_metadata(
    paper_path: Path,
    resolved_llm_config: LLMConfig | None,
    warnings: list[str],
) -> dict[str, Any]:
    meta = merge_missing_metadata_fields(_default_meta(paper_path), extract_metadata_from_xml(paper_path))
    llm_text = extract_xml_llm_text(paper_path)

    if not llm_text.strip():
        warnings.append("Could not extract text from the paper XML; using structured XML metadata only.")
        return meta

    if resolved_llm_config is None:
        warnings.append("No LLM configuration was provided; using structured XML metadata only.")
        return meta

    try:
        raw_meta = call_llm_with_retry(
            config=resolved_llm_config,
            system=SYSTEM_PROMPT_CURATOR,
            user_content=llm_text[:40000],
            max_tokens=2000,
        )
        return merge_missing_metadata_fields(meta, parse_llm_json(raw_meta))
    except Exception as exc:
        logger.warning("XML metadata completion failed for %s: %s", paper_path, exc)
        warnings.append(f"XML metadata completion failed: {exc}")
        return meta


def run_local_curation_workflow(
    paper_pdf_path: str | Path | None = None,
    supplementary_paths: list[str | Path] | None = None,
    *,
    paper_xml_path: str | Path | None = None,
    llm_config: LLMConfig | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
    temperature: float = 0.2,
    extract_metadata: bool = True,
    generate_pdf: bool = True,
    output_pdf_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Orchestrate the local curation workflow for agents.

    Scope:
      - local paper PDF path or XML path
      - local supplementary file paths
      - metadata extraction from the paper source
      - supplementary file classification
      - summary construction
      - optional PDF report generation

    Out of scope:
      - PubMed Central / PMC downloads
      - Streamlit UI state
    """
    paper_path, paper_source_type = _resolve_paper_source(paper_pdf_path, paper_xml_path)
    supp_paths = [Path(path).expanduser().resolve() for path in (supplementary_paths or [])]

    if not paper_path.is_file():
        raise FileNotFoundError(f"Paper source not found: {paper_path}")
    if not supp_paths:
        raise ValueError("At least one supplementary file path is required.")
    missing_supp = [str(path) for path in supp_paths if not path.is_file()]
    if missing_supp:
        raise FileNotFoundError(f"Supplementary file(s) not found: {', '.join(missing_supp)}")

    warnings: list[str] = []
    resolved_llm_config = _resolve_llm_config(
        llm_config=llm_config,
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )

    if extract_metadata:
        if paper_source_type == "xml":
            meta = _extract_xml_metadata(paper_path, resolved_llm_config, warnings)
        else:
            meta = _extract_pdf_metadata(paper_path, resolved_llm_config, temperature, warnings)
    else:
        meta = _default_meta(paper_path)

    records = _analyse_supplementary_files([str(path) for path in supp_paths])
    summary = build_curation_summary(meta, records)

    pdf_path: str | None = None
    if generate_pdf:
        pdf_path = save_curation_report_pdf(meta, summary, output_pdf_path)

    return {
        "meta": meta,
        "records": records,
        "summary": summary,
        "pdf_path": pdf_path,
        "warnings": warnings,
        "inputs": {
            "paper_pdf_path": str(paper_path) if paper_source_type == "pdf" else None,
            "paper_xml_path": str(paper_path) if paper_source_type == "xml" else None,
            "paper_source_path": str(paper_path),
            "paper_source_type": paper_source_type,
            "supplementary_paths": [str(path) for path in supp_paths],
        },
    }


__all__ = [
    "build_curation_summary",
    "run_local_curation_workflow",
]
