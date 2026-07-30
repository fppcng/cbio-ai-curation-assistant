from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Sequence

from cbio_curation_assistant.command_result import (
    CommandResult,
    command_error,
    command_result,
    emit_command_result,
    exit_code_for_status,
)
from cbio_curation_assistant.integrations.pmc import (
    PMCRequestError,
    ResolvedStudyIdentifier,
    discover_article_pdf_url,
    download_file,
    download_pmc_supplements,
    extract_supported_files,
    fetch_pmc_article_html,
    fetch_pmc_xml,
    lookup_oa_package_url,
    normalize_pmcid,
    pmid_to_pmcid,
)
from cbio_curation_assistant.supplements.formats import (
    SUPPORTED_SUPPLEMENT_EXTENSIONS,
)
from cbio_curation_assistant.workspace import StudyWorkspace, resolve_assistant_home
from cbio_curation_assistant.workflows.study_download import (
    ArtifactReuse,
    DownloadedArtifact,
    DownloadWorkspacePaths,
    StudyDownloadResult,
    SupplementaryArtifacts,
)

logger = logging.getLogger(__name__)

DOWNLOAD_RESULT_VERSION = 1


def _resolve_study_workspace(
    study_id: str,
    *,
    assistant_home: str | Path | None = None,
) -> StudyWorkspace:
    resolved_assistant_home = resolve_assistant_home(assistant_home)
    return StudyWorkspace.from_study_id(
        study_id,
        assistant_home=resolved_assistant_home,
    )


def _resolve_download_identifier(
    identifier: str,
    identifier_type: str,
) -> ResolvedStudyIdentifier:
    normalized_type = (identifier_type or "").strip().upper()
    raw_identifier = (identifier or "").strip()

    if normalized_type == "PMCID":
        normalized_identifier = normalize_pmcid(raw_identifier)
        return ResolvedStudyIdentifier(
            input_identifier=raw_identifier,
            identifier_type="PMCID",
            normalized_identifier=normalized_identifier,
            pmcid=normalized_identifier,
        )

    if normalized_type == "PMID":
        normalized_identifier = re.sub(r"\D", "", raw_identifier)
        if not normalized_identifier:
            raise ValueError("PMID must contain digits.")
        return ResolvedStudyIdentifier(
            input_identifier=raw_identifier,
            identifier_type="PMID",
            normalized_identifier=normalized_identifier,
            pmcid=pmid_to_pmcid(normalized_identifier),
        )

    raise ValueError("identifier_type must be either 'pmid' or 'pmcid'.")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + os.linesep, encoding="utf-8")


def _format_pmc_error(exc: PMCRequestError) -> str:
    if exc.status_code is not None:
        return f"{exc.category} (HTTP {exc.status_code}): {exc.detail}"
    return f"{exc.category}: {exc.detail}"


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


def _ensure_xml(article_xml_path: Path, pmcid: str) -> tuple[Path, bool]:
    if article_xml_path.exists():
        return article_xml_path.resolve(), True

    xml_text = fetch_pmc_xml(pmcid)
    article_xml_path.write_text(xml_text, encoding="utf-8")
    return article_xml_path.resolve(), False


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
    except PMCRequestError as exc:
        existing = _list_existing_supplements(supplementary_dir, pmcid)
        detail = _format_pmc_error(exc)
        if existing:
            warnings.append(f"Supplementary download completed partially: {detail}")
            return existing, False
        warnings.append(f"Supplementary download failed: {detail}")
        return [], False
    except Exception as exc:
        existing = _list_existing_supplements(supplementary_dir, pmcid)
        if existing:
            warnings.append(f"Supplementary download completed partially: {exc}")
            return existing, False
        warnings.append(f"Supplementary download failed: {exc}")
        return [], False

    return _list_existing_supplements(supplementary_dir, pmcid), False


def _ensure_article_pdf(
    article_pdf_path: Path,
    supplementary_dir: Path,
    pmcid: str,
    warnings: list[str],
) -> tuple[Path | None, bool]:
    if article_pdf_path.exists():
        return article_pdf_path.resolve(), True

    supplemental_copy = _find_article_pdf(supplementary_dir, pmcid)
    if supplemental_copy is not None:
        shutil.copy2(supplemental_copy, article_pdf_path)
        return article_pdf_path.resolve(), False

    try:
        package_url = lookup_oa_package_url(pmcid)
    except PMCRequestError as exc:
        warnings.append(f"Article PDF lookup failed: {_format_pmc_error(exc)}")
        return None, False

    if not package_url:
        try:
            article_html = fetch_pmc_article_html(pmcid)
            direct_pdf_url = discover_article_pdf_url(pmcid, article_html)
        except PMCRequestError as exc:
            warnings.append(f"Article PDF lookup failed: {_format_pmc_error(exc)}")
            return None, False

        if not direct_pdf_url:
            warnings.append("PMC OA package is not available. Article PDF was not downloaded.")
            return None, False

        try:
            with tempfile.TemporaryDirectory(prefix=f"{normalize_pmcid(pmcid).lower()}_pdf_") as tmp_dir_name:
                tmp_dir = Path(tmp_dir_name)
                downloaded_pdf = download_file(direct_pdf_url, tmp_dir, 0)
                shutil.copy2(downloaded_pdf, article_pdf_path)
                return article_pdf_path.resolve(), False
        except PMCRequestError as exc:
            warnings.append(f"Article PDF download failed: {_format_pmc_error(exc)}")
            return None, False
        except Exception as exc:
            warnings.append(f"Article PDF download failed: {exc}")
            return None, False

    try:
        with tempfile.TemporaryDirectory(prefix=f"{normalize_pmcid(pmcid).lower()}_oa_") as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            package_path = download_file(package_url, tmp_dir, 0)
            extract_supported_files(package_path, tmp_dir)
            candidate = _find_article_pdf(tmp_dir, pmcid)
            if candidate is None:
                warnings.append("PMC OA package did not contain an article PDF.")
                return None, False
            shutil.copy2(candidate, article_pdf_path)
            return article_pdf_path.resolve(), False
    except PMCRequestError as exc:
        warnings.append(f"Article PDF download failed: {_format_pmc_error(exc)}")
        return None, False
    except Exception as exc:
        warnings.append(f"Article PDF download failed: {exc}")
        return None, False


