"""NHA EDA step 7: what actually differs inside repeated-Facility-ID groups,
and how bad the shared-coordinate (geocoder centroid fallback) problem is.
"""
import json
from collections import Counter

import pandas as pd

SRC = "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv"
df = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)
N = len(df)
R = {}

fid = df["Facility ID"]
vc = fid.value_counts()
dups = vc[vc > 1]
sub = df[fid.isin(dups.index)].copy()

# which columns vary within a Facility ID group? (full population of dup groups)
g = sub.groupby("Facility ID")
varying = {}
for c in df.columns:
    if c == "Facility ID":
        continue
    varying[c] = int(g[c].nunique().gt(1).sum())
R["cols_varying_within_facility_id_group"] = dict(
    sorted(varying.items(), key=lambda kv: -kv[1]))
R["n_dup_id_groups"] = int(len(dups))
R["n_groups_with_zero_varying_cols"] = int(
    sum(1 for _ in [None]) and int(g.apply(lambda x: len(x.drop_duplicates()) == 1).sum()))

# concrete 2-row examples where content differs, scanning ALL dup ids
two = dups[dups == 2].index
sub2 = df[fid.isin(two)]
pairs = sub2.groupby("Facility ID")
ex = []
diffcols = Counter()
n_pairs_differing = 0
for k, grp in pairs:
    a, b = grp.iloc[0], grp.iloc[1]
    d = [c for c in df.columns if a[c] != b[c]]
    if d:
        n_pairs_differing += 1
        diffcols[tuple(d)] += 1
        if len(ex) < 8:
            ex.append({"facility_id": str(k), "rows": [int(i) for i in grp.index],
                       "differing_columns": d,
                       "values": {c: [a[c], b[c]] for c in d[:6]}})
R["two_row_groups"] = {
    "n_groups_size_2": int(len(two)),
    "n_differing": n_pairs_differing,
    "n_byte_identical": int(len(two) - n_pairs_differing),
    "top_differing_column_sets": {
        " + ".join(k): int(v) for k, v in diffcols.most_common(12)},
    "examples": ex,
}

# ------------------------------------------------- shared-coordinate fallback
cnt = df.groupby(["Latitude", "Longitude"]).size().sort_values(ascending=False)
big = cnt[cnt >= 50]
R["shared_coords"] = {
    "n_distinct_coord_pairs": int(len(cnt)),
    "n_pairs_shared_by_ge_50_rows": int(len(big)),
    "n_rows_at_a_coord_shared_by_ge_50": int(big.sum()),
    "pct_rows_at_such_coords": round(100.0 * big.sum() / N, 3),
    "n_pairs_shared_by_ge_10_rows": int((cnt >= 10).sum()),
    "n_rows_at_coord_shared_by_ge_10": int(cnt[cnt >= 10].sum()),
    "top_20": [],
}
for (la, lo), c in cnt.head(20).items():
    rows = df[(df["Latitude"] == la) & (df["Longitude"] == lo)]
    R["shared_coords"]["top_20"].append({
        "lat": la, "lon": lo, "n_rows": int(c),
        "n_distinct_names": int(rows["hospital_name"].nunique()),
        "states": sorted(rows["new_state_name"].unique().tolist())[:4],
        "districts": sorted(rows["new_district_name"].unique().tolist())[:6],
        "n_distinct_districts": int(rows["new_district_name"].nunique()),
        "sample_names": rows["hospital_name"].drop_duplicates().head(4).tolist(),
    })

# ------------------------------------------------- 'test' / junk records
junk_pat = r"(?i)^\s*(test|testing|xyz|abc|dummy|sample|demo|asd|qwe|aaa|xxx)\b"
jm = df["hospital_name"].str.match(junk_pat, na=False)
R["junk_name_records"] = {
    "n_rows": int(jm.sum()),
    "value_counts": df.loc[jm, "hospital_name"].value_counts().head(25).to_dict(),
    "example_rows": [int(i) for i in df.index[jm][:15]],
}

json.dump(R, open("eda/NHA/scripts/intermediate/_dupe_anatomy.json", "w"), indent=2, default=str)
print(json.dumps(R, indent=2, default=str)[:11000])
