# PHC — Data quality issues

Source: `21_June_2024_AM_PHC.csv`, 31,958 rows × 9 columns.
Row indices below are **0-based pandas indices** from
`pd.read_csv(..., dtype=str, keep_default_na=False)`. Add 2 to get the physical line number.
Every number here comes from `scripts/profile_phc_chc.py`, `scripts/deep_and_cross.py`, or
`scripts/issue_examples.py`.

Severity: **S1** breaks correctness if ignored · **S2** materially degrades matching ·
**S3** cosmetic / low blast radius.

---

## S1-1 — `FAC_DESC` is a facility *type*, not a name (61.92% of rows carry zero place information)

**Evidence.** After normalising case/punctuation and stripping generic facility-type words
(primary, health, centre, phc, govt, sub, hospital, …) and digits, **19,787 of 31,958 rows (61.92%)
have an empty residual**. 5,660 rows (17.71%) are ≤3 characters.

| value | rows |
|---|---|
| `PHC` | 4,390 |
| `phc` | 1,086 |
| `Phc` | 138 |
| `pHC` | 24 |
| `HSC` | 10 |
| `PHc` | 5 |

Row 4 — `Andhra Pradesh / Sri Potti Sriramulu Nell* / FACILITY_ID 144321 / FAC_DESC = "PHC"`.
Row 2751 — `Bihar / Bhagalpur / FACILITY_ID 850783 / FAC_DESC = "HC"` (2 characters).
Row 5723 — `Gujarat / Morbi / FACILITY_ID 485239 / FAC_DESC = "c"` (1 character).

**Impact.** Name-based blocking and fuzzy name matching are non-functional for the majority of the
file. Any string-similarity scorer will return ~1.0 between two unrelated facilities both named
"PHC".

**Fix.** Do not use `FAC_DESC` as a match key on its own. Materialise a
`facility_name_place_token` column = normalised name minus type words; where empty, set NULL and
set a `name_is_boilerplate = true` flag. Route those 19,787 rows to a **geo-primary** matcher
(≤500 m radius) and never let a name score alone confirm a match.

---

## S1-2 — Deduping on `(district, name)` would destroy 17,745 real facilities (55.5% of the file)

**Evidence.** `(DISTRICT_NAME, normalised FAC_DESC)` yields 14,213 groups over 31,958 rows —
**17,745 removable rows** under keep-first. The correct near-dupe measures are two to three orders
of magnitude smaller:

| key | rows involved | removable |
|---|---|---|
| all 9 columns identical | 0 | **0** |
| normalised name + exact lon/lat | 30 | **16** |
| normalised name + lon/lat @3dp (~110 m) | 262 | **134** |
| district + normalised name | 19,638 | 17,745 |

Concrete false positive: rows 720 and 1121 are both `Andhra Pradesh / Prakasam / "Govt PHC"` but
are 2 different facilities at 2 different habitations… *and* their coordinates agree to 4 dp
(79.65869872/15.49532927 vs 79.65871532/15.49538932, ~7 m apart) — so even the geo rule needs human
review at the margin. Contrast rows 7725/7735/7790/7993/8295, all `HAB_ID 38361`, all named some
variant of "primary health centre", spread over **20 km** of Solan district — five genuinely
distinct PHCs that a name+district rule would fuse into one.

**Fix.** Dedupe **only** on normalised-name + coordinate within ~110 m (134 removable). Never on
name + district. Flag the 134 for review rather than dropping blind.

---

## S1-3 — `FACILITY_ID` is shared with the CHC file; 21 rows exist verbatim in both

**Evidence.** 21 `FACILITY_ID` values appear in both `21_June_2024_AM_PHC.csv` and
`21_June_2024_AM_CHC.csv`. For all 21, **every one of the 9 columns is byte-identical** — same
state, district, BLOCK_ID, HAB_ID, name, and the exact same lon/lat (median distance 0.00 km).

Examples (PHC row index, then the identical CHC row):
- PHC row 2360 / CHC row 1183 — `Assam / Nalbari / FACILITY_ID 888987 / "Mukalmua FRU CHC BPHC"`
- PHC row 5723 / CHC row 683 — `Gujarat / Morbi / FACILITY_ID 485239 / "c"`
- PHC row 2751 / CHC row 324 — `Bihar / Bhagalpur / FACILITY_ID 850783 / "HC"`
- 10 further rows in `Jharkhand / Saraikela-kharsawan` all named exactly `HSC`
  (FACILITY_IDs 966266, 966195, 966332, 966157, 966025, 968257, 968258, 966447, 968319, 968219)

