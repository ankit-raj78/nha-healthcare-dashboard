"""NHA EDA step 3: column families — verifiers, admin geo, point geo, specialties, key."""
import json
import re

import numpy as np
import pandas as pd

SRC = "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv"
df = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)
N = len(df)
R = {}

# ---------------------------------------------------------------- verifiers
V = ["Name verifier", "Address verifier", "Facility Type verifier", "Ownership verifier"]
R["verifiers"] = {
    "all_four_identical_rowwise": bool(
        (df[V[0]] == df[V[1]]).all() and (df[V[0]] == df[V[2]]).all()
        and (df[V[0]] == df[V[3]]).all()),
    "n_rows_where_any_differ": int((df[V].nunique(axis=1) > 1).sum()),
    "value_counts": {v: dict(df[v].value_counts()) for v in V},
}
# does the verifier colour correlate with anything? cross-tab vs Facility Type / Ownership
R["verifier_vs_ownership"] = (
    pd.crosstab(df["Name verifier"], df["Ownership"]).to_dict())
R["verifier_vs_abdm"] = pd.crosstab(df["Name verifier"], df["ABDM Enabled"]).to_dict()
R["verifier_vs_facility_type_top"] = (
    pd.crosstab(df["Name verifier"], df["Facility Type"])
    .T.sort_values("Green", ascending=False).head(12).to_dict())

# ---------------------------------------------------------------- primary key
fid = df["Facility ID"]
vc = fid.value_counts()
dupids = vc[vc > 1]
R["facility_id"] = {
    "n_rows": N,
    "n_distinct": int(fid.nunique()),
    "is_unique": bool(fid.nunique() == N),
    "n_ids_appearing_more_than_once": int(len(dupids)),
    "n_rows_involved_in_dup_ids": int(dupids.sum()),
    "max_repeat": int(vc.max()),
    "repeat_count_histogram": {str(k): int(v) for k, v in
                               vc.value_counts().sort_index().items()},
    "all_numeric": bool(pd.to_numeric(fid, errors="coerce").notna().all()),
    "min": int(pd.to_numeric(fid).min()), "max": int(pd.to_numeric(fid).max()),
    "n_blank": int(fid.eq("").sum()),
    "example_dup_ids": [str(i) for i in dupids.head(5).index],
}
# are duplicate-ID rows identical across all columns?
dupmask = fid.isin(dupids.index)
sub = df[dupmask]
R["facility_id"]["dup_id_groups_fully_identical_rows"] = int(
    sub.groupby("Facility ID").apply(lambda g: g.drop_duplicates().shape[0] == 1).sum())
R["facility_id"]["n_dup_id_groups"] = int(len(dupids))

# ---------------------------------------------------------------- admin geo
R["state_name_distinct"] = sorted(df["State_name"].unique().tolist())
R["new_state_name_distinct"] = sorted(df["new_state_name"].unique().tolist())
R["state_code_distinct"] = sorted(df["state_code"].unique().tolist())
R["state_agreement"] = {
    "exact_equal": int((df["State_name"] == df["new_state_name"]).sum()),
    "equal_casefold_nospace": int(
        (df["State_name"].str.lower().str.replace(r"[^a-z]", "", regex=True)
         == df["new_state_name"].str.lower().str.replace(r"[^a-z]", "", regex=True)).sum()),
}
mism = df[df["State_name"].str.lower().str.replace(r"[^a-z]", "", regex=True)
          != df["new_state_name"].str.lower().str.replace(r"[^a-z]", "", regex=True)]
R["state_mismatch_pairs"] = {
    f"{a} || {b}": int(c) for (a, b), c in
    mism.groupby(["State_name", "new_state_name"]).size().sort_values(
        ascending=False).head(40).items()}
R["state_code_to_new_state"] = {
    str(k): sorted(v.unique().tolist())
    for k, v in df.groupby("state_code")["new_state_name"]}

R["district_agreement"] = {
    "exact_equal": int((df["District_name"] == df["new_district_name"]).sum()),
    "equal_casefold_nospace": int(
        (df["District_name"].str.lower().str.replace(r"[^a-z]", "", regex=True)
         == df["new_district_name"].str.lower().str.replace(r"[^a-z]", "", regex=True)).sum()),
    "n_distinct_old": int(df["District_name"].nunique()),
    "n_distinct_new": int(df["new_district_name"].nunique()),
    "n_distinct_district_code": int(df["district_code"].nunique()),
}
dm = df[df["District_name"].str.lower().str.replace(r"[^a-z]", "", regex=True)
        != df["new_district_name"].str.lower().str.replace(r"[^a-z]", "", regex=True)]
R["district_mismatch_examples"] = [
    {"row": int(i), "District_name": r["District_name"],
     "new_district_name": r["new_district_name"], "state": r["new_state_name"]}
    for i, r in dm.head(20).iterrows()]
R["district_mismatch_top_pairs"] = {
    f"{a} || {b}": int(c) for (a, b), c in
    dm.groupby(["District_name", "new_district_name"]).size().sort_values(
        ascending=False).head(30).items()}
