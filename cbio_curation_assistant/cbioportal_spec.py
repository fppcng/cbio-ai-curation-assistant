"""Compatibility imports for the relocated cBioPortal specifications.

Remove this module after all consumers import
``cbio_curation_assistant.cbioportal.specs``.
"""

from cbio_curation_assistant.cbioportal.specs import (
    EMBEDDED_SPEC_PROVENANCE,
    EMBEDDED_SPEC_VERSION,
    SPECS,
    SPEC_BY_KEY,
    EmbeddedSpecificationProvenance,
    FormatSpec,
    load_embedded_specification_provenance,
    verify_embedded_specifications,
)


__all__ = [
    "EMBEDDED_SPEC_PROVENANCE",
    "EMBEDDED_SPEC_VERSION",
    "EmbeddedSpecificationProvenance",
    "FormatSpec",
    "SPECS",
    "SPEC_BY_KEY",
    "load_embedded_specification_provenance",
    "verify_embedded_specifications",
]


# Removal condition: no repository or supported external consumer uses this path.
