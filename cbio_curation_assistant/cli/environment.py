"""Environment resolution shared by CLI command adapters."""

from __future__ import annotations

import os
from pathlib import Path

from cbio_curation_assistant.workspace.configuration import (
    ENV_VAR_NAME,
    resolve_assistant_home,
)


def assistant_home() -> Path:
    """Resolve the configured assistant data root."""
    return resolve_assistant_home(os.environ.get(ENV_VAR_NAME))


__all__ = ["assistant_home"]