# is district_code unique per new_district_name? (LGD check)
g = df.groupby("district_code")["new_district_name"].nunique()
R["district_code_maps_to_multiple_names"] = int((g > 1).sum())
g2 = df.groupby("new_district_name")["district_code"].nunique()
R["district_name_maps_to_multiple_codes"] = int((g2 > 1).sum())
R["district_name_multi_code_examples"] = {
    str(k): sorted(df[df["new_district_name"] == k]["district_code"].unique().tolist())
    for k in g2[g2 > 1].head(10).index}
# state_code+district_code pair uniqueness
R["n_distinct_state_district_code_pairs"] = int(
    df.groupby(["state_code", "district_code"]).ngroups)

# ---------------------------------------------------------------- point geo
lat = pd.to_numeric(df["Latitude"], errors="coerce")
lon = pd.to_numeric(df["Longitude"], errors="coerce")
R["geo"] = {
    "lat_blank": int(df["Latitude"].eq("").sum()),
    "lon_blank": int(df["Longitude"].eq("").sum()),
    "lat_unparseable_nonblank": int((~df["Latitude"].eq("") & lat.isna()).sum()),
    "lon_unparseable_nonblank": int((~df["Longitude"].eq("") & lon.isna()).sum()),
    "lat_bad_examples": df.loc[(~df["Latitude"].eq("")) & lat.isna(), "Latitude"]
        .drop_duplicates().head(20).tolist(),
    "lon_bad_examples": df.loc[(~df["Longitude"].eq("")) & lon.isna(), "Longitude"]
        .drop_duplicates().head(20).tolist(),
    "lat_min": float(lat.min()), "lat_max": float(lat.max()),
    "lon_min": float(lon.min()), "lon_max": float(lon.max()),
    "both_null": int((lat.isna() & lon.isna()).sum()),
    "either_null": int((lat.isna() | lon.isna()).sum()),
    "exactly_one_null": int((lat.isna() ^ lon.isna()).sum()),
    "zero_zero": int(((lat == 0) & (lon == 0)).sum()),
    "lat_zero": int((lat == 0).sum()), "lon_zero": int((lon == 0).sum()),
}
inbox = lat.between(6, 38) & lon.between(68, 98)
swapped = lon.between(6, 38) & lat.between(68, 98)
nz = lat.notna() & lon.notna() & ~((lat == 0) & (lon == 0))
R["geo"].update({
    "valid_in_india_bbox": int(inbox.sum()),
    "possibly_swapped": int(swapped.sum()),
    "out_of_bbox_nonnull_nonzero": int((nz & ~inbox).sum()),
    "out_of_bbox_examples": [
        {"row": int(i), "lat": float(lat[i]), "lon": float(lon[i]),
         "state": df.at[i, "new_state_name"], "name": df.at[i, "hospital_name"][:40]}
        for i in df.index[nz & ~inbox][:25]],
    "lat_precision_decimals_hist": dict(
        df.loc[lat.notna(), "Latitude"].str.split(".").str[-1].str.len()
        .value_counts().head(20).astype(int)),
})

# --- Google Maps Link: does it embed coords?
gml = df["Google Maps Link"]
R["gmaps_link"] = {
    "n_blank": int(gml.eq("").sum()),
    "n_looks_like_bare_latlon": int(gml.str.match(r"^\s*-?\d+\.?\d*\s*,\s*-?\d+\.?\d*\s*$").sum()),
    "n_starts_http": int(gml.str.startswith("http").sum()),
    "examples_nonlatlon": gml[~gml.str.match(r"^\s*-?\d+\.?\d*\s*,\s*-?\d+\.?\d*\s*$")
                              & ~gml.eq("")].drop_duplicates().head(15).tolist(),
}
parts = gml.str.extract(r"^\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*$")
glat = pd.to_numeric(parts[0], errors="coerce")
glon = pd.to_numeric(parts[1], errors="coerce")
both = glat.notna() & lat.notna()
R["gmaps_link"]["n_comparable"] = int(both.sum())
R["gmaps_link"]["n_lat_exact_match"] = int((glat[both] == lat[both]).sum())
R["gmaps_link"]["n_lat_match_6dp"] = int(
    (glat[both].round(6) == lat[both].round(6)).sum())
R["gmaps_link"]["n_lat_match_4dp"] = int(
    (glat[both].round(4) == lat[both].round(4)).sum())
R["gmaps_link"]["n_lon_match_4dp"] = int(
    (glon[both] .round(4) == lon[both].round(4)).sum())
d = ((glat[both] - lat[both]).abs() + (glon[both] - lon[both]).abs())
R["gmaps_link"]["max_abs_deg_diff"] = float(d.max()) if len(d) else None
R["gmaps_link"]["n_diff_gt_0001deg"] = int((d > 0.001).sum())

json.dump(R, open("eda/NHA/scripts/intermediate/_families.json", "w"), indent=2, default=str)
print(json.dumps({k: R[k] for k in
                  ["verifiers", "facility_id", "state_agreement",
                   "district_agreement", "geo", "gmaps_link"]},
                 indent=2, default=str))
