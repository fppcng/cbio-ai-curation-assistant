---
name: curator-cbioportal-dataset-generation
description: Generate a complete cBioPortal study dataset from local supplementary files and publication metadata. Use when asked to convert supplementary tables/files into cBioPortal study files, create study metadata and case lists, or validate a generated study against cBioPortal SOPs and file-format docs.
---

# cBioPortal Dataset Generation

Use this skill when the user wants a cBioPortal dataset generated from local supplementary files, a study raw-data directory, or publication-linked study artifacts that already exist on disk.

## Required references

Before writing or processing any files, read and understand the documentation and SOPs at:

- `references/cBioPortal_Data_Curation_SOP.md`
- `references/cBioPortal_File_Formats.md`

Treat those references as the source of truth for required files, allowed values, formatting, and study-level conventions.

## Preconditions

- The source supplementary files are already available locally.
- A study output directory is known or can be created.
- Publication metadata, manifest files, or prior abstractor outputs should be reused when available.

## Output directory

Save generated cBioPortal results under a top-level `cbioportal_dataset/` directory.

Use this structure:

```text
cbioportal_dataset/
└── <PMCID_of_the_study>/
    └── <generated cBioPortal study files>
```

Use the normalized PMCID as the study folder name, mirroring the study-per-directory pattern used under `studies/`.

Write the generated cBioPortal files for that study inside `cbioportal_dataset/<PMCID>/`.

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

1. Inventory the available inputs.
   - Identify the paper metadata, manifest, and all supplementary files.
   - Note each file's format, likely content, and whether it is already close to a cBioPortal target format.

2. Read the cBioPortal references before transforming data.
   - Use the SOP for required study structure and curation conventions.
   - Use the file-format reference for exact column requirements and file naming.

3. Create a processing plan before writing outputs.
   - List each source file.
   - Map each source file to one or more expected cBioPortal outputs.
   - Define the identifier strategy for `PATIENT_ID`, `SAMPLE_ID`, and any sample-to-patient mapping.
   - Record open questions and assumptions.

4. Establish the study root and output structure.
   - Reuse an existing study directory when the user provides one.
   - Otherwise create `cbioportal_dataset/<PMCID>/` and keep all generated files for that study there.

5. Reuse existing study metadata when available.
   - Prefer manifest files, article metadata JSON, and previously curated study-level metadata over re-deriving the same information.
   - Preserve provenance for reused metadata.

6. Normalize identifiers before file-specific transformations.
   - Identify the best patient-level and sample-level identifiers from the source files.
   - Keep mapping rules consistent across every generated file.
   - Do not silently drop identifier mismatches; report them.
   - Use the final clinical sample file as the canonical `SAMPLE_ID` vocabulary for modality-specific files.
   - If source tables drift only by a systematic formatting change such as hyphen vs underscore, reconcile them explicitly and record the rule in the assumptions / validation summary.

7. Generate clinical data first.
   - Create `data_clinical_patient.txt` when patient-level attributes are available.
   - Create `data_clinical_sample.txt` when sample-level attributes are available.
   - Preserve the correct attribute level for each field.
   - Use `curator-dictionary-consultation` when mapping source columns to standard cBioPortal clinical attributes.
   - Use `cbioportal_oncotree` when cancer-type fields need normalization to OncoTree.
   - When the study has multiple tumor samples or components per patient, preserve subtype/component detail as explicit clinical attributes instead of collapsing it into a single disease label.

8. Generate modality-specific genomic or molecular files from the supplementary data.
   - If mutation data is present, use `cbioportal_maf_curation`.
   - For other modalities, generate only the outputs that are supported by the source data and documented in the file-format reference.
   - If a source file is already very close to a cBioPortal format, curate it directly instead of rebuilding it from scratch.
   - For structural variant tables, if rows lack both partner genes, exclude them from `data_sv.txt` and report how many were dropped; gene-annotated rows are the useful cBioPortal payload.

9. Generate the required study metadata and meta files.
   - Always create the study-level metadata files required by the SOP and file-format docs.
   - Ensure each generated data file has a matching meta file with the correct file references and attributes.

10. Generate case lists for each data modality that was actually produced.
    - Case lists must reflect the final sample identifiers present in the generated dataset.
    - Do not generate case lists for modalities that were not successfully produced.
    - When the clinicopathologic sheet is broader than the sequenced/sample-linked cohort, make the case lists reflect the curated cohort actually represented in the generated files.

11. Validate the generated study before reporting completion.
    - Check that every generated file matches the documented schema and naming rules.
    - Check internal identifier consistency across patient, sample, and modality-specific files.
    - Flag unsupported rows, malformed values, and incomplete required metadata.
    - If the official cBioPortal validator is available locally, run it; otherwise perform the documented checks manually.
    - If you write summary or manifest files that enumerate generated artifacts, refresh that file list only after every late-written artifact exists on disk, including reports such as PDFs and the validation summary itself. Do not freeze `generated_files` too early and then report an incomplete inventory.

12. Report the final outcome.
    - List generated files.
    - List assumptions and unresolved issues.
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

## Use other skills

Use these local skills when relevant:

- `curator-dictionary-consultation` for clinical attribute mapping
- `cbioportal_oncotree` for disease and histology normalization
- `cbioportal_maf_curation` for mutation / MAF generation

## Output expectations

The result should include:

- the generated cBioPortal study directory under `cbioportal_dataset/<PMCID>/`
- all produced data and meta files
- case lists for generated modalities
- a concise validation summary
- a list of assumptions, warnings, and unresolved issues
