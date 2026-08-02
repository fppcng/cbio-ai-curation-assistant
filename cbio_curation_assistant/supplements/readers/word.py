"""Read Word supplementary documents."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from types import ModuleType

import pandas as pd

from cbio_curation_assistant.supplements.readers.contracts import (
    MissingExternalReaderError,
    SupplementaryParseError,
)
from cbio_curation_assistant.supplements.readers.dependencies import (
    import_reader_dependency,
)


def read_word_file(
    path: Path,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    docx_module = import_reader_dependency(
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
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
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


__all__ = ["read_word_file"]
