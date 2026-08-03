# PMJAY — `18_MAY_23_SRK_PMJAY_validated_and_standardized.csv`

**11,284 rows × 78 columns.** UTF-8 with BOM, CRLF, no ragged rows, no embedded newlines.
`wc -l` = 11,285 = 1 header + 11,284 records. No gap to explain.

```python
pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
```

The naive `pd.read_csv(path)` also produces the correct 11284×78 shape — this file is
structurally clean. `dtype=str` still matters: column 65 (`Test extract`) throws a mixed-type
warning, and the pincode columns otherwise become floats.

## What this is

A snapshot of hospitals **empanelled under Ayushman Bharat PM-JAY** (the national health
insurance scheme), dated 2023-05-18 by its filename, prepared by an analyst with the initials
SRK. It is not a raw government export — it is the **output of a prior enrichment pipeline**,
and roughly half the columns are that pipeline's own working notes rather than source data.

You can read the pipeline's history straight off the schema. Someone started with a PMJAY portal
export (`Hospital Name`, `Hospital Address`, `Hospital Type`, specialty codes, `API Latitude/
Longitude`). They hand-cleaned the names, addresses and admin geo into a parallel `Manual *`
set. They then ran the addresses through a reverse geocoder — `address_py` is raw
OSM/Nominatim output (421 rows carry Devanagari, Urdu script or diacritics), from which
`Road`/`Locality`/`City`/`District`/`State`/`Zipcode` were parsed, `pincode_py` extracted, and
`Formatted Address` re-assembled. Separately they ran a Google Maps geocode
(`gmaps_Latitude/Longitude/Accuracy`). `Auto Score` is that pipeline's self-assessment: the
string similarity between `Manual Hospital Address` and `address_py`, correlation 0.812.

Admin vintage is pre-2020: `DAMAN AND DIU` and `DADRA AND NAGAR HAVELI` are separate states,
and Ladakh is absent.

## What it's good for

- **Admin geo is excellent.** `Manual state` is the cleanest column in the file: 36 distinct
  values, zero nulls, uniformly uppercase, all clean LGD-style names. `Manual District` is 622
  distinct with 37 nulls (0.33%).
- **Geocoding coverage is complete.** Every row has a usable point. `API Latitude/Longitude` is
  inside the India bbox on 11,281/11,284 rows (99.97%) with zero nulls, zero zeros and zero
  swapped pairs — unusually good for this class of dataset.
- **Entity resolution is viable.** Only 37 rows (0.33%) fail a `name + geo + district + state`
  blocking key, and all 37 fail solely on a missing district — they keep name, state and a valid
  point, so a relaxed key still reaches them.
- **Rich clinical detail.** 25 distinct specialty codes across empanelled and upgraded lists,
  with 98.65% of rows carrying at least one empanelled specialty (mean 7.9 codes per row).
- **Ownership** is populated on 97.6% of rows (Public 5,289 / Private For-Profit 5,052 /
  Private Not-for-Profit 672), and `is_RU` gives a confirmed urban(8,400)/rural(2,876) split.

## What it's bad for

- **No source-issued facility ID.** `Sr No` is unique but positional (1..11285 with 253 absent) —
  a row ordinal, not a key that survives a re-export. Nothing else in the file is unique.
- **No specialty codebook.** See below. The codes are opaque.
- **No facility type.** `Hospital Type` is ownership. PHC/CHC/district-hospital status exists
  only inside the name string.
- **No bed counts, no ABDM flag, no accreditation, no website, no sub-district/block/village,
  no LGD codes.** Bed counts appear only as text inside names (`100 Bed Combined Hospital`).
- **Contact data is unreliable** and partly corrupt — 94.29% of phones are valid mobiles, and
  433 email addresses are shared TPA/district inboxes rather than facility addresses.

## The specialty-code investigation — a negative result worth recording

The brief asked whether the text columns decode the numeric codes, which would hand us the
codebook for both PMJAY and NHA. **They do not.** `Specialities Empanelled` contains values like
`S1, M1, M7` — the same opaque tokens as the one-hot columns, never a human-readable specialty
name. There is no decoding anywhere in this file. The codebook must come from an external source.

Three real findings did come out of it:

