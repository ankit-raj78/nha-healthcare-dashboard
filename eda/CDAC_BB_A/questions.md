# CDAC_BB_A — open questions for a human or an external source

Each item states what I could not determine from the file, what I checked, and what specific
answer would unblock the harmonisation step.

---

## Q-1 · What is the actual snapshot date of this scrape?

**What I checked:** there is no date column, no `record_status`, and no version marker anywhere in
the 12 columns. The filename encodes `16_MAY` (no year); the filesystem mtime is 2025-06-20. The
*content* must post-date mid-2022, because it uses the Andhra Pradesh districts created in the
April-2022 reorganisation (`Bapatla`, `Palnadu`, `NTR`, `Konaseema`, `Eluru`, `Kakinada`,
`Anakapalli`, `Alluri Sitharama Raju`, `Annamayya`, `Nandyal`, `Sri Sathya Sai`,
`Parvathipuram Manyam`, `Tirupati`) in the `District` column while `dist_name` still carries the
pre-2022 names.

**What I need:** the date the e-RaktKosh portal was scraped. Without it, `source_snapshot_date`
is a guess and cross-dataset recency arbitration (which of ten sources wins on a conflicting
field?) has no basis for this dataset.

---

## Q-2 · The file is four concatenated batches. What are they?

**What I found:** `State` is alphabetically sorted, but the sort restarts at row indices
**4740, 5469 and 5645**. So the file is at least four blocks appended in sequence, not one pull.
Block boundaries are identical in `CDAC_BB_B`. The last two blocks (rows 5469+) also behave
differently from the first two: that is exactly where `new_longitude`/`new_latitude` become
axis-transposed, and where the two files disagree about which of two candidate geocodes belongs
in `Latitude`/`Longitude` (see `RECONCILIATION.md` §7–8).

**What I need:** what each block is — separate scrape dates? separate states batch? a manual
"newly licensed centres" addition? If the blocks have different dates, `source_snapshot_date`
should be per-block, not per-file, and the `new_*` transposition is a per-block processing bug
that may have other per-block effects I could not detect.

---

## Q-3 · What produced `new_latitude` / `new_longitude`, and against what input?

**What I checked:** these are clearly a geocoding pass, not portal data — they are absent from any
portal schema I can infer, 344 rows (6.1%) land outside India in either axis order, and one bogus
pair (`8.804821 / 61.24833`, Arabian Sea) repeats on 35 rows, which is the signature of a
geocoder's no-result fallback. I am confident enough to recommend dropping them.

**What I need, only if we ever want to salvage them:** which geocoder, and was it fed the
`Address` string or the `Name`? The 344 failures cluster on rows whose `Address` is the
placeholder `NA, <place>, Dist. <X>`, which would confirm the input was `Address` — but I could
not verify the geocoder itself. Also: was the transposition for rows 5469+ introduced by the
geocoder or by a later manual paste?

---

## Q-4 · Rows 1977/1978 — `Holy Cross Hospital`, Kollam: `Private` or `Charitable/Vol`?

Two rows, same `Name`, same `Address` (`Kottiyam, Kollam, Dist. Kollam`), same coordinate
(`8.865947 / 76.67086`), but:

| row | `Category` | `Phone` |
|---|---|---|
| 1977 | `Private` | null |
| 1978 | `Charitable/Vol` | `9.40E+09` |

**What I need:** the correct ownership class. This is the only conflicting-value duplicate in the
file, so it is cheap to resolve by hand, but I will not pick one silently — `Category` is the
dataset's only clean coded field and a wrong value here poisons an otherwise 100%-reliable column.
(The same conflict is present in `CDAC_BB_B` at the same indices, so the other file is not a
tiebreaker.)

---

## Q-5 · Is `Category = "Red Cross"` an ownership class or a brand?

`Category` has exactly four values: `Govt.` (2,768), `Private` (1,621), `Charitable/Vol` (1,190),
`Red Cross` (100). The first three are an ownership axis. `Red Cross` is an organisation — and
93 rows have "Red Cross" in the `Name` while only 100 rows have the category, so the two do not
line up exactly.

**What I need:** is `Red Cross` meant as a subtype of `Charitable/Vol` (in which case the
canonical `facility_ownership_raw` should be 3-valued with a separate operator field), or is it a
genuine fourth class in the source portal's own taxonomy? This determines whether
"how many charitable blood banks are there" returns 1,190 or 1,290.

---

## Q-6 · What is the difference between `BSU` and `BSC` in `Name`?

