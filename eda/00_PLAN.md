# Plan: 10 Government Health-Facility Datasets → Queryable RAG Database

## Goal

Merge 10 Indian government health-facility datasets into one canonical, provenance-tracked database
that an LLM agent can query in natural language — including aggregations, geo filters, and
"where did this fact come from?".

## Starting state (verified 2026-08-02)

| Key | File | Rows | Cols |
|---|---|---|---|
| NHA | `1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv` | 323,461 | 46 |
| PHC | `21_June_2024_AM_PHC.csv` | 31,958 | 9 |
| PMGSY | `21_JULY_23_SRK_PMGSY_validated_homogenized.csv` | **13,700** ✓ | 24 |
| PMJAY | `18_MAY_23_SRK_PMJAY_validated_and_standardized.csv` | 11,285 | 78 |
| NIN | `22_MAY_22_AP_NIN.csv` | 10,612 | 25 |
| CDAC_BB_B | `CDAC_BB_DATASET - Sheet1.csv` | 5,889 | 10 |
| CDAC_BB_A | `16_MAY_AR_CDAC_BB_DATASET.csv` | 5,680 | 12 |
| CHC | `21_June_2024_AM_CHC.csv` | 4,237 | 9 |
| CGHS | `18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv` | 1,984 | 26 |
| NHP | `8_JULY_23_SRK_NHP_validated_and_standardized.csv` | 1,350 raw → **648** ✓ | 29 |

✓ = row count verified by Phase 1 EDA. Unmarked counts are naive `wc -l` and are **upper bounds** —
files with newlines embedded in quoted fields have inflated raw line counts.

### Known problems found during recon

1. **`CDAC_BB_A` and `CDAC_BB_B` are near-duplicates.** 5,467 of 5,539 distinct names overlap.
   `_B` has 209 more rows; `_A` has two extra columns (`District`, `dist_name`). Only `_A` was used
   in the existing merge. Decide which wins, or union them.
2. **A prior merge exists but is out of scope.** `master_merger.py` → `healthcare_master_dataset.csv`
   (393,980 × 142). **Decision: ignore it entirely.** Everything is built from the 10 raw CSVs. The
   file and script stay on disk untouched for the existing dashboard; no phase reads from them, and
   no phase is allowed to treat its output as ground truth.
3. **State names are inconsistent across every dataset.** `Andaman and Nicobar` /
   `ANDAMAN AND NICOBAR ISLANDS` / `ANDAMAN & NICOBAR`; distinct-state cardinality ranges 29–37.
   All joins depend on resolving these to LGD codes.
4. **NHP is malformed** — BOM, an embedded newline inside the header (`"S.\n  No."`), 10 trailing
   `Unnamed:` columns, and 1,350 physical lines for 999 logical rows.
5. **`M1_emp` … `S16_emp` / `_upg` specialty codes have no codebook.** NHA and PMJAY both use them.
   Decoding these is required for any specialty question and we currently have no key.

## Architecture decision

**Hybrid SQL + vector, not pure vector RAG.** Embedding 400K facility rows and retrieving top-k
cannot answer "how many 24x7 ABDM-enabled hospitals in Bihar offer cardiology" — that is an
aggregation over the full table, not a similarity search. Pure vector RAG on structured registry
data is the standard failure mode here.

```
                    ┌─────────────────────────────┐
                    │   Claude agent (tool use)    │
                    └──────────┬──────────────────┘
             ┌─────────────────┼──────────────────┐
             ▼                 ▼                  ▼
      run_sql(duckdb)   search_facilities()   get_schema_card()
             │                 │
             ▼                 ▼
      canonical DuckDB    vector index over
      (narrow tables)     "facility cards"
```

- **SQL path** handles ~90% of real questions: counts, filters, group-bys, geo radius, coverage gaps.
- **Vector path** handles entity finding: "the district hospital near Kalyan", misspelled names,
  specialty phrasing that doesn't match the code vocabulary.
- **Schema card** is a hand-written semantic layer (~40 curated columns with descriptions, enum
  values, and 15 few-shot question→SQL pairs). The agent never sees the raw 142-column table —
  that is what makes text-to-SQL reliable.

### Target schema (narrow, not wide)

| Table | Purpose |
|---|---|
| `facility` | One row per resolved real-world facility. uid, canonical name, geo, LGD codes, type, ownership. |
| `facility_source_record` | Provenance. Which source rows map to which uid, match method, confidence, raw JSON of the original row. |
| `facility_specialty` | Long form: (uid, specialty_code, specialty_name, status ∈ empanelled/upgraded). |
| `facility_attribute` | Key/value long tail, so adding dataset #11 never needs a migration. |
| `dim_state`, `dim_district` | LGD code crosswalk — the fix for problem #3. |
| `dim_specialty` | Codebook for `M*`/`S*` — the fix for problem #5. |
| `facility_embedding` | Vector index over a synthesized text card per facility. |
| `v_facility_public` | **PII-free view. The agent's SQL tool binds to this, not to base tables.** NIN carries internal staff names in `Coder`. |

