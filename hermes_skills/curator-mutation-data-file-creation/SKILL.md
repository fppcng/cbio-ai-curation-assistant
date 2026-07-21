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

## Main rule
Only create `data_mutations.txt` from real per-sample variant rows with genomic coordinates and alleles. Do not fabricate mutation files from summary tables, prose, or assay flags alone.

## Workflow
1. Use `studies/<PMCID>/curated/` as the study workspace.
2. Confirm the explicit reference build (`GRCh37` or `GRCh38`) and normalize source sample IDs against the study clinical sample file before writing mutation rows.
3. Build `studies/<PMCID>/curated/minimal_mutations.maf` using the minimal columns required by the local Genome Nexus runner. Add other fields only when directly supported by the source.
4. Run Genome Nexus from the repository root:
```bash
"$CBIO_CURATION_ASSISTANT_HOME/.venv/bin/python" \
  hermes_skills/curator-mutation-data-file-creation/scripts/run_genome_nexus.py \
  --workspace "$CBIO_CURATION_ASSISTANT_HOME/studies/<PMCID>/curated" \
  --genome-build <GRCh37|GRCh38>
```
5. Inspect the JSON result and generated files. Treat `partial_success` as incomplete and report failed annotations explicitly.
6. Apply the mutation sanity checks from the references before claiming the file is ready.

## Output
Report these study files under `studies/<PMCID>/curated/`:
- `minimal_mutations.maf`
- `data_mutations.txt`
- `annotations_errors.txt`
- `genome_nexus.log`
- any failed or partial Genome Nexus annotations
- any remaining mutation-specific warnings
