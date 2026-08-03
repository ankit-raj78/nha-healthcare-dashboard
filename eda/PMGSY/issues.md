# PMGSY — data-quality issues

Source: `21_JULY_23_SRK_PMGSY_validated_homogenized.csv`, 13,700 logical rows × 24 cols.
Row references use the `Sr. No. ` value (1-based, identical to `df.index + 1` after the standard read).
Every count comes from `scripts/`.

Severity: **S1** breaks a join or silently loses/duplicates entities · **S2** materially degrades
matching or query results · **S3** cosmetic / cheap to fix.

---

## S1-1 — `HAB_CODE` is not a facility key, and looks exactly like one

- **Affects:** 1,016 codes covering 2,624 rows (19.2% of the file); max 48 rows on one code.
- **Evidence:** 12,092 distinct `HAB_CODE` over 13,700 rows. `HAB_CODE = 440318` (Jagatpur, Bareilly,
  Uttar Pradesh) carries 48 rows — Sr. No. 11379 `chanderlok hospital`, 11381 `medinova hospital`,
  11392 `khushlok hospital`, 11386 `sunnayan eye hospital`, … each with distinct coordinates
  (median pairwise separation 1,717 m, bbox ~5.8 km).
- **Why it bites:** it is the only column that *looks* like a source id. Deduplicating or joining on it
  collapses 13,700 facilities into 12,092 habitations, destroying 1,608 real entities.
- **Fix:** map `HAB_CODE` to a new canonical field `habitation_code` (provenance / geographic join
  only). Build the surrogate key as `'PMGSY:' || HAB_CODE || ':' || "Sr. No. "`. The composite
  `(HAB_CODE, MASTER_FACILITY_DESC, LATITUDE, LONGITUDE)` is verified unique over all 13,700 rows if a
  natural key is required.

## S1-2 — Eight of 24 columns are exact copies or a concatenation of other columns

- **Affects:** 100% of rows, 8 columns.
- **Evidence:** byte-identical on 13,700/13,700 rows: `Street/Locality`≡`ADDRESS`,
  `Habitation`≡`HABITATION_NAME`, `Block`≡`BLOCK_NAME`, `City/District`≡`DISTRICT_NAME`,
  `State`≡`STATE_NAME`, `Pincode`≡`Postcode_py`. `Hospital Name`≡`MASTER_FACILITY_DESC` on
  13,699/13,700 (see S3-1). `Formatted Address` is reproduced **byte-exactly on 13,700/13,700** by
  `join(", ", [Hospital Name, Street/Locality, Habitation, Block (omitted when
  lower(Block)==lower(Habitation)), City/District, State, Country, Pincode])` — verified in
  `scripts/06_final.py`.
- **Why it bites:** the parsed block looks like independent geocoder output and will be trusted as
  corroboration for the raw columns. It is not; it corroborates nothing. Any "concatenate all text for
  embedding / TF-IDF" step emits every fact 2–3×.
- **Fix:** drop `Hospital Name`, `Street/Locality`, `Habitation`, `Block`, `City/District`, `State`,
  `Pincode`, `Formatted Address`. Keep `ADDRESS`, `HABITATION_NAME`, `BLOCK_NAME`, `DISTRICT_NAME`,
  `STATE_NAME`, `Postcode_py`.

## S1-3 — ~30% of facility names are a bare facility-type word

- **Affects:** **4,046 rows (29.53%)** whose whole `MASTER_FACILITY_DESC` is a type token, using the
  24-token generic list in `scripts/05_deep.py` (this is the list behind
  `profile.json → er_readiness.unmatchable_row_pct`). A slightly wider list that also folds
  spacing/spelling variants gives 4,098 (29.91%) — take 4,046 as the conservative figure.
  Separately, 5,723 rows (41.77%) have ≤2 tokens.
- **Evidence (top values):** `CHC` 528, `community health center` 322, `Bedded Hospital` 291,
  `Community Health Centre` 260, `community health centre` 256, `hospital` 244, `bedded hospital` 238,
  `Dispensary` 201, `Community Health Center` 150, `chc` 144, `Hospital` 130, `medical` 99, `PHC` 38.
- **Concrete collision:** Sr. No. 8988 and 8989 are both `Dispensary`, both `HAB_CODE 520090`
  (Kashipura, Jaipur), **87 m apart**. Sr. No. 8861 and 8915 are both `CHC` in Dholpur, within 150 m.
