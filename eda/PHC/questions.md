# PHC — Open questions

Things I could not determine from `21_June_2024_AM_PHC.csv` alone. Each states what I verified,
what I could not, and what specific artefact or person would resolve it.

---

## Q1 — What system issues `BLOCK_ID`, and is it the LGD block code? **(blocker for LGD joins)**

**What I verified.** 6,114 distinct integers in `[1, 8147]`, no gaps I checked for, no leading
zeros, no non-numerics. Every `BLOCK_ID` maps to exactly **one** `(STATE_NAME, DISTRICT_NAME)` —
0 violations across 6,114 blocks here, 2,644 in CHC, and 6,252 in the union. This is a genuine,
internally consistent national block namespace.

**What I could not determine.** Whether these are LGD (Local Government Directory) block codes.
The magnitude is wrong for my expectation of LGD block codes, and India has roughly 6,900 blocks,
so 6,114 distinct values across a dataset covering 29 states is plausible for "blocks that contain
at least one PHC" but I cannot confirm the code *system*.

**Why it matters.** If these are LGD codes, `BLOCK_ID` becomes a hard join key to the entire LGD
hierarchy and to every other dataset that carries LGD codes — that would be the single most
valuable field in this dataset. If they are internal serials, the column is useless outside this
file pair and must not be aliased to `block_lgd_code`.

**Resolves it.** The LGD block-code master (`lgdirectory.gov.in` block export). Take
`BLOCK_ID = 3265` (Solan, Himachal Pradesh, 74 rows) and `BLOCK_ID = 6` (96 rows) and check whether
those codes name the same blocks in LGD. A single confirmed match settles it.

---

## Q2 — What system issues `HAB_ID`, and what granularity is a "habitation"?

**What I verified.** 31,391 distinct integers in `[167, 1429223]`. Nests perfectly: 0 of the 35,189
union `HAB_ID`s span more than one `BLOCK_ID`, state, or district. 539 `HAB_ID`s carry more than one
facility (up to 5).

**What I could not determine.** Whether a "habitation" is an LGD village, a PMGSY habitation (which
is finer — a village can contain several habitations), or a census hamlet. The max value 1,429,223
is in the right range for either LGD villages (~660k) or PMGSY habitations (~1.7M) depending on how
sparsely the ids are allocated.

**Why it matters.** It determines whether `HAB_ID` maps to `village_lgd_code` (currently mapped at
**low** confidence) or needs a new canonical field. It also determines whether "two facilities in
one HAB_ID" is normal (habitation = small) or suspicious (habitation = whole village).

**Resolves it.** The PMGSY habitation master or the LGD village master. Check whether
`HAB_ID = 38361` (Solan, HP, 5 PHCs, spread over ~20 km) is a single habitation — if so, 20 km is
implausible and the id is coarser than the name suggests.

---

## Q3 — What is the parent dataset, and what other `FAC_CATEGO` values exist?

**What I verified.** `FAC_CATEGO` is the constant string `'Medical'` for all 31,958 PHC rows *and*
all 4,237 CHC rows. It is therefore not a facility classification.

**What I inferred but could not confirm.** The column name (`FAC_CATEGO` = facility category),
combined with `HAB_ID`/`BLOCK_ID` and the value `'Medical'`, strongly suggests these rows were
**filtered out of a larger habitation-amenities table** where the category vocabulary also contains
things like Education, Transport, Water, Sanitation. The `21_June_2024_AM_` filename prefix matches
the convention used by another dataset in this corpus (`21_JULY_23_SRK_PMGSY_...`), which points at
PMGSY as the parent — but I was instructed not to open that file, so this is unverified.

**Why it matters.** Three things follow from knowing the parent: (a) the complete `FAC_CATEGO`
codebook, which we currently have no key for; (b) whether the frame is **rural-only** — which would
explain the total absence of Delhi, Goa, Puducherry, Chandigarh, A&N, Lakshadweep and DNH&DD, and
would mean urban PHCs are systematically missing; (c) whether there are sibling files
(sub-centres? district hospitals?) that belong in this corpus.

**Resolves it.** Whoever produced the `21_June_2024_AM_` extract. Ask for the parent table and the
`FAC_CATEGO` domain. Failing that, the PMGSY habitation schema documentation.

---

## Q4 — Is the frame rural-only?

