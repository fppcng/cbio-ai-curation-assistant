"""
Search the local OncoTree table to support cBioPortal study curation.

Input
-----
The tool accepts one of the following:

- A cancer type.
- A histology.
- A diagnosis.
- A tumor subtype.
- An OncoTree code.
- A data_clinical_sample.txt file.

Output
------
The tool returns ranked OncoTree candidate mappings, including:

- ONCOTREE_CODE
- CANCER_TYPE
- CANCER_TYPE_DETAILED
- Tissue
- OncoTree hierarchy path
- Match score

When a clinical sample file is provided, the tool also reports
missing standard OncoTree-related columns and suggests possible
mappings for relevant clinical values.

The tool does not modify any files.
"""

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ONCOTREE_PATH = SCRIPT_DIR / "oncotree_latest_table.txt"
DEFAULT_LIMIT = 10
CODE_PATTERN = re.compile(r"^(?P<name>.*?)\s*\((?P<code>[A-Za-z0-9_]+)\)\s*$")
MISSING_VALUES = {"", "NA", "N/A", "NAN", "NULL", "NONE", "UNKNOWN"}
SEARCH_FIELDS = (
    "ONCOTREE_CODE",
    "CANCER_TYPE_DETAILED",
    "CANCER_TYPE",
    "HISTOLOGY",
    "TUMOR_TYPE",
    "SAMPLE_TYPE",
    "PRIMARY_SITE",
    "METASTATIC_SITE",
)
METADATA_COLUMN_COUNT = 5


@dataclass(frozen=True)
class OncotreeCandidate:
    """Store a normalized OncoTree lookup candidate."""

    oncotree_code: str
    cancer_type: str
    cancer_type_detailed: str
    tissue: str
    color: str
    nci_codes: str
    umls_codes: str
    path: list[str]
    source_row: int


def normalize_text(value: str) -> str:
    """Normalize text for OncoTree candidate matching.

    Args:
        value: Text to normalize.

    Returns:
        Lowercase text with punctuation collapsed to spaces.
    """
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().lower()
    return re.sub(r"\s+", " ", normalized)


def tokenize(value: str) -> set[str]:
    """Split normalized text into searchable tokens.

    Args:
        value: Text to tokenize.

    Returns:
        Set of non-empty normalized tokens.
    """
    return set(normalize_text(value).split())


def split_oncotree_label(value: str) -> tuple[str, str]:
    """Split an OncoTree level label into display name and code.

    Args:
        value: OncoTree label, often formatted as "Cancer Name (CODE)".

    Returns:
        Tuple of display name and code. The code is empty when absent.
    """
    match = CODE_PATTERN.match(value.strip())
    if not match:
        return value.strip(), ""

    return match.group("name").strip(), match.group("code").strip().upper()


def is_missing(value: str) -> bool:
    """Return whether a clinical value should be treated as missing.

    Args:
        value: Clinical table cell value.

    Returns:
        True when the value is blank or a common missing-value marker.
    """
    return value.strip().upper() in MISSING_VALUES


def clean_cell(value: str | None) -> str:
    """Convert a table cell to a stripped string.

    Args:
        value: Raw table cell value.

    Returns:
        Stripped cell text, or an empty string for missing cells.
    """
    if value is None:
        return ""

    return value.strip()


def load_oncotree_candidates(oncotree_path: Path) -> list[OncotreeCandidate]:
    """Load unique searchable OncoTree candidates from a local table.

    Args:
        oncotree_path: Path to oncotree_latest_table.txt.

    Returns:
        List of normalized OncoTree candidate records.
    """
    candidates_by_code: dict[str, OncotreeCandidate] = {}

    with oncotree_path.open("r", encoding="utf-8", newline="") as file_handle:
        reader = csv.reader(file_handle, delimiter="\t")
        next(reader, None)

        for source_row, row in enumerate(reader, start=2):
            if len(row) < METADATA_COLUMN_COUNT + 1:
                continue

            path = [clean_cell(value) for value in row[:-METADATA_COLUMN_COUNT]]
            path = [value for value in path if value]
            if not path:
                continue

            tissue_name, _ = split_oncotree_label(path[0])
            cancer_type = clean_cell(row[-5])
            color = clean_cell(row[-4])
            nci_codes = clean_cell(row[-3])
            umls_codes = clean_cell(row[-2])

            for level_value in path:
                detailed_name, code = split_oncotree_label(level_value)
                if not code:
                    continue

                candidate = OncotreeCandidate(
                    oncotree_code=code,
                    cancer_type=cancer_type or detailed_name,
                    cancer_type_detailed=detailed_name,
                    tissue=tissue_name,
                    color=color,
                    nci_codes=nci_codes,
                    umls_codes=umls_codes,
                    path=[split_oncotree_label(value)[0] for value in path],
                    source_row=source_row,
                )

                existing_candidate = candidates_by_code.get(code)
                if existing_candidate is None:
                    candidates_by_code[code] = candidate
                    continue

                if len(candidate.path) < len(existing_candidate.path):
                    candidates_by_code[code] = candidate

    return sorted(candidates_by_code.values(), key=lambda item: item.oncotree_code)


