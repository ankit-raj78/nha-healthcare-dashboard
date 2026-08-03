# CGHS — open questions

Things I could not determine from the file itself. Ordered by how much they block the harmonization.

---

## BLOCKING — needed before the specialty codebook can be built

### Q1. What do the 22 two-letter specialty codes mean?
`Specialities_Selected` uses this closed vocabulary on 1001 rows (968 alone, 33 alongside a literal `NA`):

`BM` (228 rows) · `ER` (154) · `IN` (50) · `MC` (341) · `MG` (562) · `MN` (257) · `MO` (268) · `MP` (369) · `MR` (98) · `SB` (533) · `SC` (91) · `SE` (494) · `SG` (531) · `SL` (288) · `SM` (376) · `SN` (396) · `SO` (467) · `SP` (349) · `SS` (234) · `ST` (124) · `SU` (471) · `SV` (197)

No expansion appears anywhere in the file. The `M*` / `S*` split plausibly means Medical / Surgical, and `SE` is the sole code on many eye hospitals (rows 1, 1584–1586 `Eye Q Vision`), `MO`/`MR` co-occur on cancer hospitals (rows 1117, 1929) — but these are guesses and I have not encoded them anywhere.
**Need:** the CGHS empanelment application form or the CGHS speciality master that this dropdown came from, for 2023 or earlier.

### Q2. What do the 24 `M#`/`S#` specialty codes mean, and are they the same taxonomy as Q1?
`M1`–`M8` and `S1`–`S16` are used by 745 rows and **never co-occur with the two-letter codes in the same row**. Counts: `M1` 336 rows, `M2` 279, `M7` 326, `S3` 406, `S8` 252, `S16` 235, down to `M8` on 4 rows.

Three sub-questions, all of which change how the codebook is modelled:
1. Are these the **same 22 specialties renumbered**, or a different (larger/finer) taxonomy? 22 vs 24 codes is suggestive but not proof.
2. If they are the same, is there a published crosswalk (`SE ↔ S3`, etc.)?
3. Is the split a **form vintage** (older applications numbered, newer lettered, or vice versa)? The distribution is state-skewed — 204 of the 303 Delhi rows with specialties use the numeric family while 299 of the 316 such UP rows use the two-letter family — which looks like different CGHS regional offices on different form versions, but I cannot date it because both date columns are blank.

**Need:** confirmation from CGHS, or the same registry pulled at two different dates so the vintages can be separated.

### Q3. What does the specialty token `NA` mean on 33 rows?
It appears mid-list among real two-letter codes, e.g. row 612 `BM,ER,IN,MC,MG,MN,MO,MP,NA,SB,SC,SE,SG,SN,SO,SP,SS,ST,SU,SV,` and row 1117 `MO,MR,NA,SC,SM,`. It is alphabetically positioned, so it was sorted along with the real codes — meaning it may be a **legitimate code that happens to spell NA** (e.g. Neonatology / Nuclear medicine / Anaesthesia) rather than a null sentinel. I have treated it as a sentinel in `field_map.yaml`; if it is a real specialty, 33 rows lose a specialty.
**Need:** same source as Q1.

---

## BLOCKING — needed before `Hospital_Id` can be parsed for geography

### Q4. Is the digit block inside `Hospital_Id` an LGD state code or a CGHS city/zone code?
`HOSP<digits><letter><serial>`. The digits match LGD/Census-2011 state codes on 24 of the 26 observed values (3=Punjab, 7=Delhi, 9=UP, 19=West Bengal, 23=MP, 27=Maharashtra, 36=Telangana …), which is far too clean to be coincidence. But two values break the reading:

- **code 4** (LGD = Chandigarh) is carried by 17 rows whose districts are **Amritsar, Jalandhar and S.A.S Nagar** and whose `State` is PUNJAB (rows 1259–1275). Either these are Chandigarh-zone administered Punjab facilities, or code 4 does not mean Chandigarh here.
- **code 37** (LGD = Ladakh) is carried by a single **Delhi** row (row 113, `HOSP37P72508 KUKREJA HOSPITAL & HEART CENTER PVT LTD`, geocoded to Mayur Vihar, East Delhi).

If it is an LGD state code we get a free `state_lgd_code` for 1901 rows. If it is a CGHS *city/zone* code that merely happens to align with LGD, deriving `state_lgd_code` from it is wrong.
**Need:** the CGHS `Hospital_Id` allocation scheme, or a list of CGHS cities/zones with their numeric codes.

### Q5. Do `G` / `P` / `T` in `Hospital_Id` mean Government / Private / Trust?
Cross-tab against `Hospital_Type` (non-null only): `G` → Public 29, Private 6; `P` → Private 1426, Public 3; `T` → all 3 rows have `Hospital_Type` null. The three `T` rows are `Smt. S.M.S. Multispeciality hospital`, `Sardar Vallabhbhai Patel Institute of Medical Sciences & Research` and `KANORIA HOSPITAL & RESEARCH CENTRE` (all Gujarat, all trust-sounding, rows 760–762).
The reading is consistent but not proven, and the 8 disagreements with `Hospital_Type` mean one of the two sources is wrong on those rows.
**Need:** confirmation of the letter semantics, and which of the two fields is authoritative when they disagree.

### Q6. What does the `LAB` prefix imply about scope of empanelment?
81 rows are `LAB…` (Dr Lal Path Labs, Metropolis, Aarthi Scans, SRL, Krsnaa …) and 80 of the 81 have `Hospital_Type` null and `Specialities_Selected` null. Are diagnostic centres empanelled under a different CGHS rate schedule with no specialty concept at all, or is the specialty data simply not captured for them? This determines whether "null specialties" means "none" or "unknown" for these rows.
**Need:** CGHS diagnostic-centre empanelment rules.

