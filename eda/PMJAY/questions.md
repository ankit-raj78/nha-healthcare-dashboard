# PMJAY — open questions

Things I could not determine from this file alone. Ordered by how much they block downstream work.
Each states what I established, what remains unknown, and what would settle it.

---

## BLOCKING — the specialty codebook

### Q1. What do the 25 specialty codes `M1`–`M8`, `M10`, `S1`–`S16` actually mean?

**Established:** the vocabulary is exactly `M1 M2 M3 M4 M5 M6 M7 M8 M10 S1 S2 S3 S4 S5 S6 S7 S8 S9
S10 S11 S12 S13 S14 S15 S16` (25 codes), from the union of `Specialities Empanelled` and
`Specialities Upgraded`. The `M`/`S` split is almost certainly **Medical** vs **Surgical**.
Prevalence is the strongest available hint:

| code | % of rows empanelled | | code | % empanelled |
|---|---|---|---|---|
| `M1` | 68.64% | | `S1` | 67.09% |
| `M7` | 65.85% | | `S4` | 65.50% |
| `M2` | 46.02% | | `S5` | 52.12% |
| `M3` | 25.31% | | `S3` | 39.70% |
| `M5` | 21.89% | | `S2` | 38.43% |
| `M4` | 19.36% | | `S7` | 34.77% |
| `M8` | 19.14% | | `S16` | 31.76% |
| `M6` | 18.82% | | `S8` | 28.77% |
| `M10` | **0.22%** | | `S9` | 26.60% |

**Unknown:** the actual specialty names. **I checked and the text columns do not decode them** —
`Specialities Empanelled` contains the same `M#`/`S#` tokens, never a word like "Cardiology". There
is no decoding anywhere in this file, so the codebook cannot be recovered from PMJAY data alone.

**What would settle it:** the PM-JAY Health Benefit Package (HBP) specialty master — the published
HBP 2.0 / HBP 2022 documents list specialties with codes. Failing that, the NHA empanelment portal's
specialty dropdown, or whoever produced this extract. **This is the single highest-value external
artifact for the project** — it unlocks both PMJAY and NHA.

### Q2. Why is `M9` absent entirely, and why do `S8`/`S9` have no one-hot column?

**Established:** `M9` never appears in the text columns *and* has no flag column — it simply does
not exist in this data. `S8` and `S9` do appear in the text (3,246 and 3,002 rows) but have no flag
column, and their omission is the *sole* cause of the flag/text mismatch: after excluding them the
reconstruction is exact on 11,284/11,284 rows.

**Unknown:** whether `M9` is a retired or reserved code, or whether the vocabulary genuinely skips
it. And whether `S8`/`S9` were dropped from the one-hot encoding deliberately (e.g. deprecated
mid-scheme) or by mistake.

**What would settle it:** the same codebook as Q1, plus asking whoever built the one-hot columns.
Practically this does not block us — parse the text columns and the problem disappears — but it
matters for interpreting the *absence* of a code.

### Q3. Why are `S10` and `S11` perfectly collinear, and why does `S9` never appear without `S8`?

**Established:** `S10` and `S11` co-occur on **all** 3,009 empanelled rows and **all** 423 upgraded
rows — zero exceptions in either direction. Separately, `S9` never occurs without `S8` (`S8` alone:
244 empanelled rows, 108 upgraded; `S9` alone: **0**).

**Unknown:** whether these are (a) two halves of one specialty that is always empanelled together,
(b) a parent/child relationship where `S9` is a sub-specialty of `S8`, or (c) an artifact of how the
source system writes the list. A perfect 3,009/3,009 collinearity is very unlikely to be
coincidental.

**What would settle it:** the codebook, plus a second PMJAY snapshot — if the collinearity holds in
a different extract it is structural, if not it is an artifact of this one.

---

## IMPORTANT — provenance and semantics

### Q4. What is the actual snapshot date, and what does "validated_and_standardized" certify?

**Established:** nothing in-band. There is **no date column anywhere in the file** — no
`source_snapshot_date`, no extract timestamp, no last-updated field. The only evidence is the
filename `18_MAY_23_SRK_...`, which reads as 18 May 2023, and initials `SRK`. Admin-boundary
vintage corroborates something **pre-2020**: `DAMAN AND DIU` and `DADRA AND NAGAR HAVELI` appear as
separate states (merged January 2020) and Ladakh is absent (created October 2019).

**Unknown:** whether 18 May 2023 is the date the *data* was extracted from PMJAY or the date this
*file* was produced. The admin vintage suggests the underlying data is materially older than the
filename. Also unknown: what "validated and standardized" was checked against — given defects 1–3
in `issues.md`, it clearly does not mean the specialty encoding was verified.

**What would settle it:** ask SRK, or whoever commissioned the extract. **Do not stamp
`source_snapshot_date = 2023-05-18` as fact** — record it as filename-derived and unconfirmed.

### Q5. Where does the `API Latitude`/`API Longitude` pair come from?

**Established:** it is the better of the two coordinate sources (99.97% in-bbox vs 99.66%), it is
100% populated, and it is *not* the Google geocode — the two agree exactly on only 1,495 rows and
differ by >500 km on 192. It also carries a geocoder no-result fallback point
(`43.1938516, -71.5723953`, New Hampshire) on rows 134 and 8355, so it is itself geocoded output,
not surveyed coordinates.

**Unknown:** which API. Whether it is the PMJAY portal's own stored coordinates, a MapmyIndia/Bing
geocode, or an earlier Google run. This determines whether it is independent evidence from the
other nine datasets' coordinates or a shared upstream — which matters for whether geo agreement
across datasets is real corroboration or just a common source.

