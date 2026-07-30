# Validator and clinical pitfalls for local cBioPortal dataset generation

## Validator environment

Run the validator only through the stable package CLI:

```bash
uv run --project "$CBIO_CURATION_ASSISTANT_HOME" cbio-curation validate-study \
  --study-id "<study_id>"
```

The command creates or reuses `cbioportal_core_validator/.venv` from the
validator lockfile. The first run can require package-index access. Never
install validator requirements into the main project environment and do not
fall back to direct script or `PYTHONPATH` invocation. Report environment
bootstrap failures as blockers.

## Interpreting validator exit status

A validator run can exit non-zero even when the study is usable.

- `exit_code = 1` with `Validation of data failed.` means real validation errors remain.
- `exit_code = 3` with `Validation of data succeeded with warnings.` should be reported as success-with-warnings, not as a failed validation run.

Always key off both the exit code and the validator summary text before deciding whether the study is blocked.

## Clinical-file pitfalls

### Duplicate clinical attributes across levels

Do not define the same clinical attribute name in both `data_clinical_patient.txt` and `data_clinical_sample.txt` unless you intentionally want the same attribute at both levels and know the validator accepts it. In practice, the validator can reject this with:

`Clinical attribute is defined both as sample-level and as patient-level`

Use distinct names when the concepts differ by level, e.g. keep sample-level `SUBTYPE` and rename the patient-level field to something like `PATIENT_SUBTYPE`.

### Patient rows without samples

If the source clinical table contains patients that do not appear in the generated sample file, filter them out before writing `data_clinical_patient.txt`. Otherwise the validator warns that clinical data exists for patients with no samples.

A safe pattern is:

1. build the sample file first
2. collect the emitted `PATIENT_ID` set from the sample rows
3. filter the patient-level dataframe to that set before writing the patient file

## Cancer type color field

`cancer_type.txt` requires a real CSS/X11 color keyword in column 3. Placeholder values like `dedicated_color` will fail validation.
