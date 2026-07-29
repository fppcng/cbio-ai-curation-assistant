"""Compatibility adapter for relocated cBioPortal sheet classification.

The legacy ``classify_sheet(df, force_refresh=False)`` API resolves live-first
specifications before calling the pure package classifier. Remove this module
after consumers resolve specifications explicitly and import
``cbio_curation_assistant.cbioportal.classification``.
"""

from __future__ import annotations

import pandas as pd

from cbio_curation_assistant.cbioportal.classification import (
    CONFIDENCE_THRESHOLD,
    MATRIX_PENALTY,
    ClassificationResult,
    classify_sheet as classify_sheet_with_specifications,
)
from cbio_curation_assistant.cbioportal.specification_sources import fetch_spec


def classify_sheet(
    df: pd.DataFrame,
    force_refresh: bool = False,
) -> ClassificationResult:
    """Classify a sheet through the legacy live-first convenience API."""
    fetch_result = fetch_spec(force_refresh=force_refresh)
    return classify_sheet_with_specifications(
        df,
        fetch_result["specs"],
        spec_source=fetch_result["source"],
        spec_fetched_at=fetch_result.get("fetched_at", "unknown"),
    )


__all__ = [
    "CONFIDENCE_THRESHOLD",
    "MATRIX_PENALTY",
    "ClassificationResult",
    "classify_sheet",
]


# Removal condition: no repository or supported external consumer relies on
# this path or on classification resolving specifications implicitly.
