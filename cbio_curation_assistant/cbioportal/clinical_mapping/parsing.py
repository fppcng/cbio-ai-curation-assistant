"""Primitive validation helpers for mapping JSON contracts."""

from __future__ import annotations

from typing import Any


def require_nonempty_string(
    value: Any,
    *,
    field: str,
    context: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} requires non-empty string field {field!r}.")
    return value.strip()


def optional_string(value: Any, *, field: str, context: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{context} {field} must be a string when provided.")
    return value.strip() or None


__all__ = ["optional_string", "require_nonempty_string"]
