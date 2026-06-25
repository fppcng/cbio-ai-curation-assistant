---
name: cbioportal_maf_curation
description: Use this skill when creating, curating, or preparing cBioPortal mutation data in MAF format.
---

# cBioPortal MAF Curation

Use this skill when mutation data must be converted into cBioPortal MAF format.

## Main rule

Create the most complete MAF supported by the source data, but do not invent unavailable mutation annotations.

If the source data already contains a complete or near-complete MAF, curate it straight into the final `data_mutations.txt` format.

If the source data only contains genomic coordinates and alleles, create a minimal MAF for later Genome Nexus annotation.

## Minimal MAF

When only minimal variant information is available, create minimal_maf.txt instead of data_mutations.txt.

When creating the minimal MAF, clearly report that the user should run Genome Nexus manually.