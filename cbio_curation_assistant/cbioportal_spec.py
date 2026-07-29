"""Compatibility imports for the relocated cBioPortal specifications.

Remove this module after all consumers import
``cbio_curation_assistant.cbioportal.specs``.
"""

from cbio_curation_assistant.cbioportal.specs import FormatSpec, SPECS, SPEC_BY_KEY


__all__ = ["FormatSpec", "SPECS", "SPEC_BY_KEY"]


# Removal condition: no repository or supported external consumer uses this path.
