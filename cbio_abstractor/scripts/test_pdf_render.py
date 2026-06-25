from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pdf_report import save_curation_report_pdf


def build_sample_payload() -> tuple[dict, dict]:
    meta = {
        "study_title": "Synthetic Multi-Omics Cohort",
        "study_id_suggestion": "synthetic_multiomics_2024",
        "cancer_type": "luad",
        "cancer_type_full": "Lung Adenocarcinoma",
        "num_samples": "148",
        "num_patients": "132",
        "reference_genome": "hg38",
        "sequencing_types": ["WES", "RNA-seq", "Methylation array"],
        "pmid": "12345678",
        "doi": "10.1000/synthetic.2024.001",
        "first_author_surname": "Rossi",
        "year": "2024",
        "journal": "Genome Medicine",
        "description": "Synthetic dataset used to validate PDF rendering and table layout.",
        "meta_description": "Synthetic PDF rendering validation report for cBioAbstractor.",
        "key_findings": [
            "High-confidence mutation and CNA tables are available.",
            "One structural variant sheet requires manual harmonisation.",
            "Expression data appears suitable for generic assay import.",
        ],
        "primary_site": "Lung",
        "cohort_description": "132 patients and 148 tumour samples from a synthetic validation cohort.",
        "data_repositories": ["GEO:GSE999999", "SRA:SRP000000"],
        "corresponding_authors": "Mario Rossi <mario.rossi@example.org>",
    }

    summary = {
        "study_id": "synthetic_multiomics_2024",
        "cancer_type": "luad",
        "num_samples": "148",
        "reference_genome": "hg38",
        "high_priority": 2,
        "medium_priority": 1,
        "not_loadable": 1,
        "file_breakdown": [
            {
                "file": "Supplementary_Table_1.xlsx",
                "sheet": "Mutations",
                "cbio_format": "data_mutations.txt",
                "curability": "YES",
                "priority": "HIGH",
                "confidence": 92,
                "verdict": "MUTATION_MAF (92% confidence)",
                "req_present": ["Hugo_Symbol", "Tumor_Sample_Barcode", "Chromosome"],
                "req_missing": ["Reference_Allele"],
                "opt_present": ["Protein_Change", "t_depth"],
            },
            {
                "file": "Supplementary_Table_2.tsv",
                "sheet": "CNA",
                "cbio_format": "data_cna.txt",
                "curability": "YES",
                "priority": "HIGH",
                "confidence": 88,
                "verdict": "DISCRETE_CNA (88% confidence)",
                "req_present": ["Hugo_Symbol"],
                "req_missing": [],
                "opt_present": ["Entrez_Gene_Id"],
            },
            {
                "file": "Supplementary_Table_3.csv",
                "sheet": "Expression",
                "cbio_format": "data_mrna_seq_rpkm.txt",
                "curability": "PARTIAL",
                "priority": "MEDIUM",
                "confidence": 64,
                "verdict": "EXPRESSION (64% confidence) | Missing required: Hugo_Symbol",
                "req_present": ["SAMPLE_ID"],
                "req_missing": ["Hugo_Symbol"],
                "opt_present": ["TPM"],
            },
            {
                "file": "Supplementary_Table_4.xlsx",
                "sheet": "Fusions",
                "cbio_format": "Not directly loadable",
                "curability": "NO",
                "priority": "N/A",
                "confidence": 0,
                "verdict": "NOT LOADABLE — best candidate: STRUCTURAL_VARIANT @ 35%",
                "req_present": ["Sample_Id"],
                "req_missing": ["Site1_Hugo_Symbol", "Site2_Hugo_Symbol"],
                "opt_present": [],
            },
        ],
    }
    return meta, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a synthetic PDF to test cBioAbstractor rendering.")
    parser.add_argument(
        "--output",
        default="/tmp/cbioabstractor_pdf_render_test.pdf",
        help="Destination PDF path.",
    )
    args = parser.parse_args()

    meta, summary = build_sample_payload()
    try:
        output_path = save_curation_report_pdf(meta, summary, Path(args.output))
    except ModuleNotFoundError as exc:
        if exc.name == "reportlab":
            print("Missing dependency: reportlab. Install project requirements before testing PDF rendering.")
            return 1
        raise

    output_file = Path(output_path)
    print(f"PDF created: {output_file}")
    print(f"Size: {output_file.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
