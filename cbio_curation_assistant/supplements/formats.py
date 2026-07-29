"""Supported supplementary document and archive formats."""

SUPPORTED_SUPPLEMENT_EXTENSIONS = frozenset(
    {
        ".csv",
        ".doc",
        ".docx",
        ".maf",
        ".pdf",
        ".tab",
        ".tsv",
        ".txt",
        ".xls",
        ".xlsx",
    }
)

ARCHIVE_EXTENSIONS = frozenset(
    {".bz2", ".gz", ".tar", ".tgz", ".xz", ".zip"}
)

__all__ = ["ARCHIVE_EXTENSIONS", "SUPPORTED_SUPPLEMENT_EXTENSIONS"]
