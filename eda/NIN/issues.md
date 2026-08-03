# NIN — data-quality issues

Source: `22_MAY_22_AP_NIN.csv`. **Row index** below = the 0-based positional index produced by
`pd.read_csv(..., encoding='utf-8-sig', dtype=str, keep_default_na=False, na_values=[''])`
*before* dropping blank rows (i.e. the index into the 10,530-row parse), so every example is
directly reproducible. `SrNo` is given alongside as the stable key.

Severity: **S1** = will produce wrong results silently · **S2** = will produce wrong results
loudly or lose data · **S3** = cosmetic / normalization chore.

---

## S1-1 — The header's first column name is an empty string behind a UTF-8 BOM

The file's first 3 bytes are `EF BB BF` and the first header field is `""`. Read without
`encoding='utf-8-sig'` and the first column is named `'﻿'` — an invisible character that no
downstream code will match. `pd.read_csv` with the BOM stripped names it `Unnamed: 0`.

- **Evidence:** header bytes `efbb bf2c 4e6f 6e20 6669 ...` = `<BOM>,Non filled numbering,SrNo,...`
- **Fix:** always `encoding='utf-8-sig'`; immediately `df.columns.values[0] = '_stale_pandas_index'`.

## S1-2 — Three different row counts, and 203 blank rows including 3 hidden in the middle

`wc -l` = **10,612**. `pd.read_csv` = **10,530**. True logical rows = **10,327**.

- 81 of the 82-line gap are cells containing an embedded CRLF inside a quoted field. All are in
  `District_Name` / `Taluka_Name`. Row 653 (`SrNo 2876`, `Dhaulchina`) has
  `District_Name = 'Almora\\\n'`; row 559 has `Taluka_Name = 'Chilakaluripet\\\n H/O.Purushotha Patnam Mandal'`.
- 203 rows have **every one of the 24 data columns null**. 200 form a contiguous trailing block
  (positions **10330–10529**); **3 are interior: positions 4789, 5740, 6444**. Position 4789 sits
  between `SrNo 48433` (`FRU MANNEKHALLI`) and `SrNo 48441` (`CHC Morinda`) and carries only
  `_stale_pandas_index = 4811`.
- **Why this bites:** the interior blanks survive a naive `df.dropna(how='all')` because column 1
  is *never* null. You end up with 3 phantom facilities scattered through the file.
- **Fix:** `df = df[~df[df.columns[1:]].isna().all(axis=1)]` — explicitly exclude column 1 from
  the emptiness test. Assert the result is 10,327 rows.

## S1-3 — `\N` is a data value, not a null (3,834 cells)

The MySQL NULL marker was exported literally. Every affected column reads as more-populated than
it is.

| column | `\N` cells | apparent fill | **real fill** |
|---|---|---|---|
| `Block_Name` | 2,460 | 100.00% | **76.18%** |
| `Taluka_Name` | 859 | 100.00% | **91.68%** |
| `street` | 229 | 78.61% | 76.39% |
| `Address` | 188 | 79.83% | 78.01% |
| `altitude` | 23 | 100.00% | see S1-4 |
| `landmark`, `locality`, `landline_number` | 23 each | — | — |
| `District_Name` | 6 | 100.00% | **99.94%** |

- **Example:** row 3459 (`SrNo 12893`, `CHC Tiloi`, Uttar Pradesh) has `District_Name = '\N'` with
  perfectly good coordinates 26.393/81.470.
- **Fix:** global `df.replace({'\\N': None})` before anything else. Add `'-'`, `'na'` to the same
  sweep (see S2-3).

## S1-4 — `altitude = 0` means "not captured", and the zeros are batch-correlated

62.20% of rows (6,423) carry `altitude = 0`, plus 23 carrying `\N`. Only **3,881 rows (37.6%)**
have a real elevation. The zeros are **not** randomly distributed:

| state | rows | fraction with a real altitude |
|---|---|---|
| Daman & Diu | 4 | 100.0% |
| Meghalaya | 66 | 98.5% |
| Tamil Nadu | 2,736 | 97.9% |
| Telengana | 173 | 96.5% |
| Maharashtra | 714 | 24.9% |
| Delhi | 619 | **0.16%** |
| Chandigarh / Goa / Tripura / Puducherry / Mizoram / Nagaland / Arunachal / Kerala / D&NH | 254 | **0.0%** |

- **Consequence:** `AVG(altitude)` over the raw column = **104.88 m**; over the rows with a
  measurement = **278.46 m**. A 2.7× error, and any state comparison is a comparison of capture
  batches, not of terrain.
