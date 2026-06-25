---
name: abstractor-study-download
description: Use this skill when asked to download or reuse a study article XML/PDF and supplementary files from PMC using a PMID or PMCID, storing them under the local cbio-ai-curation-assistant studies directory without redownloading files that already exist.
---

# cBioPortal study download

## When to use
Use this skill when the user asks to download study artifacts for a paper identified by PMID or PMCID.

## Core rule
Never redownload study assets that already exist locally unless the user explicitly asks to refresh or overwrite them.

## Path anchor
Treat the `/home/cbio26/cbio-ai-curation-assistant` as the canonical repository root.

## Directory layout
Create or reuse this structure under `/home/cbio26/cbio-ai-curation-assistant/studies/`:

studies/
└── <PMCID_of_the_study>/
    └── data/
        └── raw/
            ├── article/
            └── supplementary/

Use the normalized PMCID as the study folder name. Do not use `study_id_suggestion` as the folder key.

## Identifier handling
The user may provide either a PMID or a PMCID.

If the identifier is a bare numeric string with no `PMC` prefix, treat it as a PMID candidate and resolve it before choosing any storage path. Do not assume the number is an internal study folder name.

Always resolve the identifier with:
`pmc_supplement_fetcher.resolve_study_identifier_to_pmcid(identifier)`

Use the returned:
- `identifier_type` for reporting
- `pmcid` as the canonical PMC identifier
- normalized `pmcid` as the folder key and storage path
- resolved PMID/PMCID mapping in the final status message when the input was ambiguous or numeric-only

## Workflow
1. Resolve the input identifier to a normalized PMCID.
   - Immediately state the resolved mapping in working notes or status output, especially for bare numeric inputs, for example: `input 31130341 -> PMID 31130341 -> PMCID PMC8432745`.
   - Treat that resolved PMCID as the task lock for the rest of the run.
2. Set:
   - `study_root = /home/cbio26/cbio-ai-curation-assistant/studies/<PMCID>/data/raw/`
   - `article_dir = /home/cbio26/cbio-ai-curation-assistant/studies/<PMCID>/data/raw/article/`
   - `supp_dir = /home/cbio26/cbio-ai-curation-assistant/studies/<PMCID>/data/raw/supplementary/`
   - `manifest_path = /home/cbio26/cbio-ai-curation-assistant/studies/<PMCID>/data/raw/manifest.json`
3. Before reusing any prior files, todos, or partially completed work, verify they belong to the same resolved PMCID.
   - If a resumed thread, compaction summary, or existing notes mention a different PMCID, stop and realign to the latest user-requested identifier before proceeding.
   - Never let a prior study's PMCID leak into the current run just because it was the last active task.
4. If `manifest.json` already exists, inspect it and check whether the referenced files still exist on disk.
5. If the XML file already exists locally, reuse it and report that it was already present.
6. If the XML file is missing, fetch it with `pmc_supplement_fetcher._fetch_pmc_xml()` and save it as `article/<PMCID>.xml`.
7. Extract metadata from the local XML file using the existing `cbio_abstractor` LLM-assisted flow, then save `article/<PMCID>_metadata.json`.
   - Start from structured XML metadata with `xml_metadata.extract_metadata_from_xml()`.
   - Build the LLM input with `xml_metadata.extract_xml_llm_text()`.
   - If an LLM configuration is available, use the existing `cbio_abstractor` metadata-completion flow to fill missing fields from the XML-derived text and merge the result into the structured XML metadata.
   - If no LLM configuration is available or the LLM completion fails, keep the structured XML metadata and report that the LLM completion step was skipped or failed.
8. If supplementary files already exist locally in `supplementary/`, reuse them and report that they were already present.
9. Only if supplementary files are missing, call `pmc_supplement_fetcher.download_pmc_supplements()` and save the returned files under `supplementary/`.
   - If PMC returns a transient HTML challenge page, 403, or proof-of-work interstitial for a supplement URL, retry the same downloader at least once before declaring failure. PMC may succeed on a subsequent attempt without any code change.
   - Before concluding the download failed, inspect the `supplementary/` directory again because some files may already have been written even if one URL failed during the run.
