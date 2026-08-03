# CGHS — `18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv`

**True shape: 1983 rows × 26 columns.** (`wc -l` says 1984 — that is 1 header + 1983 data records, all CRLF-terminated. There are no embedded newlines; `csv.reader` returns 1984 records, every one exactly 26 fields wide.)

**Correct read:** `pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])`.
The file starts with a UTF-8 BOM, so a naive read names the first column `﻿Unnamed: 0`. `dtype=str` matters: without it `Postcode_py` loses leading zeros and the `-NA` / `-NA-` sentinels get partly coerced.

## What this is

The **Central Government Health Scheme (CGHS) empanelment registry** — the list of private and public facilities approved to treat central-government employees and pensioners. Every row is one **empanelment application**, keyed by `Hospital_Id`, which encodes prefix + state code + ownership letter + serial:

| | count |
|---|---|
| `HOSP…` hospitals, clinics, eye/dental centres | 1901 |
| `LAB…` diagnostic labs and imaging centres (Dr Lal Path Labs, Metropolis, Aarthi Scans …) | 81 |
| malformed (`17006035`, row 1050) | 1 |

`Application_Status` is the constant `"Hospital Approved for Empanelment"` on all 1983 rows, so this is an **approved-only slice**, not the full application pipeline. `Empanelment_Type` splits *Only CGHS* 1914 / *PMJAY and CGHS* 69. Ownership is `Private(For Profit)` 1248, `Private(Not For Profit)` 186, `Public` 32, **null 517 (26.1%)**. `OnBoarded_For_Convergence_Scheme` is Yes 1015 / No 968.

Geographically it is 24 states/UTs, heavily metro-weighted: NCT of Delhi 367, Uttar Pradesh 347, Maharashtra 279. No Himachal, Assam, Chandigarh, or most of the North-East.

## Only 12 of the 26 columns are source data

| origin | columns |
|---|---|
| **CGHS registry (12)** | `Hospital_Id`, `Hospital_Name`, `District`, `State`, `Hospital_Contact`, `Specialities_Selected`, `Hospital_Type`, `Empanelment_Type`, `Submitted_Date`, `Status_Updated_Date`, `Application_Status`, `OnBoarded_For_Convergence_Scheme` |
| **Added by a prior Python pipeline (14)** | `Unnamed: 0`, `Address`, `Latitude`, `Longitude`, `Postcode_py`, `address_py`, and the 8 similarity columns |

That prior pipeline did three things, and understanding them is the whole ballgame:

1. Built a synthetic `Address` = `Hospital_Name + ", " + District + ", " + State`. **Verified: identical on 1875/1983 rows byte-for-byte and 1983/1983 (100%) after collapsing whitespace.** It is not a filed address.
2. Forward-geocoded that string into `Latitude`/`Longitude`, then reverse-geocoded the result back into `address_py` (Nominatim/OSM format, 1981/1983 end in `"India"`) and pulled `Postcode_py` out of it (a substring of `address_py` in 1935/1935 non-null rows).
3. Scored `Address` against `address_py` with eight string metrics — an attempt to auto-validate its own geocodes.

### The eight "Distance" columns, decoded

All eight compare **`Address` vs `address_py`**, and despite the names most are **similarities**, not distances. Each formula below was reproduced in code against the actual values:

| column | what it actually is | rows reproduced exactly |
|---|---|---|
| `Levenshtein Distance` | `1 − OSA_edit_distance(a,b)/max(len)` — a similarity | **1983/1983** |
| `Jaro Wrinkler Distance` | `JaroWinkler.similarity(a,b)` | **1983/1983** |
| `Jaccard Distance` | bag-of-**characters** Jaccard similarity | **1983/1983** |
| `Cosine Distance` | bag-of-**characters** cosine similarity | **1983/1983** |
| `BWTRLENCD Distance` | `1 − NCD` with a Burrows-Wheeler + run-length compressor | **1931/1983** (r = 0.9985) |
| `Monge Elkan Distance` | range 0.0022–0.0134 — far below any real Monge-Elkan; no standard variant reproduces it. **Unresolved** | 0/1983 |
| `Monge Elkan Distance*10` | exactly `10 × Monge Elkan Distance` (max deviation 5e-9) | 1983/1983 |
| `Auto Score` | `0.1867386636·Lev + 0.1975256764·JW + 0.6157356594·ME10 + 0.4287057853` — R² = 1.0, max residual 9.0e-10, the three weights sum to 1.000000. Jaccard, Cosine and BWTRLENCD contribute **nothing** | 1983/1983 |

**They carry no reusable signal.** They compare a name-plus-admin-string against its own reverse geocode, so they mostly measure how verbose OSM was. AUC of every metric against four independent geocode-correctness proxies (coordinate is an admin centroid / district name appears in `address_py` / state name appears / any 4+ character name token appears) lands in **0.39–0.69**, and the best of those (`Monge Elkan`, 0.690) correlates −0.63 with `len(Address)`, i.e. it is measuring string length. `Auto Score` scores 0.481 / 0.484 / 0.568 / 0.615 — effectively random — and spans only [0.5351, 0.7189] with no threshold anywhere in the file. Drop all eight; do not migrate them into the canonical table.

