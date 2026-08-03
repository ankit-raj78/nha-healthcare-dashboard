# CDAC_BB_B — data-quality defects

Source: `CDAC_BB_DATASET - Sheet1.csv`, 5,889 rows × 10 cols.
Row indices below are **0-based pandas row indices** after
`pd.read_csv(f, encoding="utf-8", dtype=str, keep_default_na=False, na_values=[""])`
(add 2 to get the spreadsheet line number).

Severity: **S1** = will produce wrong answers silently · **S2** = loses data or blocks a join ·
**S3** = cosmetic / recoverable.

---

## S1-1 · Rows 5679–5888 are a duplicate of rows 5469–5678 — 210 phantom facilities

The last 210 rows of the file are the same 210 records as rows 5469–5678, pasted in a second
time. Field-by-field over the 210 pairs:

| field | identical |
|---|---|
| `Name` | 210/210 |
| `Address` | 210/210 |
| `State` | 210/210 |
| `Category` | 210/210 |
| `Email` | 210/210 |
| `new_longitude` / `new_latitude` | 210/210 |
| `Phone` | 209/210 (row 5527/5737 `Vision Blood Centre Bhopal`: `0.00E+00` vs `0` — the same value) |
| `Latitude` / `Longitude` | 0/210 identical, but **median 0.00042 km apart, max 0.00075 km** |

The coordinates differ only because the head copy is rounded to 5 decimals and the tail copy is
full float precision:

- Row **5469** `AKSHAYA BLOOD CENTRE` → `15.82497 / 78.04082`
- Row **5679** `AKSHAYA BLOOD CENTRE` → `15.82497498 / 78.04081521`  ← same point, 0.4 m apart

All 210 tail rows' `(Name, Address)` keys already exist in rows 0–5678.

**Fix:** drop rows 5679–5888 outright, or keep the tail copy (better precision) and drop rows
5469–5678. Either way, `COUNT(*)` on this file overstates the roster by 210.

---

## S1-2 · Sikkim's five rows are labelled `Rajasthan`

Rows **3716–3720** are Sikkim blood centres — their `Address` fields say `East Sikkim`,
`west sikkim`, `East District`, `South District` — but `State = "Rajasthan"`.

| row | Name | Address (excerpt) | `State` |
|---|---|---|---|
| 3716 | Blood Centre Central Referral Hospital | `3rd floor, 5th Mile Tadong, East Sikkim, Gangtok, Dist. East District` | Rajasthan |
| 3717 | Central Blood Centre, Stnm Hospital | `… STNM Multispecility Hospital, Gangtok, East Sikkim …` | Rajasthan |
| 3718 | District Hospital Blood Bank | `district hospital geyzing, west sikkim, geyzing, Dist. West District` | Rajasthan |
| 3719 | District Hospital Blood Bank Singtam | `… Singtam, Dist. East District` | Rajasthan |
| 3720 | Namchi District Blood Centre | `Government General Hospital, Namchi, Namchi, Dist. South District` | Rajasthan |

Consequence: this file reports **36 states**, no Sikkim, and 388 Rajasthan rows instead of 383.
`CDAC_BB_A` has the same five rows at the same indices labelled `SIKKIM`.

**Fix:** set rows 3716–3720 to `Sikkim`, or take the whole `State` column from CDAC_BB_A.

---

## S1-3 · Five `State` values are misspelled and will not join to any LGD/census table

| value in file | rows | correct |
|---|---|---|
| `Andra Pradesh` | 326 | Andhra Pradesh |
| `Gujrat` | 382 | Gujarat |
| `Chattisgarh` | 181 | Chhattisgarh |
| `Jammu and Kasmir` | 66 | Jammu and Kashmir |
| `Lakshwadeep` | 1 | Lakshadweep |

That is **956 rows (16.2%)** that will silently fail an exact-match state join. CDAC_BB_A spells
all 37 correctly.

**Fix:** apply a spelling map, or take the `State` column from CDAC_BB_A.

---

## S1-4 · `new_latitude` / `new_longitude` are transposed for rows 5469–5888

For rows 0–5468 the pair is `(longitude, latitude)` as labelled. From row 5469 to the end of the
file (426 rows) it is `(latitude, longitude)` — the columns are swapped.

- Row **5679** `AKSHAYA BLOOD CENTRE`, Kurnool: `new_longitude = 15.82477`, `new_latitude = 78.04035`.
  15.8 is a latitude and 78.0 is a longitude.
- Row **0** `G.B.Pant Hospital`, Port Blair: `new_longitude = 92.73976`, `new_latitude = 11.67572`
  — correct as labelled.

