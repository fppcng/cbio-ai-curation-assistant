"""Public provider-agnostic LLM configuration and completion APIs."""

from cbio_curation_assistant.llm.client import (
    ConfiguredCompletionClient,
    complete_text,
)
from cbio_curation_assistant.llm.models import (
    CompletionClient,
    LLMConfig,
    LLMSettings,
    ProviderName,
    ProviderSpec,
)
from cbio_curation_assistant.llm.parsing import parse_llm_json
from cbio_curation_assistant.llm.settings import (
    DEFAULT_DISCOVERY_ORDER,
    DEFAULT_PROVIDER_ORDER,
    build_llm_config,
    get_provider_names,
    get_provider_spec,
    is_complete_llm_config,
    load_llm_settings,
    require_complete_llm_config,
    resolve_optional_llm_config,
    resolve_required_llm_config,
    select_configured_llm_provider,
)

__all__ = [
    "CompletionClient",
    "ConfiguredCompletionClient",
    "DEFAULT_DISCOVERY_ORDER",
    "DEFAULT_PROVIDER_ORDER",
    "LLMConfig",
    "LLMSettings",
    "ProviderName",
    "ProviderSpec",
    "build_llm_config",
    "complete_text",
    "get_provider_names",
    "get_provider_spec",
    "is_complete_llm_config",
    "load_llm_settings",
    "parse_llm_json",
    "require_complete_llm_config",
    "resolve_optional_llm_config",
    "resolve_required_llm_config",
    "select_configured_llm_provider",
]
