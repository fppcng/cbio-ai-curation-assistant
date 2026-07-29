"""Provider SDK adapters and retry behavior for text completion."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from cbio_curation_assistant.llm.models import LLMConfig

Sleep = Callable[[float], None]


def call_anthropic_with_retry(
    client,
    model: str,
    system: str,
    user_content: str,
    max_tokens: int = 2000,
    retries: int = 3,
    backoff: float = 5.0,
    *,
    sleep: Sleep = time.sleep,
) -> str:
    """Call Anthropic Messages with bounded retries for transient failures."""
    import anthropic

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_content}],
            )
            return response.content[0].text
        except anthropic.RateLimitError as exc:
            last_error = exc
            sleep(backoff * (attempt + 1))
        except anthropic.APIStatusError as exc:
            if exc.status_code < 500:
                raise
            last_error = exc
            sleep(backoff * (attempt + 1))
        except anthropic.APIConnectionError as exc:
            last_error = exc
            sleep(backoff * (attempt + 1))

    raise last_error or RuntimeError(
        "Anthropic API call failed after retries."
    )


def call_openai_chat_with_retry(
    client,
    model: str,
    system: str,
    user_content: str,
    max_tokens: int = 2000,
    retries: int = 3,
    backoff: float = 5.0,
    *,
    sleep: Sleep = time.sleep,
) -> str:
    """Call OpenAI Chat Completions with bounded transient-error retries."""
    import openai

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
            )
            content = response.choices[0].message.content or ""
            if not content:
                finish_reason = response.choices[0].finish_reason
                usage = getattr(response, "usage", None)
                raise RuntimeError(
                    "OpenAI returned an empty message content. "
                    f"finish_reason={finish_reason}, usage={usage}"
                )
            return content
        except openai.RateLimitError as exc:
            last_error = exc
            sleep(backoff * (attempt + 1))
        except openai.APIStatusError as exc:
            if exc.status_code < 500:
                raise
            last_error = exc
            sleep(backoff * (attempt + 1))
        except openai.APIConnectionError as exc:
            last_error = exc
            sleep(backoff * (attempt + 1))

    raise last_error or RuntimeError("OpenAI API call failed after retries.")


def call_openai_responses_with_retry(
    client,
    model: str,
    system: str,
    user_content: str,
    max_tokens: int = 2000,
    retries: int = 3,
    backoff: float = 5.0,
    *,
    sleep: Sleep = time.sleep,
) -> str:
    """Call OpenAI Responses with bounded transient-error retries."""
    import openai

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                max_output_tokens=max_tokens,
            )
            content = (response.output_text or "").strip()
            if not content:
                raise RuntimeError(
                    "OpenAI Responses API returned an empty output_text."
                )
            return content
        except openai.RateLimitError as exc:
            last_error = exc
            sleep(backoff * (attempt + 1))
        except openai.APIStatusError as exc:
            if exc.status_code < 500:
                raise
            last_error = exc
            sleep(backoff * (attempt + 1))
        except openai.APIConnectionError as exc:
            last_error = exc
            sleep(backoff * (attempt + 1))

    raise last_error or RuntimeError(
        "OpenAI Responses API call failed after retries."
    )


def call_litellm_chat_with_retry(
    model: str,
    system: str,
    user_content: str,
    api_key: str | None = None,
    base_url: str | None = None,
    max_tokens: int = 2000,
    retries: int = 3,
    backoff: float = 5.0,
    *,
    reasoning_effort: str = "high",
    sleep: Sleep = time.sleep,
    completion_fn: Callable[..., Any] | None = None,
) -> str:
    """Call LiteLLM Chat Completions with injectable retry dependencies."""
    if completion_fn is None:
        from litellm import completion

        completion_fn = completion

    resolved_base_url = (base_url or "").strip()
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": max_tokens,
            }
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort
            if api_key:
                kwargs["api_key"] = api_key
            if resolved_base_url:
                kwargs["api_base"] = resolved_base_url.rstrip("/")

            response = completion_fn(**kwargs)
            content = response.choices[0].message.content or ""
            if not content:
                raise RuntimeError(
                    "LiteLLM returned an empty message content."
                )
            return content
        except Exception as exc:
            last_error = exc
            status_code = getattr(exc, "status_code", None)
            retryable_names = {
                "RateLimitError",
                "APIConnectionError",
                "ServiceUnavailableError",
                "InternalServerError",
                "Timeout",
            }
            if exc.__class__.__name__ in retryable_names or (
                isinstance(status_code, int) and status_code >= 500
            ):
                sleep(backoff * (attempt + 1))
                continue
            raise

    raise last_error or RuntimeError("LiteLLM API call failed after retries.")


def build_anthropic_client(config: LLMConfig):
    """Build an Anthropic SDK client from resolved configuration."""
    import anthropic

    return anthropic.Anthropic(api_key=config.api_key)


def build_openai_client(config: LLMConfig):
    """Build an OpenAI-compatible SDK client from resolved configuration."""
    from openai import OpenAI

    client_kwargs: dict[str, Any] = {}
    if config.api_key:
        client_kwargs["api_key"] = config.api_key
    if config.base_url:
        client_kwargs["base_url"] = config.base_url.rstrip("/")
    return OpenAI(**client_kwargs)


__all__ = [
    "build_anthropic_client",
    "build_openai_client",
    "call_anthropic_with_retry",
    "call_litellm_chat_with_retry",
    "call_openai_chat_with_retry",
    "call_openai_responses_with_retry",
]
