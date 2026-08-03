# NHA — open questions

Things I could not determine from the data alone. Each names what I need, who or what
could answer it, and what breaks if it stays unanswered.

---

## BLOCKING

### Q1. What specialties are PMJAY codes `S8` and `S9`?

**Status: the only unresolved gap in an otherwise complete codebook.**

`merged_specialties` decodes 23 of the 25 `M*/S*_emp` flag columns to specialty names by
exact set-equality. For `S8_emp` (4,090 positive rows) and `S9_emp` (3,623 positive rows)
it carries the **literal strings** `"S8"` and `"S9"` — the upstream decoder failed on
exactly these two codes and left the raw token in place.

Row 63's `merged_specialties`:
`"Polytrauma, Plastic & reconstructive, Burns management, S8, S9, Urology, Orthopaedics,
Obstetrics & Gynaecology, Otorhinolaryngology, General Surgery"`

What the data does tell me: `S9_emp = 1` implies `S8_emp = 1` on all 3,623 rows, so S9 is a
strict subset of S8. Both sit between `Urology` (S7) and `Plastic & reconstructive` (S10)
in ordinal position.

**Ask:** NHA/PMJAY for the official Health Benefit Package specialty list with ordinal
codes. Two names from the 24-specialty list are needed.
**Do not guess** — Neurosurgery, Neurology and Interventional Neuroradiology are all
plausible fillers for that slot and I have no evidence to choose.
**Breaks if unanswered:** 4,090 facilities carry an unnameable specialty. Queries like
"which hospitals do neurosurgery" return nothing, silently.

### Q2. Is `S10_emp` = "Plastic & reconstructive" and `S11_emp` = "Burns management", or the reverse?

`S10_emp` and `S11_emp` are **byte-identical on all 323,460 rows** (both 3,176 positive),
and the two tokens `Plastic & reconstructive` and `Burns management` always co-occur in
`merged_specialties`. The set-equality proof therefore holds for *either* assignment. I
assigned them by ordinal position and flagged it `confidence: medium`.

**Ask:** same source as Q1 — the ordered specialty list resolves it immediately.
**Breaks if unanswered:** a specialty-name query returns the right facilities under
possibly the wrong label. Low blast radius, trivial to fix once the list exists.

### Q3. Why does 22.56% of the dataset have contradictory `24/7` values?

58,370 `Facility ID`s carry both `yes` and `no`. The pattern is mechanical — 53,728 of the
60,541 two-row groups differ in `24/7` and in no other column — which reads like a join
against a per-facility attribute table that had two rows per facility, or a melt/pivot that
was never collapsed.

I cannot tell **which value is correct**, or whether the two rows encode something real
that was lost (e.g. 24/7 *emergency* vs 24/7 *OPD*, or two different service points).

