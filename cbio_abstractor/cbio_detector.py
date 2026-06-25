from typing import Optional, List, Dict, Tuple
"""
cbio_detector.py
================
Detects the cBioPortal file type of an uploaded supplemental file.

Strategy
--------
1. Heuristic pass  — fast rule-based column-name matching (no LLM call needed for obvious files)
2. Few-shot LLM pass — if heuristics are uncertain, send a compact representation of the
   file header + a few rows to an LLM together with loaded few-shot examples so the model
   can "learn" from curator-provided input→output pairs at inference time.

Few-shot learning
-----------------
Place pairs of files in ./few_shot_examples/:
    <name>.input.tsv   — the raw supplemental file
    <name>.output.tsv  — the correctly formatted cBioPortal file
    <name>.type.txt    — one line: the cBioPortal type (e.g. "clinical_patient")

The loader reads all available pairs and injects them as examples into the prompt.
This means curators can continuously improve detection accuracy just by dropping
new example pairs into the directory — no code change needed.
"""

import os
import re
import json
import glob
import logging
from pathlib import Path

import pandas as pd

from config import DETECTION_SAMPLE_ROWS, FEW_SHOT_DIR, LLMConfig, build_llm_config
from llm_client import call_llm_with_retry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Heuristic signatures — ordered from most specific to least
# ---------------------------------------------------------------------------

HEURISTIC_SIGNATURES = {
    "mutation": {
        "required_any": [
            {"hugo_symbol", "tumor_sample_barcode"},
            {"hugo_symbol", "hgvsp_short"},
            {"chromosome", "start_position", "reference_allele"},
            {"variant_classification", "tumor_sample_barcode"},
        ],
        "keywords": ["hugo_symbol", "tumor_sample_barcode", "hgvsp_short",
                     "chromosome", "start_position", "variant_classification",
                     "reference_allele", "tumor_seq_allele"],
    },
    "cna_discrete": {
        "required_any": [
            {"hugo_symbol"},  # + lots of sample columns with -2,-1,0,1,2
        ],
        "keywords": ["hugo_symbol", "entrez_gene_id"],
        # distinguished by value range check
        "value_range": (-2, 2),
    },
    "structural_variant": {
        "required_any": [
            {"sample_id", "sv_status"},
            {"site1_hugo_symbol", "site2_hugo_symbol"},
            {"site1_entrez_gene_id"},
        ],
        "keywords": ["sv_status", "site1_hugo_symbol", "site2_hugo_symbol",
                     "site1_position", "site2_position", "event_info"],
    },
    "clinical_patient": {
        "required_any": [
            {"patient_id", "os_status"},
            {"patient_id", "os_months"},
            {"patient_id", "age"},
            {"patient_id", "gender"},
            {"patient_id", "sex"},
        ],
        "keywords": ["patient_id", "os_status", "os_months", "dfs_status",
                     "dfs_months", "age", "gender", "sex", "vital_status"],
    },
    "clinical_sample": {
        "required_any": [
            {"patient_id", "sample_id"},
            {"sample_id", "cancer_type"},
            {"sample_id", "cancer_type_detailed"},
        ],
        "keywords": ["sample_id", "patient_id", "cancer_type", "subtype",
                     "cancer_type_detailed", "sample_type", "oncotree_code"],
    },
    "expression": {
        "required_any": [
            {"hugo_symbol"},
            {"entrez_gene_id"},
        ],
        "keywords": ["hugo_symbol", "entrez_gene_id", "rna_seq", "fpkm", "tpm", "rpkm"],
        # distinguished by float values in sample columns
    },
    "methylation": {
        "required_any": [
            {"hugo_symbol"},
            {"entrez_gene_id"},
        ],
        "keywords": ["hugo_symbol", "entrez_gene_id", "beta_value", "methylation"],
    },
    "timeline": {
        "required_any": [
            {"patient_id", "start_date", "event_type"},
            {"patient_id", "start_date", "stop_date"},
        ],
        "keywords": ["patient_id", "start_date", "stop_date", "event_type",
                     "treatment_type", "agent", "specimen_site"],
    },
}


# ---------------------------------------------------------------------------
# Few-shot example loader
# ---------------------------------------------------------------------------

def load_few_shot_examples() -> List[dict]:
    """
    Load all curator-provided input/output/type triples from FEW_SHOT_DIR.
    Returns a list of dicts:
        { "type": str, "input_preview": str, "output_preview": str }
    """
    examples = []
    type_files = glob.glob(os.path.join(FEW_SHOT_DIR, "*.type.txt"))
    for type_file in type_files:
        base = type_file.replace(".type.txt", "")
        input_file = base + ".input.tsv"
        output_file = base + ".output.tsv"

        if not os.path.exists(input_file) or not os.path.exists(output_file):
            continue

        try:
            cbio_type = Path(type_file).read_text().strip()
            # Read first 8 lines as preview
            with open(input_file) as f:
                input_preview = "".join(f.readlines()[:8])
            with open(output_file) as f:
                output_preview = "".join(f.readlines()[:12])

            examples.append({
                "type": cbio_type,
                "input_preview": input_preview,
                "output_preview": output_preview,
            })
        except Exception as e:
            logger.warning(f"Could not load few-shot example {base}: {e}")

    logger.info(f"Loaded {len(examples)} few-shot examples from {FEW_SHOT_DIR}")
    return examples


