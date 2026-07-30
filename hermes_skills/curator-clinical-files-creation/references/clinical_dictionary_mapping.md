# Clinical Dictionary Mapping Report

## Batch search input

Inspect every non-empty column in the selected source sheets. Use its values,
row granularity, annotations, and study context to decide whether it contains
patient- or sample-level clinical information. Do not assume that every column
or every sheet is clinical.

Use one query per source field determined to be clinically relevant and per
required or derived output field:

```json
{
  "study_id": "study_id",
  "queries": [
    {
      "id": "source-file|sheet|source-column",
      "source_file": "supplement.xlsx",
      "source_sheet": "Clinical",
      "source_column": "IHC",
      "search_query": "immunohistochemistry findings"
    }
  ]
}
```

Keep `source_column` verbatim. `search_query` is optional and must describe
source meaning rather than name a preselected cBioPortal attribute.

## Decisions

The search command writes a report with five or fewer candidates and
`decision: null` for every query. Complete every decision before generating
the clinical files. Similarity scores rank candidates; they do not establish
semantic correctness.

For a standard mapping:

```json
{
  "status": "standard",
  "selected_column_header": "IMMUNOHISTOCHEMISTRY",
  "reason": "The source reports IHC findings for the sequenced specimen."
}
```

The target file is inferred from the selected dictionary `attribute_type`.
Use `target_files` only for an intentional structural exception, notably:

```json
{
  "status": "standard",
  "selected_column_header": "PATIENT_ID",
  "target_files": ["patient", "sample"],
  "reason": "Required patient identifier and sample-to-patient link."
}
```

For a custom mapping:

```json
{
  "status": "custom",
  "target_files": ["sample"],
  "reason": "No candidate preserves the multi-component source value.",
  "custom_attribute": {
    "column_header": "LESION_COMPONENTS",
    "display_name": "Lesion Components",
    "description": "Lesion components reported for the sample.",
    "datatype": "STRING",
    "priority": "1"
  }
}
```

Use a custom STRING attribute when no standard attribute preserves the source
meaning. Set `target_files` to `patient` when the value describes the person,
diagnosis, or patient-level clinical course and is invariant across that
patient's samples. Set it to `sample` when it describes a tumor, specimen,
biopsy, or sample-level analysis, or may vary between samples from the same
patient.

Do not drop a field after determining that it contains clinical information.
Use `status: excluded` with a non-empty `reason` only as a last resort when
subsequent inspection shows that the field is administrative noise, duplicates
an emitted field without adding information, or cannot be preserved safely
even as STRING. The absence of a suitable dictionary term is not a reason for
exclusion.

Standard mappings must use the selected dictionary display name, description,
datatype, priority, and patient/sample placement. When a documented cBioPortal
rule requires different metadata, record it explicitly:

```json
{
  "metadata_overrides": {
    "priority": {
      "value": "3000",
      "reason": "Required study-view priority for CANCER_TYPE."
    }
  }
}
```

The validator requires every emitted clinical column to have exactly one
mapping decision and rejects unrecorded metadata or placement differences.
