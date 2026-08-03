# CDAC_BB_A vs CDAC_BB_B — reconciliation

| | CDAC_BB_A | CDAC_BB_B |
|---|---|---|
| file | `16_MAY_AR_CDAC_BB_DATASET.csv` | `CDAC_BB_DATASET - Sheet1.csv` |
| shape | 5,679 × 12 | 5,889 × 10 |
| mtime | 2025-06-20 | 2025-11-23 |
| extra columns | `District`, `dist_name` | — |

Every number below is printed by
`.venv/bin/python eda/CDAC_BB_A/scripts/reconcile_a_b.py` (read-only; no source CSV is modified).

---

## Executive answer

**Neither file is a superset of the other in the sense that matters, because neither contains a
single facility the other lacks.** They are two divergent edits of one common ancestor.

- `_B` has 210 more **rows** but **0 more facilities**: rows 5679–5888 are a verbatim re-append of
  `_B`'s own rows 5469–5678.
- `_A` rows 0–5678 and `_B` rows 0–5678 are **the same records in the same order**, one-to-one by
  position. This is not a fuzzy match — it is exact positional identity, verified field by field.
- Each file then damaged a different set of fields. `_A` has better geo, states and districts;
  `_B` has better `Name` / `Address` / `Email` casing.

**Recommendation: use `_A`, patched with `_B`'s text fields.** Numbers in §10.

---

## 1. The prior recon's 5,467 / 5,539 name overlap — explained

Reproduced exactly:

```
raw Name distinct        : A=5539  B=5539  intersect=5467  A-only=72  B-only=72
case/punct-normalised    : A=5502  B=5502  intersect=5501  A-only=1   B-only=1
```

The 72-name gap is **not** 72 different facilities. It is 72 rows where `_A` uppercased a state
name that happens to sit inside the facility name:

| `_A` | `_B` |
|---|---|
| `Lower ASSAM Hospital Blood Centre` | `Lower Assam Hospital Blood Centre` |
| `Blood Centre Sadar Hospital, BIHARsharif` | `Blood Centre Sadar Hospital, Biharsharif` |
| `M/S Venkateshwar Hospital New DELHI, Dwarka Sector-18 A` | `M/S Venkateshwar Hospital New Delhi, …` |
| `ODISHA Blood Centre, S.D.H. Campus, Athamalik.` | `Odisha Blood Centre, S.D.H. Campus, Athamalik.` |

44 of the 73 differing `Name` rows are the `ODISHA Blood Centre …` run alone. After case-folding, **exactly one** name
differs in either direction: row 2952, `J N Hospital Blood Bank,Serchipp` (`_A`) vs
`J N Hospital Blood Bank,Serchhip` (`_B`). Serchhip is the correct Mizoram district — `_B` is right.

**So the name-level overlap is 5,501 of 5,502, not 5,467 of 5,539.**

---

## 2. Matching on name + address + geo

Normalising `Name` and `Address` (lowercase, non-alphanumerics → space) and keying on
`name || address`:

```
distinct keys            A=5676   B=5676   intersect=5669
A rows whose key is absent from B: 7
B rows whose key is absent from A: 7
```

The 7-vs-7 residual is again the same 7 facilities, and again the cause is a state name embedded
in a field — this time a *spelling* difference, not a casing one:

| `_A` Address | `_B` Address |
|---|---|
| `Blood Bank, District Hospital, Bijapur, CHHATTISGARH, Bijapur, Dist. Bijapur` | `… Chattisgarh, Bijapur, Dist. Bijapur` |
| `District Hospital Baikunthpur, Korea, CHHATTISGARH, Koriya, Dist. Koriya` | `… Chattisgarh, Koriya, Dist. Koriya` |
| `Mungeli, CHHATTISGARH, Mungeli, Dist. Mungeli` | `Mungeli, Chattisgarh, Mungeli, Dist. Mungeli` |
| `District Hospital Blood Bank, Sukma, CHHATTISGARH, Sukma, Dist. Sukma` | `… Chattisgarh, Sukma, Dist. Sukma` |
| `-, Dohad, Dist. Dohad` | `-, Dahod, Dist. Dahod` |
| `DEPARTMENT OF PATHOLOGY MMPJ HOSPITAL BHUJ KUTCH GUJARAT, Kachchh, Dist. Kachchh` | `… BHUJ KUTCH GUJRAT, Kachchh, Dist. Kachchh` |
| `Serchhip, MIZORAM, Serchhip, Dist. Serchhip` | `Serchhip, Mizoram, Serchhip, Dist. Serchhip` |

