---
name: curator-oncotree-consultation
description: Use this skill when mapping cancer types, histologies, diagnoses, or tumor subtypes to OncoTree terminology.
required_environment_variables:
  - name: CBIO_CURATION_ASSISTANT_HOME
    prompt: Absolute path to the cBioPortal AI Curation Assistant installation directory
---

# cBioPortal OncoTree Mapping

## When to use
Use this skill whenever source disease labels need to be mapped to OncoTree values for cBioPortal study files.

## Tool command
Run the OncoTree search through the package CLI and the project selected by `CBIO_CURATION_ASSISTANT_HOME`:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation oncotree-search \
  -q '<disease or subtype text>' \
  --json
```

Example:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation oncotree-search \
  -q 'combined hepatocellular and intrahepatic cholangiocarcinoma' \
  --json
```

If you need to inspect a study clinical sample file, first run workspace discovery and derive the file path from `result.workspace.curated`:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation workspace describe \
  --study-id <study_id>

uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation oncotree-search \
  --clinical-file "<result.workspace.curated>/data_clinical_sample.txt" \
  --json
```

## Mapping workflow

1. Search using the original disease name, histology, diagnosis, cancer type, subtype, or other tumor classification information from the source data.
2. Check that the JSON envelope has `status: success`, then review the returned OncoTree candidates under `result` before selecting a mapping.
3. Use the best supported OncoTree match based on the available evidence.
4. When appropriate, use OncoTree results to help define:

   * `ONCOTREE_CODE`
   * `CANCER_TYPE`
   * `CANCER_TYPE_DETAILED`
5. If multiple mappings appear plausible or the evidence is insufficient, document the ambiguity rather than hiding it.
6. Preserve the original source information whenever it contains information that would otherwise be lost during normalization.

## Important rule

The OncoTree search tool returns candidate mappings only. It does not make the final mapping decision. The agent must inspect the candidate metadata and select the mapping that best preserves the source meaning.
