"""Read tabular supplementary formats."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cbio_curation_assistant.supplements.readers.contracts import (
    SupplementaryParseError,
)
from cbio_curation_assistant.supplements.readers.dependencies import (
    import_reader_dependency,
)


def read_excel_sheets(
    path: Path,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    extension = path.suffix.lower()
    if extension == ".xlsx":
        import_reader_dependency(
            "openpyxl",
            distribution_name="openpyxl",
            format_name="XLSX",
        )
    else:
        import_reader_dependency(
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


def read_delimited_file(
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


def read_text_file(path: Path) -> tuple[dict[str, pd.DataFrame], list[str]]:
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


__all__ = ["read_delimited_file", "read_excel_sheets", "read_text_file"]
