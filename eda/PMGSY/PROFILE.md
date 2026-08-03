# PMGSY — `21_JULY_23_SRK_PMGSY_validated_homogenized.csv`

**13,700 rows × 24 columns.** All numbers below come from `scripts/01_load.py` … `scripts/08_make_profile.py`.

## Loading it

```python
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str,
                 keep_default_na=False, na_values=[""])
df = df.dropna(how="all").reset_index(drop=True)   # -> (13700, 24)
```

`wc -l` says **14,900**. That is not the row count. The file has a UTF-8 BOM, and **322 rows contain a
literal newline inside a quoted field** (`ADDRESS`, and therefore its two copies `Street/Locality` and
`Formatted Address`) — 1,197 embedded `\n` characters in total. Plus two trailing all-comma records at
the end of the file. `13,703 logical records = 1 header + 13,700 data + 2 empty`, and
`13,703 + 1,197 = 14,900`. Reconciled exactly.

The first column name is **`'Sr. No. '` with a trailing space**. `utf-8-sig` removes the BOM; nothing
removes the trailing space, so do not `str.strip()` the header or every downstream reference breaks.
Everything must be read as `str` — `HAB_CODE`, `Pincode` and the 8-decimal coordinates all lose
information as floats/ints.

## What this dataset is

Pradhan Mantri Gram Sadak Yojana is the rural **road** programme. To justify and prioritise a road,
PMGSY surveyors record the "socio-economic facilities" a habitation connects to. This file is the
**Medical** slice of that facility master: someone went to a village, found the health facility,
GPS'd it, and typed its name. `MASTER_FACILITY_CATEGORY_NAME` is constant `'Medical'` on all 13,700
rows, so the extract has already been filtered — **there are no schools or roads as a category**. (Seven
rows do slip through with a clearly non-health free-text name; see `issues.md`.)

`FILE_UPLOAD_DATE` shows it is a **2019 field-collection campaign**: 9,978 rows (72.83%) are Aug–Dec
2019, 3,126 in 2020, 504 in 2021, 1 in 2022. Full range 2019-01-09 → 2022-11-26, with 63 nulls (all
Tamil Nadu). Coverage is 29 states/UTs; Uttar Pradesh alone is 2,718 rows (19.8%). **Goa, Nagaland,
Delhi, Chandigarh, Andaman, Dadra & Nagar Haveli, Daman & Diu and Lakshadweep are entirely absent**,
which is consistent with PMGSY's rural-road mandate but means this is not a national census.

## Grain: one row = one facility (not a habitation-facility link)

This was the key question. **One row is one health facility located in one PMGSY habitation.** Evidence:

- `HAB_CODE` is **not unique** — 12,092 distinct codes over 13,700 rows, 1,016 codes carrying 2–48 rows.
  The natural worry is a link table. It isn't.
- Inside a repeated code, the facility names and coordinates are all **different**. `HAB_CODE 440318`
  (Jagatpur, Bareilly, UP) has 48 rows: `chanderlok hospital`, `medinova hospital`, `khushlok hospital`,
  `sunnayan eye hospital`, … each with its own lat/lon. That is many facilities in one habitation.
- A link table would repeat the *same* facility under *different* habitations. It does not: only **1**
  (normalised-name, lat, lon) triple appears under more than one `HAB_CODE`, and only **7** exact
  (lat, lon) pairs do.
- `HAB_CODE` never spans more than one state (0 codes), district (0) or habitation name (0) — it is 1:1
  with the habitation.
- `(HAB_CODE, MASTER_FACILITY_DESC, LATITUDE, LONGITUDE)` is unique across all 13,700 rows.

So `HAB_CODE` is a **habitation identifier and cannot be the source primary key**. The only unique
column is `'Sr. No. '` (1..13,700, no gaps), which is a spreadsheet ordinal that will not survive a
re-extract. Use `'PMGSY:' || HAB_CODE || ':' || Sr. No.` as the surrogate.

## The two address representations

The task brief suspected the parsed set (`Hospital Name` … `Formatted Address`) was geocoder output.
**It is not.** Seven of the nine "parsed" columns are byte-identical copies of source columns:

| parsed column | source column | identical rows |
|---|---|---|
| `Hospital Name` | `MASTER_FACILITY_DESC` | 13,699 / 13,700 |
| `Street/Locality` | `ADDRESS` | 13,700 / 13,700 |
| `Habitation` | `HABITATION_NAME` | 13,700 / 13,700 |
| `Block` | `BLOCK_NAME` | 13,700 / 13,700 |
| `City/District` | `DISTRICT_NAME` | 13,700 / 13,700 |
| `State` | `STATE_NAME` | 13,700 / 13,700 |
| `Pincode` | `Postcode_py` | 13,700 / 13,700 |

(The single `Hospital Name` exception is Sr. No. 8: `'phcbededhospital'` vs `'phc beded hospital'`.)
`Country` is constant `'India'`. And `Formatted Address` is a pure concatenation — reproduced
**byte-exactly on 13,700/13,700 rows** by
`join(", ", [Hospital Name, Street/Locality, Habitation, Block (omitted when lower(Block)==lower(Habitation)), City/District, State, Country, Pincode])`.

