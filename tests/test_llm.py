from __future__ import annotations

import os
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cbio_curation_assistant.llm.client as client_module
from cbio_curation_assistant.config import LLMConfig as LegacyLLMConfig
from cbio_curation_assistant.hermes_llm import (
    resolve_optional_hermes_llm_config,
)
from cbio_curation_assistant.llm import (
    CompletionClient,
    ConfiguredCompletionClient,
    LLMConfig,
    build_llm_config,
    complete_text,
    parse_llm_json,
    resolve_optional_llm_config,
)
from cbio_curation_assistant.llm.providers import (
    call_litellm_chat_with_retry,
)
from cbio_curation_assistant.llm_client import (
    call_llm_with_retry as legacy_complete_text,
)
from cbio_curation_assistant.llm_client import (
    parse_llm_json as legacy_parse_llm_json,
)


class LlmSettingsTest(unittest.TestCase):
    def test_provider_configuration_reads_environment_at_call_time(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            first = build_llm_config("OpenAI")
            os.environ["OPENAI_API_KEY"] = "runtime-key"
            os.environ["OPENAI_MODEL"] = "gpt-5"
            second = build_llm_config("OpenAI")

        self.assertEqual(first.api_key, "")
        self.assertEqual(first.model, "gpt-4o")
        self.assertEqual(second.api_key, "runtime-key")
        self.assertEqual(second.model, "gpt-5")

    def test_settings_and_parsing_do_not_import_provider_sdks(self) -> None:
        code = """
import sys
from cbio_curation_assistant.llm import build_llm_config, parse_llm_json
build_llm_config("OpenAI", environment={"OPENAI_API_KEY": "key"})
parse_llm_json('{"ok": true}')
loaded = sorted(
    name for name in ("anthropic", "litellm", "openai")
    if name in sys.modules
)
if loaded:
    raise SystemExit(",".join(loaded))
"""
        completed = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_litellm_settings_include_mode_and_reasoning_effort(self) -> None:
        config = build_llm_config(
            "LiteLLM",
            environment={
                "LITELLM_API_KEY": "proxy-key",
                "LITELLM_BASE_URL": "https://proxy.example/",
                "LITELLM_MODEL": "custom/model",
                "LITELLM_API_MODE": "chat_completions",
                "LITELLM_REASONING_EFFORT": "medium",
            },
        )

        self.assertEqual(config.api_key, "proxy-key")
        self.assertEqual(config.base_url, "https://proxy.example/")
        self.assertEqual(config.model, "custom/model")
        self.assertEqual(config.api_mode, "chat_completions")
        self.assertEqual(config.reasoning_effort, "medium")

    def test_optional_resolution_uses_explicit_discovery_order(self) -> None:
        config = resolve_optional_llm_config(
            environment={
                "OPENAI_API_KEY": "openai-key",
                "ANTHROPIC_API_KEY": "anthropic-key",
            },
            discovery_order=("Anthropic", "OpenAI"),
        )

        self.assertIsNotNone(config)
        self.assertEqual(config.provider, "Anthropic")

    def test_hermes_adapter_uses_general_runtime_resolution(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "key",
                "OPENAI_MODEL": "gpt-4.1",
                "LITELLM_API_KEY": "",
                "LITELLM_BASE_URL": "",
                "ANTHROPIC_API_KEY": "",
            },
            clear=True,
        ):
            config = resolve_optional_hermes_llm_config()

        self.assertIsNotNone(config)
        self.assertEqual(config.provider, "OpenAI")
        self.assertEqual(config.model, "gpt-4.1")


