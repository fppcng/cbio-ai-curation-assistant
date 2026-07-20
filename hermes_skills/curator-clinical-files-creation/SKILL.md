---
name: curator-clinical-files-creation
description: Create cBioPortal clinical data files from study publications, supplementary materials, and other available study artifacts. Use during the curation of a complete cBioPortal study or when the user specifically asks to generate, curate, or update only the clinical data files.
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

