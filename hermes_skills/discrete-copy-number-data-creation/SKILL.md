---
name: discrete-copy-number-data-creation
description: Create and validate cBioPortal discrete copy-number alteration files in DISCRETE or DISCRETE_LONG format from source-supported study data.
required_environment_variables:
  - name: CBIO_CURATION_ASSISTANT_HOME
    prompt: Absolute path to the cBioPortal AI Curation Assistant installation directory
---

# Discrete Copy Number Data Creation
## Required reference
Read:
- `references/discrete_copy_number_data.md`

## Main rules
- Create CNA data only when the source supports the gene, sample, and copy-number calls.
- Do not invent gene identifiers, sample identifiers, CNA values, or sequencing coverage.
- Accepted CNA values are `-2`, `-1.5`, `-1`, `0`, `1`, `2`, and `NA`. Use `-1.5` only when supported by the source or required by its calling scheme.

## Wide format (`DISCRETE`)
- The header must contain at least one of `Hugo_Symbol` and `Entrez_Gene_Id`; include both when available.
- Gene identifier columns must precede all sample columns.
- At least one sample column is required. Sample IDs must match the clinical samples and cannot contain spaces.
- `Cytoband` is optional.
- Blank cells are allowed. Duplicate gene rows produce a validator warning and later rows may be ignored.

## Long format (`DISCRETE_LONG`)
- Required columns: `Sample_Id` and `Value`.
- At least one of `Hugo_Symbol` and `Entrez_Gene_Id` is required.
- Optional columns: `cbp_driver`, `cbp_driver_annotation`, `cbp_driver_tiers`, and `cbp_driver_tiers_annotation`.
- Column order is flexible; blank cells are allowed.
- A gene-sample combination must occur only once. Conflicting Hugo symbols for the same Entrez gene in one sample are invalid.

## Format selection (`DISCRETE` vs `DISCRETE_LONG`)
Choose the supported format that requires the least transformation of the source data.
- Use `DISCRETE` when the source data is already organized as a gene-by-sample matrix or can be represented as one directly.
- Use `DISCRETE_LONG` when the source data is already organized as one record per gene-sample combination.
- Do not convert between wide and long formats unless required for cBioPortal compatibility, annotations, or validation.
- Prefer the format that minimizes parsing, reshaping, inferred values, duplicated data, and output size.
- Preserve all explicit source values, including `0`, `NA`, and blank cells, according to their supported meaning.
- Do not omit explicit `0` calls merely to produce a smaller sparse long file.
- Do not create missing gene-sample combinations merely to produce a complete wide matrix.
- When both formats require comparable effort and preserve the same information, prefer `DISCRETE`.

## Metadata and annotations
Required metadata fields:
- cancer_study_identifier
- genetic_alteration_type: COPY_NUMBER_ALTERATION
- datatype: DISCRETE or DISCRETE_LONG
- stable_id
- show_profile_in_analysis_tab
- profile_name
- profile_description
- data_filename

## Workflow
1. Run workspace discovery for the requested study and parse the JSON response:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation workspace describe \
  --study-id <study_id>
```
2. Use only the absolute paths returned under discovery `result`. Do not infer paths from repository layout.
3. Read the reference and inspect the source evidence for genes, samples, assay type, and CNA calls.
4. Choose wide or long format and create the data and metadata files under the curated workspace.
5. Reconcile sample IDs, gene identifiers, case lists, and any gene-panel assignment.

## Output
Report:
- created data, metadata, case-list, and annotation files;
- source evidence supporting the CNA values and profile metadata;
- omitted files and any validator errors or warnings.
