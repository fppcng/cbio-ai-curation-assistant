---
name: abstractor-curation-report-generation
description: Generate a cBioPortal curation report PDF from a local paper PDF or XML file and a user-approved subset of local supplementary files using the local cbio_abstractor workspace.
---

## When to use
Use this skill when the user asks to generate a cBioPortal curation report for a study and local study artifacts may be available.

## Preconditions
- The local `cbio_abstractor` code is available under `/home/cbio26/cbio-ai-curation-assistant/cbio_abstractor`.
- A local paper PDF or XML file can be found.
- The study directory already exists under `/home/cbio26/cbio-ai-curation-assistant/studies/<PMCID>/`.
- Python dependencies are installed.

## Path anchor
Treat `/home/cbio26/cbio-ai-curation-assistant` as the repository root.

When running Python code, prefer `/home/cbio26/cbio-ai-curation-assistant/cbio_abstractor` as the working directory so the local imports resolve correctly.

## Core rule
Never run report generation on all discovered supplementary files by default when multiple candidate files are present.

## Workflow
1. Locate the local paper PDF or XML file and candidate supplementary files.
   - If a local manifest already exists for the study, use it as the source of truth for article XML/PDF paths and supplementary-file paths instead of reconstructing them manually.
2. Show the user the candidate supplementary files as a numbered list.
3. For each file, provide:
   - file number
   - filename
   - path if useful
4. Ask the user which files to use for curation.
5. Accept either:
   - a list of file numbers
   - `use recommended`
6. Create or reuse:
   - `/home/cbio26/cbio-ai-curation-assistant/studies/<PMCID>/curation-report/`
7. Do not continue until the user confirms the subset, unless there is only one clearly relevant supplementary file and the user has already implicitly requested execution.
8. If the user already approved a specific supplementary-file subset earlier in the same active thread, you may reuse that approval on repeated "generate/regenerate the report" requests instead of asking again. Restate the reused selection when you report the run.
9. Always aim to send the complete pdf file, with all the metadata, when possible.
10. Run `curation_workflow.run_local_curation_workflow(...)` using only the user-approved supplementary file paths.
11. Pass:
   - `supplementary_paths`
   - `generate_pdf=True`
   - `output_pdf_path` set to a deterministic location under `/home/cbio26/cbio-ai-curation-assistant/studies/<PMCID>/curation-report/`
   - prefer a stable filename that encodes the study identifier and the chosen source/subset when useful (for example `<PMCID>_curation_report_xml_sup3.pdf`)
   - LLM config only if available
12. Pass exactly one paper source:
   - `paper_pdf_path` when the source file is a PDF
   - `paper_xml_path` when the source file is an XML file
   - If the user explicitly asks to use the XML file for metadata, prefer `paper_xml_path` and do not also pass the PDF path.
13. If you are regenerating a report into an existing deterministic path, treat the new file as a fresh artifact:
   - rerun the workflow
   - recompute the current file hash/size after the run
   - report the current values instead of reusing older verification
   - expect byte-level hashes to differ across reruns even when inputs are unchanged
14. Collect:
   - `pdf_path`
   - `summary`
   - `warnings`
15. Always send or attach the generated PDF file to the user, not only the path.

## User interaction format
When multiple supplementary files are found, always show them to the user before running the workflow.

Use a numbered list like:

1. `Supplementary_Table_1.xlsx`
2. `Figure_S1.pdf`
3. `Supplementary_Methods.docx`

Then ask:
`Reply with the file numbers to include.`

## Important limits
- This workflow does not fetch files from PMID or PMCID by itself.
- If only a PMID or PMCID is provided and no local study artifacts exist, report that the required input files are missing.
- Do not use Streamlit for report generation.
- Do not include supplementary files that were not approved by the user.
- Do not pass both `paper_pdf_path` and `paper_xml_path` in the same workflow call.
- Always send the pdf if the task was successful.