**What would settle it:** the pipeline code or notes behind this file. There is no `geo_source`
column to stamp; the loader must supply it.

### Q6. Does `is_RU` classify the facility or its location, and who assigned it?

**Established:** the values are exactly `urban` (8,400) and `rural` (2,876), 8 null — so the name is
confirmed as rural/urban. The 8 nulls are not random: they include both rows whose API point is
outside India (134, 8355) and row 6383, the third out-of-bbox row.

**Unknown:** whether it is derived from the *geocoded point* (in which case it inherits the
geocoder drift in defect 5 and is wrong on ~189 rows) or from a PMJAY-declared attribute. The
null/out-of-bbox correlation is weak evidence for the former.

**What would settle it:** checking `is_RU` against Census 2011 urban/rural boundaries for the API
points. I did not do this — it needs an external boundary file. Worth doing before trusting the
flag, because a 74%/26% urban/rural split is high for Indian health facilities and would be
consistent with geocode-derived classification biasing toward towns.

### Q7. Is `Hospital Type` self-reported, and why is it null for 271 rows?

**Established:** three values — `Public` (5,289), `Private (For Profit)` (5,052),
`Private (Not for Profit)` (672) — plus 271 nulls. The nulls are **systematic, not random**:
uniformed-services facilities dominate them (`152 bn bsf unit hospital`, `24 BN SSB`,
`27 ASSAM RIFLES UNIT HOSPITAL`).

**Unknown:** whether central-government/paramilitary hospitals were deliberately left unclassified
because they fit none of the three buckets, or whether the field was simply never filled for them.
This affects whether we impute `Public` for them (probably correct in substance) or preserve the null.

**What would settle it:** the PMJAY empanelment form's ownership field definition. Until then,
**preserve the null** — do not impute.

---

## MINOR — would improve quality, not blocking

### Q8. Which 115 rows did `Awesome Tables` geocode, and how?

`gmaps_Accuracy` = `'Awesome Tables'` on 115 rows — a Google Sheets add-on name, not an accuracy
class. Their `gmaps` points are all inside India and their median `API`↔`gmaps` distance (0.74 km)
is unremarkable, so the coordinates look no worse than the rest. **Unknown:** what precision to
assign them. Currently unrated.

### Q9. Should the 22 confirmed duplicate pairs be merged or is one row canonical?

Established in `issues.md` defect 7: 22 genuine duplicate facilities whose specialty lists
**disagree** (row 6749 has 6 codes, its twin 6750 has 1). **Unknown:** whether the richer row
supersedes the poorer (a later re-empanelment) or they are two departments of one facility
enrolled separately. The Tamil Nadu `", <City> TN."` suffix pattern suggests a second load of a
state file rather than genuine re-enrolment.

**What would settle it:** a business rule from whoever owns the data. My recommendation is union-
merge, but that is a judgement call, not a finding.

### Q10. What is `Locality` assembled from?

`Locality` is 95.15% filled and geocoder-derived, but only **25.7%** of its values appear verbatim
in `address_py` — so it is a concatenation of several OSM fields, not a single extracted one. By
contrast `Road`, `City`, `District`, `State` and `Zipcode` each appear verbatim in `address_py`
100% of the time. **Unknown:** which fields, in what order. Affects whether `Locality` can be
parsed into `locality` + `landmark` or must stay a single opaque string. Currently mapped as one
low-confidence `locality`.

---

## Checked and settled — recorded so nobody re-investigates

These were open at the start and are now answered; the evidence is in
`scripts/03`–`scripts/09` and their `.out.txt` files.

| Question | Answer |
|---|---|
| Do the text specialty columns decode the numeric codes? | **No.** Same `M#`/`S#` tokens. No codebook here. |
| What is `Auto Score`? | Geocode confidence: string similarity between `Manual Hospital Address` and `address_py` (SequenceMatcher corr **0.812**). Range 0.490–0.917, thresholded at ~0.49. Not a cross-dataset match score. |
| What is `Test extract`? | Spreadsheet scratch. 8 rows (19–26) holding `'<DISTRICT>, <STATE>'` copied from `Manual District`/`Manual state`. |
| What is `is_RU`? | Confirmed rural/urban. See Q6 for the remaining question about its derivation. |
| What is `Types of Employees`? | 100% null. Header only, no data. |
| Is `Sr No` a usable key? | Unique and monotonic, but positional (1..11285, value 253 absent). Not a facility ID. |
| What is `Formatted Address`? | Fully derived rendering: `Manual Hospital Name` + `Road` + `Locality` + `City` + `District` + `State` + `Country` + `Zipcode`, each verbatim in 100% of sampled rows. |
| What is `address_py`? | Raw reverse-geocoder output, OSM/Nominatim (421 rows carry Devanagari/Urdu/diacritics). Parent of `Road`/`City`/`District`/`State`/`Zipcode`/`pincode_py`. |
| Relationship between `Zipcode` and `pincode_py`? | `Zipcode` is `pincode_py` filtered to valid 6-digit values — exact set correspondence, 100% agreement on the 10,374 overlapping rows. |
| Rule behind `Specialities_Upgraded_or_Empanelled`? | `Empanelled + Upgraded`, raw concat, no delimiter. Null on exactly the 143 rows where `Empanelled` = `-NA-`. Corrupt; drop. |
| Is `_upg` a subset of `_emp`? | **No** — 79.74% of rows only; 144 rows have upgraded with no empanelled. Independent lists. |
| Row count discrepancy? | None. 11,285 lines = 1 header + 11,284 records. |
