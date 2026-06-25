from typing import Optional, List, Dict, Tuple
"""
cbio_transformer.py
===================
Transforms a raw supplemental DataFrame into a correctly formatted
cBioPortal data file + matching meta file.

Uses few-shot in-context learning: if the curator has placed example pairs in
./few_shot_examples/, those are injected into the LLM prompt so the model
learns from real curator-validated transformations at inference time.
"""

import os
import io
import re
import json
import glob
import logging
from pathlib import Path

import pandas as pd

from config import (
    FEW_SHOT_DIR,
    LLMConfig,
    TRANSFORM_SAMPLE_ROWS,
    build_llm_config,
)
from llm_client import call_llm_with_retry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Meta file templates
# ---------------------------------------------------------------------------

META_TEMPLATES = {
    "clinical_patient": lambda study_id: f"""cancer_study_identifier: {study_id}
genetic_alteration_type: CLINICAL
datatype: PATIENT_ATTRIBUTES
data_filename: data_clinical_patient.txt""",

    "clinical_sample": lambda study_id: f"""cancer_study_identifier: {study_id}
genetic_alteration_type: CLINICAL
datatype: SAMPLE_ATTRIBUTES
data_filename: data_clinical_sample.txt""",

    "mutation": lambda study_id: f"""cancer_study_identifier: {study_id}
genetic_alteration_type: MUTATION_EXTENDED
datatype: MAF
stable_id: mutations
show_profile_in_analysis_tab: true
profile_name: Mutations
profile_description: Somatic mutation data.
data_filename: data_mutations.txt""",

    "cna_discrete": lambda study_id: f"""cancer_study_identifier: {study_id}
genetic_alteration_type: COPY_NUMBER_ALTERATION
datatype: DISCRETE
stable_id: gistic
show_profile_in_analysis_tab: true
profile_name: Putative copy-number alterations from GISTIC
profile_description: Putative copy-number from GISTIC 2.0. Values: -2=homozygous deletion; -1=hemizygous deletion; 0=neutral; 1=gain; 2=high level amplification.
data_filename: data_cna.txt""",

    "expression": lambda study_id: f"""cancer_study_identifier: {study_id}
genetic_alteration_type: MRNA_EXPRESSION
datatype: CONTINUOUS
stable_id: rna_seq_mrna
show_profile_in_analysis_tab: false
profile_name: mRNA expression (RNA-Seq)
profile_description: RNA-seq expression values.
data_filename: data_expression.txt""",

    "structural_variant": lambda study_id: f"""cancer_study_identifier: {study_id}
genetic_alteration_type: STRUCTURAL_VARIANT
datatype: SV
stable_id: structural_variants
show_profile_in_analysis_tab: true
profile_name: Structural Variants
profile_description: Structural variant / fusion data.
data_filename: data_sv.txt""",

    "timeline": lambda study_id: f"""cancer_study_identifier: {study_id}
genetic_alteration_type: CLINICAL
datatype: TIMELINE
data_filename: data_timeline.txt""",

    "methylation": lambda study_id: f"""cancer_study_identifier: {study_id}
genetic_alteration_type: METHYLATION
datatype: CONTINUOUS
stable_id: methylation_hm450
show_profile_in_analysis_tab: false
profile_name: Methylation (HM450)
profile_description: Methylation beta-values (HM450 platform).
data_filename: data_methylation_hm450.txt""",
}

DATA_FILENAMES = {
    "clinical_patient": "data_clinical_patient.txt",
    "clinical_sample": "data_clinical_sample.txt",
    "mutation": "data_mutations.txt",
    "cna_discrete": "data_cna.txt",
    "expression": "data_expression.txt",
    "structural_variant": "data_sv.txt",
    "timeline": "data_timeline.txt",
    "methylation": "data_methylation_hm450.txt",
}

META_FILENAMES = {
    "clinical_patient": "meta_clinical_patient.txt",
    "clinical_sample": "meta_clinical_sample.txt",
    "mutation": "meta_mutations.txt",
    "cna_discrete": "meta_cna.txt",
    "expression": "meta_expression.txt",
    "structural_variant": "meta_sv.txt",
    "timeline": "meta_timeline.txt",
    "methylation": "meta_methylation_hm450.txt",
}


# ---------------------------------------------------------------------------
# cBioPortal format specifications used in the transform prompt
# ---------------------------------------------------------------------------

