# PHC — `21_June_2024_AM_PHC.csv`

**31,958 rows × 9 columns. Zero nulls. Zero exact duplicate rows. Every coordinate valid and inside India.**
And it is still one of the hardest datasets here to match, because 62% of the rows have no name.

## What this is

A national inventory of India's **Primary Health Centres** — the third tier of the public health
pyramid (sub-centre → PHC → CHC → sub-district hospital → district hospital). One row per facility,
geocoded, tagged with state, district, and two hierarchical location codes.

The `21_June_2024_AM_` filename prefix and the `HAB_ID` / `BLOCK_ID` / `FAC_CATEGO` column naming
point at a **habitation-level rural infrastructure survey** rather than a health-ministry registry:
`FAC_CATEGO = 'Medical'` is the giveaway — it is the *category of amenity*, and 'Medical' is one
value in a vocabulary that presumably also contains 'Education', 'Transport', and so on. The health
facilities were filtered out of a larger amenities table. The most likely parent is the PMGSY /
rural-connectivity habitation database, but **this is inference, not fact** — see `questions.md`.

31,958 PHCs is the right order of magnitude for India (RHS reports roughly 30k), so this reads as
close to a national census rather than a sample. Eight states/UTs are missing entirely: Delhi, Goa,
Puducherry, Chandigarh, Andaman & Nicobar, Lakshadweep, and Dadra & Nagar Haveli and Daman & Diu.
That absence is consistent with a *rural* habitation frame — the missing entries are the ones with
no rural habitations to speak of.

**This file has a sibling, `CHC` (4,237 rows), with a byte-identical schema. Read
`CROSS_PHC_CHC.md` before doing anything with either.** The short version: they share one ID
namespace, 21 rows appear in both, and the split between them was made by keyword-matching the name
field.

## What it is good for

- **Geo.** This is the standout. 31,958/31,958 coordinates parse, none are null, zero, blank, out of
  the India bbox, or swapped. 83.7% carry 8 decimal places. Only 192 rows (0.60%) sit more than
  100 km from their own district's median point, and none sits more than 600 km from its state
  median. If you need a point layer of Indian PHCs, this is usable as-is.
- **Administrative hierarchy.** `BLOCK_ID` and `HAB_ID` are genuinely well-formed. Verified across
  the PHC+CHC union: **0 of 6,252 blocks span more than one district**, and **0 of 35,189
  habitation ids span more than one block**. That is a real, internally consistent national
  hierarchy — rarer than it sounds in this corpus.
- **A clean primary key.** `FACILITY_ID` is unique across all 31,958 rows, integer, no leading
  zeros, no non-numerics.
- **Coverage of small facilities.** The other datasets in this project skew toward hospitals.
  This one is 31,958 rows of the bottom of the pyramid — facilities that a PMJAY or NHA registry
  will largely not contain.

## What it is bad for

- **Names.** `FAC_DESC` is not a name field. It is a *facility type*, hand-typed, in whatever
  spelling the enumerator felt like. 5,660 rows (17.71%) are three characters or fewer — "PHC"
  appears 4,390 times, "phc" 1,086 more. After stripping generic facility-type words, **19,787 rows
  (61.92%) have no residual token whatsoever**. For those rows the name contributes literally
  nothing to a match.
- **Anything beyond name + geo + district.** There is no address, pincode, phone, ownership, bed
  count, specialty, scheme membership, or date. Nine columns, one of which is constant. This is a
  thin dataset and it will contribute almost nothing to a canonical record beyond existence and
  location.
- **Tier purity.** 1,298 rows (4.06%) are named as *sub-centres* (`Primary health sub centre`,
  `PHC sub center`, `HSC`), which is a lower tier with a different catchment and staffing. If you
  load this as "PHCs" you are wrong about 4% of it.
- **Provenance.** No snapshot date column, no source-sheet column, no record-status column. The
  only date is in the filename.

## The three things that would bite someone who joined this naively

**1. Joining on `(district, name)` collapses 55% of the file.**
Because "PHC" *is* the name for a sixth of the rows, `(DISTRICT_NAME, normalised FAC_DESC)` has
17,745 removable duplicates — 55.5% of the dataset. Anyone who writes
`GROUP BY district, name` or dedupes on that key will silently destroy tens of thousands of real,
distinct facilities. The correct near-dupe key is **normalised name + coordinate**, which finds
16 removable rows on an exact-coordinate match and 134 at ~110 m. Those numbers are three orders
of magnitude apart, and the second one is the true one.

**2. `FAC_CATEGO` is constant, so it does not mean what its name implies.**
It is `'Medical'` for all 31,958 rows — *and* `'Medical'` for all 4,237 rows of the CHC file. It is
a survey-level amenity category inherited from a parent table, not a facility classification.
Anyone who maps it to `facility_category_raw` and expects to distinguish PHC from CHC gets a column
of one value. Drop it. **The PHC-vs-CHC distinction exists only in the filename** and must be
materialised as a column at load time or it is lost forever.

**3. A repeated `HAB_ID` is not a duplicate row.**
1,106 rows (3.46%) share a `HAB_ID` with another row, across 539 habitations, up to 5 rows deep
(HAB_ID 38361, Solan, Himachal Pradesh — five distinct PHCs up to 20 km apart). `HAB_ID` identifies
the *habitation*, not the facility. Deduping on it destroys real facilities. `FACILITY_ID` is the
only unique column, and even that is shared with the CHC file.

## Fitness for entity resolution — blunt version

| Field | Match value | Trust |
|---|---|---|
| `Latitude`/`Longitude` | **High** — the only reliable signal | 100% populated, 100% in-bbox, 94.87% of rows sit alone in a ~1.1 km grid cell |
| `STATE_NAME` | High for blocking, zero for discrimination | 29 clean values, one LGD spelling deviation |
| `DISTRICT_NAME` | Good for blocking | 226 truncated values and 32 `Unknown` need repair first |
| `BLOCK_ID` | Good for blocking **within this corpus only** | Provably consistent, but no other dataset will carry it |
| `FAC_DESC` | **Low** | 61.92% of rows carry zero place information |
| `FACILITY_ID` | Useless across datasets | Local to this source system |

**Blocking key viability: yes for `state + district`, no for `state + district + name`.**
`(state, district)` produces 678 groups averaging 47 rows — too coarse to be a match on its own but
fine as a blocker. Adding the name isolates only 38.56% of rows into singletons.
Adding a *residual place token* extracted from the name (after stripping type words) uniquely keys
**35.17%** of rows.

**Realistic unmatchable fraction: ~62%.** For the 19,787 rows whose name is pure boilerplate, the
only usable evidence is a coordinate. Matching those to another registry requires **geo-proximity
matching with a tight radius (≤500 m) as the primary rule**, with name similarity as a tiebreak
that will usually be uninformative. There is no address, no pincode, and no phone to fall back on.
If the counterpart dataset's coordinates are poor, those 62% of rows are simply unmatchable —
and should be loaded as new canonical entities rather than forced into a bad match.
