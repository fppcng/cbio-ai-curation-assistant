"""Resolve embedded specifications and explicitly inspect the live source.

Normal runtime classification uses :func:`get_embedded_spec`, which only reads
package data. Network access is limited to the explicitly named live refresh
and comparison operations in this module.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Optional

import requests

from cbio_curation_assistant.cbioportal.specs import (
    EMBEDDED_SPEC_VERSION,
    SPECS,
    FormatSpec,
    verify_embedded_specifications,
)

logger = logging.getLogger(__name__)

_RAW_URL = (
    "https://raw.githubusercontent.com/cBioPortal/cbioportal/"
    "master/docs/File-Formats.md"
)
CACHE_TTL_SECONDS = 3600
FETCH_TIMEOUT = 15

_CACHE: dict[str, Any] = {
    "result": None,
    "ts": 0.0,
}

# Maps lowercase heading fragments to FormatSpec keys.
_SECTION_MAP = [
    ("patient attributes", "CLINICAL_PATIENT"),
    ("clinical patient", "CLINICAL_PATIENT"),
    ("sample attributes", "CLINICAL_SAMPLE"),
    ("clinical sample", "CLINICAL_SAMPLE"),
    ("mutation data", "MUTATION_MAF"),
    ("mutations", "MUTATION_MAF"),
    ("discrete copy number", "DISCRETE_CNA"),
    ("continuous copy number", "CONTINUOUS_CNA"),
    ("segmented", "SEGMENTED"),
    ("mrna expression", "EXPRESSION"),
    ("expression data", "EXPRESSION"),
    ("structural variant", "STRUCTURAL_VARIANT"),
    ("methylation", "METHYLATION"),
    ("mutsig", "MUTSIG"),
    ("gistic", "GISTIC"),
    ("generic assay", "GENERIC_ASSAY"),
]

_REQ_OPT_RE = re.compile(
    r"[`*_]*([A-Za-z][A-Za-z0-9_/]*)[`*_]*\s*\((Required|Optional)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SpecificationDifference:
    """One embedded format that differs from the parsed live documentation."""

    format_key: str
    changed_fields: tuple[str, ...]
    embedded: FormatSpec | None
    live: FormatSpec | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_key": self.format_key,
            "changed_fields": list(self.changed_fields),
            "embedded": asdict(self.embedded) if self.embedded is not None else None,
            "live": asdict(self.live) if self.live is not None else None,
        }


@dataclass(frozen=True, slots=True)
class SpecificationComparison:
    """Comparison of an explicit live refresh with the embedded runtime source."""

    embedded_version: str
    live_version: str | None
    live_fetched_at: str | None
    live_url: str
    differences: tuple[SpecificationDifference, ...]
    error: str | None = None

    @property
    def has_changes(self) -> bool:
        return bool(self.differences)

    def to_dict(self) -> dict[str, Any]:
        return {
            "embedded_version": self.embedded_version,
            "live_version": self.live_version,
            "live_fetched_at": self.live_fetched_at,
            "live_url": self.live_url,
            "has_changes": self.has_changes,
            "differences": [
                difference.to_dict() for difference in self.differences
            ],
            "error": self.error,
        }


def _parse_section(text: str) -> tuple[list[str], list[str]]:
    required: list[str] = []
    optional: list[str] = []
    for match in _REQ_OPT_RE.finditer(text):
        column = match.group(1).strip().lower()
        kind = match.group(2).lower()
        (required if kind == "required" else optional).append(column)
    return required, optional


def parse_upstream_specifications(markdown: str) -> list[FormatSpec]:
    """Parse known live sections and fill unrepresented formats from embedded data."""
    sections = re.split(r"\n##\s+", markdown)
    parsed: dict[str, FormatSpec] = {}

    for section in sections:
        newline = section.find("\n")
        heading = section[:newline].strip().lower() if newline > 0 else ""
        body = section[newline:] if newline > 0 else ""

        format_key: Optional[str] = None
        for fragment, key in _SECTION_MAP:
            if fragment in heading:
                format_key = key
                break
        if not format_key or format_key in parsed:
            continue

        base = next((spec for spec in SPECS if spec.key == format_key), None)
        if not base:
            continue

        required, optional = _parse_section(body)
        if not required and not optional:
            parsed[format_key] = base
            continue

        parsed[format_key] = FormatSpec(
            key=base.key,
            target_file=base.target_file,
            required=required if required else base.required,
            optional=optional if optional else base.optional,
            aliases=base.aliases,
            matrix=base.matrix,
            notes=base.notes,
        )

    result = list(parsed.values())
    found_keys = set(parsed)
    result.extend(spec for spec in SPECS if spec.key not in found_keys)
    return result


def _contains_recognized_specification(markdown: str) -> bool:
    for section in re.split(r"\n##\s+", markdown):
        newline = section.find("\n")
        if newline <= 0:
            continue
        heading = section[:newline].strip().lower()
        body = section[newline:]
        if any(fragment in heading for fragment, _ in _SECTION_MAP) and (
            _REQ_OPT_RE.search(body)
        ):
            return True
    return False


def get_embedded_spec(version: str | None = None) -> dict[str, Any]:
    """Return a verified embedded version without network I/O.

    Only versions packaged in the installed distribution are selectable. The
    current embedded version is used when ``version`` is omitted.
    """
    provenance = verify_embedded_specifications()
    selected_version = version or provenance.specification_version
    if selected_version != provenance.specification_version:
        raise ValueError(
            f"Embedded specification version {selected_version!r} is unavailable; "
            f"this package provides {provenance.specification_version!r}."
        )
    return {
        "specs": list(SPECS),
        "source": "embedded",
        "version": provenance.specification_version,
        "fetched_at": provenance.upstream_retrieved_at or "not-recorded",
        "url": provenance.upstream_document_url,
        "provenance": provenance.to_dict(),
        "error": None,
    }


def refresh_live_spec(force_refresh: bool = False) -> dict[str, Any]:
    """Explicitly fetch and parse live upstream documentation.

    Successful and failed results are cached for ``CACHE_TTL_SECONDS``;
    ``force_refresh=True`` bypasses that cache. Failures are returned as
    live-source errors with no specifications and never silently change the
    runtime source to embedded specifications.
    """
    now = time.time()
    cached_result = _CACHE["result"]
    if (
        not force_refresh
        and cached_result is not None
        and (now - _CACHE["ts"]) < CACHE_TTL_SECONDS
    ):
        return dict(cached_result)

    fetched_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    result: dict[str, Any]
    try:
        response = requests.get(
            _RAW_URL,
            timeout=FETCH_TIMEOUT,
            headers={"Accept": "text/plain"},
        )
        response.raise_for_status()
        if not _contains_recognized_specification(response.text):
            raise ValueError(
                "No recognized cBioPortal format sections were found in "
                "live documentation."
            )
        parsed = parse_upstream_specifications(response.text)
        if len(parsed) < 5:
            raise ValueError(
                f"Only {len(parsed)} formats parsed from live documentation."
            )
        content_sha256 = hashlib.sha256(response.content).hexdigest()
        result = {
            "specs": parsed,
            "source": "live",
            "version": f"sha256:{content_sha256}",
            "fetched_at": fetched_at,
            "url": _RAW_URL,
            "provenance": {
                "url": _RAW_URL,
                "retrieved_at": fetched_at,
                "content_sha256": content_sha256,
            },
            "error": None,
        }
        logger.info("cBioPortal specifications fetched live from %s", _RAW_URL)
    except Exception as exc:
        result = {
            "specs": [],
            "source": "live",
            "version": None,
            "fetched_at": fetched_at,
            "url": _RAW_URL,
            "provenance": {
                "url": _RAW_URL,
                "retrieved_at": fetched_at,
                "content_sha256": None,
            },
            "error": str(exc),
        }
        logger.warning("Live specification refresh failed: %s", exc)

    _CACHE.update({"result": result, "ts": now})
    return dict(result)


def compare_specifications(
    live_specifications: Sequence[FormatSpec],
    *,
    live_version: str | None = None,
    live_fetched_at: str | None = None,
    live_url: str = _RAW_URL,
    error: str | None = None,
) -> SpecificationComparison:
    """Compare parsed live specifications with the embedded runtime snapshot."""
    embedded_by_key = {spec.key: spec for spec in SPECS}
    live_by_key = {spec.key: spec for spec in live_specifications}
    differences: list[SpecificationDifference] = []

    for format_key in sorted(embedded_by_key.keys() | live_by_key.keys()):
        embedded = embedded_by_key.get(format_key)
        live = live_by_key.get(format_key)
        if embedded == live:
            continue
        if embedded is None or live is None:
            changed_fields = ("format",)
        else:
            changed_fields = tuple(
                field
                for field in asdict(embedded)
                if getattr(embedded, field) != getattr(live, field)
            )
        differences.append(
            SpecificationDifference(
                format_key=format_key,
                changed_fields=changed_fields,
                embedded=embedded,
                live=live,
            )
        )

    return SpecificationComparison(
        embedded_version=EMBEDDED_SPEC_VERSION,
        live_version=live_version,
        live_fetched_at=live_fetched_at,
        live_url=live_url,
        differences=tuple(differences),
        error=error,
    )


def compare_live_specifications(
    force_refresh: bool = False,
) -> SpecificationComparison:
    """Explicitly refresh live documentation and compare it with embedded data."""
    live_result = refresh_live_spec(force_refresh=force_refresh)
    if live_result["error"] is not None:
        return SpecificationComparison(
            embedded_version=EMBEDDED_SPEC_VERSION,
            live_version=live_result["version"],
            live_fetched_at=live_result["fetched_at"],
            live_url=live_result["url"],
            differences=(),
            error=live_result["error"],
        )
    return compare_specifications(
        live_result["specs"],
        live_version=live_result["version"],
        live_fetched_at=live_result["fetched_at"],
        live_url=live_result["url"],
        error=live_result["error"],
    )


def clear_cache() -> None:
    """Clear the explicit live-refresh memory cache."""
    _CACHE.update({"result": None, "ts": 0.0})


__all__ = [
    "CACHE_TTL_SECONDS",
    "FETCH_TIMEOUT",
    "SpecificationComparison",
    "SpecificationDifference",
    "clear_cache",
    "compare_live_specifications",
    "compare_specifications",
    "get_embedded_spec",
    "parse_upstream_specifications",
    "refresh_live_spec",
]
