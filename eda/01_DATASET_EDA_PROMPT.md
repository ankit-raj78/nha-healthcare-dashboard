# Per-Dataset EDA Prompt

Copy everything below the line into a **fresh Claude Code session**, one session per dataset.
Replace `{{DATASET_FILE}}` and `{{DATASET_KEY}}` with values from the table.

| DATASET_KEY | DATASET_FILE |
|---|---|
| NHA | `1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv` |
| NHP | `8_JULY_23_SRK_NHP_validated_and_standardized.csv` |
| CDAC_BB_A | `16_MAY_AR_CDAC_BB_DATASET.csv` |
| PMJAY | `18_MAY_23_SRK_PMJAY_validated_and_standardized.csv` |
| CGHS | `18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv` |
| PMGSY | `21_JULY_23_SRK_PMGSY_validated_homogenized.csv` |
| PHC | `21_June_2024_AM_PHC.csv` |
| CHC | `21_June_2024_AM_CHC.csv` |
| CDAC_BB_B | `CDAC_BB_DATASET - Sheet1.csv` |
| NIN | `22_MAY_22_AP_NIN.csv` |

Run `CDAC_BB_A` and `CDAC_BB_B` in the **same** session (they are ~99% duplicates — the session's job
includes deciding which one wins). Same for `PHC` + `CHC` (identical 9-column schema).

---

You are doing exploratory data analysis on ONE dataset that will become part of a queryable
canonical database of Indian health facilities. Nine other datasets are being profiled in parallel
by other sessions. Your output feeds an automated harmonization step, so the output contract below
is strict — another program will read your files.

**Dataset:** `{{DATASET_FILE}}`
**Key:** `{{DATASET_KEY}}`
**Working dir:** `/Users/ankitraj2/asar master data`
**Write outputs to:** `eda/{{DATASET_KEY}}/`
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

**`eda/{{DATASET_KEY}}/profile.json`** — machine-readable. Shape:
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

**`eda/{{DATASET_KEY}}/field_map.yaml`** — the harmonization contract:
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

**`eda/{{DATASET_KEY}}/PROFILE.md`** — 1–2 pages a human reads. What this dataset *is*, what
program produced it, what it's good for, what it's bad for, and the three things that would bite
someone who joined it naively.

**`eda/{{DATASET_KEY}}/issues.md`** — every data-quality defect, each with a concrete row example
(include row index and the actual bad value) and a proposed fix. Severity-rank them.

**`eda/{{DATASET_KEY}}/questions.md`** — things you could not determine and that need a human or an
external source: unexplained codes, ambiguous columns, suspected-but-unconfirmed meanings. Be
specific; a vague question is useless.

## Rules

- Every quantitative claim must come from code you actually ran. No estimates presented as facts.
- If something is ambiguous, put it in `questions.md` rather than picking an interpretation silently.
- Do not write cleaning/merging code. Profiling only.
- Do not read the other 9 datasets. Your context is one dataset; that's the point.
- Keep any exploratory scripts in `eda/{{DATASET_KEY}}/scripts/` so the numbers are reproducible.