- **The values themselves are real** — non-zero range 0.26–5985 m, median 175 m, and state medians
  are geographically correct (J&K 1589 m, Uttarakhand 1320 m, Meghalaya 1019 m, Chhattisgarh
  325 m, Delhi ~0). 1,928 of the 3,881 have decimal precision.
- **Fix:** `NULLIF(altitude, 0)` and `NULLIF(altitude, '\N')`. Never impute 0.

## S1-5 — 1,293 rows sit on a coordinate shared with a *different* facility

426 distinct coordinate pairs are each reused by two or more differently-named facilities. The
worst offender, `11.664325, 78.1460142`, carries **57 distinct Salem, Tamil Nadu hospitals**
(`DR.SOODAMANI NURSING HOME` `SrNo 9397`, `JAI LAKSHMI NURSING HOME` `SrNo 9398`,
`K.N. NATARAJ HOSPITAL` `SrNo 9399`, …). Runners-up: `9.925201, 78.119775` (25 rows),
`11.744699, 79.768024` (24 rows), `9.36, 78.83` (20 rows).

This is town/block-centroid geocoding presented as a point.

- **Consequence:** any entity-resolution rule of the form "same facility if within 500 m" will
  merge 57 unrelated Salem hospitals into one entity.
- **Fix:** compute the multiplicity of each coordinate pair and set `geo_accuracy = 'centroid'`
  wherever it exceeds 1. Geo may **reject** a candidate match but must never **confirm** one below
  ~1 km in this dataset.

## S1-6 — Coordinates that are in India but not in the declared state (114 rows)

Measured as great-circle distance from the row's own `State_Name` median centroid over the 10,106
in-bbox rows: **1,297 rows > 300 km (12.83%)**, **114 rows > 500 km (1.13%)**, 26 > 800 km,
8 > 1,200 km. `Haryana` / `Rewari` is a systematic failure: **59 of Rewari district's 89 rows fall
outside Rewari's bbox.**

| row | SrNo | name | state / district | lat, lon | actually near | km from state centroid |
|---|---|---|---|---|---|---|
| 8973 | 164994 | `Durga Colony` | Haryana / Rewari | 12.923, 80.159 | Chennai | 1781 |
| 6819 | 103965 | `Sanati nagar` | Haryana / Rewari | 12.957, 77.599 | Bengaluru | 1746 |
| 8365 | 147994 | `Hajariwas` | Haryana / Rewari | 26.222, 93.914 | Assam | 1704 |
| 3275 | 10250 | `BRS HOSPITAL PVT LTD` | Tamil Nadu / Chennai | 23.367, 81.043 | Madhya Pradesh | 1409 |
| 634 | 2750 | `Subhash Basti` | Haryana / Rewari | 22.490, 88.309 | Kolkata | 1337 |
| 10187 | 142896 | `Alaipur` | Uttar Pradesh / `\N` | 22.917, 88.174 | West Bengal | — |

The pattern is clear from the names: these are *locality* strings (`Durga Colony`, `Hans Nagar`,
`Sector 1`) that were geocoded without a state qualifier and landed on a same-named locality in
another city.

- **Fix:** run a point-in-state check against LGD/Survey-of-India boundaries and null out
  coordinates that fail. Do not silently trust the 97.86% in-bbox figure.

## S1-7 — `Coder` is PII in a table destined for an LLM-queryable database

600 rows carry the first name of one of five identifiable internal staff (`tanmay` 358,
`shalmali` 175, `mallika` 57, `sweta` 6, `sid` 4). It is employee-attribution metadata, not
facility data, and would be exposed by any `SELECT *`.

- **Example:** row 337 (`SrNo 809`, `I.D & B.G. HOSPITAL`) → `Coder = 'sid'`.
- **Fix:** keep in the internal provenance table for quality attribution; exclude from the
  public/agent-facing view, or map to an opaque `coder_id`.

## S1-8 — 832 personal mobile numbers in `landline_number`

Of the 6,196 non-null values, **832 (13.4%)** are 10-digit numbers starting 6–9 — Indian mobile
numbers, which for private nursing homes are very likely a proprietor's personal line.

- **Examples:** row 8 (`SrNo 27`, `DH Kanker`) `7868241214`; row 31 (`SrNo 136`, `HARUR`)
  `9751160530`.
- Two cells contain an **email address** instead of a phone number: row 2422 (`SrNo 9406`,
  `P.K. Hospital`) `pkhospital24@gmail.com`, and row 6226 (`SrNo 86510`, `Bhopalgarh`)
  `chcbhopalgarh1417.1417@rediffmail.com`.
