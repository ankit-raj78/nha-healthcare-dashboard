# CHC — Data quality issues

Source: `21_June_2024_AM_CHC.csv`, 4,237 rows × 9 columns.
Row indices below are **0-based pandas indices** from
`pd.read_csv(..., dtype=str, keep_default_na=False)`. Add 2 to get the physical line number.
Every number here comes from `../PHC/scripts/profile_phc_chc.py`,
`../PHC/scripts/deep_and_cross.py`, or `../PHC/scripts/issue_examples.py`.

Severity: **S1** breaks correctness if ignored · **S2** materially degrades matching ·
**S3** cosmetic / low blast radius.

---

## S1-1 — `FAC_DESC` is a facility *type*, not a name (56.53% of rows carry zero place information)

**Evidence.** After normalising case/punctuation and stripping generic facility-type words
(community, health, centre, chc, govt, hospital, …) and digits, **2,395 of 4,237 rows (56.53%)**
have an empty residual. 729 rows (17.21%) are ≤3 characters, across just 7 distinct values:

| value | rows |
|---|---|
| `CHC` | 558 |
| `chc` | 150 |
| `HSC` | 10 |
| `Chc` | 8 |
| `HC` | 1 |
| `c` | 1 |
| `hpc` | 1 |

Row 324 — `Bihar / Bhagalpur / FACILITY_ID 850783 / FAC_DESC = "HC"`.
Row 683 — `Gujarat / Morbi / FACILITY_ID 485239 / FAC_DESC = "c"` (1 character).

**Impact.** Fuzzy name matching returns ~1.0 similarity between unrelated facilities. Name-based
blocking does not function for the majority of the file.

**Fix.** Derive `facility_name_place_token` = normalised name minus type words; NULL where empty,
plus a `name_is_boilerplate` flag. Route those 2,395 rows to geo-primary matching. The good news
(see PROFILE.md) is that CHCs are sparse enough for geo-only matching to be viable —
95.68% of rows are alone in their ~1.1 km grid cell and the densest cell in the file holds 3 rows.

---

## S1-2 — Deduping on `(district, name)` would destroy 1,476 real facilities (34.8% of the file)

**Evidence.** `(DISTRICT_NAME, normalised FAC_DESC)` yields 2,761 groups over 4,237 rows —
**1,476 removable rows** under keep-first. The defensible near-dupe measures are far smaller:

| key | rows involved | removable |
|---|---|---|
| all 9 columns identical | 0 | **0** |
| normalised name + exact lon/lat | 2 | **1** |
| normalised name + lon/lat @3dp (~110 m) | 44 | **22** |
| district + normalised name | 1,978 | 1,476 |

The single exact-coordinate near-dupe is rows 332 and 476:
`Bihar / Vaishali / BLOCK_ID 2436 / HAB_ID 677770`, FACILITY_IDs 844793 and 844778, names
`"Community health centre."` and `"Community health centre"` — differing only by a trailing period —
at the identical point `85.49423353, 25.74601764`. That is a true duplicate.

Contrast rows 2656/2657 (`Punjab / Hoshiarpur / HAB_ID 63939`, FACILITY_IDs 424363 and 424365, 9 m
apart) — also almost certainly the same facility recorded twice, caught only by the 110 m rule.

**Fix.** Dedupe on normalised name + coordinate within ~110 m (22 removable), flagged for review.
Never on name + district.

---

## S1-3 — `FACILITY_ID` is shared with the PHC file; 21 rows exist verbatim in both

**Evidence.** 21 `FACILITY_ID` values appear in both this file and `21_June_2024_AM_PHC.csv`, and
in all 21 cases **every one of the 9 columns is byte-identical** — same state, district, BLOCK_ID,
HAB_ID, name, and the exact same lon/lat (median distance 0.00 km, max 0.00 km).

