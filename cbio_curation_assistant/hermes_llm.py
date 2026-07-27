from __future__ import annotations

import os

from cbio_curation_assistant.config import (
    LLMConfig,
    PROVIDER_SPECS,
    get_provider_default_config,
    get_provider_names,
)

HERMES_LLM_DISCOVERY_ORDER: tuple[str, ...] = ("LiteLLM", "OpenAI", "Anthropic")


def _load_hermes_env_value(env_name: str | None, default: str = "") -> str:
    if not env_name:
        return default
    return os.environ.get(env_name, "").strip() or default


def build_hermes_llm_config(
    provider: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
) -> LLMConfig:
    defaults = get_provider_default_config(
        provider,
        value_loader=lambda env_name, default="": _load_hermes_env_value(env_name, default),
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


def is_complete_hermes_llm_config(config: LLMConfig) -> bool:
    spec = PROVIDER_SPECS[config.provider]
    if spec.requires_api_key and not config.api_key:
        return False
    if config.provider == "LiteLLM" and not config.base_url:
        return False
    return bool(config.model)


def require_complete_hermes_llm_config(config: LLMConfig) -> None:
    spec = PROVIDER_SPECS[config.provider]
    if config.provider == "LiteLLM" and not config.base_url:
        raise ValueError(f"Please set {spec.base_url_env} in the Hermes environment.")
    if spec.requires_api_key and not config.api_key:
        raise ValueError(f"Please set {spec.api_key_env} in the Hermes environment.")
    if not config.model:
        raise ValueError(f"Please choose a model for {config.provider} in the Hermes environment.")


def auto_select_hermes_llm_provider() -> str | None:
    available_providers = set(get_provider_names())
    for provider in HERMES_LLM_DISCOVERY_ORDER:
        if provider not in available_providers:
            continue
        if is_complete_hermes_llm_config(build_hermes_llm_config(provider)):
            return provider
    return None


def resolve_optional_hermes_llm_config(
    *,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
) -> LLMConfig | None:
    has_explicit_overrides = any(value is not None for value in (provider, api_key, model, base_url, api_mode))
    resolved_provider = provider or auto_select_hermes_llm_provider()

    if resolved_provider is None:
        if has_explicit_overrides:
            raise ValueError(
                "No complete LLM configuration was found in the Hermes environment. "
                "Pass provider with a complete override."
            )
        return None

    config = build_hermes_llm_config(
        resolved_provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )

    if has_explicit_overrides:
        require_complete_hermes_llm_config(config)
        return config

    return config if is_complete_hermes_llm_config(config) else None


def resolve_required_hermes_llm_config(
    *,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
) -> LLMConfig:
    config = resolve_optional_hermes_llm_config(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )
    if config is None:
        raise ValueError(
            "No complete LLM configuration was found in the Hermes environment. "
            "Configure LiteLLM, OpenAI, or Anthropic."
        )
    require_complete_hermes_llm_config(config)
    return config


__all__ = [
    "HERMES_LLM_DISCOVERY_ORDER",
    "auto_select_hermes_llm_provider",
    "build_hermes_llm_config",
    "is_complete_hermes_llm_config",
    "require_complete_hermes_llm_config",
    "resolve_optional_hermes_llm_config",
    "resolve_required_hermes_llm_config",
]
