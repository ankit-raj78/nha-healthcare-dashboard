# CDAC_BB_A — `16_MAY_AR_CDAC_BB_DATASET.csv`

**5,679 rows × 12 columns.** 5,680 physical lines (CRLF, no BOM, no embedded newlines, no
trailing blank column, no `Unnamed:N`). Naive `pd.read_csv` gets the shape right, but you
**must** pass `dtype=str, keep_default_na=False, na_values=[""]` — otherwise pandas turns the
literal string `NA` (a real Address value in 965 rows) into null and silently mangles `Phone`.

## What this is

A national roster of **blood banks and blood storage units in India**, scraped from the
**e-RaktKosh / NBTC portal run by C-DAC** (Centre for Development of Advanced Computing) for the
Ministry of Health & Family Welfare. Every row is one licensed blood centre or one Blood Storage
Unit attached to a government hospital. Coverage is all 37 states/UTs; the file is sorted by
state, with three later batches appended (row-index breaks at 4740, 5469, 5645), so it is a
concatenation of at least four scrapes rather than one clean pull.

The content is dated **2022 or later** — it contains the Andhra Pradesh districts created in the
2022 reorganisation (Bapatla, Palnadu, NTR, Konaseema, Eluru, Kakinada, Anakapalli, Alluri
Sitharama Raju, Annamayya, Nandyal, Sri Sathya Sai, Parvathipuram Manyam, Tirupati). There is no
date column; the filename says `16_MAY` and the file mtime is 2025-06-20.

## Columns

| column | role | fill | note |
|---|---|---|---|
| `State` | `state_raw` | 100% | 37 values, correctly spelled, UPPERCASE; one truncated (`DADRA & NAGAR HAVE`) |
| `Name` | `facility_name_raw` | 100% | 5,539 distinct; 73 rows have an ALL-CAPS state token spliced in |
| `Address` | `address_raw` | 100% | always ends `, Dist. <district>`; 965 rows are just `NA, <place>, Dist. <X>` |
| `Latitude` / `Longitude` | `latitude` / `longitude` | 100% | **100% inside India's bbox, 0 null, 0 zero, 0 swapped** |
| `Phone` | `phone` | 91.6% nominal / **15.7% real** | Excel destroyed 63.6% of them |
| `Email` | `email` | 70.1% | 28 structurally invalid |
| `Category` | `facility_ownership_raw` | 100% | 4 codes: Govt. 2768, Private 1621, Charitable/Vol 1190, Red Cross 100 |
| `new_longitude` / `new_latitude` | — | 100% | **derived artifact of a failed geocoding pass — drop** |
| `District` | `district_raw` | 100% | 699 values, current district names; 100% redundant with `Address` |
| `dist_name` | `district_alt_raw` (proposed) | 100% | 683 values, **legacy** district names; 43 truncated at 24 chars with a `*` |

## What it is good for

- **Geo joins.** `Latitude`/`Longitude` is the single best coordinate column in either CDAC file:
  5,679/5,679 inside `lon 68–98 / lat 6–38`, no nulls, no zeros, no swapped pairs. Median
  distance from a row to the centroid of its own district (computed from the file itself) is
  **6.3 km**, p90 43.4 km, only 0.9% beyond 150 km.
- **Ownership analysis.** `Category` is a clean, complete, 4-value controlled vocabulary with no
  nulls — rare in this corpus.
- **District-level rollups.** Two district vintages are present (`District` = post-2022,
  `dist_name` = legacy), which is exactly what you need to join to LGD codes of either era.
- **Blocking for entity resolution.** State + district + name are present on 100% of rows;
  0% of rows are unmatchable.

## What it is bad for

- **Anything needing a phone number.** Only 893 of 5,679 rows (15.7%) have a recoverable one.
- **Anything needing a pincode or a structured address.** No pincode column; only 93 rows
  (1.6%) even contain a 6-digit token, and 965 addresses are placeholder `NA`.
- **Counting "blood banks".** 1,443 rows (25.4%) are **Blood Storage Units** (`BSU` in the
  `Name`, 1,435 of them Govt.) — annexes of a licensed centre, not centres. Naive counts are
  ~34% inflated.
