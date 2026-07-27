---
name: abstractor-study-download
description: Use this skill when asked to download or reuse local study source artifacts from PMC using a PMID or PMCID, without redownloading files that already exist.
required_environment_variables:
  - name: CBIO_CURATION_ASSISTANT_HOME
    prompt: Absolute path to the cBioPortal AI Curation Assistant installation directory
---

# cBioPortal study download

## When to use
Use this skill when the user asks to download study artifacts for a paper identified by PMID or PMCID.

## Core rules
- Treat the returned `study_id` as the only stable handoff to downstream steps.
- Use the download report JSON printed by the script as the source of truth for status, resolved identifiers, artifacts, warnings, and reuse details.
- After a successful or partial download, use `cbio-curation workspace describe --study-id <study_id>` when you need canonical workspace paths.
- Do not infer workspace paths from repository layout or construct them manually in agent reasoning.

## Procedure
1. Run the package CLI through the project selected by `CBIO_CURATION_ASSISTANT_HOME`:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation study-download \
  --identifier "<identifier_value>" \
  --identifier-type "<pmid|pmcid>"
```
2. Parse the JSON printed by `study-download`; it is the deterministic download report.
3. If the report has `status: error` or `success: false`, surface the error message and stop unless the user asks for debugging.
4. If the report has `status: partial_success`, surface the warnings explicitly instead of claiming a full download.
5. If you need canonical workspace paths for follow-up inspection, run discovery using the returned `study_id`:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation workspace describe \
  --study-id <study_id>
```
6. Use the discovery JSON only for paths; use the download report for what was downloaded, reused, missing, or warned.

## What the script owns
The script deterministically handles:
- PMID/PMCID normalization and PMID-to-PMCID resolution
- canonical storage-root resolution from `CBIO_CURATION_ASSISTANT_HOME`
- workspace initialization through the shared workspace module
- reuse of existing source artifacts when present locally
- XML download
- supplementary download
- article PDF attempt when available
- deterministic download report JSON generation and persistence
- printing the deterministic download report JSON to stdout
- structured error payloads for deterministic agent recovery

Do not restate those implementation details in agent reasoning unless they are directly relevant to a failure or debugging step.

## Reporting requirements
Base the user-facing summary on the deterministic download report printed by the script:
- `resolved_identifier` for the input identifier, normalized identifier, PMID, and PMCID.
- `study_id` for the stable downstream handoff.
- `status` and `success` for whether the run succeeded, reused existing files, or partially succeeded.
- `artifact_details.xml`, `artifact_details.article_pdf`, and `artifact_details.supplementary` for artifact presence, absolute paths, counts, and reuse flags.
- `reused` for whether XML, supplementary files, and article PDF were reused.
- `warnings` for any caveats; if empty, say no warnings were reported.
- Workspace paths only from `workspace describe`, when path reporting is necessary.

## Important limits
- Do not claim success for files that are not present on disk.
- Do not let a study workspace key from an earlier run leak into the current reply.
- `study_id_suggestion` is metadata, not the storage folder key.
