---
name: gene-panel-data-creation
description: Create cBioPortal gene panel matrix files and source-supported gene panel assignments from local study artifacts.
required_environment_variables:
  - name: CBIO_CURATION_ASSISTANT_HOME
    prompt: Absolute path to the cBioPortal AI Curation Assistant installation directory
---

# Gene Panel Data Creation

## Required reference
Read:
- `references/gene_panel_data.md`

## Main rules
- Create gene panel data only when the source artifacts support the required panel identifiers, sample assignments, and molecular profiles.
- Do not infer gene panel identifiers, panel membership, or sample-to-panel assignments.
- Use the `gene_panel` property in a molecular profile meta file when all samples in that profile use the same panel.
- Create a gene panel matrix when assignments vary by sample or molecular profile, or when profiled samples without reported alterations must be represented.
- Report unsupported or missing information instead of creating placeholder values.

## Workflow
1. Run workspace discovery for the requested study and parse the JSON response:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation workspace describe \
  --study-id <study_id>
```
2. Use only paths returned by the workspace command.
3. Review the curation report and inspect the underlying source artifacts.
4. Determine whether a profile-level `gene_panel` property or a gene panel matrix is appropriate.
5. Reconcile sample identifiers and molecular profile stable identifiers with the other study files.
6. Create the supported data and meta files under the workspace `curated/` directory, following the required reference.
7. Check tab separation, required fields, identifier consistency, and sample coverage.

## Output
Report:
- created or updated file paths;
- the evidence used for each assignment;
- any gene panel output omitted because the required evidence was unavailable.
