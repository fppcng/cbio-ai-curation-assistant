"""
cbioportal_spec.py
──────────────────
Authoritative cBioPortal file-format schemas, derived from:
  https://docs.cbioportal.org/file-formats/

Each FORMAT entry defines:
  required  – columns that MUST be present for the file to load
  optional  – columns that are recognised and used if present
  aliases   – alternative column names accepted for the same field
              (key = canonical cBioPortal name, value = list of aliases)
  matrix    – True if the format is a gene × sample matrix
               (first col = gene, remaining cols = sample IDs)
  notes     – free-text caveats shown in the report

Matching logic (spec_match.py):
  confidence = (required_hits / total_required) * 70
              + (optional_hits  / total_optional)  * 30
  capped at 100.  Minimum confidence to accept a classification: 40.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class FormatSpec:
    key: str                          # internal key, e.g. "MUTATION_MAF"
    target_file: str                  # cBioPortal filename pattern
    required: list[str]               # canonical required column names (lowercase)
    optional: list[str]               # canonical optional column names (lowercase)
    aliases: dict[str, list[str]]     # canonical → [alias, alias, …]
    matrix: bool = False              # gene × sample matrix?
    notes: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Format Specifications
# Source: https://docs.cbioportal.org/file-formats/
# ─────────────────────────────────────────────────────────────────────────────

SPECS: list[FormatSpec] = [

    # ── Clinical — Patient ────────────────────────────────────────────────────
    FormatSpec(
        key="CLINICAL_PATIENT",
        target_file="data_clinical_patient.txt",
        required=["patient_id"],
        optional=[
            "sex", "gender", "age", "os_status", "os_months",
            "dfs_status", "dfs_months", "pfs_status", "pfs_months",
            "race", "ethnicity", "smoking_history",
        ],
        aliases={
            "patient_id": ["patient id", "case id", "patientid", "case_id",
                           "patient", "subject_id"],
            "sex":        ["gender", "sex"],
            "os_status":  ["overall survival status", "vital status"],
            "os_months":  ["overall survival months", "survival months",
                           "follow-up months"],
        },
        notes=(
            "Requires a 5-row cBioPortal header block above the data rows: "
            "Display Name, Description, Datatype, Priority, Column Name."
        ),
    ),

    # ── Clinical — Sample ─────────────────────────────────────────────────────
    FormatSpec(
        key="CLINICAL_SAMPLE",
        target_file="data_clinical_sample.txt",
        required=["patient_id", "sample_id"],
        optional=[
            "cancer_type", "cancer_type_detailed", "sample_type",
            "tumor_site", "tumor_purity", "oncotree_code",
            "tumor_size", "mitotic_index", "risk_stratification",
            "tki_treatment", "molecular_subtype",
        ],
        aliases={
            "patient_id": ["patient id", "case id", "patientid", "case_id"],
            "sample_id":  ["sample id", "sampleid", "tumor_sample_barcode",
                           "sample", "specimen id"],
            "tumor_site": ["primary location", "primary site", "site"],
            "tumor_size": ["tumor size", "tumor size (cm)", "size (cm)"],
            "mitotic_index": ["mitotic index", "mit index",
                              "mitotic rate", "mitoses per 50 hpf"],
        },
        notes=(
            "Requires 5-row cBioPortal header. "
            "SAMPLE_ID must exactly match Tumor_Sample_Barcode in MAF files."
        ),
    ),

    # ── Mutations (MAF) ───────────────────────────────────────────────────────
    FormatSpec(
        key="MUTATION_MAF",
        target_file="data_mutations.txt",
        required=[
            "hugo_symbol", "tumor_sample_barcode",
            "chromosome", "start_position", "end_position",
            "reference_allele", "tumor_seq_allele2",
        ],
        optional=[
            "variant_classification", "variant_type",
            "ncbi_build", "strand",
            "t_depth", "t_ref_count", "t_alt_count",
            "n_depth", "n_ref_count", "n_alt_count",
            "t_af", "matched_norm_sample_barcode",
            "hgvsp_short", "hgvsc", "transcript_id",
            "exon_number", "hotspot",
        ],
        aliases={
            "hugo_symbol":           ["gene", "gene symbol", "gene_symbol",
                                      "hgnc symbol", "symbol"],
            "tumor_sample_barcode":  ["sample id", "sample_id", "barcode",
                                      "sampleid", "tumor barcode"],
            "chromosome":            ["chr", "chrom", "chromosome"],
            "start_position":        ["start location", "start pos",
                                      "start", "pos"],
            "end_position":          ["end location", "end pos", "end"],
            "reference_allele":      ["reference", "ref", "ref allele",
                                      "ref_allele"],
            "tumor_seq_allele2":     ["alteration", "alt", "alt allele",
                                      "tumor allele", "alternate allele"],
            "variant_classification":["mutation type", "mutation_type",
                                      "exonicfunc", "variant type",
                                      "exonic mutation function"],
            "t_af":                  ["vaf", "af", "variant allele frequency",
                                      "variant allele frequency mean",
                                      "tumor vaf"],
        },
        notes=(
            "Chromosome values must NOT have 'chr' prefix. "
            "NCBI_Build must be GRCh37 (hg19) or GRCh38 (hg38). "
            "ANNOVAR Exonic_func values must be remapped to MAF "
            "Variant_Classification terms."
        ),
    ),

    # ── Discrete CNA (gene-level GISTIC matrix) ───────────────────────────────
    FormatSpec(
        key="DISCRETE_CNA",
        target_file="data_CNA.txt",
        required=["hugo_symbol"],
        optional=[],
        aliases={
            "hugo_symbol": ["gene", "gene_symbol", "gene symbol", "symbol"],
        },
        matrix=True,
        notes=(
            "Gene × sample integer matrix. Values: -2 (deep del), -1 (shallow del), "
            "0 (diploid), 1 (low gain), 2 (amplification). "
            "First column must be Hugo_Symbol; remaining columns are sample IDs."
        ),
    ),

    # ── Continuous CNA (log2 ratio matrix) ────────────────────────────────────
    FormatSpec(
        key="CONTINUOUS_CNA",
        target_file="data_log2_CNA.txt",
        required=["hugo_symbol"],
        optional=[],
        aliases={
            "hugo_symbol": ["gene", "gene_symbol", "gene symbol", "symbol"],
        },
        matrix=True,
        notes=(
            "Gene × sample log2(copy-number ratio) matrix. "
            "Values are continuous floats, typically in range [-3, 3]."
        ),
    ),

    # ── Segmented CNA ─────────────────────────────────────────────────────────
    FormatSpec(
        key="SEGMENTED",
        target_file="data_segments.txt",
        required=["id", "chrom", "loc.start", "loc.end", "num.mark", "seg.mean"],
        optional=["sample"],
        aliases={
            "id":        ["sample", "sample_id", "sample id", "tumor_sample_barcode"],
            "chrom":     ["chromosome", "chr", "chrom"],
            "loc.start": ["start", "start_position", "loc start", "start pos"],
            "loc.end":   ["end", "end_position", "loc end", "end pos"],
            "num.mark":  ["num markers", "num_markers", "markers",
                          "number of markers"],
            "seg.mean":  ["mean", "log2ratio", "log2_ratio", "log2 ratio",
                          "mean log2 ratio", "segment mean"],
        },
        notes=(
            "CBS segmentation format. Chromosome values must NOT have 'chr' prefix. "
            "seg.mean is log2(copy-number ratio)."
        ),
    ),

    # ── mRNA Expression ───────────────────────────────────────────────────────
    FormatSpec(
        key="EXPRESSION",
        target_file="data_mrna_seq_fpkm.txt / data_mrna_seq_tpm.txt",
        required=["hugo_symbol"],
        optional=["entrez_gene_id"],
        aliases={
            "hugo_symbol":    ["gene", "gene_symbol", "gene symbol", "symbol"],
            "entrez_gene_id": ["entrez", "entrez id", "gene id", "ncbi gene id"],
        },
        matrix=True,
        notes=(
            "Gene × sample expression matrix. Values are FPKM, TPM, or RPKM. "
            "Log-transform is optional but recommended. "
            "Z-score matrix can also be loaded as data_mrna_seq_v2_rsem_zscores.txt."
        ),
    ),

    # ── Structural Variants / Fusions ─────────────────────────────────────────
    # Per live docs (docs.cbioportal.org/file-formats/):
    #   Required: Sample_Id + SV_Status + at least one of Site1/Site2 gene symbol
    #   Class, Annotation, Event_Info are "shown prominently" but NOT required
    FormatSpec(
        key="STRUCTURAL_VARIANT",
        target_file="data_sv.txt",
        required=["sample_id", "sv_status"],
        optional=[
            "site1_hugo_symbol", "site1_entrez_gene_id",
            "site2_hugo_symbol", "site2_entrez_gene_id",
            "site1_chromosome", "site1_position", "site1_region",
            "site2_chromosome", "site2_position", "site2_region",
            "site1_ensembl_transcript_id", "site2_ensembl_transcript_id",
            "class", "event_info", "annotation",
            "dna_support", "rna_support",
            "normal_read_count", "tumor_read_count",
            "tumor_variant_count",
        ],
        aliases={
            "sample_id":                    ["sample id", "sampleid",
                                             "tumor_sample_barcode", "barcode"],
            "sv_status":                    ["status", "somatic", "germline",
                                             "sv status"],
            "site1_hugo_symbol":            ["gene1", "gene 1", "left gene",
                                             "left_gene", "partner1", "gene a"],
            "site2_hugo_symbol":            ["gene2", "gene 2", "right gene",
                                             "right_gene", "partner2", "gene b"],
            "class":                        ["sv type", "sv_type", "event type",
                                             "structural variant type", "type",
                                             "svtype"],
            "site1_chromosome":             ["left chr", "left_chr", "chr1",
                                             "start chr", "chromosome1"],
            "site2_chromosome":             ["right chr", "right_chr", "chr2",
                                             "end chr", "chromosome2"],
            "site1_position":               ["left position", "start position",
                                             "pos1", "breakpoint1"],
            "site2_position":               ["right position", "end position",
                                             "pos2", "breakpoint2"],
            "site1_ensembl_transcript_id":  ["transcript1", "ensembl transcript1",
                                             "site1 transcript"],
            "site2_ensembl_transcript_id":  ["transcript2", "ensembl transcript2",
                                             "site2 transcript"],
        },
        notes=(
            "Per cBioPortal docs: Sample_Id + SV_Status are required. "
            "At least one of Site1_Hugo_Symbol/Site1_Entrez_Gene_Id OR "
            "Site2_Hugo_Symbol/Site2_Entrez_Gene_Id is also needed. "
            "Class, Annotation, Event_Info are optional but displayed prominently. "
            "SV_Status should be SOMATIC for tumour SVs. "
            "Chromosome values must NOT have 'chr' prefix."
        ),
    ),

    # ── DNA Methylation ───────────────────────────────────────────────────────
    FormatSpec(
        key="METHYLATION",
        target_file="data_methylation_hm27.txt / data_methylation_hm450.txt",
        required=["hugo_symbol"],
        optional=["entrez_gene_id"],
        aliases={
            "hugo_symbol":    ["gene", "gene_symbol", "gene symbol", "symbol"],
            "entrez_gene_id": ["entrez", "entrez id"],
        },
        matrix=True,
        notes=(
            "Gene × sample beta-value matrix. "
            "Values must be in range [0, 1] (proportion of methylated reads). "
            "Probe-level data must be aggregated to gene level before loading."
        ),
    ),

    # ── MutSig ────────────────────────────────────────────────────────────────
    FormatSpec(
        key="MUTSIG",
        target_file="data_mutsig.txt",
        required=["gene", "p", "q"],
        optional=["rank", "codelen", "nnon", "nsil", "npat",
                  "nsite", "frac_cov", "pCV", "pCL", "pFN"],
        aliases={
            "gene":    ["hugo_symbol", "gene symbol", "symbol"],
            "p":       ["p-value", "pvalue", "p_value"],
            "q":       ["q-value", "qvalue", "q_value", "fdr", "fdr_q_value"],
            "codelen": ["coding length", "cod len"],
            "nnon":    ["n non-silent", "non-silent count", "nonsilent"],
            "npat":    ["n patients", "num patients", "n_patients"],
        },
        notes=(
            "Output of MutSigCV. The p and q columns are mandatory — "
            "retrieve from full MutSigCV output if missing from supplement."
        ),
    ),

    # ── GISTIC gene-level output ──────────────────────────────────────────────
    FormatSpec(
        key="GISTIC",
        target_file="data_gistic_genes_amp.txt / data_gistic_genes_del.txt",
        required=["cytoband", "q value"],
        optional=["residual q value", "wide peak boundaries",
                  "genes in wide peak (ordered by frequency of alteration)"],
        aliases={
            "cytoband":  ["cytband", "cyto band", "band"],
            "q value":   ["q-value", "qvalue", "fdr"],
            "wide peak boundaries": ["peak boundaries", "wide peak"],
        },
        notes=(
            "Direct output from GISTIC2.0 all_thresholded.by_genes table. "
            "Separate files required for amplifications and deletions."
        ),
    ),

    # ── Generic Assay ─────────────────────────────────────────────────────────
    FormatSpec(
        key="GENERIC_ASSAY",
        target_file="Generic Assay (custom .txt)",
        required=["entity_stable_id"],
        optional=["name", "description"],
        aliases={
            "entity_stable_id": ["entity id", "signature", "immune cell",
                                  "cell type", "assay id"],
        },
        matrix=True,
        notes=(
            "Entity × sample matrix. GENERIC_ASSAY_TYPE must be declared in "
            "the meta file (e.g. MUTATIONAL_SIGNATURE, IMMUNE_SCORE, "
            "TREATMENT_RESPONSE, ARM_LEVEL_CNA). "
            "Values are numeric per sample."
        ),
    ),
]

# ── Quick lookup dict ─────────────────────────────────────────────────────────
SPEC_BY_KEY: dict[str, FormatSpec] = {s.key: s for s in SPECS}
