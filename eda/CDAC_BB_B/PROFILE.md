# CDAC_BB_B — `CDAC_BB_DATASET - Sheet1.csv`

**5,889 rows × 10 columns.** 5,890 physical lines (CRLF, **no trailing newline**, no BOM, no
embedded newlines, no `Unnamed:N`, no trailing blank column). Naive `pd.read_csv` gets the shape
right, but you **must** pass `dtype=str, keep_default_na=False, na_values=[""]` — otherwise
pandas turns the literal string `NA` (a real Address value in 965 rows) into null and mangles
`Phone`.

> **Read `eda/CDAC_BB_A/RECONCILIATION.md` before using this file.** It is a near-twin of
> `16_MAY_AR_CDAC_BB_DATASET.csv` (CDAC_BB_A). Rows 0–5678 are the *same records in the same
> order* as CDAC_BB_A's rows 0–5678. Rows 5679–5888 are a verbatim re-append of this file's own
> rows 5469–5678. **This file contains zero facilities that CDAC_BB_A does not contain.**

## What this is

The same national roster of **blood banks and blood storage units in India** scraped from the
**e-RaktKosh / NBTC portal run by C-DAC** for the Ministry of Health & Family Welfare. The
filename (`- Sheet1`) says it was exported from a Google Sheet; the mtime is 2025-11-23 but the
*content* is not newer than CDAC_BB_A — it is the same scrape re-exported, with a 210-row block
accidentally pasted in twice.

The content is dated 2022 or later (it contains the AP districts created in the 2022
reorganisation). There is no date column.

## Columns

| column | role | fill | note |
|---|---|---|---|
| `State` | `state_raw` | 100% | 36 values, **5 misspelled**, Sikkim missing (mislabelled Rajasthan) |
| `Name` | `facility_name_raw` | 100% | 5,539 distinct over 5,889 rows; **casing is cleaner than A's** |
| `Address` | `address_raw` | 100% | always ends `, Dist. <district>`; 965 rows are `NA, <place>, Dist. <X>` |
| `Latitude` / `Longitude` | `latitude` / `longitude` | 99.6% | 25 null, 5 outside India |
| `Phone` | `phone` | 91.9% nominal / **15.7% real** | Excel destroyed 64.2% of them |
| `Email` | `email` | 71.1% | 28 structurally invalid; cleaner casing than A's |
| `Category` | `facility_ownership_raw` | 100% | 4 codes: Govt. 2787, Private 1691, Charitable/Vol 1308, Red Cross 103 |
| `new_longitude` / `new_latitude` | — | 100% | **derived artifact of a failed geocoding pass — drop** |

There is **no `District` column** (CDAC_BB_A has one). It is recoverable for 5,888/5,889 rows by
parsing the trailing `Dist. <X>` out of `Address`. CDAC_BB_A's second district column,
`dist_name` (the legacy/LGD spelling), has **no equivalent here and cannot be recovered.**

## What it is good for

- **Repairing CDAC_BB_A's text fields.** This is its one unique value. A global
  uppercase-the-state find/replace damaged 73 `Name`, 416 `Address` and 22 `Email` values in
  CDAC_BB_A (`Lower ASSAM Hospital Blood Centre`, `lowerASSAMhospital@yahoo.in`). This file has
  the correct casing for all of them, plus the correct spelling `Serchhip` where A has `Serchipp`.
- **Ownership analysis.** `Category` is a clean, complete, 4-value vocabulary with no nulls
  (byte-identical to CDAC_BB_A on the shared rows).
- Everything else it does, CDAC_BB_A does better.

## What it is bad for

- **State-level anything.** Five of 36 state labels are misspelled and will not join to any LGD
  or census table: `Andra Pradesh` (326 rows), `Gujrat` (382), `Chattisgarh` (181),
  `Jammu and Kasmir` (66), `Lakshwadeep` (1). And Sikkim does not exist in this file — its 5 rows
  are labelled `Rajasthan`.
- **Row counting.** 213 rows are duplicates on `(Name, Address)`; 210 of those are one block
  pasted twice. Any `COUNT(*)` off this file is wrong by 210.
- **Phones, pincodes, structured addresses.** Same as CDAC_BB_A: 15.7% usable phones, 1.9% of
  addresses contain a 6-digit token, no pincode column.
- **Counting "blood banks".** 1,449 rows (24.6%) are Blood Storage Units flagged only by a `BSU`
  token inside `Name`.

## The three things that will bite you

1. **It looks like the bigger, newer file. It is neither.** 5,889 > 5,679 and the mtime is five
   months later, so the obvious move is to prefer this file. That is wrong: rows 5679–5888 are a
   byte-for-byte re-append of rows 5469–5678 (identical `Name`, `Address`, `Category`, `State`,
   `Email`, `new_*`; `Latitude`/`Longitude` differ only by rounding — the two copies are a median
   of **0.4 metres** apart). It has 210 extra *rows*, not 210 extra *facilities*.

2. **Sikkim silently became Rajasthan.** Rows 3716–3720 — five Gangtok/Namchi/Geyzing blood
   centres whose `Address` says "East Sikkim", "west sikkim" — carry `State = Rajasthan`. A
   state-filtered query returns zero blood banks in Sikkim and five phantom ones in Rajasthan,
   with no null to warn you.

3. **`new_latitude` / `new_longitude` are a trap, twice over.** They are an earlier geocoding
   pass and they are wrong in two independent ways. (a) **344 rows (5.8%) are not in India in
   either axis order** — row 9, AIIMS Mangalagiri, is `-157.862 / 21.30623` (Honolulu); row 114 is
   `-44.2575 / -2.55289` (Brazil). (b) For **rows 5469–5888 the two columns are transposed**:
   `new_longitude` holds the latitude and `new_latitude` holds the longitude (426 rows). Drop both.

## Entity-resolution readiness

| signal | value |
|---|---|
| has name | 100% |
| has coordinate | 99.58% (99.49% valid-in-India) |
| has state | 100%, but 5 spellings broken and 5 rows mislabelled |
| has district | no column; 99.98% re-derivable from `Address` |
| has pincode | 0% |
| unmatchable rows | 0.00% (name + parsed district always available) |
| blocking key `state + district + name` viable | **yes, after spell-correcting `State`** |

**Matchability of each field to another dataset**

- `Name` — *good* blocking token, *medium* discriminator, and **better than CDAC_BB_A's**
  (correct casing). 387 rows share a normalised name with another row, but 210 of those are the
  duplicated block.
- `Latitude`/`Longitude` — *good but not complete*: 25 rows have none and 5 are outside India
  (row 482 → Turkey, row 4651 → Singapore). 1,054 rows share a coordinate pair with another row,
  so treat coordinates as town-level for a meaningful minority. CDAC_BB_A has a valid coordinate
  for all 30 of the rows that fail here.
- `State` — *unreliable as given*; must be spell-corrected and the Sikkim block repaired first.
- district parsed from `Address` — *good*, 5,888/5,889.
- `Address` — *weak*: 17% placeholders, no pincode.
- `Phone` / `Email` — *do not use for matching*.

**No primary key exists.** `(Name, Address)` has 213 duplicate rows; even
`(Name, Address, Latitude, Longitude)` has 3. Synthesise a surrogate key.

**Do not load this file and CDAC_BB_A into the same canonical table.** Doing so double-counts
5,676 facilities and quadruple-counts 210 of them.

---
Reproduce every number above with:
`.venv/bin/python eda/CDAC_BB_B/scripts/profile_bb.py CDAC_BB_B` and
`.venv/bin/python eda/CDAC_BB_A/scripts/reconcile_a_b.py`