10. If no article PDF can be resolved from PMC, report that XML and supplementary files were saved but the article PDF was not available
11. Write or update a manifest JSON with:
    - input identifier
    - identifier type
    - PMID when known
    - PMCID
    - `study_id_suggestion` when available
    - XML path
    - metadata JSON path
    - article PDF path when available, otherwise `null`
    - supplementary file paths actually present on disk; if PMC blocks every supplementary download, keep this list empty rather than recording attempted URLs as saved files
12. Before reporting success, read back the manifest or list the output directory.
13. Final target-ID verification gate before replying:
    - confirm the manifest PMCID matches the resolved PMCID from step 1
    - confirm every reported path is under `studies/<resolved PMCID>/...`
    - if the reply mentions another PMCID, another paper, or artifacts from a different study, do not send the reply until corrected

## Use existing repo code
Use the existing code in `/home/cbio26/cbio-ai-curation-assistant/cbio_abstractor` rather than reimplementing PMC/PubMed logic.

Use:
- `pmc_supplement_fetcher._fetch_pmc_xml()` for PMC XML retrieval
- `pmc_supplement_fetcher.download_pmc_supplements()` for supplementary file download
- `xml_metadata.extract_metadata_from_xml()` for the structured XML metadata base
- `xml_metadata.extract_xml_llm_text()` plus the existing `cbio_abstractor` LLM metadata-completion flow for filling missing metadata fields from XML content

### Import-path pitfall when scripting from the repo root
If you run ad-hoc Python from `/home/cbio26/cbio-ai-curation-assistant` and import `cbio_abstractor.curation_workflow`, set `PYTHONPATH=./cbio_abstractor` first (or run from inside the `cbio_abstractor/` directory).

Reason: `curation_workflow.py` imports sibling modules like `cbioportal_curator`, `config`, and `llm_client` as top-level modules rather than package-qualified imports. In the project venv this can still raise `ModuleNotFoundError` unless the `cbio_abstractor/` directory itself is on `PYTHONPATH`.

## Reuse behavior
When files already exist:
- say explicitly that they are already present
- do not redownload them
- do not call `download_pmc_supplements()` if the supplementary directory already contains the expected files, unless the user explicitly asks to refresh

## Verification
- Confirm the article directory contains the XML file.
- Confirm the supplementary directory contains at least one supported file when supplementary material exists and PMC served the files successfully.
- Confirm the manifest matches the files currently on disk.
- On successful downloads, report the resolved PMID and PMCID, the canonical `studies/<PMCID>/data/raw` path, and the exact article/supplementary artifacts present so the user can reuse the folder immediately.
- If an article PDF was requested, confirm whether it exists locally or report that it was unavailable.
- If PMC returns an HTML challenge page, CAPTCHA, or a dead OA package/PDF URL instead of the expected file, retry the downloader once before treating the run as partial. If the retry still fails, save XML, metadata, and manifest, leave blocked assets absent from the manifest, and report the blocker explicitly instead of claiming a full download.

## Important limits
- `download_pmc_supplements()` downloads supplementary files only; it is not a cache layer and it does not skip existing files automatically.
- `study_id_suggestion` is useful metadata but should not be used as the storage folder key.
- Article PDF availability from PMC is not guaranteed for every paper.
- PMC may expose supplementary links in XML that still fail at download time because the endpoint serves an HTML challenge page or the OA package/PDF URL is unavailable. Retry the same downloader once before concluding the asset is blocked; if the retry still fails, verify on-disk results and report a partial download rather than assuming the links were valid.
- See `references/pmc-blocked-downloads.md` for a concise checklist and reporting pattern for blocked PMC asset downloads.
