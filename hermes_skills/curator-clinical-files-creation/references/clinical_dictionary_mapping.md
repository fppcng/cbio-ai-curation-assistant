# Clinical Dictionary Mapping Report

## Batch search input

Use one query per clinical source field considered for output and per required
or derived output field:

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

Use `status: excluded` with a non-empty `reason` for a reviewed clinical field
that should not be emitted.

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
