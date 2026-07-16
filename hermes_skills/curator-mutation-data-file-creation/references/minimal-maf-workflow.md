# Minimal MAF Workflow

This note condenses the mutation-data guidance from `curator-cbioportal-dataset-generation/references/cBioPortal_Data_Curation_SOP.md` and the contract enforced by `scripts/run_genome_nexus.py`.

## Workspace and paths

Use `studies/<PMCID>/curated/` as the mutation-curation workspace for the study.

Within that directory:
- create `minimal_mutations.maf`
- run Genome Nexus with `--workspace` only
- expect `data_mutations.txt`, `annotations_errors.txt`, and `genome_nexus.log` to be written back into the same directory

## When this workflow applies

Proceed only when local files contain real per-sample variants with:
- sample identifiers
- genomic coordinates
- reference and alternate alleles

Do not create `data_mutations.txt` from:
- narrative text
- gene-level summary tables
- mutation counts without row-level variants
- clinical assay flags such as exome availability
- pathway, drug-response, or association tables

## Minimal MAF required by the local runner

The bundled Genome Nexus runner requires these columns:
- `Chromosome`
- `Start_Position`
- `End_Position`
- `Reference_Allele`
- `Tumor_Seq_Allele2`
- `Tumor_Sample_Barcode`

Useful extra columns when directly supported by the source:
- `Hugo_Symbol`
- `Variant_Classification`
- `NCBI_Build`

Rules:
- Keep one variant per row.
- Match `Tumor_Sample_Barcode` to the final study sample IDs.
- Do not put `NA` in `Reference_Allele`.
- Do not invent protein changes, transcript annotations, dbSNP IDs, or Entrez IDs.
- Use an explicit genome build. If it is unknown, stop instead of guessing.

## Genome Nexus step

The local runner:
- validates the canonical `minimal_mutations.maf` before running
- annotates with MSK isoform override
- writes the canonical `data_mutations.txt`
- emits a machine-readable JSON result
- saves `annotations_errors.txt` and `genome_nexus.log`

Treat `partial_success` as a real warning state. Review both the JSON payload and the generated error report before considering the mutation file usable.
