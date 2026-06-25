# Sparse supplementary mutation tables -> cBioPortal MAF

Use this note when the paper provides a mutation table that is clearly somatic-variant data but does **not** ship as a full MAF.

## Common source shape

Typical columns look like:

- `Sample`
- `chromosome`
- `Position`
- `Substitution`
- `Gene`
- `Mutation type`
- optional context columns such as `Context`

This is enough to build a minimal or minimal-style cBioPortal mutation file if the study already has a stable `SAMPLE_ID` mapping.

## Recommended conversion order

1. Canonicalize `Sample` values to the final study `SAMPLE_ID` vocabulary first.
2. Parse the substitution syntax into allele fields and coordinates.
3. Infer `Variant_Type` from the allele lengths.
4. Map source mutation classes into cBioPortal `Variant_Classification` values.
5. Leave unsupported annotation columns blank and document the limitation.

## Deterministic substitution parsing

Treat the source `Position` as a 1-based start position.

### SNV / MNV pattern

- Source: `A>T`
- Output:
  - `Reference_Allele=A`
  - `Tumor_Seq_Allele2=T`
  - `Start_Position=Position`
  - `End_Position=Position + len(Reference_Allele) - 1`

### Insertion pattern

- Source: `*>+SEQ`
- Output:
  - `Reference_Allele=-`
  - `Tumor_Seq_Allele2=SEQ`
  - `Variant_Type=INS`
  - `Start_Position=End_Position=Position`

### Deletion pattern

- Source: `*>-SEQ`
- Output:
  - `Reference_Allele=SEQ`
  - `Tumor_Seq_Allele2=-`
  - `Variant_Type=DEL`
  - `End_Position=Position + len(SEQ) - 1`

## Useful class mappings

Map source labels into cBioPortal-compatible names. Example patterns that came up in practice:

- `NON_SYNONYMOUS_CODING` -> `Missense_Mutation`
- `SYNONYMOUS_CODING` -> `Silent`
- `STOP_GAINED` -> `Nonsense_Mutation`
- `STOP_LOST` -> `Nonstop_Mutation`
- `SPLICE_SITE_ACCEPTOR` / `SPLICE_SITE_DONOR` -> `Splice_Site`
- `FRAME_SHIFT` -> `Frame_Shift_Del` or `Frame_Shift_Ins` depending on inferred allele lengths
- `CODON_DELETION` -> `In_Frame_Del`
- `CODON_INSERTION` -> `In_Frame_Ins`

## Reporting guidance

If the source lacks protein annotations, explicitly say that `HGVSp_Short` and related rich annotations were left blank because they were not present in the supplement.

If you normalized sample IDs or inferred alleles from a compact syntax, include those rules in the study assumptions / validation summary.
