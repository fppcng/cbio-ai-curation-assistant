"""Human-readable rendering for Clinical Data Dictionary commands."""

from __future__ import annotations

from pathlib import Path

from cbio_curation_assistant.cbioportal.clinical_mapping import (
    ClinicalMappingReport,
    ClinicalMappingValidationResult,
)


def print_search_report(
    report: ClinicalMappingReport,
    output_path: Path | None,
) -> None:
    print(f"Clinical dictionary queries: {len(report.mappings)}")
    if output_path is not None:
        print(f"Mapping report: {output_path.resolve()}")
    for mapping in report.mappings:
        print()
        print(f"{mapping.id}: {mapping.source.column}")
        for index, candidate in enumerate(mapping.candidates, start=1):
            print(
                f"  {index}. {candidate.column_header} "
                f"(score={candidate.score}, type={candidate.attribute_type})"
            )


def print_validation_result(result: ClinicalMappingValidationResult) -> None:
    print(f"Clinical dictionary mapping valid: {result.valid}")
    print(f"Mappings: {result.mapping_count}")
    print(f"Clinical columns: {result.clinical_column_count}")
    for error in result.errors:
        print(f"- {error}")


__all__ = ["print_search_report", "print_validation_result"]
