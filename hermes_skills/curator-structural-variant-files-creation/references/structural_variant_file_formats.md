## Structural Variant Data Section From File Format cBioPortal Doc

### Structural Variants:

Structural variants (SVs) are a type of genetic variation that involves alterations in the structure of DNA molecules, including larger-scale changes in the genome. These changes can be associated with the addition, deletion, inversion, duplication, or translocation of DNA segments. Structural variants can have significant effects on an individual's genetics, and when they occur in specific regions, they can play a role in the development and progression of cancer. 

When preparing structural variant data for cBioPortal, it is important to follow the data format and metadata:
- Data Format: A structural variant data file is a tab-delimited file with one structural variant per row. In order to create a minimum SV file we need a minimum of Site1_Hugo_Symbol, Site2_Hugo_Symbol, Sample_Id, SV_Status (Somatic vs Germline) and Event_Info column. Convert the data to the format as listed in te cBioPortal  file-formats. 
- Meta Data: Add a metadata file including publication details, experimental methodologies, and any additional relevant information, will be annotated along with the curated data to provide context.

- The cBioPortal can load all kinds of structural variant data but at the moment only a subset of them, fusions, are displayed.

### Meta file
The structural variant metadata file should contain the following fields:

1. **cancer_study_identifier**: same value as specified in [study meta file](#cancer-study)
2. **genetic_alteration_type**: STRUCTURAL_VARIANT
3. **datatype**: SV
4. **stable_id**: structural_variants
5. **show_profile_in_analysis_tab**: true.
6. **profile_name**: A name for the fusion data, e.g., "Structural Variants".
7. **profile_description**: A description of the structural variant data.
8. **data_filename**: your datafile (e.g. data_sv.txt)
9. **gene_panel (Optional)**:  gene panel stable id

An example metadata file would be:

```
cancer_study_identifier: msk_impact_2017
genetic_alteration_type: STRUCTURAL_VARIANT
datatype: SV
stable_id: structural_variants
show_profile_in_analysis_tab: true
profile_name: Structural variants
profile_description: Structural Variant Data for mskimpact2017
data_filename: data_sv.txt
```

### Data file

A structural variant data file is a tab-delimited file with one structural variant per row.  For each structural variant (row) in the data file, the following tab-delimited values are required:

| Field                        | Example Values         | Allowed  Values       | Comments |
| -- | -- | -- | -- |
| Sample_Id (Required)         | Sample_1      |  | As defined in the clinical sample file. |
| SV_Status (Required)         | SOMATIC | SOMATIC or GERMLINE |  |
| Site1_Hugo_Symbol            | TMPRSS2 |   | [HUGO](http://www.genenames.org/) gene symbol of gene 1. One might call this the left site(3’) as well. (strongly recommended field) |
| Site1_Ensembl_Transcript_Id  | ENST00000398585  |  | Ensembl transcript ID of gene 1. |
| Site1_Entrez_Gene_Id         | 7113 |  | [Entrez Gene](http://www.ncbi.nlm.nih.gov/gene) identifier of gene 1. (strongly recommended field) |
| Site1_Region_Number          | 2 |  | Number of Site 1 region e.g. exon 2.(strongly recommended field) |
| Site1_Region                 | Exon | 5_Prime_UTR,3_Prime_UTR,Promoter,Exon,Intron | We advise using one of these {5_Prime_UTR,3_Prime_UTR,Promoter,Exon,Intron},but it is a free text. (strongly recommended field) |
| Site1_Chromosome             | 21 |  | Chromosome of Gene 1.(strongly recommended field) |
| Site1_Contig                 | q22.3 |  | The contig of Site 1.(strongly recommended field) |
| Site1_Position               | 42874110 |  | Genomic position of breakpoint of Gene 1.(strongly recommended field) |
| Site1_Description            | Intron of TMPRSS2(-): 511bp before exon 3  |  | Description of this event at site 2. This could be the location of the 2nd breakpoint in case of a fusion event. |
| Site2_Hugo_Symbol            | ERG |  | [HUGO](http://www.genenames.org/) gene symbol of gene 2.One might call this the right site(5’) as well. |
| Site2_Ensembl_Transcript_Id  | ENST00000288319 |   | Ensembl transcript ID of gene 2.|
| Site2_Entrez_Gene_Id         | 2078 |  | [Entrez Gene](http://www.ncbi.nlm.nih.gov/gene) identifier of gene 2. |
| Site2_Region_Number          | 4 |  | Number of Site 2 region e.g. exon 4.|
| Site2_Region                 | EXON | 5_PRIME_UTR,3_PRIME_UTR,PROMOTER,EXON,INTRON | We advise using one of these {5_PRIME_UTR,3_PRIME_UTR,PROMOTER,EXON,INTRON},but it is a free text. |
| Site2_Chromosome             | 21 |  | Chromosome of Gene 2.|
| Site2_Contig                 | q22.2 |  | The contig of Site 2.|
| Site2_Position               | 39842043 |  | Genomic position of breakpoint of Gene 2. |
| Site2_Description            | Intron of ERG(-): 6Kb after exon 1 |  | Description of this event at site 1. This could be the location of 1st breakpoint in case of a fusion event |
| Site2_Effect_On_Frame        | Out-of-frame | In_frame, Out-of-frame,Frameshift  | The effect on frame reading in gene 2. Frame_Shift or InFrame,but it is a free text. |
| NCBI_Build                   | GRCh37 | GRCh37,GRCh38 | The NCBI assembly. Only one assembly per study can be used, see[ study metadata](https://docs.cbioportal.org/5.1-data-loading/data-loading/file-formats#meta-file). |
| Class                        | Deletion | Deletion,Duplication,Insertion,Inversion,Translocation. | We advise using one of these terms [DELETION, DUPLICATION, INSERTION, INVERSION or TRANSLOCATION], but it is free text. |
| Tumor_Split_Read_Count       | 4 |  | The number of split reads of the tumor tissue that support the call.[Tumor Split Read Count is the same as “Junction Reads”.] |
| Tumor_Paired_End_Read_Count  | 55 |  | The number of paired-end reads of the tumor tissue that support the call. [Tumor Paired End Read Count is the same as “Spanning Fragments”.] |
| Event_Info                   | Protein fusion: out of frame (TMPRSS2-ERG) | Antisense fusion, Deletion within transcript: mid-exon, Duplication of 1 exon: in frame | Description of the event. For a fusion event, fill in Fusion. It is a free text. |
| Connection_Type              | 3to5 | 3to5 or 5to3 or 5to5 or 3to3 | Which direction the connection is made (3' to 5', 5' to 3', etc) |
| Breakpoint_Type              | PRECISE  | PRECISE/IMPRECISE  | PRECISE or IMPRECISE which explain the resolution. Fill in PRECISE if the breakpoint resolution is known down to the exact base pair. |
| Annotation                   | TMPRSS2 (NM_001135099) - ERG (NM_001243428) fusion (TMPRSS2 exons 1-2 fused with ERG exons 4-11):(c.126+879:TMRPSS2_c.40-63033:ERGdel) | Free Text                                                    | Free text description of the gene or transcript rearrangement. |
| DNA_Support                  | Yes  | Yes or No  | Fusion detected from DNA sequence data, "Yes" or "No".|
| RNA_Support                  |   | Yes or No | Fusion detected from DNA sequence data, "Yes" or "No".|
| SV_Length                    | 3032067 |  | Length of the structural variant in number of bases.|
| Normal_Read_Count            | 93891 |  | The total number of reads of the normal tissue.|
| Tumor_Read_Count             | 45556 |  | The total number of reads of the tumor tissue. |
| Normal_Variant_Count         | 0 |  | The number of reads of the normal tissue that have the variant/allele. |
| Tumor_Variant_Count          | 39 |  | The number of reads of the tumor tissue that have the variant/allele. |
| Normal_Paired_End_Read_Count | 41 |  | The number of paired-end reads of the normal tissue that support the call.|
| Normal_Split_Read_Count      | 63 |  | The number of split reads of the normal tissue that support the call. |
| Comments                     |  |  | Any comments/free text.|

For an example see [datahub](https://github.com/cBioPortal/datahub/blob/master/public/msk_impact_2017/data_sv.txt). For an example see [datahub](https://github.com/cBioPortal/datahub/blob/master/public/msk_impact_2017/data_sv.txt). At a minimum `Sample_Id`, either `Site1_Hugo_Symbol`/ `Site1_Entrez_Gene_Id` or  `Site2_Hugo_Symbol`/ `Site2_Entrez_Gene_Id` and `SV_Status` are required. For the stuctural variant tab visualization (still in development) one needs to provide those field as well as `Site1_Ensembl_Transcript_Id`, `Site2_Ensembl_Transcript_Id`, `Site1_Region` and `Site2_Region`. Some of the other columns are shown at several other pages on the website. The `Class`, `Annotation` and `Event_Info` columns are shown prominently on several locations.
**Note**: We strongly recommend all the data providers to submit genomic locations  in addition to required fields for future visualization features. 

### Adding your own structural variant columns
Additional mutation annotation columns can be added to the structural variant data file. In this way, the portal will
parse and store your own structural variant fields in the database.
