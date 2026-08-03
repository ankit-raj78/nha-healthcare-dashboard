# NIN — open questions for a human or an external source

Ordered by how much they block the harmonization step. Everything below is something I could
**not** determine from the file itself; nothing here is a guess dressed up as a finding.

---

## Q1 (blocking) — What does "NIN" actually stand for, and which programme produced this file?

The repository's own `README.md` line 13 asserts *"NIN | 10,530 | National Inventory for
Non-Communicable Diseases"*. Two problems:

- The row count in that README (10,530) is the **naive pandas parse**, not the logical row count
  (10,327), so the line was written without inspecting the blank rows. That undermines its
  authority as documentation.
- Nothing inside the file mentions NCDs, screening, or any programme at all. There is no scheme
  column, no NCD-specific facility type, no programme identifier.

"NIN" is also the standard abbreviation for the **National Institute of Nutrition** (ICMR,
Hyderabad), which would be a plausible commissioner of a hand-curated facility inventory.

**Ask:** whoever created `22_MAY_22_AP_NIN.csv`. What is the expansion of NIN, what is `AP` in the
filename (initials of the person who exported it? Andhra Pradesh? — Andhra Pradesh is only 236 of
10,327 rows so a state scope is unlikely), and which system was the SQL source?
**Why it matters:** this determines the `source_system` provenance value and whether the dataset
carries a selection bias (e.g. "facilities screened for NCDs") that would make it wrong to treat
as a general facility registry.

## Q2 (blocking) — What is the parent register that `SrNo` indexes, and can we get all of it?

`SrNo` is unique across all 10,327 rows and runs **1 to 192,898**. This file is therefore a
**5.35%** extract of something ~19× larger, and the extract is not a contiguous slice — the
largest consecutive-row jumps are 1,645, 1,616, 1,412, 1,295. A `Notes` value confirms `SrNo` is
the parent system's own identifier and is what coders cite when referring to another record:
`SrNo 89661` reads *"Duplicate or SR No. 85112"*, and 85112 does resolve inside this file
(see Q10).

**Ask:** what is the ~192,898-row source? Does it still exist? Was this file filtered by some
criterion (public facilities only? a specific programme? rows that had been geocoded?), and if so
what was the filter?
**Why it matters:** if the filter is knowable, we can state the dataset's coverage honestly. Right
now the state distribution (Tamil Nadu 2,736, Kerala **1**) is unexplainable and any coverage
claim about NIN would be misleading.

## Q3 (blocking) — What is the snapshot date of the underlying data?

**There is no date column of any kind in this file.** No `created_at`, no `updated_at`, no survey
year, nothing. The only signals:

- Filename `22_MAY_22` — plausibly 22 May 2022, but could be a version stamp.
- `State_Name` uses `Jammu & Kashmir` with no Ladakh, and `Dadra & Nagar Haveli` and
  `Daman & Diu` as **two separate UTs** — both admin vocabularies were superseded in
  **October 2019** and **January 2020** respectively.

So the admin vocabulary predates 2020 while the filename says 2022. Either the source data is
2019-or-earlier and was merely re-exported in 2022, or the state list was never refreshed.

**Ask:** what date should `source_snapshot_date` carry? Was the manual-curation pass done at a
different (later) date than the SQL extract?
**Why it matters:** cross-dataset conflict resolution needs a recency ordering. Without a date,
NIN cannot be ranked against NHA (2025), NHP (2023) or PMJAY (2023).

## Q4 — Which of the 50 `pincode` vs `Manual_Pincode` disagreements is correct?

On the 161 rows where both are populated they disagree on 50 (31.06%). I could only adjudicate 9
of the 50 from the file: in those 9 the manual pincode literally appears inside `Manual_Address`
and the auto pincode appears in **0** of them. That is one-directional but a thin sample.

Concrete unadjudicated examples where the two are far apart:

| row | SrNo | facility | state / district | `pincode` | `Manual_Pincode` |
|---|---|---|---|---|---|
| 819 | 4171 | `Akidattpur Nawada` | Bihar / Bhagalpur | 813204 | 805110 |
| 1385 | 7664 | `DMO Sindhudurg` | Maharashtra / Sindhudurg | 456812 | 416518 |
| 1358 | 7543 | `Medical College & Hospital, Kolkata` | West Bengal / Kolkata | 700012 | 700073 |
| 1243 | 6658 | `Kondoli Model Hospital` | Assam / Nagaon | 782101 | 782427 |

Row **1385** actually settles itself and supports the manual column: `DMO Sindhudurg` is in
Maharashtra, `456812` is a **Madhya Pradesh** series and `416518` is a **Maharashtra** series — the
auto value is in the wrong state entirely.

Row **819** is the genuinely ambiguous one: the auto pincode `813204` is a Bhagalpur series and
`District_Name` says Bhagalpur, but the facility is named `Akidattpur Nawada`, `Manual_Address`
reads `Sikandara, Lakhisarai Rd, Nawada, Bihar`, and the manual pincode `805110` is a Nawada
series. The **district itself** may be the wrong field, not the pincode.