Re-keyed on `(normalised Name, district token parsed from Address)`, the residual drops to
**2 rows each way** — the `Serchipp`/`Serchhip` typo and the `Dohad`/`Dahod` district rename.

Geo confirms it: on the 7 pairs above the coordinates are identical to the last decimal.

---

## 3. The decisive test — positional identity

Comparing `A.iloc[i]` against `B.iloc[i]` for all 5,679 of `_A`'s rows:

| column | identical | differ | % | `_A` null | `_B` null |
|---|---:|---:|---:|---:|---:|
| `State` | 0 | 5,679 | 100.00% | 0 | 0 |
| `Name` | 5,606 | **73** | 1.29% | 0 | 0 |
| `Address` | 5,257 | **422** | 7.43% | 0 | 0 |
| `Latitude` | 5,439 | **240** | 4.23% | 0 | **25** |
| `Longitude` | 5,439 | **240** | 4.23% | 0 | **25** |
| `Phone` | 5,679 | 0 | 0.00% | 476 | 476 |
| `Email` | 5,657 | **22** | 0.39% | 1,698 | 1,698 |
| `Category` | 5,679 | 0 | 0.00% | 0 | 0 |
| `new_longitude` | 5,469 | **210** | 3.70% | 0 | 0 |
| `new_latitude` | 5,469 | **210** | 3.70% | 0 | 0 |

`Phone` and `Category` are **byte-identical on all 5,679 rows**. `State` differs on every row only
because `_A` is UPPERCASE and `_B` is Title Case. Both files have **the identical 476 nulls in
`Phone` and the identical 1,698 nulls in `Email`**, on the same rows.

That is not what two independent scrapes look like. `_A` and `_B` are the same table, in the same
row order, edited twice.

---

## 4. What `_B`'s 210 extra rows actually are

`_B` rows 5679–5888 vs `_B` rows 5469–5678, pairwise:

| field | identical |
|---|---|
| `Name`, `Address`, `State`, `Category`, `Email`, `new_longitude`, `new_latitude` | **210/210** |
| `Phone` | 209/210 (`Vision Blood Centre Bhopal`: `0.00E+00` vs `0` — the same value) |
| `Latitude`, `Longitude` | 0/210 textually, but **median 0.42 m apart, max 0.75 m** |

The coordinate "difference" is pure rounding — the head copy is 5 decimals, the tail copy is full
float:

```
row 5469  AKSHAYA BLOOD CENTRE, Kurnool   15.82497    / 78.04082
row 5679  AKSHAYA BLOOD CENTRE, Kurnool   15.82497498 / 78.04081521
```

All 210 tail keys already exist in rows 0–5678. **`_B` has 210 extra rows and 0 extra facilities.**

---

## 5. Rows in one and not the other — the pattern

There are none, at facility level. What *does* follow a pattern is the **damage**, and it is
state-shaped in both files.

**`_A`'s damage is confined to rows whose state name appears inside another field.** A global
uppercase-the-state find/replace was run across the whole row instead of just the `State` column:

- 73 `Name` values (72 of them differ from `_B` in **letter case only**)
- 422 `Address` values (416 case-only)
- 22 `Email` values (**22/22** case-only, e.g. `lowerASSAMhospital@yahoo.in`)

Concentrated by state: `Name` diffs — Odisha 44, Delhi 6, Bihar 5, Karnataka 3, Telangana 3.
`Address` diffs — Delhi 75, Rajasthan 53, Telangana 37, Uttar Pradesh 32, Kerala 25.

**`_B`'s damage is state-shaped too, and worse.** Positional `State` mapping `_A` → `_B` is
one-to-one for 36 of 37 states, with five spellings broken:

| `_A` | `_B` | rows |
|---|---|---:|
| `ANDHRA PRADESH` | `Andra Pradesh` | 326 |
| `GUJARAT` | `Gujrat` | 382 |
| `CHHATTISGARH` | `Chattisgarh` | 181 |
| `JAMMU & KASHMIR` | `Jammu and Kasmir` | 66 |
| `LAKSHADWEEP` | `Lakshwadeep` | 1 |
| **`SIKKIM`** | **`Rajasthan`** | **5** |

The last one is not a spelling error. `_B` rows **3716–3720** are Gangtok / Geyzing / Singtam /
Namchi blood centres whose addresses say "East Sikkim" and "west sikkim", and they carry
`State = Rajasthan`. Rows 3711–3715 are genuine Rajasthan rows and row 3721 starts Tamil Nadu, so
this is a fill-down that overran a sort boundary by five rows. **`_B` reports 36 states and zero
blood banks in Sikkim.**

