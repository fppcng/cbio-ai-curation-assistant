"""Compatibility imports for relocated cBioPortal specification sources.

Remove this module after all consumers import
``cbio_curation_assistant.cbioportal.specification_sources``.
"""

from cbio_curation_assistant.cbioportal.specification_sources import (
    CACHE_TTL_SECONDS,
    FETCH_TIMEOUT,
    clear_cache,
    fetch_spec,
    get_spec_or_fallback,
    parse_upstream_specifications,
)


__all__ = [
    "CACHE_TTL_SECONDS",
    "FETCH_TIMEOUT",
    "clear_cache",
    "fetch_spec",
    "get_spec_or_fallback",
    "parse_upstream_specifications",
]


# Removal condition: no repository or supported external consumer uses this path.