- **Why it bites:** name-based blocking matches `CHC` in Rajasthan to `CHC` in Bihar. Name-based
  dedup either over-merges within-district or produces nothing.
- **Fix:** never use `facility_name_raw` as a blocking key for this dataset. Emit a
  `name_is_generic` boolean (test: normalised name ∈ the generic-token set in
  `scripts/05_deep.py`) so downstream can down-weight the name term to 0 for these 4,046 rows.

## S1-4 — 322 rows carry a literal newline inside a quoted field; `wc -l` over-counts by 1,197

- **Affects:** 322 rows × 3 columns (`ADDRESS`, `Street/Locality`, `Formatted Address`).
- **Evidence:** Sr. No. 56 `ADDRESS = 'Govt Hospital\nPunganur'`; Sr. No. 457
  `'Hawai\nAnjaw Dist\nArunachal Pradseh'`; Sr. No. 395 `'near panchayati office\n'`.
  1,197 embedded `\n` in total; `13,703 records + 1,197 = 14,900 physical lines`.
- **Why it bites:** any line-based tool (`wc`, `split`, `awk`, naive `readlines()`, a shell-based
  chunker) will shred these rows.
- **Fix:** always read with a real CSV parser. Normalise with
  `.str.replace(r"\s+", " ", regex=True).str.strip()` on ingest.

---

## S2-1 — `Postcode_py`/`Pincode` is 100% populated but only 82.51% is corroborated; 443 rows are wrong

- **Affects:** 2,396 rows (17.49%) uncorroborated; **443** of those demonstrably inconsistent.
- **Evidence:** `address_py` (the reverse geocode) contains a 6-digit token on 11,304 rows; on all
  11,304 it equals `Pincode` exactly (100% agreement). On the remaining 2,396 the pincode came from
  somewhere else. Testing those against the pincode 2-digit prefixes actually observed in the same
  state+district on corroborated rows: **443 fail**, while the corroborated control passes
  11,304/11,304 (100%).
  - Sr. No. 5 — Andhra Pradesh / **Visakhapatnam**, `Pincode = 515301` (a 515xxx Anantapur code);
    `address_py = "Anadapuram Road, Podugupalem, Chandaka, Anandapuram, Visakhapatnam District, Andhra Pradesh, India"`.
  - Sr. No. 15 — Andhra Pradesh / **Anantapur**, `Pincode = 533244` (533xxx is East Godavari).
  - Sr. No. 21 — Andhra Pradesh / **Prakasam**, `Pincode = 533106` (East Godavari again).
  - Sr. No. 42 — Andhra Pradesh / **Guntur**, `Pincode = 535204` (535xxx is Vizianagaram).
- **Note:** the crude state-first-digit test passes 13,672/13,700 (99.80%) and **does not catch this** —
  all the AP examples above start with `5`, which is "correct" for AP. Do not rely on it.
- **Fix:** emit `pincode_confidence = 'corroborated' | 'fallback'` derived from whether `address_py`
  echoes the same 6-digit token. Never block on pincode for this dataset.

## S2-2 — `SUB_CATEGORY` disagrees with the facility name on ~40% of CHC rows

- **Affects:** 2,546 of 6,393 `Community Health Centre` rows.
- **Evidence:** among rows labelled `Community Health Centre`, the most common names include
  `hospital` (89), `medical` (60), `Medical` (52), `PHC` (27). Conversely 49 of 7,307
  `Bedded Hospital` rows have a CHC/community-health token in the name.
  - Sr. No. 11453 — `Shri ram murti ismarak institute of medical sciences` (a tertiary teaching
    hospital) labelled `Community Health Centre`.
  - Sr. No. 11426 — `mental hospital` labelled `Bedded Hospital`.
  - Sr. No. 8111 — `school` labelled `Community Health Centre`.
- **Fix:** treat `SUB_CATEGORY` as a low-confidence prior. Derive `facility_type` primarily by parsing
  `MASTER_FACILITY_DESC`, using `SUB_CATEGORY` only as a tie-break.

## S2-3 — District names use pre-rename and misspelled forms; will not join to LGD