**Ask:** a coder, or a pincode-to-district reference table. I have recommended
`COALESCE(Manual_Pincode, pincode)` in `field_map.yaml` at *medium* confidence; a definitive rule
would let me raise it to high.

## Q5 — Is `Non filled numbering` a pointer into a separate worksheet or ticket list?

623 rows, values 3..731, unique, monotonic in file order, with **106 gaps** inside 3..731 (108 if
you count the missing 1 and 2). The
mask is **exactly identical** to `Manual Health Facility Name`'s. The name reads as "numbering of
the records that were NOT filled" — i.e. a work queue of records needing manual research.

The gaps are the question. If it were a simple re-numbering of the curated rows it would be
contiguous 1..623. The missing numbers suggest **108 more queue entries exist somewhere that did
not make it into this file** — possibly a separate tracking sheet.

**Ask:** does a companion worksheet/tracker exist with entries 1, 2, 5, 6, 7, 8, 10, 13, 20, 24,
77, 92, 94, 95…?
Would it explain the 106 deleted rows visible as gaps in the stale pandas index?
**Why it matters:** if it is just a queue counter, drop it (my current recommendation). If it
points at an external tracker with adjudications in it, that tracker is more valuable than this
column.

## Q6 — Is `Facility Type = 'Others'` (2,382 rows, 23.07%) an ownership signal or a residual bucket?

1,692 of the 2,382 `Others` names (71%) contain `hospital` / `nursing home` / `clinic` / `NH`,
and only 27 contain a government marker (`Govt`, `District`, `Civil`, `CHC`, `PHC`, `Municipal`,
`ESI`). Names like `Lotus Apollo Hospital`, `DR GROVERS NURSING HOME`, `Aswini Hospital` are
unambiguously private. But I cannot tell whether `Others` was *defined* as "private facility" or
whether it is simply "did not fit the other 12 categories" and happens to be private-heavy.

Related: one `Notes` value reads *"name as per google- Deccan Hsopital and belongs to private
hospital category"* — a coder writing "private hospital category" in free text implies a category
concept exists that is **not** in the schema.

**Ask:** the codebook for `Facility Type`. Was there an ownership column in the parent register
that was dropped from this extract?
**Why it matters:** `facility_ownership_raw` is in the canonical vocabulary and NIN currently
contributes nothing to it. If `Others ≈ private`, NIN suddenly supplies ownership for 23% of its
rows.

## Q7 — Are the three bed-band values a real capacity measure or a coder's eyeball estimate?

`<100 Bedded Hospital` (183), `100-500 Bedded Hospital` (64), `>500 Bedded Hospital` (14) — 261
rows total. These are the only capacity signal in the entire dataset and they sit on the same
axis as functional types like `Dispensaries`, which is structurally wrong.

**Ask:** where did the bed bands come from — an actual bed count in the parent register, or a
coder's judgement? If a numeric `bed_count` exists upstream, it is far more useful than the band.

## Q8 — What are the units and source of `altitude`, and why is fill batch-correlated?

The values behave like metres above sea level and the state medians are geographically right
(J&K 1589, Uttarakhand 1320, Meghalaya 1019, Delhi ~0), so I am confident about the unit. Two
things I cannot determine:

1. **Provenance.** 1,928 of 3,881 non-zero values have decimals (e.g. `138.6`, `6.74`, `490.1`),
   which suggests a DEM/GPS lookup rather than manual entry. But `2700` appears on three separate
   Auraiya, UP facilities (`SrNo 35264`, `73904`, `149144`) where the true elevation is ~130 m,
   and `285`, `183`, `16` each appear 60+ times — patterns consistent with a *district-level*
   lookup table rather than a per-point one.
2. **Why the fill splits by capture batch.** Tamil Nadu is 97.9% non-zero, Delhi 0.16%,
   Chandigarh/Goa/Tripura/Puducherry/Mizoram/Nagaland exactly 0%. And by `SrNo` band: 73.5% of
   rows in `SrNo` 5,000–20,000 have an altitude vs 22–25% in every band above 20,000.

**Ask:** was altitude captured by a GPS device for one field campaign and left blank for the
rest? Is there a device/campaign identifier in the parent register?
**Why it matters:** if `altitude != 0` identifies a distinct capture campaign, it is a proxy for
geo *provenance*, and the geo quality of that subset can be assessed separately — which is more
useful than the altitude itself.

## Q9 — The 42 swapped and 85 out-of-bbox coordinates: repair or discard?

The 42 lat/lon swaps are mechanically recoverable. The 85 out-of-bbox rows are not — `fidusar`
(`SrNo 130978`, Rajasthan/Jodhpur) at `36.112439, -115.201119` is in Las Vegas; there is no
transformation that recovers Jodhpur from that.

The Rewari cluster is the real question: **59 of 89 Haryana/Rewari rows have coordinates outside
Rewari**, with names like `Durga Colony`, `Sector 1`, `Bhim Basti`, `Housing Board Sec 3`. These
look like *localities within Rewari town* that were geocoded as bare strings and matched to
same-named localities in Chennai, Bengaluru, Kolkata, Pune.

