# NIN — `22_MAY_22_AP_NIN.csv`

**10,327 logical rows × 25 columns** (24 real + 1 stale index). All numbers below come from
`eda/NIN/scripts/*.py`; the machine-readable form is `eda/NIN/profile.json`.

---

## What this dataset is

A **hand-curated national inventory of Indian public health facilities**, exported from a SQL
database and then worked over in a spreadsheet by a small team of named coders. It is not a raw
program registry like PMJAY or CGHS — it is a *research extract* that someone was actively
cleaning when the file was saved.

Three pieces of evidence pin down its provenance:

1. **It came out of MySQL, not Excel.** 3,834 cells hold the literal string `\N` — the
   `mysqldump` NULL marker — spread across `Address`, `street`, `landmark`, `locality`,
   `landline_number`, `altitude`, `District_Name`, `Taluka_Name` and `Block_Name`. Excel never
   writes that.
2. **It was then round-tripped through pandas.** Column 1 has an *empty* header (BOM only) and
   holds a strictly-increasing integer 0..10635 — a `df.to_csv()` index. It has 106 gaps, so 106
   rows were deleted after that export.
3. **It was then edited by hand in a sheet.** 203 rows are completely blank (200 trailing, 3
   interior), one `Manual_Pincode` is `#REF!`, and there are `Manually_added` / `Coder` /
   `Notes` columns filled in by five people.

`SrNo` runs 1..192,898 across only 10,327 rows, so this file is a **~5.4% extract of a much larger
parent register** that uses the same numbering. The 10,327 rows are not a contiguous slice of it.

The repository's own `README.md` glosses NIN as "National Inventory for Non-Communicable
Diseases". That is unverified — see `questions.md`.

**Dating.** `State_Name` uses `Jammu & Kashmir` with no Ladakh, and lists `Dadra & Nagar Haveli`
and `Daman & Diu` as two separate UTs. Both facts place the admin vocabulary **before
October 2019 / January 2020**, consistent with the `22_MAY_22` in the filename being a *2022*
curation pass over older source data.

---

## The two-pass structure (the thing that explains most of the file)

This is one dataset with **two populations layered on top of each other**, and almost every
oddity falls out of that.

**Pass 1 — the bulk (9,699 rows, 93.9%).** Machine-assembled. Auto `Health Facility Name`,
auto `Address`/`street`/`landmark`/`locality`, auto `pincode`, auto lat/lon, `\N` where the
source SQL was null. No coder ever touched these.

**Pass 2 — the curated tail (628 rows, 6.08%).** Rows where a human went and looked the facility
up. These are the only rows that carry `Non filled numbering`, `Manual Health Facility Name`,
`Manual_Address`, `Manual_Pincode`, `Manually_added`, `Coder`, or `Notes`. The markers are *not*
co-extensive — `Non filled numbering` and `Manual Health Facility Name` have identical masks
(623 rows), `Coder` covers 600, `Manually_added` only 526, `Notes` only 156.

### Auto vs. manual: which wins

| pair | auto fill | manual fill | both filled | disagree (normalized) |
|---|---|---|---|---|
| `Health Facility Name` / `Manual Health Facility Name` | 100.00% | 6.03% | 623 | **354 (56.82%)** |
| `Address` / `Manual_Address` | 79.83% | 5.13% | 125 | **125 (100.00%)** |
| `pincode` / `Manual_Pincode` | 90.07% | 5.08% | 161 | **50 (31.06%)** |

**The manual column is authoritative wherever it is populated.** Use `COALESCE(manual, auto)` for
all three, and keep the auto value as `*_raw` for audit. The evidence:

- Manual is never populated on a row where the auto value is absent-and-good; it is populated
  precisely where a coder was dispatched.
- The name disagreements are systematic *rewrites into house style*, not conflicts:
  `Piler Community Health Center` → `CHC Piler`, `Sub divisional Hospital Rajauli` → `SDH Rajauli`.
