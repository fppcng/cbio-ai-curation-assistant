---
name: curator-clinical-files-creation
description: Create cBioPortal clinical data files from study publications, supplementary materials, and other available study artifacts. Use during the curation of a complete cBioPortal study or when the user specifically asks to generate, curate, or update only the clinical data files.
required_environment_variables:
  - name: CBIO_CURATION_ASSISTANT_HOME
    prompt: Absolute path to the cBioPortal AI Curation Assistant installation directory
---

# Workflow
1. Read the documentation in references/ to understand the required structure and formatting of cBioPortal clinical data files.
2. Read the abstractor report of the study to identify the contents and structure of the available supplementary files. If the abstractor report is not present generate the study with the skill `abstractor-curation-report-generation`
3. Select and inspect the supplementary files that may contain clinical data based on:
  - the abstractor report;
  - filenames;
  - file formats;
  - sheet, table, and column names.
4. For every clinical column found in the source files, run `scripts/consult_clinical_dictionary.py` using the source column name. Review the returned candidates to determine:
  - the standard cBioPortal column header;
  - whether the attribute belongs in `data_clinical_sample.txt` or `data_clinical_patient.txt`;
  - the datatype, display name, and description.
Select a candidate only when its meaning matches the source attribute. Do not choose a result based only on name similarity. If no candidate preserves the source meaning, create an appropriate custom attribute.
5. Generate:
  - meta_clinical_sample.txt;
  - data_clinical_sample.txt;
  - meta_clinical_patient.txt, only when patient-level data is available.
  - data_clinical_patient.txt, only when patient-level data is available.
6. Ensure identifiers are consistent, attributes are placed at the correct level, and no unsupported mappings or transformations are introduced.

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