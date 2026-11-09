# v1 — Homogenization and merge

`db/facilities_v1.duckdb`. Built by `eda/build_v1.py` from `db/facilities_v0.duckdb`
in ~80 seconds. v0 is untouched and still rebuildable.

**341,720 source records → 323,359 facilities.** 18,361 records absorbed (5.4%).
13,491 facilities are confirmed by more than one source.

This closes Gaps 2, 3 and 4 of `03_GAP_REGISTER.md` to the extent they can be
closed without external data. Gaps 1 (specialty codebook) and 5 (beds) are
document hunts and remain open.

---

## What changed

| | v0 | v1 |
|---|---|---|
| grain | one row per source record | **one row per facility** |
| `count(*)` | upper bound on facilities | a facility count |
| `facility_type` | 56 raw strings | **22-value enum**, 99.6% populated |
| `ownership` | 15 raw strings | **5-value enum**, 82% resolved |
| `district` | 1,051 spellings | **914 canonical** |
| provenance | — | `v_source_record.facility_uid` + `match_pair` audit trail |

Two views, both PII-free by construction (NIN's `Coder` never enters v0):

- `v_facility` — 323,359 rows, one per facility
- `v_source_record` — 341,720 rows, joins on `facility_uid`

---

## Gap 3 — controlled vocabularies

`facility_type` is derived from **name tokens first** (70% of rows), the source's
own type column second. The source column had to be demoted: PHC/CHC carry the
filename tier with a ~4% leak, and NHP's was a constant injected at ingest.

```
SUB_CENTRE 86,587 · PHC 52,053 · HOSPITAL 44,568 · PHARMACY 29,659 ·
WELLNESS_CENTRE 28,123 · CLINIC 17,904 · CHC 13,974 · DIAGNOSTIC_LAB 10,878 ·
DISPENSARY 7,686 · AYUSH 6,951 · MATERNITY_HOME 5,452 · DENTAL 5,319 ·
BLOOD_BANK 3,400 · DISTRICT_HOSPITAL 2,978 · MEDICAL_COLLEGE 2,183 ·
BLOOD_STORAGE_UNIT 1,473 · UNKNOWN 1,256 · OTHER 858 · SUB_DISTRICT_HOSPITAL 761 ·
IMAGING_CENTRE 722 · PHYSIOTHERAPY 344 · DIALYSIS_CENTRE 230
```

"How many CHCs are there" is now `WHERE facility_type = 'CHC'` instead of an
IN-list of three spellings. Every raw → canonical mapping is in `dim_facility_type`
and `dim_ownership`, so a disputed call can be found and changed.

**Judgement call to be aware of:** `WELLNESS_CENTRE` (28,123) is mostly PHCs and
sub-centres relabelled HWCs under Ayushman Bharat. Counting "PHCs" may or may not
warrant including them. The enum keeps them separate so the choice stays visible.

## Gap 2 — district clustering

Spellings are clustered **within state** (Bijapur exists in both Karnataka and
Chhattisgarh), greedily, most-frequent-first, so the canonical form is always the
commonest spelling in that state. Threshold 86 on `token_sort_ratio`.

Guards matter more than the threshold. Without them:

- `BANGALORE R` and `BANGALORE U` — Bengaluru Rural and Urban, two districts —
  both collapse into `BANGALORE` at similarity 90
- `NORTH GOA` / `SOUTH GOA` merge at 89, `PURBA` / `PASCHIM BARDHAMAN` at 82

So directional tokens, numeric tokens, single-letter tokens and the first letter
must all agree exactly. The drop from threshold 90 to 86 was verified pair by
pair: 20 variants, 571 records, no false merges.

**914 canonical values against ~790 real districts.** The residual is renames, not
typos — Gurgaon/Gurugram, Allahabad/Prayagraj are different strings by any
measure. Only the LGD district master fixes those; the gap register's item #2
still stands.

## Gap 4 — entity resolution

**Blocking is geo-primary**, five passes unioned to 1.45M candidate pairs:

| pass | why |
|---|---|
| `geo_grid` ~1.1 km | the primary path, 285K trusted coordinates |
| `geo_grid_offset` | same grid shifted half a cell — catches pairs 40 m apart that straddle a boundary |
| `name_district` | for the 56,090 rows whose geo cannot be trusted |
| `phone` | exact dialable number |
| `pincode_name` | pincode present, geo absent |

No block exceeded the 400-row cap, so nothing was dropped.

**Matching is rule-based, not a tuned score.** Each accepted pair is stamped with
the rule that caused it, so a wrong cluster traces to a rule and the rule can be
changed. 21,401 pairs accepted (1.5% of candidates):

| rule | n | condition |
|---|---:|---|
| R5_GEO_GENERIC | 8,263 | ≤150 m, one name identifies nothing, types identical |
| R2_SAME_POINT | 6,240 | ≤50 m, name sim ≥70 |
| R3_GEO_NAME | 2,550 | ≤500 m, name sim ≥85, both names strong |
| R6_GEO_MEDIUM | 1,592 | ≤150 m, one-token names, sim ≥85 |
| R4_GEO_LOOSE | 1,336 | ≤1.5 km, sim ≥95, both names strong |
| R7_NAME_DIST | 1,205 | no usable geo, same district, sim ≥95, core ≥10 chars |
| R1_PHONE | 144 | same dialable phone, same state, ≤25 km |
| R8_PIN_NAME | 71 | no usable geo, same pincode, sim ≥95 |

Every rule pairs a distance budget with a name-strength requirement: the further
apart two records are, the more the name has to carry.

### Vetoes

- **Different hard type class** (BLOOD / CARE / DIAG / RETAIL). A blood bank
  shares its host hospital's coordinate and must not absorb it.
- **Different rung of the public-health ladder** (sub-centre → PHC → CHC → SDH →
  district hospital → medical college). These are *co-located by design*, so
  proximity is not evidence. This is what stops `KARAHALLI B SUBCENTER` merging
  with `PHC KARAHALLI` 126 m away. `WELLNESS_CENTRE` is deliberately outside the
  ladder, because HWC/PHC pairs usually *are* the same building.
- **Same source dataset** — v0 already deduplicated within source; re-merging
  there would silently overrule that decision.

---

## Three defects found by auditing the first build

Worth recording, because each produced plausible-looking output.

**1. `token_set_ratio` scores 100 on subsets.** Cores of `AYURVEDA` and
`AYURVEDA VECHOOCHIRA` matched perfectly, chaining **66 distinct ayurveda
dispensaries across a whole district** into one facility. Fixed by using
`token_sort_ratio`, for which subset agreement is not identity.

**2. Hand-listed stopwords will always miss one.** The list had `DISPENSARY` but
not `AYURVEDA`. Non-identifying tokens are now learned from the corpus — any
token in more than 500 records (135 of them) cannot single out a facility.

**3. A shared phone is not proximity.** A district health office number appears
against every CHC in the district, and merged two 90 km apart. R1 now requires
same state and ≤25 km.

Between them these accounted for the difference between a 9.2% reduction (wrong)
and 5.4% (defensible).

---

## What is NOT established

**There is no precision or recall figure.** No labeled pair set exists, so the
5.4% reduction is an unvalidated number. This is exactly where the prior merge
failed, and no amount of further tuning substitutes for labels.

`eda/er_review_sample.csv` is the input for fixing that: **285 pairs**, stratified
across every accepted rule plus two reject bands (near-misses at 70–85 similarity
within 500 m, and pairs the type veto killed at the same coordinate). Fill in the
`label` column with `match` / `no` and precision becomes measurable per rule.

**Known residuals:**

- **67 clusters mix public-health tiers** despite the veto. Transitive closure
  admits A~B and B~C even where A~C is vetoed. 67 of 323,359 — reported, not
  silently accepted.
- **12 clusters exceed 8 records** and are flagged `REVIEW_LARGE_CLUSTER`. Some
  are genuine (21 near-identical `HCG CANCER CENTRE` rows at one coordinate),
  others are chains.
- **Transitivity surfaced within-source duplicates that v0 missed** — 2,676 extra
  NHA records, 182 NIN, 156 PMGSY. They only merged because a record from a third
  source bridged them, which means the same-source veto is now hiding known
  duplicates. Lifting it is the obvious next experiment.
- **The matcher is conservative by choice.** A false merge destroys a facility
  and is invisible; a missed merge leaves the count high and is visible. Given no
  labels, we take the visible error, so **totals still lean high**.

## Next

1. Label `er_review_sample.csv` (~1 hour). Until then, no accuracy claim is honest.
2. Fetch the LGD district master — closes the last ~120 district spellings and
   makes the tier veto verifiable against real boundaries.
3. Re-test the same-source veto against the labeled set.
