---
name: abstractor-study-download
description: Use this skill when asked to download or reuse a study article XML/PDF and supplementary files from PMC using a PMID or PMCID, storing them under the local cbio-ai-curation-assistant studies directory without redownloading files that already exist.
required_environment_variables:
  - name: CBIO_CURATION_ASSISTANT_HOME
    prompt: Absolute path to the cBioPortal AI Curation Assistant installation directory
---

# cBioPortal study download

## When to use
Use this skill when the user asks to download study artifacts for a paper identified by PMID or PMCID.

## Core rules
- Never redownload study assets that already exist locally unless the user explicitly asks to refresh or overwrite them.
- Treat the resolved PMCID as the canonical study identifier for the whole run.
- The storage root is `$CBIO_CURATION_ASSISTANT_HOME/studies/<PMCID>/raw/`.

## Procedure
1. Check whether `$CBIO_CURATION_ASSISTANT_HOME/studies/<PMCID>/raw/manifest.json` already exists and still points to files that are present on disk.
2. If the manifest and files are already present, reuse them and report that the study artifacts already existed locally.
3. Otherwise use the script ${HERMES_SKILL_DIR}/abstractor_study_download.py with the following command:
```bash
  "${HERMES_SKILL_DIR}/scripts/abstractor_study_download.py" \
  "<identifier>" \
  --studies-root "$CBIO_CURATION_ASSISTANT_HOME/studies" \
  --output-json "$CBIO_CURATION_ASSISTANT_HOME/studies/<identifier>_download_result.json"
```
4. After the run, verify the manifest, the download result file and the study files on disk under `$CBIO_CURATION_ASSISTANT_HOME/studies/<PMCID>/raw/`.

## What the abstractor_study_download.py script owns
The script deterministically handles:
- PMID/PMCID normalization
- study directory layout
- XML download
- supplementary download
- article PDF attempt when available
- manifest generation
- partial-download reporting through its result payload

Do not restate those implementation details in agent reasoning unless they are directly relevant to a failure or debugging step.

## Reporting requirements
- Report the resolved PMID/PMCID mapping when useful, especially for numeric-only input.
- Report the canonical study path: `$CBIO_CURATION_ASSISTANT_HOME/studies/<PMCID>/`.
- Report the canonical raw-artifacts path: `$CBIO_CURATION_ASSISTANT_HOME/studies/<PMCID>/raw/`.
- Report the actual artifacts present on disk:
  - XML path
  - article PDF path if present, otherwise say it was unavailable
  - supplementary files actually present
- If the script reports warnings or a partial download, surface that explicitly instead of claiming a full download.

## Important limits
- Do not claim success for files that are not present on disk.
- Do not let a PMCID from an earlier run leak into the current reply.
- `study_id_suggestion` is metadata, not the storage folder key.
