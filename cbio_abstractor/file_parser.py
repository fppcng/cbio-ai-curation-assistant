from typing import Optional, List, Dict, Tuple
"""
file_parser.py
==============
Parse any uploaded supplemental file into a pandas DataFrame,
regardless of whether it is CSV, TSV, Excel, or fixed-width.
"""

import io
import logging
import chardet
import pandas as pd

logger = logging.getLogger(__name__)


def _detect_encoding(raw: bytes) -> str:
    result = chardet.detect(raw[:50_000])
    return result.get("encoding") or "utf-8"


def _detect_separator(text: str) -> str:
    """Sniff tab vs comma vs semicolon vs pipe."""
    first_lines = "\n".join(text.splitlines()[:10])
    counts = {
        "\t": first_lines.count("\t"),
        ",": first_lines.count(","),
        ";": first_lines.count(";"),
        "|": first_lines.count("|"),
    }
    return max(counts, key=counts.get)


def parse_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """
    Parse uploaded file bytes into a DataFrame.
    Handles: .csv, .tsv, .txt, .tab, .xlsx, .xls
    Skips leading comment lines (starting with #) for display but keeps raw text.
    """
    name_lower = filename.lower()

    # Excel
    if name_lower.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
        df.columns = df.columns.str.strip()
        return df.fillna("")

    # Text / delimited
    encoding = _detect_encoding(file_bytes)
    try:
        text = file_bytes.decode(encoding)
    except Exception:
        text = file_bytes.decode("utf-8", errors="replace")

    # Skip comment header rows (cBioPortal # rows) for parsing
    lines = text.splitlines()
    data_lines = [l for l in lines if not l.startswith("#")]
    clean_text = "\n".join(data_lines)

    sep = _detect_separator(clean_text)
    df = pd.read_csv(io.StringIO(clean_text), sep=sep, dtype=str, engine="python")
    df.columns = df.columns.str.strip()
    return df.fillna("")


def get_raw_text(file_bytes: bytes, filename: str) -> str:
    """Return the raw decoded text of the file (for few-shot storage)."""
    encoding = _detect_encoding(file_bytes)
    try:
        return file_bytes.decode(encoding)
    except Exception:
        return file_bytes.decode("utf-8", errors="replace")