# ---------------------------------------------------------------------------
# Heuristic detector
# ---------------------------------------------------------------------------

def _normalize_cols(columns: List[str]) -> set[str]:
    return {c.strip().lower().replace(" ", "_").replace("-", "_") for c in columns}


def _heuristic_detect(df: pd.DataFrame) -> Tuple[Optional[str], float]:
    """
    Returns (detected_type, confidence) using column-name heuristics.
    confidence is in [0.0, 1.0].
    """
    cols = _normalize_cols(df.columns.tolist())

    scores: Dict[str, float] = {}

    for fmt, sig in HEURISTIC_SIGNATURES.items():
        # Score: fraction of keywords present
        kw_hits = sum(1 for kw in sig["keywords"] if kw in cols)
        kw_score = kw_hits / max(len(sig["keywords"]), 1)

        # Bonus if any required set is fully satisfied
        required_bonus = 0.0
        for req_set in sig["required_any"]:
            if req_set.issubset(cols):
                required_bonus = 0.5
                break

        scores[fmt] = min(kw_score * 0.5 + required_bonus, 1.0)

    # Disambiguate expression vs cna_discrete vs methylation
    # They all have hugo_symbol — use value distribution to differentiate
    if scores.get("cna_discrete", 0) > 0.1 or scores.get("expression", 0) > 0.1:
        # Check sample columns (non-gene-id columns)
        sample_cols = [c for c in df.columns if c.lower() not in
                       ("hugo_symbol", "entrez_gene_id", "gene_symbol", "gene_id", "cytoband")]
        if sample_cols:
            try:
                vals = df[sample_cols].apply(pd.to_numeric, errors="coerce")
                flat = vals.values.flatten()
                flat = flat[~pd.isna(flat)]
                if len(flat) > 0:
                    mn, mx = flat.min(), flat.max()
                    # CNA discrete: values exclusively in {-2,-1,0,1,2}
                    unique_vals = set(flat)
                    if unique_vals.issubset({-2.0, -1.0, 0.0, 1.0, 2.0}):
                        scores["cna_discrete"] = max(scores.get("cna_discrete", 0), 0.85)
                        scores["expression"] = scores.get("expression", 0) * 0.2
                        scores["methylation"] = scores.get("methylation", 0) * 0.1
                    # Methylation: beta values in [0,1]
                    elif 0.0 <= mn and mx <= 1.0 and (mx - mn) > 0.05:
                        scores["methylation"] = max(scores.get("methylation", 0), 0.75)
                        scores["expression"] = scores.get("expression", 0) * 0.3
                        scores["cna_discrete"] = scores.get("cna_discrete", 0) * 0.1
                    else:
                        # Expression: wide float range
                        scores["expression"] = max(scores.get("expression", 0), 0.75)
                        scores["methylation"] = scores.get("methylation", 0) * 0.2
                        scores["cna_discrete"] = scores.get("cna_discrete", 0) * 0.1
            except Exception:
                pass

    # Disambiguate clinical_patient vs clinical_sample
    norm_cols = _normalize_cols(df.columns.tolist())
    if "sample_id" in norm_cols:
        scores["clinical_sample"] = max(scores.get("clinical_sample", 0), 0.4)
        scores["clinical_patient"] = scores.get("clinical_patient", 0) * 0.6
    elif "patient_id" in norm_cols and "sample_id" not in norm_cols:
        scores["clinical_patient"] = max(scores.get("clinical_patient", 0), 0.4)

    if not scores:
        return None, 0.0

    best = max(scores, key=scores.__getitem__)
    return best, scores[best]


# ---------------------------------------------------------------------------
# LLM-powered detector (few-shot)
# ---------------------------------------------------------------------------

def _build_detection_prompt(df: pd.DataFrame, examples: List[dict]) -> str:
    few_shot_block = ""
    for i, ex in enumerate(examples[:6]):  # max 6 examples to keep prompt manageable
        few_shot_block += f"""
--- EXAMPLE {i+1} ---
Input file preview:
{ex['input_preview']}

This is a cBioPortal file of type: {ex['type']}
Output format preview:
{ex['output_preview']}
"""

    # Compact input representation
    col_list = list(df.columns)
    sample_rows = df.head(DETECTION_SAMPLE_ROWS).to_csv(sep="\t", index=False)

    return f"""You are a bioinformatics data curation expert specializing in cBioPortal data formats.

Your task: identify which cBioPortal file type this supplemental data file represents.

Valid types:
- clinical_patient  : patient-level clinical attributes (OS_STATUS, OS_MONTHS, AGE, SEX, etc.)
- clinical_sample   : sample-level attributes (SAMPLE_ID, CANCER_TYPE, SUBTYPE, etc.)
- mutation          : somatic mutation data (MAF format — Hugo_Symbol, Chromosome, Variant_Classification, etc.)
- cna_discrete      : discrete copy number alteration matrix (values: -2,-1,0,1,2 per gene per sample)
- expression        : mRNA/RNA-seq expression matrix (continuous float values per gene per sample)
- structural_variant: fusion/SV data (Site1_Hugo_Symbol, Site2_Hugo_Symbol, SV_Status, etc.)
- timeline          : patient event timeline (PATIENT_ID, START_DATE, STOP_DATE, EVENT_TYPE)
- methylation       : DNA methylation beta-values matrix (0.0–1.0 per gene per sample)

{few_shot_block}

--- INPUT FILE TO CLASSIFY ---
Columns: {col_list}

First {min(DETECTION_SAMPLE_ROWS, len(df))} rows:
{sample_rows}

Respond with ONLY a JSON object in this exact format (no markdown, no extra text):
{{
  "type": "<one of the valid types above>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one sentence explanation>",
  "column_mappings": {{
    "<original_col>": "<suggested_cbio_column>"
  }}
}}
"""


