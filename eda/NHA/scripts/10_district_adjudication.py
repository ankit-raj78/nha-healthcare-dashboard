"""NHA EDA step 10: adjudicate District_name vs new_district_name properly.

The step-9 substring test was invalid ('una' matches 'ARUNachal'). Redo with
word-boundary matching on a normalised Address.
"""
import json
import re

import pandas as pd

SRC = "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv"
df = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)
N = len(df)
R = {}

def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s.lower())).strip()

addr_n = (" " + df["Address"].map(norm) + " ")
old_n = df["District_name"].map(norm)
new_n = df["new_district_name"].map(norm)

def wb_in(needle_series, hay_series):
    return [bool(n) and (" " + n + " ") in h
            for n, h in zip(needle_series, hay_series)]

R["wordboundary_district_in_address_full_population"] = {
    "District_name_found_in_Address": int(sum(wb_in(old_n, addr_n))),
    "new_district_name_found_in_Address": int(sum(wb_in(new_n, addr_n))),
    "n_rows": N,
    "note": "word-boundary match of the district token inside the normalised Address",
}

# the disagreeing rows
mm_mask = old_n != new_n
mm = df[mm_mask]
o = pd.Series(wb_in(old_n[mm_mask], addr_n[mm_mask]), index=mm.index)
n_ = pd.Series(wb_in(new_n[mm_mask], addr_n[mm_mask]), index=mm.index)
R["disagreeing_rows"] = {
    "n": int(mm_mask.sum()),
    "old_matches_address": int(o.sum()),
    "new_matches_address": int(n_.sum()),
    "neither_matches": int((~o & ~n_).sum()),
    "both_match": int((o & n_).sum()),
    "verdict": None,
}
d = R["disagreeing_rows"]
d["verdict"] = (
    "Neither side is trustworthy on the disagreeing rows: "
    f"{d['neither_matches']}/{d['n']} rows have a district value that appears on "
    "neither side of the Address text.")

R["disagreeing_examples"] = [
    {"row": int(i), "District_name": df.at[i, "District_name"],
     "new_district_name": df.at[i, "new_district_name"],
     "district_code": df.at[i, "district_code"],
     "new_state_name": df.at[i, "new_state_name"],
     "Address": df.at[i, "Address"]}
    for i in mm.index[:12]]

# 'Not Found' sentinel
nf = df["District_name"].map(norm).eq("not found")
R["district_name_not_found"] = {
    "n_rows": int(nf.sum()),
    "their_new_district_name": df.loc[nf, "new_district_name"].value_counts().head(10).to_dict(),
    "example_rows": [
        {"row": int(i), "new_district_name": df.at[i, "new_district_name"],
         "Address": df.at[i, "Address"][:100]} for i in df.index[nf][:6]],
}

# Does new_district_name at least belong to the right state? Use LGD-style check:
# district_code must be unique within the dataset, and each district should map to
# exactly one state. Test that.
gs = df.groupby("new_district_name")["new_state_name"].nunique()
R["district_state_consistency"] = {
    "n_districts_spanning_multiple_states": int(gs.gt(1).sum()),
    "examples": {str(k): sorted(df.loc[df["new_district_name"] == k,
                                       "new_state_name"].unique().tolist())
                 for k in gs[gs > 1].head(10).index},
}
gs2 = df.groupby("District_name")["new_state_name"].nunique()
R["district_state_consistency"]["old_District_name_spanning_multiple_states"] = int(gs2.gt(1).sum())
R["district_state_consistency"]["old_examples"] = {
    str(k): sorted(df.loc[df["District_name"] == k, "new_state_name"].unique().tolist())[:6]
    for k in gs2[gs2 > 1].head(10).index}

# how many distinct districts per state vs reality-ish sanity
R["districts_per_state"] = {
    str(k): int(v) for k, v in
    df.groupby("new_state_name")["new_district_name"].nunique().sort_values(
        ascending=False).items()}
R["rows_per_state"] = {
    str(k): int(v) for k, v in df["new_state_name"].value_counts().items()}

json.dump(R, open("eda/NHA/scripts/intermediate/_district_adj.json", "w"), indent=2, default=str)
print(json.dumps(R, indent=2, default=str)[:8000])
