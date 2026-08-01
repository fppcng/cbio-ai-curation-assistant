"""Download PMC study artifacts into the canonical curation workspace."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from cbio_curation_assistant.integrations.pmc import (
    PMCRequestError,
    ResolvedStudyIdentifier,
    discover_article_pdf_url,
    download_file,
    download_pmc_supplements,
    extract_supported_files,
    fetch_pmc_article_html,
    fetch_pmc_xml,
    format_pmc_error,
    lookup_oa_package_url,
    normalize_pmcid,
    resolve_study_identifier_to_pmcid,
)
from cbio_curation_assistant.supplements.formats import (
    SUPPORTED_SUPPLEMENT_EXTENSIONS,
)
from cbio_curation_assistant.workspace import StudyWorkspace, resolve_assistant_home


DOWNLOAD_RESULT_VERSION = 1


@dataclass(frozen=True, slots=True)
class DownloadedArtifact:
    """Snapshot of one expected downloaded artifact."""

    path: Path
    relative_path: str
    present: bool
    reused: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "relative_path": self.relative_path,
            "present": self.present,
            "reused": self.reused,
        }


@dataclass(frozen=True, slots=True)
class DownloadWorkspacePaths:
    assistant_home: Path
    study_root: Path
    source_dir: Path
    study_manifest: Path
    download_manifest: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "assistant_home": str(self.assistant_home),
            "study_root": str(self.study_root),
            "source_dir": str(self.source_dir),
            "study_manifest": str(self.study_manifest),
            "download_manifest": str(self.download_manifest),
        }


@dataclass(frozen=True, slots=True)
class SupplementaryArtifacts:
    directory: Path
    relative_directory: str
    present: bool
    reused: bool
    files: tuple[DownloadedArtifact, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "directory": str(self.directory),
            "relative_directory": self.relative_directory,
            "present": self.present,
            "reused": self.reused,
            "count": len(self.files),
            "files": [artifact.to_dict() for artifact in self.files],
        }


@dataclass(frozen=True, slots=True)
class ArtifactReuse:
    xml: bool
    supplementary: bool
    article_pdf: bool

    def to_dict(self) -> dict[str, bool]:
        return {
            "xml": self.xml,
            "supplementary": self.supplementary,
            "article_pdf": self.article_pdf,
        }


@dataclass(frozen=True, slots=True)
class StudyDownloadResult:
    """Workflow result and persisted download-manifest source."""

    schema_version: int
    study_id: str
    study_manifest: str
    download_manifest: str
    workspace: DownloadWorkspacePaths
    managed_paths: Mapping[str, str]
    resolved_identifier: ResolvedStudyIdentifier
    xml: DownloadedArtifact
    article_pdf: DownloadedArtifact
    supplementary: SupplementaryArtifacts
    reused: ArtifactReuse
    warnings: tuple[str, ...] = ()

    @property
    def status(self) -> Literal["success", "partial_success"]:
        return "partial_success" if self.warnings else "success"

    def _resolved_identifier_dict(self) -> dict[str, str | None]:
        return self.resolved_identifier.to_dict()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the workflow result without persistence-only fields."""
        return {
            "manifest_version": self.schema_version,
            "study_id": self.study_id,
            "study_manifest": self.study_manifest,
            "download_manifest": self.download_manifest,
            "workspace": self.workspace.to_dict(),
            "managed_paths": dict(self.managed_paths),
            "resolved_identifier": self._resolved_identifier_dict(),
            "artifacts": {
                "xml_path": self.xml.relative_path,
                "article_pdf_path": (
                    self.article_pdf.relative_path if self.article_pdf.present else None
                ),
                "supplementary_paths": [
                    artifact.relative_path for artifact in self.supplementary.files
                ],
                "xml_present": self.xml.present,
                "article_pdf_present": self.article_pdf.present,
                "supplementary_count": len(self.supplementary.files),
            },
            "artifact_details": {
                "xml": self.xml.to_dict(),
                "article_pdf": self.article_pdf.to_dict(),
                "supplementary": self.supplementary.to_dict(),
            },
            "reused": self.reused.to_dict(),
        }

    def to_manifest_dict(self) -> dict[str, Any]:
        """Serialize the stable persisted download-manifest schema."""
        return {
            "schema_version": self.schema_version,
            **self.to_dict(),
            "status": self.status,
            "success": self.status == "success",
            "warnings": list(self.warnings),
        }


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
    return resolve_study_identifier_to_pmcid(
        identifier,
        identifier_type=identifier_type,
    )


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
        detail = format_pmc_error(exc)
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
        warnings.append(f"Article PDF lookup failed: {format_pmc_error(exc)}")
        return None, False

    if not package_url:
        try:
            article_html = fetch_pmc_article_html(pmcid)
            direct_pdf_url = discover_article_pdf_url(pmcid, article_html)
        except PMCRequestError as exc:
            warnings.append(f"Article PDF lookup failed: {format_pmc_error(exc)}")
            return None, False

        if not direct_pdf_url:
            warnings.append(
                "PMC OA package is not available. Article PDF was not downloaded."
            )
            return None, False

        try:
            prefix = f"{normalize_pmcid(pmcid).lower()}_pdf_"
            with tempfile.TemporaryDirectory(prefix=prefix) as tmp_dir_name:
                tmp_dir = Path(tmp_dir_name)
                downloaded_pdf = download_file(direct_pdf_url, tmp_dir, 0)
                shutil.copy2(downloaded_pdf, article_pdf_path)
                return article_pdf_path.resolve(), False
        except PMCRequestError as exc:
            warnings.append(
                f"Article PDF download failed: {format_pmc_error(exc)}"
            )
            return None, False
        except Exception as exc:
            warnings.append(f"Article PDF download failed: {exc}")
            return None, False

    try:
        prefix = f"{normalize_pmcid(pmcid).lower()}_oa_"
        with tempfile.TemporaryDirectory(prefix=prefix) as tmp_dir_name:
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
        warnings.append(f"Article PDF download failed: {format_pmc_error(exc)}")
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
        download_manifest=workspace.relative_to_root(
            workspace.download_manifest_path
        ),
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
            relative_directory=workspace.relative_to_root(
                workspace.supplementary_dir
            ),
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


