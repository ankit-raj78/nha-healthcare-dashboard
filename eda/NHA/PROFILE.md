# NHA — `1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv`

**323,460 data rows × 46 columns.** 102 MB. No BOM, no embedded newlines, no ragged rows,
no index column. Naive `pd.read_csv` gets the shape right; read with `dtype=str` anyway,
because inference silently turns `Latitude` into `object` and `S8_emp`/`S9_emp` into
`float64`.

> `wc -l` says 323,461. That is 1 header + 323,460 data rows on a newline-terminated file.
> The brief's "323,461 rows" is one too high.

## What this is

India's **National Health Authority facility register** — effectively an export of the
Health Facility Registry (HFR) under ABDM — with **PMJAY empanelment specialties grafted
on**. The filename dates it March 2025; nothing inside the file records a snapshot date.

Two provenance layers are visible in the schema. The base layer is the HFR record
(`Facility ID`, name, address, type, ownership, `ABDM Enabled`, coordinates). On top of
that someone ran (a) a verification pass that produced the `* verifier` traffic-light
columns, (b) a geocoding pass that produced `Google Maps Link` and the cleaned
`Latitude`/`Longitude`, (c) an LGD re-coding pass that produced `new_state_name` /
`new_district_name` / `state_code` / `district_code`, and (d) a PMJAY join that produced
the 25 `M*_emp`/`S*_emp` flags and `merged_specialties`.

By volume this is the project spine: 258,756 distinct facilities, more than the other nine
datasets are likely to hold combined.

## The headline finding: the specialty codebook is solved

`merged_specialties` **decodes the coded specialty columns exactly.** For each of the 25
`M*/S*_emp` columns, the row set where the flag is 1 is *precisely* the row set where a
particular specialty name appears in `merged_specialties` — zero rows in either direction
of the symmetric difference, across all 323,460 rows. This is a proof, not a correlation.

| | | | |
|---|---|---|---|
| `M1_emp` General Medicine (10,652) | `M2_emp` Paediatric medical management (6,405) | `M3_emp` Neo-natal (2,944) | `M4_emp` Paediatric cancer (1,349) |
| `M5_emp` Medical Oncology (1,783) | `M6_emp` Radiation Oncology (1,275) | `M7_emp` Emergency Room Packages, <12 hrs (10,321) | `M8_emp` Mental Disorders Packages (1,396) |
| `M10_emp` OPD Diagnostic (4) | `S1_emp` General Surgery (11,485) | `S2_emp` Otorhinolaryngology (4,894) | `S3_emp` Opthalmology *(sic)* (4,455) |
| `S4_emp` Obstetrics & Gynaecology (10,040) | `S5_emp` Orthopaedics (8,847) | `S6_emp` Polytrauma (4,545) | `S7_emp` Urology (4,787) |
| `S8_emp` **unresolved** (4,090) | `S9_emp` **unresolved** (3,623) | `S10_emp` Plastic & reconstructive (3,176) | `S11_emp` Burns management (3,176) |
| `S12_emp` Cardiology (2,806) | `S13_emp` Cardio-thoracic & Vascular surgery (1,592) | `S14_emp` Paediatric surgery (2,585) | `S15_emp` Surgical Oncology (1,942) |
| `S16_emp` Oral and Maxillofacial Surgery (3,416) | | | |

The flags are plain **binary 0/1** — no counts, no names. `M` is medical, `S` is surgical,
the number is an ordinal position in the PMJAY specialty list. **`M9_emp` does not exist in
this file** (M1–M8 and M10 are present).

Three caveats, all in `questions.md`: **S8 and S9 are undecoded** — `merged_specialties`
carries the literal strings `"S8"` and `"S9"`, so the upstream decoder failed on exactly
those two codes. **S10 vs S11 is ambiguous** — the two columns are byte-identical and their
two names always co-occur, so the assignment is by ordinal position only. And the
specialty data is thin: **only 15,873 rows (4.91%) have any specialty at all.**

This mapping should be tested against PMJAY's parallel `_emp`/`_upg` columns immediately.
If it transfers, it is the codebook for both datasets.

## What it's good for

- **Coverage and identity.** 99.86% have a usable name, 100% have a district and state,
  100% have a non-empty address, 99.60% have coordinates inside India's bbox.
- **Clean analytical enums.** `Facility Type` (37 values), `Ownership` (3), `ABDM Enabled`
  (2) have zero case or whitespace variants — `GROUP BY` works as-is.
- **Real LGD state codes.** `state_code` is confirmed 1:1 with `new_state_name` across all
  34 values and matches the published LGD numbering.
- **Address is 100% populated** and machine-assembled to a regular shape
  (`<premise>, <locality> <district>, <State> - <PIN>`), so a 6-digit pincode is
  extractable from 323,454 of 323,460 rows.

## What it's bad for

- **Anything counted per-facility, without de-duplication first.** The grain is broken.
- **`24/7`.** Self-contradictory on 22.56% of facilities. Unusable as delivered.
- **National statistics.** This is not a complete register — see below.
- **Distance-based matching on coordinates alone.** Half the coordinates are shared.
- **Contact and capacity.** No phone, email, website, bed count, or accreditation column
  exists. Nothing to join on there.

