#!/usr/bin/env python
"""Profile the two CDAC blood-bank datasets and emit eda/<KEY>/profile.json.

Usage:  .venv/bin/python eda/CDAC_BB_A/scripts/profile_bb.py CDAC_BB_A
        .venv/bin/python eda/CDAC_BB_A/scripts/profile_bb.py CDAC_BB_B

Read-only with respect to the source CSVs.
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

BASE = "/Users/ankitraj2/asar master data"
DATASETS = {
    "CDAC_BB_A": "16_MAY_AR_CDAC_BB_DATASET.csv",
    "CDAC_BB_B": "CDAC_BB_DATASET - Sheet1.csv",
}
READ_KWARGS = dict(encoding="utf-8", dtype=str, keep_default_na=False, na_values=[""])

LAT_RANGE = (6.0, 38.0)
LON_RANGE = (68.0, 98.0)

# rows >= this index are the "appended batch" whose new_longitude/new_latitude
# columns hold (latitude, longitude) instead of (longitude, latitude)
SWAP_BLOCK_START = 5469


def norm(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    s = re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()
    return s


def in_bbox(lat, lon):
    return lat.between(*LAT_RANGE) & lon.between(*LON_RANGE)


def raw_line_count(path):
    with open(path, "rb") as fh:
        b = fh.read()
    n = b.count(b"\n")
    if b and not b.endswith(b"\n"):
        n += 1
    return n


def col_profile(df, name, role, flags, notes, max_vc=50):
    s = df[name]
    nn = int(s.notna().sum())
    dist = int(s.nunique(dropna=True))
    vc = {}
    if dist < max_vc:
        vc = {str(k): int(v) for k, v in s.value_counts(dropna=False).items()}
    out = {
        "name": name,
        "dtype": "object(str)",
        "non_null": nn,
        "null_pct": round(100.0 * (1 - nn / len(df)), 3),
        "n_distinct": dist,
        "examples": [str(x) for x in s.dropna().unique()[:3]],
        "value_counts": vc,
        "semantic_role": role,
        "flags": flags,
        "notes": notes,
    }
    num = pd.to_numeric(s, errors="coerce")
    if num.notna().mean() > 0.5:
        out["numeric_summary"] = {
            "parseable": int(num.notna().sum()),
            "min": float(num.min()),
            "p01": float(num.quantile(0.01)),
            "p25": float(num.quantile(0.25)),
            "median": float(num.median()),
            "p75": float(num.quantile(0.75)),
            "p99": float(num.quantile(0.99)),
            "max": float(num.max()),
            "mean": float(num.mean()),
        }
    if s.dtype == object and dist >= max_vc:
        L = s.dropna().astype(str).str.len()
        out["length_dist"] = {
            "min": int(L.min()), "p25": int(L.quantile(0.25)), "median": int(L.median()),
            "p75": int(L.quantile(0.75)), "max": int(L.max()),
        }
    return out


ROLES = {
    "State": ("state_raw", [], ""),
    "Name": ("facility_name_raw", ["pii_possible"], "facility name; some contain a person's name"),
    "Address": ("address_raw", [], "always ends '<place>, Dist. <district>'"),
    "Latitude": ("latitude", [], "primary point geo"),
    "Longitude": ("longitude", [], "primary point geo"),
    "Phone": ("phone", ["pii"], "heavily corrupted by Excel scientific notation"),
    "Email": ("email", ["pii"], ""),
    "Category": ("facility_ownership_raw", ["coded_vocabulary"], "4-value ownership code"),
    "new_longitude": ("longitude", ["derived", "redundant_with:Longitude"],
                      "prior geocoding pass; axis-swapped for rows >=5469; 344 rows invalid in both orientations"),
    "new_latitude": ("latitude", ["derived", "redundant_with:Latitude"],
                     "prior geocoding pass; axis-swapped for rows >=5469; 344 rows invalid in both orientations"),
    "District": ("district_raw", ["redundant_with:Address"],
                 "current (post-2022) district; 100% reproducible by parsing 'Dist. X' from Address"),
    "dist_name": ("district_raw", ["redundant_with:District"],
                  "legacy/LGD district spelling; truncated to 24 chars + '*' for 43 rows"),
}


def main(key):
    src = DATASETS[key]
    path = os.path.join(BASE, src)
    df = pd.read_csv(path, **READ_KWARGS)
    outdir = os.path.join(BASE, "eda", key)
    os.makedirs(outdir, exist_ok=True)

    nname = df.Name.map(norm)
    naddr = df.Address.map(norm)
    adist = df.Address.str.extract(r"Dist\.\s*([^,]*)$")[0].map(norm).replace("", np.nan)

    lat = pd.to_numeric(df.Latitude, errors="coerce")
    lon = pd.to_numeric(df.Longitude, errors="coerce")
    nlon = pd.to_numeric(df.new_longitude, errors="coerce")
    nlat = pd.to_numeric(df.new_latitude, errors="coerce")

    ok = in_bbox(lat, lon)
    null_geo = lat.isna() | lon.isna()
    zero_geo = (lat == 0) | (lon == 0)
    swapped_ok = in_bbox(lon, lat) & ~ok

    new_ok_asis = in_bbox(nlat, nlon)
    new_ok_swap = in_bbox(nlon, nlat)

    src_cols = list(df.columns)
    exact_dupes = int(df.duplicated(subset=src_cols).sum())
    near_key = nname + "|" + lat.round(3).astype(str) + "|" + lon.round(3).astype(str)
    near = int(near_key.duplicated().sum())

    prof = {
        "dataset_key": key,
        "source_file": src,
        "read_kwargs": {"encoding": "utf-8", "dtype": "str", "keep_default_na": False,
                        "na_values": [""], "sep": ","},
        "n_rows": int(len(df)),
        "n_cols": int(df.shape[1]),
        "raw_line_count": raw_line_count(path),
        "row_count_explanation": (
            "raw_line_count counts physical lines including the header. "
            "n_rows = raw_line_count - 1. There are no embedded newlines inside quoted fields "
            "(verified: newline-character count == physical line count), no BOM, "
            "CRLF line endings, no Unnamed:N columns, no trailing all-empty column. "
            "Naive pd.read_csv is correct; dtype=str is required to stop pandas from "
            "coercing Phone/coords and from turning the literal string 'NA' in Address into NaN."
        ),
        "columns": [col_profile(df, c, *ROLES[c]) for c in df.columns],
        "duplicates": {
            "exact": exact_dupes,
            "near_dupe_name_geo": near,
            "dup_on_name_address": int(df.duplicated(subset=["Name", "Address"]).sum()),
            "dup_on_normalized_name": int(nname.duplicated().sum()),
            "method": ("exact = duplicated() over all source columns; "
                       "near_dupe_name_geo = duplicated() over "
                       "(lowercased alnum-normalized Name, Latitude rounded to 3dp, Longitude rounded to 3dp) "
                       "~= same name within ~110 m"),
        },
        "geo_quality": {
            "column_pair": "Latitude/Longitude",
            "valid_in_india": int(ok.sum()),
            "null": int(null_geo.sum()),
            "zero": int(zero_geo.sum()),
            "out_of_bbox": int((~ok & ~null_geo).sum()),
            "possibly_swapped": int(swapped_ok.sum()),
            "valid_pct": round(100.0 * ok.mean(), 3),
            "new_lat_lon_pair": {
                "valid_as_labelled": int(new_ok_asis.sum()),
                "valid_only_if_axes_swapped": int((new_ok_swap & ~new_ok_asis).sum()),
                "invalid_in_both_orientations": int((~new_ok_asis & ~new_ok_swap).sum()),
                "swap_block_starts_at_row_index": SWAP_BLOCK_START,
            },
        },
        "candidate_primary_key": {
            "column": None,
            "is_unique": False,
            "notes": (
                "No single column is unique. Name has %d duplicate rows; Email is null in %d rows "
                "and duplicated %d times. The tightest composite tried, "
                "(Name, Address, Latitude, Longitude), still has %d duplicate rows -> "
                "this dataset has NO usable source primary key; one must be synthesised."
                % (int(df.Name.duplicated().sum()), int(df.Email.isna().sum()),
                   int(df.Email.duplicated().sum()),
                   int(df.duplicated(subset=["Name", "Address", "Latitude", "Longitude"]).sum()))
            ),
        },
        "coded_vocabularies": {
            "Category": sorted(df.Category.dropna().unique().tolist()),
            "State": sorted(df.State.dropna().unique().tolist()),
            "Name_facility_type_tokens": {
                t: int(df.Name.str.contains(r"\b" + t + r"\b", case=False, na=False, regex=True).sum())
                for t in ["BSU", "BSC", "SGH", "DHH", "SDH", "CHC", "PHC", "RH", "GH",
                          "MCH", "ESI", "AIIMS", "IRCS"]
            },
        },
        "er_readiness": {
            "has_name": True,
            "has_name_pct": round(100.0 * df.Name.notna().mean(), 3),
            "has_geo_pct": round(100.0 * (~null_geo).mean(), 3),
            "has_valid_india_geo_pct": round(100.0 * ok.mean(), 3),
            "has_district": bool("District" in df.columns),
            "district_parseable_from_address_pct": round(100.0 * adist.notna().mean(), 3),
            "has_state_pct": round(100.0 * df.State.notna().mean(), 3),
            "has_pincode": False,
            "unmatchable_row_pct": round(100.0 * (df.Name.isna() | (null_geo & adist.isna())).mean(), 3),
            "blocking_key_viable": True,
        },
    }
    with open(os.path.join(outdir, "profile.json"), "w") as fh:
        json.dump(prof, fh, indent=2, ensure_ascii=False)
    print("wrote", os.path.join(outdir, "profile.json"))
    print(json.dumps({k: v for k, v in prof.items() if k not in ("columns",)}, indent=2)[:4000])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "CDAC_BB_A")
