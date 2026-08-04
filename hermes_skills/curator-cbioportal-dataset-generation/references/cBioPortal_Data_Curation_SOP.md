# cBioPortal Data Curation Standard Operating Procedure
# Tables of Contents

1. Introduction  
   1. Data Curation Workflow  
   2. Identifying the Data Sources  
   3. Inclusion Criteria  
2. Introduction to cBioPortal File Formats and Data Abstraction  
   1. Clinical Data  
   2. Mutation Data  
   3. Copy Number Data  
   4. Segmented Data  
   5. Expression Data  
   6. Methylation Data  
   7. Structural Variant Data  
   8. Protein Level Data  
   9. Timeline/Treatment Data  
   10. Gene Panel Data  
   11. Mutational Signatures  
   12. Resource Data  
   13. Generic Assay Data  
   14. Case Lists  
   15. Study Metadata  
3. Data Standardization and Curation Tools  
   1. Genome Nexus  
   2. Oncotree  
   3. TMB  
   4. Z-scores  
   5. Validator  
4. Data Import to cBioPortal  
   1. Set up a local cBio instance  
   2. Import Study  
5. Data Quality Control  
   1. Compare the analysis to the published article  
6. Data Analysis in cBioPortal  
7. Big Picture Updates  
   1. Gene Tables

1. # Introduction

