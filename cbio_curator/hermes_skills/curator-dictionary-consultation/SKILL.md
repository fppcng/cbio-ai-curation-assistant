---
name: curator-dictionary-consultation
description: Use this skill when mapping source clinical columns to cBioPortal clinical attributes.
---

# cBioPortal Clinical Data Dictionary Mapping

1. Use the local Clinical Data Dictionary search tool:
`/home/cbio26/cbio-ai-curation-assistant/cbio_curator/hermes_skills/curator-dictionary-consultation/search_dictionary_candidates.py`

   CLI pattern:
   `python /home/cbio26/cbio-ai-curation-assistant/cbio_curator/hermes_skills/curator-dictionary-consultation/search_dictionary_candidates.py -s '<source column>' -c '<proposed cbioportal column>' --json`

   Example:
   `python /home/cbio26/cbio-ai-curation-assistant/cbio_curator/hermes_skills/curator-dictionary-consultation/search_dictionary_candidates.py -s 'Overall Survival (Months)' -c OS_MONTHS --json`

2. For each clinical column:

- Identify the original source column.
- Propose a cBioPortal clinical attribute.
- Search the Clinical Data Dictionary before making a final decision.

3. Review the returned candidates and their metadata before selecting an attribute.

4. Prefer standard cBioPortal Clinical Data Dictionary attributes whenever a suitable candidate exists.

5. Create a custom clinical attribute only when no suitable standard attribute can be identified.

6. Preserve the appropriate attribute level (PATIENT and SAMPLE)

7. Use the datatype and attribute definition that best matches the selected Clinical Data Dictionary attribute.

8. Record important mapping decisions and assumptions when generating mapping reports.

9. If multiple candidate attributes appear plausible, use the available documentation and source data to justify the final choice rather than selecting arbitrarily.

10. Preserve the meaning of the original source data. Do not force a mapping to a standard attribute if it would misrepresent the underlying information.