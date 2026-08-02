"""Read PDF supplementary documents."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cbio_curation_assistant.supplements.readers.contracts import (
    SupplementaryParseError,
)
from cbio_curation_assistant.supplements.readers.dependencies import (
    import_reader_dependency,
)


def read_pdf_file(
    path: Path,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    pdfplumber = import_reader_dependency(
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


__all__ = ["read_pdf_file"]
