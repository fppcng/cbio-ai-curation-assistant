from __future__ import annotations

import json
import logging
import time
import re
from typing import Any

from config import LITELLM_REASONING_EFFORT, LLMConfig, build_llm_config

logger = logging.getLogger(__name__)


def call_anthropic_with_retry(
    client,
    model: str,
    system: str,
    user_content: str,
    max_tokens: int = 2000,
    retries: int = 3,
    backoff: float = 5.0,
) -> str:
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
            time.sleep(backoff * (attempt + 1))
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                last_error = exc
                time.sleep(backoff * (attempt + 1))
            else:
                raise
        except anthropic.APIConnectionError as exc:
            last_error = exc
            time.sleep(backoff * (attempt + 1))

    raise last_error or RuntimeError("Anthropic API call failed after retries.")


def call_openai_chat_with_retry(
    client,
    model: str,
    system: str,
    user_content: str,
    max_tokens: int = 2000,
    retries: int = 3,
    backoff: float = 5.0,
) -> str:
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
            time.sleep(backoff * (attempt + 1))
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                last_error = exc
                time.sleep(backoff * (attempt + 1))
            else:
                raise
        except openai.APIConnectionError as exc:
            last_error = exc
            time.sleep(backoff * (attempt + 1))

    raise last_error or RuntimeError("OpenAI API call failed after retries.")


def call_openai_responses_with_retry(
    client,
    model: str,
    system: str,
    user_content: str,
    max_tokens: int = 2000,
    retries: int = 3,
    backoff: float = 5.0,
) -> str:
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
                raise RuntimeError("OpenAI Responses API returned an empty output_text.")
            return content
        except openai.RateLimitError as exc:
            last_error = exc
            time.sleep(backoff * (attempt + 1))
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                last_error = exc
                time.sleep(backoff * (attempt + 1))
            else:
                raise
        except openai.APIConnectionError as exc:
            last_error = exc
            time.sleep(backoff * (attempt + 1))

    raise last_error or RuntimeError("OpenAI Responses API call failed after retries.")


def call_litellm_chat_with_retry(
    model: str,
    system: str,
    user_content: str,
    api_key: str | None = None,
    base_url: str | None = None,
    max_tokens: int = 2000,
    retries: int = 3,
    backoff: float = 5.0,
) -> str:
    from litellm import completion

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
                "reasoning_effort": LITELLM_REASONING_EFFORT,
            }
            if api_key:
                kwargs["api_key"] = api_key
            if resolved_base_url:
                kwargs["api_base"] = resolved_base_url.rstrip("/")

            response = completion(**kwargs)
            content = response.choices[0].message.content or ""
            if not content:
                raise RuntimeError("LiteLLM returned an empty message content.")
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
                time.sleep(backoff * (attempt + 1))
                continue
            raise

    raise last_error or RuntimeError("LiteLLM API call failed after retries.")


def _resolve_llm_config(
    *,
    config: LLMConfig | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_mode: str | None = None,
) -> LLMConfig:
    if config is not None:
        return config
    if not provider:
        raise ValueError("provider or config is required")
    return build_llm_config(
        provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )


def _build_openai_client(config: LLMConfig):
    from openai import OpenAI

    client_kwargs: dict[str, Any] = {}
    if config.api_key:
        client_kwargs["api_key"] = config.api_key
    if config.base_url:
        client_kwargs["base_url"] = config.base_url.rstrip("/")
    return OpenAI(**client_kwargs)


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


def _should_retry_litellm_as_responses(config: LLMConfig, exc: Exception) -> bool:
    if config.provider != "LiteLLM":
        return False
    if config.api_mode not in {"", "chat_completions"}:
        return False
    if not config.base_url:
        return False
    return _http_status_code(exc) == 404


def call_llm_with_retry(
    *,
    config: LLMConfig | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    system: str,
    user_content: str,
    max_tokens: int = 2000,
    base_url: str | None = None,
    api_mode: str | None = None,
) -> str:
    resolved = _resolve_llm_config(
        config=config,
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        api_mode=api_mode,
    )

    if resolved.provider == "Anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=resolved.api_key)
        return call_anthropic_with_retry(
            client=client,
            model=resolved.model,
            system=system,
            user_content=user_content,
            max_tokens=max_tokens,
        )

    if resolved.provider == "OpenAI":
        client = _build_openai_client(resolved)
        if resolved.api_mode == "responses":
            return call_openai_responses_with_retry(
                client=client,
                model=resolved.model,
                system=system,
                user_content=user_content,
                max_tokens=max_tokens,
            )
        return call_openai_chat_with_retry(
            client=client,
            model=resolved.model,
            system=system,
            user_content=user_content,
            max_tokens=max_tokens,
        )

    if resolved.provider == "LiteLLM":
        if resolved.api_mode == "responses":
            client = _build_openai_client(resolved)
            return call_openai_responses_with_retry(
                client=client,
                model=resolved.model,
                system=system,
                user_content=user_content,
                max_tokens=max_tokens,
            )
        try:
            return call_litellm_chat_with_retry(
                model=resolved.model,
                system=system,
                user_content=user_content,
                api_key=resolved.api_key or None,
                base_url=resolved.base_url,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            if not _should_retry_litellm_as_responses(resolved, exc):
                raise

            logger.warning(
                "LiteLLM chat_completions returned 404; retrying with responses. "
                "Set LITELLM_API_MODE=responses to make this explicit. model=%s base_url=%s",
                resolved.model,
                resolved.base_url,
            )
            client = _build_openai_client(resolved)
            return call_openai_responses_with_retry(
                client=client,
                model=resolved.model,
                system=system,
                user_content=user_content,
                max_tokens=max_tokens,
            )

    raise ValueError(f"Unsupported LLM provider: {resolved.provider}")


def _extract_json_object_text(raw: str) -> str:
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start : end + 1]
    return raw


def _strip_json_comments(raw: str) -> str:
    result: list[str] = []
    index = 0
    in_string = False
    escaped = False

    while index < len(raw):
        char = raw[index]

        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == "/" and index + 1 < len(raw):
            next_char = raw[index + 1]
            if next_char == "/":
                index += 2
                while index < len(raw) and raw[index] != "\n":
                    index += 1
                continue
            if next_char == "*":
                index += 2
                while index + 1 < len(raw) and raw[index : index + 2] != "*/":
                    index += 1
                index = min(index + 2, len(raw))
                continue

        result.append(char)
        index += 1

    return "".join(result)


def _strip_trailing_commas(raw: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", raw)


def parse_llm_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```[^\n]*\n?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()

    candidates = [cleaned]
    extracted = _extract_json_object_text(cleaned)
    if extracted != cleaned:
        candidates.append(extracted)

    last_error: Exception | None = None
    for candidate in candidates:
        normalized = _strip_trailing_commas(_strip_json_comments(candidate)).strip()
        if not normalized:
            continue
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue

        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except json.JSONDecodeError:
                pass

        if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
            parsed = parsed[0]

        if isinstance(parsed, dict):
            return parsed

        last_error = ValueError(f"LLM JSON payload is not an object: {type(parsed).__name__}")

    raise last_error or ValueError("LLM output did not contain a valid JSON object.")
