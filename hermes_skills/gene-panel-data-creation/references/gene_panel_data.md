## Gene Panel Data

A gene panel is a collection of genes grouped to allow simultaneous sequencing of all the genes associated with a certain disease. The gene panel functionality specifies which genes are assayed in a panel and assigns samples and genetic profiles (such as mutation data) to a panel. This data type consists of a gene panel file, a gene panel matrix file, and a meta file.

The gene panel file itself contains a list of all the genes in a panel, where one panel can be used for multiple studies within the instance and should be loaded prior to loading a study with gene panel data. For information on the format and import process please visit the [Import-Gene-Panels](https://docs.cbioportal.org/import-gene-panels/) page.

The gene panel matrix file is used to specify which samples are sequenced on which gene panel and in which genetic profile. This is recommended for mutation and structural variant data, because MAF and structural variant file formats are unable to include samples which are sequenced but contain no called mutations, and only a single gene panel can be defined in the meta file. For other genetic profiles, columns can be added to specify their gene panel, but a property can also be added to their respective meta files, as these data files contain all profiled samples. Although the gene panel matrix functionality overlaps with the case list functionality, a case list for mutations (\_sequenced) and structural variants (\_sv) is also required. In addition, a gene panel meta file will assign all samples from that profile to the gene panel. In this case, it is not necessary to include a column for this profile in the gene panel matrix file.

The ‘[Gene Panel Data’](https://docs.cbioportal.org/file-formats/#gene-panel-data) section of the file formats further explains the contents of each of the files mentioned above.

A gene panel matrix file contains a list of samples in the first column, and an additional column for each profile in the study, where for each sample-profile combination, a gene panel should be specified. The gene panel matrix data file can be created using data present in the publication’s supplementary files. Usually, the clinical supplementary files will indicate which sample was profiled/sequenced and the paper will discuss the gene panel used.

In the portal, the gene panel table or chart can be found in the study summary page, where further analysis can be done by selecting a certain panel for cohort analysis or comparison.

Gene panel functionality can specify which genes are assayed on a panel and assign samples and genetic profiles (such as mutation data) to a panel.

To include gene panel data in your instance, the following data and/or configurations can be used:
1. **Gene panel file**: This file contains the genes on the gene panel. A panel can be used for multiple studies within the instance and should be loaded prior to loading a study with gene panel data. For information on the format and import process please visit: [Import-Gene-Panels](Import-Gene-Panels.md).
2. **Gene panel matrix file**: This file is used to specify which samples are sequenced on which gene panel in which genetic profile. This is recommended for mutation and structural variant data, because the MAF and structural variant formats are unable to include samples which are sequenced but contain no called mutations, and only a single gene panel can be defined in the meta file. For other genetic profiles, columns can be added to specify their gene panel, but a property can also be added to their respective meta file, because these data files contain all profiled samples. Although the gene panel matrix functionality overlaps with the case list functionality, a case list for mutations (`_sequenced`) and Structural variants (`_sv`) is also required.
3. **Gene panel property in meta file**: Adding the `gene_panel:` property to the meta file of data profile will assign all samples from that profile to the gene panel. In this case it is not necessary to include a column for this profile in the gene panel matrix file.

### Gene Panel Matrix file

### Columns and rows
The gene panel matrix file contains a list of samples in the first column, and an additional column for each profile in the study using the stable_id as the column header. These stable_id's should match the ones in their respective meta files, for example `mutations` for mutation data and `gistic` for discrete CNA data. Columns should be separated by tabs. Fusion events are saved in the mutation table in the cBioPortal database, so they should be included in the `mutations` column. As described above, genetic profiles other than mutation and fusion data profiles can use the `gene_panel:` meta property if all samples are profiled on the same gene panel.

### Values
For each sample-profile combination, a gene panel should be specified. Please make sure this gene panel is imported before loading the study data. When the sample is not profiled on a gene panel, or if the sample is not profiled at all, use `NA` as value. If the sample is profiled for mutations, make sure it is also in the `_sequenced` case list.

### Example
An example file would look like this:

| SAMPLE_ID   | mutations | gistic    |
| ----------- | --------- | --------- |
| SAMPLE_ID_1 | IMPACT410 | IMPACT410 |
| SAMPLE_ID_2 | IMPACT410 | IMPACT410 |
| SAMPLE_ID_3 | NA       | NA        |

### Meta file
The gene panel matrix file requires a meta file, which should contain the following fields:

1. **cancer_study_identifier**: same value as specified in [study meta file](#cancer-study)
2. **genetic_alteration_type**: GENE_PANEL_MATRIX
3. **datatype**: GENE_PANEL_MATRIX
4. **data_filename**: your datafile

Example:
```
cancer_study_identifier: msk_impact_2017
genetic_alteration_type: GENE_PANEL_MATRIX
datatype: GENE_PANEL_MATRIX
data_filename: data_gene_panel_matrix.txt
```

### Gene panel property in meta file
If all samples in a genetic profile have the same gene panel associated with them, an optional field can be specified in the meta data file of that datatype called **gene_panel:**. If this is present, all samples in this data file will be assigned to this gene panel for this specific profile.
