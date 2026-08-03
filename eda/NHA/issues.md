# NHA — data-quality defects

Source: `1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv`, 323,460 data rows ×
46 columns. Row indices are **0-based positions** in a
`pd.read_csv(dtype=str, keep_default_na=False, na_filter=False)` read — i.e. row *N* is
line *N+2* of the file. Every number below comes from `eda/NHA/scripts/`.

Severity: **S1** breaks correctness of any downstream join or count · **S2** produces wrong
answers in a specific domain · **S3** cosmetic, cheap to fix.

---

## S1-1 — `Facility ID` is not unique; the file's grain is a `24/7` cross-product

**Affects 127,004 rows / 62,300 IDs (39.3% of rows).**

`Facility ID` repeats on 62,300 values; only 258,756 of 323,460 rows have a distinct ID.
The repeats are **not** ID collisions between different facilities — 62,298 of the 62,300
groups carry the same `hospital_name`, and only 1 group spans two states. **58,370 groups
(93.69%) are groups in which `24/7` takes both `yes` and `no`.** Of the 60,541 two-row
groups, **53,728 differ in `24/7` and nothing else**.

Example — `Facility ID` 500319 appears three times, twice byte-identical and once differing
only in `24/7`:

| row | Facility ID | hospital_name | Latitude | 24/7 |
|---|---|---|---|---|
| 261 | 500319 | BHANU MULTISPECIALITY HOSPITAL | 16.96968298921712 | `yes` |
| 262 | 500319 | BHANU MULTISPECIALITY HOSPITAL | 16.96968298921712 | `yes` |
| 65030 | 500319 | BHANU MULTISPECIALITY HOSPITAL | 16.96968298921712 | `no` |

Worst case: `Facility ID` 364845 occupies **220 rows**, all one name
(`DR CHOPRAS PATH CLINIC`), one district (Ghaziabad), one coordinate.

**Fix.** Before anything else, `df.drop(columns=['24/7']).drop_duplicates()` →
**261,905 rows** (61,555 eliminated), after which only 3,146 IDs remain repeated. Then
resolve the residual 3,146 (they differ mostly in `Latitude`). Treat `Facility ID` as the
source entity key, not as a primary key of the file as delivered. Anyone joining on
`Facility ID` without this step doubles ~40% of their rows and overcounts facilities by
~25%.

---

## S1-2 — `24/7` is self-contradictory on 22.56% of facilities

**Affects 58,370 of 258,756 distinct facilities.**

Those facilities carry both `yes` and `no` on different rows of the same `Facility ID`.
Since only 63,308 facilities have a `yes` row at all, **92.2% of every "24/7 = yes"
facility is contradicted by one of its own rows.** Row-level counts (`no` 259,444 /
`yes` 64,016) are therefore meaningless.

**Fix.** Do not load `24/7` as a boolean fact. Aggregate per `Facility ID` into
`is_24x7_any` plus an `is_24x7_conflicting` flag, and exclude conflicting facilities from
any 24/7 query. Root cause needs a source-side answer — see `questions.md`.

---

## S1-3 — Half the coordinates are shared points, not facility locations

**165,448 rows (51.15%) share their exact lat/lon pair with at least one other row.**

There are only 215,652 distinct coordinate pairs for 323,460 rows. 807 pairs are used by
≥10 rows; 65 pairs are used by ≥50 rows, covering 22,187 rows (6.86%).

Worst offender: **`26.917858, 75.801292` is used by 9,870 rows carrying 9,089 distinct
names across 28 different Rajasthan districts.** That is the Jaipur city centroid.

| row | Facility ID | hospital_name | new_district_name | Latitude | Longitude |
|---|---|---|---|---|---|
| 228614 | 483185 | 10 EEA | Ganganagar | 26.91785800000001 | 75.80129199999999 |
| 228615 | 530898 | 10 GM | Bikaner | 26.91785800000001 | 75.80129199999999 |
| 228616 | 483186 | 10 H | Ganganagar | 26.91785800000001 | 75.80129199999999 |

Next worst: `17.32966, 76.833588` (1,345 rows, Kalaburagi) and `16.830618, 75.711014`
(1,327 rows across 4 Karnataka districts).

**Fix.** Compute the multiplicity of every coordinate pair and set a `geo_is_shared_point`
flag (proposed in `field_map.yaml`). Suppress coordinates as a *merge* criterion wherever
multiplicity exceeds ~5, or wherever the point's rows span more than one district. Use geo
to rank candidates, never to decide them.

---

## S2-1 — `new_district_name` is wrong on the rows where it disagrees with `District_name`

**Affects 867 rows.**

