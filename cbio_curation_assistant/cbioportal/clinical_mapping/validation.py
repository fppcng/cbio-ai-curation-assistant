"""Validate Clinical Data Dictionary decisions against generated files."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from cbio_curation_assistant.cbioportal.clinical_dictionary import (
    ClinicalDictionaryAttribute,
)
from cbio_curation_assistant.cbioportal.clinical_mapping.clinical_files import (
    ClinicalHeader,
)
from cbio_curation_assistant.cbioportal.clinical_mapping.models import (
    CLINICAL_METADATA_FIELDS,
    ClinicalMappingDecision,
    ClinicalMappingReport,
    ClinicalTarget,
)


@dataclass(frozen=True, slots=True)
class ClinicalMappingValidationResult:
    """Deterministic comparison of mapping decisions and clinical headers."""

    valid: bool
    mapping_count: int
    decision_counts: Mapping[str, int]
    clinical_column_count: int
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "mapping_count": self.mapping_count,
            "decision_counts": dict(self.decision_counts),
            "clinical_column_count": self.clinical_column_count,
            "errors": list(self.errors),
        }


def _decision_targets(
    decision: ClinicalMappingDecision,
    *,
    default: str | None,
    context: str,
    errors: list[str],
) -> tuple[str, ...]:
    targets = decision.target_files
    if targets is None:
        targets = (default,) if default is not None else ()
    if not targets:
        errors.append(f"{context}: no target file was specified or inferred.")
    return targets


def _standard_metadata(
    attribute: ClinicalDictionaryAttribute,
    decision: ClinicalMappingDecision,
) -> dict[str, str]:
    expected = {
        field: str(getattr(attribute, field)) for field in CLINICAL_METADATA_FIELDS
    }
    for field, override in (decision.metadata_overrides or {}).items():
        expected[field] = override.value
    return expected


def validate_clinical_mapping_report(
    report: ClinicalMappingReport,
    *,
    dictionary: Sequence[ClinicalDictionaryAttribute],
    clinical_headers: Mapping[ClinicalTarget, ClinicalHeader],
) -> ClinicalMappingValidationResult:
    """Validate decisions, placement, coverage, and canonical header metadata."""
    errors: list[str] = []
    dictionary_by_header = {
        attribute.column_header: attribute for attribute in dictionary
    }
    expected_outputs: dict[tuple[str, str], tuple[dict[str, str], str]] = {}
    decision_counts = {"standard": 0, "custom": 0, "excluded": 0}

    for index, mapping in enumerate(report.mappings, start=1):
        context = f"Mapping {mapping.id!r}" if mapping.id else f"Mapping {index}"
        decision = mapping.decision
        if decision is None:
            errors.append(f"{context}: decision has not been completed.")
            continue
        decision_counts[decision.status] += 1
        if decision.status == "excluded":
            continue

        if decision.status == "standard":
            selected_header = decision.selected_column_header
            if selected_header is None:
                errors.append(
                    f"{context}: standard decision requires selected_column_header."
                )
                continue
            attribute = dictionary_by_header.get(selected_header)
            if attribute is None:
                errors.append(
                    f"{context}: {selected_header!r} is not in the dictionary."
                )
                continue
            if selected_header not in {
                candidate.column_header for candidate in mapping.candidates
            }:
                errors.append(
                    f"{context}: selected attribute {selected_header!r} was not "
                    "among the recorded candidates."
                )

            default_target = attribute.attribute_type.lower()
            targets = _decision_targets(
                decision,
                default=default_target,
                context=context,
                errors=errors,
            )
            for target in targets:
                if target != default_target and not (
                    selected_header == "PATIENT_ID" and target == "sample"
                ):
                    errors.append(
                        f"{context}: dictionary attribute {selected_header!r} "
                        f"belongs in {default_target}, not {target}."
                    )
            metadata = _standard_metadata(attribute, decision)
            output_header = selected_header
        else:
            custom_attribute = decision.custom_attribute
            if custom_attribute is None:
                errors.append(f"{context}: custom decision requires custom_attribute.")
                continue
            targets = _decision_targets(
                decision,
                default=None,
                context=context,
                errors=errors,
            )
            metadata = custom_attribute.metadata()
            output_header = custom_attribute.column_header

        for target in targets:
            output_key = (target, output_header)
            if output_key in expected_outputs:
                errors.append(
                    f"{context}: duplicate mapping for {target} column "
                    f"{output_header!r}."
                )
                continue
            expected_outputs[output_key] = (metadata, context)

    actual_outputs = {
        (target, header)
        for target, clinical_header in clinical_headers.items()
        for header in clinical_header.attributes
    }
    expected_output_keys = set(expected_outputs)
    for target, header in sorted(actual_outputs - expected_output_keys):
        errors.append(f"Clinical {target} column {header!r} has no mapping decision.")
    for target, header in sorted(expected_output_keys - actual_outputs):
        errors.append(
            f"Mapping decision expects missing clinical {target} column {header!r}."
        )

    for output_key in sorted(actual_outputs & expected_output_keys):
        target, header = output_key
        expected_metadata, context = expected_outputs[output_key]
        actual_metadata = clinical_headers[target].attributes[header].to_dict()
        for field in CLINICAL_METADATA_FIELDS:
            expected_value = expected_metadata.get(field)
            actual_value = actual_metadata.get(field)
            if expected_value != actual_value:
                errors.append(
                    f"{context}: {target} column {header!r} has {field} "
                    f"{actual_value!r}; expected {expected_value!r}."
                )

    return ClinicalMappingValidationResult(
        valid=not errors,
        mapping_count=len(report.mappings),
        decision_counts=decision_counts,
        clinical_column_count=len(actual_outputs),
        errors=tuple(errors),
    )


__all__ = ["ClinicalMappingValidationResult", "validate_clinical_mapping_report"]
