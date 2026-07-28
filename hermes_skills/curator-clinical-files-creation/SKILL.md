---
name: curator-clinical-files-creation
description: Create cBioPortal clinical data files from study publications, supplementary materials, and other available study artifacts. Use during the curation of a complete cBioPortal study or when the user specifically asks to generate, curate, or update only the clinical data files.
required_environment_variables:
  - name: CBIO_CURATION_ASSISTANT_HOME
    prompt: Absolute path to the cBioPortal AI Curation Assistant installation directory
---

# Workflow
1. Run workspace discovery for the requested study and parse the JSON response:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation workspace describe \
  --study-id <study_id>
```
2. Use only the absolute paths returned under discovery `result`. Do not infer paths from repository layout.
3. Read the documentation in `references/` to understand the required structure and formatting of cBioPortal clinical data files.
4. Read the abstractor agent report from `result.artifacts.curation_report_agent` when available. Use it as supporting context, not as a substitute for inspecting the source files directly. If it is not present, generate it with the `abstractor-curation-report-generation` skill, then rerun workspace discovery.
5. Select the supplementary files that may contain clinical data based on:
  - the abstractor agent report;
  - filenames;
  - file formats;
  - sheet, table, and column names.
6. Read the selected supplementary files directly from the discovered source/supplementary paths to determine their actual contents and whether they support generation of the clinical files. Do not decide that a file can or cannot be used based only on the abstractor report, filenames, or sheet names.
7. When the source is an Excel workbook, inspect any cell comments, notes, or annotations that are present. Treat them as potentially important source context for interpreting headers, values, exclusions, or sheet-level meaning.
8. For every clinical column found in the source files, run the package CLI through the project selected by `CBIO_CURATION_ASSISTANT_HOME` using the source column name:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation clinical-dictionary \
  --source-column "<source_column_name>" \
  --considered-column "<candidate_cbioportal_column>" \
  --json
```
Check that the envelope has `status: success`, then review the candidates under `result` to determine:
  - the standard cBioPortal column header;
  - whether the attribute belongs in `data_clinical_sample.txt` or `data_clinical_patient.txt`;
  - the datatype, display name, and description.
Select a candidate only when its meaning matches the source attribute. Do not choose a result based only on name similarity. If no candidate preserves the source meaning, create an appropriate custom attribute.
9. Generate clinical files under `result.workspace.curated`:
  - `meta_clinical_sample.txt`;
  - `data_clinical_sample.txt`;
  - `meta_clinical_patient.txt`, only when patient-level data is available.
  - `data_clinical_patient.txt`, only when patient-level data is available.
10. Ensure identifiers are consistent, attributes are placed at the correct level, and no unsupported mappings or transformations are introduced.

## SOMATIC_STATUS Column
- `SOMATIC_STATUS` must be included in `data_clinical_sample.txt` and assigned to each tumor sample.
- It indicates whether the tumor sample has a matched normal sample from the same patient.
- Allowed values:
* `Matched`: a matched normal sample was used for the analysis.
* `Unmatched`: the tumor was analyzed without a matched normal sample.
- The value should be determined at the sample level using the publication methods, supplementary data, sample manifests, or matched-normal information in the mutation data. It must not be inferred solely from the presence of somatic mutations.

## Policy for ambiguous source-derived clinical fields
- If a source column is clinically relevant but cannot be safely converted into a standard cBioPortal attribute, retain it as a custom attribute instead of omitting it or coercing it into an inaccurate standard field.  
- Use a custom STRING attribute when any of the following are true:
  - one cell can contain more than one measurement,
  - values are free text or mixed text/number,
  - values encode multiple lesions/components,
  - no lossless standard attribute exists,
  - source level and target level do not align,
  - a standard mapping would require undocumented collapse logic.