- **Fix:** classify each value as landline vs mobile; route the 2 emails to an `email` column;
  apply the project's PII policy to the mobiles.

---

## S2-1 — 42 rows have latitude and longitude swapped

Detectable because `latitude` lands in 68–98 and `longitude` in 6–38.

- **Example:** row 3237, `Northern Regional Centre of AYJNIHH (New Delhi)`, `State_Name = Delhi`,
  `latitude = 77.245185`, `longitude = 28.571167`. Delhi is at 28.57 N, 77.25 E — the values are
  transposed.
- Others: row 1515 `DMO Hingoli` (77.15, 19.72); row 3444 `BIDADI` (77.385637, 12.796524);
  row 3743 `CHC Nalkheda` (75.149, 24.4052).
- **Fix:** mechanically swap when `lat ∈ [68,98] AND lon ∈ [6,38]`. All 42 are recoverable.
  Verify the result against `State_Name` afterwards.

## S2-2 — 85 rows have coordinates outside India entirely, and 9 have `lat == lon`

- **Worst:** row 7781 (`SrNo 130978`, `fidusar`, Rajasthan / Jodhpur) at
  `36.112439, -115.201119` — that is **Las Vegas, Nevada**. Row 7909 (`SrNo 135175`,
  `Krishna Nagar`, Haryana / Rewari) at `34.205109, 118.657281` — eastern China.
- **`lat == lon` copy-paste errors, 9 rows:** row 199 (`SrNo 524`, `SHOLAVANDAN`, Tamil Nadu)
  `10.022023, 10.022023`; row 5614 (`SrNo 70557`, `CH Mhow`) `22.551994, 22.551994`; row 9373
  (`SrNo 175829`, `Sadar Hospital Jehanabad`) `25.2116445, 25.2116445`. In each case the latitude
  looks plausible and the longitude was overwritten with it.
- **Fix:** null both coordinates when out of bbox or when `lat == lon`. Do not attempt repair —
  there is nothing to repair from.

## S2-3 — Sentinel strings scattered through the address block

Beyond `\N`: `Address` has 124 `'0'`, 96 `'-'`, 1 `'na'`; `street` 7 `'0'`, 12 `'-'`, 1 `'na'`;
`landmark` 2 `'0'`, 6 `'-'`, 1 `'na'`; `locality` 8 `'0'`, 2 `'-'`, 1 `'na'`; `landline_number`
34 `'0'`, 27 `'-'`. Also 94 `Address` values are the bare string `'1'`.

- **Example:** row 636 (`SrNo 2760`, `Addanki Community Health Center`) has `Address = '0'` while
  `Manual_Address = 'Indira Nagar, Addanki, Andhra Pradesh'`.
- **Fix:** null out `{'\N', '-', '0', '1', 'na'}` in all six text columns.

## S2-4 — 13 hard duplicate pairs; 2 of them flagged by the coders themselves

Zero rows are exact duplicates on all 24 columns, but **13 pairs are identical on everything
except `SrNo`** (26 rows, 0.25%).

| name | SrNo pair | note |
|---|---|---|
| `CGHS Minto Road` | 4510 / 4511 | consecutive — double-entry slip |
| `Deepak Memorial Hospital` | 4004 / 4005 | consecutive |
| `ABC,Hospital` | 10078 / 10079 | consecutive |
| `Sathy NH` | 8955 / 8957 | near-consecutive |
| `CGHS Dev Nagar` | 4495 / 4498 | near-consecutive |
| `Karthik Nursing Home` | 7739 / 7746 | near-consecutive |
| `BARIPADA` | 39550 / 130674 | different batches |
| `CHC ANADAPURAM` | 61796 / 160783 | different batches |
| `CHC MANNEKHALLI` | 47349 / 139063 | different batches |
| `Khushalanagar CHC` | 125247 / 158050 | different batches |
| `Malkhed CHC` | 110901 / 113433 | different batches |
| `SIRIGERE` | 39555 / 70813 | different batches |
| `Shahjapur` | 85968 / 176683 | different batches |

Two more are flagged in `Notes` by the coders and are caught by **no** automatic rule here —
see S2-8, which explains why.

Softer measures: **104 extra rows** duplicate on normalized-name + lat/lon@3dp (208 rows
involved), **176 extra rows** on normalized-name + district (350 rows involved). Not all of these
are true duplicates — `Alangulam` (`SrNo 68484` and `SrNo 11930`, Tirunelveli) shares exact
coordinates but is typed once as `Sub-District Hospital` and once as `Community Health Center`.

