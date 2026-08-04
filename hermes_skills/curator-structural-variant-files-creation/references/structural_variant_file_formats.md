## Structural Variant Data Section From File Format cBioPortal Doc

### Structural Variants:

Structural variants (SVs) are a type of genetic variation that involves alterations in the structure of DNA molecules, including larger-scale changes in the genome. These changes can be associated with the addition, deletion, inversion, duplication, or translocation of DNA segments. Structural variants can have significant effects on an individual's genetics, and when they occur in specific regions, they can play a role in the development and progression of cancer. 

When preparing structural variant data for cBioPortal, it is important to follow the data format and metadata:

- Data Format (`data_sv.txt`): A structural variant data file is a tab-delimited file with one structural variant per row. See [Required and strongly recommended columns](#required-and-strongly-recommended-columns) for the minimum columns and identifiers required for each row.

- Metadata (`meta_sv.txt`): Defines the cBioPortal structural variant molecular profile and identifies the associated `data_sv.txt` file.

- The cBioPortal can load all kinds of structural variant data but at the moment only a subset of them, fusions, are displayed.

### Meta file
The structural variant metadata file should contain the following fields:

1. **cancer_study_identifier**: same value as specified in `meta_study.txt` file
2. **genetic_alteration_type**: STRUCTURAL_VARIANT
3. **datatype**: SV
4. **stable_id**: structural_variants
5. **show_profile_in_analysis_tab**: true.
6. **profile_name**: A name for the fusion data, e.g., "Structural Variants".
7. **profile_description**: A description of the structural variant data.
8. **data_filename**: your datafile (e.g. data_sv.txt)
9. **gene_panel (Optional)**:  gene panel stable id
10. **namespaces (Optional)**: Comma-delimited list of namespace prefixes used by custom columns in `data_sv.txt`. Include this field whenever custom namespace columns are present.


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
namespaces: CALLER,SOURCE
```

### Data file

A structural variant data file is a tab-delimited file with one structural variant per row. For each structural variant (row) in the data file, you can have the following tab-delimited values:

- **Sample_Id**
  - Example Values: Sample_1
  - Comments: As defined in the clinical sample file.

- **SV_Status**
  - Example Values: SOMATIC
  - Allowed Values: SOMATIC or GERMLINE

- **Site1_Hugo_Symbol**
  - Example Values: TMPRSS2
  - Comments: [HUGO](http://www.genenames.org/) gene symbol of gene 1. One might call this the left site(3’) as well.

- **Site1_Ensembl_Transcript_Id**
  - Example Values: ENST00000398585
  - Comments: Ensembl transcript ID of gene 1.

- **Site1_Entrez_Gene_Id**
  - Example Values: 7113
  - Comments: [Entrez Gene](http://www.ncbi.nlm.nih.gov/gene) identifier of gene 1.

- **Site1_Region_Number**
  - Example Values: 2
  - Comments: Number of Site 1 region e.g. exon 2.

- **Site1_Region**
  - Example Values: Exon
  - Allowed Values: 5_Prime_UTR,3_Prime_UTR,Promoter,Exon,Intron
  - Comments: We advise using one of these {5_Prime_UTR,3_Prime_UTR,Promoter,Exon,Intron}, but it is a free text for cBioPortal.

- **Site1_Chromosome**
  - Example Values: 21
  - Comments: Chromosome of Gene 1.

- **Site1_Contig**
  - Example Values: q22.3
  - Comments: The contig of Site 1.

- **Site1_Position**
  - Example Values: 42874110
  - Comments: Genomic position of breakpoint of Gene 1.

- **Site1_Description**
  - Example Values: Intron of TMPRSS2(-): 511bp before exon 3
  - Comments: Description of this event at site 2. This could be the location of the 2nd breakpoint in case of a fusion event.

- **Site2_Hugo_Symbol**
  - Example Values: ERG
  - Comments: [HUGO](http://www.genenames.org/) gene symbol of gene 2.One might call this the right site(5’) as well.

- **Site2_Ensembl_Transcript_Id**
  - Example Values: ENST00000288319
  - Comments: Ensembl transcript ID of gene 2.

- **Site2_Entrez_Gene_Id**
  - Example Values: 2078
  - Comments: [Entrez Gene](http://www.ncbi.nlm.nih.gov/gene) identifier of gene 2.

- **Site2_Region_Number**
  - Example Values: 4
  - Comments: Number of Site 2 region e.g. exon 4.

- **Site2_Region**
  - Example Values: EXON
  - Allowed Values: 5_PRIME_UTR,3_PRIME_UTR,PROMOTER,EXON,INTRON
  - Comments: We advise using one of these {5_PRIME_UTR,3_PRIME_UTR,PROMOTER,EXON,INTRON}, but it is a free text  for cBioPortal.

- **Site2_Chromosome**
  - Example Values: 21
  - Comments: Chromosome of Gene 2.

- **Site2_Contig**
  - Example Values: q22.2
  - Comments: The contig of Site 2.

- **Site2_Position**
  - Example Values: 39842043
  - Comments: Genomic position of breakpoint of Gene 2.

- **Site2_Description**
  - Example Values: Intron of ERG(-): 6Kb after exon 1
  - Comments: Description of this event at site 1. This could be the location of 1st breakpoint in case of a fusion event

- **Site2_Effect_On_Frame**
  - Example Values: Out-of-frame
  - Allowed Values: In_frame, Out-of-frame,Frameshift
  - Comments: The effect on frame reading in gene 2. Frame_Shift or InFrame,but it is a free text.

- **NCBI_Build**
  - Example Values: GRCh37
  - Allowed Values: GRCh37,GRCh38
  - Comments: The NCBI assembly. Only one assembly per study can be used, see[study metadata](https://docs.cbioportal.org/5.1-data-loading/data-loading/file-formats#meta-file).

- **Class**
  - Example Values: DELETION
  - Allowed Values: DELETION, DUPLICATION, INSERTION, INVERSION, TRANSLOCATION.
  - Comments: We advise using one of these terms [DELETION, DUPLICATION, INSERTION, INVERSION or TRANSLOCATION], but it is free text.

- **Tumor_Split_Read_Count**
  - Example Values: 4
  - Comments: The number of split reads of the tumor tissue that support the call. [Tumor Split Read Count is the same as “Junction Reads”.]

- **Tumor_Paired_End_Read_Count**
  - Example Values: 55
  - Comments: The number of paired-end reads of the tumor tissue that support the call. [Tumor Paired End Read Count is the same as “Spanning Fragments”.]

- **Event_Info**
  - Example Values: Protein fusion: out of frame (TMPRSS2-ERG)
  - Allowed Values: Antisense fusion, Deletion within transcript: mid-exon, Duplication of 1 exon: in frame
  - Comments: Description of the event. For a fusion event, fill in Fusion. It is a free text for cBioPortal.

- **Connection_Type**
  - Example Values: 3to5
  - Allowed Values: 3to5 or 5to3 or 5to5 or 3to3
  - Comments: Which direction the connection is made (3' to 5', 5' to 3', etc)

- **Breakpoint_Type**
  - Example Values: PRECISE
  - Allowed Values: PRECISE/IMPRECISE
  - Comments: PRECISE or IMPRECISE which explain the resolution. Fill in PRECISE if the breakpoint resolution is known down to the exact base pair.

- **Annotation**
  - Example Values: TMPRSS2 (NM_001135099) - ERG (NM_001243428) fusion (TMPRSS2 exons 1-2 fused with ERG exons 4-11):(c.126+879:TMRPSS2_c.40-63033:ERGdel)
  - Allowed Values: Free Text
  - Comments: Free text description of the gene or transcript rearrangement.

- **DNA_Support**
  - Example Values: Yes
  - Allowed Values: Yes or No
  - Comments: Fusion detected from DNA sequence data, "Yes" or "No".

- **RNA_Support**
  - Example Values: Yes
  - Allowed Values: Yes or No
  - Comments: Fusion detected from RNA sequence data, "Yes" or "No".

- **SV_Length**
  - Example Values: 3032067
  - Comments: Length of the structural variant in number of bases.

- **Normal_Read_Count**
  - Example Values: 93891
  - Comments: The total number of reads of the normal tissue.

- **Tumor_Read_Count**
  - Example Values: 45556
  - Comments: The total number of reads of the tumor tissue.

- **Normal_Variant_Count**
  - Example Values: 0
  - Comments: The number of reads of the normal tissue that have the variant/allele.

- **Tumor_Variant_Count**
  - Example Values: 39
  - Comments: The number of reads of the tumor tissue that have the variant/allele.

- **Normal_Paired_End_Read_Count**
  - Example Values: 41
  - Comments: The number of paired-end reads of the normal tissue that support the call.

- **Normal_Split_Read_Count**
  - Example Values: 63
  - Comments: The number of split reads of the normal tissue that support the call.

- **Comments**
  - Any comments/free text.


## Required and strongly recommended columns
Each emitted row in `data_sv.txt` must have:

- `Sample_Id`
- `SV_Status`
- At least one of the following supported gene site identifiers:
  - `Site1_Hugo_Symbol` or `Site1_Entrez_Gene_Id`, or
  - `Site2_Hugo_Symbol` or `Site2_Entrez_Gene_Id`

The following columns are strongly recommended when supported by the source data:

- `Site1_Hugo_Symbol`
- `Site1_Entrez_Gene_Id`
- `Site1_Region_Number`
- `Site1_Region`
- `Site1_Chromosome`
- `Site1_Contig`
- `Site1_Position`

 For the stuctural variant tab visualization (still in development) one needs to provide those field as well as `Site1_Ensembl_Transcript_Id`, `Site2_Ensembl_Transcript_Id`, `Site1_Region` and `Site2_Region`. Some of the other columns are shown at several other pages on the website. The `Class`, `Annotation` and `Event_Info` columns are shown prominently on several locations.


### Adding custom structural variant columns
Do not discard meaningful, source-supported, row-level structural variant information only because it cannot be represented by one of the standard cBioPortal structural variant fields, but do not copy source columns indiscriminately.

For every source column containing information about an individual structural variant:
1. Map it to a standard cBioPortal structural variant field when a reliable mapping exists.
2. Prefer the standard field over a custom column.
3. When no suitable standard field exists, preserve the information as a custom namespace column.
4. Do not omit a meaningful source value merely because it is available for only a subset of the structural variant rows.
5. Choose short, stable, and specific namespace names. Prefer the assay, caller,
or annotation domain over generic prefixes when that information is known. The column name of the source data may be a good option.

Custom column names must use the following format:
```text
<NAMESPACE>.<attribute>
```

For example:
```text
CALLER.name
CALLER.score
CALLER.filter
ASSAY.fusion_confidence
SOURCE.original_annotation
```

Every namespace prefix used by a custom column in `data_sv.txt` must also be
declared in the `namespaces` field of `meta_sv.txt`.


For example:
```text
namespaces: CALLER,ASSAY,SOURCE
```

A custom column whose namespace is not declared in `meta_sv.txt` will be ignored during import in cBioPortal.

#### Column-selection rules
Retain a source-specific field as a custom namespace column when:
* it describes or supports an individual structural variant call;
* its meaning can be established from the source file, its documentation, headers, comments, notes, or associated publication;
* it provides biological, technical, quality-control, evidentiary, assay, caller, filtering, confidence, or provenance information;
* no standard cBioPortal structural variant field represents the same information adequately.

Examples of potentially valuable custom information include:
* variant caller name or version;
* caller-specific confidence scores;
* source filtering status;
* assay-specific classification;
* supporting evidence not represented by a standard read-count field;
* original source annotation;
* validation method;
* source row or record identifier;
* caller-specific quality metrics.

Do not retain columns that contain only:
* empty values;
* spreadsheet formatting artifacts;
* unnamed columns;
* temporary formulas or intermediate calculations;
* unexplained codes whose meaning cannot be determined;
* information unrelated to the individual structural variant;
* exact duplicates of a retained standard or custom field.

Preserve the original meaning and granularity of custom values. Do not infer, reinterpret, calculate, or fabricate values solely to populate a custom column.
Leave a custom field empty for rows where the source does not provide a supported value.

## Validator-compatible required structure
- The `data_sv.txt` header must contain `Sample_Id` and `SV_Status`.
- The header must also contain at least one Site 1 gene identifier column:
`Site1_Hugo_Symbol` or `Site1_Entrez_Gene_Id`.
- The header must contain at least one Site 2 gene identifier column:
`Site2_Hugo_Symbol` or `Site2_Entrez_Gene_Id`.
- These are header requirements. Both sites do not need to contain a value in
every row.
- Every emitted row must contain `Sample_Id`, a source-supported `SV_Status`,
and at least one source-supported gene identifier across Site 1 or Site 2.
- When the source supports only one site, include an empty identifier column for
the other site to satisfy the bundled validator. Do not fabricate a gene value.
- Populate all other optional columns only when supported by the source.
