# Phase 1 Findings — Consolidated

Six of eight units complete (subagent-profiled). NHA and PMJAY pending manual sessions.
Every figure below was independently spot-verified against the source CSVs.

## Verified row counts

| Unit | Naive `wc -l` | **True rows** | Delta | Cause |
|---|---:|---:|---:|---|
| NHP | 1,350 | **648** | −702 | 351 trailing blank records + 350 in-field newlines |
| PMGSY | 14,900 | **13,700** | −1,200 | 1,197 in-field newlines + 2 blank rows |
| PHC + CHC | 36,195 | **36,174** | −21 | 21 rows verbatim in both files |
| CGHS | 1,984 | **1,983** | −1 | header |
| NIN | 10,612 | **10,327** | −285 | 81 in-field newlines + 203 blank rows (**3 interior**) |
| CDAC_BB (A∪B) | 11,569 | **5,678** | −5,891 | B is A re-appended; see below |
| **Subtotal** | **76,610** | **68,510** | **−8,100** | 10.6% of these rows were phantom |
| NHA | 323,461 | *pending* | | |
| PMJAY | 11,285 | *pending* | | |

**Naive line counts were wrong for 5 of 6 units.** Any pipeline that trusts `wc -l` or a default
`pd.read_csv` ingests thousands of nameless phantom facilities. NIN is the nastiest: its 203 blank
rows survive `dropna(how='all')` because a stale index column is never null.

## Decision: CDAC_BB — use A patched from B, do not union

`CDAC_BB_DATASET - Sheet1.csv` is not a second snapshot. Rows 0–5678 are byte-identical records in
identical order to `16_MAY_AR_CDAC_BB_DATASET.csv` (`Phone` and `Category` match 5,679/5,679), and its
210 "extra" rows are a verbatim re-append of its own rows 5469–5678. **Neither file contains a
facility the other lacks.** A union adds 0 facilities and 210 duplicates.

Pipeline: take A, copy `Name`/`Address`/`Email` positionally from B (517 field repairs — A ran a
global uppercase-the-state find/replace that leaked into other fields, e.g. `Lower ASSAM Hospital`),
drop `new_latitude`/`new_longitude`, drop 1 exact dupe → **5,678 × 10**.

## Cross-dataset conclusions that rewrite the plan

### 1. Geo-primary blocking is settled, not provisional

Four datasets independently show names are too weak to block on:

| Dataset | Name defect | Geo quality |
|---|---|---|
| PHC | 62% carry zero place info after stripping type words | 100% valid |
| CHC | 57% ditto | 100% valid |
| PMGSY | 29.5% named only a type word (`CHC`, `Dispensary`) | 100% valid, facility-precision |
| NHP | 17.6% generic (`government medical college` ×82) | 100% valid |
| NIN | 43% carry no facility-type keyword | 97.9% in-bbox |

A ~1.1 km geo cell isolates 95% of PHC/CHC rows; `name + district` isolates 39%.
**Block on geo, score on name.** The original plan had these the other way round.

### 2. But "in-bbox" is not a validity test — geo needs a trust score

Every dataset has geo that passes a bbox check and is still wrong:

- **Centroid stacking** — CGHS: 109 rows on 10 administrative centroids (37 on the Andhra Pradesh
  state centroid). NIN: 1,293 rows share a coordinate with a *different* facility (one point carries
  57 distinct Salem hospitals). NHP: 7 rows on 3 shared points, one being the Tamil Nadu centroid.
- **District inconsistency** — NIN: 114 in-bbox rows sit >500 km from their own state's centroid;
  59 of Rewari district's 89 rows are not in Rewari.
- **Transposition** — CDAC `new_latitude`/`new_longitude` are swapped from row 5469 onward (verified:
  210 latitude values >50°) and 344 rows fall outside India in either orientation.
- **Foreign coordinates** — CGHS has 2 rows in the USA; NIN has one in Las Vegas; CDAC_BB_B has rows
  in Turkey, Poland, Singapore.

**New Phase 2 deliverable:** `geo_trust_score` per row = in-bbox ∧ consistent with stated district ∧
not centroid-stacked ∧ not sharing a point with an unrelated facility. Phase 3 blocks on geo **only**
where the score is high; low-trust rows fall back to name+district+pincode.

### 3. `facility_type` must be derived, never read from source

