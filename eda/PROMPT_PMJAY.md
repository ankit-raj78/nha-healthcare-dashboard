You are doing exploratory data analysis on ONE dataset that will become part of a queryable
canonical database of Indian health facilities. Nine other datasets are being profiled in parallel
by other sessions. Your output feeds an automated harmonization step, so the output contract below
is strict — another program will read your files.

**Dataset:** `18_MAY_23_SRK_PMJAY_validated_and_standardized.csv`
**Key:** `PMJAY`
**Working dir:** `/Users/ankitraj2/asar master data`
**Write outputs to:** `eda/PMJAY/`
**Python:** use `.venv/bin/python`

## Context you need

Every one of the 10 datasets describes the same real-world entity: an Indian health facility
(hospital, PHC, CHC, blood bank, medical college, dispensary). They come from different government
programs, were collected in different years, and have wildly different schemas and naming
conventions. Downstream we will resolve them into one canonical entity table with provenance, load
it into DuckDB, and put an LLM agent on top that writes SQL and does semantic search.

Your job is NOT to clean the data. Your job is to **understand it precisely and report it in a form
that makes cleaning mechanical**. Do not modify the source CSV.

## Do this

### 1. Load it correctly
Establish the true shape before anything else. Watch for: BOM in the header, embedded newlines
inside quoted fields, `Unnamed: N` junk columns, trailing all-empty columns, mixed dtypes, thousands
separators in numerics, a leading unnamed index column. Report the row count you get vs `wc -l` and
explain any gap. If the naive `pd.read_csv` is wrong, find the read that is right and record the
exact kwargs.

### 2. Profile every column
For each column: dtype, non-null count and %, distinct count, example values, and — for low
cardinality (<50) — the full value counts. For numerics: min/max/mean/percentiles. For dates: parsed
range and format. For free text: length distribution.

### 3. Assign a semantic role to every column
This is the most important step. For each column decide what it *means*, not what it's called.
Use the canonical vocabulary in the next section. Flag columns that are:
- **redundant** (two columns holding the same fact, e.g. `Latitude` vs `new_latitude`)
- **derived artifacts** of someone's earlier processing (similarity scores, match flags, `Auto Score`)
- **junk** (empty, constant, row numbers)
- **PII** (phone, email, personal names)
- **unknown** — say so explicitly, do not guess

### 4. Assess quality against reality
- Are lat/lon inside India's bbox (roughly lon 68–98, lat 6–38)? How many are 0/null/swapped/outside?
- Are state and district names spelled consistently? Give the exact distinct list for state.
- Are pincodes 6 digits and plausible?
- Is there a column that is unique and could serve as a source primary key? Verify uniqueness.
- **Are there duplicate rows within this dataset?** Exact dupes, and near-dupes on (name, geo).
  Quantify. This matters as much as cross-dataset dedup.
- Any column encoding a coded vocabulary (e.g. `M1_emp`, `S3_upg`, `FAC_CATEGO`)? Extract the
  complete distinct code list — we need to build a codebook and currently have no key for it.

### 5. Judge fitness for entity resolution
State plainly: which fields in this dataset can be used to match a row to the same facility in
another dataset, and how trustworthy each is. Name + geo + district is the expected blocking key —
say whether this dataset can support that, and what fraction of rows would be unmatchable.

## Canonical field vocabulary

Map source columns onto these names. If a source column doesn't fit, propose a new canonical name
in `field_map.yaml` under `proposed_new_fields` with a rationale — don't force a bad fit.

```
identity      facility_name_raw, facility_name_alt, source_facility_id
address       address_raw, street, locality, landmark, city, pincode, country
admin geo     state_raw, district_raw, subdistrict_raw, block_raw, village_raw,
              state_lgd_code, district_lgd_code
point geo     latitude, longitude, geo_source, geo_accuracy, altitude
classify      facility_type_raw, facility_ownership_raw, facility_category_raw
capacity      bed_count, admission_intake, is_24x7
programs      abdm_enabled, scheme_membership, empanelment_type, empanelment_status
clinical      specialty_list, specialty_code_empanelled, specialty_code_upgraded, accreditation
contact       phone, email, website
provenance    source_snapshot_date, source_sheet_name, record_status
derived       (anything that is a prior pipeline's output — mark, don't map)
```

## Output contract — write exactly these five files