`new_district_name` looks trustworthy — it is perfectly 1:1 with `district_code` (615 ↔
615) and no district spans two states. But on the 867 disagreement rows its value appears
in the row's own `Address` only **112** times, versus **600** for `District_name`; on
**263** rows neither matches. The failures are fuzzy string matches that jump across
states.

Example — 92 rows recode `nadia` → `Narmada` (a Gujarat district ~250 km away). The truth
is neither: `Nadiad` is a city in **Kheda** district, which the address states plainly.

| row | Facility ID | District_name | new_district_name | district_code | Address |
|---|---|---|---|---|---|
| 13383 | 199378 | `nadia` | `Narmada` | 452.0 | NEAR BUS STAND,ALINDRA, Alindra , Nadiad **Kheda**, Gujarat - 387115 |
| 13712 | 180716 | `nadia` | `Narmada` | 452.0 | DDU Campus, College Road, Nadiad, Nadiad City **Kheda**, Gujarat - 387001 |

Same pattern: 330 rows `anoopgarh`→`Anupgarh` (benign spelling), but 91 rows `una`→`Anjaw`
where every address says **Upper Subansiri** (row 3034, 3035, 3042, …), 47 rows
`dehradun`→`Mau`, 44 rows `nainital`→`Mainpuri`, 41 rows `jangoan`→`North Goa`.

**Fix.** Do not trust either column on these 867 rows. Re-derive the district from the
`Address` tail (the token immediately before the state name) and reconcile against an
external LGD district-code table. Flag the rows that still fail.

---

## S2-2 — Two states are entirely missing; several are drastically undercounted

**Affects the whole dataset's fitness for national statistics.**

LGD state codes **19 (West Bengal)** and **31 (Lakshadweep)** have **zero rows**. Row
counts for present states are wildly uneven:

| State | rows | | State | rows |
|---|---|---|---|---|
| Uttar Pradesh | 62,801 | | **Odisha** | **11** |
| Karnataka | 56,885 | | Goa | 56 |
| Maharashtra | 26,502 | | Meghalaya | 96 |
| Rajasthan | 22,276 | | Sikkim | 173 |
| Andhra Pradesh | 21,289 | | Ladakh | 237 |
| Gujarat | 18,644 | | Manipur | 274 |
| | | | **Tamil Nadu** | **2,567** |

Odisha at 11 rows and Tamil Nadu at 2,567 are not credible facility counts for those
states.

**Fix.** Not fixable within this dataset — it is a collection-coverage limit, not a defect
to repair. Record it as a hard caveat on the canonical table, and never compute
per-state coverage or "facilities per capita" from NHA alone. Fill West Bengal and Odisha
from the other nine sources.

---

## S2-3 — 1,304 rows have unusable coordinates (out of bbox, swapped, zero, or unparseable)

Against India's bbox (lat 6–38, lon 68–98): **322,156 rows valid (99.60%)**, and:

| defect | rows |
|---|---|
| out of bbox (non-null, non-zero) | 1,222 |
| lat/lon **swapped** | 342 |
| exactly `0,0` | 66 |
| `\|lat\| > 90` (impossible) | 40 |
| `\|lon\| > 180` (impossible) | 41 |
| `Latitude` unparseable as a number | 12 |
| `Longitude` unparseable as a number | 10 |

**Swapped** — row 1162, `NIKSHAY ANANTAPUR` (Andhra Pradesh): `Latitude` = `77.600594`,
`Longitude` = `14.681888`. Reversing gives a correct Anantapur location. Rows 1163–1165
(`NIKSHAY CHITTOOR`, `NIKSHAY GUNTUR`, `NIKSHAY KURNOOL`) are the same.

**Impossible magnitudes** — row 61442, `SARVANG HOSPITAL` (UP): `26740124`, `83364653` —
a decimal point dropped from `26.740124, 83.364653`. Row 53747, `AGARWAL HOSPITAL` (UP):
`2712.28`, `781.33`. Row 191087, `DR K K GUPTA` (MP): `26213662278.12914` in *both* fields.

**Unparseable** — row 34705, `CHC MAUGANJ`: `Latitude` = `"‎24.6673639"` (leading
U+200E LEFT-TO-RIGHT MARK). Row 68156, `KRISHNA LANKA`: `"16.5062° N"` / `"80.6225° E"`.
Row 60943, `R K HOSPITAL`: `"25.44.56.410"` / `"82.41.55.32"` (DMS written with dots).
Row 34714, `CHC NALKHEDA`: `"76.235703."` (trailing period). Row 253537,
`AGRA FORT RAILWAY HEALTH UNIT`: `Longitude` = `" "` (a single space).

