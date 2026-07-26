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
- Treat the resolved study workspace key as canonical for the whole run. For PMC downloads this is the resolved PMCID when resolution succeeds.
- The storage root is `$CBIO_CURATION_ASSISTANT_HOME/studies/<study_id>/source/`.
- Treat the returned `study_id` as the only stable handoff to downstream steps. Use the script JSON payload as the source of truth for paths, status, warnings, and reuse details.

## Procedure
1. Run the repository download script from the repo root using the project virtual environment:
```bash
cd "$CBIO_CURATION_ASSISTANT_HOME"
"$CBIO_CURATION_ASSISTANT_HOME/.venv/bin/python" \
  "hermes_skills/abstractor-study-download/scripts/abstractor_study_download.py" \
  --identifier "<identifier_value>" \
  --identifier-type "<pmid|pmcid>" \
  --assistant-home "$CBIO_CURATION_ASSISTANT_HOME"
```
2. Parse the JSON payload printed by the script and treat it as authoritative.
3. If the script returns `status: error`, surface the error message and only fall back to manual debugging if the error itself requires it.
4. If the script returns `status: partial_success`, surface the warnings explicitly instead of claiming a full download.

## What the script owns
The script deterministically handles:
- PMID/PMCID normalization
- assistant-home resolution and canonical storage-root selection
- study directory layout
- reuse of existing XML/PDF/supplementary artifacts when present locally
- XML download
- supplementary download
- article PDF attempt when available
- workspace creation and `study_manifest.json` generation
- download manifest generation under `source/download_manifest.json`
- structured result payload with `status`, resolved identifiers, workspace paths, artifact presence, warnings, and reuse flags
- structured error payloads for deterministic agent recovery

Do not restate those implementation details in agent reasoning unless they are directly relevant to a failure or debugging step.

## Reporting requirements
- Report the resolved PMID/PMCID mapping when useful, especially for numeric-only input.
- Report the canonical study path and source-artifacts path from the script payload.
- Report the actual artifacts present according to the script payload:
  - XML path
  - article PDF path if present, otherwise say it was unavailable
  - supplementary files actually present
- If the script reports warnings or a partial download, surface that explicitly instead of claiming a full download.

## Important limits
- Do not claim success for files that are not present on disk.
- Do not let a study workspace key from an earlier run leak into the current reply.
- `study_id_suggestion` is metadata, not the storage folder key.
