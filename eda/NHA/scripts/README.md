# NHA profiling scripts

Run from the repo root (`/Users/ankitraj2/asar master data`) with `.venv/bin/python`, in
numeric order. Scripts 01–10 read the source CSV and write intermediates to
`intermediate/`; script 11 assembles `../profile.json` from them. Nothing writes to or
modifies the source CSV.

```bash
for s in eda/NHA/scripts/[01]*.py; do .venv/bin/python "$s"; done
```

| script | what it establishes |
|---|---|
| `01_load_and_shape.py` | byte-level facts (BOM, trailing newline), csv-module row/field counts vs `wc -l`, the correct read kwargs |
| `02_profile_columns.py` | per-column profile over all 323,460 rows, read as `str` so nothing is coerced |
| `03_families.py` | verifier columns, `Facility ID` uniqueness, state/district agreement, geo validity, `Google Maps Link` vs `Latitude`/`Longitude` |
| `04_specialties.py` | `M*/S*_emp` encoding, `merged_specialties` tokens, first-pass decode |
| `05_codebook_verify.py` | **the proof** — exact set-equality between each flag and a specialty token; S8/S9 and S10/S11 edge cases |
| `06_dupes_geo_er.py` | exact and near-duplicates, geo defects in detail, name/address profile, ER readiness |
| `07_dupe_anatomy.py` | what varies inside repeated-`Facility ID` groups; shared-coordinate fallback; test records |
| `08_the_24x7_artifact.py` | decisive test that the row fan-out is a `24/7` cross-product |
| `09_gaps.py` | residual dup IDs, coordinate precision, address structure, enum hygiene |
| `10_district_adjudication.py` | word-boundary adjudication of `District_name` vs `new_district_name`, per-state coverage |
| `11_build_profile_json.py` | assembles `../profile.json` (no CSV read) |

Note on 09 vs 10: `09_gaps.py` contains a district-vs-address substring test that is
**invalid** — `'una'` matches `'ARUNachal'`. `10_district_adjudication.py` redoes it with
word-boundary matching. The reported numbers come from 10; 09's
`district_mismatch_adjudication` block is retained only to show the superseded method.

Runtime: ~15 minutes total, dominated by 06 and 07. No sampling anywhere — every figure
covers all 323,460 rows.
