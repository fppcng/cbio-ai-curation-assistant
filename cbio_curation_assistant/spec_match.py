"""Compatibility adapter for relocated cBioPortal sheet classification.

The legacy ``classify_sheet(df, force_refresh=False)`` API now resolves the
deterministic embedded specifications before calling the pure classifier.
Live retrieval is available only through explicit source refresh/comparison
APIs. Remove this module after consumers resolve specifications and import
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
from cbio_curation_assistant.cbioportal.specification_sources import get_embedded_spec


def classify_sheet(
    df: pd.DataFrame,
    force_refresh: bool = False,
) -> ClassificationResult:
    """Classify a sheet through the deterministic embedded convenience API."""
    if force_refresh:
        raise ValueError(
            "Classification no longer refreshes live specifications. "
            "Use compare_live_specifications() explicitly."
        )
    specification_result = get_embedded_spec()
    return classify_sheet_with_specifications(
        df,
        specification_result["specs"],
        spec_source=specification_result["source"],
        spec_fetched_at=specification_result.get("fetched_at", "unknown"),
        spec_version=specification_result.get("version", "unknown"),
    )


__all__ = [
    "CONFIDENCE_THRESHOLD",
    "MATRIX_PENALTY",
    "ClassificationResult",
    "classify_sheet",
]


# Removal condition: no repository or supported external consumer relies on
# this path or on classification resolving specifications implicitly.