**Zero** — row 36262, `PHC BAKHATGARH` (MP); row 68879, `MY HEALTH ACCESS SYSTEM` (AP);
row 85058, `DIABECITY A PREMIER DIABETES CENTRE AT BARPETA` (Assam); row 90228,
`D PATH LAB` (Chandigarh).

**Fix.** Strip U+200E/U+200F and degree symbols, then `to_numeric`. Null out `0,0`,
`|lat|>90`, `|lon|>180`. Swap the 342 rows where the pair is valid only when reversed —
this is safe because India's lat and lon ranges do not overlap. Null the residual
out-of-bbox rows rather than guessing.

---

## S2-4 — 6,271 byte-identical duplicate rows; 21.9% redundancy on name+geo

| measure | redundant rows | % of file |
|---|---|---|
| identical across all 46 columns | 6,271 | 1.94% |
| identical ignoring `Facility ID` | 10,234 | 3.16% |
| normalised name + lat/lon @ 4dp (~11 m) | 70,846 | 21.90% |
| normalised name + lat/lon @ 3dp (~110 m) | 71,770 | 22.19% |
| normalised name + `new_district_name` | 81,780 | 25.28% |

Example of an exact duplicate: rows **261 and 262** are identical in all 46 fields
(`Facility ID` 500319, `BHANU MULTISPECIALITY HOSPITAL`).

Method: exact-match blocking keys over the full population — normalised name is
NFKD→ASCII, lowercased, non-alphanumerics→space, whitespace collapsed. **No sampling; all
323,460 rows.** Because this is exact-key blocking rather than fuzzy matching, every figure
is a **lower bound** on true duplication.

**Fix.** Drop exact duplicates first (they are unambiguous), then run S1-1's `24/7`
collapse, then send the name+geo near-dupes to the cross-dataset resolver rather than
merging them blindly here — 4dp name+geo agreement is strong evidence but not proof.

---

## S2-5 — 129 test/dummy records are still present

`TESTING` ×21, `TEST` ×7, `XYZ` ×7, `TEST FACILITY` ×6, `ABC CLINIC` ×4,
`DUMMY HOSPITAL FOR NHCX INTEGRATION ONLY` ×4, `TEST GAURAV CLINIC` ×3, `DEMO HOSPITAL` ×3,
`TEST NURSE GUNJAN` ×2, `TEST DHIS MAIL AD SMS` ×2, `AAA PMJAY` ×2, … First occurrences at
rows 3219, 6644, 12595, 16015, 16207, 37726, 37727.

One of them carries a real coordinate and enters the near-dupe blocking key:
`testing|28.5682|77.2121` is a repeated name+geo key.

**Fix.** Quarantine on a name regex (`^(test|testing|xyz|abc|dummy|sample|demo)\b`) into a
review table rather than deleting — a few, e.g. `ABC HOSPITAL`, could be legitimate.

---

## S2-6 — `S8_emp` / `S9_emp` use blank instead of `0`, and their specialty names are unresolved

`S8_emp` is blank on 319,370 rows and `"1.0"` on 4,090; `S9_emp` is blank on 319,837 and
`"1.0"` on 3,623. Every other specialty flag stores a literal `0`. Naive `pd.read_csv`
therefore types these two as `float64` while the other 23 are `int64`, and any
`sum()`/`GROUP BY` that treats blank as missing rather than as zero will disagree with the
other columns.

Worse, `merged_specialties` carries the **literal strings** `"S8"` and `"S9"` where every
other code was expanded to a specialty name — the upstream decoder failed on exactly these
two. Example, row 63: `"Polytrauma, Plastic & reconstructive, Burns management, S8, S9,
Urology, Orthopaedics, Obstetrics & Gynaecology, Otorhinolaryngology, General Surgery"`.

**Fix.** Read as `str`, treat blank as `0`, cast to `int8`. The names remain unknown —
escalated in `questions.md`.

---

## S3-1 — Three of the four "verifier" columns are exact copies

`Name verifier`, `Address verifier`, `Facility Type verifier` and `Ownership verifier` are
**byte-identical on all 323,460 rows** (Green 281,386 / Orange 28,615 / Blue 13,459) — the
column names promise four independent verification outcomes and deliver one.

**Fix.** Keep `Name verifier`, rename to `record_quality_tier`, drop the other three. Not
PII — these are colour tiers, not people.

---

## S3-2 — `Google Maps Link` is not a link

0 of 323,460 rows start with `http`. The column holds the bare string `<lat>,<lon>`, and
reproduces `Latitude`/`Longitude` to 4dp on 323,439 of 323,440 comparable rows (maximum
deviation 1.07e-14 degrees). It carries no independent information.

