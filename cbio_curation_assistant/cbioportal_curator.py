"""
Shared helpers used by the modern curation report generator.

This module is intentionally limited to the code paths exercised by
`hermes_skills/abstractor-curation-report-generation/scripts/abstractor_report_generator.py`:

1. Extract text from the paper PDF.
2. Extract study metadata with the LLM prompt plus regex fallback.
3. Read supplementary files into sheet-like DataFrames.
4. Classify each sheet into a cBioPortal-oriented record consumed by the report.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
from PyPDF2 import PdfReader

from cbio_curation_assistant.config import LLMConfig
from cbio_curation_assistant.llm_client import call_llm_with_retry, parse_llm_json
from cbio_curation_assistant.pdf_metadata_regex import (
    extract_metadata_regex as _extract_metadata_regex,
)
from cbio_curation_assistant.spec_match import ClassificationResult, classify_sheet

CURABILITY = {
    "CLINICAL_PATIENT": ("YES", "HIGH"),
    "CLINICAL_SAMPLE": ("YES", "HIGH"),
    "MUTATION_MAF": ("PARTIAL", "HIGH"),
    "STRUCTURAL_VARIANT": ("YES", "HIGH"),
    "DISCRETE_CNA": ("PARTIAL", "MEDIUM"),
    "CONTINUOUS_CNA": ("PARTIAL", "MEDIUM"),
    "SEGMENTED": ("PARTIAL", "MEDIUM"),
    "EXPRESSION": ("PARTIAL", "MEDIUM"),
    "METHYLATION": ("PARTIAL", "LOW"),
    "MUTSIG": ("PARTIAL", "MEDIUM"),
    "GISTIC": ("PARTIAL", "MEDIUM"),
    "GENERIC_ASSAY": ("PARTIAL", "LOW"),
    "NOT_LOADABLE": ("NO", "N/A"),
}

SYSTEM_PROMPT_CURATOR = """
You are an expert bioinformatics data curator specialising in the cBioPortal
platform (https://docs.cbioportal.org/file-formats/).

When given text extracted from a cancer genomics paper, extract the following
study metadata and return it as a JSON object with exactly these keys:

{
  "study_title": "...",
  "cancer_type": "...",           // short abbreviation e.g. brca, gist, luad
  "cancer_type_full": "...",      // e.g. Breast Invasive Carcinoma
  "num_samples": "...",           // integer or string
  "num_patients": "...",          // integer or string
  "reference_genome": "...",      // hg19 or hg38
  "sequencing_types": ["..."],    // e.g. ["WES","WGS","WTS"]
  "pmid": "...",                  // PubMed ID if mentioned
  "doi": "...",                   // DOI string
  "first_author_surname": "...",
  "year": "...",
  "journal": "...",
  "study_id_suggestion": "...",   // snake_case e.g. gist_xie_2024
  "description": "...",           // one sentence
  "key_findings": ["..."],        // up to 5 bullet points
  "primary_site": "...",          // anatomical site e.g. "Stomach and small intestine"
  "cohort_description": "...",    // one sentence describing the cohort composition
  "meta_description": "...",      // concise description for meta_study.txt (200 chars max)
  "data_repositories": ["..."],   // GEO/GDC/SRA accession strings mentioned in paper
  "corresponding_authors": "..."  // name and email of corresponding authors if mentioned
}

Return ONLY the JSON — no markdown fences, no extra text.
"""


def _extract_pdf_text(pdf_path: str, max_pages: int = 12) -> str:
    reader = PdfReader(pdf_path)
    pages = reader.pages[:max_pages]
    return "\n".join(page.extract_text() or "" for page in pages)


def _read_excel_sheets(path: str) -> dict[str, pd.DataFrame]:
    """Return non-empty sheets as DataFrames, stripping blank leading rows."""
    xl = pd.ExcelFile(path)
    sheets: dict[str, pd.DataFrame] = {}
    for name in xl.sheet_names:
        df = xl.parse(name, header=None)
        df = df.dropna(how="all")
        if df.empty:
            continue
        sheets[name] = df
    return sheets


def _read_file_as_sheets(path: str) -> dict[str, pd.DataFrame]:
    """
    Return a dict of sheet-like DataFrames for any supported supplementary file.

    Supported formats:
      .xlsx / .xls
      .csv
      .tsv / .tab / .maf
      .txt
      .doc / .docx
      .pdf
    """
    ext = Path(path).suffix.lower()

    if ext in (".xlsx", ".xls"):
        return _read_excel_sheets(path)

    if ext == ".csv":
        df = pd.read_csv(path, header=None, dtype=str, encoding_errors="replace")
        return {"Sheet1": df.dropna(how="all")}

    if ext in (".tsv", ".tab", ".maf"):
        df = pd.read_csv(path, sep="\t", header=None, dtype=str, encoding_errors="replace")
        return {"Sheet1": df.dropna(how="all")}

    if ext == ".txt":
        raw = Path(path).read_text(encoding="utf-8", errors="replace")[:4096]
        counts = {
            "\t": raw.count("\t"),
            ",": raw.count(","),
            "|": raw.count("|"),
            " ": raw.count(" "),
        }
        sep = max(counts, key=counts.get)
        if counts[sep] == 0:
            sep = "\t"
        df = pd.read_csv(
            path,
            sep=sep,
            header=None,
            dtype=str,
            encoding_errors="replace",
            on_bad_lines="skip",
        )
        return {"Sheet1": df.dropna(how="all")}

    if ext in (".doc", ".docx"):
        try:
            from docx import Document as _DocxDoc
        except ImportError as exc:
            raise ImportError(
                "python-docx is required to read .doc/.docx files. Install with: pip install python-docx"
            ) from exc

        if ext == ".doc":
            if shutil.which("libreoffice"):
                with tempfile.TemporaryDirectory() as tmp:
                    subprocess.run(
                        ["libreoffice", "--headless", "--convert-to", "docx", "--outdir", tmp, path],
                        capture_output=True,
                        timeout=30,
                    )
                    converted = list(Path(tmp).glob("*.docx"))
                    if converted:
                        path = str(converted[0])
                        ext = ".docx"
                    else:
                        ext = "_unknown"
            else:
                ext = "_unknown"

        if ext == ".docx":
            doc = _DocxDoc(path)
            result: dict[str, pd.DataFrame] = {}

            for index, table in enumerate(doc.tables, start=1):
                rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
                if rows:
                    result[f"Table_{index}"] = pd.DataFrame(rows).dropna(how="all")

            paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
            if paragraphs:
                result["Text"] = pd.DataFrame(paragraphs, columns=None)

            if not result:
                result["Sheet1"] = pd.DataFrame()
            return result

        try:
            lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
            lines = [line for line in lines if line.strip()]
            return {"Sheet1": pd.DataFrame(lines, columns=None)}
        except Exception:
            return {"Sheet1": pd.DataFrame()}

    if ext == ".pdf":
        try:
            import pdfplumber

            sheets: dict[str, pd.DataFrame] = {}
            with pdfplumber.open(path) as pdf:
                for page_index, page in enumerate(pdf.pages, start=1):
                    for table_index, table in enumerate(page.extract_tables() or [], start=1):
                        if table:
                            sheets[f"Page{page_index}_Table{table_index}"] = (
                                pd.DataFrame(table).dropna(how="all")
                            )
                if not sheets:
                    lines: list[str] = []
                    for page in pdf.pages:
                        text = page.extract_text() or ""
                        lines.extend(line for line in text.splitlines() if line.strip())
                    sheets["Text"] = pd.DataFrame(lines, columns=None)
            return sheets
        except ImportError:
            import pypdf

            reader = pypdf.PdfReader(path)
            lines: list[str] = []
            for page in reader.pages:
                text = page.extract_text() or ""
                lines.extend(line for line in text.splitlines() if line.strip())
            return {"Text": pd.DataFrame(lines, columns=None)}

    try:
        return _read_excel_sheets(path)
    except Exception:
        pass

    try:
        df = pd.read_csv(
            path,
            sep="\t",
            header=None,
            dtype=str,
            encoding_errors="replace",
            on_bad_lines="skip",
        )
        return {"Sheet1": df.dropna(how="all")}
    except Exception as exc:
        raise ValueError(f"Unsupported file format for: {path}") from exc


def _extract_metadata_llm(pdf_text: str, llm_config: LLMConfig, temperature: float) -> dict[str, Any]:
    _ = temperature
    raw = call_llm_with_retry(
        config=llm_config,
        system=SYSTEM_PROMPT_CURATOR,
        user_content=pdf_text[:12000],
        max_tokens=2000,
    ).strip()
    try:
        llm_data = parse_llm_json(raw)
    except Exception as exc:
        logging.warning("LLM JSON parse failed (%s); using regex fallback.", exc)
        llm_data = {}

    fallback = _extract_metadata_regex(pdf_text)
    merged = {**fallback}
    for key, value in llm_data.items():
        if value and value not in ("?", "...", "Unknown", "mixed", "study_2024", ""):
            merged[key] = value
    return merged


def _build_report_record(cr: ClassificationResult) -> dict[str, Any]:
    curability, priority = CURABILITY.get(cr.format_key, ("NO", "N/A"))
    return {
        "classification": cr.format_key,
        "cbio_target_file": cr.target_file,
        "curability": curability,
        "priority": priority,
        "confidence": cr.confidence,
        "verdict": cr.verdict,
        "required_present": cr.required_present,
        "required_missing": cr.required_missing,
        "optional_present": cr.optional_present,
    }


def _build_failed_supplementary_record(
    file_name: str,
    sheet_name: str,
    error: Exception,
) -> dict[str, Any]:
    return {
        "file": file_name,
        "sheet": sheet_name,
        "classification": "NOT_LOADABLE",
        "cbio_target_file": "N/A",
        "curability": "NO",
        "priority": "N/A",
        "confidence": 0,
        "verdict": f"Parse error: {error}",
        "required_present": [],
        "required_missing": [],
        "optional_present": [],
    }


def _analyse_supplementary_files(supp_paths: list[str]) -> list[dict[str, Any]]:
    """Inspect each sheet in each supplementary file and return report records."""
    records: list[dict[str, Any]] = []
    for path in supp_paths:
        file_name = Path(path).name
        try:
            sheets = _read_file_as_sheets(path)
        except Exception as exc:
            records.append(_build_failed_supplementary_record(file_name, "-", exc))
            continue

        for sheet_name, df in sheets.items():
            try:
                record = _build_report_record(classify_sheet(df))
            except Exception as exc:
                records.append(_build_failed_supplementary_record(file_name, sheet_name, exc))
                continue

            record["file"] = file_name
            record["sheet"] = sheet_name
            records.append(record)

    return records


__all__ = [
    "SYSTEM_PROMPT_CURATOR",
    "_analyse_supplementary_files",
    "_extract_metadata_llm",
    "_extract_pdf_text",
]