- On the 125 address rows where both exist, `Address` is a sentinel (`0`, `\N`) or a single town
  word in most cases, while `Manual_Address` is a full Google-Maps-formatted string
  (`DMCH Rd, Allalpatti, Laheriasarai, Darbhanga, Bihar`). 13 of them have a literal sentinel in
  `Address`. Median length: 12 chars auto, 32 chars manual.
- On the 50 pincode disagreements, the manual value literally appears inside `Manual_Address` in
  **9** cases; the auto value appears in **0**. Weak but one-directional.

**Caveat on `Manual_Pincode`:** confidence is only *medium*. 41 of the 50 disagreements are
unadjudicated, and 6 of the 525 values are not pincodes at all (`#REF!`, `Karnataka`, `Assam`,
plus three `State + pincode` strings).

### The human curation workflow

**5 coders**, from 9 raw case/whitespace variants: **tanmay 358, shalmali 175, mallika 57,
sweta 6, sid 4**. `Manually_added` is filled on **526 rows (5.09%)** and every non-null value is a
variant of yes (`Yes` 481, `yes` 25, `yes ` 12, `Yes ` 5, `Y` 3) — **there is no `No`**, so blank
means "not manually added". `Coder` is the more reliable "a human touched this row" flag: 73
tanmay rows have a `Coder` but a blank `Manually_added`.

**Is `Coder` PII? Yes — low sensitivity.** The values are the first names of five identifiable
internal staff, with no contact detail attached. It is employee-attribution metadata, not facility
data. Recommendation: retain in the internal provenance table for quality attribution; **exclude
from any user-facing or LLM-queryable view**, or replace with an opaque `coder_id`. (Note also
that 76 `Health Facility Name` values contain a doctor's personal name — `Dr. N. C. Joshi`,
`DR GROVERS NURSING HOME` — but those are business names and are not PII in the same sense.)

---

## What it's good for

- **Geo.** 97.86% of rows (10,106) have coordinates inside the India bbox. That is high, and the
  coordinates are real (median 6 decimal places).
- **A closed, complete facility-type vocabulary.** 13 values, 100% coverage, no nulls. Most of the
  ten datasets have nothing this tidy.
- **Pincode.** 90.07% filled and **every single one of the 9,302 non-null values is exactly 6
  digits with a valid Indian leading digit 1–8.** Zero malformed values. This is the cleanest
  column in the file and a strong secondary blocking key.
- **A real subdistrict/block hierarchy** — the only one of its depth here.
- **A stable, unique source PK.** `SrNo` is unique and 100% populated on all 10,327 rows.
- **Elevation.** 3,881 rows carry a genuine altitude, which no other admin field gives you.

### Admin hierarchy fill (the `\N` gap matters)

| level | raw non-null | **real** (excl. `\N`) | distinct |
|---|---|---|---|
| `State_Name` | 100.00% | **100.00%** | 34 |
| `District_Name` | 100.00% | **99.94%** (6 × `\N`) | 622 |
| `Taluka_Name` | 100.00% | **91.68%** (859 × `\N`) | 3,427 |
| `Block_Name` | 100.00% | **76.18%** (2,460 × `\N`) | 3,555 |

Every level reads as 100% filled until you strip `\N`. `Block_Name` is really only three-quarters
populated, and often holds an urban body (`COIMBATORE CORPN`, `CHENNAI ZONE X`) rather than a
rural block — treat it as low-confidence for joining.

**Exact distinct state list (34, spellings as they appear):** Andhra Pradesh, Arunachal Pradesh,
Assam, Bihar, Chandigarh, Chhattisgarh, Dadra & Nagar Haveli, Daman & Diu, Delhi, Goa, Gujarat,
Haryana, Himachal Pradesh, Jammu & Kashmir, Jharkhand, Karnataka, Kerala, Madhya Pradesh,
Maharashtra, Manipur, Meghalaya, Mizoram, Nagaland, Odisha, Puducherry, Punjab, Rajasthan,
Sikkim, Tamil Nadu, **Telengana**, Tripura, Uttar Pradesh, Uttarakhand, West Bengal.

