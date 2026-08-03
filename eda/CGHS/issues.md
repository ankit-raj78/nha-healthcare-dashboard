# CGHS — data-quality issues

Severity scale: **S1** breaks entity resolution or silently corrupts the canonical table · **S2** loses or distorts real information · **S3** cosmetic / mechanical cleanup.

Row indices are 0-based positions in the frame produced by
`pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])` (1983 rows).

---

## S1 — will corrupt entity resolution

### 1. `Address` is a synthetic concatenation, not an address
`Address` == `Hospital_Name + ", " + District + ", " + State`. Byte-identical on **1875/1983** rows; **1983/1983 (100%)** after collapsing whitespace (the 108 exceptions have a stray space before the first comma).

- Row 0 — `Address` = `"VISAKHA INSTITUTE OF MEDICAL SCIENCES , VISHAKHAPATNAM, ANDHRA PRADESH"`, which is exactly `Hospital_Name` + `District` + `State`.

Any similarity score that consumes both `Hospital_Name` and `Address` triple-counts the name and double-counts the admin geography.
**Fix:** drop the column entirely (`field_map.yaml` → `disposition: drop`). Never feed it to a matcher.

### 2. 109 rows sit on 10 administrative centroids, not on the facility
The coordinates were forward-geocoded from that synthetic `Address`; when the geocoder could not resolve a name it returned a district or state centroid.

| coordinate | rows | what it is |
|---|---|---|
| `15.9128998, 79.7399875` | **37** | Andhra Pradesh state centroid — all 37 rows are AP, 39 of the file's `District == '-NA-'` rows live here |
| `28.6139391, 77.2090212` | 20 | Delhi centroid — but the 20 rows span 5 states (Delhi 14, UP 2, Telangana 2, Rajasthan 1, West Bengal 1) |
| `17.385044, 78.486671` | 10 | Hyderabad centroid |
| `19.0759837, 72.8776559` | 8 | Mumbai centroid |
| `18.5204303, 73.8567437` / `21.1458004, 79.0881546` | 7 each | Pune / Nagpur centroids |
| 4 more at 5 rows each | 25 | Gautam Buddha Nagar, Ahmedabad, Lucknow, Visakhapatnam |

At a ≥4-row threshold this grows to **137 rows on 17 coordinates**. Example rows 3, 4, 5, 10, 16 (`CONTINENTAL HOSPITALS LIMITED`, `Satya Kidney Centre…`, `Kamineni Hospital King Koti`, `Apollo Hospitals Secunderabad`, `APOLLO HOSPITALS`) all report `15.9128998, 79.7399875` — five unrelated hospitals at one point.
**Fix:** flag these coordinates as `geo_confidence = CENTROID_SUSPECT` and exclude them from any distance-based blocking or clustering. 1872 rows (94.40%) survive as usable points.

### 3. `Hospital_Id` is an application id — the same facility appears more than once
Zero exact duplicate rows (all 26 columns, and also after dropping `Unnamed: 0`). But **32 rows form 15 groups** identical on (name, district, state, address, lat, lon) with different ids and different specialty lists:

- Rows **1082 / 1132** — `Aditya Super Speciality Hospital & Trauma Centre`, JABALPUR, `23.1491066/79.8779124`: `HOSP23P120251` with `M5,S10,S11,S3,` vs `HOSP23P128502` with 21 two-letter codes. Same building, two applications, two different specialty codebooks.
- Rows **1081 / 1172** — `AJAY BHANDARI ASSOCIATES LLP`, JABALPUR: `S12,S13,` vs `,MC,SL,`.
- Rows **1584 / 1585 / 1586** — `Eye Q Vision Private Limited`, LUCKNOW: three consecutive ids `HOSP9P128150/1/2`, all `SE,`, differing only in the convergence flag.
- Rows **1550 / 1774** — `BHARDWAJ HOSPITAL`, GAUTAM BUDDHA NAGAR: alpha codes vs numeric codes.
- Rows **732 / 766** — `Apollo hospitals city centre`, AHMEDABAD: `HOSP24P130072` vs `LAB24438130073` (same premises registered once as a hospital and once as a lab).