def candidate_search_text(candidate: OncotreeCandidate) -> str:
    """Build searchable text for an OncoTree candidate.

    Args:
        candidate: OncoTree candidate record.

    Returns:
        Combined searchable candidate text.
    """
    return " ".join(
        [
            candidate.oncotree_code,
            candidate.cancer_type,
            candidate.cancer_type_detailed,
            candidate.tissue,
            " ".join(candidate.path),
        ]
    )


def score_candidate(query: str, candidate: OncotreeCandidate) -> float:
    """Score an OncoTree candidate against a query.

    Args:
        query: Code, cancer type, histology, or other source text.
        candidate: Candidate record to score.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    query_clean = query.strip()
    query_upper = query_clean.upper()
    if query_upper == candidate.oncotree_code:
        return 1.0

    candidate_text = candidate_search_text(candidate)
    query_tokens = tokenize(query_clean)
    candidate_tokens = tokenize(candidate_text)
    token_score = 0.0
    if query_tokens:
        token_score = len(query_tokens & candidate_tokens) / len(query_tokens)

    name_score = SequenceMatcher(
        None,
        normalize_text(query_clean),
        normalize_text(candidate.cancer_type_detailed),
    ).ratio()
    text_score = SequenceMatcher(
        None,
        normalize_text(query_clean),
        normalize_text(candidate_text),
    ).ratio()

    return max(token_score, name_score, text_score)


def search_oncotree(
    query: str,
    candidates: list[OncotreeCandidate],
    limit: int,
    minimum_score: float,
) -> list[dict[str, Any]]:
    """Search OncoTree candidates by code or descriptive text.

    Args:
        query: Code, cancer type, histology, or other source text.
        candidates: Loaded OncoTree candidate records.
        limit: Maximum number of results to return.
        minimum_score: Minimum score required for returned candidates.

    Returns:
        Ranked candidate dictionaries with match scores.
    """
    scored_candidates = []
    for candidate in candidates:
        candidate_score = score_candidate(query, candidate)
        if candidate_score < minimum_score:
            continue

        result = asdict(candidate)
        result["score"] = round(candidate_score, 4)
        scored_candidates.append(result)

    return sorted(
        scored_candidates,
        key=lambda item: (item["score"], item["oncotree_code"]),
        reverse=True,
    )[:limit]


def read_clinical_sample(clinical_file: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a cBioPortal clinical sample file.

    Args:
        clinical_file: Path to data_clinical_sample.txt.

    Returns:
        Tuple of header column names and data rows.

    Raises:
        ValueError: If no non-comment header row is found.
    """
    with clinical_file.open("r", encoding="utf-8", newline="") as file_handle:
        reader = csv.reader(file_handle, delimiter="\t")
        header: list[str] | None = None
        rows: list[dict[str, str]] = []

        for row in reader:
            if not row:
                continue
            if row[0].startswith("#"):
                continue
            if header is None:
                header = row
                continue
            rows.append(dict(zip(header, row, strict=False)))

    if header is None:
        raise ValueError(f"No clinical sample header found in {clinical_file}.")

    return header, rows