FORMAT_SPECS = {
    "clinical_patient": """
CLINICAL PATIENT FILE FORMAT:
- 5 header rows starting with #:
  Row 1: #Display Name for each column
  Row 2: #Description for each column
  Row 3: #Datatype: STRING, NUMBER, or BOOLEAN
  Row 4: #Priority: integer (1=normal, higher=more prominent, 0=hidden)
  Row 5: Column names in UPPERCASE (no #)
- Required column: PATIENT_ID
- Key columns: OS_STATUS (1:DECEASED/0:LIVING), OS_MONTHS, DFS_STATUS (1:Recurred/Progressed/0:DiseaseFree), DFS_MONTHS, AGE, SEX/GENDER
- Map vital_status/survival_status → OS_STATUS using: dead/deceased/died → "1:DECEASED", alive/living → "0:LIVING"
- Time columns should be in MONTHS
- Tab-separated
""",
    "clinical_sample": """
CLINICAL SAMPLE FILE FORMAT:
- 5 header rows starting with #:
  Row 1: #Display Name
  Row 2: #Description
  Row 3: #Datatype: STRING, NUMBER, or BOOLEAN
  Row 4: #Priority: integer
  Row 5: Column names in UPPERCASE (no #)
- Required columns: PATIENT_ID, SAMPLE_ID
- Key columns: CANCER_TYPE, CANCER_TYPE_DETAILED, ONCOTREE_CODE, SAMPLE_TYPE, SUBTYPE
- Extract PATIENT_ID from TCGA barcodes: TCGA-XX-XXXX-01 → TCGA-XX-XXXX
- Tab-separated
""",
    "mutation": """
MUTATION DATA (MAF) FORMAT:
- No # header rows
- Tab-separated
- Required columns: Hugo_Symbol, Entrez_Gene_Id, NCBI_Build (GRCh37 or GRCh38), Chromosome, Start_Position, End_Position, Strand, Variant_Classification, Variant_Type, Reference_Allele, Tumor_Seq_Allele1, Tumor_Seq_Allele2, Tumor_Sample_Barcode, HGVSp_Short
- Variant_Classification values: Frame_Shift_Del, Frame_Shift_Ins, In_Frame_Del, In_Frame_Ins, Missense_Mutation, Nonsense_Mutation, Silent, Splice_Site, Translation_Start_Site, Nonstop_Mutation, 3'UTR, 5'UTR, Intron, IGR
- HGVSp_Short format: p.V600E
""",
    "cna_discrete": """
DISCRETE CNA FORMAT:
- No # header rows
- Tab-separated
- Required columns: Hugo_Symbol, then one column per sample with the SAMPLE_ID as header
- Values MUST be integers: -2 (homozygous del), -1 (hemizygous del), 0 (neutral), 1 (gain), 2 (amplification)
- Round/map any float values to nearest integer in [-2,2]
""",
    "expression": """
EXPRESSION DATA FORMAT:
- No # header rows
- Tab-separated
- Required columns: Hugo_Symbol (and optionally Entrez_Gene_Id), then one column per sample
- Values: continuous real numbers (FPKM, TPM, RPKM, or log2 values)
- NA for missing values
""",
    "structural_variant": """
STRUCTURAL VARIANT FORMAT:
- No # header rows
- Tab-separated
- Required columns: Sample_Id, SV_Status (SOMATIC or GERMLINE)
- Strongly recommended: Site1_Hugo_Symbol, Site1_Entrez_Gene_Id, Site1_Chromosome, Site1_Position, Site2_Hugo_Symbol, Site2_Entrez_Gene_Id, Site2_Chromosome, Site2_Position, Class, Event_Info, Annotation
- Class values: Deletion, Duplication, Insertion, Inversion, Translocation
""",
    "timeline": """
TIMELINE FORMAT:
- No # header rows
- Tab-separated
- Required columns: PATIENT_ID, START_DATE (days from diagnosis), STOP_DATE, EVENT_TYPE
- EVENT_TYPE values: TREATMENT, SPECIMEN, LAB_TEST, IMAGING, STATUS, SURGERY
- TREATMENT columns: TREATMENT_TYPE, SUBTYPE, AGENT
- LAB_TEST columns: TEST, RESULT
""",
    "methylation": """
METHYLATION FORMAT:
- No # header rows
- Tab-separated
- Required columns: Hugo_Symbol, then one column per sample
- Values: beta-values between 0.0 and 1.0
- NA for missing
""",
}


