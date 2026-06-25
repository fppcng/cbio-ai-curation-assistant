"""
system_prompt_config.py
-----------------------
Named system-prompt registry for Synopsis.

Callers
-------
  query.py             → DEFAULT_SYSTEM_PROMPT (via _llm_summarise)
  cbioportal_curator.py → uses its own inline SYSTEM_PROMPT_CURATOR
  gene_alteration_analyst.py → uses its own inline _CODE_SYSTEM_PROMPT
"""
import os

DEFAULT_SYSTEM_PROMPT = (
    "You are a bioinformatician that only provides answers based on the given documents. "
    "If the information is not available in the documents, respond with "
    "'I do not know the answer based on the provided documents.'"
)

CBIO_TRANSFORM_SYSTEM_PROMPT = (
    "You are a bioinformatics data curation expert specialising in cBioPortal data formats. "
    "Transform input data into the exact cBioPortal file format specified. "
    "Return ONLY the correctly formatted TSV — no explanations, no markdown fences, no preamble."
)

_PROMPTS = {
    "default":          DEFAULT_SYSTEM_PROMPT,
    "cbio_transform":   CBIO_TRANSFORM_SYSTEM_PROMPT,
}


def get_prompt(name: str) -> str:
    """Return a named system prompt, falling back to DEFAULT_SYSTEM_PROMPT."""
    return _PROMPTS.get(name, DEFAULT_SYSTEM_PROMPT)


def load_system_prompt(path: str) -> str:
    """
    Load a system prompt from a text file.
    Returns DEFAULT_SYSTEM_PROMPT if the file doesn't exist or path is empty.
    """
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return DEFAULT_SYSTEM_PROMPT
