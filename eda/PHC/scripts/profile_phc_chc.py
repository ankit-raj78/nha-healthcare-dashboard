#!/usr/bin/env python
"""
Shared profiling script for the PHC and CHC datasets (identical 9-column schema).

Usage:
    .venv/bin/python eda/PHC/scripts/profile_phc_chc.py PHC
    .venv/bin/python eda/PHC/scripts/profile_phc_chc.py CHC

Writes eda/<KEY>/profile.json and dumps a large human-readable report to stdout
which was used to author PROFILE.md / issues.md / questions.md.

Reproducible: reads only the source CSV, never writes to it.
"""
import json
import os
import re
import sys
import unicodedata
from collections import Counter

import numpy as np
import pandas as pd

ROOT = "/Users/ankitraj2/asar master data"
FILES = {
    "PHC": "21_June_2024_AM_PHC.csv",
    "CHC": "21_June_2024_AM_CHC.csv",
}

READ_KWARGS = dict(
    encoding="utf-8",
    dtype=str,
    keep_default_na=False,
    na_values=[],
    sep=",",
)

INDIA_BBOX = dict(lon_min=68.0, lon_max=98.0, lat_min=6.0, lat_max=38.0)


def raw_line_count(path):
    """Number of physical lines, accounting for a possibly-absent trailing newline."""
    with open(path, "rb") as fh:
        data = fh.read()
    n_nl = data.count(b"\n")
    trailing_nl = data.endswith(b"\n")
    return {
        "bytes": len(data),
        "newline_count": n_nl,
        "ends_with_newline": trailing_nl,
        "physical_lines": n_nl if trailing_nl else n_nl + 1,
        "has_bom": data[:3] == b"\xef\xbb\xbf",
        "has_cr": b"\r" in data,
        "n_embedded_quotes": data.count(b'"'),
    }


