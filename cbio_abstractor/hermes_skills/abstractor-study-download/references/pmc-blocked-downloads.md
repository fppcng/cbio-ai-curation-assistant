# PMC blocked or partial downloads

Use this note when PMC XML advertises supplementary files or article PDFs but the actual download endpoints do not return the expected asset.

## Failure modes seen in practice
- Supplementary file URLs return HTML instead of the binary file, including reCAPTCHA/challenge pages.
- `oa.fcgi` reports OA package locations that still return `404`.
- Article PDF URLs derived from PMC identifiers are absent even when XML is available.

## Handling rule
Treat these as **partial-download** cases, not full failures, when the XML and metadata can still be saved.

Save and verify:
- article XML
- extracted metadata JSON
- manifest JSON describing what was and was not downloaded

Do not claim the study download is complete unless the expected files are present on disk.

## Reporting pattern
State explicitly:
1. which identifier resolved to which PMCID,
2. which files were saved,
3. which files were blocked or unavailable,
4. that the manifest reflects the partial result.
