---
name: curator-dictionary-consultation
description: Use this skill when mapping source clinical columns to cBioPortal clinical attributes.
---

# cBioPortal Clinical Data Dictionary Mapping

Use this skill whenever source clinical columns need to be mapped to cBioPortal clinical attributes.

## Tool path

Use the local Clinical Data Dictionary candidate search script:
```bash
$CBIO_ASSISTANT_REPO_ROOT/hermes_skills/curator-dictionary-consultation/scripts/search_dictionary_candidates.py
```

Run it with the project virtual environment:
```bash
$CBIO_ASSISTANT_REPO_ROOT/.venv/bin/python \
  $CBIO_ASSISTANT_REPO_ROOT/hermes_skills/curator-dictionary-consultation/scripts/search_dictionary_candidates.py \
  -s '<source column>' \
  -c '<proposed cbioportal column>' \
  --json
```

Example:
```bash
$CBIO_ASSISTANT_REPO_ROOT/.venv/bin/python \
  $CBIO_ASSISTANT_REPO_ROOT/hermes_skills/curator-dictionary-consultation/scripts/search_dictionary_candidates.py \
  -s 'Overall Survival (Months)' \
  -c OS_MONTHS \
  --json
```

## Mapping workflow
For each clinical column:
1. Identify the original source column name and meaning.
2. Propose a candidate cBioPortal clinical attribute name.
3. Search the Clinical Data Dictionary before making a final mapping decision.
4. Review the returned candidates, including:
   * `column_header`
   * `display_name`
   * `description`
   * `datatype`
   * `attribute_type`
   * `priority`
   * similarity score
5. Prefer standard cBioPortal Clinical Data Dictionary attributes whenever a suitable candidate exists.
6. Create a custom clinical attribute only when no suitable standard attribute can be identified.
7. Preserve the appropriate attribute level:

   * patient-level attributes belong in `data_clinical_patient.txt`
   * sample-level or tumor-level attributes belong in `data_clinical_sample.txt`
8. Use the datatype and attribute definition that best matches the selected Clinical Data Dictionary attribute.
9. Preserve the meaning of the original source data. Do not force a mapping to a standard attribute if it would misrepresent the underlying information.
10. If multiple candidate attributes appear plausible, use the available documentation and source data to justify the final choice rather than selecting arbitrarily.
11. Record important mapping decisions, assumptions, and custom attributes in the final dataset-generation report.

## Important rule

The dictionary search tool returns candidate mappings only. It does not make the final mapping decision. The agent must inspect the candidate metadata and select the attribute that best preserves the meaning of the source data.