Examples in this file:
- Row 324 — `Bihar / Bhagalpur / 850783 / "HC"`
- Row 683 — `Gujarat / Morbi / 485239 / "c"`
- Row 826 — `Gujarat / Valsad / 471531 / "PHC Achchhari"` — a row named **PHC**, in the CHC file
- Row 263 — `Assam / Baksa / 900821 / "Barama block primary health centre cum Barama comunity health centre"`
- Rows 1156, 1160, 1176 (and 7 more) — `Jharkhand / Saraikela-kharsawan`, all named exactly `HSC`
  (FACILITY_IDs 966266, 966195, 966332, 966157, 966025, 968257, 968258, 966447, 968319, 968219)

**Impact.** Loading PHC and CHC as separate sources with dataset-prefixed IDs manufactures 21
duplicate canonical entities for the same real facility.

**Fix.** Treat the pair as one source with a `facility_tier` column. Dedupe the union on the full
9-tuple: 36,195 → **36,174**. `FACILITY_ID` is unique across the deduplicated union, so it is a
valid PK for the pair.

---

## S1-4 — The PHC/CHC split was made by keyword-matching `FAC_DESC`; the tier label is unreliable

**Evidence.** Of the 5 rows in this file whose name contains **both** a PHC-token and a CHC-token,
**all 5** also appear in the PHC file. Of the 10 rows named exactly `HSC`, **all 10** also appear
in the PHC file. The 21 overlapping rows are: 5 with both tokens, 13 with neither
(`HC`, `c`, `hpc`, `HSC`×10), 2 PHC-only, 1 CHC-only.

Row 826 — `Gujarat / Valsad / 471531 / "PHC Achchhari"` — sits in the CHC file with a name that
says PHC and nothing else.

**Impact.** "This row is a CHC" is an assertion made by a string rule over a field that is 57%
boilerplate. It is not ground truth.

**Fix.** Materialise `facility_tier` from the filename **and** a
`source_split_confidence ∈ {high, ambiguous}`. Set `ambiguous` for the 21 overlap rows and the 39
sub-centre-named rows (S2-1).

---

## S2-1 — 39 rows (0.92%) are named as sub-centres, a lower tier

**Evidence.** 39 rows match `\bsub\b|\bhsc\b|\bphsc\b|\bshc\b`.

- Row 25 — `Andhra Pradesh / Anantapur / 224150 / "community health sub centre"`
- Row 720 — `Gujarat / Navsari / 307233 / "sub center vachchharwad"`
- Row 1014 — `Himachal Pradesh / Kangra / 1008520 / "Community Health Sub Centre Beehan"`
- Row 1148 — `Jharkhand / Dhanbad / 673302 / "Telmachcho Health Sub center"`
- Rows 1156, 1160, 1176 … — `Jharkhand / Saraikela-kharsawan`, `"HSC"` ×10

**Impact.** A CHC is a ~30-bed referral unit; a sub-centre is a two-staff outpost. Conflating them
corrupts tier counts and creates false matches. The 10 `HSC` rows are doubly suspect — they are
also duplicated into the PHC file (S1-3).

**Fix.** Set `facility_tier = 'SUB_CENTRE'` for these 39 rows and flag
`tier_inferred_from_name = true`.

---

## S2-2 — 10 rows have a `DISTRICT_NAME` hard-truncated at 25 characters

**Evidence.** Three values, each exactly 25 characters ending in a literal `*`:

| value | rows | intended |
|---|---|---|
| `Sri Potti Sriramulu Nell*` | 6 | Sri Potti Sriramulu Nellore |
| `North Twenty Four Pargan*` | 3 | North Twenty Four Parganas |
| `South Twenty Four Pargan*` | 1 | South Twenty Four Parganas |

Row 1 — `Andhra Pradesh / "Sri Potti Sriramulu Nell*" / FACILITY_ID 198923`.

**Impact.** Exact joins to LGD/district masters fail for these rows; the `*` breaks `LIKE` patterns.

**Fix.** Hard-coded 3-entry repair map. Deterministic and safe. Same 3 values, 226 rows, in PHC.

---

## S2-3 — 1 row has `DISTRICT_NAME = 'Unknown'`

**Evidence.** Row 4228 — `West Bengal / Unknown / BLOCK_ID 8145 / HAB_ID 1428938 /
FACILITY_ID 824289 / "Gorubathan CHC"` at `88.70055167, 26.96108833`.

