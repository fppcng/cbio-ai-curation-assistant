# Mutation Sanity Checks

These checks are derived from the mutation-data section of `curator-cbioportal-dataset-generation/references/cBioPortal_Data_Curation_SOP.md`.

Review before reporting success:
- Use MSK isoform annotation. The bundled Genome Nexus runner already sets `--isoform-override mskcc`.
- Unknown `Entrez_Gene_Id` values should be `0` or blank.
- No row should carry `NA` as the reference allele.
- `Reference_Allele` should match `Tumor_Seq_Allele1`.
- Indels must not be mislabeled as missense mutations.
- Fix `HGVSp_Short` or protein-change values reported only as `MUTATED` when better information is available; otherwise report the limitation explicitly.
- Default expectation is `GRCh37`. If the study is `GRCh38`, make sure the study metadata declares `reference_genome: GRCh38`.
- Review germline rows explicitly; public studies usually exclude them unless there is a reason to keep them.
- Correct Excel-mangled gene symbols such as `SEPT13` becoming a date-like string.
- Review `Annotation_Status` counts and any Genome Nexus error report before calling the file complete.