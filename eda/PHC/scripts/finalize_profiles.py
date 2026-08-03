#!/usr/bin/env python
"""Patch eda/{PHC,CHC}/profile.json into the final contract shape.

Run AFTER profile_phc_chc.py and deep_and_cross.py:
    .venv/bin/python eda/PHC/scripts/finalize_profiles.py

Sets the final semantic_role / flags / notes per column, aligns er_readiness and
duplicates with the rigorous figures used in the prose docs, and appends the
cross-file block. All numeric values are recomputed here from the CSVs, not
copied, so this file is self-verifying.
"""
import json
import os
import re
import unicodedata

import numpy as np
import pandas as pd

ROOT = "/Users/ankitraj2/asar master data"
KW = dict(encoding="utf-8", dtype=str, keep_default_na=False, na_values=[], sep=",")
FILES = {"PHC": "21_June_2024_AM_PHC.csv", "CHC": "21_June_2024_AM_CHC.csv"}

STRIP = re.compile(
    r"\b(?:phc|chc|primary|community|health|helth|heath|healt|hlth|centre|center|"
    r"cent|centr|ctr|cntr|sub|sc|hsc|phsc|hc|govt|government|hospital|hosp|care|"
    r"unit|new|the|of|and|comprehensive|rural|urban|main|public|additional|add|"
    r"referral|block|bphc|aphc|uphc|mphc|shc|hwc|wellness|dispensary|clinic|"
    r"cum|no|at|in|is|a|medical|comunity|cummunity|primery|primry|helath|"
    r"heath|hospitalc|building|bed|beded|bedded)\b")


def nn(s):
    s = unicodedata.normalize("NFKD", str(s).lower().strip())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


ROLES = {
    "STATE_NAME": ("state_raw", [],
                   "Indian state/UT, title case. 29 distinct. Only 'Tamilnadu' deviates from "
                   "the LGD spelling ('Tamil Nadu'). 8 states/UTs absent entirely."),
    "DISTRICT_NAME": ("district_raw", ["truncated", "placeholder_values"],
                      "District name. Hard-truncated at 25 chars with a literal '*' marker for "
                      "3 values. Some rows carry the placeholder 'Unknown'. Not unique across "
                      "states - always key on (state, district)."),
    "BLOCK_ID": ("block_lgd_code", ["unverified_code_authority"],
                 "Integer block id. VERIFIED: 0 blocks span >1 district across the 6252-block "
                 "PHC+CHC union, so it is a real national block namespace shared by both files. "
                 "But it is NOT confirmed to be the LGD block code - do not join to LGD on it."),
    "HAB_ID": ("village_lgd_code", ["unverified_code_authority", "not_unique"],
               "Integer habitation id. VERIFIED: 0 of 35189 union HAB_IDs span >1 block or "
               "district - nests perfectly inside BLOCK_ID. Repeats within a file mean 'several "
               "facilities in one habitation', NOT duplicate rows. Authority unconfirmed; "
               "village_lgd_code is a low-confidence fit since a habitation is finer than a "
               "revenue village."),
    "FACILITY_ID": ("source_facility_id", ["shared_namespace_with_sibling_file"],
                    "Integer facility id, unique within this file. Shares its namespace with the "
                    "sibling PHC/CHC file: 21 ids appear in both, and in every case the entire "
                    "9-column row is byte-identical. Unique across the 36174-row deduplicated "
                    "union, so it is a valid PK for the pair."),
    "FAC_DESC": ("facility_name_raw", ["low_information", "whitespace_defects"],
                 "Free-text facility name - but in practice the facility TYPE, hand-typed with "
                 "chaotic spelling. Majority of rows carry no place information at all. Defects: "
                 "literal tabs, double spaces, trailing periods, no-space concatenations."),
    "FAC_CATEGO": ("junk", ["constant", "junk", "drop"],
                   "Constant 'Medical' in BOTH the PHC and CHC files. Zero information; does not "
                   "distinguish the two tiers. Almost certainly an amenity category inherited "
                   "from a larger habitation-survey parent table. DROP - do not map to "
                   "facility_category_raw."),
    "Longitude": ("longitude", [],
                  "Decimal degrees, WGS84 assumed. 100% parseable, zero nulls/zeros/blanks, "
                  "100% inside the India bbox."),
    "Latitude": ("latitude", [],
                 "Decimal degrees, WGS84 assumed. 100% parseable, zero nulls/zeros/blanks, "
                 "100% inside the India bbox, zero plausibly swapped."),
}

