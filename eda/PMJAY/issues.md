# PMJAY — data-quality defects

Source: `18_MAY_23_SRK_PMJAY_validated_and_standardized.csv`, 11,284 rows × 78 columns.
Row indices are **0-based pandas positions** for the read documented in `profile.json`
(`Sr No` is given alongside where useful; note `Sr No` = index + 1 only for the first 252 rows).

Severity: **S1** corrupts or silently loses facts · **S2** will produce wrong joins/answers ·
**S3** needs a documented convention · **S4** cosmetic.

---

## S1 — Corrupting / lossy

### 1. `S8` and `S9` have no one-hot column, silently dropping specialties on 3,246 rows
**Affects:** 3,246 rows (28.77%) empanelled, 489 rows (4.33%) upgraded.

The text vocabulary is 25 codes (`M1`–`M8`, `M10`, `S1`–`S16`), but the `_emp` and `_upg` families
have only 23 columns each — there is no `S8_emp`, `S9_emp`, `S8_upg` or `S9_upg`.

> **Row 19** (`Sr No` 20) — `Specialities Empanelled` = `'M8, M1, M2, S8, S7, S12, M7, S16, M6, M5, S5, S3, S2, S1'`
> Flags set: `M1_emp, M2_emp, M5_emp, M6_emp, M7_emp, M8_emp, S1_emp, S12_emp, S16_emp, S2_emp, S3_emp, S5_emp, S7_emp`
> — `S8` is in the text and has nowhere to go.

This is not a partial encoding failure. After removing `S8`/`S9` from the text, the flags
reconstruct it on **11,284/11,284 rows exactly**, for both families. The flags are otherwise
perfect — they are just blind to two codes.

**Fix:** parse `Specialities Empanelled` / `Specialities Upgraded` and generate the one-hot matrix
over the full 25-code vocabulary. Drop all 46 `_emp`/`_upg` columns. Never read a facility's
specialties from the flags.

### 2. Sixty rows have latitude/longitude in the email and phone columns
**Affects:** rows **319–378 inclusive** (a contiguous block of 60), `Sr No` 321–380.

> **Row 319** (`Sr No` 321, `AMAL HOSPITALS`) — `Hospital E-Mail` = `'11.506853'`,
> `Hospital Contact` = `'75.6249378'`, while `API Latitude` = `11.4951664`, `API Longitude` = `75.6238949`
> **Row 322** (`Sr No` 324, `AMAN HOSPITAL`) — `Hospital E-Mail` = `'31.519133'`,
> `Hospital Contact` = `'75.9225755'` — here the values are *identical* to that row's API lat/lon.

On all 60 rows the email value is within one degree of that row's own `API Latitude` and the
contact value within one degree of its `API Longitude`. Every other field on those rows is
correct — name, address, specialties, district and state are all fine — so a column-count or
row-shift check will not catch it, and a permissive validator will store `11.506853` as an email.
The contiguity indicates a single paste into the wrong two columns.

**Fix:** reject `^-?\d+\.\d+$` in both `Hospital E-Mail` and `Hospital Contact`, set to null.
The true contact details for these 60 facilities are not recoverable from this file.

### 3. `Specialities_Upgraded_or_Empanelled` is a delimiter-free concatenation
**Affects:** all 11,141 non-null rows; 2,879 have two codes fused, 3,720 carry a fused `-NA-`.

The column is literally `Specialities Empanelled + Specialities Upgraded` with no separator
(11,141/11,284 exact match).

> **Row 0** — E=`'S1, M1, M7'`, U=`'S5'` → `'S1, M1, M7S5'` (`M7` and `S5` fused into `M7S5`)
> **Row 4** — E=`'S3'`, U=`'-NA-'` → `'S3-NA-'`
> **Row 6** — → `'M1, M7S1, M1, M7'`, which also duplicates codes

Splitting on `,` yields invalid tokens (`M7S5`, `S3-NA-`, `S1S1`). It is null on exactly the 143
rows where `Specialities Empanelled` = `'-NA-'` — a 100% rule, so the nulls are not informative
either.

**Fix:** drop the column outright. Rebuild the union from the two source columns.

---

## S2 — Will produce wrong joins or wrong answers

### 4. `gmaps_*` coordinates geocode the facility *name*, landing 38 rows outside India
**Affects:** 38 rows out of bbox; 192 rows disagree with `API` by more than 500 km.

