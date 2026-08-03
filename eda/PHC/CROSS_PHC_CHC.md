# PHC ↔ CHC — cross-file analysis

`21_June_2024_AM_PHC.csv` (31,958 × 9) and `21_June_2024_AM_CHC.csv` (4,237 × 9).

Every number below comes from `scripts/deep_and_cross.py` (raw output reproducible by rerunning it)
and the side-car `cross_stats.json`.

**Headline: these are not two datasets. They are one dataset that was split in half by a keyword
rule, and the split leaks.**

---

## 1. Do they share an ID namespace, or collide? — **They share it. Cleanly. Union is safe.**

The schema is byte-identical: same 9 column names, same order, same CRLF encoding, same constant
`FAC_CATEGO`, same 29 states, same 3 truncated district strings. That alone suggests a common
parent, but it does not prove the IDs are compatible. Here is the empirical test.

### `BLOCK_ID` — shared namespace, proven

| | PHC | CHC | union |
|---|---|---|---|
| distinct values | 6,114 | 2,644 | 6,252 |
| range | [1, 8147] | [1, 8145] | [1, 8147] |
| blocks spanning >1 **state** | **0** | **0** | **0** |
| blocks spanning >1 **district** | **0** | **0** | **0** |

2,506 `BLOCK_ID`s (94.78% of CHC's distinct values) appear in both files. If the two files used
independent per-file numbering, those 2,506 shared codes would point at different districts roughly
at random. They do not: **0 of the 6,252 union blocks maps to more than one district.** That is a
conclusive result — under an independent-namespace hypothesis the probability of zero conflicts
across 2,506 shared codes is effectively nil.

### `HAB_ID` — shared namespace, proven

| | PHC | CHC | union |
|---|---|---|---|
| distinct values | 31,391 | 4,174 | 35,189 |
| range | [167, 1429223] | [349, 1428938] | [167, 1429223] |
| HAB_IDs spanning >1 district | — | — | **0** |
| HAB_IDs spanning >1 BLOCK_ID | — | — | **0** |

376 `HAB_ID`s (9.01% of CHC's) appear in both files. For **all 376**, the state, district *and*
`BLOCK_ID` agree between the two files. Median PHC↔CHC distance at those habitations: **60 m**.
217 of 376 are within 100 m; 312 within 1 km; only 11 are more than 10 km apart.

These are not collisions — they are **villages that have both a PHC and a CHC**, which is exactly
what you would expect. Example: `HAB_ID 1001812`, `Himachal Pradesh / Mandi / BLOCK_ID 5808` —
PHC row is `"Primary Health Centre Slapper"` at 76.85375/31.41646, CHC row is
`"Community Health Centre Slaper"` at 76.86314/31.41737. Same village, two facilities, ~940 m apart,
even the same typo'd place name.

### `FACILITY_ID` — shared namespace, and 21 rows are literally duplicated

| | PHC | CHC |
|---|---|---|
| distinct values | 31,958 (= n_rows, unique) | 4,237 (= n_rows, unique) |
| range | [43, 1059598] | [1389, 1058927] |
| intersection | **21** | |

For all 21 overlapping `FACILITY_ID`s: same state (21/21), same district (21/21), **identical
lon/lat (21/21, median distance 0.00 km)**. In fact all 9 columns are byte-identical. These are not
two facilities that happened to get the same id — they are the *same row written into both files*.

### Verdict

**PHC and CHC can be unioned. There is one namespace, not two.**

```
naive concat:                 31,958 + 4,237 = 36,195 rows
dedupe on all 9 columns:                       36,174 rows   (21 removed)
distinct FACILITY_ID in union:                 36,174        ← exactly matches
```

`FACILITY_ID` is a **valid primary key for the deduplicated union**. `BLOCK_ID` and `HAB_ID` are
valid shared hierarchy keys across the union.

**The one thing you must not do** is prefix IDs per-file (`PHC:888987` vs `CHC:888987`). That
manufactures 21 duplicate canonical entities. Load them as a single source with a `facility_tier`
column, or dedupe the union on the full row.

---

## 2. Is there row overlap? — **Yes: 21 rows exist verbatim in both files.**

| overlap key | count |
|---|---|
| all 9 columns identical | **21** |
| `FACILITY_ID` | 21 |
| exact `(Longitude, Latitude)` | 31 |
| `HAB_ID` | 376 |
| `HAB_ID` + exact coordinate | 23 |
| `(DISTRICT_NAME, normalised name)` | 12 |
| coordinate rounded to 3 dp (~110 m) | 181 cells |
| coordinate rounded to 2 dp (~1.1 km) | 332 cells (of 4,145 CHC cells) |

The 21 exact-duplicate rows:

| state | district | FACILITY_ID | FAC_DESC |
|---|---|---|---|
| Assam | Lakhimpur | 915114 | NAOBOICHA **COMMUNITY** AND BLOCK **PRIMARY** HEALTH CENTRE |
| Assam | Baksa | 900821 | Barama block **primary** health centre cum Barama **comunity** health centre |
| Assam | Nalbari | 888987 | Mukalmua FRU **CHC** **BPHC** |
| Assam | Baksa | 901130 | Jalah **CHC** and Block **PHC** |
| Assam | Darrang | 862360 | Sipajhar **Primary** and **Community** Health Centre |
| Punjab | Moga | 574880 | **primary** **community** health center |
| Rajasthan | Dhaulpur | 62397 | **CHC** **PHC** |
| Bihar | Bhagalpur | 850783 | `HC` |
| Gujarat | Morbi | 485239 | `c` |
| Jharkhand | Ramgarh | 938356 | `hpc` |
| Gujarat | Valsad | 471531 | `PHC Achchhari` |
| Jharkhand | Saraikela-kharsawan | ×10 | `HSC` (966266, 966195, 966332, 966157, 966025, 968257, 968258, 966447, 968319, 968219) |

Look at the pattern. Under strict word-boundary matching, **5 of the 21 names contain both a
PHC-token and a CHC-token, and 13 contain neither** (the remaining 3 are `Barama block primary…cum
…comunity`, `Mukalmua FRU CHC BPHC` and `PHC Achchhari` — the first two also reference both tiers
but via the misspelling `comunity` and the compound `BPHC`, so a substring match gives 8 both / 13
neither). And the converse holds exactly:

- Rows in *either* file whose name contains **both** tokens: **5**. Of those, **5 appear in both
  files.** (100%)
- Rows in *either* file named exactly `HSC`: **10**. Of those, **10 appear in both files.** (100%)

**This is proof of mechanism, not coincidence.** The two files were produced by running a keyword
rule over `FAC_DESC` against a single parent table: names matching "primary/PHC" → PHC file, names
matching "community/CHC" → CHC file, names matching **both or neither** → emitted to **both** files.

### What follows from that

1. **`facility_tier` is not ground truth.** The only thing making a row a "PHC" is which file it
   landed in, and that was decided by string-matching a field that is 62% boilerplate.
2. **The tier label is systematically wrong for some states.** 95 West Bengal rows named
   `"Block Primary Health Centre"` / `"BPHC"` are in the **PHC** file; zero are in the CHC file. A
   West Bengal BPHC is the block-level *referral* unit — functionally the CHC tier. The rule matched
   "primary" and misrouted all 95. Assam has 55 more. This is why West Bengal shows 840 PHCs but
   only **16** CHCs.
3. **Rows matching neither keyword may have been dropped entirely.** The 13 unclassifiable rows
   (`HC`, `c`, `hpc`, `HSC`×10) went to both files — but we cannot tell whether that was the rule's
   fallback or whether other unmatched rows were silently discarded. If the parent table's
   `FAC_CATEGO = 'Medical'` count exceeds 36,174, the difference is a missing set of health
   facilities. See `questions.md` Q5.

### Practical rule

Union the two files, dedupe on the full 9-tuple (36,195 → 36,174), set `facility_tier` from the
source filename, and set `source_split_confidence = 'ambiguous'` for the 21 duplicated rows, the
1,327 sub-centre-named rows and the 152 BPHC-named rows. Those sets overlap, so the distinct total
is **1,486 rows = 4.11% of the union**, whose tier should not be trusted.

---

## 3. Are `FAC_CATEGO` values disjoint? — **No. They are identical, constant, and worthless.**

```
PHC: {'Medical': 31958}     ← 100% of rows, 1 distinct value
CHC: {'Medical': 4237}      ← 100% of rows, 1 distinct value
disjoint: False             ← the intersection is the entire domain
```

`FAC_CATEGO` has exactly one value across both files combined. It carries **zero bits of
information** and — critically — **it does not distinguish PHC from CHC**. Anyone who assumes the
column named "facility category" encodes the facility category will get a single-valued column and
lose the tier distinction entirely.

The name plus the value strongly suggests this is an **amenity category** inherited from a larger
habitation-survey parent table, where the vocabulary presumably also includes Education, Transport,
Water and so on, and 'Medical' is the filter that produced these files. That is inference; we have
no codebook. See `questions.md` Q3.

**Disposition: drop the column.** Do not map it to `facility_category_raw`. Materialise
`facility_tier` from the filename instead, because that is where the information actually lives.

---

## 4. Can these be matched to a richer registry at all? — **Blunt assessment**

### What we have to match with

Nine columns. One is constant (dropped). Three are internal IDs that no external registry will
carry (`BLOCK_ID`, `HAB_ID`, `FACILITY_ID`). That leaves **name, state, district, lat, lon**.
No address. No pincode. No phone. No email. No ownership. No bed count. No specialty. No date.
This is about as thin as a facility record gets.

### Geo: excellent, and it is the only thing carrying the load

| | PHC | CHC |
|---|---|---|
| rows with a parseable coordinate | 31,958 / 31,958 = **100.00%** | 4,237 / 4,237 = **100.00%** |
| null / blank | 0 | 0 |
| zero (0,0) | 0 | 0 |
| outside India bbox (lon 68–98, lat 6–38) | **0** | **0** |
| plausibly lat/lon swapped | **0** | **0** |
| **usable geo** | **100.00%** | **100.00%** |
| ≥5 decimal places | 31,836 (99.62%) | 4,224 (99.69%) |
| >100 km from own district median | 192 (0.60%) | 30 (0.71%) |
| >600 km from own state median | 0 | 0 |
| alone in its ~1.1 km grid cell | 30,319 (**94.87%**) | 4,054 (**95.68%**) |

**100% of rows have usable geo.** That is not a rounding artefact — every single coordinate parses,
is non-zero, and falls inside India. Applying the strictest plausibility filter available without a
shapefile (>100 km from the row's own district median, which flags coordinate *or* district errors),
usable geo is still **99.40% for PHC and 99.29% for CHC**.

### Name: the problem

| | PHC | CHC |
|---|---|---|
| distinct `FAC_DESC` | 12,170 / 31,958 | 1,967 / 4,237 |
| rows ≤3 characters | 5,660 (17.71%) | 729 (17.21%) |
| **rows with zero residual after stripping type words** | **19,787 (61.92%)** | **2,395 (56.53%)** |
| rows uniquely keyed by (state, district, place-token) | 11,241 (35.17%) | 1,776 (41.92%) |

"PHC" appears 4,390 times. "phc" 1,086 more. "CHC" 558 times. For **62% of PHC rows and 57% of CHC
rows the name field contributes literally nothing** to distinguishing one facility from another.

### The verdict

**Yes, they can be matched — but only by geography, and only against a counterpart that has good
coordinates of its own.**

The standard blocking key for this project is *name + geo + district*. Here is how each leg
performs:

| blocking key | PHC rows isolated | CHC rows isolated |
|---|---|---|
| `state + district` | 0.01% | 1.70% |
| `state + district + name` | 38.56% | 53.32% |
| `BLOCK_ID + name` | 46.75% | 76.89% |
| **coordinate @ ~1.1 km cell** | **94.87%** | **95.68%** |

Name+district resolves well under half. **Geography resolves ~95%.** The recommended strategy is
therefore inverted from the project default: **geo-primary matching with a tight radius (100–500 m),
blocked by district, with name similarity used only as a tiebreak** — never as a confirmation, since
a 1.0 name similarity between two facilities both called "PHC" means nothing.

**Where this works well:** CHC. Only 4,237 facilities nationally means they are sparse — 95.68% sit
alone in a ~1.1 km cell and the *densest cell in the entire file holds 3 rows*. A geo-only match at
500 m is close to unambiguous. Combined with `BLOCK_ID`'s 43.62% singleton rate, CHC is genuinely
matchable.

**Where this works less well:** PHC. 31,958 facilities are denser, and PHCs cluster near the same
villages as sub-centres and wellness centres, which a counterpart registry may also list. A 500 m
geo match will sometimes have to choose between a PHC, a sub-centre, and an HWC at the same
location — with no name, no tier code, and no address to break the tie. Expect a meaningful false-
match rate on the 62% boilerplate-named rows unless the counterpart carries a tier field.

**Honest bottom line.** These two files should be unioned into one 36,174-row source and treated as
a **geospatial existence layer**, not as an identity source. They can confirm "there is a public
primary/community health facility at this point" with high confidence, and they can contribute a
`source_facility_id` and a block/habitation code. They cannot be relied on to tell you *which*
facility it is, or even reliably *what tier* it is. If a counterpart registry lacks coordinates,
roughly 60% of these rows are unmatchable by any means and should be loaded as new canonical
entities rather than forced into a name-similarity match that will be wrong.