- **Fix:** drop the 13 keeping the lower `SrNo`; manually adjudicate the 2 coder-flagged rows;
  review the name+geo group of 208 by hand; and re-run all of it after stripping the `NOTIONAL `
  prefix (S2-8).

## S2-8 — The undocumented `NOTIONAL ` name prefix hides 57 further near-duplicates

**74 `Health Facility Name` values begin with the literal word `NOTIONAL`** — 73 in Rajasthan,
1 in Jharkhand. Examples: `NOTIONAL Osian` (`SrNo 11669`), `NOTIONAL Gadra Road` (`SrNo 13038`),
`NOTIONAL Kanod` (`SrNo 14040`), `NOTIONAL Loonkaransar` (`SrNo 18409`). The word is not part of
any facility's real name and appears in no other column; its meaning is unknown (see
`questions.md` Q10).

- **Consequence:** stripping the prefix raises the name+district near-duplicate count from
  **176 to 239** (+63).
- **Proof the prefix conceals real duplicates:** row 6333 (`SrNo 89661`, `Gingla CHC`, Rajasthan /
  Udaipur, `latitude = 0`) carries `Notes = "Duplicate or SR No. 85112"`. `SrNo 85112` **is** in
  this file, at row 6177, as **`NOTIONAL Gingla CHC`** — same state, same district, same facility
  type, with valid coordinates 24.2990869 / 74.03024642. Neither the name+geo rule nor the
  name+district rule catches this pair, because the names differ by the prefix *and* one row's
  geo is the `0` sentinel.
- **Fix:** strip a leading `NOTIONAL\s*` (case-insensitive) into a separate flag column before any
  name matching or dedup; keep the flag, since it may encode a facility status.

## S2-5 — `Facility Type` mixes two orthogonal axes; `Others` is 23% of the file

The 13-value vocabulary contains both a function axis (`Community Health Center` 4,786,
`Sub-District Hospital` 927, `Dispensaries` 748, `District Hospital` 645,
`Medical Colleges Hospital` 166, `Civil Hospital/General Hospital` 117, `Maternity Home` 110,
`Post Partum Unit` 105, `Referral Hospital` 80) and a bed-capacity axis (`<100 Bedded Hospital`
183, `100-500 Bedded Hospital` 64, `>500 Bedded Hospital` 14) — plus `Others` at **2,382 rows
(23.07%)**.

`Others` is de-facto "private": 1,692 of those 2,382 names (71%) contain
`hospital`/`nursing home`/`clinic`/`NH`, while only 27 contain a government marker
(`Govt`, `District`, `Civil`, `CHC`, `PHC`, `Municipal`, `ESI`).

- **Fix:** split into `facility_type_raw` + `bed_count_band`. Do **not** treat `Others` as
  unknown — it is a meaningful (if implicit) ownership signal.

## S2-6 — `Manual_Pincode` contains an Excel `#REF!` and 5 non-pincodes

519 of 525 values are clean 6-digit pincodes. The 6 that are not:

| row | SrNo | name | `Manual_Pincode` | `Manual_Address` |
|---|---|---|---|---|
| 10190 | 143912 | `Sessa Te` | **`#REF!`** | `CW2M+C6H, Nij Khanikar Gaon, Assam` |
| 4568 | 42213 | `Rajeshwar CHC` | `Karnataka 585331` | `Rajeshwar` |
| 5158 | 58594 | `Badami CHC` | `Karnataka 587201` | `Badami` |
| 5292 | 61960 | `NOTIONAL Sarola Kalan` | `Rajasthan 326035` | `Sarolakala` |
| 10261 | 168365 | `CHC Hunasangi` | `Karnataka` | `585201, Yadgir, Karnataka` |
| 10296 | 181802 | `RNB Civil Hospital Gossaigaon` | `Assam` | `Habrubil,PIN-783360, Gossaigaon, Assam` |

`Manual_Address` and `Manual_Pincode` were evidently filled by dragging a formula across a
spreadsheet, and in 5 rows the two got mis-aligned (the state landed in the pincode cell) while
one row's formula reference broke entirely.

- **Fix:** regex-extract the trailing 6 digits from the three `State <pincode>` values; null the
  three that have no pincode at all; recover row 10190's pincode from `Manual_Address` (it has
  none — flag for a human).

## S2-7 — `pincode` has 2 implausible round values