**`eda/PMJAY/profile.json`** — machine-readable. Shape:
```json
{
  "dataset_key": "...",
  "source_file": "...",
  "read_kwargs": {"encoding": "utf-8-sig", "...": "..."},
  "n_rows": 0, "n_cols": 0, "raw_line_count": 0, "row_count_explanation": "...",
  "columns": [
    {"name": "...", "dtype": "...", "non_null": 0, "null_pct": 0.0, "n_distinct": 0,
     "examples": ["..."], "value_counts": {}, "semantic_role": "canonical_name|unknown|junk",
     "flags": ["redundant_with:X", "derived", "pii", "constant"], "notes": "..."}
  ],
  "duplicates": {"exact": 0, "near_dupe_name_geo": 0, "method": "..."},
  "geo_quality": {"valid_in_india": 0, "null": 0, "zero": 0, "out_of_bbox": 0, "possibly_swapped": 0},
  "candidate_primary_key": {"column": "...", "is_unique": true},
  "coded_vocabularies": {"COLUMN_NAME": ["code1", "code2"]},
  "er_readiness": {"has_name": true, "has_geo_pct": 0.0, "has_district": true,
                   "unmatchable_row_pct": 0.0, "blocking_key_viable": true}
}
```

**`eda/PMJAY/field_map.yaml`** — the harmonization contract:
```yaml
dataset_key: NHA
source_column_map:
  hospital_name: {canonical: facility_name_raw, confidence: high, transform: strip}
  State_name:    {canonical: state_raw, confidence: high, transform: "upper, normalize_lgd"}
  Auto Score:    {canonical: null, disposition: drop, reason: "prior pipeline artifact"}
proposed_new_fields:
  - name: ...
    reason: ...
unmapped_columns: [...]
```

**`eda/PMJAY/PROFILE.md`** — 1–2 pages a human reads. What this dataset *is*, what
program produced it, what it's good for, what it's bad for, and the three things that would bite
someone who joined it naively.

**`eda/PMJAY/issues.md`** — every data-quality defect, each with a concrete row example
(include row index and the actual bad value) and a proposed fix. Severity-rank them.

**`eda/PMJAY/questions.md`** — things you could not determine and that need a human or an
external source: unexplained codes, ambiguous columns, suspected-but-unconfirmed meanings. Be
specific; a vague question is useless.

## Dataset-specific priorities for PMJAY

78 columns — the widest and most information-rich dataset. Several distinct column families:

- **Specialty codes (cols 14-59)**: `M1_emp`..`M8_emp`, `S1_emp`..`S16_emp` AND a parallel `_upg`
  set (`M1_upg`..`S7_upg`). These share a vocabulary with NHA but no codebook exists. Extract the
  complete distinct value set, determine the encoding, and determine what `_emp` (empanelled) vs
  `_upg` (upgraded) means in practice — how often does a facility have one but not the other?
  Cross-check against the text columns `Specialities Empanelled`, `Specialities Upgraded`, and
  `Specialities_Upgraded_or_Empanelled`. If those text columns decode the numeric codes, that is a
  MAJOR finding — it would give us the codebook for both PMJAY and NHA. Chase it hard and report
  the mapping explicitly if you find it.
- **Geo family**: `API Latitude`/`API Longitude` vs `gmaps_Latitude`/`gmaps_Longitude` plus
  `gmaps_Accuracy` and `Auto Score`. Compare fill rates, agreement, and India-bbox validity for each
  pair. Recommend which is authoritative and under what rule.
- **Address family**: `Hospital Address`, `Manual Hospital Address`, `address_py`,
  `Formatted Address`, plus parsed components `Road`/`Locality`/`District`/`City`/`State`/`Country`/
  `Zipcode`/`pincode_py`. Map the lineage — which are raw, which are geocoder output, which are
  human-entered. Report fill rates for all.
- **Name family**: `Hospital Name` vs `Manual Hospital Name` — fill rates and disagreement rate.
- **Admin geo**: `Manual District`/`Manual state` vs `District`/`State`. Give the exact distinct
  state list (prior recon found 36 distinct, all uppercase) and quantify old/new disagreement.
- **Suspicious columns**: `Types of Employees`, `Test extract`, `is_RU`, `Auto Score`. Determine what
  each holds; several are likely prior-pipeline artifacts. `is_RU` is probably rural/urban — verify.
- `Sr No` — check uniqueness as a source key.
- Note the header BOM on `﻿Sr No`.

## Rules

- Every quantitative claim must come from code you actually ran. No estimates presented as facts.
- If something is ambiguous, put it in `questions.md` rather than picking an interpretation silently.
- Do not write cleaning/merging code. Profiling only.
- Do not read the other 9 datasets. Your context is one dataset; that's the point.
- Keep any exploratory scripts in `eda/PMJAY/scripts/` so the numbers are reproducible.