**Impact.** Prefixing IDs with the dataset key (`PHC:888987`, `CHC:888987`) manufactures 21
duplicate canonical entities for the same real facility.

**Fix.** Treat PHC and CHC as one source with a `facility_tier` column. Dedupe the union on the
full 9-tuple: 36,195 → **36,174** rows. `FACILITY_ID` is unique across that deduplicated union
(36,174 distinct), so it is a valid PK for the pair.

---

## S1-4 — The PHC/CHC split was made by keyword-matching `FAC_DESC`, so the tier label is unreliable

**Evidence.** Of the 5 rows in this file whose name contains **both** a PHC-token and a CHC-token,
**all 5** also appear in the CHC file. Of the 10 rows named exactly `HSC`, **all 10** also appear
in the CHC file. The 21 overlapping rows break down as: 5 names containing both tokens, 13 names
containing neither (`HC`, `c`, `hpc`, `HSC`×10), 2 PHC-only, 1 CHC-only.

Row 2360 — `Assam / Nalbari / 888987 / "Mukalmua FRU CHC BPHC"` — is in the *PHC* file despite the
name saying CHC first.

**Impact.** The only thing that makes a row a "PHC" is which file it landed in, and the rule that
decided that is a string match over a field that is 62% boilerplate. Do not treat
`facility_tier = PHC` as ground truth.

**Fix.** Materialise `facility_tier` from the filename **and** a
`source_split_confidence ∈ {high, ambiguous}` flag; set `ambiguous` for the 21 overlap rows and for
the 1,298 sub-centre-named rows (see S2-1).

---

## S2-1 — 1,298 rows (4.06%) are sub-centres, a different tier of facility

**Evidence.** 1,298 rows have a `FAC_DESC` matching `\bsub\b|\bhsc\b|\bphsc\b|\bshc\b`.

- Row 0 — `Andhra Pradesh / Kurnool / 67713 / "Primary health sub centre"`
- Row 5 — `Andhra Pradesh / Guntur / 93835 / "primary Sub Centre"`
- Row 19 — `Andhra Pradesh / Krishna / 402211 / "Phc sub center"`
- Row 84 — `Andhra Pradesh / Krishna / 635030 / "PHC sub centre"`

**Impact.** A Health Sub-Centre serves ~5,000 people with an ANM; a PHC serves ~30,000 with a
medical officer. Conflating them corrupts any per-tier count and will cause false matches against
registries that list only PHCs. Note also that India has ~160,000 sub-centres, so this file is
plainly *not* a sub-centre inventory — these 1,298 are contamination, not coverage.

**Fix.** Set `facility_tier = 'SUB_CENTRE'` for these rows rather than `'PHC'`, and flag them
`tier_inferred_from_name = true`.

---

## S2-2 — 226 rows have a `DISTRICT_NAME` hard-truncated at 25 characters

**Evidence.** Three values, each exactly 25 characters with a literal `*` as the last character:

| value | rows | intended |
|---|---|---|
| `Sri Potti Sriramulu Nell*` | 130 | Sri Potti Sriramulu Nellore |
| `South Twenty Four Pargan*` | 50 | South Twenty Four Parganas |
| `North Twenty Four Pargan*` | 46 | North Twenty Four Parganas |

Row 4 — `Andhra Pradesh / "Sri Potti Sriramulu Nell*" / FACILITY_ID 94421`.

**Impact.** Exact-match joins to any LGD or district-master table fail for these 226 rows, and the
`*` will break naive `LIKE` patterns.

**Fix.** Hard-coded repair map of exactly these 3 strings. The truncation is deterministic
(25 chars, `*` marker) so the rule is safe. Same 3 values, 10 rows, in the CHC file.

---

## S2-3 — 32 rows have `DISTRICT_NAME = 'Unknown'`

**Evidence.** 25 in Tamilnadu (BLOCK_IDs 8137–8141, HAB_IDs 1427787–1428920, centroid
79.7915 E / 11.1322 N) and 7 in West Bengal (BLOCK_IDs 8145–8147, HAB_IDs 1429000–1429223,
centroid 88.5861 E / 27.0626 N).

