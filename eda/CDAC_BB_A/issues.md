# CDAC_BB_A — data-quality defects

Source: `16_MAY_AR_CDAC_BB_DATASET.csv`, 5,679 rows × 12 cols.
Row indices below are **0-based pandas row indices** after
`pd.read_csv(f, encoding="utf-8", dtype=str, keep_default_na=False, na_values=[""])`
(add 2 to get the spreadsheet line number).

Severity: **S1** = will produce wrong answers silently · **S2** = loses data or blocks a join ·
**S3** = cosmetic / recoverable.

---

## S1-1 · `new_latitude` / `new_longitude` are transposed for rows 5469–5678

For rows 0–5468 the pair is `(longitude, latitude)` as labelled. From row 5469 to the end of the
file it is `(latitude, longitude)` — the columns are swapped.

- Row **5469** `AKSHAYA BLOOD CENTRE`, Kurnool, Andhra Pradesh:
  `new_longitude = 15.82497498`, `new_latitude = 78.04081521`.
  15.8 is a latitude and 78.0 is a longitude; Kurnool is at 15.83 N, 78.04 E.
- Row **0** `G.B.Pant Hospital`, Port Blair: `new_longitude = 92.73976`, `new_latitude = 11.67572`
  — correct as labelled. Port Blair is 11.7 N, 92.7 E.

216 rows are valid *only* if the axes are swapped; 5,119 are valid only *as labelled*; zero rows
are valid both ways, so the split is unambiguous.

**Fix:** drop both columns (see S1-2). If they must be kept, apply
`if row_index >= 5469: swap(new_latitude, new_longitude)`.

---

## S1-2 · `new_latitude` / `new_longitude` are 6.1% garbage regardless of orientation

344 rows (6.06%) fall outside `lat 6–38 / lon 68–98` in **both** axis orders. These are
geocoder failures that resolved a fragmentary address to a foreign place.

| row | Name | `new_longitude` | `new_latitude` | actually |
|---|---|---|---|---|
| 3 | Aapadbandhu Blood Bank Vinukonda | `-83.7623` | `37.15627` | Kentucky, USA |
| 9 | All India Institute Of Medical Sciences Blood Centre Mangalagiri | `-157.862` | `21.30623` | Honolulu |
| 114 | BSC-RAJAMPET BSU | `-44.2575` | `-2.55289` | Maranhão, Brazil |
| 138 | Cpt blood centre | `116.448` | `39.93507` | Beijing |

One bad pair, `8.804821 / 61.24833` (Arabian Sea), is repeated on **35** rows — it is the
geocoder's fallback, not a real place. Median distance from a row to its own district's centroid
is 7.6 km for these columns but **p90 is 1,549 km**, and 11.9% are more than 150 km out. The
authoritative `Latitude`/`Longitude` columns score 6.3 km median / 43.4 km p90 / 0.9% beyond
150 km.

**Fix:** drop `new_latitude` and `new_longitude`. Do not use them as a fallback.

---

## S1-3 · `Phone` is 84% unusable but 92% non-null

`Phone.notna()` reports 5,203/5,679 (91.6%). Actually dialable: **893 rows (15.7%)**.

| pattern | rows | example |
|---|---|---|
| Excel scientific notation | 3,610 | row 2 `Aapadbandhu Blood bank` → `9.12E+09` |
| literal `0` / `0.00E+00` | 1,042 | row 872 `CHC, Kawant (BSU)` → `0` |
| `########` (Excel column-too-narrow) | 168 | row 58 `BSC - BUDITHI BSU` → `########` |
| `#ERROR!` | 3 | rows 334, 1518, 3251 |
| null | 476 | |

The scientific-notation damage is **irreversible** — `9.12E+09` retains 3 significant digits of a
10-digit number.

**Fix:** null out every value matching `^\d\.\d+E\+\d+$`, `^0+$`, `^#`, then split the remainder
on `,`. Record `phone_recovered_pct = 15.7` so downstream does not treat this as a live field.
Do not use `Phone` as an ER match feature.

---

## S1-4 · 1,443 rows are Blood Storage Units, not blood banks, and nothing says so