---

## IMPORTANT — semantic ambiguity that affects the canonical model

### Q7. `Empanelment_Type` and `OnBoarded_For_Convergence_Scheme` contradict each other — which is authoritative?
1013 rows say `Only CGHS` **and** `OnBoarded = Yes`; 67 of the 69 `PMJAY and CGHS` rows say `OnBoarded = No`. The two columns are close to anti-correlated. Three readings are possible and the data cannot separate them:
1. They describe different points in time (`Empanelment_Type` = at empanelment, `OnBoarded` = current convergence status).
2. `OnBoarded` means "eligible for / invited to" the convergence scheme, not "participating in" it.
3. One of the columns is populated from a broken join upstream.

Whichever it is decides whether the canonical record should say a facility is PMJAY-empanelled. I have kept both as separate facts rather than pick.
**Need:** the CGHS/NHA definition of "OnBoarded For Convergence Scheme", and the as-of date for each column.

### Q8. What is the real snapshot date?
Both `Submitted_Date` and `Status_Updated_Date` are the constant literal `-NA` on all 1983 rows — they were blanked before export, not merely empty. The filename says `18_SEPTEMBER_23`. Was the extract actually taken on 2023-09-18, and were the date columns intentionally stripped (privacy? a broken export?) or were they empty in the source system too?
Without this, cross-dataset conflict resolution ("which source is more recent?") has nothing to work with for CGHS.
**Need:** whoever produced the file, or a re-pull with the date columns intact.

### Q9. Why are 108 upstream rows missing, and were they excluded on purpose?
`Unnamed: 0` is monotonic `0..2090` with 108 gaps (first at 6, 46, 54, 93, 99, 133, 159, 370 …). The upstream frame had 2091 rows; 1983 survived — a 5.2% loss. Combined with `Application_Status` being constant `"Hospital Approved for Empanelment"`, the most likely story is that the 108 were non-approved applications filtered out. But it could equally be geocoding failures dropped by the `_py` pipeline, which would bias the surviving set toward geocodable (i.e. urban, well-named) facilities.
**Need:** the upstream script, or the 2091-row file.

---

## MINOR — would improve the profile but does not block anything

### Q10. What exactly is `Monge Elkan Distance`?
It is the one similarity column I could not reproduce. Values span 0.002182–0.013408, two orders of magnitude below the [0,1] range a real Monge-Elkan similarity occupies, and it correlates **−0.63 with `len(Address)`** — so it looks like a Monge-Elkan score divided by a length. I tried 54 combinations (3 tokenizers × 3 inner similarities × 6 divisors) and got zero exact rows; the best fit was comma-token Jaro Monge-Elkan divided by `len(Address)` at r = 0.81. It also carries the *most* (still weak) signal of the eight columns: AUC 0.690 against "does `address_py` mention the state".
Since `Auto Score` weights it at 0.616 — by far the largest weight — knowing what it actually is would explain what `Auto Score` was optimizing. **This is curiosity only; all eight columns are dropped regardless.**
**Need:** the `py_stringmatching` / custom scoring script that produced columns 19–26.

### Q11. What was `Auto Score` used for, and was there a threshold?
It is exactly `0.1867386636·Levenshtein + 0.1975256764·JaroWinkler + 0.6157356594·(MongeElkan×10) + 0.4287057853` (R² = 1.0, max residual 9.0e-10; the three weights sum to 1.000000, but the additive 0.4287 constant means it is *not* a plain weighted average). The weights are not round numbers — they look fitted, not hand-chosen, which suggests a regression against a hand-labelled set that is not in this file. Its range is a narrow [0.5351, 0.7189] and no row is filtered by it (`Application_Status` is constant).
Knowing the threshold and the labels would tell us whether *any* of these rows were manually verified — which would be genuinely valuable ground truth for cross-dataset ER.
**Need:** the pipeline author's notes or the labelled training set.

### Q12. Which geocoding service produced `Latitude`/`Longitude`/`address_py`, and when?
`address_py` is OSM/Nominatim-formatted (`…, <X> District, <State>, <PIN>, India`), but I cannot tell whether it was Nominatim, geopy over Nominatim, or a commercial API with OSM-style output. The date matters because the geocode is demonstrably **newer** than the registry: all **40** rows whose `District` is the pre-2018 name `ALLAHABAD` have an `address_py` that says `Prayagraj District` (rows 1444, 1448, 1456 …), and rows 3–4 resolve to `Palnadu District`, an Andhra district created in 2022. So the two geographies in this file are from different eras and must not be cross-validated against each other.
**Need:** the geocoding script and its run date.

### Q13. Are the 3 Puducherry-named Tamil Nadu rows and the 1 Ranga Reddy Andhra Pradesh row genuine, or data-entry errors?
Rows 1322–1324 (`PIMS, Pondicherry TN.`, `Aravind Eye Hospital, Pondicherry TN.`, `Aravind Eye Hospital, Pondicherry DC.`) carry `District = CUDDALORE`, `State = TAMIL NADU`, and `Hospital_Id` state code 33 — but the file separately has 5 rows correctly filed under `PUDUCHERRY` (state code 34). Row 91 has `District = RANGA REDDY` under `State = ANDHRA PRADESH` while the other 14 Ranga Reddy rows are Telangana.
Either these facilities are administered by the Tamil Nadu / Andhra Pradesh CGHS office regardless of physical location, or they are simply mis-keyed. It matters because state is part of the blocking key.
**Need:** a human to check 4 rows.
