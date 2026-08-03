# PMGSY — open questions

Things I could not determine from the file alone. Each names what I need and from whom.

---

## Q1 — What code space is `HAB_CODE`, and is there a public master to decode it?

**What I know:** 12,092 distinct all-numeric values, 3–7 digits, range `349` … `1429221`. It is 1:1 with
a habitation — 0 codes span more than one `STATE_NAME`, `DISTRICT_NAME` or `HABITATION_NAME`. The code
space is *not* partitioned by state: e.g. Haryana's minimum is `349` and Bihar's is `446`, while
Ladakh's range is `1393033`–`1414251` and Telangana's is `1116814`–`1383322`, so low codes and high
codes are interleaved across states. That pattern looks like a global auto-increment assigned as
habitations were registered, with the newer states/UTs (Ladakh, Telangana, Puducherry) getting only
high codes.

**What I need:** confirmation from the PMGSY/OMMAS owner that this is the OMMAS `habitation_id`, plus
the habitation master table (code → state/district/block/habitation, LGD village code). Without it we
cannot (a) join PMGSY rows to LGD village codes, (b) tell whether the 3-digit codes are genuine or
truncated leading zeros. **Are `349` and `0000349` the same habitation?** If the codes should be
zero-padded to a fixed width, ingesting them as bare strings will break the future join.

**Why it matters:** `habitation_code` is the only external identifier in this dataset. It is our sole
route to LGD codes for `state_lgd_code` / `district_lgd_code`.

---

## Q2 — What produced `Postcode_py` on the 2,396 rows where the geocoder did not return one?

**What I know:** `address_py` is a reverse geocode of `(LATITUDE, LONGITUDE)` and contains a 6-digit
token on 11,304 rows (82.51%); on all 11,304 it equals `Postcode_py` exactly. But `Postcode_py` is
100% populated. So 2,396 pincodes came from a second, undocumented step — and 443 of them are
inconsistent with the pincodes seen elsewhere in the same district (control: 0/11,304 corroborated rows
fail the same test). Examples: Sr. No. 5 Visakhapatnam → `515301` (an Anantapur code); Sr. No. 42
Guntur → `535204` (a Vizianagaram code).

**What I need:** from whoever ran the `_py` geocoding pass — what was the fallback? A nearest-pincode
lookup? A second geocoding provider? A district-level default? A join to some pincode-centroid table?
Depending on the answer these 2,396 pincodes are either "approximately right, use with a confidence
flag" or "fabricated, drop entirely". I have flagged them rather than choosing.

**Also needed:** which geocoder, run on what date, at what zoom/precision? The output format
(`"<road>, <locality>, <sub-district>, <X> District, <State>, <pincode>, India"`, occasional
Devanagari/Chinese/Urdu names) reads like **Nominatim/OSM**, but that is an inference from the string
shape, not a fact. It matters because it determines how much we can trust `address_py` as an
independent district signal in Q3.

---

## Q3 — Are the source `DISTRICT_NAME` values wrong, or just stale?

**What I know:** the geocoder's district disagrees with `DISTRICT_NAME` on 2,871 of 13,622 comparable
rows (21.5%). Most are clearly the same district under a different spelling/vintage
(`Jalor`↔`Jalore`, `Belgaum`↔`Belagavi`, `Gurgaon`↔`Gurugram`, `Nowgaon`↔`Nagaon`). But some are real
boundary changes: Andhra Pradesh's 2022 district reorganisation means `DISTRICT_NAME='Guntur'` +
`address_py='… Palnadu District …'` is a *correct source value* against a *newer geocode*.

**What I need:** a decision from the project owner — **which district vintage is canonical for the
merged database?** Pre-2022 (matching the 2019 PMGSY collection) or current LGD? PMGSY's values are
2019-vintage; other datasets in this project were collected in 2022–2025 and will carry the new
districts. If we normalise everything to current LGD we need the AP/Telangana/UP district-split
crosswalks, which we do not currently have.

---

## Q4 — Are the 16 anomalous Tamil Nadu dates a dd/mm swap?

**What I know:** the file's mass is Aug–Dec 2019 (72.83%). Sixteen rows parse to Jan–May 2019 under
`%d-%b-%y`, and **all sixteen are Tamil Nadu, all have day ≤ 12 and month ≤ 5**, and all sit in the
same `Sr. No. ` block (9176–9598) as the 63 rows with a *null* `FILE_UPLOAD_DATE` (also all Tamil
Nadu). Across the whole file 8,598 rows have day > 12, so "day ≤ 12 on all 16 outliers" is not chance.
`09-May-19` reinterpreted as `05-Sep-19` lands squarely in the Tamil Nadu September cluster.