`500000` on row 1097 (`SrNo 5222`, `CHC Armoor`, Telengana / Nizamabad District) and `110000` on
row 9985 (`SrNo 191769`, `MH Kamla Nehru`, Delhi / Central). Neither is a real delivery pincode
(they are the "series head" values). Row 1097's `Manual_Pincode` gives the correct `503224`.

- **Fix:** validate against a pincode reference list; null anything ending in `0000`.

---

## S3-1 — `Telengana` is misspelled (173 rows)

The only state-name defect. Row 638 (`SrNo 2790`, `Area Hospital, Siddipet`) → `Telengana`.
**Fix:** map to `Telangana`.

## S3-2 — `District_Name` needs three separate normalizations

1. **468 rows carry a ` District` suffix** across 34 distinct values, concentrated in the
   north-east and the Telugu states: Andhra Pradesh 236, Telengana 173, Tripura 47, Arunachal
   Pradesh 8, Assam 4 — e.g. `Chittoor District`, `Guntur District`, `Nizamabad District`. The
   same districts appear without the suffix elsewhere. Stripping the suffix takes the distinct
   count from 623 → 620.
2. **38 rows carry a literal backslash + newline**: `District_Name = 'Almora\\\n'` (rows 653, 654,
   685, 686, …). These are the same 38 rows that create the `wc -l` discrepancy in S1-2.
3. **One case collision**: `Balrampur` (11 rows, Uttar Pradesh) vs `BALRAMPUR` (5 rows,
   Chhattisgarh).
   **These are two genuinely different districts** — row 3393 `CHC Tulsipur` is UP-Balrampur, row
   3714 `CHC Wadrafnagar` is Chhattisgarh-Balrampur. Do **not** case-fold them together without
   also keying on state.

## S3-3 — Untrimmed whitespace in 9 columns

`Manual Health Facility Name` 217 values, `Manual_Address` 170, `Taluka_Name` 41,
`District_Name` 38, `Coder` 36, `Manually_added` 17, `Health Facility Name` 10, `Notes` 9,
`Address` 1. **Fix:** `.str.strip()` everywhere on read.

## S3-4 — `Manually_added` has 5 spellings of "yes" and no "no"

`Yes` 481, `yes` 25, `yes ` 12, `Yes ` 5, `Y` 3 (first occurrences: row 496 `Yes`, row 337 `Y`,
row 5038 `yes`, row 4802 `Yes `, row 5060 `yes `). Blank = not manually added; there is no
explicit `No`. Note the flag is *incomplete*: 73 rows have `Coder = 'tanmay'` but a blank
`Manually_added`, so `Coder IS NOT NULL` is the better "a human touched this" predicate (600 rows
vs 526).

**Fix:** `lower().strip()`, map `{yes, y} → true`, `NULL → false`.

## S3-5 — `Coder` has 9 spellings of 5 names

`Mallika`, `Mallika `, `mallika`, `mallika ` are all one person (57 rows combined);
`Tanmay` / `Tanmay ` are one person (358). **Fix:** `lower().strip()`.

## S3-6 — `locality` mixes settlement class with locality name

43 rows hold the literal string `Urban` and 32 hold `Rural` in a column otherwise containing
neighbourhood and city names. **Fix:** extract those 75 into a separate `settlement_class` field.

## S3-7 — Two entirely useless columns

`Unnamed: 23` has **0 non-null values** in all 10,530 parsed rows (a trailing-comma export
artifact). The BOM-only first column is a stale pandas index — strictly increasing 0..10635,
unique, but with **106 gaps** (first missing values: 491, 496, 591, 614, 617, 624, 652, 663, 761,
778, 3406, …), meaning 106 rows were deleted after that export and it can never be a key.
**Fix:** drop both.

## S3-8 — `landline_number` is not a single number

141 values contain a comma or slash separating multiple numbers, e.g.
`04146-222210,225922`. Digit lengths run 0–19 (2,962 have 11 digits, 2,375 have 10, 406 have 8).
**Fix:** split on `[,/]`, normalize to E.164 where possible, keep the raw string.

## S3-9 — `Address` is an address *fragment*

Median length 12 characters. The most common non-null values are the facility type restated:
`Community Health Center` (77), `CHC` (68), `Community Health Centre` (34),
`Primary Health Centre` (33), `COMMUNITY HEALTH CENTER` (32). It is not a postal address and must
not be fed to a geocoder or used for address-similarity matching. Use `Manual_Address` where
available (530 rows) and otherwise concatenate `street` + `landmark` + `locality` + `pincode`.