The cBioPortal for Cancer Genomics ([http://cbioportal.org](http://cbioportal.org)) is a web resource designed for exploring and analyzing multidimensional cancer genomics data. It simplifies molecular profiling data from cancer tissues and cell lines into easily understandable genetic, epigenetic, gene expression, and proteomic events. Researchers can interactively explore genetic alterations across samples, genes, and pathways, linking them to clinical outcomes when available. The portal offers graphical summaries, network visualization, survival analysis, patient-centric queries, and programmatic access. Its user-friendly interface makes complex cancer genomics profiles accessible to researchers and clinicians without requiring bioinformatics expertise. Originally developed at Memorial Sloan Kettering Cancer Center, cBioPortal is now an open-source project hosted on GitHub and collaboratively maintained by a team from various institutions worldwide.

The data coming in cBioPortal from different data sources requires data curation and normalization efforts that allow for users to visualize and navigate datasets that are standardized therefore making cross study comparisons easier and accurate.

# A. Data Curation Workflow

The curation process for cBioPortal begins by identifying data resources rich in clinical and cancer genomic information. This involves understanding the underlying research, checking data availability, and extracting and transforming the data to meet cBioPortal standards. Additional annotations are incorporated, quality control (QC) is performed, and the data is then imported into cBioPortal. Subsequent QC steps are taken within the portal to ensure the accuracy of the data.

The detailed steps are explained below.

B. Identifying the Data Sources

For source acquisition, follow the `abstractor-study-download` skill to acquire or reuse canonical publication and supplementary artifacts.

C. Inclusion Criteria

Several methods are adopted to streamline the process of identifying data sources. In general, an inclusion criteria sets the foundation for selecting datasets suitable for cBioPortal. These criteria are applied to ensure the quality, relevance, and comprehensiveness of the data made available to users. The outlined criteria cover various aspects, including publication details, sequencing data types, mutation types, and cohort sizes, providing a structured approach to the curation process.

* Publication Year  
  * Individual lab publications: required to be added to the portal within 3 years of publication   
  * Large consortium studies: may be added to the portal even if the publication exceeds 3 years

* Sequencing Data Type  
  * Next generation (DNA and RNA) sequencing data, formats included in the portal are:  
    * Methylation data  
    * Expression data  
    * Copy number data  
    * Structural variant data  
    * Segmented data

* Mutation Types  
  * Somatic, Germline  
  * Matched normal samples preferred

* Patient/cell line cohort size  
  * Tumor-type dependent (larger cohorts expected for common cancer types).

II. Introduction to cBioPortal File Formats and Data Abstraction

A study to be loaded in cBioPortal should consist of a directory where all the data files are located. Each data file needs a meta file that refers to it and both files need to comply with the format required for the specific data type. The format and fields expected for each file are documented in the [File Formats page](https://docs.cbioportal.org/file-formats/). The following provides detailed explanations for each data type, including the curation process and conversion to the accepted formats for the portal.

**Clinical Data**

For clinical data curation, follow the `curator-clinical-files-creation` skill.

**Mutation Data**

For mutation data curation, follow the `curator-mutation-data-file-creation` skill.

**Timeline Data**

Timeline data files represent a sequence of events occurring during the course of a specific event type. This data type is essential in monitoring different events and the event progression the patient undergoes starting from the time of diagnosis (point 0 in the timeline scale).  
   
Each event type requires its own data file, which consists of [four required columns](https://docs.cbioportal.org/file-formats/#data-file-11), in addition to other relevant descriptive columns that can be added to each event type file. [Event types](https://docs.cbioportal.org/file-formats/#event-types) include treatment, surgery, diagnostics, specimen, and various others.  
   
Although not provided for all studies, the data used to construct timeline files is readily available in the clinical files of the publication, which are usually found in the paper’s supplementary files or deposited in a database where the study data is archived. Any type of data that shows patient progression through a certain event type can be used to construct timeline data files, which is later represented as one or more tracks in the patient view area of the portal.

**Segmented Data**

A .SEG (segmented data) file is a tab-delimited text file describing DNAcopy data that is segmented to identify genomic regions with abnormal copy number. The file is the output of the Circular Binary Segmentation (CBS) algorithm, and consists of 6 columns including:

* *ID* – sample name  
* *chrom* – chromosome name or ID  
* *loc.start* – segment’s genomic start position, 1-indexed  
* *loc.end* – segment end position  
* *num.mark* – (optional) number of probes or bins covered by the segment  
* *seg.mean* – segment mean value, usually in log2 scale

   
The ‘[Segmented Data’](https://docs.cbioportal.org/file-formats/#segmented-data) section in the file format provides additional details on the relevant meta and data files.

The segmented data is usually presented in the publication’s supplementary files, which are freely available for download. Usually, this type of data is provided whenever copy number data is analyzed and is calculated by the authors from copy number data using the CBS algorithm. If present, a .seg file will contain the 6 required columns mentioned above. However, column names may vary in some files yet describe similar aspects of CNA segmentation. For example, ‘NumProbes’ corresponds to ‘num.mark’ which indicates the number of probes or bins covered by a specific segment. Even though both namings have the same meaning, cBioPortal recognizes the columns as listed above.

In the portal, segmented data can be found in the 'CNA' lane in the Genomic overview of the patient view.

**Gene Panel Data**

A gene panel is a collection of genes grouped to allow simultaneous sequencing of all the genes associated with a certain disease. The gene panel functionality specifies which genes are assayed in a panel and assigns samples and genetic profiles (such as mutation data) to a panel. This data type consists of a gene panel file, a gene panel matrix file, and a meta file.  
   
The gene panel file itself contains a list of all the genes in a panel, where one panel can be used for multiple studies within the instance and should be loaded prior to loading a study with gene panel data. For information on the format and import process please visit the [Import-Gene-Panels](https://docs.cbioportal.org/import-gene-panels/) page.

The gene panel matrix file is used to specify which samples are sequenced on which gene panel and in which genetic profile. This is recommended for mutation and structural variant data, because MAF and structural variant file formats are unable to include samples which are sequenced but contain no called mutations, and only a single gene panel can be defined in the meta file. For other genetic profiles, columns can be added to specify their gene panel, but a property can also be added to their respective meta files, as these data files contain all profiled samples. Although the gene panel matrix functionality overlaps with the case list functionality, a case list for mutations (\_sequenced) and structural variants (\_sv) is also required. In addition, a gene panel meta file will assign all samples from that profile to the gene panel. In this case, it is not necessary to include a column for this profile in the gene panel matrix file.  
   
The ‘[Gene Panel Data’](https://docs.cbioportal.org/file-formats/#gene-panel-data) section of the file formats further explains the contents of each of the files mentioned above.

A gene panel matrix file contains a list of samples in the first column, and an additional column for each profile in the study, where for each sample-profile combination, a gene panel should be specified. The gene panel matrix data file can be created using data present in the publication’s supplementary files. Usually, the clinical supplementary files will indicate which sample was profiled/sequenced and the paper will discuss the gene panel used. 

In the portal, the gene panel table or chart can be found in the study summary page, where further analysis can be done by selecting a certain panel for cohort analysis or comparison.

**Expression Data:**  
   
Gene expression is the process where the information in a gene is used to create a functional product, which can be a protein or RNA molecule. This process begins with transcription, where a gene's DNA is converted into RNA. In the case of protein-coding genes, the next step is translation, where the RNA is turned into a protein.  
   
**DNA Expression:** In cBioPortal, gene expression data from various techniques, including RNA-seq, microarrays, miRNA-seq, and single-cell RNA-seq, can be visualized. These techniques quantify RNA molecules, often using measures like RPKM or FPKM, providing insights into gene expression patterns.  
   
When preparing gene expression data for cBioPortal, it's important to follow the format and metadata requirements:

1. **Data Format:** The gene expression data from multiple biological samples is organized as a two-dimensional matrix, with genes listed in rows and samples in columns. Convert the data to the format as detailed in the cBioPortal [file-formats](https://docs.cbioportal.org/file-formats/#expression-data).  
2. **Metadata File:** Include a metadata file that accompanies the expression data. The metadata file should contain essential details, including the data type (which can be one of the specified options like CONTINUOUS, DISCRETE, or Z-SCORE), the techniques used for data generation (e.g., RNA-Seq, microarrays, miRNA etc.), and any normalization methods applied to the data (FPKM, RPKM, TPM, RSEM etc.).   
   

**Z-Score Normalization:**  
It is necessary to also provide a z-score transformed version of your input data file. The z-score data is essential for the oncoprint functionality. The oncoprint shows high or low mRNA expression of the genes, based on the threshold the user sets when selecting the genomic profile.  
   
cBioPortal expects z-score normalization to take place per gene. You can calculate z-scores with your own preferred method or use the cBioPortal provided [approach](https://github.com/cBioPortal/datahub-study-curation-tools/tree/master/zscores/zscores_relative_allsamples) in which the expression distribution for a gene is estimated by calculating the mean and variance of the expression values for all available samples. This measure is useful to determine whether a gene is up- or down-regulated relative to all the other tumor samples. Additionally, a corresponding metadata file should be included with the z-score transformed data file.

Please note that, for RNA-seq data (read counts, rpkm, fpkm etc.), the reference population is defined by any non-zero, non-negative numeric values. As raw expression counts or normalized units (rpkm, fpkm..) provide a measure of the abundance of transcripts, exclude any negative counts as the values could be due to technical biases. When applying the cBioPortal-provided approach, utilize the "-e" option of the script to exclude these negative values. Additionally, if you wish to have your data log-transformed before calculating z-scores, use the "-l" option.

Make sure the “show\_profile\_in\_analysis\_tab” field in the metadata file is set to "false" by default, and to "true" if the datatype is Z-SCORE to enable its display in features like oncoprint.

Please see the cBioPortal [recommended](https://github.com/cBioPortal/datahub/blob/master/docs/recommended_staging_filenames.md) data and meta file names based on the mRNA data type when pushing the data to the public [cBioPortal](https://www.cbioportal.org/).  
   
**Protein Expression:** Protein-Seq complements RNA-Seq by focusing on the comprehensive study of proteins. It identifies, quantifies, and characterizes the proteins in a sample, revealing the functional molecules that drive various cellular processes.  
   
In cBioPortal, a comprehensive analysis of protein and phosphoprotein levels obtained through RPPA (Reverse Phase Protein Array) or mass spectrometry techniques can be performed.  
   
**Protein Level:**  
The protein level data file is organized as a two-dimensional matrix with antibodies listed in rows and samples in columns. The antibody information may include one or more HUGO gene symbols and/or entrez gene identifiers, separated by spaces, along with an antibody ID pair separated by the "|" symbol. The mass-spec data is organized as a proteins vs. samples matrix.   
   
**Phosphoprotein Level:**  
The phosphoprotein level data file is a two-dimensional matrix with each row representing a specific phosphosite and each column corresponding to a sample. For example, a phosphosite is denoted as AKT1\_pS473 (which means AKT1 protein phosphorylated at serine residue at position 473).

To query phosphoprotein levels in the portal, you need to provide unique identifiers for each phosphoprotein or phosphosite, like AKT1\_pS473. Alternatively, you can use aliases such as phosphoAKT1 or phosphoprotein, and the portal will prompt you to choose the specific phosphoprotein or phosphosite of your preference.

When preparing protein or phosphoprotein expression data for cBioPortal, it's important to follow the format and metadata requirements:

1. **Data Format:** Organize the data from multiple samples into a two-dimensional matrix, with proteins or phosphoproteins arranged in rows and samples in columns. Refer to the cBioPortal [file-formats](https://docs.cbioportal.org/file-formats/#expression-data) for guidance.  
2. **Metadata File:** Include a metadata file along with the expression data. This metadata file should contain essential information, such as the data type (choosing from specified options like LOG2-VALUE or Z-SCORE) and the technique used for data generation (e.g., rppa, mass-spec, etc.).

   
**Z-Score Normalization:**  
It is also essential to provide a z-score transformed version of your input data file. You can calculate z-scores using your preferred method or opt for the cBioPortal provided [approach](https://github.com/cBioPortal/datahub-study-curation-tools/tree/master/zscores/zscores_relative_allsamples). If you use the cBioPortal approach, please refrain from including the "-e" option of the script. This option is intended for RNA-seq methods to exclude negative integers from the reference population.

Make sure the “show\_profile\_in\_analysis\_tab” field in the metadata file is set to "false" by default, and to "true" if the datatype is Z-SCORE to enable its display in features like oncoprint.

Please see the cBioPortal [recommended](https://github.com/cBioPortal/datahub/blob/master/docs/recommended_staging_filenames.md) data and meta file names based on the protein quantification type when pushing the data to the public [cBioPortal](https://www.cbioportal.org/).

**Structural Variant Data**

For structural variant data curation, follow the `curator-structural-variant-files-creation` skill.

#### **Gene panels for Structural Variant data**

Currently, structural variant events are saved in the same database table as mutation data. Therefore, these must share the same gene panel. Adding gene panel annotations to samples profiled for structural variants can be done with the [Gene Panel Matrix file](https://d3b-center.github.io/pedcbioportal/File-Formats.html#gene-panel-matrix-file) and adding them to the column for mutations.

**Copy Number Alterations (CNAs):**

Copy number alterations (CNAs) refers to changes in the number of copies of specific regions of DNA within a cancer cell's genome. These alterations can involve the amplification (gain) or deletion (loss) of DNA segments, which can have a significant impact on the behavior and characteristics of cancer cells. CNA’s are a common features of many cancer types and are often associated with the development and progression of cancer.

**Discrete Copy Number Data:**  
Discrete copy number data, as described in the cBioPortal  [file-formats](https://docs.cbioportal.org/file-formats/#expression-data), refers to a type of data representation that discretizes or categorizes the copy number status of genomic segments in cancer samples. Typically, this data is represented in binary form, indicating whether a genomic segment is gained, lost, or neutral (no alteration) in a specific sample. The discrete nature of this data simplifies the analysis and visualization of CNAs.

In the cBioPortal, discrete copy number data is often used for quick visualization and interpretation of CNAs in cancer datasets. It allows researchers and clinicians to easily identify regions of the genome that are amplified or deleted in specific tumor samples.Copy number data sets within the portal are often generated by the GISTIC or RAE algorithms. Both algorithms attempt to identify significantly altered regions of amplification or deletion across sets of patients. Both algorithms also generate putative gene/patient copy number specific calls, which are then input into the portal.

When preparingcopy number alteration data for cBioPortal, it is important to follow the format and metadata requirements:

1. **Data Format:** For CNA data two formats are supported: the wide, and the long format:  
   **Wide Format:** A matrix, where each row is a gene, and each column is a sample.  
   **Long Format:** Not a matrix, each row is a gene-sample combination; this makes the file longer. Convert the data to the format as listed in the cBioPortal [file-formats](https://docs.cbioportal.org/file-formats/#expression-data)**.**  
2. **Meta Format:** Add a metadata file including experimental methodologies (GISTIC,LOG2-VALUE etc.,) and any additional relevant information, will be annotated along with the curated data to provide context.

**Arm Level Copy Number Alterations (CNAs):**

Copy number alterations (CNAs) at the arm level refer to large-scale changes in the copy number of entire chromosomal arms rather than focusing on individual genes or smaller DNA segments. These alterations involve the amplification (gain, 1\) or deletion (loss, \-1) of entire chromosomal arms, which can have significant implications for the overall genomic stability and behavior of a cell. Analyzing CNA data at the arm level is a common approach in cancer genomics research, and it provides insights into the genomic landscape of cancer cells.

Arm level Copy Number events are now loaded into cBioPortal using the Categorial Generic Assay Data Type. They can be found in a tab under the Add Charts Button of the Study View   
[Example: Arm Level Data in TCGA PanCancer Atlas](https://www.cbioportal.org/study/summary?id=laml_tcga_pan_can_atlas_2018%2Cacc_tcga_pan_can_atlas_2018%2Cblca_tcga_pan_can_atlas_2018%2Clgg_tcga_pan_can_atlas_2018%2Cbrca_tcga_pan_can_atlas_2018%2Ccesc_tcga_pan_can_atlas_2018%2Cchol_tcga_pan_can_atlas_2018%2Ccoadread_tcga_pan_can_atlas_2018%2Cdlbc_tcga_pan_can_atlas_2018%2Cesca_tcga_pan_can_atlas_2018%2Cgbm_tcga_pan_can_atlas_2018%2Chnsc_tcga_pan_can_atlas_2018%2Ckich_tcga_pan_can_atlas_2018%2Ckirc_tcga_pan_can_atlas_2018%2Ckirp_tcga_pan_can_atlas_2018%2Clihc_tcga_pan_can_atlas_2018%2Cluad_tcga_pan_can_atlas_2018%2Clusc_tcga_pan_can_atlas_2018%2Cmeso_tcga_pan_can_atlas_2018%2Cov_tcga_pan_can_atlas_2018%2Cpaad_tcga_pan_can_atlas_2018%2Cpcpg_tcga_pan_can_atlas_2018%2Cprad_tcga_pan_can_atlas_2018%2Csarc_tcga_pan_can_atlas_2018%2Cskcm_tcga_pan_can_atlas_2018%2Cstad_tcga_pan_can_atlas_2018%2Ctgct_tcga_pan_can_atlas_2018%2Cthym_tcga_pan_can_atlas_2018%2Cthca_tcga_pan_can_atlas_2018%2Cucs_tcga_pan_can_atlas_2018%2Cucec_tcga_pan_can_atlas_2018%2Cuvm_tcga_pan_can_atlas_2018).

**Methylation Data:** 

Methylation data refers to information about the DNA methylation patterns in a biological sample, typically in the context of a genome or epigenome analysis. DNA methylation is an epigenetic modification that involves the addition of a methyl group (CH3) to the DNA molecule, specifically at cytosine bases. It plays a crucial role in gene regulation, cellular differentiation, development, and various biological processes. 

**DNA Methylation:** DNA methylation is a chemical modification of DNA in which a methyl group is added to the carbon atom at position 5 of a cytosine ring. This modification can occur at specific cytosines within the DNA sequence and is often associated with the regulation of gene expression.  
When preparing methylation data for cBioPortal, it is important to follow the format and metadata requirements:

1. **Data Format :** The cBiPortal expects a single value for each gene in each sample, usually a beta-value from the Infinium methylation array platform.Convert the data to the format as listed in the cBioPortal [file-formats](https://docs.cbioportal.org/file-formats/#expression-data)**.**  
2. **Meta Format:** Add a metadata file along with the methylation data.This metadata file should contain essential information, such as the  methylation array platform ( 27k,450k,EPIC) and any additional relevant information, will be annotated along with the curated data to provide context.

To query Methylation probes in the portal you can either use gene name or with an unique probe id. Alternatively, you can use aliases such as EGFR or cg14094960 (Probe ID), and the portal will prompt you to choose the specific gene/probe of your preference.

**Detailed Curation steps:**

1. First we will create the mapping between hugo\_gene\_symbol, probe\_name, gene\_group(location )depending on the array we are curating. For an example if we are curating Methylation 27k data we use  [illumina\_humanmethylation27\_content.xlsx](https://drive.google.com/open?id=1un-eiPuqL9GaS740BW-uDhCNupcmGgro) to get the latest gene symbol and location for the probes.  
2. Translate probe names into gene symbols in raw data files  
1. For cases like “1 probe \<-\> multiple genes”, simple duplicate rows with each gene symbol.  
2. For cases like “1 gene \<-\> multiple probes”

   i. Separate each row into different files by locations (e.g. data\_methylation\_hm27\_body, data\_methylation\_hm27\_5UTR), based on the values in “gene\_group(location)” column in created mapping file form step 1

   Ii. For each sub group (if multiple values)

   “we can also create multiple for each: strongest positive correlation, strongest negative, average”

1. Promoter (TSS1500, TSS200)

   (Keep the strongest negatively correlated (with RNA-seq) row (the smallest value one from the calculation of the correlation between methylation and RNA-seq)

2. Body

   (Use the biggest absolute correlation value OR ?? biggest absolute correlation value)

3. 1stExon  
4. 5'UTR  
5. 3'UTR  
6. NA. 

**Other Epigenetic Modifications:**

**Acetylprotein Quantification:**

Acetylprotein quantification refers to the measurement and determination of the levels of acetylated proteins within a biological sample. Acetylation is a common post-translational modification in which acetyl groups (-COCH3) are added to specific amino acid residues, particularly lysine, in proteins. Protein acetylation plays a significant role in the regulation of various cellular processes, including gene expression, protein function, and cellular signaling.

**Data Format:** Acetylprotein quantification is imported into the cBioPortal in generic assay format. Generic Assay is a two dimensional matrix generalized to capture non-genetic measurements per sample. Instead of a gene per row and a sample per column, a Generic Assay file contains a generic entity per row and a sample per column. Acetylprotein quantification is imported using the Categorial Generic Assay Data Type. Convert the data to the format as listed in the cBioPortal [file-formats](https://docs.cbioportal.org/file-formats/#expression-data)**.**

**Ubiquitylproteome Quantification:**

Ubiquitylproteome quantification is a specialized technique in the field of proteomics that focuses on the systematic analysis and quantification of proteins that have been modified by ubiquitin molecules through a process called ubiquitination. Ubiquitin is a small protein that plays a crucial role in post-translational modification of other proteins. When ubiquitin is attached to a target protein, it can regulate various cellular processes, such as protein degradation, signal transduction, and DNA repair.

**Data Format:** Ubiquitylproteome quantification is also imported in to cBioPortal in generic assay format.The genetic entity can be either (LIMIT-VALUE, CATEGORIAL OR BINARY) depending on your data. Refer to the cBioPortal [file-formats](https://docs.cbioportal.org/file-formats/#expression-data) for more details on generic assay format.

**Metabolome Quantification:**  
Metabolome quantification is the process of measuring and determining the concentration or abundance of various metabolites in a biological sample. The metabolome represents the complete set of small molecules or metabolites present in a cell, tissue, or organism. These metabolites include sugars, amino acids, lipids, organic acids, and other small molecules involved in various metabolic pathways.

**Data Format:** Metabolome quantification  is also imported in to cBioPortal in generic assay format. The genetic entity can be either (LIMIT-VALUE, CATEGORIAL OR BINARY) depending on your data. Refer to the cBioPortal [file-formats](https://docs.cbioportal.org/file-formats/#expression-data) for more details on generic assay format.

**N-glycoproteome Quantification:**  
N-glycoproteome quantification is the process of measuring and determining the abundance or levels of glycoproteins in a biological sample. Glycoproteins are proteins that have carbohydrates (glycans) attached to them, typically at specific asparagine (N) residues within the protein sequence. N-glycoproteome quantification is a specialized area of proteomics and glycomics, which focuses on studying the glycoproteins in a given biological context.

**Data Format:**  N-glycoproteome quantification is also imported in to cBioPortal in generic assay format. The genetic entity can be either (LIMIT-VALUE, CATEGORIAL OR BINARY) depending on your data. Refer to the cBioPortal [file-formats](https://docs.cbioportal.org/file-formats/#expression-data) for more details on generic assay format.  
   
**Data Standardization and Curation Tools** 

[**Genome Nexus**](https://www.genomenexus.org/) 

Genome Nexus (GN) is a [resource](https://github.com/genome-nexus) developed by Memorial Sloan Kettering Cancer Center (MSK) with contributions from The Hyve. It is a comprehensive tool for fast, automated, and high-throughput annotation and interpretation of genetic variants in cancer. GN integrates information from a variety of existing resources, including databases that convert DNA changes to protein changes, predict the functional effects of protein mutations, and contain information about mutation frequencies, gene function, variant effects, and clinical actionability.  
   
The software is available under an open-source license via GitHub, where multiple repositories and tools allow the execution of various functions related to mutation data.

**Validator**

The data validation process is essential in ensuring that data uploaded to the portal is evaluated for accuracy, completeness, cleanliness, and usability. There are several validation methods used for cBioPortal studies, one of which is the validator tool. 

The cBioPortal validator has several roles, including:

1. Facilitate the loading of new studies into its database: Validating study compliance with the [recommended staging filenames](https://github.com/cBioPortal/datahub/blob/master/docs/recommended_staging_filenames.md) that the cancer study data should assume in order for the study to be successfully added to datahub.   
2. Examining study files for completeness: The validator examines the core components (data files, meta files, and case lists) of a study folder for completeness and accuracy. The files are scanned to ensure they are in the correct [format](https://docs.cbioportal.org/file-formats/) and all the data is accounted for, eliminating errors of duplicate, missing, or incorrect data.  
3. Generation of a cBioPortal Validation Report: the output of running the validator is an HTML report that describes the study components and indicates any warnings or errors that will cause improper loading into the portal.

The validator tool can be used in two instances; as a [standalone](https://github.com/cBioPortal/datahub-study-curation-tools/tree/master/validation/validator) version of cBioPortal data validator, and through [CircleCI](https://github.com/cBioPortal/datahub/tree/master/.circleci) in [Datahub](https://github.com/cBioPortal/datahub) on a submitted pull request (PR). 

The standalone validator can be used by [cloning the study curation tools repository](https://github.com/cBioPortal/datahub-study-curation-tools/tree/master) to validate single or multiple studies formatted in cBioPortal format. The HTML validation report gives the curator feedback used to correct, enhance, and double check the curated study before import. In addition, the validator is automatically run by CircleCI in Datahub whenever a PR is created, and on all public studies on a weekly basis. CircleCI conducts a number of checks and validates whether study tests pass on CircleCI, allowing the curator to assign a reviewer to review the PR before merging to the master branch. 

**Data import and QC** 

Quality control (QC) is an essential part of the curation process; studies go through multiple rounds of QC procedures including validation and review to ensure that data imported into the portal is accurate and reliable. When a study is curated following the cBioPortal file formats, it is scanned by the curator against the [Public Studies Curation Checklist](https://docs.google.com/document/d/1bbBUMARD0OlL7uBi3NmNLdHaBla4HxXz3UCVk_kk2Rk/edit). This document describes essential points to verify before a study is validated and added to the cBioPortal public database, highlighting points for each file type and checking for the overall study. In addition, general checks include [migrating outdated gene symbols](https://github.com/cBioPortal/datahub-study-curation-tools/tree/master/gene-table-update/data-file-migration) and making sure all files are stored as text files in character set to Unicode(UTF-8) and Unix(LF).  
   
After finalizing the study and following the public studies curation checklist, studies are validated using a standalone local [validator](https://github.com/cBioPortal/datahub-study-curation-tools/tree/master/validation/validator), which can be cloned from the [datahub-study-curation-tools](https://github.com/cBioPortal/datahub-study-curation-tools/tree/master), and automatically runs by [CircleCI](https://github.com/cBioPortal/datahub/tree/master/.circleci) on the cBioPortal [Datahub](https://github.com/cBioPortal/datahub). The validator validates single or multiple studies formatted in cBioPortal [file formats](https://docs.cbioportal.org/file-formats/), and outputs reports in both plain text and HTML format. The validation report is color coded to identify information, warnings, and errors. When a filename is selected, the report provides the error messages to identify issues that need to be fixed. Red error messages must be addressed before a study is imported to the portal.  


For the review process, the study should be imported to the [Triage](https://triage.cbioportal.mskcc.org/) portal, cBioPortal’s testing instance. The review process consists of 2 rounds of review, where the study is reviewed in the Triage portal against the publication by other curators to ensure all available data in the paper has been added and the study follows cBioPortal formats, allowing the curator to edit and fix review points after the first round to finalize the study for the second round of review. After review, the completed public studies are imported to [cBioPortal](https://www.cbioportal.org/) page. Internal and private MSK studies are added to the MSK or private portal.
