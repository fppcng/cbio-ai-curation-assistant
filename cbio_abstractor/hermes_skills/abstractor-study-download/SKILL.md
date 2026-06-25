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

Always resolve the identifier with:
`pmc_supplement_fetcher.resolve_study_identifier_to_pmcid(identifier)`

Use the returned:
- `identifier_type` for reporting
- `pmcid` as the canonical PMC identifier
- normalized `pmcid` as the folder key and storage path

## Workflow
1. Resolve the input identifier to a normalized PMCID.
2. Set:
   - `study_root = /home/cbio26/cbio-ai-curation-assistant/studies/<PMCID>/data/raw/`
   - `article_dir = /home/cbio26/cbio-ai-curation-assistant/studies/<PMCID>/data/raw/article/`
   - `supp_dir = /home/cbio26/cbio-ai-curation-assistant/studies/<PMCID>/data/raw/supplementary/`
   - `manifest_path = /home/cbio26/cbio-ai-curation-assistant/studies/<PMCID>/data/raw/manifest.json`
3. If `manifest.json` already exists, inspect it and check whether the referenced files still exist on disk.
4. If the XML file already exists locally, reuse it and report that it was already present.
5. If the XML file is missing, fetch it with `pmc_supplement_fetcher._fetch_pmc_xml()` and save it as `article/<PMCID>.xml`.
6. Extract structured metadata with `xml_metadata.extract_metadata_from_xml()` from the local XML file and save `article/<PMCID>_metadata.json`.
7. If supplementary files already exist locally in `supplementary/`, reuse them and report that they were already present.
8. Only if supplementary files are missing, call `pmc_supplement_fetcher.download_pmc_supplements()` and save the returned files under `supplementary/`.
9. If the user asked for the article PDF:
   - first check whether `article/<PMCID>.pdf` already exists and reuse it if present
   - otherwise attempt article PDF download only as a best-effort step
   - if no article PDF can be resolved from PMC, report that XML and supplementary files were saved but the article PDF was not available
10. Write or update a manifest JSON with:
    - input identifier
    - identifier type
    - PMID when known
    - PMCID
    - `study_id_suggestion` when available
    - XML path
    - metadata JSON path
    - article PDF path when available, otherwise `null`
    - supplementary file paths actually present on disk; if PMC blocks every supplementary download, keep this list empty rather than recording attempted URLs as saved files
11. Before reporting success, read back the manifest or list the output directory.
## Use existing repo code
Use the existing code in `/home/cbio26/cbio-ai-curation-assistant/cbio_abstractor` rather than reimplementing PMC/PubMed logic.

Use:
- `pmc_supplement_fetcher._fetch_pmc_xml()` for PMC XML retrieval
- `pmc_supplement_fetcher.download_pmc_supplements()` for supplementary file download
- `xml_metadata.extract_metadata_from_xml()` for structured metadata extraction

## Reuse behavior
When files already exist:
- say explicitly that they are already present
- do not redownload them
- do not call `download_pmc_supplements()` if the supplementary directory already contains the expected files, unless the user explicitly asks to refresh

## Verification
- Confirm the article directory contains the XML file.
- Confirm the supplementary directory contains at least one supported file when supplementary material exists and PMC served the files successfully.
- Confirm the manifest matches the files currently on disk.
- If an article PDF was requested, confirm whether it exists locally or report that it was unavailable.
- If PMC returns an HTML challenge page, CAPTCHA, or a dead OA package/PDF URL instead of the expected file, treat the run as a partial download: save XML, metadata, and manifest, leave blocked assets absent from the manifest, and report the blocker explicitly instead of claiming a full download.

## Important limits
- `download_pmc_supplements()` downloads supplementary files only; it is not a cache layer and it does not skip existing files automatically.
- `study_id_suggestion` is useful metadata but should not be used as the storage folder key.
- Article PDF availability from PMC is not guaranteed for every paper.
- PMC may expose supplementary links in XML that still fail at download time because the endpoint serves an HTML challenge page or the OA package/PDF URL is unavailable. In that case, verify on-disk results and report a partial download rather than assuming the links were valid.
- See `references/pmc-blocked-downloads.md` for a concise checklist and reporting pattern for blocked PMC asset downloads.