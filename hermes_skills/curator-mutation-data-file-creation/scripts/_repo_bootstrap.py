from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT_ENV = "CBIO_ASSISTANT_REPO_ROOT"


def _resolve_repo_root() -> Path:
    raw_repo_root = os.environ.get(REPO_ROOT_ENV)
    if raw_repo_root:
        repo_root = Path(raw_repo_root).expanduser().resolve()
    else:
        repo_root = Path(__file__).resolve().parents[3]

    if not repo_root.is_dir():
        raise RuntimeError(
            f"Unable to resolve repository root from {REPO_ROOT_ENV} or script location: {repo_root}"
        )

    return repo_root


REPO_ROOT = _resolve_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