- Row 31260 — `West Bengal / Unknown / BLOCK_ID 8147 / 824104 / "Algarah Primary Health Centre"`
- Row 24403-ish block — `Tamilnadu / Unknown / BLOCK_ID 8140 / 790832 / "Primary Health Centre-Sembanarkoil"`

These carry the **highest** BLOCK_IDs and HAB_IDs in the entire file, i.e. they were appended last.
The Tamilnadu centroid falls in the Mayiladuthurai area and the West Bengal one in the
Kalimpong/Algarah area — both are districts created in **2017–2020**, after the parent district
master was frozen. Strong hypothesis, not verified; see `questions.md`.

**Impact.** These 32 rows cannot be blocked by district and will be missed by any
district-partitioned matcher.

**Fix.** Reverse-geocode from the coordinates (which are valid) to recover the district. Do not
drop the rows — their names are unusually *good* (`"Algarah Primary Health Centre"`,
`"Primary Health Centre Thirukalachery"`), so they are among the more matchable rows in the file.

---

## S2-4 — 192 rows (0.60%) sit >100 km from their own district's median coordinate

**Evidence.** Distance from the median point of the row's own `(state, district)` group:
p50 = 24.8 km, p90 = 54.2 km, p99 = 93.0 km, max 379.0 km. 192 rows exceed 100 km; 1 exceeds
200 km; none exceeds 500 km.

- Row 18764 — `Maharashtra / Raigarh / 629730 / "PHC"` at 76.47604 E, 20.06464 N — **379 km** from
  the Raigarh median. Raigarh (Maharashtra) is a coastal Konkan district around 73.1 E; this point
  is in inland Vidarbha. Note there is also a *Chhattisgarh* Raigarh at ~83.4 E — this looks like a
  district-name collision (see S2-5), but the point matches neither.
- Row 18458 — `Maharashtra / Hingoli / 275252 / "primary Health center"` at 77.66594 E — 190 km out.
- Row 24089 — `Rajasthan / Sirohi / 32940 / "PHC"` at 71.89843 E, 25.66147 N — 150 km out.
- Rows 6166 and 6167 — `Gujarat / Kachchh / 525783` and `604946`, both ~141 km from the Kachchh
  median at essentially the same point (70.984 E, 23.55 N).

**Impact.** Either the coordinate or the district is wrong. Both are load-bearing for matching.

**Fix.** Flag rows >100 km from their district median as `geo_district_mismatch`. Resolve with a
district polygon point-in-polygon test rather than a median-distance heuristic before trusting
either field for those rows.

---

## S2-5 — 8 district names occur in more than one state

**Evidence.** `Aurangabad`, `Balrampur`, `Bijapur`, `Bilaspur`, `Hamirpur`, `Pratapgarh`,
`Raigarh`, `Unknown` each appear under 2 different `STATE_NAME` values.

**Impact.** Any join or blocking key on `DISTRICT_NAME` alone silently merges facilities from
different states.

**Fix.** Always key on `(STATE_NAME, DISTRICT_NAME)`. Enforce as a constraint at load.

---

## S2-6 — 1,106 rows (3.46%) share a `HAB_ID`, which looks like duplication but is not

**Evidence.** 539 `HAB_ID` values are repeated, max repeat 5.

`HAB_ID 38361` (`Himachal Pradesh / Solan / BLOCK_ID 3265`) — rows 7725, 7735, 7790, 7993, 8295:
FACILITY_IDs 1015746, 1015576, 1015579, 1015764, 1015765, named `phc`, `primary health center`,
`primary health centre`, `primary  health`, `primary health`, at coordinates spanning
76.79674–77.02783 E and 31.05404–31.20620 N — roughly **20 km apart**. Five real, distinct PHCs in
one habitation code.

**Impact.** Anyone who sees "duplicate HAB_ID" and dedupes on it deletes real facilities.

**Fix.** Document that `HAB_ID` is a habitation identifier, not a facility identifier. Add a
uniqueness constraint on `FACILITY_ID` only. (`HAB_ID` *is* internally consistent — verified 0 of
35,189 union HAB_IDs span more than one block or district.)

---

## S2-7 — 122 rows (0.38%) have low-precision coordinates

