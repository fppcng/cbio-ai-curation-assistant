---
name: curator-oncotree-consultation
description: Use this skill when mapping cancer types, histologies, diagnoses, or tumor subtypes to OncoTree terminology.
---

# cBioPortal OncoTree Mapping

Use this skill whenever source disease labels need to be mapped to OncoTree values for cBioPortal study files.

## Prerequisites - Environment verification

Before running the workflow, verify that the Hermes environment has loaded the required repository root.

Run:

```bash
test -n "$CBIO_ASSISTANT_REPO_ROOT"
test -d "$CBIO_ASSISTANT_REPO_ROOT"
test -x "$CBIO_ASSISTANT_REPO_ROOT/.venv/bin/python"

printf 'CBIO_ASSISTANT_REPO_ROOT=%s\n' "$CBIO_ASSISTANT_REPO_ROOT"
```

If any check fails, stop and report that the Hermes environment was not loaded correctly or that `CBIO_ASSISTANT_REPO_ROOT` does not point to a valid repository.

## Tool path

Use the local OncoTree search script:
```bash
$CBIO_ASSISTANT_REPO_ROOT/hermes_skills/curator-oncotree-consultation/scripts/search_oncotree_code.py
```

Run it with the project virtual environment:
```bash
"$CBIO_ASSISTANT_REPO_ROOT/.venv/bin/python" \
  "$CBIO_ASSISTANT_REPO_ROOT/hermes_skills/curator-oncotree-consultation/scripts/search_oncotree_code.py" \
  -q '<disease or subtype text>' \
  --json
```

Example:
```bash
"$CBIO_ASSISTANT_REPO_ROOT/.venv/bin/python" \
  "$CBIO_ASSISTANT_REPO_ROOT/hermes_skills/curator-oncotree-consultation/scripts/search_oncotree_code.py" \
  -q 'combined hepatocellular and intrahepatic cholangiocarcinoma' \
  --json
```

If you need to inspect a clinical sample file for missing OncoTree fields and suggested mappings:
```bash
"$CBIO_ASSISTANT_REPO_ROOT/.venv/bin/python" \
  "$CBIO_ASSISTANT_REPO_ROOT/hermes_skills/curator-oncotree-consultation/scripts/search_oncotree_code.py" \
  --clinical-file "$CBIO_ASSISTANT_REPO_ROOT/studies/<PMCID>/curated/data_clinical_sample.txt" \
  --json
```

## Mapping workflow

1. Search using the original disease name, histology, diagnosis, cancer type, subtype, or other tumor classification information from the source data.
2. Review the returned OncoTree candidates before selecting a mapping.
3. Use the best supported OncoTree match based on the available evidence.
4. When appropriate, use OncoTree results to help define:

   * `ONCOTREE_CODE`
   * `CANCER_TYPE`
   * `CANCER_TYPE_DETAILED`
5. If multiple mappings appear plausible or the evidence is insufficient, document the ambiguity rather than hiding it.
6. Preserve the original source information whenever it contains information that would otherwise be lost during normalization.

## Important rule

The OncoTree search tool returns candidate mappings only. It does not make the final mapping decision. The agent must inspect the candidate metadata and select the mapping that best preserves the source meaning.