1,448 rows contain the token `BSU` and 107 contain `BSC`. I am confident `BSU` = Blood Storage
Unit (1,435 of the 1,443 are `Category = Govt.`, and names like `CHC, Khambhat BSU`,
`SDH Kaij BSU`, `Balaram SM SGH BSU` describe hospital annexes). `BSC` appears in names like
`BSC-DHONE BSU`, `BSC - BUDITHI BSU`, `BSC-RAJAMPET BSU` — often **alongside** `BSU`, which rules
out "Blood Storage Centre" as a synonym.

**What I need:** the expansion of `BSC`, and whether a `BSC-X BSU` is one facility or a BSU
operated by a BSC. Also, is there an official e-RaktKosh field that distinguishes
centre / storage unit / component-separation unit, so we do not have to infer subtype from a
name substring?

---

## Q-7 · Are the other name-embedded tokens a real vocabulary, and what are their expansions?

Counts of tokens found inside `Name`: `BSU` 1448, `CHC` 433, `SDH` 125, `BSC` 107, `RH` 98,
`SGH` 13, `AIIMS` 13, `DHH` 9, `GH` 9, `MCH` 6, `ESI` 5, `IRCS` 7, `PHC` 3, `GMC` 1.

I can guess most (CHC = Community Health Centre, SDH = Sub-Divisional Hospital, DHH = District
Head-quarters Hospital, RH = Rural Hospital, PHC = Primary Health Centre, GH = General Hospital,
IRCS = Indian Red Cross Society, ESI = Employees' State Insurance) — but they are *guesses from
naming convention, not from a key*, and `SGH`, `MCH` and `GH` are genuinely ambiguous
(`MCH` = Maternal & Child Health? Medical College Hospital? `SGH` = Sub-Group Hospital? State
General Hospital?).

**What I need:** the official abbreviation list from NHM/e-RaktKosh. This is the codebook the
plan says we currently lack, and it is needed to populate `facility_type_raw` consistently with
the `PHC`/`CHC` datasets being profiled in parallel.

---

## Q-8 · Which district vintage should `district_raw` carry?

`District` and `dist_name` disagree on **702 rows**. The pattern is that `District` is the
current name and `dist_name` is the pre-reorganisation / older-LGD name
(`Bapatla` vs `Guntur`, `Kakinada` vs `East Godavari`, `Gurgaon` vs `Gurugram`,
`Mysore` vs `Mysuru`, `Khargone (West Nimar)` vs `West Nimar`). But it is not a clean rule:
row 3129 has `District = "Sahibzada Ajit Singh Nagar"` and `dist_name = "Shahid Bhagat Singh Nagar"`,
which are **two different Punjab districts**, not two names for one; row 4355 has
`District = "Rangareddy"` and `dist_name = "Kamareddy"`, likewise two different Telangana districts;
row 3823 has `District = "Tirupattur"` and `dist_name = "Tiruppur"`, also two different Tamil Nadu
districts.

**What I need:** (a) which vintage of LGD codes the canonical database will key on, and (b) a
human decision on the handful of rows where the two columns name genuinely different districts —
those are data errors, not renames, and I could not determine which one is right.

---

## Q-9 · Are the 5 Sikkim rows really the whole of Sikkim?

`SIKKIM` has 5 rows: Central Referral Hospital, STNM Hospital (Gangtok), District Hospital
Geyzing, District Hospital Singtam, Namchi District Blood Centre. That is plausible for a small
state but I have no way to verify completeness from inside the file.

This matters more than it looks: `CDAC_BB_B` labels these same five rows `Rajasthan`, so if this
file's roster is also incomplete for small states, the error is systematic upstream rather than a
one-off paste mistake. **Needed:** the e-RaktKosh count of licensed blood centres in Sikkim,
Lakshadweep (1 row), Dadra & Nagar Haveli (1 row) and Andaman & Nicobar (2 rows) as a coverage
check.

---

## Q-10 · Are the 1,030 repeated coordinates deliberate town centroids?

18.1% of rows share their exact `Latitude`/`Longitude` with at least one other row —
`12.9716, 77.59456` (central Bengaluru) on 13 rows, `8.548821, 77.65361` on 14, and so on. I can
detect this but cannot tell whether the portal deliberately publishes a town centroid when the
building location is unknown, or whether a spreadsheet fill-down created it.

**What I need:** confirmation of which. If it is deliberate, we should set
`geo_accuracy = 'settlement'` on those rows rather than treating them as building-level points —
otherwise a "nearest blood bank" query will confidently return the wrong one of 13 facilities.
