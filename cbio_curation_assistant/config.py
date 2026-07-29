"""Compatibility imports for the public :mod:`cbio_curation_assistant.llm` API."""

from __future__ import annotations

import os

from cbio_curation_assistant.llm.models import (
    LLMConfig,
    ProviderName,
    ProviderSpec,
)
from cbio_curation_assistant.llm.settings import (
    DEFAULT_PROVIDER_ORDER,
    ValueLoader,
    build_llm_config,
    get_provider_names,
)

PROVIDER_ORDER = DEFAULT_PROVIDER_ORDER


def read_provider_value(env_name: str | None, default: str = "") -> str:
    """Read one provider value from the current process environment."""
    if not env_name:
        return default
    return os.environ.get(env_name, "").strip() or default


def get_provider_default_config(
    provider: ProviderName,
    value_loader: ValueLoader | None = None,
) -> LLMConfig:
    """Compatibility wrapper for runtime provider configuration."""
    return build_llm_config(provider, value_loader=value_loader)


__all__ = [
    "LLMConfig",
    "PROVIDER_ORDER",
    "ProviderName",
    "ProviderSpec",
    "get_provider_default_config",
    "get_provider_names",
    "read_provider_value",
]
