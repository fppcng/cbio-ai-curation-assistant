---
name: cbioportal_oncotree
description: Use this skill when mapping cancer types, histologies, diagnoses, or tumor subtypes to OncoTree terminology.
---

# cBioPortal OncoTree Mapping

1. Use the local OncoTree search tool:

```text
/workspace/ai_curation_assistant/tool/search_oncotree_code/search_oncotree_code.py
```

2. Search using the original disease name, histology, diagnosis, cancer type, subtype, or other tumor classification information from the source data.

3. Review the returned OncoTree candidates before selecting a mapping.

4. Use the best supported OncoTree match based on the available evidence.

5. When appropriate, use OncoTree results to help define:

```text
ONCOTREE_CODE
CANCER_TYPE
CANCER_TYPE_DETAILED
```

6. If multiple mappings appear plausible or the evidence is insufficient, document the ambiguity rather than hiding it.

7. Preserve the original source information whenever it contains information that would otherwise be lost during normalization.