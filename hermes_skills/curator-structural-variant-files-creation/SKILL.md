---
name: curator-structural-variant-files-creation
description: Create `data_sv.txt` and `meta_sv.txt` structural variant files for a cBioPortal study from local study artifacts that contain real per-sample structural variant or fusion calls.
required_environment_variables:
  - name: CBIO_CURATION_ASSISTANT_HOME
    prompt: Absolute path to the cBioPortal AI Curation Assistant installation directory
---

# Structural Variant File Creation

## When to use
Use this skill when the user asks to generate structural variant or fusion files for a cBioPortal study, or when a full study curation workflow needs `data_sv.txt` and `meta_sv.txt` and the local study artifacts contain source-supported per-sample structural variant calls.

## Required references
Read:
- `references/structural_variant_file_formats.md`

## Role of the curation report
Use the abstractor report as a guide for locating promising supplementary files, but always inspect the underlying supplementary files directly before deciding whether structural variant curation is supported. Do not make that decision from the abstractor report alone.

## Comments, notes and annotations in source files
When a source file is an Excel workbook, inspect any cell comments, notes, or annotations that are present. Treat them as potentially important evidence for interpreting sheet structure, column meaning, filters, exclusions, and call semantics.

## Main rules
- Only create `data_sv.txt` and `meta_sv.txt` from real per-sample structural variant or fusion rows present in local tables, spreadsheets, manifests, or reportable study artifacts.
- Do not fabricate structural variant rows from narrative mentions, cohort summaries, pathway diagrams, assay descriptions, or gene-level statements without sample-level calls.
- Do not create empty placeholder files just because structural variants are expected by the study design.
- `Sample_Id` values must match the study clinical sample identifiers when `data_clinical_sample.txt` is available.
- Use one study-level genome build only. Do not mix `GRCh37` and `GRCh38` within the same file.
- Populate required and optional columns only from source-supported values. Do not infer breakpoints, exons, transcript IDs, read counts, frame effect, or event class unless the source supports them.
- Set `SV_Status` only from supported study context or supplementary files. If the source does not support a required status for a row, do not emit that row.
- If the available evidence is insufficient for a valid structural variant file, report the gap explicitly instead of generating a speculative file.

## Workflow
1. Run workspace discovery for the requested study and parse the JSON response:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation workspace describe \
  --study-id <study_id>
```
2. Use only the absolute paths returned under discovery `result`. Do not infer paths from repository layout.
3. Ensure study source artifacts are available by inspecting `result.workspace.source` and relevant discovery availability fields.
  - If the required publication or supplementary files are missing, use the `abstractor-study-download` skill, then rerun workspace discovery.
4. Ensure the study abstractor agent report is available using `result.artifacts.curation_report_agent` and `result.availability.curation_report_agent`.
  - If it is missing, use the `abstractor-curation-report-generation` skill.
5. Read the abstractor agent report to identify promising supplementary files.
6. Read candidate supplementary files directly from the discovered source/supplementary paths to determine whether they contain real per-sample rows that satisfy the minimum evidence requirements. Do not make that decision from the abstractor report alone.
7. Determine whether the source contains real per-sample rows that satisfy the minimum evidence requirements. If not, do not create the structural variant files; report that the study does not currently support source-grounded SV curation.
8. Normalize sample identifiers against `data_clinical_sample.txt` under `result.workspace.curated` when that file already exists.
  - Do not silently rewrite sample identifiers to values that cannot be traced back to the source or clinical sample file.
  - If the source uses a trivially different delimiter form (for example `-` in one sheet and `_` in the clinical sample file) and the mapping is one-to-one, normalize it explicitly and report that normalization.
9. Determine the study genome build from the study metadata or the source artifacts before writing `NCBI_Build`.
  - If the source rows would require mixed builds or the build cannot be determined for rows that need it, report the issue instead of guessing.
10. Create `data_sv.txt` under `result.workspace.curated`.
  - Include the required columns for every emitted row.
  - Add optional columns only when they are directly supported by the source data.
11. Create `meta_sv.txt` under `result.workspace.curated` with cBioPortal-compliant structural variant metadata.
  - Use `genetic_alteration_type: STRUCTURAL_VARIANT`
  - Use `datatype: SV`
  - Use `stable_id: structural_variants`
  - Use `show_profile_in_analysis_tab: true`
  - Use `data_filename: data_sv.txt`
  - Set `cancer_study_identifier` to the same value used by the study metadata
  - Use a clear profile name and description such as `Structural variants` and `Structural Variant Data for <study_id>`
12. Review the generated files for consistency before claiming success.
  - Confirm tab-delimited formatting.
  - Confirm required headers are present.
  - Confirm `Sample_Id` values match the study sample universe.
  - Confirm no row relies on unsupported inferred values for required fields.
  - Remove or blank obviously invalid pseudo-gene values before writing `Site1_Hugo_Symbol` / `Site2_Hugo_Symbol` (for example numeric placeholders or Excel-mangled non-symbol artifacts) unless you can map them confidently to a real supported gene symbol.

## Output
Report these outcomes using paths derived from `result.workspace.curated`:
- `data_sv.txt` when source-supported structural variant rows were generated
- `meta_sv.txt` when a structural variant profile was generated
- whether the study had sufficient evidence for structural variant curation
- any omitted rows, unsupported columns, study-level assumptions, and remaining validation risks

## Important limits
- Do not confuse structural variant evidence with copy-number, mutation, or expression evidence.
- Do not claim that a fusion panel, assay, or manuscript discussion implies reportable sample-level structural variant calls.
- Do not create `meta_sv.txt` without a corresponding valid `data_sv.txt`.