This is the highest `BLOCK_ID` in the file — appended last. The coordinate falls in the
Kalimpong/Gorubathan area; Kalimpong was carved out of Darjeeling in **2017**, after the parent
district master was presumably frozen. Hypothesis, not verified — see `questions.md`. The PHC file
has 32 such rows (25 Tamilnadu at BLOCK_IDs 8137–8141, 7 West Bengal at 8145–8147) with the same
signature.

**Fix.** Reverse-geocode from the coordinate. Do not drop — this row's name (`"Gorubathan CHC"`)
is more informative than most of the file.

---

## S2-4 — 30 rows (0.71%) sit >100 km from their own district's median coordinate

**Evidence.** Distance from the median point of the row's own `(state, district)` group:
p50 = 20.1 km, p90 = 49.6 km, p99 = 95.2 km, max 447.1 km. 30 rows exceed 100 km, 1 exceeds 200 km,
none exceeds 500 km.

- Row 566 — `Chhattisgarh / Bijapur / 277284 / "community health center"` at
  `80.05969048, 22.89167225` — **447 km** from the Bijapur (Chhattisgarh) median. Chhattisgarh's
  Bijapur is at ~80.8 E / 18.8 N; this point is ~400 km north in Madhya Pradesh territory. Note
  `Bijapur` also exists in Karnataka (~75.7 E) — a district-name collision (S2-5) — but the
  coordinate matches neither.
- Row 3025 — `Rajasthan / Barmer / 8614 / "CHC Kalyanpur"` — 133 km out.
- Row 815 — `Gujarat / Kachchh / 604957 / "Community Health Center"` at `70.91920833, 23.47012167`
  — 130 km out. (The PHC file has two rows at nearly the same point with the same Kachchh problem.)
- Row 2 — `Andhra Pradesh / Guntur / 379633 / "Community health centre"` at
  `79.38421115, 16.51680493` — 129 km out. This is the **third data row of the file**.

**Impact.** Either the coordinate or the district is wrong; both are load-bearing.

**Fix.** Flag `geo_district_mismatch` for rows >100 km from their district median and resolve with
a point-in-polygon test before trusting either field.

---

## S2-5 — 6 district names occur in more than one state

**Evidence.** `Aurangabad`, `Balrampur`, `Bijapur`, `Bilaspur`, `Hamirpur`, `Pratapgarh` each
appear under 2 different `STATE_NAME` values.

**Fix.** Always key on `(STATE_NAME, DISTRICT_NAME)`. Enforce at load.

---

## S2-6 — Implausible per-state coverage: West Bengal has 16 CHCs, Uttar Pradesh has 760

**Evidence.** Row counts by state range from 2 (Sikkim) to 760 (Uttar Pradesh). West Bengal: 16.
Mizoram: 4. Ladakh: 5. Tamilnadu: 98. Maharashtra: 204.

West Bengal has ~90 million people and a documented CHC count in the hundreds; 16 rows cannot be a
census. Contrast the PHC file, where West Bengal has 840 rows.

**Impact.** Per-state counts from this file are **submission artifacts, not facility density**.
Absence of a CHC in a given West Bengal district is not evidence of absence in reality.

**Fix.** Record per-state completeness as a known limitation in provenance. Do not use this file
for denominators, coverage statistics, or "missing facility" analyses at state level.

---

## S2-7 — 126 rows (2.97%) share a `HAB_ID`, which looks like duplication but usually is not

**Evidence.** 63 `HAB_ID` values are repeated, max repeat 2.

Row 979 / row 1047 — `Himachal Pradesh / Kangra / BLOCK_ID 1487 / HAB_ID 561596`,
FACILITY_IDs 1007675 and 1009371, `"Community Health Centre Khundian"` / `"Community Health centre
Khundian"`, 40 m apart — this pair almost certainly **is** a duplicate and is caught by the 110 m
rule (S1-2).

Row 3860 / row 4167 — `Uttar Pradesh / Etah / HAB_ID 69236`, `"Community health center"` /
`"community healthcare"`, 3 m apart — same.