def _build_file_record(
    workspace: StudyWorkspace,
    path: Path,
    *,
    reused: bool,
) -> DownloadedArtifact:
    return DownloadedArtifact(
        path=path.resolve(),
        relative_path=workspace.relative_to_root(path),
        present=path.is_file(),
        reused=reused,
    )


def _build_result_payload(
    *,
    workspace: StudyWorkspace,
    resolved: ResolvedStudyIdentifier,
    warnings: list[str],
    xml_reused: bool,
    supplementary_reused: bool,
    article_pdf_reused: bool,
    supplementary_paths: list[Path],
) -> StudyDownloadResult:
    xml_record = _build_file_record(
        workspace,
        workspace.article_xml_path,
        reused=xml_reused,
    )
    article_pdf_record = _build_file_record(
        workspace,
        workspace.article_pdf_path,
        reused=article_pdf_reused,
    )
    supplementary_files = [
        _build_file_record(workspace, path, reused=supplementary_reused)
        for path in supplementary_paths
    ]

    return StudyDownloadResult(
        schema_version=DOWNLOAD_RESULT_VERSION,
        study_id=workspace.study_id,
        study_manifest=workspace.relative_to_root(workspace.manifest_path),
        download_manifest=workspace.relative_to_root(workspace.download_manifest_path),
        workspace=DownloadWorkspacePaths(
            assistant_home=workspace.assistant_home,
            study_root=workspace.root.resolve(),
            source_dir=workspace.source_dir.resolve(),
            study_manifest=workspace.manifest_path.resolve(),
            download_manifest=workspace.download_manifest_path.resolve(),
        ),
        managed_paths=workspace.as_manifest_paths(),
        resolved_identifier=resolved,
        xml=xml_record,
        article_pdf=article_pdf_record,
        supplementary=SupplementaryArtifacts(
            directory=workspace.supplementary_dir.resolve(),
            relative_directory=workspace.relative_to_root(workspace.supplementary_dir),
            present=workspace.supplementary_dir.is_dir(),
            reused=supplementary_reused,
            files=tuple(supplementary_files),
        ),
        reused=ArtifactReuse(
            xml=xml_reused,
            supplementary=supplementary_reused,
            article_pdf=article_pdf_reused,
        ),
        warnings=tuple(warnings),
    )


def run_study_download(
    *,
    identifier: str,
    identifier_type: str,
    assistant_home: str | Path | None = None,
) -> StudyDownloadResult:
    resolved = _resolve_download_identifier(identifier, identifier_type)
    workspace = _resolve_study_workspace(
        resolved.pmcid,
        assistant_home=assistant_home,
    )
    workspace.initialize()

    supplementary_dir = workspace.supplementary_dir
    manifest_path = workspace.download_manifest_path

    warnings: list[str] = []
    _, xml_reused = _ensure_xml(workspace.article_xml_path, resolved.pmcid)
    supplementary_paths, supplementary_reused = _ensure_supplementary_files(
        pmcid=resolved.pmcid,
        supplementary_dir=supplementary_dir,
        warnings=warnings,
    )
    _, article_pdf_reused = _ensure_article_pdf(
        article_pdf_path=workspace.article_pdf_path,
        supplementary_dir=supplementary_dir,
        pmcid=resolved.pmcid,
        warnings=warnings,
    )

    result = _build_result_payload(
        workspace=workspace,
        resolved=resolved,
        warnings=warnings,
        xml_reused=xml_reused,
        supplementary_reused=supplementary_reused,
        article_pdf_reused=article_pdf_reused,
        supplementary_paths=supplementary_paths,
    )
    _write_json(manifest_path, result.to_manifest_dict())
    return result


def _emit(payload: CommandResult[Any]) -> None:
    emit_command_result(payload)


def _response_from_download_result(
    result: StudyDownloadResult,
) -> CommandResult[StudyDownloadResult]:
    return command_result(
        "study-download",
        status=result.status,
        result=result,
        warnings=result.warnings,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download article XML/PDF and supplementary files from PMC into the canonical "
            "study source workspace resolved from $CBIO_CURATION_ASSISTANT_HOME."
        ),
    )
    parser.add_argument(
        "--identifier",
        required=True,
        help="User-supplied publication identifier value, for example 8432745 or PMC8432745.",
    )
    parser.add_argument(
        "--identifier-type",
        required=True,
        choices=["pmid", "pmcid"],
        help="Interpret --identifier explicitly as a PMID or PMCID.",
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
            identifier_type=args.identifier_type,
        )
    except PMCRequestError as exc:
        _emit(command_error("study-download", _format_pmc_error(exc)))
        return 1
    except Exception as exc:
        _emit(command_error("study-download", exc))
        return 1

    response = _response_from_download_result(result)
    _emit(response)
    return exit_code_for_status(response.status)


if __name__ == "__main__":
    raise SystemExit(main())
