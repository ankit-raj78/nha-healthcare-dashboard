# Gap Register — what's missing between here and the goal

Built from `eda/facilities_v0.duckdb` (341,720 source records, all 10 datasets harmonized).
Every number below came from querying that database.

---

## Where you are

`eda/facilities_v0.duckdb` exists and is queryable **now**. One table, one view:

- `facility_source_record` — 341,720 rows, one per source record
- `v_facility` — the clean query view. **PII-free by construction** (NIN's `Coder` is never ingested)

```
NHA 261,905 · PHC 31,958 · PMGSY 13,700 · PMJAY 11,284 · NIN 10,327
CDAC_BB 5,678 · CHC 4,237 · CGHS 1,983 · NHP 648
```

**The one caveat that governs everything:** this is v0 — harmonized and deduplicated *within* each
source, but **no cross-source entity resolution yet**. A facility listed in both NHA and PMJAY is two
rows. So `count(*)` is an **upper bound on facilities**, not a facility count. Confirmed:
**8,408 `name + district` groups already span more than one source.**

### Field coverage as it stands

| Field | Coverage | Verdict |
|---|---:|---|
| name | 100.0% | usable |
| state | 100.0% | **fixed** — 36 distinct values, down from 43 raw variants |
| district | 99.8% | populated but **not normalized** — see Gap 2 |
| latitude/longitude | 100.0% | 99.6% in-bbox, **83.6% pass geo trust** |
| facility_type | 96.1% | populated but **uncontrolled vocabulary** — see Gap 3 |
| ownership | 82.4% | usable after grouping |
| specialty | **7.0%** | **see Gap 1 — this is the big one** |
| pincode | **11.1%** | mostly absent |
| phone | **8.6%** | mostly absent, and partly corrupt |
| bed_count | **0.1%** | effectively absent |

---

## Gap 1 — Specialties: opaque *and* nearly absent  ⛔ BLOCKING

Two separate problems that compound.

**1a. The codes have no meaning.** `M1`–`M10` / `S1`–`S16` appear in NHA, PMJAY and CGHS. Your PMJAY
session established a **negative result**: the text columns contain the same opaque tokens, never a
word like "Cardiology". The codebook is not recoverable from any of the 10 datasets. CGHS carries a
*second*, mutually exclusive 22-token two-letter vocabulary on 1,001 rows.

**1b. Coverage is far thinner than the headline suggests.** This was not visible before the build:

| Source | Rows with any specialty | Of total |
|---|---:|---:|
| PMJAY | 11,284 | 100% |
| **NHA** | **10,585** | **4.0% of 261,905** |
| CGHS | 1,746 | 88% |
| everything else | **0** | — |

So "323K facilities with PMJAY specialties" is not what the data holds. Only **23,615 records
(7.0%)** carry any specialty at all, and for all of them the codes are undecoded.

**What's needed:** the PM-JAY Health Benefit Package specialty master (HBP 2.0 / HBP 2022), or the
NHA empanelment portal's specialty dropdown. **~25 rows of lookup data.** Separately, the CGHS
specialty code list (~22 rows). This is the highest-leverage missing artifact in the project — and
it is a document hunt, not a data-engineering task.

**Until then:** every specialty question is unanswerable, and no amount of further engineering
changes that.

---

## Gap 2 — District names are not normalized  🔴 HIGH

**1,051 distinct district values** for a country with ~790 districts. The excess is spelling variants.
Live example from the build:

```
KERALA / KASARAGOD  →  386 records
KERALA / KASARGOD   →   11 records     ← same district, split
```

**Impact:** every district-level aggregation is silently wrong, and district is a component of the
entity-resolution fallback key. This corrupts both querying and merging.

**What's needed:** the **LGD (Local Government Directory) district master** — ~790 rows of
`(state_code, district_code, district_name)` from `lgdirectory.gov.in`. Fuzzy-match our 1,051
variants onto it. This is the single highest-value *structured* artifact to fetch.

---

## Gap 3 — `facility_type` is an uncontrolled vocabulary  🔴 HIGH

96% populated, but the values are raw source strings that don't reconcile:

```
Community Health Centre   12,109        Primary Health Centre  22,497
Community Health Center    4,786   ←    PHC                    31,958   ← same thing,
CHC                        4,237        Sub Centre             96,439     3 spellings
```

**Impact:** "how many CHCs are there" currently requires knowing all three spellings. Any type-based
filter under-counts.

**What's needed:** no external data — this is derivable. A mapping table from ~60 observed raw values
onto a controlled enum (`SUB_CENTRE`, `PHC`, `CHC`, `DISTRICT_HOSPITAL`, `MEDICAL_COLLEGE`,
`BLOOD_BANK`, `BLOOD_STORAGE_UNIT`, `PHARMACY`, `DIAGNOSTIC_LAB`, `CLINIC`, `AYUSH`, …). Half a day
of work. Note the PHC/CHC tier labels are themselves unreliable (4.1% leak) and must be re-derived
from name tokens, not trusted.

---

## Gap 4 — No cross-source entity resolution  🔴 HIGH

**8,408 `name + district` groups span multiple sources**, and that's a floor — it only catches exact
normalized-name collisions, missing everything that differs by spelling or is name-poor.

**Impact:** you cannot currently answer "how many hospitals are in India" from this database. Only
"how many source records mention a hospital."

**What's needed:** Phase 3 as planned — geo-primary blocking, multi-signal scoring, transitive
closure. Plus **~300 hand-labeled match/non-match pairs**, which have to be *created*, not sourced.
Without them there is no way to know whether the matcher is right, which is exactly how the prior
merge ended up unvalidated.

---

## Gap 5 — Pincode 11%, phone 8.6%, beds 0.1%  🟡 MEDIUM

Sparse fields that limit both matching and answers.

- **Pincode** is the best fallback join key when geo is untrusted, and it's absent on 89% of records.
  **What's needed:** the **India Post PIN code directory** (~19,300 rows, `pincode → district,
  state`). This both fills the field *and* validates geo — a pincode that disagrees with the
  coordinate flags a bad record.
- **Phone** — CDAC_BB's is 91.6% populated but only **15.7% dialable** (3,611 rows destroyed by Excel
  scientific notation, irreversibly). Not fixable from these files.
- **Bed count** exists only in NHP (468 rows). Any capacity question is out of scope.
  **What's needed:** an external bed-capacity source (e.g. NHA facility registry export, HMIS).

---

## Gap 6a — NHA state labels disagree with NHA coordinates  🔴 HIGH

Found while smoke-testing the query agent, and not visible from single-dataset EDA.

Query `state = 'GOA'` and NHA returns facilities at 24.75°N / 79.5°E — Madhya
Pradesh. Checked against Goa's real bounding box (14.8–15.9°N, 73.6–74.4°E):

| source | rows labelled GOA | actually in Goa |
|---|---:|---:|
| **NHA** | **52** | **1** |
| PMJAY | 17 | 17 |
| NIN | 9 | 9 |
| CDAC_BB | 5 | 5 |
| CGHS | 1 | 1 |
| NHP | 1 | 1 |

Every other source is perfect; NHA is wrong on 51 of 52. Two things follow:

1. **`state` and `latitude/longitude` are independently unreliable in NHA** — the
   largest dataset, 77% of all records. Any state-filtered query against NHA
   inherits this.
2. **NHA's Goa coverage is separately suspect** — 52 rows for an entire state, out
   of 261,905, is implausibly low for a national registry.

Whether this is confined to Goa or is a broader label/coordinate misalignment is
**not yet established** — a median-distance test across all states is confounded
by genuinely large states (Rajasthan is 800km across), so it produced no clean
signal. Establishing the true scope needs the district boundary polygons from
Gap 6 — that's now the load-bearing reason to fetch them, not just a nice-to-have.

**Impact on Phase 3:** geo-primary blocking assumes the coordinate is right. Where
state and coordinate disagree, neither can be trusted, and the record needs a
third signal (pincode, address tokens) to break the tie.

## Gap 6 — Geo trust on 16.4% of records  🟡 MEDIUM

285,630 of 341,720 records (83.6%) pass the geo trust test; **56,090 do not** — centroid stacking,
shared points, nulls, out-of-bbox. Since Phase 3 blocks on geo, these fall to a weaker path.

**What's needed:** no external data. The LGD district master (Gap 2) plus district boundary polygons
would let us verify each point falls inside its stated district, upgrading the test from
"is it in India" to "is it where it claims to be."

---

## Gap 7 — Provenance and vintage  🟢 LOW

Snapshot dates are assigned from **filenames**, not data — CGHS's two date columns are the literal
constant `-NA`; PHC/CHC, NHP, NIN and CDAC_BB have no date column at all. Sources span **2022–2025**,
so a facility that closed in 2023 may still be present via an older source.

Also unexplained: NIN is a **5.4% extract** (`SrNo` runs 1→192,898 over 10,327 rows) of a larger
register, with no stated selection criterion. Its absences must not be read as "no facility there."

---

# The shopping list — what to actually go get

Ranked by value per unit of effort. The first three are small files that unblock disproportionate work.

| # | Artifact | Size | Unblocks |
|---|---|---|---|
| 1 | **PM-JAY HBP specialty master** | ~25 rows | All specialty queries across 23,615 records. **Currently blocking.** |
| 2 | **LGD district directory** | ~790 rows | Gap 2 entirely; strengthens Gaps 4 and 6 |
| 3 | **India Post PIN directory** | ~19,300 rows | Gap 5; a geo cross-check for Gap 6 |
| 4 | **CGHS specialty code list** | ~22 rows | 1,001 CGHS records |
| 5 | LGD block/village codes | ~2,600 blocks | Interprets PHC/CHC `BLOCK_ID`/`HAB_ID`; may resolve 43.6% of CHC rows directly |
| 6 | District boundary polygons (GeoJSON) | 790 shapes | Upgrades geo trust from bbox to point-in-district |
| 7 | Bed capacity source (HMIS / NHA export) | — | Capacity questions, currently impossible |
| 8 | ~300 hand-labeled match pairs | — | **Must be created.** Gates any credible Phase 3. |

Items 1–6 are public government data. Item 8 is the only one that requires human judgment, and it's
the one that determines whether the final numbers can be trusted.

---

# What you can honestly ask today

**Works now:**
- Counts and rankings by state — *"which states have the most facilities"*
- Source composition — *"what's in NHA vs PMJAY"*, *"which records appear in multiple sources"*
- Ownership splits — public 163,910 / private-trust 115,481
- Blood banks vs storage units (4,231 / 1,447) — the BSU extraction worked
- Geographic/radius queries on the 83.6% with trusted geo
- Any question about a *single* named facility

**Works with a caveat you must state:**
- District-level counts — until Gap 2, treat as approximate
- Facility-type counts — until Gap 3, you must enumerate spelling variants
- Any total facility count — it's an upper bound until Gap 4

**Cannot work yet:**
- Anything about specialties (Gap 1)
- Anything about beds or capacity (Gap 5)
- *"How many hospitals are in India"* as a true deduplicated count (Gap 4)
