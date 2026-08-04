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
8. Follow `references/clinical_dictionary_mapping.md`. In each selected sheet, inspect every non-empty source column and use its header, values, row granularity, annotations, and study context to decide whether it contains patient- or sample-level clinical information. Do not treat every column or every sheet as clinical, but do not omit a potential clinical fact merely because its header is unfamiliar or ambiguous.
9. Create one batch query for every source column determined to be clinically relevant, plus every required or derived output column. Preserve the original header; an optional `search_query` may clarify its meaning but must not propose a cBioPortal header. Run:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation clinical-dictionary search \
  --input "<clinical_dictionary_queries.json>" \
  --limit 5 \
  --output "<result.workspace.reports>/clinical_dictionary_mapping.json" \
  --json
```
Review all candidates and complete every report decision. Choose by meaning, not score alone. Standard mappings use the selected dictionary header, metadata, and `attribute_type` placement; otherwise follow the custom-attribute rules below.
10. Generate clinical files under `result.workspace.curated`:
  - `meta_clinical_sample.txt`;
  - `data_clinical_sample.txt`;
  - `meta_clinical_patient.txt`, only when patient-level data is available.
  - `data_clinical_patient.txt`, only when patient-level data is available.
11. Validate the completed report against the generated files:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation clinical-dictionary validate \
  --report "<result.workspace.reports>/clinical_dictionary_mapping.json" \
  --sample-file "<result.workspace.curated>/data_clinical_sample.txt" \
  --patient-file "<result.workspace.curated>/data_clinical_patient.txt" \
  --json
```
Omit `--patient-file` when no patient file exists. Do not finish until validation returns `status: success`.

## Clinical-column decisions
- Every queried clinical field must end with exactly one `standard`, `custom`, or `excluded` decision.
- Do not silently drop a field after determining that it contains clinical information.
- Use a custom STRING attribute when no standard attribute preserves the source meaning. Place it in `patient` when it describes the person, diagnosis, or patient-level clinical course and is invariant across that patient's samples. Place it in `sample` when it describes a tumor, specimen, biopsy, or sample-level analysis, or may vary between samples from the same patient.
- Use `excluded` only as a documented last resort when subsequent inspection shows that the field is administrative noise, duplicates an emitted field without adding information, or cannot be preserved safely even as STRING.
- Do not exclude a clinically meaningful field merely because no standard dictionary term exists or a standard mapping would require undocumented collapse.

## SOMATIC_STATUS Column
- Treat `SOMATIC_STATUS` as a strongly recommended project attribute, although it is not required by the base cBioPortal clinical-file format.
- It indicates whether the tumor sample has a matched normal sample from the same patient.
- Allowed values:
  - `Matched`: a matched normal sample was used for the analysis.
  - `Unmatched`: the tumor was analyzed without a matched normal sample.
- The value should be determined at the sample level using the publication methods, supplementary data, sample manifests, or matched-normal information in the mutation data. It must not be inferred solely from the presence of somatic mutations.
- If it cannot be determined, omit the column rather than fabricating values.
- Continue generating the remaining clinical files, but report the missing status, affected sample IDs, and mark the clinical result as partial.
