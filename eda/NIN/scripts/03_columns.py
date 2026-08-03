"""Step 3: full per-column profile on the 10,327 effective rows."""
import pandas as pd, numpy as np, re, json
pd.set_option("display.width", 250)

SRC = "/Users/ankitraj2/asar master data/22_MAY_22_AP_NIN.csv"
READ = dict(encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = pd.read_csv(SRC, **READ)
IDX = df.columns[0]
data_cols = [c for c in df.columns if c != IDX]
allblank = df[data_cols].isna().all(axis=1)
print("interior blank rows (positional):", allblank[allblank].index[allblank[allblank].index < 10329].tolist())
d = df.loc[~allblank].copy()
print("effective rows:", len(d))

def show(c, topn=20):
    s = d[c]
    print(f"\n########## {c} ##########")
    print(f"non_null={s.notna().sum()} ({s.notna().mean()*100:.2f}%)  distinct={s.nunique()}")
    L = s.dropna().str.len()
    if len(L):
        print(f"len min/med/mean/p95/max = {L.min()}/{L.median()}/{L.mean():.1f}/{L.quantile(.95):.0f}/{L.max()}")
    vc = s.value_counts(dropna=False)
    if s.nunique() < 50:
        print("FULL value_counts:")
        print(vc.to_string())
    else:
        print(f"top {topn}:")
        print(vc.head(topn).to_string())
        print("examples:", s.dropna().sample(min(6, s.notna().sum()), random_state=7).tolist())

for c in ["Facility Type", "State_Name", "Manually_added", "Coder", "altitude", "Notes"]:
    show(c)

for c in ["Health Facility Name", "Manual Health Facility Name", "Address", "street",
          "landmark", "locality", "pincode", "landline_number", "District_Name",
          "Taluka_Name", "Block_Name", "Manual_Address", "Manual_Pincode"]:
    show(c, topn=12)