---

## 6. Do shared rows have identical values? — per-column disagreement

Summarised from §3, with the cause of each disagreement:

| column | rows differing | cause | which file is right |
|---|---:|---|---|
| `Phone` | 0 | — | tie |
| `Category` | 0 | — | tie |
| `Email` | 22 | `_A`'s uppercase find/replace | **`_B`** (22/22 case-only) |
| `Name` | 73 | `_A`'s uppercase find/replace (72) + `Serchipp` typo (1) | **`_B`** (73/73) |
| `Address` | 422 | `_A`'s uppercase find/replace (416) + state-name spelling (6) | **`_B`** for casing; mixed for spelling (`_A`: `CHHATTISGARH`, `GUJARAT` correct; `_B`: `Dahod` correct) |
| `State` | 5,679 | case (all) + 5 misspellings + Sikkim mislabel | **`_A`** |
| `Latitude` / `Longitude` | 240 | 25 `_B`-null, 5 `_B`-out-of-bbox, 210 different geocode choice | **`_A`** (see §7) |
| `new_longitude` / `new_latitude` | 210 | mirror image of the `Latitude` disagreement | neither — drop both |

---

## 7. `new_latitude` / `new_longitude` vs `Latitude` / `Longitude`

India bbox = `lon 68–98`, `lat 6–38`.

| column pair | `_A` | `_B` |
|---|---|---|
| `Latitude`/`Longitude` in bbox | **5,679 / 5,679 = 100.00%** | 5,859 / 5,889 = 99.49% |
| … null | **0** | 25 |
| … outside bbox | **0** | 5 |
| … zero | 0 | 0 |
| … axis-swapped | 0 | 0 |
| `new_*` valid as labelled | 5,119 | 5,119 |
| `new_*` valid **only if axes swapped** | 216 | 426 |
| `new_*` invalid in **both** orientations | **344** | **344** |

### `new_latitude`/`new_longitude` are broken in two independent ways

**(a) The axes are transposed from row 5469 onward.** For rows 0–5468 the pair is
`(longitude, latitude)` as labelled; from row 5469 to the end of each file it holds
`(latitude, longitude)`. Zero rows are valid in both orientations, so the split is unambiguous:

```
row 0     G.B.Pant Hospital, Port Blair   new_longitude=92.73976    new_latitude=11.67572   correct
row 5469  AKSHAYA BLOOD CENTRE, Kurnool   new_longitude=15.82497498 new_latitude=78.04081521  swapped
```

**(b) 344 rows (6.1% of `_A`, 5.8% of `_B`) are not in India in either orientation.**

| row | Name | `new_longitude` | `new_latitude` | lands in |
|---|---|---|---|---|
| 3 | Aapadbandhu Blood Bank Vinukonda | `-83.7623` | `37.15627` | Kentucky |
| 9 | AIIMS Blood Centre Mangalagiri | `-157.862` | `21.30623` | **Honolulu** |
| 114 | BSC-RAJAMPET BSU | `-44.2575` | `-2.55289` | Brazil |
| 138 | Cpt blood centre | `116.448` | `39.93507` | Beijing |

One bad pair, `8.804821 / 61.24833` (Arabian Sea), repeats on **35** rows — a geocoder's
no-result fallback.

### Accuracy test: distance from each row to its own district's centroid

Reference centroids = the median `Latitude`/`Longitude` of each district, computed from `_A` rows
0–5468 (518 districts with ≥3 rows). District is parsed from the trailing `Dist. <X>` in `Address`.

| coordinate pair | median | p90 | >50 km | >150 km |
|---|---:|---:|---:|---:|
| `_A` `Latitude`/`Longitude` | **6.3 km** | **43.4 km** | **8.0%** | **0.9%** |
| `_B` `Latitude`/`Longitude` | 6.5 km | 45.7 km | 8.6% | 1.3% |
| `_A` `new_*` (as labelled) | 7.6 km | **1,549 km** | 18.1% | 11.9% |

**Verdict: `Latitude`/`Longitude` is trustworthy; `new_latitude`/`new_longitude` is not.**
Drop `new_*` in both files. Do not use it as a fallback for the 25 rows where `_B`'s `Latitude`
is null — `_A` has a real value for all 25.

### `_A`'s geo beats `_B`'s, head to head

Of the 240 rows where the two files disagree on `Latitude`:

- **30 rows: `_B` is unusable and `_A` is fine** (25 `_B`-nulls + 5 `_B` out-of-bbox).
- **0 rows: `_A` is unusable and `_B` is fine.**

