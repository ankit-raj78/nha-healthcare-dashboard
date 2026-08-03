"""Step 8: pull concrete row examples for issues.md (row index = positional index in the 10530-row parse)."""
import pandas as pd, numpy as np
pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 90)
SRC = "/Users/ankitraj2/asar master data/22_MAY_22_AP_NIN.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
IDX = df.columns[0]; data_cols = [c for c in df.columns if c != IDX]
d = df.loc[~df[data_cols].isna().all(axis=1)].copy()
lat = pd.to_numeric(d["latitude"], errors="coerce"); lon = pd.to_numeric(d["longitude"], errors="coerce")
show = ["SrNo", "Health Facility Name", "latitude", "longitude", "State_Name", "District_Name", "pincode"]

print("--- extreme lon ---")
print(d.assign(_lo=lon).nsmallest(4, "_lo")[show].to_string())
print(d.assign(_lo=lon).nlargest(4, "_lo")[show].to_string())
print("--- extreme lat ---")
print(d.assign(_la=lat).nlargest(4, "_la")[show].to_string())
print("--- lat == lon ---")
eq = d[(lat == lon) & lat.notna() & (lat != 0)]
print(eq[show].to_string())
print("--- lat/lon exactly 0 (sample) ---")
print(d[((lat == 0) | (lon == 0))][show].head(6).to_string())
print("--- lat/lon NULL (sample) ---")
print(d[lat.isna() | lon.isna()][show].head(6).to_string())
print("--- Manual_Pincode #REF! and non-numeric ---")
mp = d["Manual_Pincode"].dropna().str.strip()
print(d.loc[mp[~mp.str.fullmatch(r"\d{6}")].index, ["SrNo","Health Facility Name","Manual_Pincode","Manual_Address","State_Name"]].to_string())
print("--- District_Name with embedded newline ---")
print(d.loc[d["District_Name"].str.contains("\n", na=False), ["SrNo","Health Facility Name","District_Name","Taluka_Name","State_Name"]].head(4).to_string())
print("--- District_Name == '\\N' ---")
print(d.loc[d["District_Name"].str.strip()=="\\N", show].to_string())
print("--- suspicious round pincodes ---")
p = d["pincode"].dropna()
sus = p[p.str.endswith("0000") | p.isin(["500000","110000","400000","600000","700000","000000"])]
print(sus.value_counts().to_dict())
print(d.loc[sus.index, show].head(8).to_string())
print("--- Balrampur case collision ---")
print(d.loc[d["District_Name"].str.strip().str.lower()=="balrampur", ["SrNo","Health Facility Name","District_Name","State_Name"]].to_string())
print("--- Manually_added raw variants w/ row ids ---")
for v in d["Manually_added"].dropna().unique():
    i = d.index[d["Manually_added"]==v][0]
    print(f"  {v!r:8s} first at row {i}  SrNo={d.at[i,'SrNo']}  name={d.at[i,'Health Facility Name']!r}")
print("--- Coder raw variants w/ row ids ---")
for v in d["Coder"].dropna().unique():
    i = d.index[d["Coder"]==v][0]
    print(f"  {v!r:12s} first at row {i}  SrNo={d.at[i,'SrNo']}")
print("--- duplicate-flagging Notes ---")
print(d.loc[d["Notes"].str.contains("Duplicate|Same as row", case=False, na=False), ["SrNo","Health Facility Name","Notes","State_Name"]].to_string())
print("--- Address sentinel examples w/ manual fill ---")
sen = d[d["Address"].isin(["\\N","0","-"]) & d["Manual_Address"].notna()]
print(sen[["SrNo","Health Facility Name","Address","Manual_Address"]].head(6).to_string())
print("--- Auraiya altitude 2700 rows ---")
print(d.loc[(d["District_Name"]=="Auraiya") & (d["altitude"]=="2700"), ["SrNo","Health Facility Name","altitude","latitude","longitude"]].to_string())
print("--- Uttarakhand 5985 m ---")
print(d.loc[d["altitude"]=="5985", ["SrNo","Health Facility Name","altitude","latitude","longitude","District_Name","State_Name"]].to_string())
print("--- mobile numbers in landline_number ---")
ll = d["landline_number"].dropna().str.strip(); dg = ll.str.replace(r"\D","",regex=True)
mob = ll[(dg.str.len()==10) & dg.str[0].isin(list("6789"))]
print(d.loc[mob.index[:5], ["SrNo","Health Facility Name","landline_number","State_Name"]].to_string())
print("--- 13 near-exact dupe pairs, SrNo listing ---")
nokey=[c for c in data_cols if c not in ("SrNo","Non filled numbering")]
dup=d[d.duplicated(subset=nokey,keep=False)]
print(dup.groupby(dup["Health Facility Name"].str.lower())["SrNo"].apply(list).to_string())
print("--- Telengana rows sample ---")
print(d.loc[d["State_Name"]=="Telengana", show].head(3).to_string())
print("--- coord shared by 57 rows ---")
print(d.loc[(d["latitude"]=="11.664325")&(d["longitude"]=="78.1460142"), ["SrNo","Health Facility Name","District_Name","Facility Type"]].head(8).to_string())
