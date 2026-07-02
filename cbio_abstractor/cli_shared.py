from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from cbioportal_curator import SYSTEM_PROMPT_CURATOR
from config import LLMConfig, PROVIDER_SPECS, get_provider_default_config, get_provider_names
from llm_client import call_llm_with_retry, parse_llm_json
from metadata_merge import merge_missing_metadata_fields
from xml_metadata import extract_metadata_from_xml, extract_xml_llm_text


def is_provider_configured(config: LLMConfig) -> bool:
    spec = PROVIDER_SPECS[config.provider]
    if spec.requires_api_key and not config.api_key:
        return False
    if config.provider == "LiteLLM" and not config.base_url:
        return False
    return bool(config.model)


def default_configured_provider() -> str | None:
    providers = list(get_provider_names())
    for provider in ("OpenAI", "Anthropic", "LiteLLM"):
        if provider in providers and is_provider_configured(get_provider_default_config(provider)):
            return provider
    for provider in providers:
        if is_provider_configured(get_provider_default_config(provider)):
            return provider
    return None


def require_llm_config(config: LLMConfig) -> None:
    spec = PROVIDER_SPECS[config.provider]
    if config.provider == "LiteLLM" and not config.base_url:
        raise ValueError(f"Please set {spec.base_url_env} in .env or the process environment.")
    if spec.requires_api_key and not config.api_key:
        raise ValueError(f"Please add your {config.provider} API key or set {spec.api_key_env}.")
    if not config.model:
        raise ValueError(f"Please choose a model for {config.provider}.")


def _build_llm_config(
    resolved_provider: str,
    api_key: str | None,
    model: str | None,
    base_url: str | None,
    api_mode: str | None,
) -> LLMConfig:
    defaults = get_provider_default_config(resolved_provider)
    spec = PROVIDER_SPECS[resolved_provider]
    resolved_api_mode = defaults.api_mode if api_mode is None else (api_mode or "").strip().lower()
    return LLMConfig(
        provider=resolved_provider,
        api_key=(defaults.api_key if api_key is None else api_key).strip(),
        model=(defaults.model if model is None else model).strip(),
        base_url=(defaults.base_url if base_url is None else base_url).strip(),
        api_mode=resolved_api_mode or spec.default_api_mode,
    )


def build_required_llm_config(
    provider: str | None,
    api_key: str | None,
    model: str | None,
    base_url: str | None,
    api_mode: str | None,
    *,
    fallback_provider: str = "OpenAI",
) -> LLMConfig:
    resolved_provider = provider or default_configured_provider() or fallback_provider
    config = _build_llm_config(
        resolved_provider=resolved_provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )
    require_llm_config(config)
    return config


def build_optional_llm_config(
    provider: str | None,
    api_key: str | None,
    model: str | None,
    base_url: str | None,
    api_mode: str | None,
) -> LLMConfig | None:
    resolved_provider = provider or default_configured_provider()
    if not resolved_provider:
        return None

    config = _build_llm_config(
        resolved_provider=resolved_provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )
    if any(value is not None for value in (provider, api_key, model, base_url, api_mode)):
        require_llm_config(config)
    return config if is_provider_configured(config) else None


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
        raw_meta = call_llm_with_retry(
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
    "build_optional_llm_config",
    "build_required_llm_config",
    "default_configured_provider",
    "extract_xml_metadata_with_llm",
    "is_provider_configured",
    "require_llm_config",
]
