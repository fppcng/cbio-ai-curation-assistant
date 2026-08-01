"""Shared human-readable presentation values for curation reports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def format_curability(value: str) -> str:
    """Render a canonical curability value for human-readable reports."""
    normalized = str(value or "").strip().upper()
    return {
        "YES": "Yes",
        "PARTIAL": "Partly curatable",
        "NO": "Needs manual intervention",
    }.get(normalized, str(value or "").strip() or "—")


def format_label(value: str) -> str:
    """Render exceptional classification labels without altering file names."""
    text = str(value or "").strip()
    return {
        "NOT_LOADABLE": "Needs manual intervention",
        "Not directly loadable": "Needs manual intervention",
    }.get(text, text or "—")


def build_publication(metadata: Mapping[str, Any]) -> str:
    """Build the compact journal-and-year publication label."""
    return " ".join(
        str(item).strip()
        for item in [metadata.get("journal", ""), metadata.get("year", "")]
        if str(item).strip()
    )


__all__ = ["build_publication", "format_curability", "format_label"]
