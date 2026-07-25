### Mutation Data Section From SOP

In cBioPortal, mutation data is presented in a Mutation Annotation Format (MAF) file, which is a tab-delimited text file containing somatic and germline mutations that are aggregated from VCF files produced by various variant calling pipelines. A cBioPortal MAF contains all types of mutations, however by default, the portal filters out synonymous mutations (not supported) as well as a couple variants including silent, intron, IGR, 3'UTR, 5'UTR, 3'Flank and 5'Flank (except for the promoter mutations of the TERT gene). If otherwise preferred, the variant filter setting can be changed by adding the [variant\_classification\_filter](https://docs.cbioportal.org/file-formats/#variant-classification-filter) field in the MAF file and adjusting accordingly. In addition, Germline mutations are supported by cBioPortal, but are, with a few exceptions, not available in the public instance.  
   
In cases where a study has multiple sequencing profiles, this is shown in one MAF file by using different sample IDs (for the same patient) and different sequencing panels. A [Gene Panel](https://docs.cbioportal.org/file-formats/#gene-panel-matrix-file) file accompanies a MAF file in such cases.  
   
MAF files have a common layout of presenting mutation data, however cBioPortal accepts a minimal MAF created with 5 attributes (and the extended MAF created with 37 attributes)  linked below. The minimal MAF contains the data required for further annotation with protein changes using the [Genome Nexus Annotation Pipeline](https://github.com/genome-nexus/genome-nexus-annotation-pipeline). cBioPortal utilizes mutation calls as provided by the publication, then standardizes annotation using [Genome Nexus Server](https://genomenexus.org/), which in turn leverages Ensembl’s Variant Effect Predictor (VEP) and selects a single effect per variant.   
   
The cBioPortal MAF attributes are explained in the ‘[Mutation Data](https://docs.cbioportal.org/file-formats/#cbioportal-mutation-data-file-format)’ section of the file formats page. Also, in addition to the attributes listed in the document linked, custom driver annotation attributes can be manually added to complement or replace the default driver annotation resources OncoKB and HotSpots.

For curation, mutation data is usually found available in the publication supplementary files, deposited in a database where the study data is archived, or found available in a study portal. All the resources listed enable the download of the mutation data files. When curating a MAF, Genome Nexus (GN) is a significant and comprehensive resource used throughout the process. GN integrates variant annotations from various sources relevant to cancer to provide thorough mutation data. To begin with, since cBioPortal accepts mutation data in a MAF format, the [VCF2MAF](https://github.com/genome-nexus/annotation-tools#vcf-to-maf-conversion-tool) tool in the [Genome Nexus Annotation Tool](https://github.com/genome-nexus/annotation-tools) enables the easy conversion of VCF files provided by the publication into MAF files using a Python script. GN also provides a [MAF2MAF](https://github.com/genome-nexus/annotation-tools/blob/master/maf2maf.py) tool that can be used to standardize MAF files and add or fix minor issues of an incomplete MAF file. After curation and conversion into the file formats, the GN [annotation pipeline](https://github.com/genome-nexus/genome-nexus-annotation-pipeline) can be used to annotate the MAF file.  
   
After creating a MAF file, several points should be noted and reviewed as part of a MAF sanity check after curation and annotation. This ensures the correct format and contents of the file before uploading it to the portal. These include:

* MAF file should be annotated with MSK (data\_muations.txt) isoform  
* If unknown, the Entrez Gene Id value should either be 0 or empty  
* Make sure no ‘NA’ for ref alleles ([\#621](https://github.com/cBioPortal/datahub/issues/621))  
* The Reference Build should be GRCh37. Do a liftover if needed. If the values are 37/hg19/NA replace with GRCh37.  
* In cases where the reference build in GRCh38, it must be noted in the study meta file that the reference\_genome: GRCh38  
* Mutated Issue: make sure no cases of deletion/insertions are annotated as missense mutations ([\#255](https://github.com/cBioPortal/datahub/issues/255))  
* Cases with HGVSp\_short annotated as MUTATED should be fixed  
* By default, germline mutations are not included in the portal. However, if the mutations data file contains germline mutations, double check with PI to see if they should be kept  
* Correct gene symbols convereted to Dates (SEPT13 \-\> 13-Sept) by Excel, using [this scirpt](https://github.com/cBioPortal/datahub-study-curation-tools/tree/master/hugo-symbol-corrector)  
* Fix cases with ‘protein\_change’ annotated as ‘MUTATED’  
* Make sure to follow the rule of Ref\_seq\_allele \= tumor\_seq\_allele\_1

   
In the portal, genetic mutations are provided in two ways:    
1\. 	*For an individual patient*: this shows all the genetic alterations a patient has, and is retrieved from the summary in the patient view  
![][image5]  
2\. 	*For the whole cohort*: this shows all the mutations from the entire cohort for a single gene, and is found using the Oncoprint or mutations tab when querying a certain gene  
![][image6]  
![][image7]  