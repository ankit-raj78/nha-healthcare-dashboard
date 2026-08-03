# CHC — Open questions

Things I could not determine from `21_June_2024_AM_CHC.csv` alone. Each states what I verified,
what I could not, and what specific artefact or person would resolve it. Questions Q1–Q5 and Q7–Q9
apply identically to the PHC sibling file; Q6 and Q10 are CHC-specific.

---

## Q1 — What system issues `BLOCK_ID`, and is it the LGD block code? **(blocker for LGD joins)**

**What I verified.** 2,644 distinct integers in `[1, 8145]`, no leading zeros, no non-numerics.
Every `BLOCK_ID` maps to exactly **one** `(STATE_NAME, DISTRICT_NAME)` — 0 violations across 2,644
blocks here and 6,252 in the PHC+CHC union. 2,506 of the 2,644 (94.78%) also appear in the PHC
file, always denoting the same district. This is a real, shared, internally consistent national
block namespace.

**What I could not determine.** Whether these are LGD (Local Government Directory) block codes. The
magnitude looks wrong for LGD block codes, and India has roughly 6,900 blocks, so ~6,250 distinct
values across the union is plausible for "blocks containing at least one PHC or CHC" — but that
does not identify the code *system*.

**Why it matters more for CHC than for PHC.** `BLOCK_ID` alone isolates **43.62%** of CHC rows into
singleton groups (vs 3.42% for PHC), because CHCs are roughly one-per-block. If `BLOCK_ID` is an
LGD code, it becomes a near-primary-key join to any LGD-coded dataset and instantly resolves nearly
half this file. That is the highest-leverage unknown here.

**Resolves it.** The LGD block-code master (`lgdirectory.gov.in` block export). Check
`BLOCK_ID = 6171` (55 rows) and `BLOCK_ID = 4060` (31 rows) against LGD. One confirmed match
settles it.

---

## Q2 — What system issues `HAB_ID`, and what granularity is a "habitation"?