The 5 out-of-bbox rows:

| row | Name | `_B` | lands in | `_A` |
|---|---|---|---|---|
| 482 | Rddjm Medical College, Muzaffarpur | `38.96375 / 35.24332` | Turkey | `26.03297613 / 85.33101487` |
| 523 | SDH Jaynagar, Madhubani (BSU) | `54.3972 / 18.2252` | Poland | `26.59694399 / 86.1370695` |
| 524 | SDH Jhanjharpur, Madhubani (BSU) | `54.3972 / 18.2252` | Poland | `26.25351924 / 86.27870045` |
| 534 | SDH Phulparas, Madhubani (BSU) | `54.3972 / 18.2252` | Poland | `26.31963821 / 86.47716978` |
| 4651 | District Hospital, Dhalai, Kulai | `1.662981 / 103.5999` | Singapore | `23.95019416 / 91.84096931` |

The remaining **210** disagreeing rows are the block at 5469–5678, where the two files simply
picked **opposite members of the same pair of candidate geocodes** — verified: for 210 of the 240
rows, `_A.Latitude ≈ _B.new_longitude` and `_A.Longitude ≈ _B.new_latitude` to within 1e-4.

On that disputed block (203 rows with a comparable district centroid):

| | median | p90 | >50 km | >150 km |
|---|---:|---:|---:|---:|
| `_A` | **10.5 km** | **48.2 km** | **17** | **5** |
| `_B` | 12.1 km | 72.6 km | 31 | 13 |

`_A` is closer to its own district's centroid on 113 rows, `_B` on 90. The tail is where it
matters — `_B`'s worst mislocations, with `_A` correct:

| Name | State | `_A` km | `_B` km | `_A` | `_B` |
|---|---|---:|---:|---|---|
| District Hospital Blood Centre, Chitradurga | Karnataka | 16 | **425** | `14.2250932 / 76.3980464` | `17.91801 / 77.51483` (Bidar — copied from the previous row) |
| BSU chc charama | Chhattisgarh | 49 | **416** | `20.4935109 / 81.3687151` | `22.84305 / 83.92842` |
| Chaitanya Blood Centre, Anantapur | Andhra Pradesh | **0.7** | **383** | `14.6740256 / 77.6009047` | `16.49896 / 80.65648` (Vijayawada) |
| Andhra Hospital Blood Bank, Vijayawada | Andhra Pradesh | 6.4 | **288** | `16.5400016 / 80.5827599` | `15.81884 / 78.03989` (Kurnool) |
| Kurinji Hospital Blood Centre | Tamil Nadu | **0.9** | **277** | `11.6770989 / 78.1353645` | `13.10323 / 80.23683` (Chennai) |

---

## 8. The extra columns `District` and `dist_name`

- **`District` is worth almost nothing as an exclusive.** Parsing the trailing `Dist. <X>` token
  out of `Address` reproduces it for **5,677 / 5,679** rows. `_B` can regenerate it for
  **5,888 / 5,889** of its rows. Losing it costs nothing.
- **`dist_name` is genuinely exclusive to `_A`.** It is the legacy / pre-reorganisation district
  name and matches the parsed address token for only **5,040 / 5,679** rows. It disagrees with
  `District` on **702 rows** — `Bapatla`↔`Guntur`, `Kakinada`↔`East Godavari`,
  `Gurgaon`↔`Gurugram`, `Mysore`↔`Mysuru`. That alias is what makes LGD-code joins work across
  both district vintages, and **it exists nowhere in `_B`.**
  (Caveat: 43 values are truncated at 24 chars with a `*` — `Sri Potti Sriramulu Nell*` — and a
  handful of rows name two genuinely *different* districts rather than two names for one. See
  `questions.md` Q-8.)

---

## 9. Duplicates within each file

| | `_A` | `_B` |
|---|---:|---:|
| exact duplicate rows (all columns) | **1** | **1** |
| duplicates on `(Name, Address)` | 3 | **213** |
| rows sharing a normalised `Name` | 177 | 387 |
| near-dupes on (normalised name, coord @ ~110 m) | **5** | **213** |

`_B`'s 213 are 210 from the re-appended block plus the same 3 `_A` has. The 3 shared ones:

- rows **872 / 873** `CHC, Kawant (BSU)` — identical in every column.
- rows **1977 / 1978** `Holy Cross Hospital`, Kollam — same address and coordinate, but
  `Category = Private / Phone = null` vs `Category = Charitable/Vol / Phone = 9.40E+09`.
  **Conflicting ownership; present in both files; needs a human** (`questions.md` Q-4).
