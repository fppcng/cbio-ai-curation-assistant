## Clinical Data

The clinical data is used to capture both clinical attributes and the mapping between patient and sample ids. The software supports multiple samples per patient.  

As of March 2016, the clinical file is split into a patient clinical file and a sample clinical file. The *sample* file is required, whereas the *patient* file is optional. cBioPortal has specific functionality for a core set of patient and sample columns, but can also display custom columns (see section ["Custom columns in clinical data"](#custom-columns-in-clinical-data)).

### Meta files
The two clinical metadata files (or just one metadata file if you choose to leave the *patient* file out) have to contain the following fields:

1. **cancer_study_identifier**: same value specified in meta_study.txt
2. **genetic_alteration_type**: CLINICAL
3. **datatype**: PATIENT_ATTRIBUTES or SAMPLE_ATTRIBUTES
4. **data_filename**: your datafile

### Examples
An example metadata file, e.g. named meta_clinical_sample.txt, would be:
```
cancer_study_identifier: brca_tcga_pub
genetic_alteration_type: CLINICAL
datatype: SAMPLE_ATTRIBUTES
data_filename: data_clinical_sample.txt
```

An example metadata file, e.g. named meta_clinical_patient.txt, would be:
```
cancer_study_identifier: brca_tcga_pub
genetic_alteration_type: CLINICAL
datatype: PATIENT_ATTRIBUTES
data_filename: data_clinical_patient.txt
```

### Data files
For both patients and samples, the clinical data file is a two dimensional matrix with multiple clinical attributes. When the attributes are defined in the *patient* file they are considered to be patient attributes; when they are defined in the *sample* file they are considered to be sample attributes. 

The first four rows of the clinical data file contain tab-delimited metadata about the clinical attributes. These rows **have to start with a '#' symbol**. Each of these four rows contain different type of information regarding each of the attributes that are defined in the fifth row:

- Row 1: **The attribute Display Names**: The display name for each clinical attribute
- Row 2: **The attribute Descriptions**: Long(er) description of each clinical attribute
- Row 3: **The attribute Datatype**: The datatype of each clinical attribute (must be one of:  STRING, NUMBER, BOOLEAN)
- Row 4: **The attribute Priority**: A number which indicates the importance of each attribute.  In the future, higher priority attributes will appear in more prominent places than lower priority ones on relevant pages (such as the [Study View](https://www.cbioportal.org/study?id=brca_tcga)). A higher number indicates a higher priority.
    ```
    To promote certain chart in study view, please increase priority to a certain number. The higher the score, the higher priority it will be displayed in the study view.
    If you want to hide chart, please set the priority to 0. For combination chart, as long as one of the clinical attribute has been set to 0, it will be hidden.
    
    Currently, we preassigned priority to few charts, but as long as you assign a priority except than 1, these preassigned priorities will be overwritten.
    
    CANCER_TYPE: 3000, CANCER_TYPE_DETAILED: 2000,
    Overall survival plot: 400 (This is combination of OS_MONTH and OS_STATUS) 
    Disease Free Survival Plot: 300 (This is combination of DFS_MONTH and DFS_STATUS) 
    Mutation Count vs. CNA Scatter Plot: 200,
    Mutated Genes Table: 90, CNA Genes Table: 80, study_id: 70, # of Samples Per Patient: 40,
    With Mutation Data Pie Chart: 60, With CNA Data Pie Chart: 50, 
    Mutation Count Bar Chart: 30, CNA Bar Chart: 20,
    GENDER: 9, SEX: 9, AGE: 8
    ```
    
    Please note: 
    Priority is not the sole factor determining which chart will be displayed first.
    A layout algorithm in study view also makes a minor adjustment on the layout.
    The algorithm tries to fit all charts into a 2 by 2 matrix (Mutated Genes Table occupies 2 by 2 space).
    When a chart can not be fitted in the first matrix, the second matrixed will be generated. 
    And the second matrix will have lower priority than the first one. 
    If later chart can fit into the first matrix, then its priority will be promoted.
    
    Please see [here](/deployment/customization/Studyview.md) for more detailed information about how study view utilize priority and how the layout is calculated based on priority.
- Row 5: **The attribute name for the database**: This name should be in upper case.
- Row 6: This is the first row that contains actual data.


### Example clinical header
Below is an example of the first 4 rows with the respective metadata for the attributes defined in the 5th row. 
```
#Patient Identifier<TAB>Overall Survival Status<TAB>Overall Survival (Months)<TAB>Disease Free Status<TAB>Disease Free (Months)<TAB>...
#Patient identifier<TAB>Overall survival status<TAB>Overall survival in months since diagnosis<TAB>Disease free status<TAB>Disease free in months since treatment<TAB>...
#STRING<TAB>STRING<TAB>NUMBER<TAB>STRING<TAB>NUMBER<TAB>...
#1<TAB>1<TAB>1<TAB>1<TAB>1<TAB>
PATIENT_ID<TAB>OS_STATUS<TAB>OS_MONTHS<TAB>DFS_STATUS<TAB>DFS_MONTHS<TAB>...
....
data - see examples below
....
```

### Clinical patient columns
The file containing the patient attributes has one **required** column:
- **PATIENT_ID (required)**: a unique patient ID. This field allows only numbers, letters, points, underscores and hyphens.

The following columns are used by the study view as well as the patient view. In the [study view](https://www.cbioportal.org/study?id=brca_tcga) they are used to create the survival plots. In the patient view they are used to add information to the [header](https://www.cbioportal.org/patient?studyId=lgg_ucsf_2014&caseId=P05).

**Note on survival plots**: to generate the survival plots successfully, the columns are required to be in pairs, which means the file should have a pair of columns that have the same prefix but ending with `_STATUS` and `_MONTHS` individually. For example, `PFS_STATUS` and `PFS_MONTHS` are a valid pair of columns that can generate the survival plots.

**Note on survival status value**: the value of survival status must prefixed with `0:` or `1:`. Value with prefix `0:` means that no event (e.g. `LIVING`, `DiseaseFree`). Value with prefix `1:` means that an event occurred (e.g. `DECEASED`, `Recurred/Progressed`). 

- **OS_STATUS**:  Overall patient survival status
    - Possible values: 1:DECEASED, 0:LIVING
    - In the patient view, 0:LIVING creates a green label, 1:DECEASED a red label.
- **OS_MONTHS**:  Overall survival in months since initial diagnosis
- **DFS_STATUS**: Disease free status since initial treatment
    - Possible values: 0:DiseaseFree, 1:Recurred/Progressed
    - In the patient view, 0:DiseaseFree creates a green label, 1:Recurred/Progressed a red label.
- **DFS_MONTHS**: Disease free (months) since initial treatment

These columns, when provided, add additional information to the patient description in the header:
- **PATIENT_DISPLAY_NAME**: Patient display name (string)
- **GENDER** or **SEX**: Gender or sex of the patient (string)
- **AGE**: Age at which the condition or disease was first diagnosed, in years (number)
- **TUMOR_SITE**

Use PATIENT_DISPLAY_NAME only if it adds information beyond PATIENT_ID.

Simple rule
- If PATIENT_DISPLAY_NAME == PATIENT_ID for all rows, do not create PATIENT_DISPLAY_NAME.
- Create PATIENT_DISPLAY_NAME only when it provides a cleaner, more human-readable, or publication-preferred label than the internal PATIENT_ID.

Custom attributes:
- **Custom Clinical Attribute Headers**: Any other custom attribute can be added as well. See section ["Custom columns in clinical data"](#custom-columns-in-clinical-data).

### Example *patient* data file
```
#Patient Identifier<TAB>Overall Survival Status<TAB>Overall Survival (Months)<TAB>Disease Free Status<TAB>Disease Free (Months)<TAB>...
#Patient identifier<TAB>Overall survival status<TAB>Overall survival in months since diagnosis<TAB>Disease free status<TAB>Disease free in months since treatment<TAB>...
#STRING<TAB>STRING<TAB>NUMBER<TAB>STRING<TAB>NUMBER<TAB>...
#1<TAB>1<TAB>1<TAB>1<TAB>1<TAB>
PATIENT_ID<TAB>OS_STATUS<TAB>OS_MONTHS<TAB>DFS_STATUS<TAB>DFS_MONTHS<TAB>...
PATIENT_ID_1<TAB>1:DECEASED<TAB>17.97<TAB>1:Recurred/Progressed<TAB>30.98<TAB>...
PATIENT_ID_2<TAB>0:LIVING<TAB>63.01<TAB>0:DiseaseFree<TAB>63.01<TAB>...
...
```

### Clinical sample columns
The file containing the sample attributes has two **required** columns:
- **PATIENT_ID (required)**: A patient ID. This field can only contain numbers, letters, points, underscores and hyphens.
- **SAMPLE_ID (required)**: A sample ID. This field can only contain numbers, letters, points, underscores and hyphens.

By adding `PATIENT_ID` here, cBioPortal will map the given sample to this patient. This enables one to associate multiple samples to one patient. For example, a single patient may have had multiple biopsies, each of which has been genomically profiled. See [this example for a patient with multiple samples](https://www.cbioportal.org/patient?studyId=lgg_ucsf_2014&caseId=P04).

The following columns are required for the pan-cancer summary statistics tab ([example](https://www.cbioportal.org/index.do?cancer_study_id=msk_impact_2017&Z_SCORE_THRESHOLD=2&RPPA_SCORE_THRESHOLD=2&data_priority=0&case_set_id=msk_impact_2017_cnaseq&gene_list=BRAF&geneset_list=+&tab_index=tab_visualize&Action=Submit&genetic_profile_ids_PROFILE_MUTATION_EXTENDED=msk_impact_2017_mutations&genetic_profile_ids_PROFILE_COPY_NUMBER_ALTERATION=msk_impact_2017_cna)).
- **CANCER_TYPE**: Cancer Type
- **CANCER_TYPE_DETAILED**: Cancer Type Detailed, a sub-type of the specified CANCER_TYPE

The following columns affect the header of the patient view by adding text to the samples in the header:
- **SAMPLE_DISPLAY_NAME**: displayed in addition to the ID
- **SAMPLE_CLASS**
- **METASTATIC_SITE** or **PRIMARY_SITE**: Override TUMOR_SITE (patient level attribute) depending on sample type

The following columns additionally affect the [Timeline data](#timeline-data) visualization:
- **OTHER_SAMPLE_ID**: OTHER_SAMPLE_ID is no longer supported. Please replace this column header with SAMPLE_ID.   
- **SAMPLE_TYPE**, **TUMOR_TISSUE_SITE** or **TUMOR_TYPE**: gives sample icon in the timeline a color.
    - If set to `recurrence`, `recurred`, `progression` or `progressed`: orange
    - If set to `metastatic` or `metastasis`: red
    - If set to `primary` or otherwise: black

Custom attributes:
- **Custom Clinical Attribute Headers**: Any other custom attribute can be added as well. See section ["Custom columns in clinical data"](#custom-columns-in-clinical-data).

### Example sample data file
```
#Patient Identifier<TAB>Sample Identifier<TAB>Subtype<TAB>...
#Patient identifier<TAB>Sample Identifier<TAB>Subtype description<TAB>...
#STRING<TAB>STRING<TAB>STRING<TAB>...
#1<TAB>1<TAB>1<TAB>...
PATIENT_ID<TAB>SAMPLE_ID<TAB>SUBTYPE<TAB>...
PATIENT_ID_1<TAB>SAMPLE_ID_1<TAB>basal-like<TAB>...
PATIENT_ID_2<TAB>SAMPLE_ID_2<TAB>Her2 enriched<TAB>...
...
```

### Columns with specific functionality
These columns can be in either the patient or sample file.
- **CANCER_TYPE**: Overrides study wide cancer type
- **CANCER_TYPE_DETAILED**
- **KNOWN_MOLECULAR_CLASSIFIER**
- **GLEASON_SCORE**: Radical prostatectomy Gleason score for prostate cancer
- **HISTOLOGY**
- **TUMOR_STAGE_2009**
- **TUMOR_GRADE**
- **ETS_RAF_SPINK1_STATUS**
- **TMPRSS2_ERG_FUSION_STATUS**
- **ERG_FUSION_ACGH**
- **SERUM_PSA**
- **DRIVER_MUTATIONS**

### Custom columns in clinical data
cBioPortal supports custom columns with clinical data in either the patient or sample file. They should follow the previously described 5-row header format. Be sure to provide the correct `Datatype`, for optimal search, sorting, filtering (in [clinical data tab](https://www.cbioportal.org/study?id=brca_tcga#clinical)) and visualization.

The Clinical Data Dictionary from MSKCC is used to normalize clinical data, and should be followed to make the clinical data comparable between studies. This dictionary provides a definition whether an attribute should be defined on the patient or sample level, as well as provides a name, description and datatype. The data curator can choose to ignore these proposed definitions, but not following this dictionary might make comparing data between studies more difficult. It should however not break any cBioPortal functionality. See GET /api/ at [https://cdd.cbioportal.mskcc.org/swagger-ui.html](https://cdd.cbioportal.mskcc.org/swagger-ui.html#!/clinical-data-dictionary-controller/getClinicalAttributeMetadataBySearchTermsUsingPOST) for the data dictionary of all known clinical attributes.