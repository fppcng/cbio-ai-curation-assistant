"""
Download article XML, article PDF when available, and supplementary study files from PMC.

Example
-------
    python hermes_skills/abstractor-study-download/scripts/abstractor_study_download.py PMC8432745           --output-json /tmp/pmc8432745_download.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MODULE_ROOT = _REPO_ROOT / "cbio_abstractor"
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from pmc_supplement_fetcher import (  # noqa: E402
    SUPPORTED_SUPPLEMENT_EXTENSIONS,
    _download_url,
    _extract_supported_files,
    _fetch_pmc_xml,
    _oa_package_url,
    download_pmc_supplements,
    normalize_pmcid,
    resolve_study_identifier_to_pmcid,
)

logger = logging.getLogger(__name__)
_DEFAULT_STUDIES_DIR = _REPO_ROOT / "studies"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + os.linesep, encoding="utf-8")


def _article_pdf_name(pmcid: str) -> str:
    return f"{normalize_pmcid(pmcid)}.pdf"


def _is_supported_supplement(path: Path, pmcid: str) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in SUPPORTED_SUPPLEMENT_EXTENSIONS
        and path.name.lower() != _article_pdf_name(pmcid).lower()
    )


def _list_existing_supplements(directory: Path, pmcid: str) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        path.resolve()
        for path in directory.rglob("*")
        if _is_supported_supplement(path, pmcid)
    )


def _find_article_pdf(directory: Path, pmcid: str) -> Path | None:
    if not directory.exists():
        return None

    expected = _article_pdf_name(pmcid).lower()
    for path in sorted(directory.rglob("*.pdf")):
        if path.is_file() and path.name.lower() == expected:
            return path.resolve()
    return None


def _ensure_xml(article_dir: Path, pmcid: str) -> tuple[Path, bool]:
    xml_path = article_dir / f"{normalize_pmcid(pmcid)}.xml"
    if xml_path.exists():
        return xml_path.resolve(), True

    xml_text = _fetch_pmc_xml(pmcid)
    xml_path.write_text(xml_text, encoding="utf-8")
    return xml_path.resolve(), False


def _ensure_supplementary_files(
    pmcid: str,
    supplementary_dir: Path,
    warnings: list[str],
) -> tuple[list[Path], bool]:
    existing = _list_existing_supplements(supplementary_dir, pmcid)
    if existing:
        return existing, True

    try:
        download_pmc_supplements(
            identifier=pmcid,
            identifier_type="PMCID",
            output_dir=str(supplementary_dir),
        )
    except Exception as exc:
        existing = _list_existing_supplements(supplementary_dir, pmcid)
        if existing:
            warnings.append(f"Supplementary download completed partially: {exc}")
            return existing, False
        warnings.append(f"Supplementary download failed: {exc}")
        return [], False

    return _list_existing_supplements(supplementary_dir, pmcid), False


def _ensure_article_pdf(
    article_dir: Path,
    supplementary_dir: Path,
    pmcid: str,
    warnings: list[str],
) -> tuple[Path | None, bool]:
    article_pdf_path = article_dir / _article_pdf_name(pmcid)
    if article_pdf_path.exists():
        return article_pdf_path.resolve(), True

    supplemental_copy = _find_article_pdf(supplementary_dir, pmcid)
    if supplemental_copy is not None:
        shutil.copy2(supplemental_copy, article_pdf_path)
        return article_pdf_path.resolve(), False

    package_url = _oa_package_url(pmcid)
    if not package_url:
        warnings.append("PMC OA package is not available. Article PDF was not downloaded.")
        return None, False

    try:
        with tempfile.TemporaryDirectory(prefix=f"{normalize_pmcid(pmcid).lower()}_oa_") as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            package_path = _download_url(package_url, tmp_dir, 0)
            _extract_supported_files(package_path, tmp_dir)
            candidate = _find_article_pdf(tmp_dir, pmcid)
            if candidate is None:
                warnings.append("PMC OA package did not contain an article PDF.")
                return None, False
            shutil.copy2(candidate, article_pdf_path)
            return article_pdf_path.resolve(), False
    except Exception as exc:
        warnings.append(f"Article PDF download failed: {exc}")
        return None, False


def run_study_download(
    *,
    identifier: str,
    studies_dir: str | Path | None = None,
) -> dict[str, Any]:
    resolved = resolve_study_identifier_to_pmcid(identifier)

    root_dir = Path(studies_dir).expanduser().resolve() if studies_dir else _DEFAULT_STUDIES_DIR.resolve()
    study_root = root_dir / resolved.pmcid / "data" / "raw"
    article_dir = study_root / "article"
    supplementary_dir = study_root / "supplementary"
    manifest_path = study_root / "manifest.json"

    article_dir.mkdir(parents=True, exist_ok=True)
    supplementary_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    xml_path, xml_reused = _ensure_xml(article_dir, resolved.pmcid)
    supplementary_paths, supplementary_reused = _ensure_supplementary_files(
        pmcid=resolved.pmcid,
        supplementary_dir=supplementary_dir,
        warnings=warnings,
    )
    article_pdf_path, article_pdf_reused = _ensure_article_pdf(
        article_dir=article_dir,
        supplementary_dir=supplementary_dir,
        pmcid=resolved.pmcid,
        warnings=warnings,
    )

    manifest = {
        "input_identifier": resolved.input_identifier,
        "identifier_type": resolved.identifier_type,
        "normalized_identifier": resolved.normalized_identifier,
        "pmid": resolved.normalized_identifier if resolved.identifier_type == "PMID" else None,
        "pmcid": resolved.pmcid,
        "xml_path": str(xml_path),
        "article_pdf_path": str(article_pdf_path) if article_pdf_path else None,
        "supplementary_paths": [str(path) for path in supplementary_paths],
    }
    _write_json(manifest_path, manifest)

    return {
        "resolved_identifier": {
            "input_identifier": resolved.input_identifier,
            "identifier_type": resolved.identifier_type,
            "normalized_identifier": resolved.normalized_identifier,
            "pmcid": resolved.pmcid,
        },
        "study_root": str(study_root),
        "article_dir": str(article_dir),
        "supplementary_dir": str(supplementary_dir),
        "manifest_path": str(manifest_path),
        "xml_path": str(xml_path),
        "article_pdf_path": str(article_pdf_path) if article_pdf_path else None,
        "supplementary_paths": [str(path) for path in supplementary_paths],
        "warnings": warnings,
        "reused": {
            "xml": xml_reused,
            "supplementary": supplementary_reused,
            "article_pdf": article_pdf_reused,
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download article XML/PDF and supplementary files from PMC into studies/<PMCID>/data/raw.",
    )
    parser.add_argument("identifier", help="Numeric PMID or PMCID such as PMC8432745.")
    parser.add_argument(
        "--studies-dir",
        help="Override the studies root directory. Defaults to <repo>/studies.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional file path where the full download result JSON will be written.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        result = run_study_download(
            identifier=args.identifier,
            studies_dir=args.studies_dir,
        )
    except Exception as exc:
        logger.error("%s", exc)
        return 1

    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output_json:
        output_json_path = Path(args.output_json).expanduser().resolve()
        _write_json(output_json_path, result)

    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