Wider counts: `duplicated(Hospital_Name)` = 68, `(Hospital_Name, District, State)` = 20, normalized name = 115 rows across 77 groups, normalized name + coords@3dp = 28.
**Fix:** dedupe on (normalized name, state, district) with coordinate corroboration, then **union** the specialty lists across the merged rows — never keep only the first row, or you lose half the specialties.

### 4. `Postcode_py` is derived from the geocode, not from the registry
It is a substring of `address_py` in **1935/1935** non-null rows.
- Row **220** — `SHAKUNTLA NH & HOSPITAL`, NEW DELHI, NCT OF DELHI: `Postcode_py = 3302`, `address_py = "Hunt Field, Dunbarton Road, Concord, Merrimack County, New Hampshire, 03302, United States"`.

Using pincode to corroborate a name+geo match is circular, and the one malformed value is a US ZIP whose leading zero was eaten by a numeric cast upstream.
**Fix:** load with `geo_source = reverse_geocode`; never treat as an independent match key. Null the row-220 value.

### 5. Two rows geocoded to the United States
| row | facility | State | lat/lon | `address_py` |
|---|---|---|---|---|
| 220 | `SHAKUNTLA NH & HOSPITAL` | NCT OF DELHI | `43.1938516, -71.5723953` | Concord, New Hampshire, USA |
| 1319 | `Joseph Sahaayam Speciality Hospital,Kanyakumar TN.` | TAMIL NADU | `35.5174913, -86.5804473` | Bedford County, Tennessee, USA |

No zero coordinates, no swapped lat/lon. **Fix:** null both coordinate pairs, `address_py` and `Postcode_py` for these rows.

### 6. `Empanelment_Type` and `OnBoarded_For_Convergence_Scheme` contradict each other
They look like they encode the same fact and are in fact almost anti-correlated:

| | OnBoarded = No | OnBoarded = Yes |
|---|---|---|
| `Only CGHS` (1914) | 901 | **1013** |
| `PMJAY and CGHS` (69) | **67** | 2 |

1013 rows claim CGHS-only empanelment yet are onboarded for the PMJAY convergence scheme, while 67 of the 69 PMJAY-and-CGHS rows are *not* onboarded.
**Fix:** do **not** reconcile or collapse. Persist both as separate facts (`empanelment_type` and a `scheme_membership` entry) and raise the contradiction with the data owner — see `questions.md`.

---

## S2 — loses or distorts real information

### 7. Both date columns are constant `-NA` — no snapshot date exists
`Submitted_Date` and `Status_Updated_Date` each have **exactly 1 distinct value, `-NA`, on all 1983 rows**. There is nothing to parse. The only date signal is the filename token `18_SEPTEMBER_23`.
**Fix:** drop both columns; record `source_snapshot_date: null` and carry `2023-09-18` only as an externally-asserted, clearly-labelled dataset attribute.

### 8. `Specialities_Selected` mixes two mutually exclusive codebooks in one column
47 distinct tokens: **22 two-letter codes** (`BM ER IN MC MG MN MO MP MR SB SC SE SG SL SM SN SO SP SS ST SU SV`) on 968 rows, and **24 numeric codes** (`M1…M8`, `S1…S16`) on 745 rows. **Zero rows mix the families.** 33 rows use two-letter codes plus a literal `NA` token.

- Row 0 — `,BM,MG,MO,MP,SB,SE,SG,SL,SM,SO,SP,` (Family A, leading + trailing comma)
- Row 43 — `M1,M1,M2,S8,M1,M7,M1,S7,S1,S10,S11,S12,S13,S2,S3,S4,S5,S6,S7,S8,S9,` (Family B, `M1` repeated 4×)
- Row 612 — `BM,ER,IN,MC,MG,MN,MO,MP,NA,SB,SC,SE,SG,SN,SO,SP,SS,ST,SU,SV,` (`NA` as a specialty)

`S3` in Family A and `S3` in Family B are different things; merging them silently is a correctness bug.
**Fix:** emit a `specialty_code_system` column (`CGHS_ALPHA2` / `CGHS_MS_NUMERIC`) alongside every code. Strip the `NA` token, dedupe within row, drop the leading/trailing empty tokens.