Its one use: it preserves the **raw pre-cleaning** coordinate string, which is how the 20
malformed-coordinate rows in S2-3 are diagnosable (e.g. row 320607,
`"26.210161338547195, , 84.3548238744555"` — a stray empty field; row 253537,
`"27.182597717100556, ,78.01800471271476"`).

**Fix.** Drop from the canonical table; retain in a provenance side-table for the 20
malformed rows.

---

## S3-3 — 23 rows have a blank `hospital_name`; 426 names are ≤3 characters

Blank at rows 52, 53, 53478, 64202–64205, 90490, 102975–102980, 118554, 188592, 212247,
212248, 228613, 252625–252627, 271107. Row 52 is `Facility ID` 4200, address
`", Pedatummidi , Bantumilli Krishna, Andhra Pradesh - 531324"`, type `Hospital`.

Uselessly short names: `HWC` ×61, `OPD` ×20, `PHC` ×18, `CHC` ×14, `ANM` ×10, `CHO` ×10,
`ENT` ×9, `EYE` ×5. Six names are purely numeric. Generic names are also common:
`HEALTH AND WELLNESS CENTER` ×262, `HOSPITAL` ×254, `PHARMACY` ×144, `CITY HOSPITAL` ×138.

**Fix.** Mark blank and ≤3-character names as `name_is_unusable` so entity resolution
falls back to address + geo for them. Note that `HEALTH AND WELLNESS CENTER` (262) and
`HEALTH AND WELLNESS CENTRE` (92) are the same thing spelled two ways — normalise
`CENTER`/`CENTRE` before blocking.

---

## S3-4 — 63,594 rows carry 15 decimal places of fake precision

Decimal-place distribution of `Latitude`: 6 dp on 100,591 rows, then **15 dp on 63,594,
14 dp on 50,301, 13 dp on 40,594** — **155,023 rows (47.93%) have ≥12 decimals**. That is
float64 round-trip noise from a prior pipeline, not survey precision (15 dp is ~10⁻⁹ m).
At the other end, 5,249 rows have ≤2 decimals (~1 km or coarser), e.g. row with
`KATURI MEDICAL COLLEGE & HOSPITAL` at `16.23, 80.31`.

**Fix.** Round all coordinates to 6 dp (~0.1 m) on load. Store the observed decimal count
as a crude `geo_accuracy` hint — ≤2 dp genuinely is low-accuracy.

---

## S3-5 — Casing and sentinel inconsistencies in the admin-geo columns

- `State_name` is mixed-case with lowercase `and`; `new_state_name` is Title Case with
  `And`. Their only substantive difference is `Andaman and Nicobar` vs
  `Andaman And Nicobar Islands` (238 rows).
- `District_name` is **lowercase** (`anoopgarh`, `una`); `new_district_name` is Title Case
  (`Anupgarh`, `Anjaw`). A naive equality test reports 0/323,460 agreement; case-folded it
  is 322,593/323,460.
- `District_name` contains the literal sentinel **`Not Found`** on rows 2794 and 2795,
  which are then assigned `new_district_name` = `Ntr` — while their address reads
  `"…, Andhra Pradesh - 533001"` (Kakinada, not NTR district).
- `state_code` and `district_code` are stored as floats (`"35.0"`, `"602.0"`).

**Fix.** Upper-case both name families before comparison; map `Not Found` → NULL; cast both
codes to `int`.

---

## Not defects — verified clean

Worth recording so nobody re-checks them:

- **`Facility Type`** (37 values), **`Ownership`** (3), **`ABDM Enabled`** (2),
  **`24/7`** (2), **verifier** (3): zero leading/trailing whitespace, zero double spaces,
  and `n_distinct` is unchanged after `strip().lower()`. `GROUP BY` is safe on all of them.
- **`Address`**: 0 blanks, minimum length 30 characters, and 323,456/323,460 end in
  `- <6-digit pin>`. A 6-digit pincode is extractable from **323,454** rows (15,723
  distinct); 13 rows contain a leading-zero 6-digit string that is not a valid Indian pin.
- **`state_code`**: 1:1 with `new_state_name` on all 34 present values, matching published
  LGD numbering exactly.
- **`district_code`**: perfectly bijective with `new_district_name` (615 ↔ 615); no code
  maps to two names, no name maps to two codes, no district spans two states.
- **The specialty codebook**: exact set-equality between each of the 25 flags and a token
  in `merged_specialties`, on all 323,460 rows. See `PROFILE.md`.
- **No PII columns.** No phone, email, or person-name field. The `verifier` columns are
  colour tiers. (`hospital_name` does contain sole-practitioner names such as
  `DR GAURAV MISHRA` — indirect personal data, but that is the facility's registered name.)