**What I verified.** Eight states/UTs have **zero** rows: Delhi, Goa, Puducherry, Chandigarh,
Andaman & Nicobar Islands, Lakshadweep, Dadra & Nagar Haveli and Daman & Diu (and Tamil Nadu appears
only under the non-LGD spelling `Tamilnadu`). Only 22 rows out of 31,958 (0.07%) have a name
containing `urban` or `UPHC`.

**What I could not determine.** Whether urban PHCs (UPHCs, of which India has several thousand under
NUHM) are excluded by design or simply absent from the parent frame.

**Why it matters.** If rural-only, then "facility not found in PHC dataset" carries no information
for any urban location, and matching an urban PHC from another registry against this file will
always fail — correctly. That needs to be encoded as a coverage boundary, not learned the hard way.

**Resolves it.** The parent dataset's inclusion criteria (see Q3). A quick proxy: check whether any
row falls inside a major metropolitan boundary.

---

## Q5 — What rule produced the PHC/CHC file split, and was it applied to `FAC_DESC`?

**What I verified.** 21 rows appear byte-identically in both files. **All 5** rows in either file
whose name contains both a PHC-token and a CHC-token are among them. **All 10** rows named exactly
`HSC` are among them. The remaining overlaps are `HC`, `c`, `hpc` — names that match no keyword at
all.

**What this means.** The split is almost certainly a keyword rule over `FAC_DESC` that emitted
ambiguous and unmatched rows to both outputs. That is an inference from a very clean pattern, not a
documented fact.

**What I could not determine.** (a) The exact rule and its keyword list. (b) **Whether rows that
matched neither keyword were dropped entirely from both files** — which would mean the parent table
contains health facilities that are in neither file. (c) Whether there was a `FAC_TYPE` column in
the parent that was used instead of, or alongside, the name.

**Why it matters.** If the parent had an authoritative facility-type column, we should use *that*
rather than trusting a filename. And if unmatched rows were dropped, this corpus is missing an
unknown number of health facilities.

**Resolves it.** The parent table row count for `FAC_CATEGO = 'Medical'`. If it is 36,174 (the
deduplicated union), nothing was dropped. If it is larger, the difference is the missing set.

---

## Q6 — Are the 32 `Unknown` districts the newly-created districts I think they are?

**What I verified.** 25 rows in Tamilnadu (BLOCK_IDs 8137–8141, HAB_IDs 1427787–1428920, centroid
79.7915 E / 11.1322 N) and 7 in West Bengal (BLOCK_IDs 8145–8147, HAB_IDs 1429000–1429223, centroid
88.5861 E / 27.0626 N). These carry the **highest** BLOCK_IDs and HAB_IDs in the file, i.e. they
were appended after everything else. Their facility names are unusually specific
(`"Algarah Primary Health Centre"`, `"Primary Health Centre Thirukalachery"`,
`"PHC Puthupattinam"`).

**What I inferred but could not confirm.** The Tamilnadu centroid sits in the Mayiladuthurai /
Sirkazhi area (Mayiladuthurai district created 2020) and the West Bengal one in the
Kalimpong / Algarah / Gorubathan area (Kalimpong district created 2017). Both post-date the
apparent freeze of the parent district master.

**Why it matters.** If confirmed, this is a **deterministic** repair for all 32 rows plus the 1 in
CHC — assign by BLOCK_ID range rather than reverse-geocoding each row. And it tells us the district
master's vintage, which predicts which *other* recently-created districts are mis-assigned to their
parent districts rather than flagged `Unknown`.

**Resolves it.** A point-in-polygon test of those 32 coordinates against a current district
shapefile. Five minutes of work for someone with the shapefile; I do not have one and will not
guess.

---

## Q7 — What is the actual snapshot date? Is `21 June 2024` the survey date or the export date?

**What I verified.** There is no date column anywhere in the file. The only temporal signal is the
filename `21_June_2024_AM_PHC.csv`.

**What I could not determine.** Whether 21 June 2024 is when the data was *collected*, when it was
*exported*, or when someone *saved the file*. Also unknown: what `AM` denotes — initials of the
person who produced it (matching the `SRK` / `AP` / `AR` initials in the other filenames in this
corpus) or something else.

**Why it matters.** Provenance and conflict resolution. When this dataset disagrees with another
about a facility's location, recency decides the winner. A 2024 export of a 2019 survey should lose
to a 2023 survey.

**Resolves it.** Ask whoever owns the `21_June_2024_AM_` extract. The `AM` initials are the thread
to pull.

