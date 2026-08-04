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

## WES/WGS assignments without a named gene panel
- A gene panel matrix is not limited to named targeted panels. The bundled cBioPortal validator accepts `WXS`, `WGS`, and `WXS/WGS` as built-in assay values; they are not gene panel stable identifiers and do not require a panel gene list or standalone gene panel definition.
- Before omitting gene panel data because a named panel or gene list is unavailable, check whether the sources explicitly report whole-exome or whole-genome sequencing for each sample and molecular profile.
- Normalize explicit WES or whole-exome sequencing evidence to `WXS`, explicit WGS or whole-genome sequencing evidence to `WGS`, and explicit evidence that both assays support the same sample-profile combination to `WXS/WGS`. This normalization is deterministic and is not fabrication.
- Do not require a source artifact to already have cBioPortal's import-ready matrix shape. Create the matrix when its sample-profile assignments can be reconstructed deterministically from explicit source fields.
- Do not propagate an assay across molecular profiles. A sample being sequenced by WES or WGS for one profile does not support assigning that assay to another profile.
- Use `NA` only when the available evidence establishes that the sample-profile combination was not profiled. If the profiling status is unresolved, report the missing evidence instead of encoding the uncertainty as `NA`.
- Reconcile every matrix column with a generated molecular-profile `stable_id`, every row with the clinical sample file, mutation assignments with the `_sequenced` case list, and structural-variant assignments with the `_sv` case list.

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