426 rows are valid *only* when swapped, 5,119 *only* as labelled, and zero rows are valid both
ways, so the split is unambiguous.

**Fix:** drop both columns (see S1-5).

---

## S1-5 · `new_latitude` / `new_longitude` are 5.8% garbage regardless of orientation

344 rows fall outside `lat 6–38 / lon 68–98` in **both** axis orders.

| row | Name | `new_longitude` | `new_latitude` | actually |
|---|---|---|---|---|
| 3 | Aapadbandhu Blood Bank Vinukonda | `-83.7623` | `37.15627` | Kentucky, USA |
| 9 | All India Institute Of Medical Sciences Blood Centre Mangalagiri | `-157.862` | `21.30623` | Honolulu |
| 114 | BSC-RAJAMPET BSU | `-44.2575` | `-2.55289` | Maranhão, Brazil |
| 138 | Cpt blood centre | `116.448` | `39.93507` | Beijing |

The single pair `8.804821 / 61.24833` (Arabian Sea) is repeated on **35** rows — a geocoder
fallback, not a place. 2,984 rows share a `new_*` pair with some other row.

**Fix:** drop `new_latitude` and `new_longitude`; do not use them as a fallback for the 25 rows
with a missing `Latitude`.

---

## S1-6 · `Phone` is 84% unusable but 92% non-null

`Phone.notna()` reports 5,413/5,889 (91.9%). Actually dialable: **925 rows (15.7%)**.

| pattern | rows | example |
|---|---|---|
| Excel scientific notation | 3,783 | row 2 `Aapadbandhu Blood bank` → `9.12E+09` |
| literal `0` / `0.00E+00` | 1,043 | row 872 `CHC, Kawant (BSU)` → `0` |
| `########` | 172 | row 58 `BSC - BUDITHI BSU` → `########` |
| `#ERROR!` | 3 | rows 334, 1518, 3251 |
| null | 476 | |

The scientific-notation damage is irreversible.

**Fix:** null out `^\d\.\d+E\+\d+$`, `^0+$`, `^#`; then split on `,`. Do not use `Phone` for ER.

---

## S1-7 · 1,449 rows are Blood Storage Units, not blood banks, and nothing says so

24.6% of rows have `BSU` inside `Name`; a further 107 have `BSC`. A BSU is a storage annexe of a
licensed blood centre, not an independent centre.

- Row 1011 `Katavara (BSU)`, address `-, Dahod, Dist. Dahod`
- Row 875 `CHC, Khambhat BSU` (which also has no coordinate — see S2-1)

**Fix:** parse `\b(BSU|BSC)\b` out of `Name` into a `facility_subtype_raw` field before
publishing any facility count.

---

## S2-1 · 25 rows have no coordinate at all

`Latitude` and `Longitude` are both null on rows
**875, 911, 917, 1458, 1470, 1471, 1495, 1515, 1610, 1772, 2803, 2825, 3805, 3995, 4008, 4016,
4041, 4094, 4132, 4267, 4271, 4274, 5279, 5394, 5428**.

They are all BSU/RH rows in Gujarat (3), Karnataka (7), Maharashtra (2), Tamil Nadu (10) and
West Bengal (3) — e.g. row 875 `CHC, Khambhat BSU`.

`CDAC_BB_A` has a valid in-India coordinate for **every one of these 25 rows**
(row 875 → `22.32630144 / 72.62971906`).

**Fix:** fill from CDAC_BB_A positionally (row *i* of B ↔ row *i* of A for all i < 5679).

---

## S2-2 · 5 coordinates are outside India

| row | State | Name | `Latitude` | `Longitude` | lands in | CDAC_BB_A has |
|---|---|---|---|---|---|---|
| 482 | Bihar | Rddjm Medical College & Hospital Turki Muzaffarpur | `38.96375` | `35.24332` | Turkey | `26.03297613 / 85.33101487` |
| 523 | Bihar | SDH Jaynagar, Madhubani (BSU) | `54.3972` | `18.2252` | Poland | `26.59694399 / 86.1370695` |
| 524 | Bihar | SDH Jhanjharpur, Madhubani (BSU) | `54.3972` | `18.2252` | Poland | `26.25351924 / 86.27870045` |
| 534 | Bihar | SDH Phulparas, Madhubani (BSU) | `54.3972` | `18.2252` | Poland | `26.31963821 / 86.47716978` |
| 4651 | Tripura | District Hospital, Dhalai, Kulai, Blood Centre | `1.662981` | `103.5999` | Singapore | `23.95019416 / 91.84096931` |