> **Row 417** (`Sr No` 419) — `AMERICAN ONCOLOGY INSTITUTE A Unit of CTSI`, `Manual state` = `ANDHRA PRADESH`,
> `gmaps` = `(42.3375158, -71.1081418)` — Boston, Massachusetts. `gmaps_Accuracy` = **`ROOFTOP`**.
> **Row 1147** — `Boston Hospital & Research Institute`, `Manual state` = `MADHYA PRADESH`,
> `gmaps` = `(42.3472234, -71.0818372)` — also Boston.
> **Row 705** — `ARYA ORTHOPAEDIC HOSPITAL & SKIN CARE`, `GUJARAT`, `gmaps` = `(34.0252517, -118.4912198)` — Los Angeles.

Full list of 38: `174, 207, 246, 417, 427, 518, 705, 1089, 1111, 1147, 1720, 2767, 3173, 3203,
3365, 3699, 3707, 3770, 4602, 4692, 4733, 4748, 4765, 4805, 4820, 5240, 5642, 5704, 6171, 6786,
7841, 8626, 9773, 9783, 9808, 9879, 10968, 10987`.

`gmaps_Accuracy` gives no warning — the `ROOFTOP` class holds the single worst disagreement in
the file (row 5704, 14,706 km).

**Fix:** use `API Latitude`/`API Longitude` as authoritative (99.97% in-bbox vs 99.66%). Fall back
to `gmaps` only for rows where API is out of bbox and gmaps is not — there are exactly 3.
Never average the pairs.

### 5. Geocoder drift contaminates the whole derived-address family on ~189 rows
**Affects:** 266 rows where `State` ≠ `Manual state`; 189 rows where the pincode's first digit is
impossible for the stated state; 171 rows in both sets.

When the geocoder missed, it missed by a lot, and it wrote a consistent-looking but wrong
`address_py`, `City`, `State`, `pincode_py`, `Zipcode` and `Formatted Address` together.

> **Row 156** (`Sr No` 157) — `Manual state` = `ASSAM`, `API` = `(27.4921251, 94.9279949)` (correctly in Assam),
> but `State` = `Haryana`, `City` = `Gurugram`, `pincode_py` = `122001` (Gurugram).
> **Row 78** — `Manual state` = `HIMACHAL PRADESH`, `API` = `(31.6957348, 76.5015592)` (correctly in HP),
> but `City` = `Bareilly`, `pincode_py` = `243122` (Uttar Pradesh).

On these 189 rows the median `API`↔`gmaps` distance is **754 km**, against 0.90 km across the
file — so the API point and `Manual state` are the correct side and the geocoder is wrong.

**Fix:** treat `Manual state`, `Manual District` and `API Latitude/Longitude` as authoritative.
Validate `Zipcode`/`pincode_py` against `Manual state` by pincode-region first digit and null it
on conflict. Do not use `City` or `State` to populate admin geo.

### 6. `Manual Hospital Name` is the *worse* join key despite looking cleaner
**Affects:** 1,189 rows (10.54%) had a location qualifier stripped; 1,490 rows (13.20%) share a
normalised `Manual Hospital Name`, vs 892 rows (7.90%) for `Hospital Name`.

> **Row 20** — `Hospital Name` = `'A G Eye Hospital, Puthur, Trichy TN.'` → `Manual Hospital Name` = `'A G Eye Hospital'`
> **Row 10248** — `Hospital Name` = `'SMCU-PHC ATHWA (PANAS) U.H.C.'` → `Manual Hospital Name` = `'UPHC Surat Municipal Commission'`
> **Row 10249** — `Hospital Name` = `'SMCU-PHC B.P. U.H.C.'` → `Manual Hospital Name` = `'UPHC Surat Municipal Commission'`

Rows 10248–10251 and 25 others are 29 *distinct* Surat urban PHCs that all collapse to the single
string `UPHC Surat Municipal Commission` — here the name was not truncated but **replaced with an
administrative owner label**. Within-(state, district) name collisions rise from 91 rows using
`Hospital Name` to 310 using `Manual Hospital Name`.

**Fix:** block and match on `Hospital Name`. Keep `Manual Hospital Name` as `facility_name_alt`
for display and fuzzy recall only.

### 7. 22 confirmed intra-dataset duplicate facilities, disagreeing on specialties
**Affects:** 23 near-duplicate groups on (normalised name, API point @4dp ≈ 11 m); 22 confirmed
genuine on inspection, 1 false positive.

> **Rows 6749 / 6750** (`Sr No` 6751 / 6752) — `'P K HOSPITAL'` and `'P K Hospital, Erode TN.'`,
> same point, same email `pkh_kvp@yahoo.in`, same address — but
> `Specialities Empanelled` = `'M1, M7, S7, S5, S4, S1'` vs **`'S4'`**.
> **Rows 8203 / 8204** — `Primary Health Centre KADACHH` twice, different emails
> (`phckadachha...` vs `phcgarej...`), specialty lists differ in membership.