def persist_study_download_result(
    path: Path,
    result: StudyDownloadResult,
) -> Path:
    """Persist the stable download-manifest representation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.to_manifest_dict(), indent=2, ensure_ascii=False)
        + os.linesep,
        encoding="utf-8",
    )
    return path.resolve()


def run_study_download(
    *,
    identifier: str,
    identifier_type: str,
    assistant_home: str | Path | None = None,
) -> StudyDownloadResult:
    """Download or reuse all available source artifacts for one PMC study."""
    resolved = _resolve_download_identifier(identifier, identifier_type)
    workspace = _resolve_study_workspace(
        resolved.pmcid,
        assistant_home=assistant_home,
    )
    workspace.initialize()

    warnings: list[str] = []
    _, xml_reused = _ensure_xml(workspace.article_xml_path, resolved.pmcid)
    supplementary_paths, supplementary_reused = _ensure_supplementary_files(
        pmcid=resolved.pmcid,
        supplementary_dir=workspace.supplementary_dir,
        warnings=warnings,
    )
    _, article_pdf_reused = _ensure_article_pdf(
        article_pdf_path=workspace.article_pdf_path,
        supplementary_dir=workspace.supplementary_dir,
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
    persist_study_download_result(workspace.download_manifest_path, result)
    return result


__all__ = [
    "ArtifactReuse",
    "DOWNLOAD_RESULT_VERSION",
    "DownloadedArtifact",
    "DownloadWorkspacePaths",
    "StudyDownloadResult",
    "SupplementaryArtifacts",
    "persist_study_download_result",
    "run_study_download",
]