def _parse_detection_response(raw: str) -> Tuple[str, float, str, dict]:
    raw = raw.strip()
    raw = re.sub(r"^```[^\n]*\n?", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```$", "", raw, flags=re.MULTILINE).strip()

    result = json.loads(raw)
    return result["type"], float(result["confidence"]), result.get("reasoning", ""), result.get("column_mappings", {})


def _llm_detect(
    df: pd.DataFrame,
    examples: List[dict],
    llm_config: LLMConfig,
) -> Tuple[str, float, str, dict]:
    """
    Use the shared LLM client to detect the file type with few-shot examples injected.
    Returns (detected_type, confidence, reasoning, column_mappings).
    """
    prompt = _build_detection_prompt(df, examples)
    raw = call_llm_with_retry(
        config=llm_config,
        system="You identify cBioPortal file types from tabular inputs. Return only JSON.",
        user_content=prompt,
        max_tokens=800,
    )
    return _parse_detection_response(raw)


def _build_legacy_llm_config(
    anthropic_api_key: Optional[str],
    openai_api_key: Optional[str],
    openai_model: str,
    litellm_api_key: Optional[str],
    litellm_model: Optional[str],
    litellm_base_url: Optional[str],
) -> Optional[LLMConfig]:
    if anthropic_api_key:
        return build_llm_config("Anthropic", api_key=anthropic_api_key)
    if openai_api_key:
        return build_llm_config("OpenAI", api_key=openai_api_key, model=openai_model)
    if litellm_model:
        return build_llm_config(
            "LiteLLM",
            api_key=litellm_api_key,
            model=litellm_model,
            base_url=litellm_base_url,
        )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_file_type(
    df: pd.DataFrame,
    llm_config: Optional[LLMConfig] = None,
    anthropic_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    openai_model: str = "gpt-5.5",
    litellm_api_key: Optional[str] = None,
    litellm_model: Optional[str] = None,
    litellm_base_url: Optional[str] = None,
) -> dict:
    """
    Detect the cBioPortal format of a DataFrame.

    Returns a dict:
    {
        "type": str,           # e.g. "clinical_patient"
        "confidence": float,   # 0.0 – 1.0
        "method": str,         # "heuristic" | "llm_few_shot"
        "reasoning": str,
        "column_mappings": dict,
        "low_confidence": bool,
    }
    """
    from config import DETECTION_CONFIDENCE_THRESHOLD

    # 1. Heuristic pass
    h_type, h_conf = _heuristic_detect(df)
    logger.info(f"Heuristic detection: type={h_type}, confidence={h_conf:.2f}")

    if h_conf >= DETECTION_CONFIDENCE_THRESHOLD:
        return {
            "type": h_type,
            "confidence": h_conf,
            "method": "heuristic",
            "reasoning": f"Column names strongly match '{h_type}' pattern.",
            "column_mappings": {},
            "low_confidence": False,
        }

    # 2. LLM few-shot pass
    resolved_llm_config = llm_config or _build_legacy_llm_config(
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        litellm_api_key=litellm_api_key,
        litellm_model=litellm_model,
        litellm_base_url=litellm_base_url,
    )

    if resolved_llm_config:
        try:
            examples = load_few_shot_examples()
            llm_type, llm_conf, reasoning, mappings = _llm_detect(df, examples, resolved_llm_config)
            logger.info(
                "LLM detection via %s: type=%s, confidence=%.2f",
                resolved_llm_config.provider,
                llm_type,
                llm_conf,
            )
            return {
                "type": llm_type,
                "confidence": llm_conf,
                "method": f"{resolved_llm_config.provider.lower()}_few_shot",
                "reasoning": reasoning,
                "column_mappings": mappings,
                "low_confidence": llm_conf < DETECTION_CONFIDENCE_THRESHOLD,
            }
        except Exception as e:
            logger.error("LLM detection failed for %s: %s", resolved_llm_config.provider, e)

    # 3. Fallback: return best heuristic guess with low confidence flag
    return {
        "type": h_type or "clinical_sample",
        "confidence": h_conf,
        "method": "heuristic_fallback",
        "reasoning": "Low-confidence heuristic guess. Please verify.",
        "column_mappings": {},
        "low_confidence": True,
    }
