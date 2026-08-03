"""Step 6: addenda — altitude provenance, manual-pincode adjudication, emails, blank rows, name/geo near-dupes."""
import pandas as pd, numpy as np, re, json
pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 130)

SRC = "/Users/ankitraj2/asar master data/22_MAY_22_AP_NIN.csv"
READ = dict(encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = pd.read_csv(SRC, **READ)
IDX = df.columns[0]
data_cols = [c for c in df.columns if c != IDX]
blank = df[data_cols].isna().all(axis=1)
d = df.loc[~blank].copy()
N = len(d)

print("=== the 3 interior blank rows ===")
print(df.loc[blank & (df.index < 10329), [IDX]].to_string())
print("neighbours of positional 4789:")
print(df.loc[4787:4791, [IDX, "SrNo", "Health Facility Name", "State_Name"]].to_string())

print("\n=== altitude provenance ===")
alt = pd.to_numeric(d["altitude"], errors="coerce")
lat = pd.to_numeric(d["latitude"], errors="coerce"); lon = pd.to_numeric(d["longitude"], errors="coerce")
in_bbox = lat.between(6, 38) & lon.between(68, 98)
print("altitude by state: fraction non-zero (top/bottom 10)")
fr = d.assign(_nz=(alt != 0) & alt.notna()).groupby("State_Name")["_nz"].agg(["mean", "size"]).sort_values("mean", ascending=False)
print(fr.head(10).to_string()); print("..."); print(fr.tail(10).to_string())
print("\naltitude nonzero vs SrNo bin:")
sr = pd.to_numeric(d["SrNo"], errors="coerce")
print(d.assign(_nz=(alt != 0) & alt.notna(), _b=pd.cut(sr, [0,5000,20000,50000,100000,200000])).groupby("_b", observed=True)["_nz"].agg(["mean","size"]).to_string())
print("\nplausibility: altitude vs known state means")
print(d.assign(_a=alt).loc[alt > 0].groupby("State_Name")["_a"].agg(["median","max","size"]).sort_values("median", ascending=False).head(12).to_string())
print("\nsuspicious: Auraiya UP altitude=2700 rows (real elevation ~130m):")
print(d.loc[(d["District_Name"] == "Auraiya"), ["Health Facility Name","altitude","latitude","longitude"]].head(8).to_string())
print("\ndecimal vs integer altitudes:", int(d.loc[alt.notna() & (alt != 0), "altitude"].str.contains(r"\.").sum()), "have decimals of", int(((alt != 0) & alt.notna()).sum()))

print("\n=== Manual_Pincode adjudication (does Manual_Address confirm it?) ===")
sub = d[d["Manual_Pincode"].notna() & d["pincode"].notna()].copy()
dis = sub[sub["pincode"].str.strip() != sub["Manual_Pincode"].str.strip()]
print("disagreeing rows:", len(dis))
pin_in_maddr = dis.apply(lambda r: (str(r["Manual_Address"]) or "").find(str(r["Manual_Pincode"]).strip()) >= 0, axis=1)
print("  Manual_Pincode literally appears in Manual_Address:", int(pin_in_maddr.sum()), "of", len(dis))
auto_in_maddr = dis.apply(lambda r: (str(r["Manual_Address"]) or "").find(str(r["pincode"]).strip()) >= 0, axis=1)
print("  auto pincode appears in Manual_Address:", int(auto_in_maddr.sum()))
print(dis[["Health Facility Name","pincode","Manual_Pincode","Manual_Address","District_Name","State_Name"]].head(10).to_string())

print("\n=== emails found in landline_number ===")
m = d["landline_number"].str.contains(r"[\w\.]+@[\w\.]+", regex=True, na=False)
print(d.loc[m, ["Health Facility Name","landline_number","State_Name"]].to_string())

print("\n=== near-dupe (name+geo rounded to 3dp) ===")
def norm(s): return (s.astype(str).str.strip().str.lower().str.replace(r"[^\w\s]"," ",regex=True).str.replace(r"\s+"," ",regex=True).str.strip())
d["_n"] = norm(d["Health Facility Name"])
d["_la"] = lat.round(3); d["_lo"] = lon.round(3)
g = d[in_bbox]
n1 = int(g.duplicated(subset=["_n","_la","_lo"]).sum())
print("dupes on normalized name + geo rounded 3dp:", n1, f"({n1/N*100:.2f}%)")
n2 = int(g.duplicated(subset=["_n", "_la", "_lo"], keep=False).sum())
print("rows involved in such groups:", n2)
# name+district near dupes involved
d2 = d[d.duplicated(subset=["_n","District_Name"], keep=False)]
print("rows involved in name+district dupe groups:", len(d2), f"({len(d2)/N*100:.2f}%)")
# geo-only clusters (same exact coords, different names) - shared block-level geocode
gd = g.groupby(["latitude","longitude"]).agg(n=("_n","size"), names=("_n","nunique"))
multi = gd[(gd["n"] > 1) & (gd["names"] > 1)]
print("coord pairs shared by >1 DIFFERENT facility:", len(multi), "covering rows:", int(multi["n"].sum()))
print(multi.sort_values("n", ascending=False).head(6).to_string())

print("\n=== Facility Type vs name keyword agreement (spot check) ===")
ct = pd.crosstab(d["Facility Type"], d["Health Facility Name"].str.contains(r"\bCHC\b", case=False, na=False))
print(ct.to_string())

print("\n=== District_Name cleanliness detail ===")
dn = d["District_Name"].str.strip()
print("distinct after strip:", dn.nunique(), " (raw:", d["District_Name"].nunique(), ")")
print("values ending in ' District':", dn.str.endswith("District").sum(), "distinct:", dn[dn.str.endswith("District")].nunique())
print("would collapse to:", sorted(set(dn[dn.str.endswith("District")].str.replace(r"\s*District$","",regex=True)) & set(dn))[:20])
print("case-variant collisions:", int(dn.nunique() - dn.str.lower().nunique()))
lc = dn.str.lower(); coll = lc.groupby(lc).size()
vv = dn.groupby(lc).unique()
print("examples of case/space variants:", [list(x) for x in vv[vv.map(len) > 1].head(8)])