## The specialty vocabulary

`Specialities_Selected` is comma-delimited (`,` — the only delimiter present; `;`, `|`, `/` appear zero times), with a **trailing comma on all 1746 non-null values** and a **leading comma on 383**. 13334 total tokens, **47 distinct**, 1–30 per row (mean 7.6, median 3). 237 rows (11.95%) are null.

The 47 tokens are **two mutually exclusive codebooks** — this is the single most important thing in the file for a specialty codebook:

- **Family A, 22 two-letter codes** — `BM ER IN MC MG MN MO MP MR SB SC SE SG SL SM SN SO SP SS ST SU SV` — used by **968 rows**
- **Family B, 24 numeric codes** — `M1…M8`, `S1…S16` — used by **745 rows**
- plus a literal `NA` token on 33 rows (always alongside Family A)

**Zero rows mix the two families.** The split is not random: 204 of the 303 Delhi rows with specialties use Family B, while 299 of the 316 such UP rows use Family A — consistent with two different application-form vintages. Neither codebook is expanded anywhere in the file, and `S3` in Family A does not mean `S3` in Family B, so a `specialty_code_system` discriminator column is mandatory before either can be loaded.

## No snapshot date

`Submitted_Date` and `Status_Updated_Date` are the **constant literal `-NA` on all 1983 rows** — one distinct value each. There is no format to parse and no range to report. **This dataset carries no usable snapshot date.** The only date signal is the `18_SEPTEMBER_23` token in the filename (→ 2023-09-18), which is an assertion by whoever named the file, not data.

## Good for / bad for

**Good for:** a clean, unique, real source key (`Hospital_Id`, 1983/1983 unique); trustworthy state (24 values, 0 nulls, internally consistent) and district (98.03% usable); a genuine private-hospital empanelment signal (CGHS empanelment is a meaningful quality/scale proxy) and the CGHS↔PMJAY convergence flag; a substantial specialty code list; a phone number on 97.9% of rows.

**Bad for:** anything address-shaped. There is **no filed street address** in the file — `Address` is synthetic and `address_py` describes wherever the geocoder landed. Coordinates are geocoder output, not survey. No beds, no accreditation, no email/website, no ABDM flag, no dates, no sub-district geography.

## Three things that will bite someone who joins this naively

1. **`Address` is not an address, and `Latitude`/`Longitude` are not measurements.** `Address` is a 100% reconstructible concatenation of name + district + state, so any fuzzy match that uses both `Hospital_Name` and `Address` triple-counts the name. And because the geocoder was fed that string, **109 rows sit on just 10 administrative centroids** — 37 rows share `15.9128998, 79.7399875` (the Andhra Pradesh state centroid) and 20 share `28.6139391, 77.2090212` (Delhi). A geo-radius join will fuse 37 unrelated Andhra hospitals into one cluster. Only **1872 rows (94.40%)** have coordinates that are both in-country and not on a shared centroid.

2. **`Hospital_Id` is an application id, not a facility id — the dataset contains real duplicates that no exact key catches.** Zero exact row duplicates, but **32 rows form 15 groups identical on (name, district, state, address, lat, lon)** with different `Hospital_Id` and different specialty lists. E.g. *Aditya Super Speciality Hospital & Trauma Centre*, Jabalpur appears as `HOSP23P120251` (`M5,S10,S11,S3`) and `HOSP23P128502` (21 Family-A codes) — the same building, filed twice under two codebook vintages. Deduping on `Hospital_Id` will leave all of them in. Normalized-name duplicates run to 115 rows across 77 groups.

3. **`Postcode_py` looks like an independent match key and is not.** It is a substring of `address_py` in 1935/1935 non-null rows — it came out of the reverse geocode. Row 220 (`SHAKUNTLA NH & HOSPITAL`, New Delhi) carries pincode `3302` because its coordinates resolved to **Concord, New Hampshire, USA** (ZIP 03302). Using pincode to corroborate a name+geo match is circular, and it silently launders geocoding errors into the canonical table.

## Entity-resolution readiness

| signal | coverage | trust |
|---|---|---|
| `Hospital_Name` | 1983 (100%) | high — real applicant-entered names, but heavy corporate boilerplate (117 rows contain "unit of") |
| `State` | 1983 (100%) | high |
| `District` | 1944 (98.03%, excl. `-NA-`) | high — 8 casing outliers, `RANGA REDDY` straddles TG/AP |
| coordinates in India bbox | 1981 (99.90%) | **medium-low** — geocoded, 109 on centroids |
| coordinates usable as a point | 1872 (94.40%) | medium |
| pincode | 1935 (97.58%) | low — derived from the geocode, not independent |
| phone | 1941 (97.88%) valid mobiles | medium — 201 rows share a number with another row |

**(state, district, normalized name) is a viable blocking key for 98.03% of rows.** Only **41 rows (2.07%)** lack the full name + district + in-bbox-geo triple, and **0 rows** lack name plus at least one of district/geo — nothing here is truly unmatchable. Block on name + state + district; use geo only as a tie-breaker, and only after excluding the 10 known centroid coordinates.
