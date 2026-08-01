"""JSON file IO used by command adapters."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def load_json_object(path: Path, *, description: str) -> dict[str, Any]:
    """Load a JSON object or raise a descriptive validation error."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{description} must be a JSON object.")
    return payload


def write_json_object(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON object to a caller-selected output path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


__all__ = ["load_json_object", "write_json_object"]
