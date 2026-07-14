# Pipeline: read the local Clinical Data Dictionary, compare a source column and proposed cBioPortal name to standard attributes, and print ranked mapping candidates.
"""Search candidate attributes in a local Clinical Data Dictionary JSON file."""

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DICTIONARY_PATH = SCRIPT_DIR / "dictionary.json"
DEFAULT_LIMIT = 10
TOKEN_MATCH_WEIGHT = 0.55
STRING_MATCH_WEIGHT = 0.45


def normalize_text(value: str) -> str:
    """Normalize text for dictionary candidate matching.

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
        value: Text to split.

    Returns:
        Set of non-empty normalized tokens.
    """
    return set(normalize_text(value).split())


def load_dictionary(dictionary_path: Path) -> list[dict[str, Any]]:
    """Load the Clinical Data Dictionary JSON list.

    Args:
        dictionary_path: Path to the local dictionary JSON file.

    Returns:
        List of dictionary attribute objects.

    Raises:
        ValueError: If the JSON root is not a list.
    """
    with dictionary_path.open("r", encoding="utf-8") as file_handle:
        dictionary = json.load(file_handle)

    if not isinstance(dictionary, list):
        raise ValueError("Clinical Data Dictionary JSON must be a list of objects.")

    return dictionary


def attribute_search_text(attribute: dict[str, Any]) -> str:
    """Build searchable text for a dictionary attribute.

    Args:
        attribute: Dictionary attribute object.

    Returns:
        Combined searchable text from key descriptive fields.
    """
    fields = [
        "column_header",
        "display_name",
        "description",
    ]
    return " ".join(str(attribute.get(field, "")) for field in fields)


def score_candidate(
    query_text: str,
    candidate_text: str,
    candidate_header: str,
    considered_column_name: str,
) -> float:
    """Score a dictionary attribute as a possible candidate.

    Args:
        query_text: Combined original and considered column names.
        candidate_text: Combined dictionary attribute text.
        candidate_header: Dictionary column_header value.
        considered_column_name: Column name Codex is considering.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    normalized_query = normalize_text(query_text)
    normalized_candidate = normalize_text(candidate_text)
    normalized_header = normalize_text(candidate_header)
    normalized_considered = normalize_text(considered_column_name)

    query_tokens = tokenize(query_text)
    candidate_tokens = tokenize(candidate_text)
    token_score = 0.0
    if query_tokens:
        token_score = len(query_tokens & candidate_tokens) / len(query_tokens)

    string_score = SequenceMatcher(
        None,
        normalized_query,
        normalized_candidate,
    ).ratio()
    header_score = SequenceMatcher(
        None,
        normalized_considered,
        normalized_header,
    ).ratio()

    if normalized_considered and normalized_considered == normalized_header:
        return 1.0

    return max(
        (TOKEN_MATCH_WEIGHT * token_score) + (STRING_MATCH_WEIGHT * string_score),
        header_score,
    )


def search_candidates(
    original_column_name: str,
    considered_column_name: str,
    dictionary: list[dict[str, Any]],
    limit: int,
    minimum_score: float,
) -> list[dict[str, Any]]:
    """Search the dictionary for candidate standard attributes.

    Args:
        original_column_name: Column name from the source data.
        considered_column_name: Column name Codex is considering using.
        dictionary: Clinical Data Dictionary entries.
        limit: Maximum number of candidates to return.
        minimum_score: Minimum score required for returned candidates.

    Returns:
        Ranked candidate dictionaries with match scores.
    """
    query_text = f"{original_column_name} {considered_column_name}"
    candidates = []

    for attribute in dictionary:
        if not isinstance(attribute, dict):
            continue

        candidate_score = score_candidate(
            query_text=query_text,
            candidate_text=attribute_search_text(attribute),
            candidate_header=str(attribute.get("column_header", "")),
            considered_column_name=considered_column_name,
        )

        if candidate_score < minimum_score:
            continue

        candidates.append(
            {
                "score": round(candidate_score, 4),
                "column_header": attribute.get("column_header", ""),
                "display_name": attribute.get("display_name", ""),
                "description": attribute.get("description", ""),
                "datatype": attribute.get("datatype", ""),
                "attribute_type": attribute.get("attribute_type", ""),
                "priority": attribute.get("priority", ""),
            }
        )

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate["score"],
            candidate["column_header"],
        ),
        reverse=True,
    )[:limit]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        None.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Search the local Clinical Data Dictionary for possible standard "
            "cBioPortal clinical attributes. This tool returns candidates only "
            "and does not decide the mapping."
        ),
    )
    parser.add_argument(
        "-s",
        "--source-column",
        required=True,
        help="Original column name from the source data.",
    )
    parser.add_argument(
        "-c",
        "--considered-column",
        required=True,
        help="Column name Codex is considering using.",
    )
    parser.add_argument(
        "-d",
        "--dictionary",
        default=DEFAULT_DICTIONARY_PATH,
        type=Path,
        help="Path to the Clinical Data Dictionary JSON file.",
    )
    parser.add_argument(
        "-l",
        "--limit",
        default=DEFAULT_LIMIT,
        type=int,
        help="Maximum number of candidates to return.",
    )
    parser.add_argument(
        "-m",
        "--minimum-score",
        default=0.2,
        type=float,
        help="Minimum similarity score for returned candidates.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print candidates as JSON instead of a readable text report.",
    )
    return parser.parse_args()


def print_text_report(
    original_column_name: str,
    considered_column_name: str,
    candidates: list[dict[str, Any]],
) -> None:
    """Print a readable candidate report.

    Args:
        original_column_name: Column name from the source data.
        considered_column_name: Column name Codex is considering using.
        candidates: Ranked dictionary candidates.

    Returns:
        None.
    """
    print("Clinical Data Dictionary candidate search")
    print("========================================")
    print(f"Source column: {original_column_name}")
    print(f"Considered column: {considered_column_name}")
    print()

    if not candidates:
        print("No candidates found above the minimum score.")
        return

    for index, candidate in enumerate(candidates, start=1):
        print(f"{index}. {candidate['column_header']} (score={candidate['score']})")
        print(f"   Display name: {candidate['display_name']}")
        print(f"   Description: {candidate['description']}")
        print(f"   Datatype: {candidate['datatype']}")
        print(f"   Attribute type: {candidate['attribute_type']}")
        print(f"   Priority: {candidate['priority']}")


def main() -> int:
    """Run the candidate search command-line interface.

    Args:
        None.

    Returns:
        Process exit code.
    """
    args = parse_args()
    dictionary = load_dictionary(args.dictionary)
    candidates = search_candidates(
        original_column_name=args.source_column,
        considered_column_name=args.considered_column,
        dictionary=dictionary,
        limit=args.limit,
        minimum_score=args.minimum_score,
    )

    if args.json:
        print(json.dumps(candidates, indent=2))
    else:
        print_text_report(args.source_column, args.considered_column, candidates)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
