# Discrete Copy Number Data
The discrete copy number data file contain values that would be derived from copy-number analysis algorithms like [GISTIC 2.0](https://www.ncbi.nlm.nih.gov/sites/entrez?term=18077431) or [RAE](https://www.ncbi.nlm.nih.gov/sites/entrez?term=18784837). GISTIC 2.0 can be [installed](https://www.broadinstitute.org/cgi-bin/cancer/publications/pub_paper.cgi?mode=view&paper_id=216&p=t) or run online using the GISTIC 2.0 module on [GenePattern](https://cloud.genepattern.org). For some help on using GISTIC 2.0, check the [Data Loading: Tips and Best Practices](Data-Loading-Tips-and-Best-Practices.md) page. When loading case list data, the `_cna` case list is required. See the [case list section](#case-lists).

## Wide vs Long format
For CNA data two formats are supported: the wide, and the long format:
- **Wide format**: a matrix, where each row is a gene, and each column is a sample
- **Long format**: not a matrix, each row is a gene-sample combination; this makes the file longer

## Wide format

### Meta file 
The meta file is comprised of the following fields:

1. **cancer_study_identifier**: same value as specified in [study meta file](#cancer-study)
2. **genetic_alteration_type**: COPY_NUMBER_ALTERATION
3. **datatype**: `DISCRETE`
4. **stable_id**: gistic, cna, cna_rae or cna_consensus
5. **show_profile_in_analysis_tab**: true
6. **profile_name**: A name for the discrete copy number data, e.g., "Putative copy-number alterations from GISTIC"
7. **profile_description**: A description of the copy number data, e.g., "Putative copy-number from GISTIC 2.0. Values: -2 = homozygous deletion; -1 = hemizygous deletion; 0 = neutral / no change; 1 = gain; 2 = high level amplification."
8. **data_filename**: your datafile
9. **gene_panel (Optional)**:  gene panel stable id
10. **pd_annotations_filename (Optional)**: name of [custom driver annotations file](File-Formats.md#custom-driver-annotations-file)

#### Example of meta file
An example metadata file could be named meta_cna.txt and its contents could be:
```
cancer_study_identifier: brca_tcga_pub
genetic_alteration_type: COPY_NUMBER_ALTERATION
datatype: DISCRETE
stable_id: gistic
show_profile_in_analysis_tab: true
profile_name: Putative copy-number alterations from GISTIC
profile_description: Putative copy-number from GISTIC 2.0. Values: -2 = homozygous deletion; -1 = hemizygous deletion; 0 = neutral / no change; 1 = gain; 2 = high level amplification.
data_filename: data_cna.txt
pd_annotations_filename: data_cna_pd_annotations.txt
```

### Data file
For each gene (row) in the data file, the following columns are required in the order specified:

One or both of:
- ***Hugo_Symbol***: A [HUGO](https://www.genenames.org/) gene symbol.
- ***Entrez_Gene_Id***: A [Entrez Gene](https://www.ncbi.nlm.nih.gov/gene) identifier.

And:
- An additional column for each sample in the dataset using the sample id as the column header.

For each gene-sample combination, a copy number level is specified:
- "-2" is a deep loss, possibly a homozygous deletion
- "-1" is a single-copy loss (heterozygous deletion)
- "0" is diploid
- "1" indicates a low-level gain
- "2" is a high-level amplification.

#### Example of data file
An example data file which includes the required column header would look like:
```
Hugo_Symbol<TAB>Entrez_Gene_Id<TAB>SAMPLE_ID_1<TAB>SAMPLE_ID_2<TAB>...
ACAP3<TAB>116983<TAB>0<TAB>-1<TAB>...
AGRN<TAB>375790<TAB>2<TAB>0<TAB>...
...
...
```

## Long format

### Meta file 
The meta file of **wide format** is comprised of the following fields:

1. **cancer_study_identifier**: same value as specified in [study meta file](#cancer-study)
2. **genetic_alteration_type**: COPY_NUMBER_ALTERATION
3. **datatype**: `DISCRETE_LONG`
   Note: It will end up as datatype `DISCRETE` in the database, because the LONG data format is only relevant while importing. 
4. **stable_id**: gistic, cna, cna_rae or cna_consensus
5. **show_profile_in_analysis_tab**: true
6. **profile_name**: A name for the discrete copy number data, e.g., "Putative copy-number alterations from GISTIC"
7. **profile_description**: A description of the copy number data, e.g., "Putative copy-number from GISTIC 2.0. Values: -2 = homozygous deletion; -1 = hemizygous deletion; 0 = neutral / no change; 1 = gain; 2 = high level amplification."
8. **data_filename**: your datafile
9. **gene_panel (Optional)**:  gene panel stable id
10. **namespaces (Optional)**: Comma-delimited list of `namespaces` to import. 

#### Example of meta file
An example metadata file could be named meta_cna.txt and its contents could be:
```
cancer_study_identifier: brca_tcga_pub
genetic_alteration_type: COPY_NUMBER_ALTERATION
datatype: DISCRETE_LONG
stable_id: gistic
show_profile_in_analysis_tab: true
profile_name: Putative copy-number alterations from GISTIC
profile_description: Putative copy-number from GISTIC 2.0. Values: -2 = homozygous deletion; -1 = hemizygous deletion; 0 = neutral / no change; 1 = gain; 2 = high level amplification.
data_filename: data_cna.txt
namespaces: MyNamespace,MyNamespace2
```

### Data file
Each row contains a row-sample combination. Custom driver annotations are added as columns to the data file, just like custom namespace columns.

#### Example of data file
An example data file which includes the required column header would look like:
```
Hugo_Symbol	Entrez_Gene_Id	Sample_Id	Value	cbp_driver	cbp_driver_annotation	cbp_driver_tiers	cbp_driver_tiers_annotation	MyNamespace.column1
ACAP3	116983	TCGA-A2-A04U-01	2	Putative_Passenger	Test passenger	Class 2	Class annotation	value1
...
```

### Adding your own discrete copy number columns
Additional columns can be added to the discrete copy number **long** data file. In this way, the portal will parse and store your own CNA fields in the database.

See [Custom namespace columns](#custom-namespace-columns) for more information on adding custom columns to data files.

## Custom driver annotations file

Custom driver annotations can be defined for discrete copy number data. These annotations can be used to complement or replace default driver annotation resources OncoKB and HotSpots.
Custom driver annotations can be placed in a separate file that is referenced by the `pd_annotations_filename` field of the meta file. The annotation file can hold the following columns:

1. **Hugo_Symbol (Optional)**: A [HUGO](https://www.genenames.org/) gene symbol. Required when column `Entrez_Gene_Id` is not present.
2. **Entrez_Gene_Id (Optional)**: A [Entrez Gene](https://www.ncbi.nlm.nih.gov/gene) identifier. Required when column `Hugo_Symbol` is not present.
3. **SAMPLE_ID**: A sample ID. This field can only contain numbers, letters, points, underscores and hyphens.
4. **cbp_driver (Optional)**: "Putative_Driver", "Putative_Passenger", "Unknown", "NA" or "" (empty value). This field must be present if the cbp_driver_annotation is also present in the MAF file. 
5. **cbp_driver_annotation (Optional)**: Description field for the cbp_driver value (limited to 80 characters). This field must be present if the cbp_driver is also present in the MAF file. This field is free text. Example values for this field are: "Pathogenic" or "VUS".
6. **cbp_driver_tiers (Optional)**: Free label/category that marks the mutation as a putative driver such as "Driver", "Highly actionable", "Potential drug target". . This field must be present if the cbp_driver_tiers_annotation is also present in the MAF file. In the OncoPrint view's Mutation Color dropdown menu, these tiers are ordered alphabetically. This field is free text and limited to 20 characters. For mutations without a custom annotation, leave the field blank or type "NA".
7. **cbp_driver_tiers_annotation (Optional)**: Description field for the cbp_driver_tiers value (limited to 80 characters). This field must be present if the cbp_driver_tiers is also present in the MAF file. This field can not be present when the cbp_driver_tiers field is not present. 

All genes referenced in the custom driver annotation file must be present in the data file for discrete copy number alterations.

The `cbp_driver` column flags the mutation as either driver or passenger. In cBioPortal, passenger mutations are also known as variants of unknown significance (VUS). The `cbp_driver_tiers` column assigns an annotation tier to the mutation, such as "Driver", "Highly actionable" or "Potential drug target". When a tier is selected, mutations with that annotation are highlighted as driver. Both types of custom annotations contain a second column with the suffix `_annotation`, to add a description. This is displayed in the tooltip that appears when hovering over the sample's custom annotation icon in the OncoPrint view.

You can learn more about configuring these annotations in the [application.properties documentation](/deployment/customization/application.properties-Reference.md#custom-annotation-of-driver-and-passenger-mutations). When properly configured, the customized annotations appear in the "Mutation Color" menu of the OncoPrint view: \
![screenshot mutation color menu](images/screenshot-mutation-color-menu.png) 

### Example of custom driver annotations file
An example data file which includes the required column header would look like:
```
SAMPLE_ID<TAB>Hugo_Symbol<TAB>Entrez_Gene_Id<TAB>cbp_driver<TAB>cbp_driver_annotation<TAB>cbp_driver_tiers<TAB>cbp_driver_tiers_annotation<TAB>...
TCGA-BH-A0E6-01<TAB>GENEA<TAB>116983<TAB>Putative_Driver<TAB>see: PMID:12345678<TAB>Highly actionable<TAB>Per decision 01/01/2020<TAB>
TCGA-BH-A0E6-01<TAB>GENEB<TAB>375790<TAB>Putative_Passenger<TAB>see: PMID:12345678<TAB><TAB><TAB>
...
```

## GISTIC 2.0 Format
GISTIC 2.0 outputs a tabular file similarly formatted to the cBioPortal format, called `<prefix>_all_thresholded.by_genes.txt`.
In this file the gene symbol is found in the `Gene Symbol` column, while Entrez gene IDs are in the `Gene ID` or 
`Locus ID` column. Please rename `Gene Symbol` to `Hugo_Symbol` and `Gene ID` or `Locus ID` to `Entrez_Gene_Id`. The 
`Cytoband` column can be kept in the table, but note that these values are ignored in cBioPortal. cBioPortal uses 
cytoband annotations from the `map_location` column in NCBI's `Homo_sapiens.gene_info.gz` when loading genes into 
the seed database.
