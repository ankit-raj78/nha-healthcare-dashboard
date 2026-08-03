"""NHA EDA step 9: remaining gaps — residual dup IDs, lat/lon precision artifacts,
Address lineage/structure, enum hygiene, district-vs-address cross-check.
"""
import json
import re

import pandas as pd

SRC = "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv"
df = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)
N = len(df)
R = {}

# ---------------- residual repeated IDs after collapsing on everything-but-24/7
collapsed = df.drop(columns=["24/7"]).drop_duplicates()
cvc = collapsed["Facility ID"].value_counts()
still = cvc[cvc > 1]
R["residual_dup_ids_after_24x7_collapse"] = {"n_ids": int(len(still))}
varying = {}
sub = collapsed[collapsed["Facility ID"].isin(still.index)]
gg = sub.groupby("Facility ID")
for c in collapsed.columns:
    if c != "Facility ID":
        varying[c] = int(gg[c].nunique().gt(1).sum())
R["residual_dup_ids_after_24x7_collapse"]["varying_cols"] = {
    k: v for k, v in sorted(varying.items(), key=lambda kv: -kv[1]) if v}
ex = []
for k in still.index[:200]:
    grp = sub[sub["Facility ID"] == k]
    d = [c for c in collapsed.columns if grp[c].nunique() > 1]
    if d and len(ex) < 6:
        ex.append({"facility_id": str(k), "differing": d,
                   "values": {c: grp[c].tolist()[:3] for c in d[:4]}})
R["residual_dup_ids_after_24x7_collapse"]["examples"] = ex

# ---------------- lat/lon precision artifacts
lat = pd.to_numeric(df["Latitude"], errors="coerce")
dec = df["Latitude"].str.split(".").str[1].fillna("").str.len()
R["coord_precision"] = {
    "decimals_hist": {str(k): int(v) for k, v in dec.value_counts().sort_index().items()},
    "n_ge_12_decimals": int(dec.ge(12).sum()),
    "pct_ge_12_decimals": round(100.0 * dec.ge(12).mean(), 2),
    "n_le_2_decimals": int(dec.le(2).sum()),
    "note": (">=12 decimals is float64 round-trip noise, not survey precision; "
             "<=2 decimals is ~1 km or coarser."),
    "examples_high": df.loc[dec.ge(15), ["Latitude", "Longitude"]].head(5).to_dict("records"),
    "examples_low": df.loc[dec.le(2) & lat.notna(),
                           ["Latitude", "Longitude", "hospital_name"]].head(8).to_dict("records"),
}

# ---------------- Address structure / lineage
addr = df["Address"]
R["address_structure"] = {
    "n_ending_with_dash_pin": int(addr.str.contains(r"-\s*\d{6}\s*$", regex=True).sum()),
    "n_containing_state_name": int(
        df.apply(lambda r: r["new_state_name"].lower() in r["Address"].lower(), axis=1).sum()),
    "n_comma_separated_ge3": int(addr.str.count(",").ge(3).sum()),
    "comma_count_hist": {str(k): int(v) for k, v in
                         addr.str.count(",").value_counts().sort_index().head(15).items()},
    "examples": addr.drop_duplicates().head(6).tolist(),
    "note": ("Address looks machine-assembled: '<premise>, <locality> <district>, "
             "<State> - <PIN>'. It is a single free-text column; there are NO parsed "
             "components (no street/locality/city/pincode columns) in this dataset."),
}
# does the trailing district token in Address agree with new_district_name?
R["address_vs_district"] = {
    "n_rows_where_new_district_appears_in_address": int(
        df.apply(lambda r: r["new_district_name"].lower() in r["Address"].lower(), axis=1).sum()),
    "n_rows_where_old_district_appears_in_address": int(
        df.apply(lambda r: r["District_name"].lower() in r["Address"].lower(), axis=1).sum()),
}

# for the 867 district-mismatch rows, which one matches the Address?
key = lambda s: re.sub(r"[^a-z]", "", s.lower())
mm = df[df["District_name"].map(key) != df["new_district_name"].map(key)]
old_ok = mm.apply(lambda r: r["District_name"].lower() in r["Address"].lower(), axis=1)
new_ok = mm.apply(lambda r: r["new_district_name"].lower() in r["Address"].lower(), axis=1)
R["district_mismatch_adjudication"] = {
    "n_mismatch_rows": int(len(mm)),
    "old_District_name_matches_Address": int(old_ok.sum()),
    "new_district_name_matches_Address": int(new_ok.sum()),
    "neither_matches": int((~old_ok & ~new_ok).sum()),
    "both_match": int((old_ok & new_ok).sum()),
    "verdict_hint": ("whichever side matches the free-text Address more often is the "
                     "one that survived correctly"),
    "examples": [
        {"row": int(i), "District_name": r["District_name"],
         "new_district_name": r["new_district_name"],
         "new_state_name": r["new_state_name"], "Address": r["Address"][:110]}
        for i, r in mm.head(10).iterrows()],
}

# ---------------- enum hygiene (case/whitespace that would break GROUP BY)
for c in ["Facility Type", "Ownership", "ABDM Enabled", "24/7", "Name verifier"]:
    s = df[c]
    R.setdefault("enum_hygiene", {})[c] = {
        "n_distinct": int(s.nunique()),
        "n_distinct_strip_lower": int(s.str.strip().str.lower().nunique()),
        "n_rows_with_leading_trailing_ws": int((s != s.str.strip()).sum()),
        "n_rows_with_double_space": int(s.str.contains("  ", regex=False).sum()),
        "clean": bool(s.nunique() == s.str.strip().str.lower().nunique()),
    }

# ---------------- state/district name hygiene
for c in ["State_name", "new_state_name", "District_name", "new_district_name"]:
    s = df[c]
    R.setdefault("geo_name_hygiene", {})[c] = {
        "n_distinct": int(s.nunique()),
        "n_distinct_strip_lower": int(s.str.strip().str.lower().nunique()),
        "casing": ("lower" if s.str.islower().all() else
                   "title/mixed" if s.str.istitle().any() else "mixed"),
        "n_blank": int(s.eq("").sum()),
        "n_literal_not_found": int(s.str.strip().str.lower().eq("not found").sum()),
    }
R["district_name_not_found"] = {
    "District_name": int(df["District_name"].str.strip().str.lower().eq("not found").sum()),
    "new_district_name": int(
        df["new_district_name"].str.strip().str.lower().eq("not found").sum()),
    "example_rows": [int(i) for i in
                     df.index[df["District_name"].str.strip().str.lower().eq("not found")][:10]],
}

json.dump(R, open("eda/NHA/scripts/intermediate/_gaps.json", "w"), indent=2, default=str)
print(json.dumps(R, indent=2, default=str)[:10000])
