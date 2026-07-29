"""Discover and parse supported supplementary documents into tabular sheets."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Sequence

import pandas as pd

from cbio_curation_assistant.supplements.formats import (
    ARCHIVE_EXTENSIONS,
    SUPPORTED_SUPPLEMENT_EXTENSIONS,
)


class SupplementaryReaderError(Exception):
    """Base exception for supplementary discovery and parsing failures."""


class UnsupportedSupplementaryFormatError(
    SupplementaryReaderError,
    ValueError,
):
    """Raised when a caller explicitly requests an unsupported file."""


class EmptySupplementaryFileError(SupplementaryReaderError, ValueError):
    """Raised when a supported file contains no readable content."""


class SupplementaryParseError(SupplementaryReaderError, ValueError):
    """Raised when a supported file cannot be parsed."""


class MissingReaderDependencyError(SupplementaryReaderError, ImportError):
    """Raised when a format-specific Python dependency cannot be imported."""

    def __init__(
        self,
        *,
        format_name: str,
        dependency: str,
        detail: str | None = None,
    ) -> None:
        self.format_name = format_name
        self.dependency = dependency
        self.detail = detail
        message = f"{format_name} supplementary files require {dependency}."
        if detail:
            message = f"{message} Import failed: {detail}"
        super().__init__(message)


class MissingExternalReaderError(SupplementaryReaderError, RuntimeError):
    """Raised when a required external document converter is unavailable."""


@dataclass(frozen=True, slots=True)
class ReaderDependencyIssue:
    """One missing or broken dependency required by discovered file formats."""

    extension: str
    dependency: str
    detail: str


class SupplementaryReaderPreflightError(SupplementaryReaderError, RuntimeError):
    """Raised when discovered supplements cannot all be read in this environment."""

    def __init__(self, issues: Sequence[ReaderDependencyIssue]) -> None:
        self.issues = tuple(issues)
        lines = [
            f"{issue.extension}: {issue.dependency} ({issue.detail})"
            for issue in self.issues
        ]
        super().__init__(
            "Supplementary reader preflight failed:\n- " + "\n- ".join(lines)
        )


@dataclass(frozen=True, slots=True)
class SupplementaryReadResult:
    """Readable sheets from one supplement plus non-fatal parse warnings."""

    path: Path
    sheets: dict[str, pd.DataFrame]
    warnings: tuple[str, ...] = ()


_PYTHON_DEPENDENCIES = {
    ".doc": (("docx", "python-docx"),),
    ".docx": (("docx", "python-docx"),),
    ".pdf": (("pdfplumber", "pdfplumber"),),
    ".xls": (("xlrd", "xlrd"),),
    ".xlsx": (("openpyxl", "openpyxl"),),
}


def is_supported_supplementary_file(path: str | Path) -> bool:
    """Return whether an existing file has a supported reader."""
    candidate = Path(path)
    return (
        candidate.is_file()
        and candidate.suffix.lower() in SUPPORTED_SUPPLEMENT_EXTENSIONS
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
            _validate_supported_path(candidate)
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


def check_supplementary_reader_dependencies(
    paths: Sequence[str | Path],
) -> tuple[ReaderDependencyIssue, ...]:
    """Import dependencies required by the supplied file extensions."""
    extensions = sorted({Path(path).suffix.lower() for path in paths})
    issues: list[ReaderDependencyIssue] = []

    for extension in extensions:
        for module_name, distribution_name in _PYTHON_DEPENDENCIES.get(
            extension, ()
        ):
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
    """Raise one aggregated error when required reader capabilities are missing."""
    issues = check_supplementary_reader_dependencies(paths)
    if issues:
        raise SupplementaryReaderPreflightError(issues)


def read_supplementary_file(
    path: str | Path,
) -> SupplementaryReadResult:
    """Parse one supported, extracted supplement.

    Archives are intentionally rejected here. Archive extraction belongs to the
    download workflow; readers consume only extracted document and table files.
    """
    candidate = Path(path).expanduser().resolve()
    if not candidate.is_file():
        raise FileNotFoundError(f"Supplementary file not found: {candidate}")
    _validate_supported_path(candidate)
    if candidate.stat().st_size == 0:
        raise EmptySupplementaryFileError(
            f"Supplementary file is empty: {candidate}"
        )

    extension = candidate.suffix.lower()
    try:
        if extension in {".xlsx", ".xls"}:
            sheets, warnings = _read_excel_sheets(candidate)
        elif extension == ".csv":
            sheets, warnings = _read_delimited_file(candidate, separator=",")
        elif extension in {".tsv", ".tab", ".maf"}:
            sheets, warnings = _read_delimited_file(candidate, separator="\t")
        elif extension == ".txt":
            sheets, warnings = _read_text_file(candidate)
        elif extension in {".doc", ".docx"}:
            sheets, warnings = _read_word_file(candidate)
        elif extension == ".pdf":
            sheets, warnings = _read_pdf_file(candidate)
        else:
            raise UnsupportedSupplementaryFormatError(
                f"Unsupported supplementary file type: {candidate}"
            )
    except SupplementaryReaderError:
        raise
    except pd.errors.EmptyDataError as exc:
        raise EmptySupplementaryFileError(
            f"Supplementary file contains no tabular data: {candidate}"
        ) from exc
    except Exception as exc:
        raise SupplementaryParseError(
            f"Could not parse supplementary file {candidate}: {exc}"
        ) from exc

    if not sheets:
        raise EmptySupplementaryFileError(
            f"Supplementary file contains no readable content: {candidate}"
        )
    return SupplementaryReadResult(
        path=candidate,
        sheets=sheets,
        warnings=tuple(warnings),
    )


def _validate_supported_path(path: Path) -> None:
    extension = path.suffix.lower()
    if extension in ARCHIVE_EXTENSIONS:
        raise UnsupportedSupplementaryFormatError(
            f"Archive must be extracted before supplementary parsing: {path}"
        )
    if extension not in SUPPORTED_SUPPLEMENT_EXTENSIONS:
        raise UnsupportedSupplementaryFormatError(
            f"Unsupported supplementary file type: {path}"
        )


def _import_reader_dependency(
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


def _read_excel_sheets(
    path: Path,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    extension = path.suffix.lower()
    if extension == ".xlsx":
        _import_reader_dependency(
            "openpyxl",
            distribution_name="openpyxl",
            format_name="XLSX",
        )
    else:
        _import_reader_dependency(
            "xlrd",
            distribution_name="xlrd",
            format_name="XLS",
        )

    sheets: dict[str, pd.DataFrame] = {}
    warnings: list[str] = []
    try:
        with pd.ExcelFile(path) as workbook:
            for sheet_name in workbook.sheet_names:
                try:
                    dataframe = workbook.parse(sheet_name, header=None)
                except Exception as exc:
                    warnings.append(
                        f"Could not read sheet {sheet_name!r}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    continue
                dataframe = dataframe.dropna(how="all")
                if not dataframe.empty:
                    sheets[sheet_name] = dataframe
    except Exception as exc:
        raise SupplementaryParseError(
            f"Could not open Excel supplement {path}: {exc}"
        ) from exc

    if not sheets and warnings:
        raise SupplementaryParseError(
            f"No Excel sheets could be read from {path}: " + "; ".join(warnings)
        )
    return sheets, warnings


def _read_delimited_file(
    path: Path,
    *,
    separator: str,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    dataframe = pd.read_csv(
        path,
        sep=separator,
        header=None,
        dtype=str,
        encoding_errors="replace",
    ).dropna(how="all")
    return ({"Sheet1": dataframe} if not dataframe.empty else {}), []


def _read_text_file(
    path: Path,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    raw = path.read_text(encoding="utf-8", errors="replace")[:4096]
    counts = {
        "\t": raw.count("\t"),
        ",": raw.count(","),
        "|": raw.count("|"),
        " ": raw.count(" "),
    }
    separator = max(counts, key=counts.get)
    if counts[separator] == 0:
        separator = "\t"
    dataframe = pd.read_csv(
        path,
        sep=separator,
        header=None,
        dtype=str,
        encoding_errors="replace",
        on_bad_lines="skip",
    ).dropna(how="all")
    return ({"Sheet1": dataframe} if not dataframe.empty else {}), []


def _read_word_file(
    path: Path,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    docx_module = _import_reader_dependency(
        "docx",
        distribution_name="python-docx",
        format_name=path.suffix.upper().lstrip("."),
    )
    if path.suffix.lower() == ".doc":
        return _read_legacy_word_file(path, docx_module)
    return _read_docx_file(path, docx_module), []


def _read_legacy_word_file(
    path: Path,
    docx_module: ModuleType,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    executable = shutil.which("libreoffice")
    if executable is None:
        raise MissingExternalReaderError(
            "DOC supplementary files require the libreoffice executable."
        )

    with tempfile.TemporaryDirectory() as temporary_directory:
        try:
            completed = subprocess.run(
                [
                    executable,
                    "--headless",
                    "--convert-to",
                    "docx",
                    "--outdir",
                    temporary_directory,
                    str(path),
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired as exc:
            raise SupplementaryParseError(
                f"LibreOffice conversion timed out for {path}."
            ) from exc
        converted = sorted(Path(temporary_directory).glob("*.docx"))
        if completed.returncode != 0 or not converted:
            detail = (completed.stderr or completed.stdout).strip()
            raise SupplementaryParseError(
                f"LibreOffice could not convert {path}"
                + (f": {detail}" if detail else ".")
            )
        return _read_docx_file(converted[0], docx_module), []


def _read_docx_file(
    path: Path,
    docx_module: ModuleType,
) -> dict[str, pd.DataFrame]:
    document = docx_module.Document(path)
    sheets: dict[str, pd.DataFrame] = {}

    for index, table in enumerate(document.tables, start=1):
        rows = [
            [cell.text.strip() for cell in row.cells]
            for row in table.rows
        ]
        if rows:
            dataframe = pd.DataFrame(rows).dropna(how="all")
            if not dataframe.empty:
                sheets[f"Table_{index}"] = dataframe

    paragraphs = [
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]
    if paragraphs:
        sheets["Text"] = pd.DataFrame(paragraphs)
    return sheets


def _read_pdf_file(
    path: Path,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    pdfplumber = _import_reader_dependency(
        "pdfplumber",
        distribution_name="pdfplumber",
        format_name="PDF",
    )
    sheets: dict[str, pd.DataFrame] = {}
    warnings: list[str] = []

    with pdfplumber.open(path) as document:
        for page_index, page in enumerate(document.pages, start=1):
            try:
                tables = page.extract_tables() or []
            except Exception as exc:
                warnings.append(
                    f"Could not extract tables from PDF page {page_index}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue
            for table_index, table in enumerate(tables, start=1):
                if not table:
                    continue
                dataframe = pd.DataFrame(table).dropna(how="all")
                if not dataframe.empty:
                    sheets[f"Page{page_index}_Table{table_index}"] = dataframe

        if not sheets:
            lines: list[str] = []
            for page_index, page in enumerate(document.pages, start=1):
                try:
                    text = page.extract_text() or ""
                except Exception as exc:
                    warnings.append(
                        f"Could not extract text from PDF page {page_index}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    continue
                lines.extend(line for line in text.splitlines() if line.strip())
            if lines:
                sheets["Text"] = pd.DataFrame(lines)

    if not sheets and warnings:
        raise SupplementaryParseError(
            f"No PDF pages could be read from {path}: " + "; ".join(warnings)
        )
    return sheets, warnings


__all__ = [
    "EmptySupplementaryFileError",
    "MissingExternalReaderError",
    "MissingReaderDependencyError",
    "ReaderDependencyIssue",
    "SupplementaryParseError",
    "SupplementaryReadResult",
    "SupplementaryReaderError",
    "SupplementaryReaderPreflightError",
    "UnsupportedSupplementaryFormatError",
    "check_supplementary_reader_dependencies",
    "discover_supplementary_files",
    "is_supported_supplementary_file",
    "read_supplementary_file",
    "require_supplementary_reader_dependencies",
]