So the **whole parsed block carries zero new information and should be dropped**. `ADDRESS` is the
authoritative human-entered address; there is no competing representation.

The genuine geocoder output is the pair `address_py` + `Postcode_py`/`Pincode` — a **reverse geocode of
`(LATITUDE, LONGITUDE)`**, not a forward geocode of `ADDRESS`. 13,699 of 13,700 `address_py` values end
in `"India"`; 333 contain Devanagari, Chinese or Urdu script from OSM local-name tags. This is the only
*independent* locational evidence in the file, and it is what makes the pincode auditable.

## Type vocabulary

`MASTER_FACILITY_CATEGORY_NAME`: `{Medical: 13700}` — constant.
`SUB_CATEGORY`: `{Bedded Hospital: 7307, Community Health Centre: 6393}` — two values, and that is the
entire classification available. It is a **weak** label: 2,546 of the 6,393 `Community Health Centre`
rows contain no CHC/community-health token in their name, and 89 of them are literally named
`hospital`; `Shri ram murti ismarak institute of medical sciences` (Sr. No. 11453) is labelled
Community Health Centre while `mental hospital` (Sr. No. 11426) is labelled Bedded Hospital. Treat
`SUB_CATEGORY` as a prior, never as ground truth, and prefer parsing the name.

## What it's good for

**Geography.** This is the cleanest coordinate set you are likely to see in this project:
13,700/13,700 (**100%**) lat/lon are non-null, non-zero, inside India's bbox (lat 8.119–34.665, lon
68.712–96.800), with **0** out-of-bbox and **0** swapped. 81.3% carry 8 decimal places, and the
precision is genuinely facility-level (48 distinct points inside habitation `440318`, median pairwise
separation 1,717 m, minimum 4 m, spread over a ~5.8 km bbox — these are individual buildings, not a
habitation centroid repeated). Also
**0 exact duplicate rows** — even ignoring `Sr. No. `.

It is also good for **rural reach**: this is habitation-level, so it contains small private nursing
homes and rural dispensaries that a scheme-empanelment registry (PMJAY/CGHS) would never list.

## What it's bad for

**Names.** 4,046 rows (**29.53%**) have a `MASTER_FACILITY_DESC` that is *nothing but a facility-type
word* — `CHC` (528), `community health center` (322), `Bedded Hospital` (291), `hospital` (244),
`Dispensary` (201). 41.77% of names are ≤2 tokens. There is no `facility_ownership`, no `bed_count`, no
`phone`, no `email`, no specialty, no scheme membership, no ABDM id. It has identity + geography and
nothing else.

## Three things that would bite you if you joined this naively

1. **You would think `HAB_CODE` is the facility key and lose 1,608 facilities.** It is not unique
   (12,092 / 13,700). Deduplicating on it silently collapses 48 distinct Bareilly hospitals into one.
2. **You would double-count every column.** Seven of the 24 columns are exact copies of another seven,
   and `Formatted Address` is a concatenation of eight of them. A naive "concatenate all text fields for
   embedding" step produces every fact 2–3× and skews any TF-IDF/embedding similarity toward
   whichever facts happen to be duplicated.
3. **You would block on name and match 30% of rows to the wrong facility — or nothing.** `CHC` in
   Rajasthan matches `CHC` in Bihar perfectly. Two rows named `Dispensary` 87 m apart in Kashipura,
   Jaipur (Sr. No. 8988 and 8989, `HAB_CODE 520090`) are indistinguishable by name. Block on
   **district + coordinate**, and use the name only as a scorer.

## Entity-resolution verdict

| signal | coverage | trust |
|---|---|---|
| latitude/longitude | 100.00% | **high** — facility-precision, fully validated |
| state_raw | 100.00% | high after LGD normalisation (`Tamilnadu`, `Pondicherry`) |
| district_raw | 100.00% | medium — 663 values with pre-rename drift, needs LGD alias table |
| facility_name_raw | 100.00% populated / **70.47% informative** | medium |
| pincode | 100.00% populated / **82.51% corroborated** | medium |
| block_raw, village_raw | 100.00% | medium — free-text, no codes |
| address_raw | 100.00% populated | **low** — 60.9% are ≤12 chars |

**Blocking key `name + geo + district` is viable, but only because of geo.** Recommended:
`state + district (LGD-normalised) + lat/lon rounded to 3 dp`, with name similarity as the scorer.
**29.53% of rows (4,046) are unmatchable by name alone** and depend entirely on the coordinate.
0% are unmatchable by geo.

Within-dataset near-duplicates are low but non-zero: **131 row pairs** lie within 150 m of each other
*and* have ≥0.85 name similarity (285 pairs at ≥0.70; 1,005 pairs within 150 m in total). Examples:
Sr. No. 466/470 both `First Referral Unit Ruksin`, Sr. No. 12373/12374 `SABA HOSPITAL`/`saba hospital`,
Sr. No. 327/328 both `Byrraju Foundation Hospital`.