- **Being a source of record.** There is no source ID, no licence number, no snapshot date, and
  no primary key of any kind (see below).

## The three things that will bite you

1. **`new_latitude` / `new_longitude` are a trap, twice over.** They are the output of an earlier
   geocoding pass, and they are wrong in two independent ways. (a) **344 rows (6.1%) are not in
   India in either axis order** — row 9, AIIMS Mangalagiri, is `-157.862 / 21.30623`, which is
   Honolulu; row 114 is `-44.2575 / -2.55289`, which is Brazil. (b) For **rows 5469–5678 the two
   columns are transposed**: `new_longitude` holds the latitude and `new_latitude` holds the
   longitude (216 rows). Their p90 distance-to-district-centroid is **1,549 km** against 43 km for
   `Latitude`/`Longitude`. Drop both columns; do not "fall back" to them for the rows where
   `Latitude` looks odd.

2. **`Phone` is 84% dead, but looks 92% alive.** `notnull()` says 5,203 of 5,679. In reality
   3,610 rows are Excel scientific notation (`9.12E+09` — the low-order 8 digits are gone
   *permanently*), 1,042 are the literal `0` or `0.00E+00`, 168 are `########` (Excel's
   column-too-narrow render), and 3 are `#ERROR!`. Only **893 rows** (15.7%) hold a number you
   could dial. Anything that treats `Phone` as a match feature or a contact field will be wrong.

3. **This file is one of a near-identical pair, and it is the one to keep — but its text is
   damaged.** `CDAC_BB_DATASET - Sheet1.csv` (CDAC_BB_B) contains exactly the same 5,676
   facilities. Loading both double-counts the entire dataset. Choose this file for its geo,
   states and district columns — but be aware that a global uppercase-the-state find/replace
   corrupted **73 `Name` values** (`Lower ASSAM Hospital Blood Centre`), **416 `Address` values**
   and **22 `Email` values** (`lowerASSAMhospital@yahoo.in`) in this file only. The fix is to lift
   those strings from CDAC_BB_B, which has the correct casing. Full analysis and the merge rule
   are in **`RECONCILIATION.md`** in this directory.

## Entity-resolution readiness

| signal | value |
|---|---|
| has name | 100% |
| has coordinate | 100% (and 100% valid-in-India) |
| has state | 100% (37 correctly-spelled values) |
| has district | 100% (`District` column, and 99.98% re-derivable from `Address`) |
| has pincode | 0% |
| unmatchable rows | 0.00% |
| blocking key `state + district + name` viable | **yes** |

**Matchability of each field to another dataset**

- `Name` — *good* blocking token, *medium* as a discriminator. Highly conventionalised
  ("… Blood Centre", "… Blood Bank"), so token-overlap scores will be inflated; strip the
  facility-type suffix before scoring. 177 rows share a normalised name with another row.
- `Latitude`/`Longitude` — **the strongest signal here.** 100% present and plausible. But 1,030
  rows (18%) share a coordinate pair with at least one other row (top pair repeats 14 times),
  i.e. some coordinates are town centroids, not building locations. Use a 200–500 m radius with
  a name check, not a coordinate join.
- `State` + `District` — *good*. Both 100% present; use `District` for display and `dist_name`
  as a second alias so pre-/post-2022 renames still match.
- `Address` — *weak*. 17% are placeholders; no pincode; no structure beyond the trailing
  `Dist. <X>`.
- `Phone` / `Email` — *do not use for matching* (15.7% and 70.1% usable, and both are shared
  across facilities).

**No primary key exists.** `Name` has 140 duplicate rows; `Email` is null in 1,698 and repeated
1,745 times; even `(Name, Address, Latitude, Longitude)` has 3 duplicate rows. Synthesise a
surrogate key and retain the source row index as `source_facility_id`.

---
Reproduce every number above with:
`.venv/bin/python eda/CDAC_BB_A/scripts/profile_bb.py CDAC_BB_A` and
`.venv/bin/python eda/CDAC_BB_A/scripts/reconcile_a_b.py`
