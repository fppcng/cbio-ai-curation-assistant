"""Dispatch supplementary documents to format-specific readers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cbio_curation_assistant.supplements.readers.contracts import (
    EmptySupplementaryFileError,
    SupplementaryParseError,
    SupplementaryReadResult,
    SupplementaryReaderError,
    UnsupportedSupplementaryFormatError,
)
from cbio_curation_assistant.supplements.readers.discovery import (
    validate_supported_path,
)
from cbio_curation_assistant.supplements.readers.pdf import read_pdf_file
from cbio_curation_assistant.supplements.readers.tabular import (
    read_delimited_file,
    read_excel_sheets,
    read_text_file,
)
from cbio_curation_assistant.supplements.readers.word import read_word_file


def read_supplementary_file(path: str | Path) -> SupplementaryReadResult:
    """Parse one supported, extracted supplementary document."""
    candidate = Path(path).expanduser().resolve()
    if not candidate.is_file():
        raise FileNotFoundError(f"Supplementary file not found: {candidate}")
    validate_supported_path(candidate)
    if candidate.stat().st_size == 0:
        raise EmptySupplementaryFileError(f"Supplementary file is empty: {candidate}")

    extension = candidate.suffix.lower()
    try:
        if extension in {".xlsx", ".xls"}:
            sheets, warnings = read_excel_sheets(candidate)
        elif extension == ".csv":
            sheets, warnings = read_delimited_file(candidate, separator=",")
        elif extension in {".tsv", ".tab", ".maf"}:
            sheets, warnings = read_delimited_file(candidate, separator="\t")
        elif extension == ".txt":
            sheets, warnings = read_text_file(candidate)
        elif extension in {".doc", ".docx"}:
            sheets, warnings = read_word_file(candidate)
        elif extension == ".pdf":
            sheets, warnings = read_pdf_file(candidate)
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


__all__ = ["read_supplementary_file"]