Spelling is consistent and correctly cased throughout — the **only** state defect is `Telengana`
(173 rows), the wrong spelling of Telangana.

---

## What it's bad for

- **National coverage.** It is not a census of anything. Tamil Nadu has 2,736 rows; **Kerala has
  one** (`PHC CHITTAR`, Pathanamthitta). Delhi 619, Goa 9, Sikkim 4. Any per-state count computed
  from this file is meaningless.
- **Addresses.** `Address` has a median length of 12 characters. It is a fragment, frequently the
  facility type restated (`Community Health Center` 77 times, `CHC` 68 times). Not geocodable.
- **Facility classification.** `Facility Type` collapses two orthogonal axes onto one: function
  (`Community Health Center`, `Dispensaries`, `Post Partum Unit`) and bed-size band
  (`<100 Bedded Hospital`, `100-500 Bedded Hospital`, `>500 Bedded Hospital`). And `Others` is
  2,382 rows (23.07%) and is overwhelmingly private: 1,692 of those names (71%) contain
  `hospital`/`nursing home`/`clinic`/`NH` while only 27 contain a government marker
  (`Govt`, `District`, `Civil`, `CHC`, `PHC`, `Municipal`, `ESI`).
- **Ownership, capacity, specialties, schemes, ABDM, accreditation, email, website.** None of
  these exist in this dataset at all. It contributes identity + geo + admin only.
- **Anything time-stamped.** There is no date column of any kind. No snapshot date, no
  last-updated, no year. Provenance dating has to be inferred from the filename.

---

## Entity-resolution readiness

**Blocking key `(name, district, state)` with geo as a confirmer is fully viable.**

| signal | coverage |
|---|---|
| usable name (≥3 chars) | 100.00% |
| real district | 99.94% |
| geo inside India bbox | 97.86% |
| pincode | 90.07% |
| **all of name + district + geo** | **97.80%** |
| **unmatchable (no usable name or district)** | **0.06% (6 rows)** |

Trustworthiness of each field for matching:

- `SrNo` — **high**, but only for re-joining to the same parent register. Useless cross-dataset.
- `pincode` — **high**. 100% well-formed. The best cheap confirmer in the file.
- `State_Name` — **high** after fixing `Telengana`.
- `District_Name` — **medium-high** after normalization (strip ` District` suffix on 468 rows,
  strip embedded `\` + newline on 38 rows, upper-case before matching). Note `Balrampur` (UP) and
  `BALRAMPUR` (Chhattisgarh) are **two different real districts** — do not case-fold them together
  without the state.
- `Health Facility Name` — **medium**. 100% present but weak: 4,465 values (43.24%) contain no
  facility-type keyword and are bare place names (`Chunawadh`, `KODAVASAL`, `POLLACHI`). Name-only
  matching will over-merge badly.
- lat/lon — **medium**. High coverage, but see the geo warning below.
- `Taluka_Name` / `Block_Name` — **low**. Real fill 91.68% / 76.18%, and `Block_Name` mixes grain.

---

## The three things that would bite you if you joined this naively

**1. You will read the wrong number of rows, three different ways.**
`wc -l` says **10,612**. `pd.read_csv` gives you **10,530**. The truth is **10,327**.
The 82-line gap is 81 cells with a CRLF embedded inside a quoted field (all `District_Name` /
`Taluka_Name`, e.g. `Almora\⏎`) plus the header. The further 203-row gap is completely blank rows
— **200 in a trailing block at positions 10330–10529, and 3 hidden in the middle at positions
4789, 5740, 6444**, each carrying nothing but a stale pandas index. Interior blanks survive a
naive `.dropna(how='all')` only if you remember to exclude column 1 from the check, because
column 1 is *never* null. And the header itself is booby-trapped: **column 1's name is an empty
string behind a UTF-8 BOM** — read without `encoding='utf-8-sig'` and your first column is called
`'﻿'`.

**2. `\N` is not null and `0` is not zero.**
3,834 cells carry the literal two-character string `\N`, and pandas will happily treat it as
data. `Block_Name` looks 100% populated and is really 76.18%; `Taluka_Name` looks 100% and is
91.68%. Separately, `0` is the file's other null: 6,423 altitudes, 124 addresses, 68 latitudes and
69 longitudes are the character `0`. **`altitude = 0` does not mean sea level — it means not
captured**, and it is batch-correlated, not random (97.9% of Tamil Nadu rows have a real altitude;
Delhi 0.16%; Chandigarh, Goa, Tripura, Puducherry, Mizoram, Nagaland exactly 0%). `AVG(altitude)` over the raw column returns **104.88 m**; over the rows that actually have a
measurement it is **278.46 m** — a 2.7x error.

**3. Good-looking coordinates are frequently not this facility's coordinates.**
97.86% in-bbox hides two failure modes. First, **1,293 rows sit on a coordinate that is shared
with a *different* facility** — 426 coordinate pairs are reused across differently-named
facilities, and one pair (`11.664325, 78.1460142`) carries **57 distinct Salem hospitals**. That's
block/town-centroid geocoding, and it means geo can *reject* a match but must never *confirm* one
below about 1 km. Second, **114 in-bbox rows sit more than 500 km from their own declared state's
median centroid** — 59 of Rewari district's 89 Haryana rows are not in Rewari at all (`Durga
Colony` is placed in Chennai, `Sanati nagar` in Bengaluru). Nine rows say so explicitly in
`Notes`: *"geo cordinates for Balipura BPHC used for Harchura TE"*. Always cross-check
coordinates against `State_Name` before trusting them.

---

## `Notes` — is it worth extracting? Yes, partly.

156 rows, 66 distinct values, free text — but five patterns account for ~85% of it and each maps
onto a real field:

| pattern | rows | extract to |
|---|---|---|
| `NF` / `not found` / `NF, <detail>` | 81 | `record_status = 'not_located'` |
| `Listed as <type>` / `Labelled as <type> on map` | 26 | `facility_type_alt` |
| `name as per google-<name>` / `named X on google` | 17 | name provenance = `google_maps` |
| `geo cordinates for X used for Y` | 9 | `geo_accuracy = 'borrowed_from_other_facility'` |
| explicit duplicate pointers | 2 | dedup hints (see below) |

The `not found` flag is real and load-bearing: **50 of the 81 `NF` rows have `latitude = 0`** and
only 28 have valid geo. And two rows point at duplicates by hand —
`SrNo 3508` says *"Same as row 702"* and `SrNo 89661` says *"Duplicate or SR No. 85112"* — which
is a coder telling you the dedup answer directly.

The remaining ~21 values are genuine one-off remarks (`mobile unit`, `nursing home`,
`hospital name written in a Pvt website- gomyhealth.com`); keep them as raw text.

---

## Duplicates within this dataset

| measure | count | % of 10,327 |
|---|---|---|
| exact duplicates on all 24 data columns | **0** | 0.00% |
| exact duplicates ignoring `SrNo` / `Non filled numbering` | **13** (26 rows) | 0.25% |
| near-dupes: normalized name + lat/lon @3dp | **104** extra (208 rows) | 1.01% |
| near-dupes: normalized name + district | **176** extra (350 rows) | 1.70% |

The 13 hard duplicates are unambiguous — same name, same coordinates, same everything, two
`SrNo`s (`CHC ANADAPURAM` at 61796 and 160783; `BARIPADA` at 39550 and 130674). Two of them are
consecutive `SrNo` (4510/4511, 4004/4005) — a double-entry slip; the rest are far apart, meaning
the same facility entered the parent register twice in different batches. Dedup keeping the lower
`SrNo`.