class LlmJsonParsingTest(unittest.TestCase):
    def test_parser_accepts_fences_comments_trailing_commas_and_text(self) -> None:
        raw = """
        Here is the result:
        ```json
        {
          // a line comment
          "study": "value", /* block comment */
          "items": [1, 2,],
        }
        ```
        """
        self.assertEqual(
            parse_llm_json(raw),
            {"study": "value", "items": [1, 2]},
        )

    def test_parser_unwraps_single_object_lists_and_double_encoded_json(
        self,
    ) -> None:
        self.assertEqual(parse_llm_json('[{"value": 1}]'), {"value": 1})
        self.assertEqual(parse_llm_json('"{\\"value\\": 1}"'), {"value": 1})

    def test_parser_rejects_non_object_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "not an object"):
            parse_llm_json("[1, 2]")

    def test_legacy_parser_facade_uses_public_parser(self) -> None:
        self.assertIs(legacy_parse_llm_json, parse_llm_json)


class LlmClientTest(unittest.TestCase):
    def test_configured_client_implements_provider_agnostic_contract(self) -> None:
        configured = ConfiguredCompletionClient(
            LLMConfig(provider="OpenAI", api_key="key", model="model")
        )

        self.assertIsInstance(configured, CompletionClient)

    def test_provider_router_rejects_unknown_providers(self) -> None:
        config = LLMConfig(provider="Other", api_key="", model="model")
        with self.assertRaisesRegex(ValueError, "Unsupported LLM provider"):
            complete_text(config=config, system="system", user_content="user")

    def test_openai_responses_mode_uses_responses_adapter(self) -> None:
        config = LLMConfig(
            provider="OpenAI",
            api_key="key",
            model="model",
            api_mode="responses",
        )
        sdk_client = Mock()
        with (
            patch.object(
                client_module.providers,
                "build_openai_client",
                return_value=sdk_client,
            ),
            patch.object(
                client_module.providers,
                "call_openai_responses_with_retry",
                return_value="response",
            ) as responses,
        ):
            result = complete_text(
                config=config,
                system="system",
                user_content="user",
                max_tokens=12,
            )

        self.assertEqual(result, "response")
        responses.assert_called_once_with(
            client=sdk_client,
            model="model",
            system="system",
            user_content="user",
            max_tokens=12,
        )

    def test_litellm_404_falls_back_to_openai_responses(self) -> None:
        class StatusError(Exception):
            status_code = 404

        config = LLMConfig(
            provider="LiteLLM",
            api_key="key",
            model="model",
            base_url="https://proxy.example",
            api_mode="chat_completions",
            reasoning_effort="medium",
        )
        sdk_client = Mock()
        with (
            patch.object(
                client_module.providers,
                "call_litellm_chat_with_retry",
                side_effect=StatusError("not found"),
            ) as chat,
            patch.object(
                client_module.providers,
                "build_openai_client",
                return_value=sdk_client,
            ),
            patch.object(
                client_module.providers,
                "call_openai_responses_with_retry",
                return_value="fallback",
            ) as responses,
        ):
            result = complete_text(
                config=config,
                system="system",
                user_content="user",
            )

        self.assertEqual(result, "fallback")
        self.assertEqual(chat.call_args.kwargs["reasoning_effort"], "medium")
        responses.assert_called_once()

    def test_litellm_retry_uses_injected_sleep_without_network(self) -> None:
        RateLimitError = type("RateLimitError", (Exception,), {})
        attempts = 0

        def completion(**_kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RateLimitError("retry")
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="completed")
                    )
                ]
            )

        sleep = Mock()
        result = call_litellm_chat_with_retry(
            model="model",
            system="system",
            user_content="user",
            retries=3,
            backoff=2,
            sleep=sleep,
            completion_fn=completion,
        )

        self.assertEqual(result, "completed")
        self.assertEqual(sleep.call_args_list[0].args, (2,))
        self.assertEqual(sleep.call_args_list[1].args, (4,))

    def test_legacy_client_facade_uses_public_completion_function(self) -> None:
        self.assertIs(legacy_complete_text, complete_text)
        self.assertIs(LegacyLLMConfig, LLMConfig)


if __name__ == "__main__":
    unittest.main()
