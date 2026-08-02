"""Discover supported supplementary documents."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from cbio_curation_assistant.supplements.formats import (
    ARCHIVE_EXTENSIONS,
    SUPPORTED_SUPPLEMENT_EXTENSIONS,
)
from cbio_curation_assistant.supplements.readers.contracts import (
    EmptySupplementaryFileError,
    UnsupportedSupplementaryFormatError,
)


def is_supported_supplementary_file(path: str | Path) -> bool:
    candidate = Path(path)
    return (
        candidate.is_file()
        and candidate.suffix.lower() in SUPPORTED_SUPPLEMENT_EXTENSIONS
    )


def validate_supported_path(path: Path) -> None:
    extension = path.suffix.lower()
    if extension in ARCHIVE_EXTENSIONS:
        raise UnsupportedSupplementaryFormatError(
            f"Archive must be extracted before supplementary parsing: {path}"
        )
    if extension not in SUPPORTED_SUPPLEMENT_EXTENSIONS:
        raise UnsupportedSupplementaryFormatError(
            f"Unsupported supplementary file type: {path}"
        )


def discover_supplementary_files(
    paths: Sequence[str | Path],
    *,
    recursive: bool = False,
) -> tuple[Path, ...]:
    """Resolve, validate, sort, and deduplicate supplementary input files."""
    resolved_paths: list[Path] = []
    seen: set[Path] = set()

    for raw_path in paths:
        candidate = Path(raw_path).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"Supplementary path not found: {candidate}")
        if candidate.is_file():
            validate_supported_path(candidate)
            if candidate not in seen:
                seen.add(candidate)
                resolved_paths.append(candidate)
            continue
        if not candidate.is_dir():
            raise UnsupportedSupplementaryFormatError(
                f"Unsupported supplementary path: {candidate}"
            )

        iterator = candidate.rglob("*") if recursive else candidate.iterdir()
        for path in sorted(
            (
                path.resolve()
                for path in iterator
                if is_supported_supplementary_file(path)
            ),
            key=lambda item: item.as_posix(),
        ):
            if path not in seen:
                seen.add(path)
                resolved_paths.append(path)

    if not resolved_paths:
        raise EmptySupplementaryFileError(
            "No supported supplementary files were found."
        )
    return tuple(resolved_paths)


__all__ = [
    "discover_supplementary_files",
    "is_supported_supplementary_file",
    "validate_supported_path",
]
