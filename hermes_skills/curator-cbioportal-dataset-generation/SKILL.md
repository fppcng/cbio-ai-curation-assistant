---
name: curator-cbioportal-dataset-generation
description: Generate and validate a complete cBioPortal study dataset from study publications and supplementary files. Use this skill when the user asks to generate a complete cBioPortal dataset.
required_environment_variables:
  - name: CBIO_CURATION_ASSISTANT_HOME
    prompt: Absolute path to the cBioPortal AI Curation Assistant installation directory
---

# cBioPortal Dataset Generation
- This is an orchestration skill. It coordinates the acquisition, extraction, generation, and validation steps required to produce a cBioPortal study dataset.

## Required references and delegated skills
- Read the documentation under ${HERMES_SKILL_DIR}/references before starting the curation workflow.
- Use cBioPortal_Data_Curation_SOP and cBioPortal_File_Formats as shared context for the overall study structure, naming conventions, allowed values, formatting requirements, validation rules, and data-transformation constraints.
- Treat these references as cross-cutting guidance for the complete dataset.
- Follow the delegated skills for detailed, file-specific generation instructions. Each delegated skill is responsible for the interpretation, mapping, transformation, and validation rules associated with the file types it generates.
- For cBioPortal file types that do not have a delegated skill, follow cBioPortal_Data_Curation_SOP and cBioPortal_File_Formats directly.
- Do not duplicate, replace, or override file-specific instructions from delegated skills unless they conflict with an explicit cBioPortal requirement documented in the references. Report any such conflict instead of resolving it silently.

## Main rules
- Generate the most complete valid study that the available source evidence supports.
- Do not invent missing values, unsupported identifiers, nonexistent molecular modalities, or source relationships that cannot be established from the available evidence.
- If a required cBioPortal file cannot be produced, report the missing evidence or unsupported requirement explicitly instead of fabricating its contents.
- If the source data supports only a partial study, generate the supported files and clearly document the remaining gaps.
- Do not fabricate required fields solely to satisfy the cBioPortal schema or validator.
- Do not claim that the study is complete unless all expected generated files are present, internally consistent, and successfully validated.
- Preserve assumptions, warnings, inferred decisions, validation errors, and unresolved issues throughout the workflow so they can be reported clearly to the user at the end.

## Workflow
1. Read the documentation under `${HERMES_SKILL_DIR}/references`.
2. Ensure that the study source artifacts are available.
  - Check for source data under: `<CBIO_CURATION_ASSISTANT_HOME>/studies/<PMCID>/raw/`
  - If the required publication or supplementary files are missing, use the `abstractor-study-download` skill.
3. Ensure that the abstractor report is available.
  - Check for: `<CBIO_CURATION_ASSISTANT_HOME>/studies/<PMCID>/reports/<study_id>_abstractor_report.json`
  - If it is missing, use the `abstractor-curation-report-generation` skill.
4. Generate the clinical data of the study using the `curator-clinical-files-creation` skill.
5. Generate the mutation data of the study using the `curator-mutation-data-file-creation` skill.
6. Generate any additional cBioPortal files supported by the available evidence.
  - Use delegated skills when they exist for the file type.
  - Otherwise follow cBioPortal_Data_Curation_SOP and cBioPortal_File_Formats directly.
7. Save all generated cBioPortal data and metadata files under: `<CBIO_CURATION_ASSISTANT_HOME>/studies/<PMCID>/curated/`.
8. Validate the generated dataset.
  - Run the cBioPortal validator against: `<CBIO_CURATION_ASSISTANT_HOME>/studies/<PMCID>/curated/`
  - Write validator artifacts under: `<CBIO_CURATION_ASSISTANT_HOME>/studies/<PMCID>/validation/`
  - Interpret validator results carefully: a warning-only run may return a non-zero exit code, so use the validator summary text as well as the exit status.
  - Do not claim successful validation unless the validator output has been reviewed.
  - If the validator cannot be executed, report the blocker explicitly.
9. Report the final outcome to the user.
  - List the generated files.
  - List omitted or unsupported files.
  - List assumptions, warnings, and unresolved issues.
  - Distinguish source-supported values from inferred decisions.
  - Distinguish generated outputs from successfully validated outputs.
  - State clearly whether the study is complete, partial, or invalid.

## How to run the cBioPortal validator
From the `<CBIO_CURATION_ASSISTANT_HOME>`, validate the generated study with:
```bash
./.venv/bin/python cbioportal_core_validator/scripts/importer/validateData.py \
  -s studies/<PMCID>/curated/ \
  -html studies/<PMCID>/validation/validator_report.html \
  -json studies/<PMCID>/validation/validator_report.json \
  -n \
  -v
```
If the validator environment is missing dependencies, report the missing dependency or environment issue to the user instead of claiming validation succeeded.
Interpret validator results carefully: a warning-only run may return a non-zero exit code, so use the validator summary text as well as the exit status before deciding whether validation failed (look at `references/validator-and-clinical-pitfalls.md`)

## Output expectations
- The workflow should produce:
  - A cBioPortal dataset under: `<CBIO_CURATION_ASSISTANT_HOME>/studies/<PMCID>/curated/`
  - Validator artifacts under: `<CBIO_CURATION_ASSISTANT_HOME>/studies/<PMCID>/validation/`
