---
name: abstractor-curation-report-generation
description: Use this skill when asked to generate or regenerate a cBioPortal curation report PDF from local paper XML/PDF inputs and a chosen set of local supplementary files, using the repository deterministic report-generation script.
---

# cBioPortal curation report generation

## When to use
Use this skill when the user asks to generate or regenerate a cBioPortal curation report from local study artifacts that already exist on disk.

## Prerequisites - Environment verification

Before running the workflow, verify that the Hermes environment has loaded the required repository root.

Run:

test -n "$CBIO_ASSISTANT_REPO_ROOT"
test -d "$CBIO_ASSISTANT_REPO_ROOT"
test -x "$CBIO_ASSISTANT_REPO_ROOT/.venv/bin/python"

printf 'CBIO_ASSISTANT_REPO_ROOT=%s\n' "$CBIO_ASSISTANT_REPO_ROOT"

If any check fails, stop and report that the Hermes environment was not loaded correctly or that CBIO_ASSISTANT_REPO_ROOT does not point to a valid repository.

## Core rules
- Never invent paper or supplementary paths. Use only files that exist locally.
- Pass exactly one paper source to the script: `--paper-pdf` or `--paper-xml`.
- Save report artifacts under `$CBIO_ASSISTANT_REPO_ROOT/studies/<PMCID>/reports/` whenever the inputs belong to a single study, using recognizable default names like `<study_id>_abstractor_report.pdf` and `<study_id>_abstractor_report.json`.
- Use LLM-backed metadata extraction when configuration is available; otherwise allow the script to fall back deterministically without LLM.
- It is acceptable to return or attach the generated PDF to the user when the run succeeds.

## Workflow
1. Locate the local paper source and the supplementary files that should be included.
2. If the user provided only a PMID or PMCID and no local study artifacts exist yet, report that the required local inputs are missing.
3. Treat `$CBIO_ASSISTANT_REPO_ROOT/studies/<PMCID>/reports/` as the canonical report directory for the study.
4. Run the repository report-generation script from the repo root using the project virtual environment:
cd "$CBIO_ASSISTANT_REPO_ROOT"
`"$CBIO_ASSISTANT_REPO_ROOT/.venv/bin/python" \`
  `hermes_skills/abstractor-curation-report-generation/scripts/abstractor_report_generator.py \`
  `--paper-xml <paper_xml_path> \`
  `--supp <supp_path_1> <supp_path_2>`
6. When a supplementary input is a directory and recursive discovery is required, also pass `--recursive-supp`.
7. When the paper source is a PDF, use `--paper-pdf` instead of `--paper-xml`.
8. If the script cannot infer a unique study root from the paper and supplementary paths, pass `--output-dir /home/cbio26/cbio-ai-curation-assistant/studies/<PMCID>/reports` explicitly.
9. If you need a fixed PDF filename, pass `--output-pdf` with an absolute path inside the study reports/ directory:
`--output-pdf "$CBIO_ASSISTANT_REPO_ROOT/studies/<PMCID>/reports/<study_id>_abstractor_report.pdf"`
10. If you need a fixed JSON filename, pass `--output-json` with an absolute path inside the study reports/ directory:
`--output-json "$CBIO_ASSISTANT_REPO_ROOT/studies/<PMCID>/reports/<study_id>_abstractor_report.json"`
11. After the run, verify the generated PDF and JSON paths on disk.

## What the abstractor_report_generator.py script owns
The script deterministically handles:

- validation that exactly one paper source was provided
- supplementary path expansion and filtering of supported file types
- local paper path resolution
- LLM config detection from the process environment when provider settings are available
- fallback to non-LLM metadata handling when no usable LLM config is available or completion fails
- metadata extraction from the paper source
- supplementary-file analysis
- curation summary construction
- default PDF and JSON path resolution under `studies/<PMCID>/reports/` with recognizable names like `<study_id>_abstractor_report.pdf` and `<study_id>_abstractor_report.json` when a unique study root can be inferred
- PDF generation when PDF output is enabled
- JSON report rendering and persistence when an output location is available

Do not restate those implementation details in agent reasoning unless they are directly relevant to a failure or debugging step.

## Reporting requirements
- Report which paper source was used and whether it was XML or PDF.
- Report the supplementary files actually passed to the script.
- Report whether LLM metadata extraction was enabled or skipped.
- Report the generated PDF path and JSON path.
- Surface warnings returned by the script instead of claiming a clean run.
- If the task was successful and a PDF was generated, it is fine to return or attach the PDF to the user.

## Important limits
- This workflow does not fetch files from PMID or PMCID by itself.
- Do not pass both `--paper-pdf` and `--paper-xml` in the same run.
- Do not claim success for a PDF or JSON file that is not present on disk.
- Do not include supplementary files that were not requested or approved by the user.
