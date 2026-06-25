# Post-Generation Curation Tools

## Overview

After generating the cBioPortal study directory, run the following normalization and validation tools from the [datahub-study-curation-tools](https://github.com/cBioPortal/datahub-study-curation-tools) repository before packaging the final study.

These tools must be run **in the order listed below**. Some tools are conditional and should only be run when the relevant data type is present in the study.

---

## Prerequisites

Clone the curation tools repository before running any tools:

```bash
git clone https://github.com/cBioPortal/datahub-study-curation-tools.git
TOOLS_DIR=/path/to/datahub-study-curation-tools
STUDY_DIR=/path/to/study_output_directory
STUDY_ID=your_study_id
```

---

## Step 1 — Hugo Symbol Corrector (Conditional: MAF data present)

**When to run:** If mutation data (`data_mutations_extended.txt` or any MAF file) was sourced from or processed through Microsoft Excel. Excel auto-converts certain gene symbols (e.g., `SEPT2` → `2-Sep`, `MARCH1` → `1-Mar`). This step must run **before** Genome Nexus annotation.

**Purpose:** Restores gene symbols in the Hugo Symbol column that were incorrectly converted to date strings by Excel.

```bash
python $TOOLS_DIR/hugo-symbol-corrector/gene_symbol_correction.py \
  --mapping $TOOLS_DIR/hugo-symbol-corrector/hugo_mapping_file.txt \
  --hugo $STUDY_DIR/data_mutations_extended.txt
```

**Output:** Corrected MAF file in-place (or as a new file depending on script version).

---

## Step 2 — Genome Nexus MAF Annotation (Conditional: MAF data present)

**When to run:** If the study contains mutation data in MAF format (`data_mutations_extended.txt`). This step enriches the MAF with functional annotations including protein change, variant classification, HGVSp, transcript ID, and oncogenicity.

**Purpose:** Annotates a MAF file using the Genome Nexus annotation pipeline via Docker. No build from source is required — Docker pulls the pre-built image from DockerHub automatically.

**Docker image:** [`genomenexus/gn-annotation-pipeline`](https://hub.docker.com/r/genomenexus/gn-annotation-pipeline)

### Pull the image

```bash
docker pull genomenexus/gn-annotation-pipeline:latest
```

### Run annotation

The `-v ${PWD}:/wd` flag mounts your current directory into the container at `/wd`. Input and output files must be in the same directory.

```bash
cd $STUDY_DIR

docker run --rm \
  -v ${PWD}:/wd \
  genomenexus/gn-annotation-pipeline:latest \
  java -jar annotationPipeline.jar \
    --filename /wd/data_mutations_extended.txt \
    --output-filename /wd/data_mutations_annotated.txt \
    --isoform-override mskcc \
    --error-report-location /wd/data_mutations_unannotated.txt
```

**Isoform note:** `mskcc` is the preferred isoform override. Use `uniprot` only for legacy compatibility.

### GRCh38 studies

If the study uses GRCh38 (hg38), set the `GENOMENEXUS_BASE` environment variable:

```bash
docker run --rm \
  -e GENOMENEXUS_BASE=https://grch38.genomenexus.org \
  -v ${PWD}:/wd \
  genomenexus/gn-annotation-pipeline:latest \
  java -jar annotationPipeline.jar \
    --filename /wd/data_mutations_extended.txt \
    --output-filename /wd/data_mutations_annotated.txt \
    --isoform-override mskcc \
    --error-report-location /wd/data_mutations_unannotated.txt
```

Default reference genome is **GRCh37**. Use GRCh38 only when the study explicitly states hg38.

### Handling unannotated records with the GN-annotation-wrapper

The GN annotation wrapper in `datahub-study-curation-tools` retries annotation for any records that fail due to API timeouts. Run it **after** the initial Docker annotation if `data_mutations_unannotated.txt` is non-empty:

```bash
python $TOOLS_DIR/GN-annotation-wrapper/GN_annotation_wrapper.py \
  --input_maf $STUDY_DIR/data_mutations_unannotated.txt \
  --annotator_jar_path "docker run --rm -v \${PWD}:/wd genomenexus/gn-annotation-pipeline:latest java -jar annotationPipeline.jar" \
  --isoform mskcc \
  --annotated_maf $STUDY_DIR/data_mutations_retry_annotated.txt \
  --unannotated_maf $STUDY_DIR/data_mutations_still_unannotated.txt
```

Then merge all annotated records into the final MAF:

```bash
python $TOOLS_DIR/GN-annotation-wrapper/merge_mafs.py \
  --input_maf1 $STUDY_DIR/data_mutations_annotated.txt \
  --input_maf2 $STUDY_DIR/data_mutations_retry_annotated.txt \
  --merged_maf $STUDY_DIR/data_mutations_extended.txt
```

**Note:** Replace the original MAF with the merged output. Manually review any remaining `data_mutations_still_unannotated.txt` records before proceeding.

---

## Step 3 — Oncotree Code Converter (Required)

**When to run:** Always. The clinical sample file must contain `CANCER_TYPE` and `CANCER_TYPE_DETAILED` columns derived from the `ONCOTREE_CODE` column. cBioPortal requires these for study display.

**Purpose:** Queries the Oncotree API and inserts `CANCER_TYPE` and `CANCER_TYPE_DETAILED` columns into the clinical sample file based on the `ONCOTREE_CODE` value.

```bash
python $TOOLS_DIR/oncotree-code-converter/oncotree_code_converter.py \
  --clinical-file $STUDY_DIR/data_clinical_sample.txt \
  --oncotree-url "https://oncotree.info/" \
  --oncotree-version oncotree_latest_stable
```

**Note:** `clinicalfile_utils.py` must be present in the same directory as `oncotree_code_converter.py` (it is included in the repo). Use a stable Oncotree version for reproducibility. Common versions include `oncotree_latest_stable` or a dated release such as `oncotree_2024_01_01`.

---

## Step 4 — Add Clinical Header (Conditional)

**When to run:** If the clinical patient or sample data files are missing the required 5-line cBioPortal metadata header (display name, description, datatype, priority, and attribute type rows). Files generated from scratch by this agent should already have these headers, but run this step if they are absent or malformed.

**Purpose:** Inserts the cBioPortal-required metadata header rows into `data_clinical_patient.txt` and `data_clinical_sample.txt`.

**Prerequisites:** A `clinical_attributes_metadata.txt` dictionary file must exist in the study directory or a shared config path.

```bash
cd $STUDY_DIR
python $TOOLS_DIR/add-clinical-header/insert_clinical_metadata.py -d .

# Replace original files with the annotated versions
rm data_clinical_patient.txt data_clinical_sample.txt
mv data_clinical_patient.txt.metadata data_clinical_patient.txt
mv data_clinical_sample.txt.metadata data_clinical_sample.txt
```

---

## Step 5 — Generate Case Lists (Required)

**When to run:** Always. Case lists define which samples are included for each data type (e.g., `cases_all`, `cases_sequenced`, `cases_RNA_Seq_mRNA`). cBioPortal will not load a study without appropriate case lists.

**Purpose:** Auto-generates all case list files under `case_lists/` based on which data files are present in the study directory.

**Prerequisites:** A `case_list_conf.txt` configuration file is required. Use the standard config from the tools repo or from the datahub. `clinicalfile_utils.py` must be in the same directory as the script.

```bash
cd $STUDY_DIR
rm -rf case_lists
mkdir case_lists

python $TOOLS_DIR/generate-case-lists/generate_case_lists.py \
  --case-list-config-file $TOOLS_DIR/generate-case-lists/case_list_conf.txt \
  --case-list-dir $STUDY_DIR/case_lists \
  --study-dir $STUDY_DIR \
  --study-id $STUDY_ID
```

**Output:** Populates `case_lists/` with individual case list files (e.g., `cases_all.txt`, `cases_sequenced.txt`).

---

## Step 6 — Z-Score Calculation (Conditional: expression data present)

**When to run:** If the study includes mRNA expression data (`data_expression_median.txt` or similar). Z-scores are required for the expression comparison view in cBioPortal.

**Purpose:** Calculates per-gene z-scores across samples from a normalized expression matrix.

```bash
python $TOOLS_DIR/zscores/calculate_zscores.py \
  --expression-file $STUDY_DIR/data_expression_median.txt \
  --output-file $STUDY_DIR/data_mRNA_median_Zscores.txt
```

**Note:** Check the `zscores/` directory for the exact script name and available flags, as the interface may vary by version. The output file should be referenced by a corresponding `meta_mRNA_median_Zscores.txt` metadata file in the study.

---

## Step 7 — TMB Calculation (Optional: MAF data present)

**When to run:** If the study contains MAF data and TMB (Tumor Mutation Burden) is not already provided as a clinical attribute. TMB is useful for studies where mutational load is clinically relevant.

**Purpose:** Calculates TMB per sample from the MAF file and can append it as a clinical attribute.

```bash
python $TOOLS_DIR/TMB/calculate_TMB.py \
  --input-maf $STUDY_DIR/data_mutations_extended.txt \
  --output-file $STUDY_DIR/tmb_scores.txt
```

**Note:** Verify the script name and arguments from the `TMB/` directory. If appending TMB to the clinical sample file, ensure the header rows are updated accordingly and re-run the clinical header step if needed.

---

## Step 8 — Validation (Required)

**When to run:** Always. This is the final gate before packaging. The validator checks all study files for format compliance, cross-file consistency, required fields, and valid values.

**Purpose:** Runs the cBioPortal study validator against the generated study directory and reports errors and warnings.

```bash
python $TOOLS_DIR/validation/validate_data.py \
  --study-directory $STUDY_DIR \
  --verbose
```

**Interpreting results:**
- **ERRORs** must be resolved before the study can be loaded into cBioPortal.
- **WARNINGs** should be reviewed and addressed where possible.
- A clean validation report (no errors) is required for the final package.

**If the cBioPortal validator script is installed separately** (e.g., via the cBioPortal backend repo), use:

```bash
python /path/to/cbioportal/core/src/main/scripts/importer/validateData.py \
  -s $STUDY_DIR \
  -n \
  -v
```

---

## Final Packaging

Once all steps above complete without errors, create the final study archive:

```bash
cd $(dirname $STUDY_DIR)
tar -czf ${STUDY_ID}_final.tar.gz $(basename $STUDY_DIR)
```

The archive is ready for import into cBioPortal via the standard data loading pipeline.

---

## Tool Run Order Summary

| Step | Tool | Required | Condition |
|------|------|----------|-----------|
| 1 | `hugo-symbol-corrector` | Conditional | MAF data present and sourced from Excel |
| 2 | `GN-annotation-wrapper` | Conditional | MAF data present |
| 3 | `oncotree-code-converter` | **Always** | — |
| 4 | `add-clinical-header` | Conditional | Clinical header rows missing |
| 5 | `generate-case-lists` | **Always** | — |
| 6 | `zscores` | Conditional | Expression data present |
| 7 | `TMB` | Optional | MAF data present, TMB not in clinical data |
| 8 | `validation` | **Always** | — |
