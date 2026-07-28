"""Typed publication metadata shared by report workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


MetadataCount = str | int | None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value if str(item).strip())


@dataclass(frozen=True, slots=True)
class PublicationMetadata:
    """Normalized metadata used while constructing a curation report."""

    study_title: str | None = None
    cancer_type: str | None = None
    cancer_type_full: str | None = None
    num_samples: MetadataCount = None
    num_patients: MetadataCount = None
    reference_genome: str | None = None
    sequencing_types: tuple[str, ...] = ()
    pmid: str | None = None
    doi: str | None = None
    first_author_surname: str | None = None
    year: str | None = None
    journal: str | None = None
    study_id_suggestion: str | None = None
    description: str | None = None
    key_findings: tuple[str, ...] = ()
    primary_site: str | None = None
    cohort_description: str | None = None
    meta_description: str | None = None
    data_repositories: tuple[str, ...] = ()
    corresponding_authors: str | None = None

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> PublicationMetadata:
        """Validate and normalize an extraction result at the workflow boundary."""
        return cls(
            study_title=_optional_text(values.get("study_title")),
            cancer_type=_optional_text(values.get("cancer_type")),
            cancer_type_full=_optional_text(values.get("cancer_type_full")),
            num_samples=values.get("num_samples"),
            num_patients=values.get("num_patients"),
            reference_genome=_optional_text(values.get("reference_genome")),
            sequencing_types=_text_tuple(values.get("sequencing_types")),
            pmid=_optional_text(values.get("pmid")),
            doi=_optional_text(values.get("doi")),
            first_author_surname=_optional_text(values.get("first_author_surname")),
            year=_optional_text(values.get("year")),
            journal=_optional_text(values.get("journal")),
            study_id_suggestion=_optional_text(values.get("study_id_suggestion")),
            description=_optional_text(values.get("description")),
            key_findings=_text_tuple(values.get("key_findings")),
            primary_site=_optional_text(values.get("primary_site")),
            cohort_description=_optional_text(values.get("cohort_description")),
            meta_description=_optional_text(values.get("meta_description")),
            data_repositories=_text_tuple(values.get("data_repositories")),
            corresponding_authors=_optional_text(values.get("corresponding_authors")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the stable representation consumed by report renderers."""
        return {
            "study_title": self.study_title,
            "cancer_type": self.cancer_type,
            "cancer_type_full": self.cancer_type_full,
            "num_samples": self.num_samples,
            "num_patients": self.num_patients,
            "reference_genome": self.reference_genome,
            "sequencing_types": list(self.sequencing_types),
            "pmid": self.pmid,
            "doi": self.doi,
            "first_author_surname": self.first_author_surname,
            "year": self.year,
            "journal": self.journal,
            "study_id_suggestion": self.study_id_suggestion,
            "description": self.description,
            "key_findings": list(self.key_findings),
            "primary_site": self.primary_site,
            "cohort_description": self.cohort_description,
            "meta_description": self.meta_description,
            "data_repositories": list(self.data_repositories),
            "corresponding_authors": self.corresponding_authors,
        }
