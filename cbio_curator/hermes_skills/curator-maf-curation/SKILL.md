---
name: curator-maf-curation
description: Use this skill when creating, curating, or preparing cBioPortal mutation data in MAF format.
---

# cBioPortal MAF Curation

Use this skill when mutation data must be converted into cBioPortal MAF format.

## Main rule

Create the most complete MAF supported by the source data, but do not invent unavailable mutation annotations.

If the source data already contains a complete or near-complete MAF, curate it straight into the final `data_mutations.txt` format.

If the source data only contains genomic coordinates and alleles, create a minimal MAF for later Genome Nexus annotation.

## Workflow

1. Inspect the source mutation table before deciding whether it is a full MAF or a sparse mutation table.
   - Common sparse-table patterns are columns like `Sample`, `chromosome`, `Position`, `Substitution`, `Gene`, and `Mutation type`.
   - Do not assume protein-level annotations exist just because the file is mutation-like.

2. Canonicalize sample identifiers against the study clinical sample file before writing mutation rows.
   - Use the final `SAMPLE_ID` vocabulary from `data_clinical_sample.txt` as the source of truth.
   - Normalize systematic punctuation drift such as hyphen/underscore mismatches before validation.
   - Record the normalization rule if you had to reconcile source IDs.

3. Preserve only supported MAF fields.
   - Populate required columns from the source table.
   - Leave unsupported annotation columns blank rather than fabricating values.
   - Do not invent Entrez IDs, dbSNP IDs, protein changes, or validation fields when the supplement does not provide them.

4. When the source encodes alleles in a compact substitution column, convert them deterministically.
   - `REF>ALT` at a single position -> SNV/MNV with explicit `Reference_Allele` and `Tumor_Seq_Allele2`.
   - `*>+SEQ` -> insertion with `Reference_Allele=-` and inserted sequence as the tumor allele.
   - `*>-SEQ` -> deletion with deleted sequence as `Reference_Allele`, tumor allele `-`, and `End_Position` extended by deleted length.
   - Keep the conversion rule reproducible and mention it in the validation summary.

5. Map source mutation classes into cBioPortal-compatible `Variant_Classification` values.
   - Determine frame-shift insertion vs deletion from the inferred allele lengths.
   - Collapse donor/acceptor splice labels to `Splice_Site` when the source is more specific than cBioPortal.
   - Use standard cBioPortal names like `Missense_Mutation`, `Nonsense_Mutation`, `Silent`, `Frame_Shift_Del`, `Frame_Shift_Ins`, `In_Frame_Del`, and `In_Frame_Ins`.

6. If the table supports only a minimal-but-loadable mutation file, it is acceptable to write `data_mutations.txt` with blank optional annotations.
   - In particular, leave `HGVSp_Short` blank when the source does not provide protein-change annotations.
   - Clearly report that the result is a minimal or minimal-style MAF and list which downstream annotations remain absent.

## Minimal MAF

When only minimal variant information is available, create minimal_maf.txt instead of data_mutations.txt.

When creating the minimal MAF, clearly report that the user should run Genome Nexus manually.

## Pitfalls

- Do not let identifier mismatches silently remove mutation rows from the study; reconcile them before concluding the dataset is inconsistent.
- Do not confuse a sparse supplementary mutation table with a validator-ready rich MAF.
- When the source lacks protein consequences, treat blank `HGVSp_Short` as a known limitation to report, not a reason to invent values.
- If you infer alleles from a compact substitution syntax, add that inference rule to the study assumptions.

## Reference

See `references/sparse-supplementary-mutation-tables.md` for a reusable pattern for converting supplement-style mutation tables into cBioPortal-compatible MAF rows.