# CHC — `21_June_2024_AM_CHC.csv`

**4,237 rows × 9 columns. Zero nulls. Zero exact duplicate rows. Every coordinate valid and inside India.**
Structurally the cleanest file in the corpus, and informationally one of the thinnest.

## What this is

A national inventory of India's **Community Health Centres** — the fourth tier of the public health
pyramid, above PHCs, typically 30-bed referral units serving roughly 80,000–120,000 people.
One row per facility, geocoded, tagged with state, district, and two hierarchical location codes.

4,237 CHCs is a plausible national figure (RHS reports roughly 5,500), so this is close to a census
but not complete — West Bengal has only 16 rows against Uttar Pradesh's 760, which cannot be right
demographically and points at uneven state-level submission rather than uneven reality.

The `HAB_ID` / `BLOCK_ID` / `FAC_CATEGO` naming and the constant `FAC_CATEGO = 'Medical'` indicate
this is not a health-ministry registry but health rows filtered out of a **habitation-level rural
amenities survey** — 'Medical' is the amenity category, not the facility class. The likely parent
is a rural-connectivity habitation database. That is inference, not fact; see `questions.md`.

**This file is one half of a pair.** `21_June_2024_AM_PHC.csv` (31,958 rows) has a *byte-identical*
schema, the same 29 states, the same constant `FAC_CATEGO`, and a shared ID namespace. 21 rows
appear verbatim in both files. Read `../PHC/CROSS_PHC_CHC.md` before treating them as independent
sources.

## What it is good for

- **Geo.** 4,237/4,237 coordinates parse; none null, zero, blank, out of bbox, or swapped. Range
  lon [68.83, 96.80], lat [8.20, 34.50]. 83.3% carry 8 decimal places. Only 30 rows (0.71%) are
  more than 100 km from their district median, and none is more than 600 km from its state median.
- **Administrative hierarchy.** Verified across the PHC+CHC union: 0 of 6,252 `BLOCK_ID`s span more
  than one district; 0 of 35,189 `HAB_ID`s span more than one block. This is a genuinely consistent
  national hierarchy.
- **Blocking power that PHC does not have.** Because CHCs are sparse — roughly one per block —
  `BLOCK_ID` alone isolates **43.62%** of CHC rows into singleton groups (the same key isolates only
  3.42% of PHC rows). `BLOCK_ID + name` isolates **76.89%**. For a 4,237-row file that is genuinely
  strong.
- **A clean primary key.** `FACILITY_ID` is unique across all 4,237 rows.

## What it is bad for

- **Names.** `FAC_DESC` is a facility *type*, hand-typed. 729 rows (17.21%) are ≤3 characters —
  "CHC" 558 times, "chc" 150, "Chc" 8. After stripping generic facility-type words, **2,395 rows
  (56.53%) have no residual token at all**. Spelling is chaotic: comunity, cummunity, cmmunity,
  Cammunity, Communty, helth, heath, healt, Helath all appear.
- **Everything except name, geo, state and district.** No address, pincode, phone, email, bed count,
  ownership, specialty, accreditation, scheme membership, or date. Nine columns, one of them
  constant. As a contributor to a canonical record this adds existence and a point, nothing more.
- **State coverage.** West Bengal (16), Sikkim (2), Mizoram (4), Ladakh (5) are implausibly low
  relative to Uttar Pradesh (760) and Rajasthan (479). Treat per-state counts as submission
  artifacts, not facility density.
- **Tier purity.** 39 rows (0.92%) are named as sub-centres, including 10 named exactly `HSC` —
  and all 10 of those also appear in the PHC file.

## The three things that would bite someone who joined this naively

**1. `FAC_CATEGO` does not distinguish CHC from anything.**
It is `'Medical'` for all 4,237 rows — and identically `'Medical'` for all 31,958 PHC rows. It is a
constant inherited from a parent amenities table. Mapping it to `facility_category_raw` yields a
single-valued column. **The CHC-vs-PHC distinction lives only in the filename** and must be
materialised as a column at load time, or the union of the two files becomes indistinguishable
from a single undifferentiated list.

**2. Joining on `(district, name)` collapses 35% of the file.**
"CHC" *is* the name for a sixth of the rows, so `(DISTRICT_NAME, normalised FAC_DESC)` has 1,476
removable duplicates — 34.8% of the dataset. The honest near-dupe key is normalised name plus
coordinate, which finds **1** removable row on an exact coordinate match and **22** at ~110 m.
Two orders of magnitude apart; the second number is the real one.

**3. `FACILITY_ID` is not local to this file.**
21 `FACILITY_ID`s in this file also appear in the PHC file, and in all 21 cases every one of the
nine columns is byte-identical. These are not collisions — they are the same facility written into
both files by the pipeline that split them. If you load PHC and CHC as separate sources and prefix
IDs with the dataset key, you manufacture 21 duplicate canonical entities. Prefix with a shared
key, or dedupe the union on the full row (36,195 → 36,174).

## Fitness for entity resolution — blunt version

| Field | Match value | Trust |
|---|---|---|
| `Latitude`/`Longitude` | **High** — the primary signal | 100% populated, 100% in-bbox, 95.68% of rows sit alone in a ~1.1 km grid cell |
| `BLOCK_ID` | **High within this corpus** | Isolates 43.62% of rows alone; but no external dataset carries this code |
| `STATE_NAME` | Good for blocking | 29 clean values; only `Tamilnadu` deviates from LGD |
| `DISTRICT_NAME` | Good for blocking | 10 truncated values, 1 `Unknown`; 6 names occur in 2 states |
| `FAC_DESC` | **Low** | 56.53% of rows carry zero place information |
| `FACILITY_ID` | Useless across datasets | Local to this source system (and shared with PHC) |

**Blocking key viability: yes.** `(state, district, name)` isolates **53.32%** of rows into
singletons — noticeably better than PHC's 38.56%, purely because there are fewer CHCs per district.
Using a residual place token extracted from the name uniquely keys **41.92%** of rows on
`(state, district, place-token)`.

**Realistic unmatchable fraction: ~57%.** For the 2,395 rows whose name is boilerplate, the only
evidence is a coordinate. Those rows can only be resolved by **geo-proximity matching at a tight
radius (≤500 m)** against a counterpart registry that itself has good coordinates. There is no
address, pincode, or phone to fall back on. The saving grace relative to PHC is density: CHCs are
sparse enough that a 1 km radius rarely admits two candidates, so a geo-only match is far less
ambiguous here than it is for PHCs — 95.68% of CHC rows are alone in their ~1.1 km cell, and the
most crowded cell in the entire file holds just 3 rows.
