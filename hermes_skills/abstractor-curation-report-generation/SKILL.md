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
- Discover study workspace paths through `cbio-curation workspace describe --study-id <study_id>` before inspecting files.
- Run report generation with only `--study-id`; let project code resolve canonical inputs and outputs.
- Use the agent report JSON printed by the script as the source of truth for user-facing status.
- Do not summarize sources, supplementary files, LLM use, warnings, or output paths from ad hoc inspection when the agent report is available.

## Procedure
1. Describe the initialized workspace through the package CLI:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation workspace describe \
  --study-id <study_id>
```
2. Parse the workspace JSON and use only returned absolute paths when checking local artifacts.
3. If workspace discovery fails, stop and report the diagnostic instead of guessing where files should be.
4. Run the report generator through the package CLI:
```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation curation-report \
  --study-id <study_id>
```
5. Parse the JSON printed by `curation-report`; it is the deterministic agent report.
6. Verify any output files you mention using the paths in `outputs`.
7. Report the run to the user using the agent report fields.

## What the script owns
The script deterministically handles:
- workspace loading and validation using `--study-id`
- article-source selection
- supplementary-file discovery
- LLM config detection from the process environment when provider settings are available
- fallback to non-LLM metadata handling when no usable LLM config is available or completion fails
- metadata extraction from the paper source
- supplementary-file analysis
- curation summary construction
- PDF and curation JSON output resolution and persistence
- deterministic agent report JSON generation and persistence
- printing the deterministic agent report JSON to stdout

Do not restate those implementation details in agent reasoning unless they are directly relevant to a failure or debugging step.

## Reporting requirements
Base the user-facing summary on the deterministic agent report printed by the script:
- `paper_source.type` and `paper_source.path` for the paper source used.
- `supplementary_files.count` and `supplementary_files.paths` for supplementary files actually analysed.
- `llm_metadata_extraction.enabled`, plus provider/model when present, for LLM metadata extraction.
- `outputs.pdf`, `outputs.curation_report_json`, and `outputs.agent_report_json` for generated artifacts.
- `warnings` for any caveats; if empty, say no warnings were reported.
- `status` and `success` for whether the run succeeded.

## Important limits
- This workflow does not fetch files by itself; it expects the canonical study workspace to exist already.
- Do not point the script at ad hoc paper or supplementary paths; use the canonical study workspace and `--study-id`.
- Do not claim success for a PDF or JSON file that is not present on disk.
- Do not include supplementary files that were not requested or approved by the user.
