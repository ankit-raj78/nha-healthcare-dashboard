# NHP — Open questions requiring a human or an external source

Each item states what was measured, what could not be determined from the data alone, and what
answer would unblock the harmonization step. Nothing here is a guess presented as a finding.

---

## Q1 · What is the `Domains` column supposed to hold? **(blocks: nothing today, but it is a named canonical target)**

`Domains` is 100% empty — 0 non-null across all 999 CSV records, only the header exists.

Plausible readings, none confirmable from this file:
- website domain names (would be `website` in the canonical vocabulary),
- clinical domains / specialty areas (would be `specialty_list`),
- "domain" in the NHP-portal sense of a subject taxonomy,
- an administrative jurisdiction.

**Ask:** whoever produced `8_JULY_23_SRK_...`. If any *other* NHP extract has this column populated,
one populated sample settles it. Until then it is dropped, and no canonical field is created from it.

---

## Q2 · Are `Accrediation` and `Contact` empty because the data was never collected, or because it was stripped?

Both are 100% empty (0/999). `Accrediation` (misspelled in the header) would map to the canonical
`accreditation`; `Contact` would map to `phone`.

This matters because they are the only route to two canonical fields we otherwise cannot fill for
medical colleges. If the source NHP pages carry NMC/NAAC accreditation status and a phone number,
re-scraping is worth doing; if they never had them, the fields should be marked
"not available from NHP" in the canonical schema and stop being chased.

**Ask:** does the upstream NHP medical-colleges page carry accreditation and contact fields?
Was a PII-stripping step applied to this file? (No PII of any kind survives: 0 emails, 0 phone-shaped
strings, 0 URLs across all 648 rows — which is itself weakly suggestive of stripping.)

---

## Q3 · Are S.No 177 and S.No 234 the same institution?

```
S.No 177  'Shri Atal Bihari Vajpayee Medical College & Research Centre, Bangalore
           (formerly known as Bowring & Lady Curzon Medical College & Research Institute'
S.No 234  'Shri Atal Bihari Vajpayee Medical College & Research Institute'
```
Both: City = Bangalore, State = Karnataka, coordinates **identical** (12.98323, 77.60422),
`address_py` **identical** ("Bowring and Lady Curzon Hospitals, Opposite Bowring Hospital, ...").
Note S.No 177's name is itself truncated — the closing parenthesis is missing.

`Admission Intake` and bed counts should differentiate them if they are genuinely two entities.
Neither is a fully-exact duplicate row, so the automated exact-dupe check (0 hits) will not catch it.

**Ask:** is this one college double-listed under its old and new name, or two co-located
institutions? If it is a double-listing, it is the only within-dataset entity duplicate found and
the true row count is 647, not 648.

---

## Q4 · Is (11.12712, 78.65689) a state-centroid fallback, and how many other rows are affected?

Three rows share that exact coordinate:
```
S.No 482 'St. Peters Medical College Hospital and Research Instt.'       City = Chennai
S.No 483 'Swamy Vivekanandha Medical College Hospital and Research Instt.' City = Chennai
S.No 497 'Bhaarat Medical College & Hospital'                            City = Chennai
```
That coordinate is the widely-published geographic centroid of Tamil Nadu, roughly 250 km from
Chennai — so all three are almost certainly geocoder fallbacks, and their `City = Chennai` is
inconsistent with their own coordinates. Two more rows share the Chennai city centroid
(13.08268, 80.27072).

I can detect *shared* coordinates (7 rows) but **cannot** detect a centroid fallback that happened
to hit only one row, because I have no reference table of state/district/city centroids.

**Ask:** provide (or point me at) the centroid table the original geocoder used — most likely
Google Geocoding's `location` for the administrative-area result. With it, a single join would flag
every centroid-fallback row instead of only the collisions. **Do not resolve this by guessing.**

---

## Q5 · What snapshot date does this file represent?

Nothing inside the file carries a date. The only evidence is the filename prefix
`8_JULY_23_SRK_` → 2023-07-08, and `SRK` presumably being the person who produced it.

648 medical colleges is consistent with India's count in the 2022–23 academic year, which weakly
corroborates a 2023 vintage — but "when the file was made" and "when NHP last refreshed the
underlying page" are different dates, and the `Admission Intake` figures belong to the latter.