**Evidence.** 122 rows have ≤4 decimal places on `Longitude` (13 rows at 3 dp, 109 at 4 dp), giving
positional granularity of ~11 m to ~110 m rather than the sub-metre implied by the 26,758 rows with
8 dp.

- Row 40 — `Andhra Pradesh / Guntur / 639681` — `80.6774, 16.01063`
- Row 635 — `Andhra Pradesh / Krishna / 374837 / "PHC sub center"` — `80.9992, 16.6526` (both 4 dp)
- Row 1178 — `Andhra Pradesh / Anantapur / 141420 / "PHC"` — `77.0413, 14.38654333`

**Impact.** A ≤500 m geo-matching rule is fine at 4 dp but the mixed precision means a fixed
tolerance is over-strict for some rows and over-loose for others.

**Fix.** Derive `geo_accuracy` from the decimal-place count and let the matcher widen its radius
for low-precision rows.

---

## S3-1 — `FAC_CATEGO` is constant `'Medical'`

**Evidence.** 31,958/31,958 rows. Also constant `'Medical'` for all 4,237 CHC rows.

**Fix.** Drop the column. Do not map it to `facility_category_raw` — it is an amenity category from
a parent survey, not a facility class, and it carries zero bits.

---

## S3-2 — `FAC_DESC` whitespace and punctuation defects

**Evidence.**
- 15 rows with leading/trailing whitespace, several a literal **TAB**:
  row 5701 `FACILITY_ID 99433` = `'Primary Medical Facility\t'`; row 11731 `139141` =
  `'Primary Health Centre\t'`; row 17900 `187107` = `'PHC Arhernawargaon\t'`.
- 681 rows with internal double spaces: row 247 `71701` = `'primary  health  centre'`;
  row 508 `540070` = `'primary  health center center'`.
- 12 rows ending in `.`: row 1876 `964133` = `'Gajendra Bora PHC.'`; row 1924 `964275` =
  `'Futuri PHC.'`.
- 130 rows with no spaces at all: row 103 `401746` = `'PrimaryHelthCenter'`; row 226 `501174` =
  `'primaryhealthcentre'`; row 201 `137003` = `'phcsubcentre'`.
- 224 rows contain a comma (correctly RFC-quoted in the file): row 1653 `988814` =
  `'Primary Health Center, Assam Rifles'`.

**Impact.** Trailing tabs and double spaces break exact-string joins and inflate edit distance.
The trailing `.` is exactly what makes rows 3223/3334 (`"A PHC."` vs `"A PHC"`, same HAB_ID
863627, same coordinate) look like distinct facilities.

**Fix.** `strip()` → collapse internal whitespace → strip trailing `.` — apply **before** any
comparison. Handle the no-space names with a separate word-segmentation pass or accept that they
will not match.

---

## S3-3 — `STATE_NAME = 'Tamilnadu'` deviates from LGD (`'Tamil Nadu'`)

**Evidence.** 1,920 rows. Row 24403 — `Tamilnadu / Krishnagiri / 781159`. All other 28 state values
match the LGD state/UT list verbatim. The CHC file has the identical deviation (98 rows).

**Fix.** One-entry rename map. Trivial, but it will silently drop 6% of the file from any inner
join to an LGD state table.

---

## S3-4 — Eight states/UTs are entirely absent

**Evidence.** No rows for Delhi, Goa, Puducherry, Chandigarh, Andaman & Nicobar Islands,
Lakshadweep, or Dadra & Nagar Haveli and Daman & Diu (and `Tamil Nadu` only under the misspelling).
Identical absence list in CHC.

**Impact.** Not a defect in the file, but a coverage limit: this dataset can never confirm or deny
the existence of a PHC in those 7 territories. Consistent with a *rural* habitation frame.

**Fix.** Record as a known coverage boundary in provenance so downstream "not found in PHC dataset"
is not read as "does not exist".

---

## S3-5 — No provenance columns at all

**Evidence.** No snapshot date, source sheet, record status, or last-updated column. The only
temporal signal is the filename (`21_June_2024`).

**Fix.** Inject `source_snapshot_date = 2024-06-21` and `source_sheet_name = '21_June_2024_AM_PHC'`
at load. Note this is the *file* date, not necessarily the survey date — see `questions.md`.
