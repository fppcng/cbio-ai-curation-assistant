from __future__ import annotations


DEFAULT_VALUES = {
    "",
    "?",
    "Unknown",
}


def is_missing_metadata_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return value in DEFAULT_VALUES


def build_study_id(cancer_type: str | None, author: str | None, year: str | None) -> str | None:
    if cancer_type and author and year:
        study_id = f"{cancer_type}_{author.lower()}_{year}"
    elif author and year:
        study_id = f"study_{author.lower()}_{year}"
    else:
        return None

    return "".join(
        char if char.isalnum() or char == "_" else "_"
        for char in study_id.lower()
    ).strip("_")


def merge_missing_metadata_fields(base: dict, completion: dict) -> dict:
    merged = dict(base)
    for key, value in completion.items():
        if key not in merged or not is_missing_metadata_value(merged[key]):
            continue
        if is_missing_metadata_value(value):
            continue
        merged[key] = value

    merged["study_id_suggestion"] = build_study_id(
        cancer_type=merged.get("cancer_type"),
        author=merged.get("first_author_surname"),
        year=merged.get("year"),
    )
    return merged