**Ask:** what NHP snapshot / academic year do the `Admission Intake` and bed figures describe?
`source_snapshot_date` is currently set to `2023-07-08` with `confidence: low` in `field_map.yaml`.
Also: who is `SRK`, and is there a processing script for the `_py` columns we can read?

---

## Q6 · What produced `address_py`, and can we recover its confidence signal?

`address_py` is clearly reverse-geocoded from lat/lon (37.2% of values share zero tokens with the
facility name; 117 name a blood bank; some are as short as `'park 4, India'` and
`'Uttar Pradesh, India'`). Its format — repeated street segments, e.g.
`"...Lady Curzon Rd, Tasker Town, Shivaji Nagar, 560001, Opposite Bowring Hospital, Lady Curzon Rd,
Tasker Town, Shivaji Nagar, Bangalore, Karnataka, India"` — looks like assembled geocoder address
components, not a raw formatted_address.

**Ask:** which library/API (geopy+Nominatim? Google? MapMyIndia?) and does the original run still
have the response payload? A geocoder `location_type` / `place_id` / match-confidence value would
turn `address_py` from unusable into a usable low-confidence enrichment, and would answer Q4 at the
same time.

---

## Q7 · Should `Trust`, `Society` and `Govt-Society` collapse, and to what?

`Type` value counts (n=648): `Govt.` 337, `Trust` 204, `Private` 69, `Society` 29,
`Govt-Society` 9. This is a finer ownership split than most Indian health-facility datasets carry
(which typically offer only Public/Private).

`Govt-Society` (9 rows) is genuinely ambiguous — it reads like a PPP or a government-funded
autonomous society, and the choice between `PUBLIC` and `PPP` changes public/private counts.

**Ask:** what is the target `facility_ownership_raw` enum for the canonical table? If it is binary,
Trust/Society/Private all become `PRIVATE` and the distinction is lost — confirm that is acceptable
before the harmonizer throws it away.

---

## Q8 · How should a medical college relate to its attached hospital in the canonical table?

`No. of beds in attached Hospital` is populated for 468 rows (median 750 beds). Those attached
teaching hospitals are real facilities, frequently share a name and campus with the college, and
will very likely appear as separate rows in the hospital-oriented datasets.

Three incompatible policies:
1. one canonical entity per college, with `bed_count` as an attribute (what this file implies);
2. two entities (college + hospital) linked by a `parent_facility_id`;
3. one entity, where the college row and the hospital row from another dataset are *merged*.

Each produces a different count of "facilities" and a different answer to "how many beds does X
have". **Ask:** which policy? This is a schema decision, not a data question, and it must be made
before NHP is merged — it is the only dataset in the set where the distinction arises.

---

## Q9 · Is `City` meant to be a district, and do we have a city→district lookup?

There is no district column and no LGD code anywhere in this file. `City` is free-text with 429
distinct values, and is contaminated on ~14 rows (6 hold the facility name, 8 hold a state name —
see `issues.md` S2-4).

The expected blocking key is `(name, geo, district)`. This dataset cannot supply `district` at all.

**Ask:** is there a canonical Indian city/town → LGD district crosswalk available to this project?
If yes, `City` becomes a usable district proxy for ~633 rows (647 populated minus the 14 contaminated). If no, NHP must be blocked on
`(name, geo)` / `(name, state, pincode)` and will be inconsistent with datasets blocked on district.

---

## Q10 · Are the 5 zero `Admission Intake` rows missing data or genuinely non-admitting?

```
S.No 62  Radha Devi Jageshwari Memorial Medical College and Hospital  Bihar / Private
S.No 211 Sambharam Institute of Medical Sciences & Research           Karnataka / Trust
S.No 292 ACPM Medical College                                         Maharashtra / Trust
S.No 532 TRR Institute of Medical Sciences                            Telangana / Private
S.No 588 Major S D Singh Medical College and Hospital, Fathehgarh     UP / Trust  (beds also 0)
```
All five are private/trust colleges. A zero intake could plausibly mean "NMC admission ban that
year" (which does happen to private colleges) rather than "value missing" — the two readings are
observationally identical here.

`field_map.yaml` currently specifies `0 -> NULL`. If any of these were genuinely suspended, that
coercion destroys a real fact.

**Ask:** cross-check against the NMC list of colleges with suspended admissions for the relevant
year. If a suspension is confirmed, we need a `record_status` value rather than a NULL intake.
