from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_ROOT = REPO_ROOT / "tests" / "curation_report" / "fixtures"
SYNTHETIC_ARTICLE_PATH = FIXTURES_ROOT / "synthetic_article.xml"
SYNTHETIC_METADATA_PATH = FIXTURES_ROOT / "synthetic_publication_metadata.json"
NO_LLM_WARNING = (
    "No Hermes LLM configuration is available. Using structured XML metadata only."
)