def inspect_clinical_sample(
    clinical_file: Path,
    candidates: list[OncotreeCandidate],
    limit: int,
) -> dict[str, Any]:
    """Inspect clinical sample OncoTree-related fields.

    Args:
        clinical_file: Path to data_clinical_sample.txt.
        candidates: Loaded OncoTree candidate records.
        limit: Maximum number of example values to report.

    Returns:
        Clinical file inspection summary.
    """
    header, rows = read_clinical_sample(clinical_file)
    existing_columns = set(header)
    missing_standard_columns = [
        column
        for column in ("ONCOTREE_CODE", "CANCER_TYPE", "CANCER_TYPE_DETAILED")
        if column not in existing_columns
    ]

    summary: dict[str, Any] = {
        "clinical_file": str(clinical_file),
        "row_count": len(rows),
        "missing_standard_columns": missing_standard_columns,
        "available_search_columns": [
            column for column in SEARCH_FIELDS if column in existing_columns
        ],
        "suggestions": [],
    }

    query_values: dict[str, set[str]] = {}
    for column in SEARCH_FIELDS:
        if column not in existing_columns:
            continue
        values = {
            row.get(column, "").strip()
            for row in rows
            if not is_missing(row.get(column, ""))
        }
        query_values[column] = values

    for column, values in query_values.items():
        for value in sorted(values)[:limit]:
            matches = search_oncotree(
                query=value,
                candidates=candidates,
                limit=3,
                minimum_score=0.4,
            )
            summary["suggestions"].append(
                {
                    "source_column": column,
                    "source_value": value,
                    "matches": matches,
                }
            )

    return summary


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        None.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Search the local oncotree_latest_table.txt for candidates Codex can "
            "use when defining ONCOTREE_CODE, CANCER_TYPE, and "
            "CANCER_TYPE_DETAILED in data_clinical_sample.txt."
        )
    )
    parser.add_argument(
        "-q",
        "--query",
        help="Cancer type, histology, tissue, or OncoTree code to search.",
    )
    parser.add_argument(
        "-c",
        "--clinical-file",
        type=Path,
        help="Optional data_clinical_sample.txt file to inspect.",
    )
    parser.add_argument(
        "-o",
        "--oncotree-table",
        default=DEFAULT_ONCOTREE_PATH,
        type=Path,
        help="Path to oncotree_latest_table.txt.",
    )
    parser.add_argument(
        "-l",
        "--limit",
        default=DEFAULT_LIMIT,
        type=int,
        help="Maximum number of candidates or example values to return.",
    )
    parser.add_argument(
        "-m",
        "--minimum-score",
        default=0.25,
        type=float,
        help="Minimum similarity score for direct query results.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print output as JSON instead of a readable text report.",
    )
    return parser.parse_args()


def print_query_report(query: str, results: list[dict[str, Any]]) -> None:
    """Print a readable OncoTree query report.

    Args:
        query: Original search query.
        results: Ranked OncoTree search results.

    Returns:
        None.
    """
    print("OncoTree candidate search")
    print("=========================")
    print(f"Query: {query}")
    print()

    if not results:
        print("No candidates found above the minimum score.")
        return

    for index, result in enumerate(results, start=1):
        print(
            f"{index}. {result['oncotree_code']} "
            f"({result['score']}) - {result['cancer_type_detailed']}"
        )
        print(f"   CANCER_TYPE: {result['cancer_type']}")
        print(f"   CANCER_TYPE_DETAILED: {result['cancer_type_detailed']}")
        print(f"   Tissue: {result['tissue']}")
        print(f"   Path: {' > '.join(result['path'])}")


def print_clinical_report(summary: dict[str, Any]) -> None:
    """Print a readable clinical sample inspection report.

    Args:
        summary: Clinical sample inspection summary.

    Returns:
        None.
    """
    print("Clinical sample OncoTree inspection")
    print("===================================")
    print(f"Clinical file: {summary['clinical_file']}")
    print(f"Rows: {summary['row_count']}")
    print(
        "Missing standard columns: "
        f"{', '.join(summary['missing_standard_columns']) or 'none'}"
    )
    print(
        "Available search columns: "
        f"{', '.join(summary['available_search_columns']) or 'none'}"
    )
    print()

    if not summary["suggestions"]:
        print("No source values were available for OncoTree suggestions.")
        return

    for suggestion in summary["suggestions"]:
        print(
            f"{suggestion['source_column']}={suggestion['source_value']}"
        )
        if not suggestion["matches"]:
            print("   No confident matches.")
            continue

        for match in suggestion["matches"]:
            print(
                f"   {match['oncotree_code']} ({match['score']}) - "
                f"{match['cancer_type']} / {match['cancer_type_detailed']}"
            )


def main() -> int:
    """Run the OncoTree search command-line interface.

    Args:
        None.

    Returns:
        Process exit code.
    """
    args = parse_args()
    candidates = load_oncotree_candidates(args.oncotree_table)
    output: dict[str, Any] = {}

    if args.query:
        output["query_results"] = search_oncotree(
            query=args.query,
            candidates=candidates,
            limit=args.limit,
            minimum_score=args.minimum_score,
        )

    if args.clinical_file:
        output["clinical_inspection"] = inspect_clinical_sample(
            clinical_file=args.clinical_file,
            candidates=candidates,
            limit=args.limit,
        )

    if not output:
        raise SystemExit("Provide --query, --clinical-file, or both.")

    if args.json:
        print(json.dumps(output, indent=2))
        return 0

    if args.query:
        print_query_report(args.query, output["query_results"])
        if args.clinical_file:
            print()

    if args.clinical_file:
        print_clinical_report(output["clinical_inspection"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
