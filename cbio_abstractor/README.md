# cBioAbstractor

cBioAbstractor is a Streamlit-based curation assistant for cancer genomics studies. It helps curators review a published paper and its supplementary files, classify the data against cBioPortal file formats, and generate a structured curation report for downstream cBioPortal ingestion.

---

## Features

- Upload a cancer genomics paper PDF
- Upload supplementary data files such as `.xlsx`, `.csv`, `.tsv`, `.txt`, `.maf`, `.docx`, and `.pdf`
- Download supplementary files automatically from PubMed Central using a PMCID or PMID
- Extract study-level metadata from the paper
- Classify supplementary sheets against cBioPortal file-format schemas
- Identify likely cBioPortal target files
- Highlight required columns, missing fields, and curation gaps
- Generate a downloadable PDF curation report from the Streamlit UI
- Support few-shot examples for curator-guided learning

---

## Streamlit App

This repository is designed to run as a simple local Streamlit app.

No Docker setup is required.

No FastAPI backend is required.

---

## Recommended Project Structure

```text
cBioAbstractor/
├── streamlit_app.py
├── cbioportal_curator.py
├── cbio_detector.py
├── cbio_transformer.py
├── cbioportal_spec.py
├── spec_match.py
├── spec_fetcher.py
├── file_parser.py
├── few_shot_manager.py
├── config.py
├── utils.py
├── requirements.txt
└── few_shot_examples/
```

---

## Installation

Clone the repository:

```bash
git clone git@github.com:sbabyanusha/cBioAbstractor.git
cd cBioAbstractor
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## API Key Setup

Set an Anthropic, OpenAI, or LiteLLM credential locally as an environment variable:

```bash
export ANTHROPIC_API_KEY="your-api-key"
# or
export OPENAI_API_KEY="your-api-key"
# or, for LiteLLM Proxy / compatible gateways
export LITELLM_API_KEY="your-proxy-key"
export LITELLM_BASE_URL="http://localhost:4000"
export LITELLM_MODEL="openai/gpt-4o"

# for Hermes / codex-style gateways exposing the Responses API
export LITELLM_API_MODE="responses"
```

The Streamlit app loads `/home/cbio26/cBioAbstractor/.env` automatically if present.
The Streamlit sidebar lets you choose between Anthropic, OpenAI, and LiteLLM.
When using LiteLLM, you can either:

- point `LITELLM_BASE_URL` at a LiteLLM Proxy and use the proxy model alias or provider/model string
- leave `LITELLM_BASE_URL` empty and use a direct LiteLLM model string such as `openai/gpt-4o`, provided the upstream provider credentials are already available in the environment
- set `LITELLM_API_MODE=responses` when your LiteLLM-compatible gateway exposes the OpenAI Responses API instead of `/chat/completions` (the default Hermes/codex backend needs this)

Do not commit API keys to GitHub.

Recommended `.gitignore` entries:

```text
.env
api_config.py
__pycache__/
*.pyc
.venv/
vector_store/
```

---

## Run the App

```bash
streamlit run streamlit_app.py
```

The app will open at:

```text
http://localhost:8501
```

---

## How to Use

1. Open the Streamlit app
2. Upload the main paper PDF
3. Upload one or more supplementary files, or enter a PMCID/PMID to fetch them from PubMed Central
4. Run the curation workflow
5. Review detected file types, required fields, and missing fields
6. Download the generated PDF cBioPortal curation report

---

## Core Modules

| File | Purpose |
|---|---|
| `streamlit_app.py` | Main Streamlit user interface |
| `cbioportal_curator.py` | Core report-generation engine |
| `cbio_detector.py` | Detects likely cBioPortal file type |
| `cbio_transformer.py` | Helps transform raw files toward cBioPortal format |
| `cbioportal_spec.py` | Embedded cBioPortal file-format schemas |
| `spec_match.py` | Matches uploaded files against cBioPortal schemas |
| `spec_fetcher.py` | Fetches live cBioPortal file-format documentation |
| `file_parser.py` | Parses uploaded CSV, TSV, Excel, and text files |
| `few_shot_manager.py` | Saves curator-approved examples |
| `config.py` | Central configuration |
| `utils.py` | Shared helper functions |

---

## Few-Shot Examples

Curators can save reviewed examples to improve future file detection and transformation.

Examples are stored in:

```text
few_shot_examples/
```

Each example may include:

```text
001.input.tsv
001.output.tsv
001.type.txt
001.meta.json
```

These examples help the app recognize recurring supplemental file patterns.

---

## What This Tool Does

- Publication review
- Supplementary file classification
- cBioPortal format assessment
- Curation report generation