**What I need:** confirmation from the data owner that the Tamil Nadu block was ingested through a
different path (which would also explain the 63 nulls). I have **not** applied the swap — flipping
day/month on 16 rows on a hunch is exactly the kind of silent decision that poisons a provenance table.
They are flagged `date_suspect` in `issues.md` S2-6.

---

## Q5 — Are the 15 veterinary facilities in scope?

**What I know:** 15 rows are unambiguously animal-health facilities — Sr. No. 15
`Govt Veterinary Hospital`, 201 `veterinary  hospital`, 1811, 3056, 4600 `Animal husbandry`, 5846
`veterinary`, 6544, 6881 and 7 more. All carry
`MASTER_FACILITY_CATEGORY_NAME = 'Medical'` and a `SUB_CATEGORY` of `Bedded Hospital` or
`Community Health Centre`, so PMGSY itself classified them as medical infrastructure.

**What I need:** a scope ruling. "Indian health facility" in this project's brief almost certainly means
human health, but PMGSY's own vocabulary does not distinguish. These are 15 rows out of 13,700 — the
cost of getting it wrong is small, but the rule must be written down once and applied to all ten
datasets, not decided per-dataset. Same question for the **478 AYUSH** rows
(ayurveda/homeopathy/unani/siddha) and the **90 medical/nursing college** rows, which I have kept.

---

## Q6 — Is `SUB_CATEGORY` genuinely only two-valued, or is this extract truncated?

**What I know:** `MASTER_FACILITY_CATEGORY_NAME` is constant `'Medical'` and `SUB_CATEGORY` has exactly
two values (`Bedded Hospital` 7,307, `Community Health Centre` 6,393). A "sub-category" with two values
under a category with one value is a suspiciously flat vocabulary for a national programme, especially
when the free-text names clearly contain PHCs, sub-centres, dispensaries, district hospitals and
medical colleges — none of which have their own sub-category code.

**What I need:** the full PMGSY facility-category codebook from OMMAS: the complete
`MASTER_FACILITY_CATEGORY_NAME` list (I expect Education / Transport / Marketing / etc. exist in the
unfiltered master) and the complete `SUB_CATEGORY` list under `Medical`. If `Medical` really only has
two sub-categories then the field is nearly useless and we should say so; if the extract dropped other
sub-categories (PHC, Sub-Centre, Dispensary, District Hospital) then **this file is a filtered subset
and its coverage claims are wrong** — we would be missing every PHC and sub-centre in rural India,
which materially changes what "PMGSY coverage" means downstream.

---

## Q7 — Why are Goa, Nagaland, Delhi and 5 UTs entirely absent?

**What I know:** 29 `STATE_NAME` values. Missing: Goa, Nagaland, Delhi, Chandigarh, Andaman & Nicobar,
Dadra & Nagar Haveli, Daman & Diu, Lakshadweep. Mizoram has 9 rows, Pondicherry 8, Sikkim 14,
Ladakh 15 — implausibly low for a facility census but plausible for a road-programme survey.

**What I need:** confirmation that this is a genuine programme-coverage boundary (PMGSY does not
operate in fully-urban UTs; Goa and Nagaland may have completed their PMGSY connectivity targets before
this survey) rather than an extraction filter or a lost file. If it is an extraction artefact there may
be more PMGSY rows we should be ingesting. This determines whether "absent from PMGSY" is meaningful
evidence about a facility or just missing data.

---

## Q8 — What does the filename mean, and is there a newer extract?

**What I know:** `21_JULY_23_SRK_PMGSY_validated_homogenized.csv`. By analogy with the other nine
filenames in this project, `21_JULY_23` is a 2023-07-21 processing date and `SRK` are someone's
initials. `validated_homogenized` implies a prior cleaning pipeline ran — which is consistent with the
`_py` geocoding columns and the duplicated "parsed" block, both of which are that pipeline's output,
not source data.

**What I need:** (a) what did `validated` and `homogenized` actually do — were rows dropped, were values
edited in place? The trailing-period and ` 1` numeric-suffix name variants at identical coordinates
(`issues.md` S2-8) look like a de-collision step from that pipeline, which means the pipeline *created*
apparent duplicates. (b) Does the raw pre-pipeline PMGSY extract still exist? It would be strictly
better input than this file, since we would drop 8 of 24 columns anyway. (c) Is there a post-2019
PMGSY facility extract? This data is 5–7 years old.
