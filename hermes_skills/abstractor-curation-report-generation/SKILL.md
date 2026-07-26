---
name: abstractor-curation-report-generation
description: Use this skill when asked to generate or regenerate a cBioPortal curation report PDF from local paper XML/PDF inputs and a chosen set of local supplementary files, using the repository deterministic report-generation script.
required_environment_variables:
  - name: CBIO_CURATION_ASSISTANT_HOME
    prompt: Absolute path to the cBioPortal AI Curation Assistant installation directory
---

# Abstractor curation report generation

## When to use
Use this skill when the user asks or you need to generate or regenerate a cBioPortal curation report from local study artifacts that already exist on disk.

## Core rules
- Never invent paper or supplementary paths. Use only files that exist locally.
- Pass the canonical study workspace key to the script with `--study-id`. The script loads the initialized workspace from `study_manifest.json` and resolves the canonical article source and supplementary files from there.
- Save report artifacts under `$CBIO_CURATION_ASSISTANT_HOME/studies/<study_id>/reports/` whenever the inputs belong to a single study, using recognizable default names like `<study_id>_abstractor_report.pdf` and `<study_id>_abstractor_report.json`.
- Use LLM-backed metadata extraction when configuration is available; otherwise allow the script to fall back deterministically without LLM.
- It is acceptable to return or attach the generated PDF to the user when the run succeeds.

## Procedure
1. Locate the local paper source and the supplementary files that should be included.
2. If the user provided only a publication identifier and no local study artifacts exist yet, report that the required local inputs are missing.
3. Treat `$CBIO_CURATION_ASSISTANT_HOME/studies/<study_id>/reports/` as the canonical report directory for the study.
4. Run the repository report-generation script from the repo root using the project virtual environment:
cd "$CBIO_CURATION_ASSISTANT_HOME"
`"$CBIO_CURATION_ASSISTANT_HOME/.venv/bin/python" \`
  `hermes_skills/abstractor-curation-report-generation/scripts/abstractor_report_generator.py \`
  `--study-id <study_id>`
5. The script resolves canonical inputs from `studies/<study_id>/source/` and writes report artifacts under `studies/<study_id>/reports/`.
6. If `source/article/article.xml` is present it is used as the primary paper source; otherwise the script falls back to `source/article/article.pdf`.
7. Use `--no-pdf` only when you explicitly want to skip PDF report generation.
8. After the run, verify the generated PDF and JSON paths on disk.

## What the script owns
The script deterministically handles:
- canonical workspace loading and validation from `study_manifest.json` using `--study-id`
- canonical article-source selection between `source/article/article.xml` and `source/article/article.pdf`
- supplementary-file discovery under `source/supplementary/`
- LLM config detection from the process environment when provider settings are available
- fallback to non-LLM metadata handling when no usable LLM config is available or completion fails
- metadata extraction from the paper source
- supplementary-file analysis
- curation summary construction
- canonical PDF and JSON path resolution under `studies/<study_id>/reports/` with recognizable names like `<study_id>_abstractor_report.pdf` and `<study_id>_abstractor_report.json`
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
- This workflow does not fetch files by itself; it expects the canonical study workspace to exist already.
- Do not point the script at ad hoc paper or supplementary paths; use the canonical study workspace and `--study-id`.
- Do not claim success for a PDF or JSON file that is not present on disk.
- Do not include supplementary files that were not requested or approved by the user.