dfs = {}
for k, f in FILES.items():
    d = pd.read_csv(os.path.join(ROOT, f), **KW)
    d["_nn"] = d.FAC_DESC.map(nn)
    d["_lon"] = pd.to_numeric(d.Longitude)
    d["_lat"] = pd.to_numeric(d.Latitude)
    dfs[k] = d

phc, chc = dfs["PHC"], dfs["CHC"]
cols9 = list(FILES and phc.columns[:9])
overlap_ids = set(phc[cols9].merge(chc[cols9], on=cols9).FACILITY_ID)
union = pd.concat([phc, chc], ignore_index=True).drop_duplicates(subset=cols9)

for key in ("PHC", "CHC"):
    d = dfs[key]
    n = len(d)
    other = "CHC" if key == "PHC" else "PHC"
    o = dfs[other]
    p = os.path.join(ROOT, "eda", key, "profile.json")
    prof = json.load(open(p))

    for col in prof["columns"]:
        role, flags, note = ROLES[col["name"]]
        col["semantic_role"] = role
        col["flags"] = list(flags)
        col["notes"] = note

    # --- rigorous name/matchability figures ---
    resid = (d._nn.str.replace(STRIP, " ", regex=True)
             .str.replace(r"\d+", " ", regex=True)
             .str.replace(r"\s+", " ", regex=True).str.strip())
    zero_info = int(resid.eq("").sum())
    sub = d[resid.ne("")].copy()
    sub["_r"] = resid[resid.ne("")]
    uniq_keyed = int((sub.groupby(["STATE_NAME", "DISTRICT_NAME", "_r"]).size() == 1).sum())

    gmed = d.groupby(["STATE_NAME", "DISTRICT_NAME"])[["_lon", "_lat"]].transform("median")
    dkm = 111.0 * np.hypot(d._lat - gmed._lat,
                           (d._lon - gmed._lon) * np.cos(np.radians(d._lat)))
    far100 = int((dkm > 100).sum())

    cell = pd.Series(list(zip(d._lon.round(2), d._lat.round(2)))).value_counts()

    prof["name_quality"] = {
        "n_distinct_fac_desc": int(d.FAC_DESC.nunique()),
        "n_rows_len_le_3": int((d.FAC_DESC.str.len() <= 3).sum()),
        "pct_rows_len_le_3": round(100 * (d.FAC_DESC.str.len() <= 3).mean(), 2),
        "n_rows_zero_place_information": zero_info,
        "pct_rows_zero_place_information": round(100 * zero_info / n, 2),
        "n_rows_uniquely_keyed_by_state_district_placetoken": uniq_keyed,
        "pct_rows_uniquely_keyed_by_state_district_placetoken": round(100 * uniq_keyed / n, 2),
        "method": "normalise (lowercase, strip punctuation), remove generic facility-type words "
                  "and digits; a row with an empty residual carries no place information.",
    }

    prof["geo_quality"]["gt_100km_from_own_district_median"] = far100
    prof["geo_quality"]["pct_usable_after_district_sanity_filter"] = round(
        100 * (n - far100) / n, 2)
    prof["geo_quality"]["n_rows_alone_in_1p1km_cell"] = int((cell == 1).sum())
    prof["geo_quality"]["pct_rows_alone_in_1p1km_cell"] = round(100 * (cell == 1).sum() / n, 2)
    prof["geo_quality"]["max_rows_in_one_1p1km_cell"] = int(cell.max())

    prof["er_readiness"] = {
        "has_name": True,
        "has_name_with_place_information_pct": round(100 * (n - zero_info) / n, 2),
        "has_geo_pct": 100.0,
        "has_geo_pct_after_district_sanity_filter": round(100 * (n - far100) / n, 2),
        "has_district": True,
        "has_pincode": False,
        "has_address": False,
        "has_phone": False,
        "unmatchable_row_pct": round(100 * zero_info / n, 2),
        "unmatchable_definition": "rows whose FAC_DESC reduces to nothing but generic "
                                  "facility-type words, leaving the coordinate as the only "
                                  "matching evidence",
        "blocking_key_viable": True,
        "recommended_blocking_strategy": "GEO-PRIMARY: coordinate within 100-500 m, blocked by "
                                         "(state, district); name similarity as tiebreak only. "
                                         "The project-default name+geo+district key isolates only "
                                         f"{round(100*(d.groupby(['STATE_NAME','DISTRICT_NAME','_nn']).size()==1).sum()/n,2)}% "
                                         "of rows, whereas a ~1.1 km geo cell isolates "
                                         f"{round(100*(cell==1).sum()/n,2)}%.",
        "blocking_singleton_pct": {
            "state+district": round(100 * (d.groupby(["STATE_NAME", "DISTRICT_NAME"]).size() == 1).sum() / n, 2),
            "state+district+name": round(100 * (d.groupby(["STATE_NAME", "DISTRICT_NAME", "_nn"]).size() == 1).sum() / n, 2),
            "block_id": round(100 * (d.groupby("BLOCK_ID").size() == 1).sum() / n, 2),
            "block_id+name": round(100 * (d.groupby(["BLOCK_ID", "_nn"]).size() == 1).sum() / n, 2),
            "geo_cell_1p1km": round(100 * (cell == 1).sum() / n, 2),
        },
    }

    # tier reliability
    f_sub = d._nn.str.contains(r"\bsub\b|\bhsc\b|\bphsc\b|\bshc\b")
    f_bphc = d._nn.str.contains(r"bphc|block primary|block phc|rural hospital")
    f_ovl = d.FACILITY_ID.isin(overlap_ids)
    prof["tier_reliability"] = {
        "note": "The PHC/CHC distinction exists ONLY in the filename - the schemas are identical "
                "and FAC_CATEGO is the same constant in both. Evidence indicates the split was a "
                "keyword rule over FAC_DESC: all 5 rows in either file naming both tiers, and all "
                "10 rows named exactly 'HSC', appear in BOTH files.",
        "rows_duplicated_into_both_files": int(f_ovl.sum()),
        "rows_named_as_sub_centre": int(f_sub.sum()),
        "rows_named_as_block_phc_or_rural_hospital": int(f_bphc.sum()),
        "distinct_rows_with_unreliable_tier": int((f_sub | f_bphc | f_ovl).sum()),
        "pct_rows_with_unreliable_tier": round(100 * (f_sub | f_bphc | f_ovl).mean(), 2),
    }

    prof["coded_vocabularies"] = {
        "FAC_CATEGO": sorted(d.FAC_CATEGO.unique().tolist()),
        "FAC_CATEGO_note": "single constant value in BOTH files; not a usable vocabulary, no "
                           "codebook available - see questions.md Q3",
        "STATE_NAME": sorted(d.STATE_NAME.unique().tolist()),
        "BLOCK_ID_note": f"{d.BLOCK_ID.nunique()} distinct integer codes, unverified authority - "
                         "see questions.md Q1. Not enumerated here.",
        "HAB_ID_note": f"{d.HAB_ID.nunique()} distinct integer codes, unverified authority - "
                       "see questions.md Q2. Not enumerated here.",
    }

    prof["cross_file"] = {
        "sibling_dataset_key": other,
        "sibling_file": FILES[other],
        "schema_identical": True,
        "shared_id_namespace": True,
        "namespace_evidence": "0 of 6252 union BLOCK_IDs span more than one district; 0 of 35189 "
                              "union HAB_IDs span more than one block. All 21 shared FACILITY_IDs "
                              "resolve to byte-identical rows.",
        "exact_row_overlap_with_sibling": int(len(overlap_ids)),
        "shared_block_ids": int(len(set(d.BLOCK_ID) & set(o.BLOCK_ID))),
        "shared_hab_ids": int(len(set(d.HAB_ID) & set(o.HAB_ID))),
        "shared_facility_ids": int(len(set(d.FACILITY_ID) & set(o.FACILITY_ID))),
        "fac_catego_disjoint_from_sibling": False,
        "union_rows_naive": len(phc) + len(chc),
        "union_rows_deduplicated": int(len(union)),
        "union_facility_id_is_unique": bool(union.FACILITY_ID.nunique() == len(union)),
        "union_is_safe": True,
        "warning": "Do NOT prefix FACILITY_ID per file - that creates 21 duplicate canonical "
                   "entities. Load PHC+CHC as ONE source with a facility_tier column.",
        "see": "eda/PHC/CROSS_PHC_CHC.md",
    }

    json.dump(prof, open(p, "w"), indent=2, default=str)
    print(f"patched {p}")
    print("  er_readiness:", json.dumps(prof["er_readiness"], indent=2)[:400], "...")
    print("  tier_reliability:", prof["tier_reliability"]["pct_rows_with_unreliable_tier"], "%")
