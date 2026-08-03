import pandas as pd, numpy as np, re
from collections import Counter
SRC = "/Users/ankitraj2/asar master data/21_JULY_23_SRK_PMGSY_validated_homogenized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = df.dropna(how="all").reset_index(drop=True)
N=len(df)

print("### Formatted Address final rule (case-insensitive block==habitation drop) ###")
def build3(r):
    parts=[r["Hospital Name"], r["Street/Locality"], r["Habitation"]]
    if str(r["Block"]).lower() != str(r["Habitation"]).lower(): parts.append(r["Block"])
    parts += [r["City/District"], r["State"], r["Country"], r["Pincode"]]
    return ", ".join("" if pd.isna(p) else str(p) for p in parts)
b=df.apply(build3,axis=1)
print("  matches:",(b==df["Formatted Address"]).sum(),"/",N)
mm=df.index[b!=df["Formatted Address"]]
print("  mismatches:",len(mm))
for i in mm[:6]:
    print("   built :",b[i][:200]); print("   actual:",df.loc[i,"Formatted Address"][:200])

print("\n### The one MASTER_FACILITY_DESC != Hospital Name row ###")
r=df[df["MASTER_FACILITY_DESC"]!=df["Hospital Name"]]
print(r[["Sr. No. ","STATE_NAME","DISTRICT_NAME","MASTER_FACILITY_DESC","Hospital Name","Formatted Address"]].to_string())

print("\n### SUB_CATEGORY x STATE (top) ###")
ct=pd.crosstab(df.STATE_NAME,df.SUB_CATEGORY)
print(ct.sort_values("Bedded Hospital",ascending=False).to_string())

print("\n### Pincode present but address_py lacks pincode -> where from? ###")
apy_pin=df["address_py"].fillna("").str.extract(r"\b(\d{6})\b")[0]
sub=df[apy_pin.isna()]
print("  n:",len(sub))
print(sub[["Sr. No. ","STATE_NAME","DISTRICT_NAME","Pincode","address_py"]].head(8).to_string())

print("\n### numeric summary of LAT/LON ###")
lat=pd.to_numeric(df.LATITUDE); lon=pd.to_numeric(df.LONGITUDE)
print(pd.DataFrame({"LATITUDE":lat,"LONGITUDE":lon}).describe(percentiles=[.01,.25,.5,.75,.99]).to_string())

print("\n### HAB_CODE numeric range ###")
h=pd.to_numeric(df.HAB_CODE)
print("  min/max:",h.min(),h.max())
print("  by-state min/max sample:")
print(df.assign(h=h).groupby("STATE_NAME")["h"].agg(["min","max","nunique"]).to_string())

print("\n### Sr. No. trailing-space header confirmed; other header oddities ###")
print([repr(c) for c in df.columns])

print("\n### null counts per column ###")
for c in df.columns:
    print(f"  {c!r}: nulls={df[c].isna().sum()}")

print("\n### rows with embedded newline in ADDRESS -- example ###")
ex=df[df.ADDRESS.fillna("").str.contains("\n")]
print("  n:",len(ex))
print("  example Sr. No.:",ex["Sr. No. "].head(3).tolist())
print("  example value:",repr(ex.ADDRESS.iloc[0]))
print("  does Formatted Address also carry it?", ex["Formatted Address"].str.contains("\n").sum())
