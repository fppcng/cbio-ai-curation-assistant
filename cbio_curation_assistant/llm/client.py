"""Provider-agnostic completion client and provider routing."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from cbio_curation_assistant.llm import providers
from cbio_curation_assistant.llm.models import LLMConfig

logger = logging.getLogger(__name__)


def _http_status_code(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status

    message = str(exc)
    if "404" in message and "Not Found" in message:
        return 404
    return None


def _should_retry_litellm_as_responses(
    config: LLMConfig,
    exc: Exception,
) -> bool:
    if config.provider != "LiteLLM":
        return False
    if config.api_mode not in {"", "chat_completions"}:
        return False
    if not config.base_url:
        return False
    return _http_status_code(exc) == 404


def complete_text(
    *,
    config: LLMConfig,
    system: str,
    user_content: str,
    max_tokens: int = 2000,
) -> str:
    """Route one text completion through the configured provider."""
    if config.provider == "Anthropic":
        return providers.call_anthropic_with_retry(
            client=providers.build_anthropic_client(config),
            model=config.model,
            system=system,
            user_content=user_content,
            max_tokens=max_tokens,
        )

    if config.provider == "OpenAI":
        client = providers.build_openai_client(config)
        if config.api_mode == "responses":
            return providers.call_openai_responses_with_retry(
                client=client,
                model=config.model,
                system=system,
                user_content=user_content,
                max_tokens=max_tokens,
            )
        return providers.call_openai_chat_with_retry(
            client=client,
            model=config.model,
            system=system,
            user_content=user_content,
            max_tokens=max_tokens,
        )

    if config.provider == "LiteLLM":
        if config.api_mode == "responses":
            return providers.call_openai_responses_with_retry(
                client=providers.build_openai_client(config),
                model=config.model,
                system=system,
                user_content=user_content,
                max_tokens=max_tokens,
            )
        try:
            return providers.call_litellm_chat_with_retry(
                model=config.model,
                system=system,
                user_content=user_content,
                api_key=config.api_key or None,
                base_url=config.base_url,
                max_tokens=max_tokens,
                reasoning_effort=config.reasoning_effort or "high",
            )
        except Exception as exc:
            if not _should_retry_litellm_as_responses(config, exc):
                raise

            logger.warning(
                "LiteLLM chat_completions returned 404; retrying with "
                "responses. Set LITELLM_API_MODE=responses to make this "
                "explicit. model=%s base_url=%s",
                config.model,
                config.base_url,
            )
            return providers.call_openai_responses_with_retry(
                client=providers.build_openai_client(config),
                model=config.model,
                system=system,
                user_content=user_content,
                max_tokens=max_tokens,
            )

    raise ValueError(f"Unsupported LLM provider: {config.provider}")


@dataclass(frozen=True, slots=True)
class ConfiguredCompletionClient:
    """Reusable completion client bound to one resolved provider config."""

    config: LLMConfig

    def complete(
        self,
        *,
        system: str,
        user_content: str,
        max_tokens: int = 2000,
    ) -> str:
        return complete_text(
            config=self.config,
            system=system,
            user_content=user_content,
            max_tokens=max_tokens,
        )


__all__ = ["ConfiguredCompletionClient", "complete_text"]