- rows **3172 / 3173** `CHC-Gharyala BSU` — identical except `Phone` `"0.00E+00"` vs `"0"`.

---

## 10. RECOMMENDATION

### Use `CDAC_BB_A` as the base. Patch its three text columns from `CDAC_BB_B`. Load only the result.

**Do not union the row sets.** A union adds 0 facilities and 210 duplicates, and would
double-count all 5,676.

```python
A = pd.read_csv("16_MAY_AR_CDAC_BB_DATASET.csv",
                encoding="utf-8", dtype=str, keep_default_na=False, na_values=[""])
B = pd.read_csv("CDAC_BB_DATASET - Sheet1.csv",
                encoding="utf-8", dtype=str, keep_default_na=False, na_values=[""])

# 1. positional patch: A.iloc[i] and B.iloc[i] are the same record for all i < len(A)
for col in ("Name", "Address", "Email"):
    A[col] = B[col].iloc[:len(A)].values          # 517 field repairs across 476 rows

# 2. drop the failed geocoding pass
A = A.drop(columns=["new_longitude", "new_latitude"])

# 3. drop the one exact duplicate (rows 872/873)  -> 5,678 rows
A = A.drop_duplicates()

# 4. fix the two known State defects
A["State"] = A["State"].replace({"DADRA & NAGAR HAVE": "DADRA AND NAGAR HAVELI"})
# ('&' -> 'AND' for JAMMU & KASHMIR, DAMAN & DIU, ANDAMAN & NICOBAR as well)

# 5. synthesise the key that does not exist
A["source_facility_id"] = "CDAC_BB_A:" + A.index.astype(str)
```

Result: **5,678 rows × 11 columns**, one row per real facility.

### Why `_A` and not `_B`

| | `_A` | `_B` |
|---|---|---|
| valid-in-India coordinate | **5,679 / 5,679 = 100%** | 5,859 / 5,889 = 99.49% |
| rows with no coordinate | **0** | 25 |
| rows with a coordinate outside India | **0** | 5 |
| rows where the *other* file's coordinate is better | 0 | 30 |
| geo accuracy (median km to own district centroid) | **6.3** | 6.5 |
| geo accuracy on the disputed 210-row block (p90) | **48 km** | 73 km |
| state names correctly spelled | **37 / 37** | 31 / 36 (956 rows broken) |
| Sikkim present | **yes** | **no** (5 rows labelled Rajasthan) |
| district column | **2** (`District` + legacy `dist_name`) | 0 (`District` recoverable; `dist_name` is not) |
| duplicate rows | **1** | **211** |
| damaged `Name` / `Address` / `Email` | 73 / 422 / 22 | 0 / 6 / 0 |

`_A` wins on six criteria that cannot be repaired from `_B`, and loses on one that can be repaired
from `_B` in three lines. `_B`'s only unique asset is 517 correctly-cased strings across 476 rows;
step 1 above takes them.

### Why the positional patch is safe

It rests on §3: `_A.iloc[i]` and `_B.iloc[i]` are the same record for every `i` in `0…5678`,
demonstrated by `Phone` matching on **5,679/5,679** rows (including the same 476 nulls),
`Category` on **5,679/5,679**, and `Name` on 5,606/5,679 with all 73 exceptions being the same
string in different case. If you distrust position, key on
`(normalised Name, district token from Address)` — that leaves 2 unmatched rows each way, and both
are documented in §2.

### If someone insists on a union rule

Union on `(lower(Name-with-state-tokens-title-cased), district token from Address)`, take **all**
fields from `_A` except `Name` / `Address` / `Email` which come from `_B`, and discard the 210 rows
of `_B` with index ≥ 5679. This produces the identical 5,678-row table. The union is not worth the
machinery.

### Also, regardless of which file wins

1. Drop `new_latitude` / `new_longitude` (§7). They are wrong for 344 rows in any orientation and
   transposed for a further 216.
2. Treat `Phone` as ~84% missing, not ~8% (only 893 of 5,679 rows are dialable — see `issues.md`).
3. Extract the `BSU` token from `Name` before counting facilities — 1,443 rows (25.4%) are Blood
   Storage Units, not blood centres.
4. Resolve rows 1977/1978 (`Holy Cross Hospital`) by hand; both files carry the same conflict.
5. Re-export from the original Google Sheet if it still exists — the common ancestor of these two
   files would be better than either (see `eda/CDAC_BB_B/questions.md` Q-B1).