def norm_name(s):
    """Aggressive name normalisation used for near-dupe detection."""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def profile(key):
    path = os.path.join(ROOT, FILES[key])
    rlc = raw_line_count(path)

    df = pd.read_csv(path, **READ_KWARGS)
    n_rows, n_cols = df.shape

    out = {
        "dataset_key": key,
        "source_file": FILES[key],
        "read_kwargs": {
            "encoding": "utf-8",
            "sep": ",",
            "dtype": "str",
            "keep_default_na": False,
            "na_values": [],
            "note": "read as str to preserve ID zero-padding and avoid float coercion; "
                    "numerics cast explicitly downstream",
        },
        "n_rows": int(n_rows),
        "n_cols": int(n_cols),
        "raw_line_count": int(rlc["physical_lines"]),
        "raw_file_facts": rlc,
    }
    out["row_count_explanation"] = (
        f"`wc -l` reports {rlc['newline_count']} because the file does not end with a newline "
        f"({rlc['ends_with_newline']}). Physical lines = {rlc['physical_lines']} "
        f"= 1 header + {rlc['physical_lines'] - 1} data lines. pandas returns {n_rows} rows, "
        f"which matches exactly: no embedded newlines "
        f"(double-quote chars in file = {rlc['n_embedded_quotes']}), no BOM ({rlc['has_bom']}), "
        f"no CR ({rlc['has_cr']}), no Unnamed/trailing-empty columns."
    )

    print("=" * 100)
    print(f"DATASET {key}   file={FILES[key]}")
    print("=" * 100)
    print(json.dumps({k: v for k, v in out.items() if k != "columns"}, indent=2, default=str))
    print("\ncolumns:", list(df.columns))
    print("repr of columns:", [repr(c) for c in df.columns])

    # ---------- numeric casts ----------
    lon = pd.to_numeric(df["Longitude"], errors="coerce")
    lat = pd.to_numeric(df["Latitude"], errors="coerce")

    # ---------- per-column profile ----------
    cols = []
    for c in df.columns:
        s = df[c]
        blank = s.str.strip().eq("")
        non_null = int((~blank).sum())
        distinct = int(s[~blank].nunique())
        col = {
            "name": c,
            "dtype": "object(str as read); " + (
                "float64 after to_numeric" if c in ("Longitude", "Latitude")
                else "int64-castable" if c in ("BLOCK_ID", "HAB_ID", "FACILITY_ID")
                else "string"
            ),
            "non_null": non_null,
            "null_pct": round(100.0 * (n_rows - non_null) / n_rows, 4),
            "n_distinct": distinct,
            "examples": [str(x) for x in s[~blank].head(5).tolist()],
        }
        if distinct < 50:
            col["value_counts"] = {str(k): int(v) for k, v in s.value_counts().items()}
        else:
            col["value_counts"] = {}
            col["top_10"] = {str(k): int(v) for k, v in s.value_counts().head(10).items()}
        cols.append(col)

        print(f"\n--- COLUMN {c} ---")
        print(f"non_null={non_null}/{n_rows}  distinct={distinct}")
        print("examples:", col["examples"])
        if distinct < 50:
            print("FULL value counts:", col["value_counts"])
        else:
            print("top 10:", col.get("top_10"))

    # ---------- ID columns ----------
    print("\n=== ID COLUMN ANALYSIS ===")
    id_stats = {}
    for c in ("BLOCK_ID", "HAB_ID", "FACILITY_ID"):
        v = pd.to_numeric(df[c], errors="coerce")
        n_bad = int(v.isna().sum())
        nunq = int(df[c].nunique())
        id_stats[c] = {
            "n_distinct": nunq,
            "is_unique": bool(nunq == n_rows),
            "n_non_numeric": n_bad,
            "min": None if v.notna().sum() == 0 else float(v.min()),
            "max": None if v.notna().sum() == 0 else float(v.max()),
            "n_leading_zero": int(df[c].str.match(r"^0\d").sum()),
            "len_dist": {str(k): int(vv) for k, vv in df[c].str.len().value_counts().sort_index().items()},
            "n_dup_rows": int(df[c].duplicated(keep=False).sum()),
            "max_repeat": int(df[c].value_counts().max()),
        }
        print(c, json.dumps(id_stats[c], indent=2))
        # top repeated
        print("  most repeated values:", df[c].value_counts().head(5).to_dict())

    # FACILITY_ID uniqueness detail
    fid_counts = df["FACILITY_ID"].value_counts()
    dup_fids = fid_counts[fid_counts > 1]
    print(f"\nFACILITY_ID: {len(dup_fids)} values appear >1 time, covering "
          f"{int(dup_fids.sum())} rows")
    if len(dup_fids):
        ex = dup_fids.index[0]
        print("example duplicated FACILITY_ID rows:")
        print(df[df["FACILITY_ID"] == ex].to_string())

    # composite key candidates
    print("\n=== COMPOSITE KEY CANDIDATES ===")
    combos = [
        ["FACILITY_ID"],
        ["HAB_ID"],
        ["FACILITY_ID", "HAB_ID"],
        ["STATE_NAME", "FACILITY_ID"],
        ["BLOCK_ID", "HAB_ID", "FACILITY_ID"],
        ["Longitude", "Latitude"],
        ["FACILITY_ID", "Longitude", "Latitude"],
    ]
    combo_res = {}
    for combo in combos:
        nun = int(df[combo].drop_duplicates().shape[0])
        combo_res["+".join(combo)] = {"n_distinct": nun, "is_unique": nun == n_rows}
        print(f"{'+'.join(combo):45s} distinct={nun:7d} unique={nun == n_rows}")

    # ---------- geo quality ----------
    print("\n=== GEO QUALITY ===")
    lon_blank = df["Longitude"].str.strip().eq("")
    lat_blank = df["Latitude"].str.strip().eq("")
    geo_null = int((lon.isna() | lat.isna()).sum())
    geo_zero = int(((lon == 0) | (lat == 0)).sum())
    in_bbox = (
        lon.between(INDIA_BBOX["lon_min"], INDIA_BBOX["lon_max"])
        & lat.between(INDIA_BBOX["lat_min"], INDIA_BBOX["lat_max"])
    )
    swapped = (
        lat.between(INDIA_BBOX["lon_min"], INDIA_BBOX["lon_max"])
        & lon.between(INDIA_BBOX["lat_min"], INDIA_BBOX["lat_max"])
        & ~in_bbox
    )
    out_of_bbox = (~in_bbox) & lon.notna() & lat.notna() & (lon != 0) & (lat != 0)
    geo = {
        "valid_in_india": int(in_bbox.sum()),
        "null": geo_null,
        "blank_string_lon": int(lon_blank.sum()),
        "blank_string_lat": int(lat_blank.sum()),
        "zero": geo_zero,
        "out_of_bbox": int(out_of_bbox.sum()),
        "possibly_swapped": int(swapped.sum()),
        "lon_min": float(lon.min()), "lon_max": float(lon.max()),
        "lat_min": float(lat.min()), "lat_max": float(lat.max()),
        "lon_mean": float(lon.mean()), "lat_mean": float(lat.mean()),
    }
    for q in (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99):
        geo[f"lon_p{int(q*100)}"] = float(lon.quantile(q))
        geo[f"lat_p{int(q*100)}"] = float(lat.quantile(q))
    print(json.dumps(geo, indent=2))

    if int(out_of_bbox.sum()):
        print("\nOUT-OF-BBOX ROWS (up to 30):")
        print(df[out_of_bbox].head(30).to_string())

    # decimal precision of coords
    def dec_places(s):
        return s.str.extract(r"\.(\d+)$", expand=False).fillna("").str.len()
    print("\nLongitude decimal-place distribution:")
    print(dec_places(df["Longitude"]).value_counts().sort_index().to_string())
    print("Latitude decimal-place distribution:")
    print(dec_places(df["Latitude"]).value_counts().sort_index().to_string())

    # coordinate reuse (same point used by many rows)
    ptcounts = df.groupby(["Longitude", "Latitude"]).size().sort_values(ascending=False)
    print(f"\ndistinct (lon,lat) points: {len(ptcounts)} for {n_rows} rows")
    print("most-reused points:\n", ptcounts.head(10).to_string())
    geo["n_distinct_points"] = int(len(ptcounts))
    geo["n_rows_sharing_a_point"] = int((ptcounts[ptcounts > 1]).sum())
    geo["max_rows_at_one_point"] = int(ptcounts.max())

    # rounded-coordinate collision (4dp ~ 11m)
    lat4 = lat.round(4); lon4 = lon.round(4)
    pt4 = pd.Series(list(zip(lon4, lat4)))
    c4 = pt4.value_counts()
    geo["n_rows_sharing_point_4dp"] = int(c4[c4 > 1].sum())
    print(f"rows sharing a coordinate rounded to 4dp (~11m): {geo['n_rows_sharing_point_4dp']}")

    # ---------- duplicates ----------
    print("\n=== DUPLICATES ===")
    exact = int(df.duplicated(keep=False).sum())
    exact_extra = int(df.duplicated().sum())
    print(f"fully-identical rows (all 9 cols): {exact} rows in {exact - exact_extra} groups "
          f"({exact_extra} removable)")
    if exact:
        d = df[df.duplicated(keep=False)].sort_values(list(df.columns))
        print(d.head(20).to_string())

    df["_name_norm"] = df["FAC_DESC"].map(norm_name)
    ng_key = df["_name_norm"] + "|" + df["Longitude"].astype(str) + "|" + df["Latitude"].astype(str)
    near_all = int(ng_key.duplicated(keep=False).sum())
    near_extra = int(ng_key.duplicated().sum())
    print(f"near-dupe (normalised name + exact lon/lat): {near_all} rows, {near_extra} removable")

    # name + rounded geo (3dp ~ 110m)
    lat3 = lat.round(3).astype(str); lon3 = lon.round(3).astype(str)
    ng3 = df["_name_norm"] + "|" + lon3 + "|" + lat3
    near3_all = int(ng3.duplicated(keep=False).sum())
    near3_extra = int(ng3.duplicated().sum())
    print(f"near-dupe (normalised name + geo@3dp ~110m): {near3_all} rows, {near3_extra} removable")

    # district + name
    dn = df["DISTRICT_NAME"].str.lower().str.strip() + "|" + df["_name_norm"]
    print(f"district+normname collisions: {int(dn.duplicated(keep=False).sum())} rows, "
          f"{int(dn.duplicated().sum())} removable")

    if near_all:
        ex_key = ng_key[ng_key.duplicated(keep=False)].iloc[0]
        print("example near-dupe group (name+exact geo):")
        print(df[ng_key == ex_key].to_string())

    dupes = {
        "exact": exact_extra,
        "exact_rows_involved": exact,
        "near_dupe_name_geo": near_extra,
        "near_dupe_name_geo_rows_involved": near_all,
        "near_dupe_name_geo3dp": near3_extra,
        "near_dupe_district_name": int(dn.duplicated().sum()),
        "method": "exact = df.duplicated() over all 9 columns. near_dupe_name_geo = "
                  "duplicated() over (lowercased/punctuation-stripped FAC_DESC, raw Longitude "
                  "string, raw Latitude string). 3dp variant rounds coords to 3 decimals "
                  "(~110 m) before keying. Counts reported are removable duplicates "
                  "(keep-first); *_rows_involved is the total rows in any dup group.",
    }

    # ---------- state / district ----------
    print("\n=== STATE / DISTRICT ===")
    states = sorted(df["STATE_NAME"].unique())
    print(f"n distinct STATE_NAME: {len(states)}")
    for s in states:
        print(f"  {s!r:45s} {int((df['STATE_NAME'] == s).sum())}")
    print("\nstates containing '*' or non-ascii or leading/trailing space:")
    for s in states:
        if "*" in s or s != s.strip() or any(ord(ch) > 127 for ch in s):
            print("   ", repr(s))

    dists = sorted(df["DISTRICT_NAME"].unique())
    print(f"\nn distinct DISTRICT_NAME: {len(dists)}")
    trunc = [d for d in dists if "*" in d]
    print(f"districts with '*' (truncation marker): {len(trunc)}")
    for d in trunc:
        print(f"   {d!r} len={len(d)} n={int((df['DISTRICT_NAME'] == d).sum())}")
    print("\ndistrict name length distribution:")
    print(df["DISTRICT_NAME"].str.len().value_counts().sort_index().to_string())
    print("\nfull district list:")
    print(dists)

    # state x district cardinality
    sd = df.groupby("STATE_NAME")["DISTRICT_NAME"].nunique().sort_values(ascending=False)
    print("\ndistricts per state:\n", sd.to_string())

    # districts appearing in >1 state (ambiguity for blocking)
    ds = df.groupby("DISTRICT_NAME")["STATE_NAME"].nunique()
    amb = ds[ds > 1]
    print(f"\ndistrict names appearing in >1 state: {len(amb)}")
    print(amb.to_string())

    # ---------- FAC_DESC free text ----------
    print("\n=== FAC_DESC (facility name) ===")
    L = df["FAC_DESC"].str.len()
    print("length: min", int(L.min()), "max", int(L.max()), "mean", round(float(L.mean()), 2))
    print("length percentiles:", {f"p{int(q*100)}": float(L.quantile(q))
                                  for q in (0.01, 0.25, 0.5, 0.75, 0.95, 0.99)})
    print("\nlength distribution head:")
    print(L.value_counts().sort_index().head(20).to_string())
    print("\nshortest 20 FAC_DESC values:", df.loc[L.nsmallest(20).index, "FAC_DESC"].tolist())
    print("\nlongest 10 FAC_DESC values:", df.loc[L.nlargest(10).index, "FAC_DESC"].tolist())
    print(f"\ndistinct FAC_DESC: {df['FAC_DESC'].nunique()}")
    print("top 25 FAC_DESC verbatim:")
    print(df["FAC_DESC"].value_counts().head(25).to_string())
    print("\ntop 25 FAC_DESC normalised (case/punct folded):")
    print(df["_name_norm"].value_counts().head(25).to_string())

    # how many names are pure generic type strings with no distinguishing token
    generic_tokens = {
        "primary", "health", "sub", "centre", "center", "phc", "chc", "hospital", "community",
        "care", "unit", "govt", "government", "new", "the", "of", "and", "dispensary",
        "clinic", "hc", "sc", "uphc", "chospital", "medical", "heath", "helth", "healt",
        "comprehensive", "rural", "urban", "main", "public", "ayush", "hosp", "hlth",
        "hospitalc", "centr", "cntr", "cent", "cen", "ctr", "primry", "primery", "bphc",
        "aphc", "mphc", "shc", "hsc", "phsc", "hwc", "pheath",
    }

    def is_generic(nm):
        toks = [t for t in nm.split() if t]
        if not toks:
            return True
        return all(t in generic_tokens or t.isdigit() for t in toks)

    gen = df["_name_norm"].map(is_generic)
    n_generic = int(gen.sum())
    print(f"\nFAC_DESC that are PURELY generic facility-type words (no place/person token): "
          f"{n_generic} ({round(100*n_generic/n_rows,2)}%)")
    print("sample non-generic names:", df.loc[~gen, "FAC_DESC"].head(20).tolist())

    # distinctness of name within district
    dn_counts = df.groupby([df["DISTRICT_NAME"], df["_name_norm"]]).size()
    n_unique_in_district = int((dn_counts == 1).sum())
    print(f"\n(district, normname) pairs that are unique: {n_unique_in_district} of "
          f"{len(dn_counts)} pairs")
    rows_unique_in_district = int(dn_counts[dn_counts == 1].sum())
    print(f"rows whose (district, normname) is unique in the file: {rows_unique_in_district} "
          f"({round(100*rows_unique_in_district/n_rows,2)}%)")

    # ---------- FAC_CATEGO ----------
    print("\n=== FAC_CATEGO ===")
    print(df["FAC_CATEGO"].value_counts(dropna=False).to_string())

    # ---------- character / encoding hygiene ----------
    print("\n=== ENCODING / WHITESPACE HYGIENE ===")
    for c in df.columns:
        if c.startswith("_"):
            continue
        s = df[c]
        n_lead_trail = int((s != s.str.strip()).sum())
        n_double_space = int(s.str.contains(r"  ").sum())
        n_nonascii = int(s.map(lambda x: any(ord(ch) > 127 for ch in str(x))).sum())
        n_comma = int(s.str.contains(",").sum())
        print(f"{c:16s} lead/trail_ws={n_lead_trail:6d} double_space={n_double_space:6d} "
              f"non_ascii={n_nonascii:6d} contains_comma={n_comma:6d}")

    nonascii_chars = Counter()
    for c in df.columns:
        if c.startswith("_"):
            continue
        for v in df[c]:
            for ch in str(v):
                if ord(ch) > 127:
                    nonascii_chars[ch] += 1
    print("non-ascii characters present:", dict(nonascii_chars))

    # ---------- build final profile ----------
    role_map = {
        "STATE_NAME":    ("state_raw", [], "State name, title case, Indian state/UT."),
        "DISTRICT_NAME": ("district_raw", ["truncated"], "District name; values are truncated to 25 chars with a trailing '*' marker."),
        "BLOCK_ID":      ("block_lgd_code?", ["unverified_code"], "Integer block identifier; namespace/authority unconfirmed (see questions.md)."),
        "HAB_ID":        ("village_lgd_code?", ["unverified_code"], "Integer habitation identifier; near-unique per row. Authority unconfirmed."),
        "FACILITY_ID":   ("source_facility_id", [], "Integer facility identifier within the source system."),
        "FAC_DESC":      ("facility_name_raw", [], "Free-text facility name; frequently just the generic facility type."),
        "FAC_CATEGO":    ("facility_category_raw", [], "Coded category vocabulary."),
        "Longitude":     ("longitude", [], "Decimal degrees, WGS84 assumed."),
        "Latitude":      ("latitude", [], "Decimal degrees, WGS84 assumed."),
    }
    for col in cols:
        r, f, note = role_map[col["name"]]
        col["semantic_role"] = r
        col["flags"] = list(f)
        col["notes"] = note
        if col["name"] == "FAC_CATEGO" and len(col.get("value_counts", {})) == 1:
            col["flags"].append("constant")

    has_geo = int(in_bbox.sum())
    out.update({
        "columns": cols,
        "duplicates": dupes,
        "geo_quality": geo,
        "id_column_stats": id_stats,
        "composite_key_candidates": combo_res,
        "candidate_primary_key": {
            "column": "FACILITY_ID",
            "is_unique": id_stats["FACILITY_ID"]["is_unique"],
        },
        "coded_vocabularies": {
            "FAC_CATEGO": sorted(df["FAC_CATEGO"].unique().tolist()),
            "STATE_NAME": states,
        },
        "state_district": {
            "n_states": len(states),
            "states": states,
            "n_districts": len(dists),
            "n_districts_truncated": len(trunc),
            "truncated_districts": trunc,
            "district_names_in_multiple_states": {k: int(v) for k, v in amb.items()},
        },
        "name_quality": {
            "n_distinct_fac_desc": int(df["FAC_DESC"].nunique()),
            "n_distinct_normalised": int(df["_name_norm"].nunique()),
            "n_purely_generic_names": n_generic,
            "pct_purely_generic_names": round(100.0 * n_generic / n_rows, 2),
            "rows_with_unique_district_name_pair": rows_unique_in_district,
            "pct_rows_with_unique_district_name_pair": round(100.0 * rows_unique_in_district / n_rows, 2),
            "len_min": int(L.min()), "len_max": int(L.max()), "len_mean": round(float(L.mean()), 2),
        },
        "er_readiness": {
            "has_name": True,
            "has_geo_pct": round(100.0 * has_geo / n_rows, 2),
            "has_district": True,
            "unmatchable_row_pct": round(100.0 * n_generic / n_rows, 2),
            "blocking_key_viable": True,
        },
    })

    outdir = os.path.join(ROOT, "eda", key)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "profile.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(f"\n>>> wrote {outdir}/profile.json")
    return df, out


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "PHC"
    profile(key)
