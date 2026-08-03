# NHP — `8_JULY_23_SRK_NHP_validated_and_standardized.csv`

**Dataset key:** `NHP` · **True rows:** 648 · **Real columns:** 19 of 29 · **Physical lines:** 1,350

---

## What this dataset actually is

**This is a register of Indian medical colleges, not general hospitals.** That is the single most
important fact about the file and it is not obvious from the column named `Hospital Name`.

The evidence, all measured:

| Signal | Value |
|---|---|
| `Source Sheet Name` constant on every row | `NHP_Medical_Colleges` (648/648) |
| Names containing "medical college" | 441 / 648 (68.1%) |
| Names containing "college" (any) | 454 / 648 (70.1%) |
| Names containing "institut" | 170 / 648 (26.2%) |
| Names containing "academy" / "university" / "school of medicine" | 16 |
| Names matching *none* of college / institute / academy / university / school / AIIMS / ESIC | 28 |
| Rows carrying an `Admission Intake` (annual MBBS seat count) | 648 / 648 (100%) |
| `Admission Intake` values that are multiples of 50 | 555 / 648 |

The 28 names that match no institution keyword are abbreviations and truncations
(`GMC`, `Fathima Instt. of Medical Sciences`, `Dr. Vasantrao Pawar Med. Col. Hosp. & Research Centr`),
not a different class of facility — every one of them still carries an MBBS seat intake, which only a
teaching institution has. India had roughly 650–700 recognised medical colleges around 2022–23, so
648 rows is a plausible near-census.

**Consequence for harmonization:** `facility_type_raw` is not a column here. It must be *injected*
as the constant `MEDICAL_COLLEGE` for all 648 rows. No other dataset in this set should receive that
value by default. This is the only file whose facility type is uniform and distinct.

The producing program is the **National Health Portal** (nhp.gov.in), a MoHFW/NIHFW public
information portal that published directory listings. The `_py` suffixed columns (`Postcode_py`,
`address_py`) and the `validated_and_standardized` filename show it has already been through at
least one Python enrichment pass before reaching us.

---

## True shape, and why `wc -l` lies

`wc -l` says **1,350**. The real answer is **648 data rows**. The gap decomposes exactly:

```
  1,350 LF bytes  (what wc -l counts)
=     2 physical lines   header           (1 CSV record, split by the LF inside "S.\n  No.")
+   997 physical lines   648 data records (648 records + 349 LFs embedded in quoted fields)
+   351 physical lines   351 all-blank ",,,,..." records at the end of the file
```

Three separate defects stack here:

1. **CRLF records, bare-LF soft wraps.** The record separator is `\r\n` (1,000 pairs = 1 header +
   999 records). On top of that there are **350 bare `\n` characters inside quoted fields** — 1 in
   the header, 349 in data. The quoting is *well-formed*, so `pd.read_csv` handles this correctly
   with no special kwargs; only `wc -l` is fooled.
2. **351 trailing blank records.** Records 649–999 are entirely empty (`,,,,...` × 29), contiguous,
   at the end of the file — an Excel "export the whole used range" artifact. Naive profiling reports
   every column as ~64.86% filled. It isn't; it's 100% filled over 648 real rows. `dropna(how='all')`
   fixes it.
3. **UTF-8 BOM.** Byte 0 is `EF BB BF`. Without `encoding='utf-8-sig'` the first column becomes
   `'﻿S.\n  No.'`.

**Correct read:**
```python
df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = df.rename(columns={"S.\n  No.": "S. No."})
df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed:")])   # 10 empty cols
df = df.dropna(how="all").reset_index(drop=True)                            # 999 -> 648
```

`Unnamed: 19` through `Unnamed: 28` are **verified 0 non-null across all 999 records** — 10 junk
columns, drop them.

---

## The whitespace artifact — and the exact rule

Text cells contain a soft-wrap artifact from whatever copied this table out of a PDF/HTML source.
The pattern is **always the same**: a line feed followed by **exactly two spaces**, `"\n  "`.

```
"Andaman & Nicobar Islands Institute of Medical\n  Sciences"
"Sri Ramachandra Medical College & Research\n  Institute"
"World College of Medical Sciences & Research,\n  Jhajjar"
```

Measured incidence — **188 of 648 rows (29.01%)** have at least one affected field:

| Column | Rows affected | % of populated |
|---|---:|---:|
| `Given Address` | 188 | 29.01% |
| `Standardized Address` | 78 | 12.04% |
| `Hospital Name` | **73** | **11.27%** |
| `City` | 7 | 1.08% |
| `State`, `Country`, `Type`, `Source Sheet Name`, `address_py` | 0 | 0% |

**Proposed rule — apply to every text column before any matching, hashing or indexing:**

```python
value = re.sub(r"\s+", " ", value).strip()
```

