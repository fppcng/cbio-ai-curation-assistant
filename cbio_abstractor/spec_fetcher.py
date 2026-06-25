"""
spec_fetcher.py
───────────────
Fetches the cBioPortal File-Formats spec from GitHub at runtime.

Source: raw.githubusercontent.com/cBioPortal/cbioportal/master/docs/File-Formats.md
  — always current, plain text, no authentication required.

Caching: results are kept in memory for CACHE_TTL_SECONDS (1 hr default).
Fallback: if GitHub is unreachable, returns the embedded cbioportal_spec.py specs.

Public API
──────────
    fetch_spec(force_refresh=False)
        → {"specs": list[FormatSpec], "source": "live"|"embedded",
           "fetched_at": str, "url": str, "error": str|None}

    get_spec_or_fallback(force_refresh=False)
        → list[FormatSpec]   (always returns something usable)

    clear_cache()
"""

from __future__ import annotations

import re
import time
import datetime
import logging
from typing import Optional

import requests

from cbioportal_spec import SPECS, FormatSpec

logger = logging.getLogger(__name__)

_RAW_URL = (
    "https://raw.githubusercontent.com/cBioPortal/cbioportal/"
    "master/docs/File-Formats.md"
)
CACHE_TTL_SECONDS = 3600
FETCH_TIMEOUT     = 15

_CACHE: dict = {
    "specs": None, "source": None, "fetched_at": None,
    "url": None, "error": None, "ts": 0.0,
}

# Maps lowercase heading fragments → FormatSpec key
_SECTION_MAP = [
    ("patient attributes",          "CLINICAL_PATIENT"),
    ("clinical patient",            "CLINICAL_PATIENT"),
    ("sample attributes",           "CLINICAL_SAMPLE"),
    ("clinical sample",             "CLINICAL_SAMPLE"),
    ("mutation data",               "MUTATION_MAF"),
    ("mutations",                   "MUTATION_MAF"),
    ("discrete copy number",        "DISCRETE_CNA"),
    ("continuous copy number",      "CONTINUOUS_CNA"),
    ("segmented",                   "SEGMENTED"),
    ("mrna expression",             "EXPRESSION"),
    ("expression data",             "EXPRESSION"),
    ("structural variant",          "STRUCTURAL_VARIANT"),
    ("methylation",                 "METHYLATION"),
    ("mutsig",                      "MUTSIG"),
    ("gistic",                      "GISTIC"),
    ("generic assay",               "GENERIC_ASSAY"),
]

_REQ_OPT_RE = re.compile(
    r'[`*_]*([A-Za-z][A-Za-z0-9_/]*)[`*_]*\s*\((Required|Optional)',
    re.IGNORECASE,
)


def _parse_section(text: str) -> tuple[list[str], list[str]]:
    required, optional = [], []
    for m in _REQ_OPT_RE.finditer(text):
        col  = m.group(1).strip().lower()
        kind = m.group(2).lower()
        (required if kind == "required" else optional).append(col)
    return required, optional


def _parse_markdown(md: str) -> list[FormatSpec]:
    """Split on ## headings and extract req/opt columns per section."""
    sections = re.split(r'\n##\s+', md)
    parsed: dict[str, FormatSpec] = {}

    for section in sections:
        nl = section.find('\n')
        heading = section[:nl].strip().lower() if nl > 0 else ""
        body    = section[nl:] if nl > 0 else ""

        fmt_key: Optional[str] = None
        for fragment, key in _SECTION_MAP:
            if fragment in heading:
                fmt_key = key
                break
        if not fmt_key or fmt_key in parsed:
            continue

        base = next((s for s in SPECS if s.key == fmt_key), None)
        if not base:
            continue

        req, opt = _parse_section(body)
        if not req and not opt:
            parsed[fmt_key] = base   # nothing to update
            continue

        parsed[fmt_key] = FormatSpec(
            key=base.key,
            target_file=base.target_file,
            required=req  if req  else base.required,
            optional=opt  if opt  else base.optional,
            aliases=base.aliases,      # aliases don't change often
            matrix=base.matrix,
            notes=base.notes,
        )

    # Fill in any format not found in the live doc
    result = list(parsed.values())
    found_keys = set(parsed.keys())
    for s in SPECS:
        if s.key not in found_keys:
            result.append(s)
    return result


def fetch_spec(force_refresh: bool = False) -> dict:
    """Fetch (or return cached) live spec from GitHub."""
    now = time.time()
    if (not force_refresh
            and _CACHE["specs"] is not None
            and (now - _CACHE["ts"]) < CACHE_TTL_SECONDS):
        return dict(_CACHE)

    error:  Optional[str] = None
    specs:  list[FormatSpec] = []
    source = "embedded"
    url    = _RAW_URL

    try:
        resp = requests.get(_RAW_URL, timeout=FETCH_TIMEOUT,
                            headers={"Accept": "text/plain"})
        resp.raise_for_status()
        parsed = _parse_markdown(resp.text)
        if len(parsed) >= 5:
            specs  = parsed
            source = "live"
            logger.info("cBioPortal spec fetched live from %s", _RAW_URL)
        else:
            error = (
                f"Only {len(parsed)} formats parsed from live doc "
                "— falling back to embedded spec."
            )
            specs = list(SPECS)
    except Exception as exc:
        error = str(exc)
        specs = list(SPECS)
        logger.warning("Live spec fetch failed (%s) — using embedded spec.", exc)

    fetched_at = datetime.datetime.utcnow().isoformat() + "Z"
    _CACHE.update({"specs": specs, "source": source, "fetched_at": fetched_at,
                   "url": url, "error": error, "ts": now})
    return {"specs": specs, "source": source, "fetched_at": fetched_at,
            "url": url, "error": error}


def get_spec_or_fallback(force_refresh: bool = False) -> list[FormatSpec]:
    return fetch_spec(force_refresh)["specs"]


def clear_cache() -> None:
    _CACHE["ts"] = 0.0
    _CACHE["specs"] = None
