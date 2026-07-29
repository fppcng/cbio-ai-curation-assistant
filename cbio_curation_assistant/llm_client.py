"""Compatibility facade for the public :mod:`cbio_curation_assistant.llm` API."""

from cbio_curation_assistant.llm.client import (
    _should_retry_litellm_as_responses,
    complete_text,
)
from cbio_curation_assistant.llm.parsing import parse_llm_json
from cbio_curation_assistant.llm.providers import (
    build_openai_client as _build_openai_client,
    call_anthropic_with_retry,
    call_litellm_chat_with_retry,
    call_openai_chat_with_retry,
    call_openai_responses_with_retry,
)

call_llm_with_retry = complete_text

__all__ = [
    "_build_openai_client",
    "_should_retry_litellm_as_responses",
    "call_anthropic_with_retry",
    "call_litellm_chat_with_retry",
    "call_llm_with_retry",
    "call_openai_chat_with_retry",
    "call_openai_responses_with_retry",
    "parse_llm_json",
]