A batch of Tamil Nadu records was clearly loaded twice, one copy carrying a `", <City> TN."`
suffix. The false positive is **rows 9550 / 9551**, two genuinely different Jodhpur satellite
hospitals (Diggi Kala and Pratap Nagar) sharing a city-centroid geocode.

**Fix:** dedupe as a **merge, not a drop** — take the union of specialty codes and the
non-placeholder contact fields. Choosing either row arbitrarily loses clinical detail. Confirm
each pair against `Manual Hospital Address` before merging.

### 8. Emails and phones are shared and placeholdered — not facility identifiers
**Affects:** 433 duplicated emails; 390 phones `-NA-`, 38 `'0'`, 48 `'9898989898'`, 34 `'2222222222'`;
only 94.29% of phones are valid 10-digit Indian mobiles.

> `nithia.d@vidalhealthtpa.com` appears on **54** rows (113, 475, 536, …) — a third-party
> administrator inbox, not a hospital.
> `dporsbyvalsad@gmail.com` on 43 rows — a district programme office.
> **Row 124** — `Hospital Contact` = `'0'`; **row 113** — `Hospital Contact` = `'9898989898'`.

**Fix:** never use email or phone as a match key or blocking key. Null the placeholder values
(`-NA-`, `0`, repeated-digit runs) before exposing them.

---

## S3 — Conventions that must be documented

### 9. `-NA-` is a sentinel string, not a null
**Affects:** `Specialities Empanelled` 143 rows; `Specialities Upgraded` 3,720 rows (plus 4,542
true nulls); `Hospital Contact` 390 rows.

> **Row 106** (`Sr No` 107, `Abhaya Hospital`) — `Specialities Empanelled` = `'-NA-'` while
> `Specialities Upgraded` = `'S10, S11, S16, M1'`.

`Specialities Empanelled` has **zero** true nulls — every absence is spelled `-NA-`. In
`Specialities Upgraded` both conventions coexist, so "no upgrade" is 3,720 + 4,542 = 8,262 rows.

**Fix:** map `-NA-` → null on read, and record that a null upgraded list means "none", not "unknown".

### 10. `pincode_py` uses `'0'` for missing and holds non-Indian postcodes
**Affects:** 875 rows `'0'`, 35 rows non-Indian, 910 unusable total (8.06%).

> **Row 15** — `pincode_py` = `'0'`, `Zipcode` = null.
> **Row 174** — `pincode_py` = `'43614'` (Toledo, Ohio), `Manual state` = `MANIPUR`.
> **Row 417** — `pincode_py` = `'2215'` (Boston), `Manual state` = `ANDHRA PRADESH`.

`Zipcode` is exactly `pincode_py` filtered to valid 6-digit values — the 6-digit subset of
`pincode_py` is precisely the non-null set of `Zipcode`, and they agree on 100% of those 10,374 rows.

**Fix:** prefer `Zipcode`; if using `pincode_py`, treat `'0'` as null and reject anything not
matching `^\d{6}$`. Then apply defect 5's state cross-check.

### 11. `gmaps_Accuracy` contains a tool name as an accuracy class
**Affects:** 115 rows.

> **Row 49** (`Sr No` 50, `AARAIKE SUPER SPECILITY HOSPITAL`) — `gmaps_Accuracy` = `'Awesome Tables'`.

The other four values are genuine Google classes (`ROOFTOP`, `RANGE_INTERPOLATED`,
`GEOMETRIC_CENTER`, `APPROXIMATE`). `Awesome Tables` is a Google Sheets add-on — these 115 rows
were geocoded by a different tool.

**Fix:** map `Awesome Tables` → `UNKNOWN` and treat those rows' accuracy as unrated.

### 12. `Sr No` is positional, not an identifier, and skips a value
**Affects:** the whole column. `Sr No` runs 1..11285 across 11,284 rows.

> **Row 251** has `Sr No` = 252; **row 252** has `Sr No` = **254**. The value 253 is absent — a row
> was deleted after numbering.

It is unique and monotonic, so it works as a within-file surrogate key, but it will not survive a
re-export and must not be published as a facility ID.

**Fix:** use it as `source_facility_id` with a documented `positional` caveat, or mint a synthetic
key. There is no source-issued facility ID anywhere in this file.

### 13. 37 rows have no district; 271 have no ownership; 8 have no urban/rural
**Affects:** `Manual District` 37 nulls (0.33%), `Hospital Type` 271 (2.40%), `is_RU` 8 (0.07%).