- **Affects:** 663 distinct districts; the geocoder disagrees with `DISTRICT_NAME` on 2,871 rows
  (`address_py` contains an `"<X> District"` token on 13,622 rows, matching `DISTRICT_NAME` on only
  10,751 = 78.47%).
- **Evidence (source → geocoded, count):** `Jalor`→`Jalore` 138 (e.g. Sr. No. 8260), `Sangali`→`Sangli`
  120, `Maharajganj`→`Mahrajganj` 111, `Lakhimpur-Kherii`→`Lakhimpur Kheri` 75,
  `Jhunjhunun`→`Jhunjhunu` 70, `G.B. Nagar`→`Gautam Buddha Nagar` 61,
  `Siddharathnagar`→`Siddharthnagar` 53, `Belgaum`→`Belagavi` 47, `Nowgaon`→`Nagaon` 45,
  `Bangalore R`→`Bengaluru Rural` 42, `Baramula`→`Baramulla` 39, `Ambedkarnagar`→`Ambedkar Nagar` 38,
  `Gurgaon`→`Gurugram` 37. Also `South 24-Parganas` vs `North 24 Parganas` — inconsistent hyphenation
  *within* this file.
- **Fix:** an LGD district alias table is mandatory before any district-level join or blocking.

## S2-4 — State names are non-LGD for 3 states

- **Affects:** `Tamilnadu` 457 rows, `Pondicherry` 8 rows, `Jammu And Kashmir` 230 rows.
- **Evidence:** the geocoder's own state token is `Tamil Nadu` on all 456 comparable rows and
  `Puducherry` on all 8 (e.g. Sr. No. 9152 `STATE_NAME='Tamilnadu'`,
  `address_py='… Dharmapuri District, Tamil Nadu, 636811, India'`). Overall geocoded-state agreement
  is 13,184/13,700 (96.23%); after correcting these three names it would be ~99.7%.
- **Also note:** 17 Karnataka rows and 5 more geocode to a *division* (`Bengaluru Division`,
  `Mysuru Division`) rather than a state — an OSM artefact, not a data error.
- **Fix:** `normalize_lgd(state_raw)`. Full 29-value list is in `profile.json → coded_vocabularies.STATE_NAME`.

## S2-5 — 63 rows have a null `FILE_UPLOAD_DATE`, all in Tamil Nadu

- **Affects:** 63 rows (0.46%), `Sr. No. ` 9152–9601, all `STATE_NAME='Tamilnadu'`
  (Salem 29, Dharmapuri 18, Krishnagiri 8, Karur 4, The Nilgiris 4).
- **Evidence:** Sr. No. 9152 `Govt Hospital Perumbalai`, 9164 `Dharan hospital`, 9165 `AVM Hospital`.
- **Fix:** leave null; do not impute. Flag `source_snapshot_date_missing`.

## S2-6 — 16 suspicious early dates, all Tamil Nadu, all day ≤ 12 (probable dd/mm swap)

- **Affects:** 16 rows, all `Tamilnadu`, all in the same `Sr. No. ` block (9176–9598) as S2-5.
- **Evidence:** the file's mass is Aug–Dec 2019 (72.83%), but these parse to Jan–May 2019:
  Sr. No. 9414 `09-Jan-19`, 9245 `10-Jan-19`, 9244/9324/9433/9554/9598 `11-Jan-19`, 9551 `11-Feb-19`,
  9545 `06-Apr-19`, 9509/9535 `09-Apr-19`, 9176/9232/9270/9371/9563 `09-May-19`. Every one has
  day ≤ 12 and month ≤ 5. Across the whole file 8,598 rows have day > 12, so day ≤ 12 on all 16
  outliers is not chance. `09-May-19` → `05-Sep-19` would land squarely in the Tamil Nadu Sept cluster.
- **Fix:** do not silently swap. Flag these 16 as `date_suspect` and raise with the data owner
  (see `questions.md`).

## S2-7 — 131 within-dataset near-duplicate row pairs

- **Affects:** 131 pairs at ≥0.85 name similarity within 150 m; 285 pairs at ≥0.70; 1,005 pairs within
  150 m in total. Exact duplicates: **0** (even ignoring `Sr. No. `).
