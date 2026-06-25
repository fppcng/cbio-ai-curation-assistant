"""
spec_match.py
─────────────
Spec-driven cBioPortal format classifier.

Fetches the live cBioPortal format spec from GitHub at startup (cached 1 hr),
falls back to the embedded spec in cbioportal_spec.py if the fetch fails.

Classification logic:
  confidence = (required_hits / total_required) × 70
              + (optional_hits  / total_optional)  × 30
  Minimum to accept: CONFIDENCE_THRESHOLD (default 40).

Returns ClassificationResult with:
  - best format key + confidence
  - required columns present / missing (with alias names actually found)
  - optional columns present
  - top-5 candidate scores for alternative-format display
  - verdict string
  - spec_source ("live" | "embedded") + spec_fetched_at timestamp
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd
from cbioportal_spec import FormatSpec
from spec_fetcher import fetch_spec

CONFIDENCE_THRESHOLD = 40
MATRIX_PENALTY       = 25


@dataclass
class ClassificationResult:
    format_key:          str
    target_file:         str
    confidence:          float
    required_present:    list[str]
    required_missing:    list[str]
    optional_present:    list[str]
    detected_as_aliases: dict[str, str]
    all_scores:          list[dict]
    is_matrix:           bool
    notes:               str
    verdict:             str
    spec_source:         str   # "live" or "embedded"
    spec_fetched_at:     str   # ISO timestamp


def _normalise(s: str) -> str:
    return " ".join(str(s).lower().strip().split())


def _sheet_col_tokens(df: pd.DataFrame) -> set[str]:
    tokens: set[str] = set()
    for col in df.columns:
        tokens.add(_normalise(col))
    for _, row in df.head(3).iterrows():
        for val in row:
            if pd.notna(val) and isinstance(val, str):
                tokens.add(_normalise(val))
    return tokens


def _looks_like_matrix(df: pd.DataFrame) -> bool:
    if df.shape[1] < 3:
        return False
    str_frac = df.iloc[:, 0].apply(lambda x: isinstance(x, str)).mean()
    if str_frac < 0.5:
        return False
    numeric_frac = (
        df.iloc[:, 1:]
        .apply(pd.to_numeric, errors="coerce")
        .notna().mean().mean()
    )
    return numeric_frac >= 0.5


def _match_spec(spec: FormatSpec, col_tokens: set[str], df: pd.DataFrame) -> dict:
    req_present: list[str] = []
    req_missing: list[str] = []
    opt_present: list[str] = []
    alias_map:   dict[str, str] = {}

    def _find(canon: str) -> Optional[str]:
        if _normalise(canon) in col_tokens:
            return _normalise(canon)
        for alias in spec.aliases.get(canon, []):
            if _normalise(alias) in col_tokens:
                return _normalise(alias)
        return None

    for req in spec.required:
        found = _find(req)
        if found:
            req_present.append(req)
            alias_map[req] = found
        else:
            req_missing.append(req)

    for opt in spec.optional:
        if _find(opt):
            opt_present.append(opt)

    n_req = len(spec.required)
    n_opt = len(spec.optional)
    req_score  = (len(req_present) / n_req * 70) if n_req else 70
    opt_score  = (len(opt_present) / n_opt * 30) if n_opt else 0
    confidence = round(req_score + opt_score, 1)

    matrix_detected = _looks_like_matrix(df)
    if spec.matrix and not matrix_detected:
        confidence = max(0, confidence - MATRIX_PENALTY)
    elif not spec.matrix and matrix_detected:
        confidence = max(0, confidence - 10)

    return {
        "key":             spec.key,
        "target_file":     spec.target_file,
        "confidence":      confidence,
        "req_present":     req_present,
        "req_missing":     req_missing,
        "opt_present":     opt_present,
        "alias_map":       alias_map,
        "matrix_detected": matrix_detected,
    }


def classify_sheet(df: pd.DataFrame,
                   force_refresh: bool = False) -> ClassificationResult:
    """
    Classify a DataFrame against the live cBioPortal format spec.

    Fetches from GitHub raw markdown on first call each hour; falls back to
    the embedded cbioportal_spec.py on network failure.
    """
    fetch_result = fetch_spec(force_refresh=force_refresh)
    live_specs   = fetch_result["specs"]
    spec_source  = fetch_result["source"]
    spec_fetched = fetch_result.get("fetched_at", "unknown")
    spec_by_key  = {s.key: s for s in live_specs}

    col_tokens = _sheet_col_tokens(df)
    scores     = [_match_spec(s, col_tokens, df) for s in live_specs]
    scores.sort(key=lambda x: x["confidence"], reverse=True)
    best = scores[0]

    # Top-5 candidates for the alternative-format display
    all_scores_summary = [
        {
            "format":      s["key"],
            "confidence":  s["confidence"],
            "req_hits":    len(s["req_present"]),
            "req_total":   len(spec_by_key[s["key"]].required) if s["key"] in spec_by_key else 0,
            "opt_hits":    len(s["opt_present"]),
            "req_missing": s["req_missing"],
        }
        for s in scores[:5]
    ]

    # Winner
    if best["confidence"] < CONFIDENCE_THRESHOLD:
        fmt_key     = "NOT_LOADABLE"
        target_file = "Not directly loadable"
        notes       = (
            f"Best match: {best['key']} @ {best['confidence']:.0f}% "
            f"(below {CONFIDENCE_THRESHOLD}% threshold). "
            "Sheet may contain methods, enrichment results, or QC metrics."
        )
    else:
        fmt_key   = best["key"]
        spec_obj  = spec_by_key.get(fmt_key)
        target_file = spec_obj.target_file if spec_obj else "Unknown"
        notes       = spec_obj.notes if spec_obj else ""

    # Verdict string
    if fmt_key == "NOT_LOADABLE":
        verdict = (
            f"NOT LOADABLE — best candidate: {best['key']} "
            f"@ {best['confidence']:.0f}%"
        )
    else:
        parts = [f"{fmt_key}  ({best['confidence']:.0f}% confidence)"]
        if best["req_missing"]:
            parts.append("Missing required: " + ", ".join(best["req_missing"]))
        runner_up = next(
            (s for s in scores[1:] if s["confidence"] >= CONFIDENCE_THRESHOLD),
            None,
        )
        if runner_up:
            parts.append(f"Alt: {runner_up['key']} @ {runner_up['confidence']:.0f}%")
        verdict = "  |  ".join(parts)

    return ClassificationResult(
        format_key=fmt_key,
        target_file=target_file,
        confidence=best["confidence"] if fmt_key != "NOT_LOADABLE" else 0.0,
        required_present=best["req_present"],
        required_missing=best["req_missing"],
        optional_present=best["opt_present"],
        detected_as_aliases=best["alias_map"],
        all_scores=all_scores_summary,
        is_matrix=best["matrix_detected"],
        notes=notes,
        verdict=verdict,
        spec_source=spec_source,
        spec_fetched_at=spec_fetched,
    )
