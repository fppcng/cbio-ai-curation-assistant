"""Compatibility adapters for legacy Hermes-named LLM configuration APIs."""

from __future__ import annotations

from cbio_curation_assistant.llm import (
    DEFAULT_DISCOVERY_ORDER,
    LLMConfig,
    build_llm_config,
    is_complete_llm_config,
    require_complete_llm_config,
    resolve_optional_llm_config,
    resolve_required_llm_config,
    select_configured_llm_provider,
)

HERMES_LLM_DISCOVERY_ORDER: tuple[str, ...] = DEFAULT_DISCOVERY_ORDER


def build_hermes_llm_config(
    provider: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
) -> LLMConfig:
    return build_llm_config(
        provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )


def is_complete_hermes_llm_config(config: LLMConfig) -> bool:
    return is_complete_llm_config(config)


def require_complete_hermes_llm_config(config: LLMConfig) -> None:
    require_complete_llm_config(config)


def auto_select_hermes_llm_provider() -> str | None:
    return select_configured_llm_provider(
        discovery_order=HERMES_LLM_DISCOVERY_ORDER
    )


def resolve_optional_hermes_llm_config(
    *,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
) -> LLMConfig | None:
    return resolve_optional_llm_config(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
        discovery_order=HERMES_LLM_DISCOVERY_ORDER,
    )


def resolve_required_hermes_llm_config(
    *,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
) -> LLMConfig:
    return resolve_required_llm_config(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
        discovery_order=HERMES_LLM_DISCOVERY_ORDER,
    )


__all__ = [
    "HERMES_LLM_DISCOVERY_ORDER",
    "auto_select_hermes_llm_provider",
    "build_hermes_llm_config",
    "is_complete_hermes_llm_config",
    "require_complete_hermes_llm_config",
    "resolve_optional_hermes_llm_config",
    "resolve_required_hermes_llm_config",
]
