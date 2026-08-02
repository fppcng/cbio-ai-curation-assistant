"""Resolve and preflight supplementary-reader dependencies."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from importlib import import_module
from pathlib import Path
from types import ModuleType

from cbio_curation_assistant.supplements.readers.contracts import (
    MissingReaderDependencyError,
    ReaderDependencyIssue,
    SupplementaryReaderPreflightError,
)


_PYTHON_DEPENDENCIES = {
    ".doc": (("docx", "python-docx"),),
    ".docx": (("docx", "python-docx"),),
    ".pdf": (("pdfplumber", "pdfplumber"),),
    ".xls": (("xlrd", "xlrd"),),
    ".xlsx": (("openpyxl", "openpyxl"),),
}


def check_supplementary_reader_dependencies(
    paths: Sequence[str | Path],
) -> tuple[ReaderDependencyIssue, ...]:
    """Import dependencies required by the supplied file extensions."""
    extensions = sorted({Path(path).suffix.lower() for path in paths})
    issues: list[ReaderDependencyIssue] = []
    for extension in extensions:
        for module_name, distribution_name in _PYTHON_DEPENDENCIES.get(extension, ()):
            try:
                import_module(module_name)
            except Exception as exc:
                issues.append(
                    ReaderDependencyIssue(
                        extension=extension,
                        dependency=distribution_name,
                        detail=f"{type(exc).__name__}: {exc}",
                    )
                )
        if extension == ".doc" and shutil.which("libreoffice") is None:
            issues.append(
                ReaderDependencyIssue(
                    extension=extension,
                    dependency="libreoffice",
                    detail="executable not found on PATH",
                )
            )
    return tuple(issues)


def require_supplementary_reader_dependencies(
    paths: Sequence[str | Path],
) -> None:
    issues = check_supplementary_reader_dependencies(paths)
    if issues:
        raise SupplementaryReaderPreflightError(issues)


def import_reader_dependency(
    module_name: str,
    *,
    distribution_name: str,
    format_name: str,
) -> ModuleType:
    try:
        return import_module(module_name)
    except Exception as exc:
        raise MissingReaderDependencyError(
            format_name=format_name,
            dependency=distribution_name,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc


__all__ = [
    "check_supplementary_reader_dependencies",
    "import_reader_dependency",
    "require_supplementary_reader_dependencies",
]
