"""Compatibility imports for relocated cBioPortal specification sources.

Remove this module after all consumers import
``cbio_curation_assistant.cbioportal.specification_sources``.
"""

from cbio_curation_assistant.cbioportal.specification_sources import (
    CACHE_TTL_SECONDS,
    FETCH_TIMEOUT,
    SpecificationComparison,
    SpecificationDifference,
    clear_cache,
    compare_live_specifications,
    compare_specifications,
    fetch_spec,
    get_embedded_spec,
    get_spec_or_fallback,
    parse_upstream_specifications,
    refresh_live_spec,
)


__all__ = [
    "CACHE_TTL_SECONDS",
    "FETCH_TIMEOUT",
    "SpecificationComparison",
    "SpecificationDifference",
    "clear_cache",
    "compare_live_specifications",
    "compare_specifications",
    "fetch_spec",
    "get_embedded_spec",
    "get_spec_or_fallback",
    "parse_upstream_specifications",
    "refresh_live_spec",
]


# Removal condition: no repository or supported external consumer uses this path.