**Ask:** should NIN's coordinates for the Rewari block be discarded wholesale, or re-geocoded from
`District_Name` + `Health Facility Name`? Is there a known bad batch?
**Why it matters:** 89 rows is small, but if the same geocoding routine was used elsewhere the
1,297 rows sitting >300 km from their state centroid may be a much larger version of the same bug.

## Q10 — What does the `NOTIONAL ` name prefix mean? (74 rows — and it hides duplicates)

**74 facility names begin with the literal word `NOTIONAL`** — 73 in Rajasthan, 1 in Jharkhand:
`NOTIONAL Osian` (`SrNo 11669`), `NOTIONAL Gadra Road` (`SrNo 13038`), `NOTIONAL Kanod`
(`SrNo 14040`), `NOTIONAL Loonkaransar` (`SrNo 18409`), … The word is not part of any facility's
real name and appears in no other column.

This is **load-bearing for dedup**: stripping the prefix raises the name+district near-duplicate
count from **176 to 239** (+63). The coders' own duplicate flag confirms the mechanism —
`SrNo 89661` (`Gingla CHC`, Udaipur, `latitude = 0`) carries `Notes = "Duplicate or SR No. 85112"`,
and `SrNo 85112` **is** in this file as `NOTIONAL Gingla CHC`, same district, with valid
coordinates 24.299/74.030. Neither my name+geo nor my name+district rule catches that pair,
because the names differ by the prefix *and* one row's geo is the `0` sentinel.

**Ask:** what does NOTIONAL denote — a sanctioned-but-not-yet-functional facility, a
notional/planned location used for geo-placement, or an internal coder marker? Was it added by the
NIN team or inherited from the parent register?
**Why it matters:** if it is a status, it belongs in `record_status` and those 74 rows may not be
real operating facilities at all. Either way the prefix must be stripped before name matching, and
the resulting 63 extra near-duplicate pairs need adjudication.

## Q11 — What row-numbering did the coder mean by "Same as row 702"?

Row 693 (`SrNo 3508`, `Sub Divisional Hospital Biraul`) has `Notes = "Same as row 702"`. "Row 702"
does not resolve: positional index 702 is `SrNo 3626` / `Kanigiri` / Andhra Pradesh (unrelated),
there is no `SrNo 702` in the file, and `Non filled numbering` never reaches 702 for a Bihar row.
Almost certainly a spreadsheet row number in a version that has since been re-sorted or filtered.

**Ask:** which sheet and which sort order was the coder looking at?
**Why it matters:** together with `SrNo 89661` (resolved above, Q10) these are the only two
human-adjudicated duplicate calls in the file — ground truth for validating an automated dedup
rule.

## Q12 — Is `locality = 'Urban'` / `'Rural'` (75 rows) a settlement class, or a real place name?

43 rows hold the literal `Urban` and 32 hold `Rural` in a column otherwise full of neighbourhood
and city names. I read this as a settlement classification that leaked into the wrong column, but
I cannot rule out that the parent register had a `Urban/Rural` field whose values were
concatenated in. **Ask:** was there an urban/rural flag upstream?

## Q13 — What was deleted? 106 gaps in the stale pandas index, 203 blank rows

The BOM-only first column runs 0..10,635 with **106 missing values** (491, 496, 591, 614, 617,
624, 652, 663, 761, 778, 3406, 3547, 3600, 3601, …), meaning 106 rows were deleted after the
pandas export. Separately, 203 rows are present but entirely blank — 200 trailing and **3
interior** (positions 4789, 5740, 6444, holding index values 4811, 5771, 6487).

The trailing 200 look like spreadsheet drag-fill. The 106 deletions and the 3 interior blanks look
deliberate.

**Ask:** were the 106 deleted rows removed as duplicates, as out-of-scope facilities, or as bad
data? If they were removed as duplicates, that decision is itself useful signal and we should
recover the list.

---

## Things I checked and can answer — recorded here so nobody re-asks

- **Is `altitude` junk?** No. It holds real metres-above-sea-level for 3,881 rows; the other
  6,423 are the sentinel `0` and 23 are `\N`. State medians are geographically correct. Details in
  `issues.md` S1-4 and Q8 above.
- **Is `Coder` PII?** Yes, low sensitivity — first names of five internal staff. Keep internal,
  exclude from public/agent views. `issues.md` S1-7.
- **Which of the auto/manual pair is authoritative?** The manual one, in all three pairs. Evidence
  in `PROFILE.md`. Only `Manual_Pincode` retains a caveat (Q4).
- **Does `Notes` contain structured information worth extracting?** Yes — five patterns cover ~85%
  of the 156 populated rows (`not found` ×81, `Listed as <type>` ×26, `name as per google` ×17,
  borrowed-geo ×9, duplicate pointers ×2). Mapping in `field_map.yaml`.
- **What is column 1?** A stale pandas RangeIndex, and column 2 (`Non filled numbering`) is a
  manual-curation work-queue counter. Neither is facility data. See Q5 for the one residual
  unknown about column 2.