- **PHC/CHC**: the tier distinction exists *only in the filename*. `FAC_CATEGO` is the constant
  `'Medical'` in both. The keyword rule that split them leaks — West Bengal shows 840 PHCs and 16
  CHCs because its CHC-equivalent tier is named "Block Primary Health Centre". 4.1% of union rows
  carry an untrustworthy tier label.
- **PMGSY**: `MASTER_FACILITY_CATEGORY_NAME` is the constant `'Medical'`; `SUB_CATEGORY` is weak —
  2,546 of 6,393 "Community Health Centre" rows have no CHC token in the name.
- **CDAC_BB**: 1,448 rows (25.5%) are Blood Storage Units, flagged only by a `BSU` token inside
  `Name`. Facility counts are ~34% inflated without extracting it.
- **NHP**: type is not a column at all — inject the constant `MEDICAL_COLLEGE`.

### 4. Specialty codebook — composite key required

`M1–M10` / `S1–S16` appears in **NHA, PMJAY, and CGHS** (745 CGHS rows). CGHS *also* carries a
second, mutually exclusive 22-token two-letter vocabulary (`BM`, `ER`, `MC`, `SB`, `SU`…) on 1,001
rows — **zero rows mix the two families**. Ranges differ by source (CGHS `M1–M8`, NHA `M1–M10`).

`dim_specialty` therefore needs a composite key **`(code_system, code)`**, not `code`. Without the
discriminator, CGHS's two-letter `SC` collides with the numeric family's `S3`.

PMJAY is the Rosetta stone — the only source carrying the codes and free-text specialty names side
by side. Decoding it unlocks specialty queries across ~335K facilities.

### 5. PII requires an internal/public schema split

NIN's `Coder` column holds first names of five identifiable internal staff (tanmay, shalmali,
mallika, sweta, sid), on 600 rows. This cannot be reachable by the agent. Phase 4 must build a
public view that excludes PII, and the agent's SQL tool must be bound to that view — not to the
base tables.

### 6. Roughly a third of all columns are derived noise

Verified droppable: PMGSY 8 of 24 (the "parsed address" set is a byte-identical copy of source
columns; `Formatted Address` is reconstructible exactly). CGHS 8 of 26 (all eight similarity metrics
compare `Address` vs `address_py`, and `Address` is itself just `Name + District + State` — the
comparison is circular; AUC against geocode-correctness proxies is 0.39–0.69, i.e. random).
NHP 3 empty + `Postcode_py` (byte-identical to `Postcode`). NIN 2 index columns. CDAC `new_*`.

### 7. No usable snapshot dates

CGHS's two date columns are the constant literal `-NA` on all 1,983 rows. PHC/CHC, NHP, NIN and
CDAC_BB have no date column at all. Only PMGSY has a real one (`FILE_UPLOAD_DATE`, 2019-01-09 →
2022-11-26). **`source_snapshot_date` must be assigned from filenames**, not read from data.

### 8. Known dedup traps

- Deduplicating PHC on `(district, name)` destroys **15,701 rows — 49% of the dataset**. True
  near-dupe count is 134.
- PMGSY's `HAB_CODE` looks like a PK but is a habitation key (12,092 distinct / 13,700). One code
  has 48 rows spanning 5.8 km. Joining on it would collapse 1,608 distinct facilities.
- CGHS's `Hospital_Id` is unique but is an *application* ID — 32 rows form 15 groups with identical
  name/district/geo but different IDs.
- NIN has an undocumented `NOTIONAL ` name prefix on ~72 rows that hides real duplicates.

## Open questions blocking Phase 2

1. **What do the `M*`/`S*` specialty codes mean?** (blocks all specialty queries) — PMJAY session
   should answer.
2. **Is a medical college with an attached hospital one entity or two?** Only NHP forces this, but
   the answer determines whether its 648 rows collide with hospital rows in other sources.
3. **Is PMGSY's `BLOCK_ID` / PHC's `BLOCK_ID` the LGD block code?** If yes, it alone resolves 43.6%
   of CHC rows.
4. **Why is NIN a 5.4% extract** (`SrNo` 1→192,898 over 10,327 rows) of a larger register? Its
   absences must not be read as "no facility there".
5. **Do PHC/CHC and PMGSY share upstream provenance?** Both use the identical constant `'Medical'`
   category vocabulary. If they cover overlapping facilities, PMGSY's 13,700 rows add less genuine
   coverage than the raw count suggests. Test directly in Phase 3.
