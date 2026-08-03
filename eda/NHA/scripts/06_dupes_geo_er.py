"""NHA EDA step 6: duplicates, geo defects in detail, ER readiness, address/name."""
import json
import re
import unicodedata

import numpy as np
import pandas as pd

SRC = "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv"
df = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)
N = len(df)
R = {}

# ------------------------------------------------------------ exact dupes
R["exact_dupes"] = {
    "n_fully_duplicated_rows_all46cols": int(df.duplicated().sum()),
    "n_distinct_rows": int(N - df.duplicated().sum()),
    "n_dupe_groups": int(df.duplicated(keep=False).sum() - df.duplicated().sum()),
}
# excluding Facility ID (in case the ID is the only differentiator)
noid = df.drop(columns=["Facility ID"])
R["exact_dupes"]["n_dupes_ignoring_facility_id"] = int(noid.duplicated().sum())

# ------------------------------------------------------------ near dupes
def norm_name(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()

nm = df["hospital_name"].map(norm_name)
lat = pd.to_numeric(df["Latitude"], errors="coerce")
lon = pd.to_numeric(df["Longitude"], errors="coerce")

# key 1: normalised name + coords rounded to 4dp (~11 m)
k4 = nm + "|" + lat.round(4).astype(str) + "|" + lon.round(4).astype(str)
# key 2: normalised name + coords rounded to 3dp (~110 m)
k3 = nm + "|" + lat.round(3).astype(str) + "|" + lon.round(3).astype(str)
# key 3: normalised name + district (no geo)
kd = nm + "|" + df["new_district_name"].str.lower()

def dupstats(key, label):
    vc = key.value_counts()
    d = vc[vc > 1]
    return {"label": label, "n_keys_repeated": int(len(d)),
            "n_rows_in_repeated_keys": int(d.sum()),
            "n_redundant_rows": int(d.sum() - len(d)),
            "pct_redundant": round(100.0 * (d.sum() - len(d)) / N, 3),
            "max_group": int(vc.max()),
            "example_keys": [str(x) for x in d.head(5).index]}

R["near_dupes"] = {
    "method": ("normalised name = NFKD->ascii, lowercase, non-alnum->space, collapse "
               "whitespace. Full-population (no sampling, all 323,460 rows)."),
    "name_geo_4dp": dupstats(k4, "name + lat/lon rounded 4dp (~11m)"),
    "name_geo_3dp": dupstats(k3, "name + lat/lon rounded 3dp (~110m)"),
    "name_district": dupstats(kd, "name + new_district_name (no geo)"),
    "exact_coord_pair_reuse": {
        "n_coord_pairs_used_by_multiple_rows": int(
            (df.groupby(["Latitude", "Longitude"]).size() > 1).sum()),
        "n_rows_sharing_a_coord_pair": int(
            df.groupby(["Latitude", "Longitude"])["Latitude"].transform("size").gt(1).sum()),
        "top_reused_coords": {
            f"{a},{b}": int(c) for (a, b), c in
            df.groupby(["Latitude", "Longitude"]).size().sort_values(
                ascending=False).head(10).items()},
    },
}

# ------------------------------------------------------------ Facility ID dupes, characterised
fid = df["Facility ID"]
vc = fid.value_counts()
dups = vc[vc > 1]
sub = df[fid.isin(dups.index)]
g = sub.groupby("Facility ID")
R["facility_id_dupes"] = {
    "n_dup_ids": int(len(dups)),
    "n_rows": int(len(sub)),
    "groups_identical_on_all_cols": int(g.apply(lambda x: len(x.drop_duplicates()) == 1).sum()),
    "groups_same_name": int(g["hospital_name"].nunique().eq(1).sum()),
    "groups_same_name_and_coords": int(
        g.apply(lambda x: x["hospital_name"].nunique() == 1
                and x["Latitude"].nunique() == 1).sum()),
    "groups_differing_state": int(g["new_state_name"].nunique().gt(1).sum()),
    "groups_differing_facility_type": int(g["Facility Type"].nunique().gt(1).sum()),
    "biggest_id": str(dups.index[0]),
}
big = df[fid == dups.index[0]]
R["facility_id_dupes"]["biggest_id_sample"] = big[
    ["Facility ID", "hospital_name", "Facility Type", "new_state_name",
     "new_district_name", "Latitude"]].head(6).to_dict("records")
R["facility_id_dupes"]["biggest_id_distinct_names"] = int(big["hospital_name"].nunique())
R["facility_id_dupes"]["biggest_id_distinct_states"] = sorted(
    big["new_state_name"].unique().tolist())
# a couple of readable 2-row examples where content differs
ex = []
for k in dups.index[:400]:
    grp = df[fid == k]
    if len(grp) == 2 and len(grp.drop_duplicates()) == 2:
        diff = [c for c in df.columns if grp.iloc[0][c] != grp.iloc[1][c]]
        ex.append({"facility_id": str(k), "rows": [int(i) for i in grp.index],
                   "differing_columns": diff,
                   "name_a": grp.iloc[0]["hospital_name"],
                   "name_b": grp.iloc[1]["hospital_name"]})
    if len(ex) >= 6:
        break
R["facility_id_dupes"]["examples_2row_differing"] = ex

# ------------------------------------------------------------ geo defects, detailed
nz = lat.notna() & lon.notna() & ~((lat == 0) & (lon == 0))
inbox = lat.between(6, 38) & lon.between(68, 98)
swapped = lon.between(6, 38) & lat.between(68, 98)
R["geo_detail"] = {
    "n_rows": N,
    "null_either": int((lat.isna() | lon.isna()).sum()),
    "zero_zero": int(((lat == 0) & (lon == 0)).sum()),
    "valid_in_india": int(inbox.sum()),
    "out_of_bbox_nonnull_nonzero": int((nz & ~inbox).sum()),
    "possibly_swapped": int(swapped.sum()),
    "swapped_examples": [
        {"row": int(i), "Latitude": df.at[i, "Latitude"], "Longitude": df.at[i, "Longitude"],
         "state": df.at[i, "new_state_name"], "name": df.at[i, "hospital_name"]}
        for i in df.index[swapped][:10]],
    "absurd_magnitude": {
        "n_abs_lat_gt_90": int((lat.abs() > 90).sum()),
        "n_abs_lon_gt_180": int((lon.abs() > 180).sum()),
        "examples": [
            {"row": int(i), "Latitude": df.at[i, "Latitude"],
             "Longitude": df.at[i, "Longitude"], "name": df.at[i, "hospital_name"],
             "state": df.at[i, "new_state_name"]}
            for i in df.index[(lat.abs() > 90) | (lon.abs() > 180)][:10]],
    },
    "unparseable_rows": [
        {"row": int(i), "Latitude": df.at[i, "Latitude"],
         "Longitude": df.at[i, "Longitude"], "gmaps": df.at[i, "Google Maps Link"],
         "name": df.at[i, "hospital_name"]}
        for i in df.index[(lat.isna() | lon.isna())][:20]],
    "in_ocean_or_foreign_sample": [
        {"row": int(i), "lat": float(lat[i]), "lon": float(lon[i]),
         "state": df.at[i, "new_state_name"], "name": df.at[i, "hospital_name"]}
        for i in df.index[nz & ~inbox & ~swapped][:15]],
}
# how far is the point from its declared state? crude: count out-of-bbox per state
oob = (nz & ~inbox)
R["geo_detail"]["out_of_bbox_by_state"] = {
    str(k): int(v) for k, v in
    df.loc[oob, "new_state_name"].value_counts().head(15).items()}

# ------------------------------------------------------------ name / address
R["name_address"] = {
    "hospital_name_blank": int(df["hospital_name"].eq("").sum()),
    "hospital_name_blank_rows": [int(i) for i in df.index[df["hospital_name"].eq("")][:25]],
    "hospital_name_len": {
        "min": int(df.loc[~df["hospital_name"].eq(""), "hospital_name"].str.len().min()),
        "max": int(df["hospital_name"].str.len().max()),
        "p50": int(df["hospital_name"].str.len().quantile(.5)),
    },
    "n_names_len_le_3": int(df["hospital_name"].str.len().between(1, 3).sum()),
    "short_name_examples": df.loc[df["hospital_name"].str.len().between(1, 3),
                                  "hospital_name"].value_counts().head(15).to_dict(),
    "n_names_purely_numeric": int(df["hospital_name"].str.fullmatch(r"[\d\s\.\-]+").sum()),
    "n_names_needing_strip": int(
        (df["hospital_name"] != df["hospital_name"].str.strip()).sum()),
    "n_distinct_names": int(df["hospital_name"].nunique()),
    "n_distinct_names_normalised": int(nm.nunique()),
    "top_names": df["hospital_name"].value_counts().head(15).to_dict(),
    "address_blank": int(df["Address"].eq("").sum()),
    "address_len": {
        "min": int(df["Address"].str.len().min()), "max": int(df["Address"].str.len().max()),
        "p50": int(df["Address"].str.len().quantile(.5)),
        "p95": int(df["Address"].str.len().quantile(.95)),
    },
    "n_address_len_lt_10": int(df["Address"].str.len().lt(10).sum()),
    "short_address_examples": df.loc[df["Address"].str.len().lt(10), "Address"]
        .value_counts().head(10).to_dict(),
}
# pincode present inside Address?
pin = df["Address"].str.extract(r"\b([1-9]\d{5})\b")[0]
R["pincode_in_address"] = {
    "n_rows_with_6digit_pin_in_address": int(pin.notna().sum()),
    "pct": round(100.0 * pin.notna().sum() / N, 2),
    "n_distinct_pins": int(pin.nunique()),
    "n_pins_starting_0": int(df["Address"].str.contains(r"\b0\d{5}\b", regex=True).sum()),
    "examples": pin.dropna().head(10).tolist(),
    "note": "no dedicated pincode column exists; this is an extraction from free text",
}

# ------------------------------------------------------------ ER readiness
has_name = ~df["hospital_name"].eq("") & df["hospital_name"].str.len().ge(4)
has_geo = inbox
has_dist = ~df["new_district_name"].eq("")
R["er_readiness"] = {
    "has_name_pct": round(100.0 * has_name.mean(), 3),
    "has_valid_geo_pct": round(100.0 * has_geo.mean(), 3),
    "has_district_pct": round(100.0 * has_dist.mean(), 3),
    "has_state_pct": round(100.0 * (~df["new_state_name"].eq("")).mean(), 3),
    "has_all_three_pct": round(100.0 * (has_name & has_geo & has_dist).mean(), 3),
    "unmatchable_rows": int((~(has_name & has_dist)).sum()),
    "unmatchable_pct": round(100.0 * (~(has_name & has_dist)).mean(), 3),
    "n_rows_name_and_district_but_no_geo": int((has_name & has_dist & ~has_geo).sum()),
}

json.dump(R, open("eda/NHA/scripts/intermediate/_dupes_geo_er.json", "w"), indent=2, default=str)
print(json.dumps({k: v for k, v in R.items() if k != "geo_detail"}, indent=2, default=str)[:9000])
