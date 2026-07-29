"""Provider-agnostic LLM configuration and completion contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

ProviderName = str


@dataclass(frozen=True, slots=True)
class LLMConfig:
    """Resolved configuration for one completion provider."""

    provider: ProviderName
    api_key: str
    model: str
    base_url: str = ""
    api_mode: str = ""
    reasoning_effort: str = ""


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Static capabilities and environment keys for one provider."""

    api_key_env: str
    default_model: str
    model_env: str | None = None
    model_choices: tuple[str, ...] = ()
    base_url_env: str | None = None
    default_base_url: str = ""
    api_mode_env: str | None = None
    default_api_mode: str = ""
    api_modes: tuple[str, ...] = ()
    requires_api_key: bool = True
    requires_base_url: bool = False
    supports_custom_model: bool = False
    reasoning_effort_env: str | None = None
    default_reasoning_effort: str = ""


@dataclass(frozen=True, slots=True)
class LLMSettings:
    """Provider specifications resolved from one environment snapshot."""

    provider_order: tuple[ProviderName, ...]
    provider_specs: Mapping[ProviderName, ProviderSpec]
    provider_configs: Mapping[ProviderName, LLMConfig]


@runtime_checkable
class CompletionClient(Protocol):
    """Minimal completion interface used by domain workflows."""

    def complete(
        self,
        *,
        system: str,
        user_content: str,
        max_tokens: int = 2000,
    ) -> str:
        """Return provider text for one system and user prompt."""


__all__ = [
    "CompletionClient",
    "LLMConfig",
    "LLMSettings",
    "ProviderName",
    "ProviderSpec",
]
