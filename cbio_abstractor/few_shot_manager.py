from typing import Optional, List, Dict, Tuple
"""
few_shot_manager.py
===================
Manages the few-shot example library that teaches the AI to detect and transform
new file patterns.

When a curator uploads a file, reviews the AI output, edits it to be correct,
and clicks "Save as Training Example", this module persists the triple:
  <n>.input.tsv  — the original supplemental file
  <n>.output.tsv — the curator-corrected cBioPortal output
  <n>.type.txt   — the cBioPortal type label

On next run, the AI automatically incorporates this example.
"""

import os
import glob
import json
import logging
from pathlib import Path
from datetime import datetime

from config import FEW_SHOT_DIR

logger = logging.getLogger(__name__)


def _next_example_id() -> str:
    existing = glob.glob(os.path.join(FEW_SHOT_DIR, "*.type.txt"))
    if not existing:
        return "001"
    nums = []
    for f in existing:
        stem = Path(f).stem.replace(".type", "")
        try:
            nums.append(int(stem))
        except ValueError:
            pass
    return str(max(nums) + 1).zfill(3) if nums else "001"


def save_example(
    input_tsv: str,
    output_tsv: str,
    cbio_type: str,
    description: str = "",
) -> str:
    """
    Save a new few-shot training example.
    Returns the example ID.
    """
    os.makedirs(FEW_SHOT_DIR, exist_ok=True)
    eid = _next_example_id()
    base = os.path.join(FEW_SHOT_DIR, eid)

    Path(base + ".input.tsv").write_text(input_tsv)
    Path(base + ".output.tsv").write_text(output_tsv)
    Path(base + ".type.txt").write_text(cbio_type)

    # Optional metadata
    meta = {
        "id": eid,
        "type": cbio_type,
        "description": description,
        "created_at": datetime.utcnow().isoformat(),
    }
    Path(base + ".meta.json").write_text(json.dumps(meta, indent=2))

    logger.info(f"Saved few-shot example {eid} for type={cbio_type}")
    return eid


def list_examples() -> List[dict]:
    """Return summary of all saved examples."""
    examples = []
    for f in sorted(glob.glob(os.path.join(FEW_SHOT_DIR, "*.type.txt"))):
        base = f.replace(".type.txt", "")
        cbio_type = Path(f).read_text().strip()
        meta_file = base + ".meta.json"
        meta = {}
        if os.path.exists(meta_file):
            try:
                meta = json.loads(Path(meta_file).read_text())
            except Exception:
                pass
        examples.append({
            "id": Path(base).name,
            "type": cbio_type,
            "description": meta.get("description", ""),
            "created_at": meta.get("created_at", ""),
            "has_input": os.path.exists(base + ".input.tsv"),
            "has_output": os.path.exists(base + ".output.tsv"),
        })
    return examples


def delete_example(example_id: str) -> bool:
    """Delete a few-shot example by ID."""
    base = os.path.join(FEW_SHOT_DIR, example_id)
    deleted = False
    for ext in [".input.tsv", ".output.tsv", ".type.txt", ".meta.json"]:
        p = base + ext
        if os.path.exists(p):
            os.remove(p)
            deleted = True
    return deleted