25.4% of rows have `BSU` inside `Name` (1,435 of them `Category = Govt.`); a further 107 have
`BSC`. A BSU is a storage annexe of a licensed blood centre, not an independent centre.

- Row 1011 `Katavara (BSU)`, address `-, Dohad, Dist. Dohad`
- Row 875 `CHC, Khambhat BSU`

**Fix:** parse `\b(BSU|BSC)\b` (and `CHC`/`SDH`/`DHH`/`RH`/`SGH`) out of `Name` into the proposed
`facility_subtype_raw` field before any facility count is published.

---

## S2-1 · A global uppercase-the-state find/replace corrupted `Name`, `Address` and `Email`

Whoever normalised the `State` column to UPPERCASE ran the replacement across the whole row, so
state names embedded in other fields were uppercased too.

- Row **351** `Name = "Lower ASSAM Hospital Blood Centre"` (should be `Lower Assam …`)
- Row **351** `Email = "lowerASSAMhospital@yahoo.in"` (should be `lowerassamhospital@yahoo.in`)
- Row **411** `Name = "Blood Centre Sadar Hospital, BIHARsharif"` (should be `Biharsharif`)
- Row **808** `Name = "M/S Venkateshwar Hospital New DELHI, Dwarka Sector-18 A"`
- Row **32** `Address = "… Konaseema District, ANDHRA PRADESH, RAMACHANDRAPURAM, Dist. Konaseema"`

Affected: **73 `Name` values, 422 `Address` values (416 case-only), 22 `Email` values.**

**Fix:** lift `Name`, `Address` and `Email` verbatim from `CDAC_BB_DATASET - Sheet1.csv`
positionally (row *i* of A ↔ row *i* of B, verified aligned for all 5,679 rows). That file has the
correct casing for all of them.

---

## S2-2 · Row 2952 has a misspelled facility name

Row **2952** `Name = "J N Hospital Blood Bank,Serchipp"`. The Mizoram district is **Serchhip**;
the same row's `Address` and `District` both say `Serchhip`. CDAC_BB_B has it right.

**Fix:** take the string from CDAC_BB_B (this is covered by the S2-1 fix).

---

## S2-3 · `State` value `DADRA & NAGAR HAVE` is truncated at 18 characters

Row **735** `Indian Red Cross Society Blood Centre Dadra & Nagar Haveli`, `State = "DADRA & NAGAR HAVE"`.
`ANDAMAN & NICOBAR` and `ARUNACHAL PRADESH` are also 17–18 chars, which suggests an 18-char column
width somewhere upstream — but they happen to be complete words, so only this one value is broken.

**Fix:** map `DADRA & NAGAR HAVE` → `DADRA AND NAGAR HAVELI` before any LGD join. Also expand
`&` → `AND` and normalise `JAMMU & KASHMIR`, `DAMAN & DIU`, `ANDAMAN & NICOBAR`.

---

## S2-4 · 43 `dist_name` values are truncated at 24 chars and marked with `*`

Rows **6, 16, 23, 27, 28, 49, …** — three distinct truncated values:
`Sri Potti Sriramulu Nell*`, `North Twenty Four Pargan*`, `South Twenty Four Pargan*`.
The corresponding `District` values are complete (`Sri Potti Sriramulu Nellore`, etc.).

**Fix:** strip the trailing `*` and treat the value as a prefix; resolve against the complete
`District` value on the same row.

---

## S2-5 · 965 addresses are placeholders

17.0% of rows have an `Address` of the form `NA, <place>, Dist. <district>` or `-, <place>, …`.

- Row 491 `NA, Darbhanga, Dist. Darbhanga`
- Row 492 `NA, Jamui, Dist. Jamui`
- Row 1011 `-, Dohad, Dist. Dohad`

Only the district and a place name survive. Combined with the fact that only 93 rows (1.6%)
contain a 6-digit pincode, address-based matching is not viable for this dataset.

**Fix:** flag `address_is_placeholder` when `Address` matches `^\s*(NA|-|\.)\s*,`; do not feed
these into address similarity.

---

## S2-6 · No primary key of any kind