### 9. `Specialities_Selected` formatting noise
Trailing comma on **all 1746** non-null values, leading comma on **383**, intra-row duplicate tokens on **280** rows (row 43 has `M1` four times; row 52 has `M1` ×4, `M2` ×2, `S7` ×2, `S8` ×2). 237 rows (11.95%) null.
**Fix:** `split(',')` → strip → drop empties → drop `NA` → dedupe → sort.

### 10. `Hospital_Type` 26.07% null, and partly structurally so
517 nulls. **80 of the 81 `LAB…` rows** are null (only `LAB24438130073` is typed) and all 3 `…T…` rows are null. Where both exist, the `Hospital_Id` ownership letter disagrees with `Hospital_Type` on 8 rows (5 `G` rows typed Private, 3 `P` rows typed Public) — e.g. row 114 `HOSP7G124633` `FORESIGHT EYE CLINIC` is typed `Private(For Profit)` despite the `G`.
**Fix:** keep `Hospital_Type` as the primary ownership fact; use the id letter only to fill nulls, and record the disagreement rather than overwriting.

### 11. `Specialities_Selected` and phone are jointly missing on a contiguous Andhra Pradesh block
**Every one of the 38 null-phone rows in the file is a contiguous block: rows 2–39**, all Andhra Pradesh, all `HOSP28P…`. All 38 also have `Specialities_Selected` null and `District = '-NA-'`, and 37 of them carry the AP state centroid. Row 2: `Malla reddy narayana multispeciality HospitalA unit of chandramma educational society`, District `-NA-`, phone null, specialties null.
This is a block-level ingestion gap, not scattered missingness. 39 rows in total have `District = '-NA-'`, all Andhra Pradesh.
**Fix:** treat the AP block as lower-confidence provenance; do not infer that these facilities have no specialties.

### 12. Facility names carry state/city suffixes and embedded commas
13 Tamil Nadu rows end with a 2-letter code and a period; 18 rows contain a comma inside the name.
- Row 1319 — `Joseph Sahaayam Speciality Hospital,Kanyakumar TN.`
- Row 1279 — `Govt. Raja Mirasdar Hospital, Paediatric Medi, TN.`
- Row 1322 — `PIMS, Pondicherry TN.` (also see issue 13)

**Fix:** strip trailing ` (TN|DC|MC|NH)\.` suffixes and split on the trailing comma to recover a locality hint before matching.

### 13. Three Puducherry facilities are filed under `State = TAMIL NADU`
Rows **1322, 1323, 1324** — `PIMS, Pondicherry TN.` / `Aravind Eye Hospital, Pondicherry TN.` / `Aravind Eye Hospital, Pondicherry DC.` — all carry `District = CUDDALORE`, `State = TAMIL NADU` and `Hospital_Id` state code 33 (Tamil Nadu), even though the names say Pondicherry. Separately, row **91** `Prasad Hospitals(a unit of Biosciences Pvt Ltd)` has `District = RANGA REDDY` (Telangana) but `State = ANDHRA PRADESH` — a post-bifurcation leftover; the other 14 RANGA REDDY rows are Telangana.
**Fix:** flag for manual state correction; do not auto-correct from the name.

### 14. `Hospital_Id` state code disagrees with `State` on 23 rows
The digit block inside `Hospital_Id` matches LGD/Census-2011 state codes on 24 of the 26 observed values. Exceptions:
- code **4** (LGD = Chandigarh), 17 rows, all `State = PUNJAB` with districts Amritsar / Jalandhar / S.A.S Nagar — e.g. row 1259 `HOSP4P125507 AKAL EYE HOSPITAL`, JALANDHAR.
- code **37** (LGD = Ladakh), 1 row — row 113 `HOSP37P72508 KUKREJA HOSPITAL & HEART CENTER PVT LTD`, NEW DELHI.
- code **36** (Telangana) on 3 rows labelled ANDHRA PRADESH (rows 89, 90, 91).
- code **7** (Delhi) on 2 rows labelled HARYANA / UTTAR PRADESH (rows 597, 1439).

**Fix:** trust the `State` column, not the id; do not derive `state_lgd_code` from `Hospital_Id` until the code-4 / code-37 semantics are confirmed (see `questions.md`).

---

## S3 — cosmetic / mechanical