- **Evidence:**
  - Sr. No. 466 and 470 — both `First Referral Unit Ruksin`, East Siang, Arunachal Pradesh.
  - Sr. No. 327 and 328 — both `Byrraju Foundation Hospital`, `HAB_CODE 581624`, West Godavari,
    coordinates 8.6 m apart. Only **two** pairs in the file share a byte-identical
    `Formatted Address`: this one, and Sr. No. 3468/3469 `comonity health center`, `HAB_CODE 674931`,
    Pashchimi Singhbhum (coordinates 47.6 m apart). Both are near-certain duplicate records.
  - Sr. No. 12373 `SABA HOSPITAL` / 12374 `saba hospital`, Azamgarh.
  - Sr. No. 4373 `Little flower mission hospital` / 5329 `LITTLE FLOWER MISSION HOSPITAL`, Kollam.
  - Sr. No. 12198 `Community health centre` / 12199 `Community health  centre`, Farrukhabad
    (differ only by a double space).
  - 29 rows share an **exact** (`LATITUDE`,`LONGITUDE`) pair with another row, e.g. Sr. No. 4165
    `Vivekananda Hospital` and 4166 `Government Hospital`, both `12.00083717, 76.39676417`, Mysore —
    genuinely two facilities or a copy-paste error, cannot be resolved from the file alone.
- **Fix:** run a same-district + ≤150 m + name-similarity dedup pass. Do **not** dedup on
  `(normalised name, district)` — that flags 3,066 pairs, almost all false positives created by the
  generic names of S1-3.

## S2-8 — 6 facility names carry a numeric disambiguation suffix from a prior pipeline

- **Affects:** 6 rows; collapsing the suffix merges 28 rows into an existing `(HAB_CODE, name)` group.
- **Evidence:** Sr. No. 1593 `community health centre 1` and 1594 `community health centre` are at
  **the same coordinate** (`26.2946078, 85.94641708`, KEOTI RANWAY, Darbhanga); likewise Sr. No. 1669
  `Community health centre 1` / 1668 `Community health centre` at `26.80024312, 84.61846231`; also
  `Govt Up swathya kendra 1` (Sr. No. 1875) / `Govt Up swathya kendra` (1876) at `23.58139, 81.70619833`;
  `Bedded Hospital 1`, `Samudaik Swastha Kendra, Riga 2`.
- **Also:** trailing-period variants at the identical coordinate — Sr. No. 1692 `Bedded hospital.` and
  1691 `Bedded hospital` at `25.66276208, 85.45373365`; Sr. No. 1431 `Bedded hospital.` / 1430
  `Bedded hospital` at `25.70584399, 85.53288209`; Sr. No. 1492 `Community health centre.` / 1491
  `Community health centre` at `25.74601764, 85.49423353`.
- **Fix:** these are almost certainly an upstream de-collision artefact, not two facilities. Strip
  trailing `[\s.]*\d{0,2}$` before matching, and merge same-coordinate pairs.

## S2-9 — `ADDRESS` is close to worthless as an address

- **Affects:** 8,343 rows (60.90%) are ≤12 characters; 5,362 (39.14%) are byte-identical to
  `HABITATION_NAME`; 1,499 are identical to `BLOCK_NAME`; only 224 rows contain any digit.
- **Evidence:** Sr. No. 1 `ADDRESS = 'chatrai'` (`HABITATION_NAME = 'Chatrai'`); Sr. No. 4
  `'chittoor district'`; Sr. No. 5 `'main Road side'`.
- **Fix:** map to `address_raw` but exclude it from address-similarity scoring. `address_py` is the
  better address string — but remember it is derived from the coordinate, so it must not be used to
  validate the coordinate.

---

## S3-1 — One row where `MASTER_FACILITY_DESC` ≠ `Hospital Name`

- Sr. No. 8: `MASTER_FACILITY_DESC = 'phcbededhospital'`, `Hospital Name = 'phc beded hospital'`.
  `Formatted Address` uses the spaced form. Prefer `Hospital Name` for this single row, or just
  normalise whitespace and accept the loss.

## S3-2 — Non-breaking spaces (U+00A0) leading 7 habitation values

- Sr. No. 7225 `'\xa0Mawdiang Diang'`, 7226 `'\xa0Kharang'`, 7227 `'\xa0Pynursla'` (all Meghalaya,
  East Khasi Hills). Propagates into `Habitation` and `Formatted Address` (8 rows affected there).
  One `ADDRESS` value too: `'\xa0Tamulbari T E Ghoramora'`.
