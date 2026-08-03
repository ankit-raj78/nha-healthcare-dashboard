# NHP — Data-quality issues

Source: `8_JULY_23_SRK_NHP_validated_and_standardized.csv`
All counts are over the **648 real data rows** unless stated. Row references are given as
`df_idx` (0-based index after `dropna(how='all')`) and `S. No.` (the file's own serial).

Severity: **S1** = will corrupt the canonical table or produce wrong matches if not fixed ·
**S2** = degrades quality or coverage · **S3** = cosmetic / low blast radius.

---

## S1-1 · 351 phantom rows (35.1% of what a naive read returns)

CSV records **649–999** are entirely empty — 29 consecutive commas, contiguous, at the end of the
file. `pd.read_csv` returns 999 rows; only 648 carry data.

```
byte tail: b',,,,,,,,,,,,,,,,,,,,,,,,,,,,\r\n' x 351
df_idx 648..998 : every field NaN
```

**Impact:** every column reports `notna().mean() == 0.6486`, making a ~100%-complete file look
35% empty. Any fill-rate threshold, any "drop sparse columns" rule, and any load into the canonical
table will be wrong. 351 nameless facilities would be inserted.

**Fix:** `df = df.dropna(how="all").reset_index(drop=True)` immediately after read. Assert
`len(df) == 648`.

---

## S1-2 · Facility names contain raw newlines — 73 rows (11.27%)

The artifact is always LF + exactly two spaces (`"\n  "`), a soft-wrap from the original
PDF/HTML source. 350 occurrences file-wide, **188 of 648 rows (29.01%)** affected in at least one
text field.

```
df_idx 0   S.No 1   Hospital Name = 'Andaman & Nicobar Islands Institute of Medical\n  Sciences'
df_idx 478 S.No 479 Hospital Name = 'Sri Ramachandra Medical College & Research\n  Institute'
df_idx 138 S.No 139 Hospital Name = 'World College of Medical Sciences & Research,\n  Jhajjar'
```

Per-column incidence: `Given Address` 188, `Standardized Address` 78, `Hospital Name` **73**,
`City` 7. `State`, `Country`, `Type`, `Source Sheet Name`, `address_py` are unaffected (0).

**Impact:** 73 facilities will fail every exact-match, hash and blocking key against every other
dataset until this is normalized. This is the single defect that most directly damages entity
resolution.

**Fix (verified lossless):**
```python
value = re.sub(r"\s+", " ", value).strip()
```
Verified safe: there are **0** runs of 2+ spaces in the file not immediately preceded by a newline
— the doubled space never occurs independently, so a blanket collapse cannot merge separate tokens.
There are also **0** cells containing NBSP, zero-width space or tab, so `\s+` is sufficient.
Effect: distinct `Hospital Name` 527 → 526.

---

## S1-3 · `State` misspelled on 81 rows (12.5%)

```
'Utttar Pradesh'  -> 'Uttar Pradesh'   67 rows   (three t's)   e.g. df_idx 549, S.No 550
'Chattisgarh'     -> 'Chhattisgarh'    14 rows                 e.g. df_idx 65,  S.No 66
```

Full distinct list is 33 values (see `profile.json.coded_vocabularies.State`). Also inconsistent
ampersand usage: `Jammu & Kashmir`, `Andaman & Nicobar Islands` use `&` while
`Dadra and Nagar Haveli` spells it out.

**Impact:** any join or group-by on state name silently drops or mis-buckets 1 in 8 records. Uttar
Pradesh is the largest state in the file, so the damage concentrates on the largest bucket.

**Fix:** map to LGD-canonical state names before use. No LGD codes exist in the file; the mapping
must be built from the 33-value list.

---

## S1-4 · `address_py` describes a different establishment in 37.2% of rows

`address_py` is reverse-geocoded from `Latitude`/`Longitude` by a prior Python step. It is the only
column with street detail and it is not reliably about the facility.

- **241 / 648 (37.2%)** share **zero** 4-or-more-character tokens with `Hospital Name`.
- **117** values contain `"Blood Bank"`.
- **4 pairs** of distinct facilities carry byte-identical `address_py`.

```
df_idx 1   S.No 2   'ACSR Government Medical College'
           address_py = 'Raja Rajeshwari Temple, GNT Rd, 524004, GNT Rd, Nellore, Andhra Pradesh, India'
df_idx 400 S.No 401 'Dr. S. S. Tantia Medical College Hospital & Research Centre'
           address_py = 'Jan Sewa Kendra Hospital, 335001, Sri Ganganagar, Rajasthan, India'
df_idx 518 S.No 519 'Malla Reddy Institute of Medical Sciences,'   lat 17.54654
df_idx 519 S.No 520 'Mallareddy Medical College for Womens'        lat 17.54497
           both address_py = "Malla Reddy Institute of Medical Sciences & Hospital's Blood Bank, 500055, Telangana, India"
df_idx 569 S.No 570 'Government Medical College' (Firozabad)
           address_py = 'Uttar Pradesh, India'          <- 20 chars, state-level only
df_idx 418 S.No 419 'RUHS College of Medical Sciences'
           address_py = 'park 4, India'                 <- 13 chars, useless
```

**Impact:** if mapped to `address_raw` and fed to an address-similarity matcher, ~37% of rows would
match on the wrong establishment's address.

**Fix:** map to a distinct canonical field (`address_reverse_geocoded`, proposed in
`field_map.yaml`) with `confidence: low` and a `geo_derived` provenance flag. Never use as a
matching key. Do not use as the facility's `street`/`locality` without a token-overlap guard.

---

## S1-5 · 114 rows (17.59%) have a non-discriminating facility name

After whitespace normalization and casefolding, `Hospital Name` has 526 distinct values over 648
rows. The collisions are not data-entry errors — they are genuinely different institutions that
share a generic government name:

| Normalized name | Rows |
|---|---:|
| `government medical college` | 82 |
| `all india institute of medical sciences` | 16 |
| `gmers medical college` | 6 |
| `autonomous state medical college society` | 4 |
| `jawaharlal nehru medical college` | 4 |
| `rajiv gandhi institute of medical sciences` | 3 |
| `employees state insurance corporation medical college` | 3 |
| (11 more names at 2 rows each) | 22 |

```
df_idx 10  S.No 11 'Government Medical College' Ananthapuram, Andhra Pradesh (14.67249, 77.59825)
df_idx 47  S.No 48 'Government Medical College' Bettiah,      Bihar          (26.79568, 84.49970)
df_idx 64  S.No 65 'Government Medical College' Chandigarh,   Chandigarh     (30.71084, 76.83747)
```
82 rows named `Government Medical College` collapse to 82-way clusters if blocked on name alone.
Even `(name, state)` still collides: 82 rows are duplicated on that pair (7 in Madhya Pradesh,
5 in Jammu & Kashmir, 4 each in Gujarat and Kerala).

**Impact:** false-positive entity merges, both within this dataset and against every other one.
Note that within-dataset these are **not** duplicates — `(name, geo@2dp)` yields **0** duplicates.

**Fix:** never block on name alone. Use `(rounded lat/lon) × (fuzzy name)`. Emit a
`name_is_generic` boolean so the resolver can downweight name similarity for these rows.

---

## S2-1 · 7 rows sit on 3 shared coordinate pairs (centroid fallback)

Geo is otherwise perfect — 648/648 numeric, all inside the India bbox, 0 null, 0 zero, 0 out-of-bbox,
0 swapped, 644 distinct pairs. But:

```
(11.12712, 78.65689) x3 :  S.No 482 'St. Peters Medical College Hospital and Research Instt.'
                           S.No 483 'Swamy Vivekanandha Medical College Hospital and Research Instt.'
                           S.No 497 'Bhaarat Medical College & Hospital'
                           -- all three listed City='Chennai'; this coordinate is the published
                              geographic centroid of Tamil Nadu, ~250 km from Chennai.
(13.08268, 80.27072) x2 :  S.No 479 'Sri Ramachandra Medical College & Research Institute'
                           S.No 496 'Sri Venkateswaraa Medical College Hospital and Research Institute'
                           -- Chennai city centroid.
(12.98323, 77.60422) x2 :  S.No 177 and S.No 234 -- Bangalore. These two are very likely the SAME
                           institution under an old and a new name ('Shri Atal Bihari Vajpayee
                           Medical College & Research Centre, Bangalore (formerly known as Bowring
                           & Lady Curzon...' vs '...& Research Institute'). Identical coords AND
                           identical address_py. See questions.md.
```

Additionally, 8 rows carry only 3 decimal places of latitude (~110 m precision) vs 573 rows at 5 and
24 at 6 — e.g. `df_idx 319, S.No 320 'Government Medical College' Nagpur (21.126, 79.097)`.

**Impact:** ~1% of rows have geo that points at a region, not a building. Geo-only matching within
100 m will mis-merge them.

**Fix:** flag rows whose coordinate is shared with another row as `geo_accuracy = 'centroid_suspect'`
and require a name-similarity confirmation for those rows. Do not drop them — the state/city is
still correct.

---

## S2-2 · `No. of beds in attached Hospital` — 2 unparseable values, 27.8% missing

```
df_idx 82  S.No 83  'Dr. Baba Saheb Ambedkar Medical College, Rohini' -> '500 + 50 (floating)'
df_idx 357 S.No 358 'Shija Academy of Health Sciences'                -> 'Na'
```
468/648 populated (72.22%); 466 parse as integers. Range 0–5702, median 750, p95 2036.

**Fix:** `to_int(errors='coerce')`; parse `'500 + 50 (floating)'` to `550` or `500` by policy (record
the choice), map `'Na'` to NULL. No thousands separators exist, so no separator stripping is needed.

---

## S2-3 · Missing values encoded as `0`

```
Admission Intake == 0 : 5 rows
  df_idx 61  S.No 62  'Radha Devi Jageshwari Memorial Medical College and Hospital'  Bihar/Private
  df_idx 210 S.No 211 'Sambharam Institute of Medical Sciences & Research'     Karnataka/Trust
  df_idx 291 S.No 292 'ACPM Medical College'                                   Maharashtra/Trust
  df_idx 531 S.No 532 'TRR Institute of Medical Sciences'                      Telangana/Private
  df_idx 587 S.No 588 'Major S D Singh Medical College and Hospital, Fathehgarh' UP/Trust

bed_count == 0 : 2 rows
  df_idx 385 S.No 386 'All India Institute of Medical Sciences' (Punjab) -- intake 100, beds 0
  df_idx 587 S.No 588 'Major S D Singh Medical College and Hospital'     -- intake 0,   beds 0
```
A medical college with a zero MBBS intake is not a real state; an AIIMS with 0 beds is not either.
2 rows have `beds < intake`.

**Fix:** coerce `0 -> NULL` on both `Admission Intake` and `bed_count`. Never let a 0 propagate into
an average.

---

## S2-4 · `City` column contaminated on ~14 rows

`City` is free-text and in several rows holds something that is not a city.

**(a) City = the facility name (6 rows)**
```
df_idx 227 S.No 228  City = 'G. R. Medical College Hospital and Research Centre'      (Karnataka)
df_idx 372 S.No 373  City = 'Hospital'                                                (Odisha)
df_idx 400 S.No 401  City = 'Dr. S. S. Tantia Medical College Hospital &\n  Research Centre'
df_idx 428 S.No 429  City = 'Arunai Medical College and Hospital'                     (Tamil Nadu)
df_idx 592 S.No 593  City = 'Noida International Institute of Medical Sciences'        (UP)
df_idx 248 S.No 249  City = 'Kannur (Prev.\n  Known as Academy of Medical Sciences)'   (Kerala)
```

**(b) City = a state name that is not a city-state (8 rows)**
```
S.No 139 'Haryana' · S.No 239/240/259 'Kerala' · S.No 360 'Mizoram' ·
S.No 369 'Odisha' · S.No 410 'Rajasthan' · S.No 624 'West Bengal'
```
(The other 13 City==State rows are legitimate: Chandigarh, Delhi ×3, Puducherry ×9.)

**(c) Trailing punctuation (5 rows)**
```
S.No 246 'Malapuram Dist.' · S.No 261 'Idukki.' · S.No 552 'Etah,' · S.No 564 'Hapur,' · S.No 565 'Banda,'
```

**(d) 1 null:** `df_idx 373, S.No 374 'Government Medical College, Keonjhar,'` (Odisha, pincode
758001 present) — the city `Keonjhar` is recoverable from the name.

**Impact:** ~2.2% of a column already being used as a district proxy is unusable. Since these rows
also feed the derived `Given Address` and `Standardized Address`, the corruption propagates.

**Fix:** strip trailing `,` and `.`; null out values that appear verbatim in `Hospital Name`; for
state-name cities, null and recover from `address_py` or the name. Flag, do not silently guess.

---

## S2-5 · `Postcode` — 1 malformed, 2 missing

```
df_idx 91  S.No 92  'Ahmedabad Municipal Coporation Medical Education Trust Medical College'
           Postcode = '380 006'   (embedded space; Postcode_py identical)
df_idx 418 S.No 419 'RUHS College of Medical Sciences' (Jaipur)      Postcode = NULL
df_idx 422 S.No 423 'Government Medical College' (Chittorgarh)       Postcode = NULL
```
645/646 populated values are clean 6-digit. No leading-zero pincodes exist, so the string↔int
round-trip is safe here — but keep as string anyway.

The two nulls leak into the derived `Standardized Address` as a dangling separator:
`'RUHS College of Medical Sciences, Jaipur, Rajasthan, India, .'`

**Fix:** `value.replace(" ", "")` then validate `^\d{6}$`.

---

## S2-6 · `Postcode_py` is a byte-identical duplicate of `Postcode`

648/648 rows match exactly, including both NULLs and the malformed `'380 006'`. It adds nothing and
is not even a cleaned version. **Fix:** drop.

---

## S2-7 · `Given Address` and `Standardized Address` are derived, not evidence

- `Standardized Address`: **648/648 (100%)** reconstruct exactly as
  `"<Hospital Name>, <City>, <State>, India, <Postcode>."` — verified in code.
- `Given Address`: 509/648 are exactly `"<Hospital Name>, <City> <State>"`; 631/648 contain City;
  648/648 end with State; only **27 rows** contain any token not already in name+city+state.
  Contains **0** pincodes.

```
df_idx 1 S.No 2  GA = 'ACSR Government Medical College Nellore Andhra Pradesh'
                 SA = 'ACSR Government Medical College, Nellore, Andhra Pradesh, India, 524004.'
```

**Impact:** feeding either into a TF-IDF / embedding matcher double- and triple-counts the facility
name, inflating similarity for any two rows that share generic name tokens ("Government", "Medical",
"College") — which is exactly the 17.59% generic-name population from S1-5.

**Fix:** drop `Given Address`. Keep `Standardized Address` as `address_display` only, never as
matching evidence.

---

## S2-8 · 3 columns are 100% empty and 1 is misspelled

```
Accrediation  -- 0 non-null across all 999 records (header misspelled; should be 'Accreditation')
Domains       -- 0 non-null across all 999 records
Contact       -- 0 non-null across all 999 records
```
All three are named after things we genuinely want (`accreditation`, `phone`). Their presence-as-
headers with zero content is a trap: a schema-driven mapper would map them and produce three
all-null canonical fields.

**Fix:** drop all three. Do **not** create the canonical fields from them.

---

## S2-9 · Names are truncated or abbreviated on ~68 rows

```
Truncated mid-word (8 rows):
  df_idx 170 S.No 171 'Al-Ameen Medical Colleg'
  df_idx 448 S.No 449 'Government Medical Colleg'
  df_idx 477 S.No 478 'Sri Muthukumaran Medical Colleg'
  df_idx 485 S.No 486 'Thanjavur Medical Colleg'
  df_idx 486 S.No 487 'Theni Government Medical Colleg'
  df_idx 489 S.No 490 'Tirunelveli Medical Colleg'
  df_idx 307 S.No 308 'Dr. Vasantrao Pawar Med. Col. Hosp. & Research Centr'
  df_idx 262 S.No 263 'Sree Narayana Instt. of Medical Sciences,\n  Chalakk'   (Chalakudy)
Trailing comma  : 47 rows, e.g. df_idx 191 S.No 192 'Kanachur Institute of Medical Sciences,'
Abbreviations   : 27 rows using 'Instt.', 'Med. Col.', 'Govt.', 'Hosp.'
```
The truncated lengths are 23, 24, 25, 26, 31, 31, 52, 90 — **not** a fixed-width cutoff, so this is
source-side sloppiness, not a column-width truncation we can reverse.

**Fix:** strip trailing `,` and `.`; expand a small abbreviation dictionary
(`Instt.`→`Institute`, `Med. Col.`→`Medical College`, `Govt.`→`Government`, `Hosp.`→`Hospital`)
during name canonicalization; accept fuzzy matching for the 8 mid-word truncations.

---

## S3-1 · Header cell contains a literal newline; file has a BOM

```
byte 0..2  : EF BB BF                       (UTF-8 BOM)
column 0   : 'S.\n  No.'                    (LF + two spaces inside the header cell)
```
Without `encoding='utf-8-sig'` the first column name becomes `'﻿S.\n  No.'`.

**Fix:** `encoding='utf-8-sig'` + `rename(columns={"S.\n  No.": "S. No."})`.

---

## S3-2 · 10 all-empty `Unnamed` columns

`Unnamed: 19` … `Unnamed: 28` — verified **0 non-null across all 999 records**. The header row ends
in 10 bare commas. Pure Excel export padding.

**Fix:** `df.drop(columns=[c for c in df.columns if c.startswith("Unnamed:")])`.

---

## S3-3 · Cosmetic value formatting

- `Type`: only `Govt.` carries a trailing period; `Trust`/`Private`/`Society`/`Govt-Society` do not.
  Strip it before enum mapping.
- `Standardized Address`: all 648 end with a `.`; 1 has a space before a comma.
- `Given Address`: 4 values have a space before a comma.
- `Country`: constant `'India'` — safe to drop and re-inject.
- `S. No.`: contiguous 1..648, complete and unique, but positional. Usable as a within-snapshot
  surrogate key only; it will not survive a re-export.

---

## Non-issues (checked and clean)

| Check | Result |
|---|---|
| Exact duplicate rows | **0** (also 0 excluding the row number) |
| Near-dupes on (normalized name, lat/lon @2dp) | **0** (also 0 at 4dp) |
| Lat/lon nulls / zeros / out-of-bbox / swapped | **0 / 0 / 0 / 0** — all 648 inside lon 68–98, lat 6–38 |
| `Admission Intake` numeric parse failures | **0 / 648** |
| Thousands separators in any numeric column | **0** |
| Leading-zero pincodes | **0** |
| NBSP / zero-width space / tab in any cell | **0** |
| PII (email / 10-digit phone / URL) | **0 / 0 / 0** |
| Opaque coded vocabularies needing an external codebook | **none** — `Type` is plain language |
| CSV quoting well-formed (embedded newlines parse correctly) | **yes** — no `engine='python'` needed |