But `HAB_ID` is a *habitation* code, not a facility code: 0 of the 35,189 union HAB_IDs span more
than one block or district (verified), and 376 HAB_IDs legitimately carry both a PHC and a CHC.

**Fix.** Never dedupe on `HAB_ID`. Use it as a blocking key only; confirm with coordinate distance.

---

## S2-8 — 13 rows (0.31%) have low-precision coordinates

**Evidence.** 13 rows carry ≤4 decimal places on `Longitude` (1 at 3 dp, 12 at 4 dp) versus 3,529
rows at 8 dp.

- Row 318 — `Assam / Jorhat / 972264 / "Mariani CHC"` — `94.342, 26.63064333` (3 dp on longitude)
- Row 2097 — `Maharashtra / Ahmadnagar / 453485 / "CHC"` — `74.4887, 19.946105`
- Row 879 — `Haryana / Kurukshetra / 713906 / "community health center"` — `77.0452, 29.99632833`

**Fix.** Derive `geo_accuracy` from decimal-place count; widen the match radius for these rows.

---

## S3-1 — `FAC_CATEGO` is constant `'Medical'`

**Evidence.** 4,237/4,237 rows. Also constant `'Medical'` across all 31,958 PHC rows — so it does
not even distinguish the two files.

**Fix.** Drop. Do not map to `facility_category_raw`.

---

## S3-2 — `FAC_DESC` whitespace and punctuation defects

**Evidence.**
- 5 rows with leading/trailing whitespace, all involving literal **TABs**:
  row 1324 `FACILITY_ID 158411` = `'\t Govt Community Health Center Hampasagar'`;
  row 1475 `216853` = `'\t Community Health centre'`;
  row 2918 `24834` = `'Community Health Centre\t\t'`;
  rows 2737 / 2781 = `'Community Health Centre\t'`.
- 101 rows with internal double spaces: row 19 `524905` = `'community  health centre'`;
  row 136 `134041` = `'Community  Health  centre'`.
- 1 row ending in `.`: row 332 `844793` = `'Community health centre.'` — and this is exactly the
  row that forms the file's only exact-coordinate duplicate pair (S1-2).
- 20 rows with no spaces at all: row 72 `208436` = `'communityhealthcentre'`;
  row 744 `506912` = `'chcsatlasana'`; row 2273 `755457` = `'CommunityHealthCenterPapadahandi'`.
- 20 rows contain a comma (correctly RFC-quoted): row 192 `991574` =
  `'Community Health Center, Kanubari HQ'`.
- Pervasive misspellings: `comunity`, `cummunity`, `cmmunity`, `Cammunity`, `Communty`, `helth`,
  `heath`, `healt`, `Helath`.

**Fix.** `strip()` → collapse internal whitespace → strip trailing `.`, before any comparison.
Consider a curated misspelling map for the ~10 recurring variants of "community" and "health";
edit-distance alone will not reliably link `cmmunity` to `community` at short lengths.

---

## S3-3 — `STATE_NAME = 'Tamilnadu'` deviates from LGD (`'Tamil Nadu'`)

**Evidence.** 98 rows. Row 3163 — `Tamilnadu / Tiruvannamalai / 797499`. All other 28 state values
match LGD verbatim. Same deviation in PHC (1,920 rows).

**Fix.** One-entry rename map.

---

## S3-4 — Eight states/UTs are entirely absent

**Evidence.** No rows for Delhi, Goa, Puducherry, Chandigarh, Andaman & Nicobar Islands,
Lakshadweep, or Dadra & Nagar Haveli and Daman & Diu. Identical absence list in PHC.

**Fix.** Record as a coverage boundary in provenance so "not found" is not read as "does not exist".

---

## S3-5 — No provenance columns at all

**Evidence.** No snapshot date, source sheet, record status, or last-updated column.

**Fix.** Inject `source_snapshot_date = 2024-06-21` and `source_sheet_name = '21_June_2024_AM_CHC'`
at load, noting this is the file date and not necessarily the survey date.
