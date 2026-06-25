# Guidelines

## Build, Test, and Development Commands
* Assume you will be using a uv environment with a pyproject.toml unless otherwise stated so project files will be run like "uv run python FILE.py"

## Coding Style & Naming Conventions
* Follow PEP 8 with 4-space indentation and keep modules ASCII-only.
* Prefer type hints.
* Add explicit Google-style docstrings (Args/Returns) for functions that include function purpose.
* Add concise comments only when logic is non-obvious.
* Comment code sections for educational purposes especially function purpose.
* Configuration constants should live near the top of files
* Favor descriptive snake_case for variables and lowercase filenames (e.g., power_law_result_dict.json).
* Use DiskCache if cache is used or requested unless explicitly overriden
* If argparse is used, place argparse parsing in main() unless explicitly overriden
* If pyproject.toml present, then use black and flake8 if present for formatting and linting, otherwise use ruff
* Prefer f-strings
* Prefer using triple-quoted multiline strings ("""...""") for long string literals; no implicit string concatenation unless explicitly requested.
* If neither PEP723 nor a pyproject.toml exist suggest that one of these dependency tracking methods be used if >=2 Python files exist in the workspace
* Prefer Python >=3.14 and avoid 'from __future__ import annotations'
* Attempt to include short argparse and long ones like -s --string
* Use python-dotenv to load .env environment variables if needed; if using AzureOpenAI, use load_dotenv('.env', override=True) to avoid variable conflicts

### PEP 723
If the user requests uv-based PEP 723 "inline script metadata" dependencies, then follow this example:

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.2.1",
# ]
# ///

PYTHON_CODE_HERE

Run using; IMPORTANT: you must chmod +x the script!

chmod +x script.py
./script.py

## Analysis Tasks
* Use csvkit if you need to explore a Excel or CSV file; example `uvx --from csvkit csvcut