---

## Q8 — Are the 1,298 sub-centre-named rows really sub-centres, or PHCs with sloppy names?

**What I verified.** 1,298 rows (4.06%) have names matching `sub`/`HSC`/`PHSC`/`SHC`, e.g.
`"Primary health sub centre"` (137 rows normalised), `"PHC sub center"` (158),
`"Primary Sub Centre"`. India has roughly 160,000 sub-centres, so 1,298 cannot be a sub-centre
inventory — but 4% contamination of a PHC inventory is entirely plausible.

**What I could not determine.** Whether the enumerator meant "this is a sub-centre" or "this is the
PHC that supervises a sub-centre" or simply typed a wrong word. Nothing in the row distinguishes
the cases: there is no bed count, no staffing, no type code.

**Why it matters.** It determines whether `facility_tier` for these rows should be `SUB_CENTRE` or
`PHC`. Getting it wrong creates false matches against registries that list only one tier, in either
direction.

**Resolves it.** A tier column from the parent table (Q3/Q5), or a sample cross-check of 20 of
these coordinates against a known sub-centre list.

---

## Q9 — Is the coordinate the facility building or the habitation centroid?

**What I verified.** All 31,958 coordinates are valid and in-bbox. 26,758 rows (83.7%) carry
8 decimal places — sub-millimetre precision, which is meaningless for a building and typical of a
value computed or copied rather than measured. 122 rows carry ≤4 dp. 61 rows share an exact
coordinate with another row, and 281 rows share a coordinate rounded to 4 dp (~11 m).

**What I could not determine.** Whether the point is a GPS reading taken at the facility door, a
habitation centroid inherited from `HAB_ID`, or a geocoded address. The 8-dp precision argues
against a handheld GPS reading. But the 376 shared-`HAB_ID` PHC/CHC pairs have a **median
separation of 60 m** and only 22 are at exactly the same point — if coordinates were habitation
centroids, far more pairs would coincide exactly. So they are probably facility-level. Probably.

**Why it matters.** It sets the correct radius for geo-primary matching, which is the *only* viable
matching strategy for the 62% of rows with no usable name. Facility-level points justify a 100–200 m
rule; habitation centroids would force something like 2 km and make the matching far more ambiguous.

**Resolves it.** The parent dataset's geo methodology (Q3), or a spot check of 10 coordinates
against satellite imagery to see whether they land on a building.

---

## Q10 — Why does West Bengal have 840 PHCs here but only 16 CHCs?

**What I verified.** PHC row counts by state look broadly proportionate to population
(Maharashtra 3,445; Uttar Pradesh 3,095; West Bengal 840). CHC counts do not: West Bengal has 16
against Uttar Pradesh's 760.

**What I could not determine.** Whether West Bengal's CHCs are absent because the state calls them
something else (Block Primary Health Centres / Rural Hospitals — West Bengal genuinely does use
different nomenclature), or because of a submission gap, or because the keyword split (Q5) failed
on West Bengal's naming convention and dumped them into the PHC file.

**Partial answer — I tested it.** Counting rows whose name matches
`bphc|block primary|block phc|rural hospital`:

| file | total such rows | West Bengal | Assam | Uttar Pradesh |
|---|---|---|---|---|
| PHC | 152 | **95** | 55 | 2 |
| CHC | 4 | 0 | 4 | 0 |

So **95 West Bengal rows in the PHC file are named "Block Primary Health Centre" / "BPHC"** —
e.g. `"KAMAKHYAGURI BLOCK PRIMARY HEALTH CENTRE"`, `"Sultanpur BPHC"`,
`"Dewanhat Block Primary Health Center"`, `"Patrasayer Block Primary Health Center"` — and **zero**
West Bengal rows in the CHC file carry that name. A BPHC in West Bengal is the block-level referral
unit, i.e. functionally the CHC tier. The keyword split (Q5) matched "primary" and routed them all
into the PHC file.

**What remains unresolved.** Whether a West Bengal BPHC should be canonicalised as `CHC` or as a
distinct tier. 95 rows does not close the gap to a plausible West Bengal CHC count either, so there
is probably a submission gap *as well as* a naming problem. And 55 Assam rows have the same issue.

**Resolves it.** Someone who knows West Bengal / Assam health-system nomenclature confirming
whether BPHC ≡ CHC for canonicalisation purposes. Until then, do not treat these 152 rows'
`facility_tier` as reliable.