The wide 142-column table stays available as a materialized view for the dashboard, but it is not
what the agent queries.

## Phases

### Phase 1 — Per-dataset EDA (parallel)
One session per dataset using `eda/01_DATASET_EDA_PROMPT.md`. Eight units of work (CDAC_BB_A+B share
a session; PHC+CHC share a session). Each emits `profile.json`, `field_map.yaml`, `PROFILE.md`,
`issues.md`, `questions.md` into `eda/<KEY>/`.

**Exit criteria:** all 10 `field_map.yaml` files exist and every source column is either mapped to a
canonical field, explicitly dropped with a reason, or listed as an open question.

### Phase 2 — Harmonization
*Revised after Phase 1 — see `02_PHASE1_FINDINGS.md` for the evidence behind each item.*

1. **Correct ingest per dataset.** Use the exact `read_kwargs` recorded in each `profile.json`.
   Naive line counts were wrong for 5 of 6 profiled units. Drop blank rows using a
   non-index column mask — `dropna(how='all')` silently fails on NIN.
2. Merge the 10 field maps into one `canonical_schema.yaml`.
3. **Purge derived columns** (~1/3 of all columns; verified list in the findings doc).
4. Build LGD state/district crosswalks from the official LGD directory.
5. **Derive `facility_type`** from name tokens + source, never read it from source columns.
   Includes extracting `BSU` from CDAC names and re-deriving the PHC/CHC tier.
6. **Compute `geo_trust_score`** per row: in-bbox ∧ district-consistent ∧ not centroid-stacked ∧
   not sharing a point with an unrelated facility. Detect and fix axis transposition.
7. Build `dim_specialty` keyed on **`(code_system, code)`**.
8. Assign `source_snapshot_date` **from filenames** — the data does not carry usable dates.

Output: `harmonize.py` producing one long-form staging table with
`(source_dataset, source_row_id, canonical_field, value)`.

**Exit criteria:** every source row is representable in canonical fields; state/district resolve to
LGD codes for >95% of rows; every row carries a `geo_trust_score`.

### Phase 3 — Entity resolution
The hard part. Built from scratch — the prior merge is not consulted, not diffed against, and not
used as a baseline.

1. Hand-label ~300 candidate pairs as match/non-match. **Do this first** — without a labeled set
   there is no way to know whether 500m + fuzzy is right.
2. **Blocking is geo-primary** (Phase 1 finding — names are unusable on 17–62% of rows depending on
   dataset). Candidates from a ~1 km geo cell where `geo_trust_score` is high; fall back to
   `name + district + pincode` for low-trust rows. Name is a **scoring** signal, not a blocking key.
3. Score with multiple signals (name similarity, geo distance, address token overlap, type
   agreement, phone/email exact) rather than a single threshold. Note `phone` is near-useless for
   CDAC_BB — only 15.7% is dialable (3,611 rows destroyed by Excel scientific notation).
   Never match two rows that share a known centroid coordinate.
4. Measure precision/recall on the labeled set. Tune. Report the number.
5. Transitive closure → `facility_uid`. Keep every source row in `facility_source_record`.

**Exit criteria:** a stated precision/recall figure on the hand-labeled set. Match rates that look
surprising (e.g. two datasets with identical schemas matching at very different rates) must be
explained from the data, not accepted.

### Phase 4 — Load and index
`build_db.py` → DuckDB file. Generate one text card per facility (name, type, location, specialties,
programs) → embeddings → vector index. Add spatial index for radius queries.

### Phase 5 — Agent
Tools: `run_sql`, `search_facilities`, `get_schema_card`. Write a 50-question eval set spanning
lookup / aggregation / geo / provenance / multi-hop **before** tuning prompts, so agent quality is
measured rather than vibed.

## Phase 1 execution (decided)

**Split.** Subagents handle the six lighter units; the two heavyweight datasets get dedicated
sessions where context room matters most.

| Unit | Datasets | Who |
|---|---|---|
| 1 | PHC + CHC | subagent |
| 2 | CDAC_BB_A + CDAC_BB_B | subagent |
| 3 | CGHS | subagent |
| 4 | PMGSY | subagent |
| 5 | NIN | subagent |
| 6 | NHP | subagent |
| 7 | **NHA** (323K × 46) | manual session |
| 8 | **PMJAY** (78 cols) | manual session |

For units 7 and 8: open a fresh Claude Code session, paste `eda/01_DATASET_EDA_PROMPT.md` with
`{{DATASET_KEY}}` / `{{DATASET_FILE}}` substituted.