| candidate | duplicate rows |
|---|---|
| `Name` | 140 |
| `Email` | 1,745 (plus 1,698 nulls) |
| `(Name, Address)` | 3 |
| `(Name, Address, State)` | 3 |
| `(Name, Address, Latitude, Longitude)` | **3** |

**Fix:** synthesise `source_facility_id = "CDAC_BB_A:" + str(row_index)` and carry it as
provenance.

---

## S3-1 · One fully exact duplicate row, plus two conflicting near-duplicates

- Rows **872 / 873** — `CHC, Kawant (BSU)`, `-, Chhota Udaipur, Dist. Chhotaudepur`,
  `22.30849 / 74.012` — identical in all 12 columns. Safe to dedupe.
- Rows **1977 / 1978** — `Holy Cross Hospital`, `Kottiyam, Kollam, Dist. Kollam`,
  `8.865947 / 76.67086`. Same facility, but row 1977 has `Category = Private` / `Phone = null`
  and row 1978 has `Category = Charitable/Vol` / `Phone = 9.40E+09`. **The ownership fields
  conflict** — an unresolved merge.
- Rows **3172 / 3173** — `CHC-Gharyala BSU`. Identical except `Phone = "0.00E+00"` vs `"0"`.

Near-dupes on (normalised name + coordinate rounded to ~110 m): **5**.
Rows sharing a normalised name with some other row: **177**.

**Fix:** drop the exact pair; escalate 1977/1978 to a human (see questions.md Q-4); collapse
3172/3173 after phone normalisation.

---

## S3-2 · 47 rows contain U+FFFD mojibake

An earlier encode/decode round trip replaced non-ASCII punctuation with `ï¿½`.

- Row **989** `Indian Red Cross Society, Anand District Branch, ï¿½SARDAR BHAVANï¿½, Opp. Nagarpalika, …`
  (was a pair of curly quotes)
- Row **1184** `Golf Course Road , Sushant Lok ï¿½II, Sector 56, …` (was an en dash)
- Row **1207** `National Highway No. 1, Village ï¿½ Siwah, …`

**Fix:** replace `ï¿½` / `�` with a space and collapse whitespace. The original characters
are unrecoverable but were punctuation only.

---

## S3-3 · 28 `Email` values are structurally invalid

- Row **102** `ahpalakonda@gmail. Com` (space before TLD)
- Row **216** `gimsrbloodbank @gitam.edu` (space before `@`)
- `BSUnamsai0922@123` (no domain)
- `Civil Surgeon [civilsurgeonbsp@gmail.com` (a label was pasted in)
- `Lifelinebloodcentre123@gmail`, `datarambloodcentre323@gmail` (no TLD)

39 addresses are shared by more than one facility (`nandkishor@arpanbloodbank.org` on 6 rows).

**Fix:** strip internal whitespace, lowercase, append `.com` only where the domain is a known
provider missing its TLD, and null the rest. Never use `Email` as an identity key.

---

## S3-4 · `District` is 100% redundant with `Address`

Parsing the trailing `Dist. <X>` out of `Address` reproduces `District` for **5,677/5,679** rows.
The two exceptions:

- Row **299** `Address = "District Hospital Namsai BSU, Namsai, Dist. "` — the district token is
  empty; `District = "Namsai"` supplies it.
- Row **1011** `Address = "-, Dohad, Dist. Dohad"` but `District = "Dahod"` (the current
  spelling; `dist_name = "Dohad"`).

This is not a defect in itself — it means the column costs nothing to keep and that CDAC_BB_B's
lack of a `District` column is fully recoverable. `dist_name`, by contrast, is only reproducible
for 5,040/5,679 rows and is genuinely extra information.

---

## S3-5 · 1,030 rows share a coordinate with another row

18.1% of rows are not at a unique point. The most-repeated pairs:
`8.548821, 77.65361` (14 rows), `12.9716, 77.59456` (13, central Bengaluru),
`12.91652, 79.1325` (13), `10.79048, 78.70467` (12).

These are town/city centroids substituted for building locations.

**Fix:** set `geo_accuracy = 'centroid_suspected'` where a coordinate pair occurs on more than 2
rows; require a name match in addition to proximity when resolving entities.
