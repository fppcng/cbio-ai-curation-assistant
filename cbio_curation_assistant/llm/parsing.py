"""Parse structured JSON objects from imperfect LLM text output."""

from __future__ import annotations

import json
import re
from typing import Any


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
    """Return one JSON object after conservative common-output repairs."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```[^\n]*\n?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()

    candidates = [cleaned]
    extracted = _extract_json_object_text(cleaned)
    if extracted != cleaned:
        candidates.append(extracted)

    last_error: Exception | None = None
    for candidate in candidates:
        normalized = _strip_trailing_commas(
            _strip_json_comments(candidate)
        ).strip()
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

        if (
            isinstance(parsed, list)
            and len(parsed) == 1
            and isinstance(parsed[0], dict)
        ):
            parsed = parsed[0]

        if isinstance(parsed, dict):
            return parsed

        last_error = ValueError(
            f"LLM JSON payload is not an object: {type(parsed).__name__}"
        )

    raise last_error or ValueError(
        "LLM output did not contain a valid JSON object."
    )


__all__ = ["parse_llm_json"]
