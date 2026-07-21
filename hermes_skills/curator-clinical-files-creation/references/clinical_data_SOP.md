# Clinical Data

Clinical data involves various types of data related to patient demographics, their disease and exposures, diagnosis, laboratory tests, and treatment. Clinical data has a major role in providing a comprehensive view of the patient case by providing additional significant information pertaining to each patient.  
   
In cBioPortal, clinical data is divided into patient-level and sample-level data as separate files to facilitate the provision of relevant information. In general, both data files follow the same format, where the first four rows of the files contain tab-delimited metadata about the clinical attributes. These rows start with a '\#' symbol and describe the attributes defined in the fifth row. This, along with the various data file attributes, is explained in further details in the [‘Clinical Data](https://docs.cbioportal.org/file-formats/#clinical-data)’ section of the file formats page.  
   
Regarding the data, some examples of the different commonly used attributes are listed in the document linked above, but any additional data relating to the patient or sample can be added in the relevant file in the format explained. The minimum required columns define the patient ID (in the clinical patient file) and map that to the sample ID (from the clinical sample file), allowing mapping multiple samples to the same patient.

During curation, clinical data is usually found available in the publication supplementary files or deposited in a database where the study data is archived. Most publications have easily accessible supplementary files which can be downloaded and curated to cBioPortal file formats. When creating the curated data files, this [tool](https://github.com/cBioPortal/datahub-study-curation-tools/tree/master/add-clinical-header) allows the addition of the meta data header lines (described above) for the clinical attributes. In addition, almost all clinical files have the cancer Oncotree code, where the [Oncotree converter tool](https://github.com/cBioPortal/datahub-study-curation-tools/tree/master/oncotree-code-converter) is used to extract and add the cancer type and cancer type detailed information from the database into the clinical files.  
   
In the portal, clinical data visualization can be seen in several places in the study page. The study page summary provides a comprehensive summary of both genomic and clinical information for the entire cohort as seen below (example from a pediatric pan-cancer study). This feature is helpful when conducting cross study comparisons, where custom groups can be created and compared for their clinical and genomic features. All charts are in 2-dimensional systems, and the type of chart (pie chart, bar chart, or table) shown by the portal is determined by the attribute datatype, while the layout position of the chart is determined by its priority.

![][image3]  
   
In addition, the patient view allows users to view the clinical data specific to individual patients, where the data is divided into patient and sample attributes to ease understanding and provide a complete profile for each patient and their samples as shown below.

![][image4]