### 15. `Unnamed: 0` proves 108 upstream rows were dropped
Monotonic increasing `0..2090`, unique, with **108 missing integers** (first gaps: 6, 46, 54, 93, 99, 133, 159, 370, 500 …). The upstream frame had 2091 rows; this export has 1983.
**Fix:** drop the column, but record the 5.2% upstream loss as a completeness caveat.

### 16. Malformed `Hospital_Id`
Row **1050** — `17006035` (`BANSARA EYE CARE HOSPITAL`, EAST KHASI HILLS, MEGHALAYA). The only value with neither a `HOSP` nor `LAB` prefix, and the only 8-character id (others are 11–14).
**Fix:** keep as-is (it is still unique) but flag `id_format = nonstandard`.

### 17. Sentinel strings masquerading as data
`-NA` in `Submitted_Date`/`Status_Updated_Date` (1983 each), `-NA-` in `District` (39) and `Hospital_Contact` (row 654, `NARAYANA NETHRALAYA 1`), `0` in `Hospital_Contact` (rows 1322, 1324, 1325), `NA` as a specialty token (33 rows).
**Fix:** convert all to NULL on load; they will otherwise be counted as real values by every `COUNT DISTINCT` in the warehouse.

### 18. Name casing and whitespace
1424 names ALL CAPS, 51 all lowercase (row 39 `omega hospitals a unit of hyderabad institute of oncology pvt ltd`, row 64 `praveen hospitals`), 508 mixed; **36 rows contain double spaces** (row 4 `Satya Kidney Centre  And Super Speciality Hospital`, row 10 `Apollo Hospitals  Secunderabad`). No leading/trailing whitespace, no non-ASCII. 117 names contain `"unit of"`.
**Fix:** keep raw, add a normalized column (upper, collapse whitespace, strip corporate suffixes).

### 19. District casing inconsistency
8 of 101 district values are title case among an otherwise UPPERCASE column: `Bagpat`, `Darjiling`, `Gandhi Nagar` (rows 704, 722, 753, 762), `Kanyakumari`, `North 24 Parganas`, `S.A.S Nagar` (rows 1197, 1206 …), `Tiruvallur`, `West Tripura`. Also `RAIGARH(MH)` embeds a state disambiguator and `24 PARAGANAS SOUTH` vs `North 24 Parganas` use opposite word orders.
**Fix:** uppercase and normalize against the LGD district list.

### 19b. `District` uses pre-rename district names; `address_py` uses post-rename ones
All **40** rows with `District = 'ALLAHABAD'` (the pre-2018 name) have an `address_py` that says `Prayagraj District` — e.g. row 1448 `HOSP9P124629`, `District = ALLAHABAD`, `address_py = "Kareli, Prayagraj, Prayagraj District, Uttar Pradesh, 211001, India"`. Similarly rows 3–4 geocode into `Palnadu District`, an Andhra district that did not exist until 2022. The registry geography and the geocoded geography are from different eras.
**Fix:** normalize `District` through an LGD alias table (ALLAHABAD→PRAYAGRAJ, GURGAON→GURUGRAM, …) before joining; never cross-validate `District` against `address_py` — they will disagree for legitimate reasons.

### 20. `address_py` non-ASCII and a stray U+2013
68 rows contain non-ASCII characters in `address_py` (row 2 contains `Medchal–Malkajgiri District` with an en-dash U+2013; row 500 contains `Delābaritoli`). Harmless for storage but will break naive ASCII matching.
**Fix:** NFKD-normalize before any string comparison.

### 21. Eight prior-pipeline metric columns are mislabelled "Distance"
`Levenshtein Distance`, `Jaro Wrinkler Distance` (sic — "Wrinkler"), `Jaccard Distance`, `Cosine Distance` and `BWTRLENCD Distance` all hold **similarities**, so a naive reader will invert the ranking. `Monge Elkan Distance*10` is exactly `10 ×` its sibling. `Auto Score` is an exact affine function of three of them and has essentially no discriminative power (AUC 0.481–0.615 against four independent geocode-correctness proxies).
**Fix:** drop all eight — see `field_map.yaml`. If anyone insists on keeping them, rename to `*_similarity` first.
