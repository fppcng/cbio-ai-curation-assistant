## Mutation Data
When loading mutation data, the `_sequenced` case list is required. See the [case list section](#case-lists).

### Meta file
The mutation metadata file should contain the following fields:

1. **cancer_study_identifier**: same value as specified in [study meta file](#cancer-study)
2. **genetic_alteration_type**: MUTATION_EXTENDED
3. **datatype**: MAF
4. **stable_id**: mutations
5. **show_profile_in_analysis_tab**: true
6. **profile_name**: A name for the mutation data, e.g., "Mutations".
7. **profile_description**: A description of the mutation data, e.g., "Mutation data from whole exome sequencing.".
8. **data_filename**: your data file
9. **gene_panel (optional)**: gene panel stable id. See [Gene panels for mutation data](#gene-panels-for-mutation-data).
10. **swissprot_identifier (optional)**: `accession` or `name`, indicating the type of identifier in the `SWISSPROT` column
11. **variant_classification_filter (optional)**: List of `Variant_Classifications` values to be filtered out.
12. **namespaces (optional)**: Comma-delimited list of `namespaces` to import. 

### Gene panels for mutation data
Using the `gene_panel` property it is possible to annotate **all samples in the MAF file** as being profiled on the **same** specified gene panel. 

Please use the [Gene Panel Matrix file](#gene-panel-matrix-file) when:
- Data contains samples that are profiled but no mutations are called. Also please add these to the `_sequenced` case list. 
- Multiple gene panels are used to profile the samples in the MAF file.

### Variant classification filter
The `variant_classification_filter` field can be used to filter out specific mutations. This field should contain a comma separated list of `Variant_Classification` values. By default, cBioPortal filters out `Silent, Intron, IGR, 3'UTR, 5'UTR, 3'Flank and 5'Flank`, except for the promoter mutations of the TERT gene. For no filtering, include this field in the metadata file, but leave it empty. For cBioPortal default filtering, do not include this field in the metadata file.
Allowed values to filter out (mainly from [Mutation Annotation Format page](https://docs.gdc.cancer.gov/Data/File_Formats/MAF_Format/)): `Frame_Shift_Del, Frame_Shift_Ins, In_Frame_Del, In_Frame_Ins, Missense_Mutation, Nonsense_Mutation, Silent, Splice_Site, Translation_Start_Site, Nonstop_Mutation, 3'UTR, 3'Flank, 5'UTR, 5'Flank, IGR, Intron, RNA, Targeted_Region, De_novo_Start_InFrame, De_novo_Start_OutOfFrame, Splice_Region and Unknown`

### Tumor seq allele ambiguity
Bugs may exist in MAF data that make it ambiguous as to whether `Tumor_Seq_Allele1` or `Tumor_Seq_Allele2` should be seen as the variant allele to be used when a new mutation record is created and imported in cBioPortal. In such cases, preference is given to the tumor seq allele value that matches a valid nucleotide pattern `^[ATGC]*$` versus a null or empty value, or "-".
For example, given `Reference_Allele` = "G", `Tumor_Seq_Allele` = "-", and `Tumor_Seq_Allele2` = "A", preference will be given to `Tumor_Seq_Allele2`. Using this same example with `Tumor_Seq_Allele1` = "T", preference will be given to `Tumor_Seq_Allele1` if it does not match `Reference_Allele`, which in this case it does not.

When curating MAF data, it is best practice to leave `Tumor_Seq_Allele1` empty if this information is not provided in your data source to avoid this ambiguity.

### Namespaces
The `namespaces` field can be used to specify additional MAF columns for import. This field should contain a comma separated list of namespaces. Namespaces can be identified as prefixes to an arbitrary set of additional MAF columns (separated with a period e.g `ASCN.total_copy_number`, `ASCN.minor_copy_number`). All columns with a prefix matching a namespace specified in the metafile will be imported; columns with an unspecified namespace will be ignored. If no additional columns beyond the required set need to be imported, the field should be left blank. 

### Example
An example metadata file would be:
```
cancer_study_identifier: brca_tcga_pub
genetic_alteration_type: MUTATION_EXTENDED
datatype: MAF
stable_id: mutations
show_profile_in_analysis_tab: true
profile_description: Mutation data from whole exome sequencing.
profile_name: Mutations
data_filename: data_mutations.txt
namespaces: ASCN
```

### Data file
The cBioPortal mutation data file extends the [Mutation Annotation Format](https://docs.gdc.cancer.gov/Data/File_Formats/MAF_Format/) (MAF) created as part of The Cancer Genome Atlas (TCGA) project, by adding *extra annotations* to each mutation record. This section describes:
1. How to create the cBioPortal mutation data file with a minimal MAF file using the [Genome Nexus Annotation Pipeline](https://github.com/genome-nexus/genome-nexus-annotation-pipeline).
2. The description of the cBioPortal mutation data file. You can also get the cBioPortal mutation data file from vcf using: [vcf2maf](https://github.com/mskcc/vcf2maf).

### Create the cBioPortal mutation data file with Genome Nexus with a minimal MAF file
#### Minimal MAF file format
A minimal mutation annotations file can contain just the five genomic change columns plus one sample identifier column. From this minimal MAF, it is possible to create the cBioPortal mutation data file by running it through the [Genome Nexus Annotation Pipeline](https://github.com/genome-nexus/genome-nexus-annotation-pipeline).
1. **Chromosome (Required)**:  A chromosome number, e.g., "7".
2. **Start_Position (Required)**: Start position of event.
3. **End_Position (Required)**: End position of event.
4. **Reference_Allele (Required)**: The plus strand reference allele at this position.
5. **Tumor_Seq_Allele2 (Required)**: Primary data genotype.
6. **Tumor_Sample_Barcode (Required)**: This is the sample ID. Either a TCGA barcode (patient identifier will be extracted), or for non-TCGA data, a literal SAMPLE_ID as listed in the clinical data file.

In addition to the above columns, it is recommended to have the read counts to calculate variant allele frequencies:

7. **t_alt_count (Optional, but recommended)**: Variant allele count (tumor). 
8. **t_ref_count (Optional, but recommended)**: Reference allele count (tumor).

The following extra annotation columns are important for making sure mutation specific UI functionality works well in the portal:

9. **Protein_position (Optional)**: (annotation column) Required to initialize the 3D viewer in [mutations view](https://www.cbioportal.org/index.do?cancer_study_list=brca_tcga_pub&cancer_study_id=brca_tcga_pub&genetic_profile_ids_PROFILE_MUTATION_EXTENDED=brca_tcga_pub_mutations&genetic_profile_ids_PROFILE_COPY_NUMBER_ALTERATION=brca_tcga_pub_gistic&genetic_profile_ids_PROFILE_MRNA_EXPRESSION=brca_tcga_pub_mrna_median_Zscores&Z_SCORE_THRESHOLD=2.0&RPPA_SCORE_THRESHOLD=2.0&data_priority=0&case_set_id=brca_tcga_pub_complete&case_ids=&patient_case_select=sample&gene_set_choice=prostate-cancer%3A-ar-signaling-%2810-genes%29&gene_list=TP53&clinical_param_selection=null&tab_index=tab_visualize&Action=Submit#mutation_details)
10. **SWISSPROT (Optional)**: (annotation column) UniProtKB/SWISS-PROT name (formerly called ID) or accession code depending on the value of the `swissprot_identifier` metadatum, e.g. O11H1_HUMAN or Q8NG94. Is not required, but not having it may result in inconsistent PDB structure matching in [mutations view](https://www.cbioportal.org/index.do?cancer_study_list=brca_tcga_pub&cancer_study_id=brca_tcga_pub&genetic_profile_ids_PROFILE_MUTATION_EXTENDED=brca_tcga_pub_mutations&genetic_profile_ids_PROFILE_COPY_NUMBER_ALTERATION=brca_tcga_pub_gistic&genetic_profile_ids_PROFILE_MRNA_EXPRESSION=brca_tcga_pub_mrna_median_Zscores&Z_SCORE_THRESHOLD=2.0&RPPA_SCORE_THRESHOLD=2.0&data_priority=0&case_set_id=brca_tcga_pub_complete&case_ids=&patient_case_select=sample&gene_set_choice=prostate-cancer%3A-ar-signaling-%2810-genes%29&gene_list=TP53&clinical_param_selection=null&tab_index=tab_visualize&Action=Submit#mutation_details).

### Creating the cBioPortal mutation data file
Once you have a minimal MAF you can run it through the [Genome Nexus Annotation Pipeline](https://github.com/genome-nexus/genome-nexus-annotation-pipeline).
This tool runs annotates variants against the [Genome Nexus Server](https://genomenexus.org), which in turn leverages Ensembl Variant Effect Predictor (VEP) and selects a single effect per variant. Protein identifiers will be mapped to UniProt canonical isoforms (see also [this mapping file](https://github.com/genome-nexus/genome-nexus-importer/blob/master/data/grch37_ensembl92/export/ensembl_biomart_canonical_transcripts_per_hgnc.txt)).

### cBioPortal mutation data file format
The cBioPortal mutation data file format recognized by the portal has:
* 32 columns from the [TCGA MAF format](https://docs.gdc.cancer.gov/Data/File_Formats/MAF_Format/).
* 1 column with the amino acid change.
* 4 columns with information on reference and variant allele counts in tumor and normal samples. 

1. **Hugo_Symbol (Required)**: A [HUGO](https://www.genenames.org/) gene symbol.
2. **Entrez_Gene_Id (Optional, but recommended)**: A [Entrez Gene](https://www.ncbi.nlm.nih.gov/gene) identifier.
3. **Center (Optional)**: The sequencing center.
4. **NCBI_Build (Required)<sup>1</sup>**: The Genome Reference Consortium Build is used by a variant calling software. It must be "GRCh37" or "GRCh38" for a human, and "GRCm38" for a mouse.
5. **Chromosome (Required)**: A chromosome number, e.g., "7".
6. **Start_Position (Optional, but recommended for additional features such as [Cancer Hotspots annotations](https://www.cancerhotspots.org/))**: Start position of event.
7. **End_Position (Optional, but recommended for additional features such as [Cancer Hotspots annotations](https://www.cancerhotspots.org/))**: End position of event.
8. **Strand (Optional)**: We assume that the mutation is reported for the + strand.
9. **Variant_Classification (Required)**: Translational effect of variant allele, e.g. Missense_Mutation, Silent, etc.
10. **Variant_Type <sup>1</sup>(Optional)**: Variant Type, e.g. SNP, DNP, etc.
11. **Reference_Allele (Required)**: The plus strand reference allele at this position.
12. **Tumor_Seq_Allele1 (Optional)**: Primary data genotype.
13. **Tumor_Seq_Allele2 (Required)**: Primary data genotype.
14. **dbSNP_RS<sup>1</sup> (Optional)**: Latest dbSNP rs ID.
15. **dbSNP_Val_Status<sup>1</sup> (Optional)**: dbSNP validation status.
16. **Tumor_Sample_Barcode (Required)**: This is the sample ID. Either a TCGA barcode (patient identifier will be extracted), or for non-TCGA data, a literal SAMPLE_ID as listed in the clinical data file.
17. **Matched_Norm_Sample_Barcode<sup>1</sup> (Optional)**: The sample ID for the matched normal sample.
18. **Match_Norm_Seq_Allele1 (Optional)**: Primary data.
19. **Match_Norm_Seq_Allele2 (Optional)**: Primary data.
20. **Tumor_Validation_Allele1 (Optional)**: Secondary data from orthogonal technology.
21. **Tumor_Validation_Allele2 (Optional)**: Secondary data from orthogonal technology.
22. **Match_Norm_Validation_Allele1<sup>1</sup> (Optional)**: Secondary data from orthogonal technology.
23. **Match_Norm_Validation_Allele2<sup>1</sup> (Optional)**: Secondary data from orthogonal technology.
24. **Verification_Status<sup>1</sup> (Optional)**: Second pass results from independent attempt using same methods as primary data source. "Verified", "Unknown" or "NA".
25. **Validation_Status (Optional)**: Second pass results from orthogonal technology. "Valid", "Invalid", "Untested", "Inconclusive", "Redacted", "Unknown" or "NA".
26. **Mutation_Status (Optional)**: "Somatic" or "Germline" are supported by the UI in Mutations tab. "None", "LOH" and "Wildtype" will not be loaded. Other values will be displayed as text.
27. **Sequencing_Phase<sup>1</sup> (Optional)**: Indicates current sequencing phase.
28. **Sequence_Source<sup>1</sup> (Optional)**: Molecular assay type used to produce the analytes used for sequencing.
29. **Validation_Method<sup>1</sup> (Optional)**: The assay platforms used for the validation call.
30. **Score<sup>1</sup> (Optional)**: Not used.
31. **BAM_File<sup>1</sup> (Optional)**: Not used.
32. **Sequencer<sup>1</sup> (Optional)**: Instrument used to produce primary data.
33. **HGVSp_Short (Required)**: Amino Acid Change, e.g. p.V600E.
34. **t_alt_count (Optional)**: Variant allele count (tumor). 
35. **t_ref_count (Optional)**: Reference allele count (tumor).
36. **n_alt_count (Optional)**: Variant allele count (normal).
37. **n_ref_count (Optional)**: Reference allele count (normal).

<sup>**1**</sup> These columns are currently not shown in the Mutation tab and Patient view.

### Custom driver annotations
It is possible to manually add columns for defining custom driver annotations. These annotations can be used to complement or replace default driver annotation resources OncoKB and HotSpots.

38. **cbp_driver (Optional)**: "Putative_Driver", "Putative_Passenger", "Unknown", "NA" or "" (empty value). This field must be present if the cbp_driver_annotation is also present in the MAF file. 
39. **cbp_driver_annotation (Optional)**: Description field for the cbp_driver value (limited to 80 characters). This field must be present if the cbp_driver is also present in the MAF file. This field is free text. Example values for this field are: "Pathogenic" or "VUS".
40. **cbp_driver_tiers (Optional)**: Free label/category that marks the mutation as a putative driver such as "Driver", "Highly actionable", "Potential drug target". . This field must be present if the cbp_driver_tiers_annotation is also present in the MAF file. In the OncoPrint view's Mutation Color dropdown menu, these tiers are ordered alphabetically. This field is free text and limited to 20 characters. For mutations without a custom annotation, leave the field blank or type "NA".
41. **cbp_driver_tiers_annotation (Optional)**: Description field for the cbp_driver_tiers value (limited to 80 characters). This field must be present if the cbp_driver_tiers is also present in the MAF file. This field can not be present when the cbp_driver_tiers field is not present. 

The `cbp_driver` column flags the mutation as either driver or passenger. In cBioPortal, passenger mutations are also known as variants of unknown significance (VUS). The `cbp_driver_tiers` column assigns an annotation tier to the mutation, such as "Driver", "Highly actionable" or "Potential drug target". When a tier is selected, mutations with that annotation are highlighted as driver. Both types of custom annotations contain a second column with the suffix `_annotation`, to add a description. This is displayed in the tooltip that appears when hovering over the sample's custom annotation icon in the OncoPrint view.

You can learn more about configuring these annotations in the [application.properties documentation](/deployment/customization/application.properties-Reference.md#custom-annotation-of-driver-and-passenger-mutations). When properly configured, the customized annotations appear in the "Mutation Color" menu of the OncoPrint view: \
![screenshot mutation color menu](/images/screenshot-mutation-color-menu.png) 

### Adding your own mutation annotation columns
Additional mutation annotation columns can be added to the cBioPortal mutation data file. In this way, the portal will
parse and store your own MAF fields in the database. For example, mutation data that you find on cBioPortal.org comes
from MAF files that have been further enriched with information
from [mutationassessor.org](https://mutationassessor.org/), which leads to a "Mutation Assessor" column in
the [mutation table](https://www.cbioportal.org/index.do?cancer_study_list=acc_tcga&cancer_study_id=acc_tcga&genetic_profile_ids_PROFILE_MUTATION_EXTENDED=acc_tcga_mutations&Z_SCORE_THRESHOLD=2.0&RPPA_SCORE_THRESHOLD=2.0&data_priority=0&case_set_id=acc_tcga_sequenced&case_ids=&patient_case_select=sample&gene_set_choice=user-defined-list&gene_list=ZFPM1&clinical_param_selection=null&tab_index=tab_visualize&Action=Submit).

See [Custom namespace columns](#custom-namespace-columns) for more information on adding custom columns to data files.

### Allele specific copy number (ASCN) annotations
Allele specific copy number (ASCN) annotation is also supported and may be added using namespaces, described [here](#adding-mutation-annotation-columns-through-namespaces). If ASCN data is present in the cBioPortal mutation data file, the deployed cBioPortal instance will display additional columns in the mutation table showing ASCN data.

**The ASCN columns below are optional by default. If `ascn` is a defined namespace in `meta_mutations_extended.txt`, then these columns are ALL required.**

42. **ASCN.ASCN_METHOD (Optional)**: Method used to obtain ASCN data e.g "FACETS".
43. **ASCN.CCF_EXPECTED_COPIES (Optional)**: Cancer-cell fraction if mutation exists on major allele. Displayed as a plain number for single-sample patients or as a bar chart for multi-sample patients in the patient view mutation table.
44. **ASCN.CCF_EXPECTED_COPIES_UPPER (Optional)**: Upper error for CCF estimate.
45. **ASCN.EXPECTED_ALT_COPIES (Optional)**: Estimated number of copies harboring mutant allele.
46. **ASCN.CLONAL (Optional)**: "Clonal", "Subclonal", or "Indeterminate". Displayed as a "Clonal" boolean column in the patient view mutation table, where only "Clonal" values are indicated with a dot.
47. **ASCN.TOTAL_COPY_NUMBER (Optional)**: Total copy number of the gene.
48. **ASCN.MINOR_COPY_NUMBER (Optional)**: Copy number of the minor allele.
49. **ASCN.ASCN_INTEGER_COPY_NUMER (Optional)**: Absolute integer copy-number estimate.

### Example cBioPortal mutation data file
An example cBioPortal mutation data file can be found in the cBioPortal test study [study_es_0](https://github.com/cBioPortal/cbioportal/blob/master/test/test_data/study_es_0/data_mutations_extended.maf).

### Filtered mutations
A special case for **Entrez_Gene_Id=0** and **Hugo_Symbol=Unknown**: when this combination is given, the record is parsed in the same way as **Variant_Classification=IGR** and therefore filtered out.