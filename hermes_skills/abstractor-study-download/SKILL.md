---
name: abstractor-study-download
description: Use this skill when asked to download or reuse a study article XML/PDF and supplementary files from PMC using a PMID or PMCID, storing them under the local cbio-ai-curation-assistant studies directory without redownloading files that already exist.
---

# cBioPortal study download

## When to use

Use this skill when the user asks to download study artifacts for a paper identified by PMID or PMCID.

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

## Core rules

* Never redownload study assets that already exist locally unless the user explicitly asks to refresh or overwrite them.
* Treat the resolved PMCID as the canonical study identifier for the whole run.
* The storage root is `$CBIO_ASSISTANT_REPO_ROOT/studies/<PMCID>/raw/`.

## Workflow

1. Check whether `$CBIO_ASSISTANT_REPO_ROOT/studies/<PMCID>/raw/manifest.json` already exists and still points to files that are present on disk.
2. If the manifest and files are already present, reuse them and report that the study artifacts already existed locally.
3. Otherwise run the repo's download script from the repo root using the project virtual environment:

```bash
cd "$CBIO_ASSISTANT_REPO_ROOT"

"$CBIO_ASSISTANT_REPO_ROOT/.venv/bin/python" \
  hermes_skills/abstractor-study-download/scripts/abstractor_study_download.py \
  <identifier>
```

4. If you want the structured result payload preserved, also pass:

```bash
--output-json /tmp/<identifier>_download_result.json
```

5. After the run, verify the manifest and the files on disk under `$CBIO_ASSISTANT_REPO_ROOT/studies/<PMCID>/raw/`.

## What the abstractor_study_download.py script owns

The script deterministically handles:

* PMID/PMCID normalization
* study directory layout
* XML download
* supplementary download
* article PDF attempt when available
* manifest generation
* partial-download reporting through its result payload

Do not restate those implementation details in agent reasoning unless they are directly relevant to a failure or debugging step.

## Reporting requirements

* Report the resolved PMID/PMCID mapping when useful, especially for numeric-only input.
* Report the canonical study path: `$CBIO_ASSISTANT_REPO_ROOT/studies/<PMCID>/`.
* Report the canonical raw-artifacts path: `$CBIO_ASSISTANT_REPO_ROOT/studies/<PMCID>/raw/`.
* Report the actual artifacts present on disk:

  * XML path
  * article PDF path if present, otherwise say it was unavailable
  * supplementary files actually present
* If the script reports warnings or a partial download, surface that explicitly instead of claiming a full download.

## Important limits

* Do not claim success for files that are not present on disk.
* Do not let a PMCID from an earlier run leak into the current reply.
* `study_id_suggestion` is metadata, not the storage folder key.
* If `CBIO_ASSISTANT_REPO_ROOT` changes, restart or reload Hermes before relying on the new value.