- **Fix:** `.str.replace(" ", " ").str.strip()`.

## S3-3 — Untrimmed and double-spaced text

- 199 `ADDRESS` values are untrimmed (Sr. No. 395 `'near panchayati office\n'`, 572
  `'Fulkumri Dhubri Assam\n'`, 575 `'Chamata\n'`); 2 `MASTER_FACILITY_DESC`; 7 `HABITATION_NAME`.
- Double internal spaces: `MASTER_FACILITY_DESC` 297, `ADDRESS` 291, `HABITATION_NAME` 75,
  `BLOCK_NAME` 35, `Formatted Address` 645.
- **Fix:** `.str.replace(r"\s+", " ", regex=True).str.strip()` on every text column at ingest.

## S3-4 — 333 `address_py` values contain non-Latin script

- Sr. No. 209 `'करवदी, Ongole, Prakasam District, Andhra Pradesh, 523182, India'`; Sr. No. 561
  `'都登, Tuting, Tuting ADC, Upper Siang District, Arunachal Pradesh, 791105, India'`; Sr. No. 992
  `'اے ٹی روڈ, Rupai, Dett Rupai, Doom Dooma, Tinsukia District, Assam, 786153, India'`.
- Not an error — OSM local-language name tags leaking through the reverse geocoder. Flagged so nobody
  "fixes" it by stripping non-ASCII, which would also mangle legitimate content.

## S3-5 — 7 rows are not health facilities despite `MASTER_FACILITY_CATEGORY_NAME = 'Medical'`

The PMGSY school/road contamination risk is **mostly not present** — the category column is constant
`'Medical'` and there are 0 road/bridge rows — but a handful survive in the free text:

| Sr. No. | `MASTER_FACILITY_DESC` | `SUB_CATEGORY` | State / District |
|---|---|---|---|
| 2204 | `bank` | Community Health Centre | Gujarat / Sabarkantha |
| 2390 | `BOB BANK` | Bedded Hospital | Gujarat / Chhotaudepur |
| 6479 | `Bank` | Bedded Hospital | Maharashtra / Nanded |
| 8111 | `school` | Community Health Centre | Punjab / Kapurthala |
| 11128 | `MOHAL INTERNATIONAL SCHOOL` | Bedded Hospital | Uttar Pradesh / G.B. Nagar |
| 11699 | `anganwadi centre` | Community Health Centre | Uttar Pradesh / Kushinagar |
| 12547 | `Mamta memorial public school` | Bedded Hospital | Uttar Pradesh / Gorakhpur |

- **Adjacent, judgement-call:** 15 rows are **veterinary** facilities (Sr. No. 15
  `Govt Veterinary Hospital`, 201 `veterinary  hospital`, 1811, 3056, 4600 `Animal husbandry`, 5846
  `veterinary`, 6544, 6881 …) — animal health, not human health. 478 rows are **AYUSH**
  (ayurveda/homeopathy/unani/siddha) and 90 mention a **medical/nursing college** — these are
  legitimate health facilities but a different type; do not silently drop them.
- **Fix:** drop the 7 above; route the 15 veterinary rows by policy decision (see `questions.md`);
  keep AYUSH and colleges with a `facility_type` label.

## S3-6 — 93 facility names embed a personal name (`Dr <surname>`)

- 0.68% of rows, e.g. `Dr Das Hospital and Diagnostic Center`, `dr. ram krishna hospital`,
  `DR DHANI RAM BARUAH HEART INSTITUTE AND RESEARCH CENTRE`, `Dr Ravi Boro Civil Hospital Mushalpur`.
- These are business names, not personal records, so **no PII redaction is warranted**. Recorded here
  only so a blanket PII scanner's hits are already accounted for.
- **No phone numbers or email addresses exist anywhere in this file** (regex scan of all 24 columns
  returned 0 hits). There are no contact fields at all.

## S3-7 — `Country` and `MASTER_FACILITY_CATEGORY_NAME` are constant

- `Country = 'India'` ×13,700; `MASTER_FACILITY_CATEGORY_NAME = 'Medical'` ×13,700.
- Zero information within this file. Keep `MASTER_FACILITY_CATEGORY_NAME` only as provenance that the
  extract was pre-filtered to health infrastructure.
