"""
config.py
---------
Central configuration for cBioAbstractor.
All tunable constants live here, including explicit LLM provider settings.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE / ".env", override=False)

ProviderName = str
ValueLoader = Callable[[str, str], str]


@dataclass(frozen=True)
class LLMConfig:
    provider: ProviderName
    api_key: str
    model: str
    base_url: str = ""
    api_mode: str = ""


@dataclass(frozen=True)
class ProviderSpec:
    api_key_env: str
    placeholder: str
    default_model: str
    model_env: str | None = None
    model_choices: tuple[str, ...] = ()
    base_url_env: str | None = None
    default_base_url: str = ""
    api_mode_env: str | None = None
    default_api_mode: str = ""
    api_modes: tuple[str, ...] = ()
    requires_api_key: bool = True
    supports_custom_model: bool = False


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _normalise_api_mode(value: str | None, default: str = "") -> str:
    clean = (value or "").strip().lower()
    return clean or default


# ── Paths ─────────────────────────────────────────────────────────────────────
FEW_SHOT_DIR = _env("FEW_SHOT_DIR", "./few_shot_examples")

# ── Detection / transform settings ────────────────────────────────────────────
DETECTION_SAMPLE_ROWS = 10
TRANSFORM_SAMPLE_ROWS = 20
DETECTION_CONFIDENCE_THRESHOLD = 0.6

# ── Explicit provider settings ────────────────────────────────────────────────
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o")
OPENAI_API_MODE = "responses"

LITELLM_API_KEY_ENV = _env("LITELLM_API_KEY_ENV", "LITELLM_API_KEY")
LITELLM_BASE_URL = _env("LITELLM_BASE_URL")
LITELLM_MODEL = _env("LITELLM_MODEL", "openai/gpt-4o-mini")
LITELLM_API_MODE = "responses"
LITELLM_REASONING_EFFORT = _env("LITELLM_REASONING_EFFORT", "high")

PROVIDER_ORDER: tuple[ProviderName, ...] = ("OpenAI", "Anthropic", "LiteLLM")

PROVIDER_SPECS: dict[ProviderName, ProviderSpec] = {
    "Anthropic": ProviderSpec(
        api_key_env=ANTHROPIC_API_KEY_ENV,
        placeholder="sk-ant-...",
        default_model=ANTHROPIC_MODEL,
        model_env="ANTHROPIC_MODEL",
        model_choices=(
            "claude-sonnet-4-20250514",
            "claude-3-5-haiku-20241022",
            "claude-3-5-sonnet-20241022",
            "claude-sonnet-4-6",
            "claude-opus-4-6",
            "claude-haiku-4-5-20251001",
        ),
        default_api_mode="messages",
        api_modes=("messages",),
    ),
    "OpenAI": ProviderSpec(
        api_key_env=OPENAI_API_KEY_ENV,
        placeholder="sk-...",
        default_model=OPENAI_MODEL,
        model_env="OPENAI_MODEL",
        model_choices=(
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
        ),
        default_api_mode=OPENAI_API_MODE,
        api_modes=("responses",),
    ),
    "LiteLLM": ProviderSpec(
        api_key_env=LITELLM_API_KEY_ENV,
        placeholder="proxy key",
        default_model=LITELLM_MODEL,
        model_env="LITELLM_MODEL",
        model_choices=(LITELLM_MODEL,),
        base_url_env="LITELLM_BASE_URL",
        default_base_url=LITELLM_BASE_URL,
        default_api_mode=LITELLM_API_MODE,
        api_modes=(LITELLM_API_MODE,),
        requires_api_key=True,
        supports_custom_model=True,
    ),
}

LEGACY_PROVIDER_PREFIXES = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "litellm": "LiteLLM",
}


def get_provider_names() -> tuple[ProviderName, ...]:
    return PROVIDER_ORDER


def read_provider_value(env_name: str | None, default: str = "") -> str:
    if not env_name:
        return default
    return _env(env_name, default)


def get_provider_default_config(
    provider: ProviderName,
    value_loader: ValueLoader | None = None,
) -> LLMConfig:
    spec = PROVIDER_SPECS[provider]
    load = value_loader or read_provider_value
    api_key = load(spec.api_key_env, "")
    model = load(spec.model_env, spec.default_model) if spec.model_env else spec.default_model
    base_url = load(spec.base_url_env, spec.default_base_url) if spec.base_url_env else ""
    api_mode = load(spec.api_mode_env, spec.default_api_mode) if spec.api_mode_env else spec.default_api_mode
    if spec.model_choices and model not in spec.model_choices and not spec.supports_custom_model:
        model = spec.default_model
    return LLMConfig(
        provider=provider,
        api_key=api_key,
        model=model or spec.default_model,
        base_url=base_url,
        api_mode=_normalise_api_mode(api_mode, spec.default_api_mode),
    )


def build_llm_config(
    provider: ProviderName,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
) -> LLMConfig:
    default = get_provider_default_config(provider)
    return LLMConfig(
        provider=provider,
        api_key=(default.api_key if api_key is None else api_key).strip(),
        model=(default.model if model is None else model).strip() or default.model,
        base_url=(default.base_url if base_url is None else base_url).strip(),
        api_mode=_normalise_api_mode(
            default.api_mode if api_mode is None else api_mode,
            PROVIDER_SPECS[provider].default_api_mode,
        ),
    )


def with_model(config: LLMConfig, model: str) -> LLMConfig:
    return replace(config, model=model.strip() or config.model)


def build_llm_config_from_legacy_model(
    llm_model: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
) -> LLMConfig:
    provider = "OpenAI"
    model = (llm_model or "").strip()
    if "/" in model:
        prefix, resolved_model = model.split("/", 1)
        mapped_provider = LEGACY_PROVIDER_PREFIXES.get(prefix.strip().lower())
        if mapped_provider:
            provider = mapped_provider
            model = resolved_model.strip()
    return build_llm_config(
        provider,
        api_key=api_key,
        model=model or None,
        base_url=base_url,
        api_mode=api_mode,
    )
