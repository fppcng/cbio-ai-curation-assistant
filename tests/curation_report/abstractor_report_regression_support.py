from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = (
    REPO_ROOT
    / "hermes_skills"
    / "abstractor-curation-report-generation"
    / "scripts"
    / "abstractor_report_generator.py"
)
FIXTURES_ROOT = REPO_ROOT / "tests" / "curation_report" / "fixtures"
SYNTHETIC_ARTICLE_PATH = FIXTURES_ROOT / "synthetic_article.xml"
SYNTHETIC_METADATA_PATH = FIXTURES_ROOT / "synthetic_publication_metadata.json"
NO_LLM_WARNING = (
    "No Hermes LLM configuration is available. "
    "Using structured XML metadata only."
)


def load_report_generator_module():
    script_dir = str(GENERATOR_PATH.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    spec = importlib.util.spec_from_file_location(
        "abstractor_report_generator_regression",
        GENERATOR_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Unable to load report generator module from {GENERATOR_PATH}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