Note rows 523/524/534 share the identical bogus pair.

**Fix:** replace from CDAC_BB_A. There are **zero** rows where CDAC_BB_A's coordinate is
unusable and this file's is fine.

---

## S2-3 · No `District` column

`CDAC_BB_A` carries `District` (current name) and `dist_name` (legacy/LGD name); this file has
neither.

- `District` is fully recoverable: the trailing `Dist. <X>` token in `Address` is parseable for
  **5,888/5,889** rows and reproduces CDAC_BB_A's `District` for 5,677/5,679 shared rows. The one
  failure is row **299** `District Hospital Namsai BSU, Namsai, Dist. ` — empty district token.
- `dist_name` is **not** recoverable from this file. It matches the parsed address token for only
  5,040/5,679 rows, so the other 639 legacy district aliases exist only in CDAC_BB_A.

**Fix:** derive `district_raw` by regex `Dist\.\s*([^,]*)$`; accept that `district_alt_raw` is lost
unless CDAC_BB_A is also loaded.

---

## S2-4 · 965 addresses are placeholders

16.4% of rows have an `Address` of the form `NA, <place>, Dist. <district>` or `-, <place>, …`.

- Row 491 `NA, Darbhanga, Dist. Darbhanga`
- Row 1011 `-, Dahod, Dist. Dahod`

Only 114 rows (1.9%) contain a 6-digit token that might be a pincode; there is no pincode column.

**Fix:** flag `address_is_placeholder` on `^\s*(NA|-|\.)\s*,`; exclude from address similarity.

---

## S2-5 · No primary key of any kind

| candidate | duplicate rows |
|---|---|
| `Name` | 350 |
| `Email` | 1,955 (plus 1,701 nulls) |
| `(Name, Address)` | 213 |
| `(Name, Address, State)` | 213 |
| `(Name, Address, Latitude, Longitude)` | **3** |

**Fix:** synthesise `source_facility_id = "CDAC_BB_B:" + str(row_index)`.

---

## S3-1 · One exact duplicate row and two conflicting near-duplicates (in addition to S1-1)

- Rows **872 / 873** — `CHC, Kawant (BSU)`, `-, Chhota Udaipur, Dist. Chhotaudepur` — identical in
  all 10 columns.
- Rows **1977 / 1978** — `Holy Cross Hospital`, `Kottiyam, Kollam, Dist. Kollam`. Same facility,
  but 1977 has `Category = Private` / `Phone = null` and 1978 has `Category = Charitable/Vol` /
  `Phone = 9.40E+09`. **The ownership fields conflict.**
- Rows **3172 / 3173** — `CHC-Gharyala BSU`. Identical except `Phone = "0.00E+00"` vs `"0"`.

Near-dupes on (normalised name + coordinate rounded to ~110 m): **213** (210 of them from S1-1).
Rows sharing a normalised name with some other row: **387**.

---

## S3-2 · 52 rows contain U+FFFD mojibake

- Row **989** `Indian Red Cross Society, Anand District Branch, ï¿½SARDAR BHAVANï¿½, …`
- Row **1184** `Golf Course Road , Sushant Lok ï¿½II, Sector 56, …`

**Fix:** replace `ï¿½` / `�` with a space and collapse whitespace.

---

## S3-3 · 28 `Email` values are structurally invalid

- Row **102** `ahpalakonda@gmail. Com`
- Row **216** `gimsrbloodbank @gitam.edu`
- `BSUnamsai0922@123`, `Lifelinebloodcentre123@gmail`, `Civil Surgeon [civilsurgeonbsp@gmail.com`

243 addresses are shared by more than one row (inflated by the S1-1 duplication).

**Fix:** strip internal whitespace, lowercase, null anything still unparseable. Never use `Email`
as an identity key.

---

## S3-4 · 1,054 rows share a coordinate with another row

17.9% of rows are not at a unique point (excluding the 25-row `nan,nan` group). Most-repeated:
`8.548821, 77.65361` (14 rows), `12.91652, 79.1325` (13), `12.9716, 77.59456` (13, central
Bengaluru).

**Fix:** set `geo_accuracy = 'centroid_suspected'` where a pair occurs on more than 2 rows.

---

## S3-5 · File has no trailing newline

The last line (`… R.G. Kar Medical College And Hospital …`) is not newline-terminated, so
`wc -l` reports 5,889 while the file actually has 5,890 physical lines (1 header + 5,889 records).
Harmless for pandas; will trip line-count sanity checks and naive `cat`-based concatenation.
