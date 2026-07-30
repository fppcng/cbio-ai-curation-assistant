"""Safe extraction of supported files from PMC archives."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

from cbio_curation_assistant.supplements.formats import (
    ARCHIVE_EXTENSIONS,
    SUPPORTED_SUPPLEMENT_EXTENSIONS,
)


def is_supported_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_SUPPLEMENT_EXTENSIONS


def is_archive(path: Path) -> bool:
    lower = path.name.lower()
    return (
        lower.endswith(
            (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")
        )
        or path.suffix.lower() in ARCHIVE_EXTENSIONS
    )


def safe_extract_path(base_dir: Path, member_name: str) -> Path:
    base_dir = base_dir.resolve()
    target = (base_dir / member_name).resolve()
    try:
        target.relative_to(base_dir)
    except ValueError:
        raise ValueError(
            f"Archive member escapes extraction directory: {member_name}"
        )
    return target


def extract_supported_files(
    archive_path: Path,
    output_dir: Path,
) -> list[Path]:
    extract_dir = output_dir / f"{archive_path.stem}_extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                target = safe_extract_path(extract_dir, info.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, open(target, "wb") as dest:
                    dest.write(source.read())
                if is_supported_file(target):
                    extracted.append(target)
        return extracted

    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                target = safe_extract_path(extract_dir, member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    continue
                with source, open(target, "wb") as dest:
                    dest.write(source.read())
                if is_supported_file(target):
                    extracted.append(target)
        return extracted

    return []


__all__ = [
    "extract_supported_files",
    "is_archive",
    "is_supported_file",
    "safe_extract_path",
]
