---
name: curator-mutation-data-file-creation
description: Create `data_mutations.txt` for a cBioPortal study by building a minimal per-sample MAF from local mutation tables and annotating it with Genome Nexus.
required_environment_variables:
  - name: CBIO_CURATION_ASSISTANT_HOME
    prompt: Absolute path to the cBioPortal AI Curation Assistant installation directory
---

# Mutation Data File Creation
Use this skill when the user wants `data_mutations.txt` generated from local mutation tables that are not already a complete cBioPortal MAF.

## Required references
Read:
- `references/minimal-maf-workflow.md`
- `references/mutation-sanity-checks.md`
- `references/mutation_data_SOP.md`
- `references/mutations_data_file_formats.md`

## Main rule
Only create `data_mutations.txt` from real per-sample variant rows with genomic coordinates and alleles. Do not fabricate mutation files from summary tables, prose, or assay flags alone.

## Workflow
1. Run workspace discovery for the requested study and parse the JSON response:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation workspace describe \
  --study-id <study_id>
```
2. Use only the absolute paths returned under discovery `result`. Do not infer paths from repository layout.
3. Confirm the explicit reference build (`GRCh37` or `GRCh38`) and normalize source sample IDs against the study clinical sample file under `result.workspace.curated` before writing mutation rows.
4. Build `minimal_mutations.maf` under `result.workspace.curated` using the minimal columns required by the local Genome Nexus runner. Add other fields only when directly supported by the source.
5. Run Genome Nexus through the package CLI and the project selected by `CBIO_CURATION_ASSISTANT_HOME`:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation genome-nexus \
  --study-id "<study_id>" \
  --genome-build <GRCh37|GRCh38>
```
6. Inspect the JSON envelope. A `success` result reports canonical files under `result`; a `partial_success` reports candidate files under `result.attempt_directory` and does not replace canonical outputs. Report failed annotations explicitly.
7. Apply the mutation sanity checks from the references before claiming the file is ready.

## Output
For a successful run, report these study files using paths returned under `result`:
- `minimal_mutations.maf`
- `data_mutations.txt`
- `annotations_errors.txt`
- `genome_nexus.log`
- any failed or partial Genome Nexus annotations
- any remaining mutation-specific warnings

For `partial_success`, report the candidate and log paths under `result`, and state that no candidate was promoted to the canonical curated output.