> **Row 591** (`Sr No` 593) — `ARALAGUPPE MALLEGOWDA District HospitalCHIKMAGALUR`,
> `Manual District` = null, `Manual state` = `KARNATAKA`, `City` = `Chikkamagaluru district`.
> **Row 6** — `152 bn bsf unit hospital`, `Hospital Type` = null (paramilitary facilities dominate
> the null set: BSF, SSB, Assam Rifles).

All 37 district-null rows still carry name, state and a valid point.

Full district-null list: `591, 757, 894, 927, 954, 1090, 1228, 3078, 3155, 3302, 3407, 4198, 4428,
4437, 4442, 4533, 5173, 5312, 5678, 6040, 6102, 6169, 6410, 6752, 7881, 7891, 9155, 9236, 10163,
10164, 10217, 10340, 10485, 10691, 10729, 10887, 11268`.

**Fix:** for district, back-fill from `City` **only after** the defect-5 drift check, and mark the
provenance. Leave `Hospital Type` null rather than guessing — the nulls are systematic (uniformed-
services hospitals), not random.

### 14. Three rows have an API point outside India, two on a shared "not found" fallback
> **Row 134** — `Acharya Shri Chander College of Medical Sciences and Hospital`, `JAMMU AND KASHMIR`,
> API = `(43.1938516, -71.5723953)` — New Hampshire, USA.
> **Row 8355** — `Primary Health Centre Orwad`, `GUJARAT`, API = `(43.1938516, -71.5723953)` — the *same* point.
> **Row 6383** — `Nankam Hospital, Nilgiris TN.`, `TAMIL NADU`, API = `(52.1386394, -0.4667782)` — England.

The repeated New Hampshire coordinate is a geocoder no-result fallback, and it also appears in
`gmaps` on row 427.

**Fix:** null API coordinates outside the India bbox and blocklist the literal point
`43.1938516, -71.5723953`. All 3 rows have a valid `gmaps` point to fall back to.

---

## S4 — Cosmetic / low impact

### 15. `Manual District` casing is inconsistent
1,056 rows (9.36%) are not uppercase (`Banaskantha`, `Sabarkantha`, `Surendra Nagar`, `Kachchh`)
while the majority are (`AHMEDABAD`, `SURAT`). Only **one** district actually appears in both
casings within this file — `KARBI ANGLONG` / `Karbi Anglong` — so intra-dataset damage is small,
but any cross-dataset join will split keys.
**Fix:** upper-case and collapse whitespace before joining.

### 16. `Hospital Name` casing is inconsistent
4,881 rows (43.3%) are ALL CAPS, the rest mixed case.
> **Row 5** — `'111 SAVE LIFE HOSPITAL'` vs `Manual Hospital Name` `'111 Save Life Hospital'`.
**Fix:** case-fold for comparison; do not treat casing as signal.

### 17. Three columns carry no information
- `Types of Employees` — 100% null across all 11,284 rows.
- `M10_upg` — constant `0`; `M10` never appears as an upgraded specialty.
- `Country` — constant `'India'`.
- `Test extract` — 8 non-null rows (**19–26**) holding `'<DISTRICT>, <STATE>'` copied from
  `Manual District`/`Manual state`, e.g. row 19 = `'KOLLAM, KERALA'`. A dragged spreadsheet formula
  left in the export. Note row 24 is title-cased (`'Bareilly, Uttar Pradesh'`) while the other 7
  are uppercase.

**Fix:** drop all four.

### 18. One typo'd email domain
> **Row 593** (`Sr No` 595) — `arasaneyehospital@gmaul.com` (`gmaul` → `gmail`). Its duplicate
> partner row 592 has the correct `arasaneyehospital@gmail.com`.

Found incidentally via the duplicate pair; there is no systematic way to detect the rest.
**Fix:** none proposed — flag domains with edit distance 1 from common providers for review.

---

## Not a defect

- **Row count.** `wc -l` = 11,285 = 1 header + 11,284 records. CRLF endings, terminal newline,
  every record exactly 78 fields, no embedded newlines. Nothing to reconcile.
- **2,967 rows share an API coordinate** with another row. This is geocoder centroid fallback
  (143 rows sit on `24.3454739,71.7622481`), not duplication. A shared point alone is not evidence
  of a duplicate — see defect 7 for the real ones.
- **`_upg` ⊄ `_emp`.** Only 79.74% of rows satisfy the subset relation and 144 rows have an
  upgraded specialty with no empanelled one. This is not corruption; the two lists are independent,
  not a hierarchy. Do not "repair" it.