**Why this exact rule is safe (verified, not assumed):** there are **zero** runs of 2-or-more spaces
anywhere in the file that are not immediately preceded by a newline. So a blanket
whitespace-collapse cannot merge two genuinely separate tokens — the doubled space *is* the artifact,
it never occurs on its own. There are also **0 cells containing NBSP, zero-width space or tab**, so
`\s+` is sufficient and no Unicode pre-pass is needed. Applying the rule takes distinct
`Hospital Name` values from **527 → 526** (one pair differed only by the artifact); casefolding
afterwards changes nothing further.

**This matters directly for entity matching.** 11.27% of facility names currently contain a raw
newline. Any exact-match, hash, or blocking key built on the un-normalized name will silently miss
those 73 rows against every other dataset.

---

## Columns unique to this dataset

| Column | Fill (of 648) | Parses cleanly? | Distribution |
|---|---:|---|---|
| `Admission Intake` | 648 (100%) | **Yes** — 648/648 integer, no separators | 0–250, median **150**. Top: 150 (259), 100 (146), 250 (77), 200 (60), 125 (35). 555/648 are multiples of 50. **5 rows are 0** (missing-as-zero). 21 distinct values. |
| `No. of beds in attached Hospital` | 468 (**72.22%**) | **Almost** — 466/468 integer; 2 free text | 0–5702, median **750**, p25 545, p75 1128, p95 2036. Bad values: `"500 + 50 (floating)"` (S.No 83), `"Na"` (S.No 358). 2 rows are 0. Median beds/intake = 5.0. |
| `Accrediation` *(sic)* | **0 (0.00%)** | n/a | Entirely empty across all 999 records. Header is misspelled. Drop. |
| `Domains` | **0 (0.00%)** | n/a | Entirely empty across all 999 records. Meaning undetermined — see `questions.md`. Drop. |
| `Contact` | **0 (0.00%)** | n/a | Entirely empty across all 999 records. Drop. **No PII exists anywhere in this file** (0 emails, 0 phone-shaped strings, 0 URLs). |

### `Type` — the ownership enum (full counts, n=648)

| Value | Count | % |
|---|---:|---:|
| `Govt.` | 337 | 52.0% |
| `Trust` | 204 | 31.5% |
| `Private` | 69 | 10.6% |
| `Society` | 29 | 4.5% |
| `Govt-Society` | 9 | 1.4% |

This is **ownership/sector, not facility type**. The Trust / Society / Private three-way split is
finer than most government datasets carry — confirm the target enum before flattening them all to
`PRIVATE`. `Govt-Society` reads as a PPP arrangement.

### `Source Sheet Name` — provenance

Exactly **one** distinct value: `NHP_Medical_Colleges`, on all 648 rows. This file was assembled from
a single source sheet, not a multi-sheet merge. Keep it — it is the evidence backing the injected
`facility_type_raw`.

---

## The three address columns — which one is authoritative?

**None of them is a real street address. Recommendation: keep `address_py` (low confidence) for
street/locality enrichment, keep `Standardized Address` as a display string only, and drop
`Given Address` entirely.**

| Column | Fill | Distinct | Median len | Has pincode | What it actually is |
|---|---:|---:|---:|---:|---|
| `Given Address` | 648 (100%) | 648 | 58 | **0** | **Derived.** 509/648 are *exactly* `"<Hospital Name>, <City> <State>"`. 631/648 contain City; 648/648 end with State; only **27 rows** contain any token not already in name+city+state. No street, no pincode. |
| `Standardized Address` | 648 (100%) | 648 | 76 | 645 | **Derived, 100%.** All 648 reconstruct byte-for-byte as `"<Hospital Name>, <City>, <State>, India, <Postcode>."` — verified in code. Zero new information. |
| `address_py` | 648 (100%) | 644 | 90 | 613 | **Reverse-geocoded from lat/lon** by a prior Python step. The only source of street detail — and untrustworthy. |

The `address_py` problem, measured: **241 of 648 (37.2%) share zero 4-or-more-character tokens with
the facility name.** 117 values mention `"Blood Bank"`. 249 mention `"Hospital"` — frequently a
different one. Four pairs of distinct facilities carry an *identical* `address_py`. Examples:

```
S.No 2   ACSR Government Medical College
         -> "Raja Rajeshwari Temple, GNT Rd, 524004, GNT Rd, Nellore, Andhra Pradesh, India"
S.No 401 Dr. S. S. Tantia Medical College Hospital & Research Centre
         -> "Jan Sewa Kendra Hospital, 335001, Sri Ganganagar, Rajasthan, India"
S.No 519 Malla Reddy Institute of Medical Sciences      \  identical address_py,
S.No 520 Mallareddy Medical College for Womens          /  different coordinates
S.No 570 Government Medical College (Firozabad)         -> "Uttar Pradesh, India"   (13 chars)
```

So: `address_py` is enrichment, never a matching key. `Given Address` and `Standardized Address` are
concatenations of columns we already have — feeding either into a TF-IDF or embedding matcher would
double- and triple-count the facility name.

---

## What it's good for

