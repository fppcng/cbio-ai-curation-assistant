"""Load and validate LLM provider settings at runtime."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence

from cbio_curation_assistant.llm.models import (
    LLMConfig,
    LLMSettings,
    ProviderName,
    ProviderSpec,
)

ValueLoader = Callable[[str, str], str]

DEFAULT_PROVIDER_ORDER: tuple[ProviderName, ...] = (
    "OpenAI",
    "Anthropic",
    "LiteLLM",
)
DEFAULT_DISCOVERY_ORDER: tuple[ProviderName, ...] = (
    "LiteLLM",
    "OpenAI",
    "Anthropic",
)

_ANTHROPIC_MODELS = (
    "claude-sonnet-4-20250514",
    "claude-3-5-haiku-20241022",
    "claude-3-5-sonnet-20241022",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-haiku-4-5-20251001",
)
_OPENAI_MODELS = (
    "gpt-4o",
    "gpt-5.5",
    "gpt-5.5-pro",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
)


def _mapping_loader(environment: Mapping[str, str]) -> ValueLoader:
    def load(name: str, default: str = "") -> str:
        return environment.get(name, "").strip() or default

    return load


def _runtime_loader(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


def _normalise_api_mode(value: str | None, default: str = "") -> str:
    return (value or "").strip().lower() or default


def load_llm_settings(
    *,
    environment: Mapping[str, str] | None = None,
    value_loader: ValueLoader | None = None,
) -> LLMSettings:
    """Build provider settings from the current or supplied environment."""
    if environment is not None and value_loader is not None:
        raise ValueError("Provide either environment or value_loader, not both.")

    load = (
        value_loader
        or (_mapping_loader(environment) if environment is not None else _runtime_loader)
    )
    litellm_api_key_env = load("LITELLM_API_KEY_ENV", "LITELLM_API_KEY")

    provider_specs = {
        "Anthropic": ProviderSpec(
            api_key_env="ANTHROPIC_API_KEY",
            default_model="claude-sonnet-4-20250514",
            model_env="ANTHROPIC_MODEL",
            model_choices=_ANTHROPIC_MODELS,
            default_api_mode="messages",
            api_modes=("messages",),
        ),
        "OpenAI": ProviderSpec(
            api_key_env="OPENAI_API_KEY",
            default_model="gpt-4o",
            model_env="OPENAI_MODEL",
            model_choices=_OPENAI_MODELS,
            api_mode_env="OPENAI_API_MODE",
            default_api_mode="responses",
            api_modes=("responses", "chat_completions"),
        ),
        "LiteLLM": ProviderSpec(
            api_key_env=litellm_api_key_env,
            default_model="openai/gpt-4o-mini",
            model_env="LITELLM_MODEL",
            base_url_env="LITELLM_BASE_URL",
            api_mode_env="LITELLM_API_MODE",
            default_api_mode="responses",
            api_modes=("responses", "chat_completions"),
            requires_base_url=True,
            supports_custom_model=True,
            reasoning_effort_env="LITELLM_REASONING_EFFORT",
            default_reasoning_effort="high",
        ),
    }
    provider_configs = {
        provider: LLMConfig(
            provider=provider,
            api_key=load(spec.api_key_env, ""),
            model=(
                load(spec.model_env, spec.default_model)
                if spec.model_env
                else spec.default_model
            ),
            base_url=(
                load(spec.base_url_env, spec.default_base_url)
                if spec.base_url_env
                else ""
            ),
            api_mode=_normalise_api_mode(
                (
                    load(spec.api_mode_env, spec.default_api_mode)
                    if spec.api_mode_env
                    else spec.default_api_mode
                ),
                spec.default_api_mode,
            ),
            reasoning_effort=(
                load(
                    spec.reasoning_effort_env,
                    spec.default_reasoning_effort,
                )
                if spec.reasoning_effort_env
                else spec.default_reasoning_effort
            ),
        )
        for provider, spec in provider_specs.items()
    }
    return LLMSettings(
        provider_order=DEFAULT_PROVIDER_ORDER,
        provider_specs=provider_specs,
        provider_configs=provider_configs,
    )


def get_provider_names(
    settings: LLMSettings | None = None,
) -> tuple[ProviderName, ...]:
    """Return providers in stable display order."""
    return (settings or load_llm_settings()).provider_order


def get_provider_spec(
    provider: ProviderName,
    *,
    settings: LLMSettings | None = None,
) -> ProviderSpec:
    """Return one provider specification with an explicit unknown-provider error."""
    resolved_settings = settings or load_llm_settings()
    try:
        return resolved_settings.provider_specs[provider]
    except KeyError as exc:
        raise ValueError(f"Unsupported LLM provider: {provider}") from exc


def build_llm_config(
    provider: ProviderName,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
    reasoning_effort: str | None = None,
    environment: Mapping[str, str] | None = None,
    value_loader: ValueLoader | None = None,
    settings: LLMSettings | None = None,
) -> LLMConfig:
    """Resolve one provider configuration at call time."""
    environment_sources = sum(
        source is not None
        for source in (environment, value_loader, settings)
    )
    if environment_sources > 1:
        raise ValueError(
            "Provide only one of environment, value_loader, or settings."
        )
    resolved_settings = settings or load_llm_settings(
        environment=environment,
        value_loader=value_loader,
    )
    spec = get_provider_spec(provider, settings=resolved_settings)
    defaults = resolved_settings.provider_configs[provider]
    resolved_model = (
        defaults.model if model is None else model.strip()
    ) or spec.default_model

    return LLMConfig(
        provider=provider,
        api_key=(defaults.api_key if api_key is None else api_key).strip(),
        model=resolved_model,
        base_url=(defaults.base_url if base_url is None else base_url).strip(),
        api_mode=_normalise_api_mode(
            defaults.api_mode if api_mode is None else api_mode,
            spec.default_api_mode,
        ),
        reasoning_effort=(
            defaults.reasoning_effort
            if reasoning_effort is None
            else reasoning_effort
        ).strip(),
    )


def is_complete_llm_config(
    config: LLMConfig,
    *,
    settings: LLMSettings | None = None,
) -> bool:
    """Return whether a resolved configuration can call its provider."""
    spec = get_provider_spec(config.provider, settings=settings)
    if spec.requires_api_key and not config.api_key:
        return False
    if spec.requires_base_url and not config.base_url:
        return False
    return bool(config.model)


def require_complete_llm_config(
    config: LLMConfig,
    *,
    settings: LLMSettings | None = None,
) -> None:
    """Raise a targeted error for the first missing required setting."""
    spec = get_provider_spec(config.provider, settings=settings)
    if spec.requires_base_url and not config.base_url:
        raise ValueError(f"Please set {spec.base_url_env} in the environment.")
    if spec.requires_api_key and not config.api_key:
        raise ValueError(f"Please set {spec.api_key_env} in the environment.")
    if not config.model:
        raise ValueError(f"Please choose a model for {config.provider}.")


def select_configured_llm_provider(
    *,
    discovery_order: Sequence[ProviderName] = DEFAULT_DISCOVERY_ORDER,
    environment: Mapping[str, str] | None = None,
    settings: LLMSettings | None = None,
) -> ProviderName | None:
    """Select the first complete provider in the requested discovery order."""
    resolved_settings = settings or load_llm_settings(environment=environment)
    available = set(get_provider_names(resolved_settings))
    for provider in discovery_order:
        if provider not in available:
            continue
        config = build_llm_config(
            provider,
            settings=resolved_settings,
        )
        if is_complete_llm_config(config, settings=resolved_settings):
            return provider
    return None


def resolve_optional_llm_config(
    *,
    provider: ProviderName | None = None,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
    reasoning_effort: str | None = None,
    discovery_order: Sequence[ProviderName] = DEFAULT_DISCOVERY_ORDER,
    environment: Mapping[str, str] | None = None,
) -> LLMConfig | None:
    """Resolve a complete provider configuration or return ``None``."""
    settings = load_llm_settings(environment=environment)
    has_overrides = any(
        value is not None
        for value in (
            provider,
            api_key,
            model,
            base_url,
            api_mode,
            reasoning_effort,
        )
    )
    resolved_provider = provider or select_configured_llm_provider(
        discovery_order=discovery_order,
        settings=settings,
    )
    if resolved_provider is None:
        if has_overrides:
            raise ValueError(
                "No complete LLM configuration was found. "
                "Pass a provider with complete overrides."
            )
        return None

    config = build_llm_config(
        resolved_provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
        reasoning_effort=reasoning_effort,
        settings=settings,
    )
    if has_overrides:
        require_complete_llm_config(config, settings=settings)
        return config
    return config if is_complete_llm_config(config, settings=settings) else None


def resolve_required_llm_config(**kwargs) -> LLMConfig:
    """Resolve a complete provider configuration or raise."""
    config = resolve_optional_llm_config(**kwargs)
    if config is None:
        raise ValueError(
            "No complete LLM configuration was found. "
            "Configure LiteLLM, OpenAI, or Anthropic."
        )
    require_complete_llm_config(config)
    return config


__all__ = [
    "DEFAULT_DISCOVERY_ORDER",
    "DEFAULT_PROVIDER_ORDER",
    "ValueLoader",
    "build_llm_config",
    "get_provider_names",
    "get_provider_spec",
    "is_complete_llm_config",
    "load_llm_settings",
    "require_complete_llm_config",
    "resolve_optional_llm_config",
    "resolve_required_llm_config",
    "select_configured_llm_provider",
]