**Ask:** whoever produced this export — what was the join that fanned these rows out, and
does the source have a single `24/7` value per facility?
**Breaks if unanswered:** `24/7` is unusable for 22.56% of facilities, and the correct
de-duplication rule for S1-1 in `issues.md` is a guess (I collapse on "all columns except
`24/7`", which is safe for row counts but discards whatever the second row meant).

---

## IMPORTANT

### Q4. What do the verifier colours Green / Orange / Blue mean, and why is one column copied four times?

Green 281,386 / Orange 28,615 / Blue 13,459, **byte-identical across all four verifier
columns on every row**. So it is one signal, not four, despite names promising per-field
verification of name, address, facility type and ownership.

Cross-tabulating against `Ownership`, `ABDM Enabled` and `Facility Type` showed no clean
correspondence, so it is not a re-encoding of any of those.

Specifically: (a) Is this an ordinal confidence tier — Green verified, Orange
partially verified, Blue unverified? (b) Is Blue "not attempted" rather than "failed"?
(c) Was the four-column split ever populated independently, or was one result broadcast to
all four?

**Ask:** the team that ran the verification pass.
**Breaks if unanswered:** we cannot use the flag to weight record trust during entity
resolution — which is precisely what a quality tier is for. It gets loaded as an opaque
enum.

### Q5. Which district column is authoritative, and against which LGD vintage?

`new_district_name` is 1:1 with `district_code` (615 ↔ 615) and no district spans two
states, so the pair is internally consistent. But on the 867 rows where it disagrees with
`District_name`, its value appears in the row's own `Address` only 112 times vs 600 for
`District_name`, and on 263 rows **neither** matches (see `issues.md` S2-1).

So I can say `new_district_name` is *wrong* on those rows without being able to say
`District_name` is *right*.

Two sub-questions I cannot resolve internally:
1. **Which LGD vintage are `district_code` and `state_code` from?** `state_code` matches
   published LGD state numbering exactly. `district_code` values (e.g. 452 for `Narmada`,
   602 for `South Andamans`, 628 for `Anjaw`, 749 for `Ntr`) are plausible LGD district
   codes but I have **no LGD reference file in this project** to verify them against.
   India's districts change often — 615 distinct districts is well short of the ~780
   currently notified, which is expected given two states are missing, but I cannot confirm
   the codes are current rather than from an older vintage.
2. **Was `new_district_name` produced by fuzzy string matching?** The error signature says
   yes — `nadia`→`Narmada`, `una`→`Anjaw`, `dehradun`→`Mau`, `nainital`→`Mainpuri`,
   `jangoan`→`North Goa` are all edit-distance neighbours that cross state lines. If
   confirmed, the same failure mode is probably present, unflagged, on rows where the
   fuzzy match happened to land on a district in the correct state and so did not surface
   as a disagreement.

**Ask:** (1) an LGD district master file — **this is the single highest-value external
artefact for the whole project**, since every dataset's joins depend on district codes;
(2) the pipeline author, for the re-coding method.
**Breaks if unanswered:** district-level joins across the ten datasets are built on
unverified codes, and we have no way to bound the silent error rate.

---

## WORTH ASKING

### Q6. What is the snapshot date, and what does `AR` in the filename mean?

`1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv` implies March 2025, but **no
column in the file records a date** — no created, updated, verified, or extracted
timestamp. The canonical vocabulary wants `source_snapshot_date` and I can only fill it
from the filename, which is not evidence.

Sibling files in the working directory use the same convention with different initials
(`SRK`, `AM`, `AP`), so `AR` is most likely the initials of the person who prepared the
extract — but that is an inference from filenames, not a fact.

**Ask:** the data owner. Also worth asking whether the PMJAY specialty join was performed
at the same date as the NHA extract, since a stale join would explain part of Q3.
**Breaks if unanswered:** provenance metadata is filename-derived, and we cannot tell
which of ten datasets is freshest when they disagree about the same facility.

### Q7. Is `Facility ID` the HFR ID, and is it stable across releases?

Values run 108 – 588,417, dense, all numeric. It is almost certainly the ABDM Health
Facility Registry ID, which would make it joinable to any other HFR-derived source and the
strongest source key in the project.

But: is it stable across HFR releases, or re-issued? And is there a separate public
HFR facility code (the alphanumeric `IN…` form) that this is an internal surrogate for?

**Ask:** NHA/ABDM documentation.
**Breaks if unanswered:** we treat it as opaque and cannot join NHA to future refreshes or
to other ABDM-derived datasets by ID — falling back to fuzzy name+geo matching that we
would not otherwise need.

### Q8. Why are West Bengal and Lakshadweep absent, and Odisha down to 11 rows?

LGD codes 19 and 31 have zero rows. Odisha has 11, Goa 56, Meghalaya 96, Tamil Nadu 2,567
— against Uttar Pradesh's 62,801 (see `issues.md` S2-2).

Is this (a) states that never onboarded to HFR, (b) a failed extract for those states, or
(c) an intentional scope limit? The answer changes whether the gap is fillable.

**Ask:** the data owner.
**Breaks if unanswered:** we cannot tell whether the canonical database is missing West
Bengal because NHA never had it or because this particular file lost it — and therefore
cannot say whether another source would fill the hole.

### Q9. Should pharmacies and diagnostic labs be in a "health facility" table?

`Facility Type` includes `Pharmacy` (41,290 rows, 12.8%) and `Diagnostic Laboratory`
(14,865), plus `Imaging Center` (1,130) and `Dental Clinic` (4,087). These are not
care-delivery facilities in the sense the other nine datasets (PHC, CHC, blood banks,
medical colleges) use.

This is a scope decision for the canonical entity, not a data defect — but it needs
deciding *before* entity resolution runs, because 41,290 pharmacies with generic names
(`PHARMACY` ×144) and shared centroid coordinates are exactly the rows most likely to
produce false merges.

**Ask:** the project owner.
**Breaks if unanswered:** ~18% of NHA rows are of undecided relevance, and they are
disproportionately represented in the near-duplicate blocking keys.

### Q10. Does `M9_emp` exist upstream?

The file has `M1_emp`–`M8_emp` and `M10_emp` — **`M9_emp` is absent from the header**, and
`M10_emp` is positive on only 4 rows (decoding to `OPD Diagnostic`). No token in
`merged_specialties` is left over to account for a missing M9.

So either the source specialty list genuinely has no M9, or the column was dropped and the
4 remaining `M10_emp` rows are the tail of a mostly-lost column family.

**Ask:** same source as Q1 — the ordered specialty list settles it.
**Breaks if unanswered:** if M9 exists upstream, an entire specialty is missing from
every NHA row, invisibly. Low probability, high cost, cheap to check.
