from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from cbio_curation_assistant.cbioportal_curator import SYSTEM_PROMPT_CURATOR
from cbio_curation_assistant.llm import LLMConfig, complete_text, parse_llm_json
from cbio_curation_assistant.metadata_merge import merge_missing_metadata_fields
from cbio_curation_assistant.xml_metadata import extract_metadata_from_xml, extract_xml_llm_text


def extract_xml_metadata_with_llm(
    xml_source: str | Path,
    llm_config: LLMConfig | None,
    warnings: list[str],
    *,
    logger: logging.Logger | None = None,
    missing_text_warning: str,
    missing_llm_warning: str,
    completion_failure_warning: str,
) -> dict[str, Any]:
    meta = extract_metadata_from_xml(xml_source)
    llm_text = extract_xml_llm_text(xml_source)

    if not llm_text.strip():
        warnings.append(missing_text_warning)
        return meta

    if llm_config is None:
        warnings.append(missing_llm_warning)
        return meta

    active_logger = logger or logging.getLogger(__name__)
    raw_meta = ""
    try:
        raw_meta = complete_text(
            config=llm_config,
            system=SYSTEM_PROMPT_CURATOR,
            user_content=llm_text[:40000],
            max_tokens=2000,
        )
        return merge_missing_metadata_fields(meta, parse_llm_json(raw_meta))
    except Exception:
        active_logger.exception(
            "XML metadata completion failed: provider=%s model=%s api_mode=%s base_url=%s raw_meta=%r",
            llm_config.provider,
            llm_config.model,
            llm_config.api_mode,
            llm_config.base_url,
            raw_meta[:2000],
        )
        warnings.append(completion_failure_warning)
        return meta


__all__ = [
    "extract_xml_metadata_with_llm",
]
