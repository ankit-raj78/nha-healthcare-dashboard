"""NHA EDA step 8: decisive test of the '24/7 fan-out' hypothesis.

Hypothesis: Facility ID is genuinely the entity key. The 62,300 repeated IDs are
a cross-product artifact where one facility got emitted once per 24/7 value.
"""
import json

import pandas as pd

SRC = "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv"
df = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)
N = len(df)
R = {}

fid = df["Facility ID"]
vc = fid.value_counts()
dups = vc[vc > 1]
sub = df[fid.isin(dups.index)]
g = sub.groupby("Facility ID")["24/7"]

R["hypothesis_test"] = {
    "n_dup_id_groups": int(len(dups)),
    "groups_where_24x7_has_both_yes_and_no": int(g.nunique().eq(2).sum()),
    "groups_where_24x7_constant": int(g.nunique().eq(1).sum()),
    "pct_dup_groups_explained_by_24x7_split": round(
        100.0 * g.nunique().eq(2).sum() / len(dups), 2),
}

# Drop 24/7 -> how many rows collapse?
nodrop = df.drop(columns=["24/7"])
R["collapse_after_dropping_24x7"] = {
    "n_rows_before": N,
    "n_distinct_rows_ignoring_24x7": int(len(nodrop.drop_duplicates())),
    "n_rows_eliminated": int(N - len(nodrop.drop_duplicates())),
}
# Is Facility ID unique once you dedupe on everything-but-24/7?
collapsed = nodrop.drop_duplicates()
R["collapse_after_dropping_24x7"]["facility_id_unique_after_collapse"] = bool(
    collapsed["Facility ID"].is_unique)
cvc = collapsed["Facility ID"].value_counts()
R["collapse_after_dropping_24x7"]["n_ids_still_repeated"] = int((cvc > 1).sum())
R["collapse_after_dropping_24x7"]["n_rows_after_collapse"] = int(len(collapsed))

# What does 24/7 look like once you know it fans out?
R["24x7_reliability"] = {
    "overall_value_counts": df["24/7"].value_counts().to_dict(),
    "n_yes_rows": int(df["24/7"].eq("yes").sum()),
    "n_facilities_with_a_yes_row": int(df.loc[df["24/7"].eq("yes"), "Facility ID"].nunique()),
    "n_facilities_with_a_no_row": int(df.loc[df["24/7"].eq("no"), "Facility ID"].nunique()),
    "n_facilities_with_both": int(
        df.groupby("Facility ID")["24/7"].nunique().eq(2).sum()),
    "n_facilities_total": int(df["Facility ID"].nunique()),
}
b = R["24x7_reliability"]
b["pct_facilities_with_contradictory_24x7"] = round(
    100.0 * b["n_facilities_with_both"] / b["n_facilities_total"], 2)

# does the same fan-out logic explain ABDM Enabled / Ownership? (control test)
for c in ["ABDM Enabled", "Ownership", "Facility Type", "new_state_name"]:
    R.setdefault("control_columns_varying_in_dup_groups", {})[c] = int(
        sub.groupby("Facility ID")[c].nunique().gt(1).sum())

json.dump(R, open("eda/NHA/scripts/intermediate/_24x7.json", "w"), indent=2, default=str)
print(json.dumps(R, indent=2, default=str))