# ---------------------------------------------------------------------------
# Few-shot example loader (type-specific)
# ---------------------------------------------------------------------------

def load_few_shot_examples_for_type(cbio_type: str) -> List[dict]:
    """Load only examples matching the target cBioPortal type."""
    examples = []
    type_files = glob.glob(os.path.join(FEW_SHOT_DIR, "*.type.txt"))
    for type_file in type_files:
        try:
            t = Path(type_file).read_text().strip()
            if t != cbio_type:
                continue
            base = type_file.replace(".type.txt", "")
            input_file = base + ".input.tsv"
            output_file = base + ".output.tsv"
            if not os.path.exists(input_file) or not os.path.exists(output_file):
                continue
            with open(input_file) as f:
                input_text = "".join(f.readlines()[:15])
            with open(output_file) as f:
                output_text = "".join(f.readlines()[:20])
            examples.append({"input": input_text, "output": output_text})
        except Exception as e:
            logger.warning(f"Could not load example {type_file}: {e}")
    return examples


# ---------------------------------------------------------------------------
# LLM transform
# ---------------------------------------------------------------------------

def _llm_transform(
    df: pd.DataFrame,
    cbio_type: str,
    study_id: str,
    column_mappings: dict,
    curator_notes: str,
    llm_config: LLMConfig,
) -> str:
    """
    Call the shared LLM client to transform df into cBioPortal format.
    Returns transformed TSV as a string.
    """
    examples = load_few_shot_examples_for_type(cbio_type)

    few_shot_block = ""
    for i, ex in enumerate(examples[:4]):
        few_shot_block += f"""
=== FEW-SHOT EXAMPLE {i+1} ===
Input:
{ex['input']}

Correct cBioPortal output for type "{cbio_type}":
{ex['output']}
"""

    input_preview = df.head(TRANSFORM_SAMPLE_ROWS).to_csv(sep="\t", index=False)
    mapping_hint = ""
    if column_mappings:
        mapping_hint = f"\nDetected column mappings to apply:\n{json.dumps(column_mappings, indent=2)}\n"

    system = f"""You are a bioinformatics data curation expert specializing in cBioPortal data formats.
Transform input data into the exact cBioPortal file format specified.
Return ONLY the correctly formatted TSV content — no explanations, no markdown code fences, no preamble.

{FORMAT_SPECS.get(cbio_type, '')}
"""

    user = f"""Transform the following data into cBioPortal format: {cbio_type}
Cancer study identifier: {study_id}
{mapping_hint}
{f'Curator notes: {curator_notes}' if curator_notes else ''}

{few_shot_block}

=== INPUT DATA ===
{input_preview}

Return ONLY the properly formatted cBioPortal TSV. No explanations. No markdown fences.
"""

    raw = call_llm_with_retry(
        config=llm_config,
        system=system,
        user_content=user,
        max_tokens=4096,
    )

    # Strip any accidental markdown fences
    raw = re.sub(r"^```[^\n]*\n?", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```$", "", raw, flags=re.MULTILINE).strip()
    return raw


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transform_to_cbio(
    df: pd.DataFrame,
    cbio_type: str,
    study_id: str = "my_study_2025",
    column_mappings: Optional[dict] = None,
    curator_notes: str = "",
    llm_config: Optional[LLMConfig] = None,
    anthropic_api_key: Optional[str] = None,
) -> dict:
    """
    Transform df into cBioPortal format.

    Returns:
    {
        "data_content": str,     # TSV string of the data file
        "meta_content": str,     # content of the meta file
        "data_filename": str,
        "meta_filename": str,
        "cbio_type": str,
    }
    """
    resolved_llm_config = llm_config
    if resolved_llm_config is None and anthropic_api_key:
        resolved_llm_config = build_llm_config("Anthropic", api_key=anthropic_api_key)
    if resolved_llm_config is None:
        raise ValueError("An LLM configuration is required for transformation.")

    data_content = _llm_transform(
        df=df,
        cbio_type=cbio_type,
        study_id=study_id,
        column_mappings=column_mappings or {},
        curator_notes=curator_notes,
        llm_config=resolved_llm_config,
    )

    meta_content = META_TEMPLATES[cbio_type](study_id)

    return {
        "data_content": data_content,
        "meta_content": meta_content,
        "data_filename": DATA_FILENAMES[cbio_type],
        "meta_filename": META_FILENAMES[cbio_type],
        "cbio_type": cbio_type,
    }