## The three things that will bite you

**1. `Facility ID` is not unique, and the reason is a `24/7` fan-out.**
62,300 IDs repeat across 127,004 rows (max repeat: 220). It is tempting to conclude the
IDs collide — they don't. 62,298 of the 62,300 repeated groups carry the *same*
`hospital_name`, and only one group spans two states. **93.69% of the repeated groups are
groups where `24/7` takes both `yes` and `no`.** Among the 60,541 two-row groups, 53,728
differ *only* in `24/7`. Drop that one column and de-duplicate: 323,460 → 261,905 rows,
and only 3,146 IDs remain repeated. So `Facility ID` *is* the entity key; the file just has
a cross-product defect. If you `JOIN` on it without collapsing first, you will silently
double roughly 40% of your rows — and any `COUNT(*)` of facilities will be ~25% too high.

**2. Half the coordinates are geocoder centroids wearing 15 decimal places.**
165,448 rows (51.1%) share their exact lat/lon pair with at least one other row. The single
point `26.917858, 75.801292` is used by **9,870 rows spanning 28 Rajasthan districts** — it
is a Jaipur city centroid, not a facility. 22,187 rows sit on a coordinate shared by ≥50
rows. Meanwhile 63,594 rows carry 15 decimal places of float64 round-trip noise, which
looks like sub-millimetre survey precision and is nothing of the sort. Any entity
resolution that trusts "same coordinates ⇒ same facility" will over-merge catastrophically.
`Google Maps Link` will not save you: it is not a URL, it is the bare string `<lat>,<lon>`,
and it reproduces `Latitude`/`Longitude` to 4dp on 323,439 of 323,440 rows.

**3. West Bengal and Lakshadweep are entirely absent, and Odisha has 11 rows.**
LGD state codes 19 and 31 have zero rows. Odisha: 11 rows. Goa: 56. Meghalaya: 96. Tamil
Nadu: 2,567 — against Uttar Pradesh's 62,801 and Karnataka's 56,885. Because this dataset
is the biggest, it will look authoritative, and someone will compute "facilities per state"
from it. Those numbers describe this file's collection process, not India.

## Also worth knowing

**The four "verifier" columns are one column.** `Name verifier`, `Address verifier`,
`Facility Type verifier` and `Ownership verifier` are **byte-identical on all 323,460
rows** — not merely similarly distributed. They hold a 3-value traffic light (Green
281,386 / Orange 28,615 / Blue 13,459), not people, so **no PII**. Keep one, drop three.
What the colours mean is not determinable from the data.

**`new_district_name` is internally consistent but externally wrong in places.** It is
perfectly 1:1 with `district_code` (615 ↔ 615, no district spans two states), which makes
it look trustworthy. On the 867 rows where it disagrees with `District_name`, its value
appears in the row's own `Address` only 112 times, versus 600 for `District_name` — and on
263 of those rows *neither* matches. The failures look like fuzzy-match errors across state
lines: 92 rows recoded `nadia` (West Bengal) → `Narmada` (Gujarat), and 91 rows recoded
`una` → `Anjaw` where the address plainly says *Upper Subansiri*. The state columns, by
contrast, disagree only cosmetically (238 rows of "Andaman and Nicobar" vs "Andaman And
Nicobar Islands").

**Duplication beyond the ID problem.** 6,271 rows are byte-identical across all 46 columns;
10,234 are identical once you ignore `Facility ID`. On a normalised-name + 4dp-coordinate
blocking key, 70,846 rows (21.9%) are redundant. That is a lower bound — it is exact-key
blocking, not fuzzy matching.

**129 test records are still in the file** (`TESTING` ×21, `TEST` ×7, `XYZ` ×7,
`DUMMY HOSPITAL FOR NHCX INTEGRATION ONLY` ×4, `TEST NURSE GUNJAN` ×2, …). And 41,290
`Pharmacy` plus 14,865 `Diagnostic Laboratory` rows are not care-delivery facilities —
decide deliberately whether they belong in a "health facility" table.

## Entity-resolution verdict

**Name + geo + district blocking is viable on 99.46% of rows.** Only 449 rows (0.14%) lack
a usable name-and-district pair.

| Field | Coverage | Trust |
|---|---|---|
| `hospital_name` | 99.86% | **Medium.** 217,163 distinct, but 254 rows are literally `HOSPITAL` and 262 are `HEALTH AND WELLNESS CENTER`. Generic names need geo to disambiguate. |
| `new_state_name` / `state_code` | 100% | **High.** LGD-verified. |
| `new_district_name` | 100% | **Medium.** 1:1 with its code, but wrong on ~867 rows. |
| `Latitude`/`Longitude` | 99.60% in-bbox | **Low for precision, high for region.** Fine for state/district-level blocking; unsafe as a merge criterion. |
| `Address` | 100% | **High as a tiebreaker.** Extract the pincode — it is a better second blocking key than coordinates. |
| `Facility ID` | 100% | **High as an intra-NHA key**, useless across datasets. |

There is no phone, email, website, or registration number — so cross-dataset matching rests
entirely on name + admin geo + pincode. Block on `state_code` + pincode + normalised name;
use coordinates only to *rank* candidates, never to *decide* them.
