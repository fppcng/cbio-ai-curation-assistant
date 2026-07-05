---
name: curator-cbioportal-dataset-generation
description: Generate a complete cBioPortal study dataset from local supplementary files plus the matching cbioabstractor report JSON. Use when asked to convert study artifacts into cBioPortal study files, create study metadata and case lists, or validate a generated study against cBioPortal SOPs and file-format docs.
---

# cBioPortal Dataset Generation

Use this skill when the user wants a cBioPortal dataset generated from local supplementary files and study artifacts that already exist on disk.

## Path anchor

Treat `/home/cbio26/cbio-ai-curation-assistant` as the repository root.

## Required references

Before writing or processing any files, read and understand:

- `references/cBioPortal_Data_Curation_SOP.md`
- `references/cBioPortal_File_Formats.md`

Treat those references as the source of truth for schema, required study structure, allowed values, file naming, formatting, validation rules, and data-transformation requirements.

## Required study context

Before generating the dataset, locate and use the matching cbioabstractor report JSON for the study.

Treat that report as required context for:

- study-level metadata
- disease and cohort description
- expected data modalities
- supplementary file interpretation
- previously established assumptions or warnings

Prefer the report JSON over re-deriving the same study context from scratch. Reuse local manifests, article metadata, and other study artifacts when they agree with the report.

If the matching cbioabstractor report JSON is missing, report that explicitly before claiming a complete dataset.

The canonical location is typically `studies/<PMCID>/reports/*.json`.

## Output directory

Save generated cBioPortal results under `cbioportal_dataset/<PMCID>/`.

## Main rule

Generate the most complete valid study that the source data supports, but do not invent missing values, unsupported identifiers, or nonexistent modalities.

If a required cBioPortal file cannot be produced from the available evidence, report it explicitly instead of fabricating it.

## Scope

This skill covers end-to-end dataset generation from local inputs, including:

- study metadata files
- clinical patient data
- clinical sample data
- mutation / MAF files
- copy-number, structural variant, fusion, or expression outputs when supported by the source files
- case lists
- study validation and issue reporting

## Workflow

1. Read the required references and load the matching cbioabstractor report JSON.
2. Inventory the available local inputs.
   - Identify supplementary files, manifests, paper metadata, and prior study artifacts.
   - Use the report JSON to understand the study context before inferring outputs.
3. Create a short processing plan before writing outputs.
   - List source files.
   - Map them to expected cBioPortal outputs.
   - Define the identifier strategy for `PATIENT_ID` and `SAMPLE_ID`.
   - Record open questions and assumptions.
4. Reuse study metadata from the cbioabstractor report JSON whenever possible.
   - Do not re-derive metadata that is already available in the report unless the source files clearly contradict it.
   - Preserve provenance for reused metadata.
5. Generate only the cBioPortal files supported by the evidence.
   - Always create required study metadata and matching meta files for every produced data file.
   - Generate clinical data first, then modality-specific files, then case lists.
   - Keep patient and sample identifiers consistent across all outputs.
6. Use other local skills when relevant.
   - Use `curator-dictionary-consultation` for clinical attribute mapping.
   - Use `cbioportal_oncotree` for disease and histology normalization.
   - Use `cbioportal_maf_curation` for mutation / MAF generation.
7. Validate before reporting completion.
   - Check schema, naming, and identifier consistency.
   - Flag unsupported rows, malformed values, and incomplete required metadata.
   - Run the cBioPortal validator and report its result.
   - Interpret validator results carefully: a warning-only run may return a non-zero exit code, so use the validator summary text as well as the exit status.
   - Watch for common clinical pitfalls: duplicate attribute names across patient/sample files, patient rows with no generated samples, and invalid placeholder colors in `cancer_type.txt`.
   - See `references/validator-and-clinical-pitfalls.md` for concrete fixes and caveats.
8. Report the final outcome.
   - List generated files.
   - List assumptions, warnings, and unresolved issues.
   - Distinguish validated outputs from inferred decisions.

## File-classification guidance

When classifying supplementary files:

- prefer the actual columns and values over the filename alone
- one source file may contribute to multiple cBioPortal outputs
- not every supplementary file should become a cBioPortal file
- keep unsupported or ambiguous files out of the final dataset until the ambiguity is explained

## Validation rules

- Do not claim a study is complete unless all required generated files are present and internally consistent.
- Do not fabricate required fields simply to satisfy a schema.
- If the source data only supports a partial study, produce the partial study and explain the gaps.
- Keep all transformations reproducible and easy to trace back to the source supplementary files.
- Do not skip the final validator run silently. If the validator cannot be executed, report the blocker explicitly.

## Final validation command

From the repository root, validate the generated study with:

```bash
./.venv/bin/python cbioportal_core_validator/scripts/importer/validateData.py \
  -s cbioportal_dataset/<PMCID>/ \
  -n \
  -v
```

Use that interpreter and script path unless the user provides a different validator environment explicitly.

If the validator environment is missing dependencies, report the missing dependency or environment issue instead of claiming validation succeeded.

## Output expectations

The result should include:

- the generated cBioPortal study directory under `cbioportal_dataset/<PMCID>/`
- all produced data and meta files
- case lists for generated modalities
- a concise validation summary
- a list of assumptions, warnings, and unresolved issues