**What I verified.** 4,174 distinct integers in `[349, 1428938]`. Nests perfectly: 0 of the 35,189
union `HAB_ID`s span more than one `BLOCK_ID`, state, or district. 63 `HAB_ID`s carry 2 rows.
376 `HAB_ID`s (9.01% of CHC's habitations) also appear in the PHC file — same village with both a
PHC and a CHC — at a median separation of 60 m.

**What I could not determine.** Whether a "habitation" is an LGD village, a PMGSY habitation (finer
than a village), or a census hamlet. The max value 1,428,938 is consistent with either LGD villages
(~660k) or PMGSY habitations (~1.7M) depending on id density.

**Why it matters.** It decides whether `HAB_ID` legitimately maps to `village_lgd_code` (currently
mapped at **low** confidence) or needs a new canonical field. It also calibrates the 376 shared-HAB
PHC/CHC pairs: if a habitation is small, a 60 m median separation confirms these are two facilities
on one campus; if it is a whole village, the pairs mean much less.

**Resolves it.** The PMGSY habitation master or the LGD village master.

---

## Q3 — What is the parent dataset, and what other `FAC_CATEGO` values exist?

**What I verified.** `FAC_CATEGO` is the constant string `'Medical'` for all 4,237 CHC rows *and*
all 31,958 PHC rows. It is not a facility classification and does not distinguish the two files.

**What I inferred but could not confirm.** `FAC_CATEGO` = facility *category*, combined with
`HAB_ID`/`BLOCK_ID` and the value `'Medical'`, points at these rows having been **filtered out of a
larger habitation-amenities table** whose category vocabulary presumably also contains Education,
Transport, Water, Sanitation. The `21_June_2024_AM_` filename convention matches
`21_JULY_23_SRK_PMGSY_...` elsewhere in this corpus, which suggests PMGSY as the parent — but I was
instructed not to open that file, so this is unverified.

**Why it matters.** Knowing the parent gives us (a) the complete `FAC_CATEGO` codebook, for which
we currently have no key; (b) whether the frame is rural-only (see Q4); (c) whether sibling files
exist for other facility tiers.

**Resolves it.** Whoever produced the `21_June_2024_AM_` extract, or the PMGSY habitation schema
documentation.

---

## Q4 — Is the frame rural-only?

**What I verified.** Eight states/UTs have **zero** rows: Delhi, Goa, Puducherry, Chandigarh,
Andaman & Nicobar Islands, Lakshadweep, Dadra & Nagar Haveli and Daman & Diu (and Tamil Nadu appears
only under the non-LGD spelling `Tamilnadu`). **Zero** rows in the file contain `urban` or `UPHC` in
the name.

**What I could not determine.** Whether urban facilities are excluded by design or simply absent
from the parent frame.

**Why it matters.** If rural-only, then "no CHC found near this urban coordinate" carries no
information, and matching an urban facility from another registry against this file will always
fail — correctly. That must be encoded as a coverage boundary rather than discovered downstream.

**Resolves it.** The parent dataset's inclusion criteria (Q3).

---

## Q5 — What rule produced the PHC/CHC file split?

**What I verified.** 21 rows appear byte-identically in both files. **All 5** rows in either file
whose name contains both a PHC-token and a CHC-token are among them. **All 10** rows named exactly
`HSC` are among them. The rest are `HC`, `c`, `hpc` — names matching no keyword at all.

**What this implies.** A keyword rule over `FAC_DESC` that emitted ambiguous and unmatched rows to
both outputs. Clean pattern, but an inference, not a documented fact.

**What I could not determine.** (a) The exact rule and keyword list. (b) **Whether rows matching
neither keyword were dropped from both files** — which would mean the parent contains health
facilities present in neither. (c) Whether the parent had an authoritative `FAC_TYPE` column that
should have been used instead.

**Why it matters.** `facility_tier = 'CHC'` is currently an assertion made by a string rule over a
field that is 57% boilerplate. If the parent has a real type column, use that.

**Resolves it.** The parent table's row count for `FAC_CATEGO = 'Medical'`. If it equals 36,174
(the deduplicated union), nothing was dropped; anything larger is the missing set.

---

## Q6 — Why does West Bengal have only 16 CHCs? **(CHC-specific, and I have a partial answer)**

**What I verified.** State counts range from 2 (Sikkim) to 760 (Uttar Pradesh). West Bengal has
**16** CHC rows against 840 PHC rows — implausible for a state of ~90 million.

I tested the "different nomenclature" hypothesis by counting rows named
`bphc|block primary|block phc|rural hospital`:

| file | total | West Bengal | Assam | Uttar Pradesh |
|---|---|---|---|---|
| PHC | 152 | **95** | 55 | 2 |
| CHC | 4 | **0** | 4 | 0 |

**95 West Bengal block-level referral units are sitting in the PHC file** under names like
`"KAMAKHYAGURI BLOCK PRIMARY HEALTH CENTRE"`, `"Sultanpur BPHC"`,
`"Dewanhat Block Primary Health Center"`. Zero are in the CHC file. West Bengal calls its
block-level referral unit a BPHC, the split rule (Q5) matched "primary", and routed them all to PHC.
Assam has the same problem with 55 rows.

**What remains unresolved.** (a) Whether a West Bengal BPHC should canonicalise as `CHC` or as its
own tier — this needs someone who knows the state's health-system structure. (b) 16 + 95 = 111 is
still short of a plausible West Bengal CHC count, so there is likely a **submission gap as well**.
(c) The same question for Sikkim (2), Mizoram (4), Ladakh (5).

**Why it matters.** This file cannot be used for per-state denominators or coverage analysis until
resolved. "No CHC in this West Bengal district" currently means nothing.

**Resolves it.** West Bengal's and Assam's own facility lists, plus a nomenclature ruling on
BPHC ≡ CHC.

---

## Q7 — What is the actual snapshot date? Is `21 June 2024` the survey date or the export date?

**What I verified.** No date column exists anywhere in the file. The only temporal signal is the
filename `21_June_2024_AM_CHC.csv`.

**What I could not determine.** Whether 21 June 2024 is collection, export, or file-save date. Also
unknown what `AM` denotes — plausibly the initials of the person who produced it, matching the
`SRK` / `AP` / `AR` initials in other filenames in this corpus.

**Why it matters.** Recency decides the winner when this dataset disagrees with another about a
facility. A 2024 export of a 2019 survey should lose to a 2023 survey.

**Resolves it.** Whoever owns the `21_June_2024_AM_` extract. The `AM` initials are the thread.

---

## Q8 — Are the 39 sub-centre-named rows really sub-centres?

**What I verified.** 39 rows (0.92%) match `sub`/`HSC`/`PHSC`/`SHC`, including 10 named exactly
`HSC` (all in `Jharkhand / Saraikela-kharsawan`) — and all 10 of those also appear in the PHC file.
Others: `"community health sub centre"` (Anantapur), `"Community Health Sub Centre Beehan"`
(Kangra), `"sub center vachchharwad"` (Navsari), `"Telmachcho Health Sub center"` (Dhanbad).

**What I could not determine.** Whether the enumerator meant "this is a sub-centre", "this is the
CHC supervising a sub-centre", or simply typed the wrong word. Nothing else in the row
distinguishes the cases — there is no bed count, staffing, or type code. The 10 Jharkhand `HSC`
rows are the most suspicious: a real CHC would not be recorded with a three-letter sub-centre
acronym, and their presence in both files means the split rule could not classify them either.

**Why it matters.** A CHC is a ~30-bed referral unit; a sub-centre is a two-staff outpost.
Mis-tiering creates false matches in both directions.

**Resolves it.** A tier column from the parent (Q3/Q5), or a spot check of the 10 Saraikela-kharsawan
coordinates against a Jharkhand sub-centre list.

---

## Q9 — Is the coordinate the facility building or the habitation centroid?

**What I verified.** All 4,237 coordinates are valid and in-bbox. 3,529 rows (83.3%) carry 8 decimal
places — sub-millimetre, which is meaningless for a building and typical of a computed or copied
value rather than a measured one. 13 rows carry ≤4 dp. 5 pairs share an exact coordinate;
32 rows share a coordinate rounded to 4 dp (~11 m).

**Evidence it is facility-level.** The 376 habitations that have both a PHC and a CHC show a median
PHC↔CHC separation of **60 m**, with only 22 pairs at exactly the same point and 312 within 1 km.
If both files inherited a habitation centroid, far more of those 376 pairs would coincide exactly.
So the points are probably per-facility. Probably.

**What I could not determine.** Whether it is a GPS reading at the door, a geocoded address, or
something else. The 8-dp precision argues against a handheld GPS reading.

**Why it matters.** It sets the radius for geo-primary matching, which is the only viable strategy
for the 57% of rows with no usable name. Facility-level points justify 100–200 m; habitation
centroids would force ~2 km and make matching far more ambiguous.

**Resolves it.** The parent dataset's geo methodology (Q3), or a spot check of 10 coordinates
against satellite imagery.

---

## Q10 — Is 4,237 a national census of CHCs, or a partial extract? **(CHC-specific)**

**What I verified.** 4,237 rows across 29 states. India's Rural Health Statistics reports on the
order of 5,500 CHCs. The shortfall is concentrated in specific states (Q6), not spread evenly.

**What I could not determine.** Whether the ~1,300-row gap is (a) urban CHCs excluded by a
rural-only frame (Q4), (b) nomenclature routing errors like West Bengal's BPHCs (Q6), (c) states
that did not submit, or (d) a different vintage of the CHC count. All four are plausible and they
are not mutually exclusive.

**Why it matters.** This determines whether "facility absent from the CHC dataset" is usable as
negative evidence during entity resolution. Right now it is not, and any pipeline that treats a
non-match as "this facility does not exist" will be wrong at an unknown rate.

**Resolves it.** Reconciling this file's per-state counts against the corresponding-year Rural
Health Statistics table. That is a 30-minute task for someone with the RHS PDF, and it would
convert this from an unknown into a documented, per-state coverage figure.