- **Geo is excellent.** 648/648 have latitude and longitude; **all 648 are inside the India bbox**;
  **zero** nulls, **zero** zeros, **zero** out-of-bbox, **zero** swapped. Range lat 8.174–34.136,
  lon 69.629–94.941. 573 rows carry 5 decimal places, 24 carry 6. This is the cleanest geo column
  you are likely to see in this collection.
- **Complete on every field that exists.** After dropping the blank rows, `Hospital Name`, `Latitude`,
  `Longitude`, `State`, `Country`, `Type`, `Admission Intake`, `Source Sheet Name` and all three
  address columns are 100% populated. `City` is 647/648, `Postcode` 646/648.
- **Zero duplicate rows.** 0 exact duplicates, 0 duplicates excluding the row number, 0 near-dupes on
  (normalized name, lat/lon @ 2dp).
- **Capacity data other datasets won't have.** `Admission Intake` (100%) and `bed_count` (72%) are a
  genuine, cleanly-typed contribution to the canonical table.
- **No PII whatsoever.** Nothing to redact.

## What it's bad for

- **No district.** There is no district column and no LGD code anywhere in the file. `City` is a
  town name (429 distinct, e.g. `Bangalore`, `Narketpally`, `Ambedkarnagar`). The expected
  `(name, geo, district)` blocking key **cannot be built from this file alone** — it needs an
  external city→district lookup, or must be replaced by `(name, geo)` / `(name, state, pincode)`.
- **Names are frequently generic.** 114 rows (17.59%) carry a non-discriminating name:
  `government medical college` × 82, `all india institute of medical sciences` × 16,
  `gmers medical college` × 6, `autonomous state medical college society` × 4, `esic` × 2,
  `medical college` × 2. Name-only matching against these produces 82-way false-positive clusters.
- **No clinical or programme data at all.** No specialties, no accreditation (column is empty), no
  scheme membership, no empanelment, no ABDM, no contact details, no ownership sub-codes.
- **No stable identifier.** `S. No.` is a positional 1..648 row number that will not survive a
  re-export of the source sheet.
- **Small.** 648 rows against datasets that will have tens of thousands.

## Fitness for entity resolution

| Field | Usable for matching? | Trust |
|---|---|---|
| `Latitude` / `Longitude` | **Yes — primary key signal** | **High.** 100% present and valid. Caveat: 7 rows sit on 3 shared coordinate pairs (centroid fallback). |
| `Hospital Name` (after `WS_NORM`) | Yes, but only in combination | **Medium.** 526/648 distinct; 17.59% generic; 68 truncated/abbreviated. |
| `State` (after spelling fix) | Yes, as a blocking dimension | **High** once `Utttar Pradesh` and `Chattisgarh` are corrected. |
| `Postcode` | Yes, as a blocking dimension | **High.** 645/648 clean 6-digit. |
| `City` | Coarse blocking only | **Medium.** Free-text town, not a district. |
| `address_py` | **No** | **Low.** 37% describe a different establishment. |
| `Given Address` / `Standardized Address` | **No** | Derived; would double-count the name. |
| `S. No.` | No (provenance only) | Positional. |

**Verdict:** `blocking_key_viable = true`, `unmatchable_row_pct = 0.0%`. Every row has a name, valid
geo, a state and a pincode, so nothing is structurally unmatchable. Use **(rounded lat/lon) × (fuzzy
normalized name)** as the blocking key and add `state` + `pincode` as a tiebreaker. Do **not** use
district (absent) and do **not** use name alone (17.59% generic).

---

## The three things that would bite you if you joined this naively

1. **You'd think it's hospitals, and you'd merge 648 medical colleges into the hospital table.**
   The column is called `Hospital Name`; the entities are teaching institutions. Many *do* have an
   attached hospital (median 750 beds) which often shares a name and a location with the college —
   so the same physical campus may legitimately exist in another dataset as a *hospital* record. That
   is a genuine 1:1 entity match, not a duplicate, but only if you know that going in. Inject
   `facility_type_raw = MEDICAL_COLLEGE` and decide the college↔attached-hospital policy explicitly.

2. **You'd report every column as 65% null and half-populate your canonical table.** The 351 trailing
   blank records make `df.notna().mean()` read `0.6486` on almost every column. If you compute fill
   rates, thresholds, or "drop columns below X% populated" without `dropna(how='all')` first, you
   will draw exactly the wrong conclusion about a file that is in fact ~100% complete. Worse: those
   351 blank rows will be loaded as 351 phantom facilities with a null name.

3. **Your name-based matcher would miss 73 facilities and false-positive on 82.** 11.27% of
   `Hospital Name` values contain a raw `\n  ` and will not exact-match anything until you run
   `re.sub(r"\s+"," ",s).strip()`. And at the other end, 82 rows are literally named
   `Government Medical College` — normalized name alone will cluster them into one entity. You need
   the whitespace fix *and* geo/pincode disambiguation; either one without the other gives a wrong
   answer in opposite directions.

*(Runner-up, worth knowing: `State` contains `Utttar Pradesh` with three t's on 67 rows — 10.3% of
the file. Any join on state name drops or mis-buckets one in ten records.)*