1. **`S8` and `S9` have no one-hot columns.** The text vocabulary is 25 codes (M1–M8, M10, S1–S16;
   `M9` never occurs). The `_emp`/`_upg` families have only 23 each. Once `S8`/`S9` are removed
   from the text, the flags reconstruct it on **11,284/11,284 rows exactly** — for both families.
   So the flags are a perfect but *lossy* encoding, silently dropping specialties for 3,246 rows
   (28.77%) empanelled and 489 rows (4.33%) upgraded. **Parse the text columns; ignore the flags.**
2. **`Specialities_Upgraded_or_Empanelled` is corrupt.** It is `Empanelled + Upgraded`
   concatenated with *no delimiter* (11,141/11,284 exact), yielding `S1, M1, M7S5`, `S3-NA-`,
   `S1S1`. It is null on exactly the 143 rows where Empanelled is `-NA-` — a 100% rule. Drop it.
3. **Upgraded is not a subset of empanelled.** Only 79.74% of rows satisfy `_upg ⊆ _emp`; 144 rows
   have an upgraded specialty with no empanelled one. They are independent lists, not a hierarchy.

Also worth flagging for the codebook effort: `S10` and `S11` are **perfectly collinear** — they
co-occur on all 3,009 empanelled and all 423 upgraded rows, with zero exceptions. And `S9` never
appears without `S8`. Both patterns say something about what these codes mean; see `questions.md`.

## Three things that will bite someone who joins this naively

**1. `Manual Hospital Name` looks like the clean name and is the worse join key.**
It is title-cased and tidy, so it is the obvious pick. But the cleanup *stripped the location
qualifier* on 1,189 rows (10.54%) — `A G Eye Hospital, Puthur, Trichy TN.` became
`A G Eye Hospital`. That makes it strictly less distinctive: **13.20% of rows share a normalised
`Manual Hospital Name` versus 7.90% for `Hospital Name`**, and collisions within a
(state, district) block go from 91 rows to 310. Worst case, all 29 Surat urban PHCs collapse to
the single string `UPHC SURAT MUNICIPAL COMMISSION`. **Block on `Hospital Name`.**

**2. `gmaps_*` is not a better version of `API *` — it is a worse one, and it fails in a way
that looks plausible.** 38 gmaps points land outside India, in the US, Europe and Australia,
because the geocoder matched the facility *name*: `Boston Hospital & Research Institute` (Madhya
Pradesh) → Boston, Massachusetts. `American Oncology Institute` (Andhra Pradesh) → Ohio.
The two sources disagree by **over 500 km on 192 rows**, and `gmaps_Accuracy` does not warn you —
the `ROOFTOP` class, which sounds most precise, contains the single worst disagreement in the
file (14,706 km). Use `API Latitude/Longitude`; fall back to gmaps only for the 3 rows where API
is out of bbox and gmaps is not; never average them. Note also that `Auto Score` scores the
*geocode*, not any cross-dataset match — do not carry it forward as a match confidence.

**3. Sixty rows have latitude and longitude sitting in the email and phone columns.**
Rows 319–328 and beyond: `Hospital E-Mail = '11.506853'`, `Hospital Contact = '75.6249378'`.
On all 60, the email value is within one degree of that row's own `API Latitude` and the contact
value within one degree of its `API Longitude`. Everything else on those rows is correct — name,
address, specialties, state all fine — so this is not a row shift you would catch with a column-
count check, and a permissive email validator will happily ingest `11.506853` as a string. Filter
`^-?\d+\.\d+$` on both columns before touching them.

## Duplicates

**Zero exact duplicate rows**, with or without `Sr No`. But 23 near-duplicate pairs match on
normalised name plus API point at 4 decimal places (~11 m), and manual inspection confirms **22
are genuine re-entries of the same facility** — adjacent `Sr No`, identical email, near-identical
address. One is a false positive (two distinct Jodhpur satellite hospitals sharing a city-centroid
geocode). A visible sub-pattern: a batch of Tamil Nadu records was loaded twice, one copy carrying
a `", <City> TN."` suffix (`Erode Kidneys Center` / `Erode Kidneys Center, Erode TN.`).

The duplicates **disagree with each other on specialties** — row 6749 has
`M1, M7, S7, S5, S4, S1` and its twin 6750 has just `S4`. So deduplication here is a merge, not a
drop; picking either row arbitrarily loses clinical detail.

Beyond that, 2,967 rows share an API coordinate with another row — mostly legitimate
geocoder centroid fallback (143 rows sit on the single point `24.3454739,71.7622481`), not
duplication. Do not treat a shared point as evidence of a duplicate on its own.
