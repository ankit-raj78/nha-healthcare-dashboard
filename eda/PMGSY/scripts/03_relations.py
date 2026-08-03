"""Step 3: column redundancy, duplicates, geo, dates, keys, granularity."""
import pandas as pd, numpy as np, re, json
from collections import Counter

SRC = "/Users/ankitraj2/asar master data/21_JULY_23_SRK_PMGSY_validated_homogenized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = df.dropna(how="all").reset_index(drop=True)
N = len(df)
print("N =", N)

print("\n### 1. EXACT COLUMN-PAIR EQUALITY (parsed set vs source) ###")
pairs = [("MASTER_FACILITY_DESC", "Hospital Name"), ("ADDRESS", "Street/Locality"),
         ("HABITATION_NAME", "Habitation"), ("BLOCK_NAME", "Block"),
         ("DISTRICT_NAME", "City/District"), ("STATE_NAME", "State"),
         ("Postcode_py", "Pincode")]
for a, b in pairs:
    eq = (df[a].fillna("\x00") == df[b].fillna("\x00")).sum()
    print(f"  {a:30s} == {b:20s}: {eq}/{N} ({100*eq/N:.3f}%)  mismatches={N-eq}")
    if eq != N:
        m = df[df[a].fillna("\x00") != df[b].fillna("\x00")]
        print("    sample mismatches:", m[[a, b]].head(5).to_dict("records"))

print("\n### 2. Formatted Address reconstruction ###")
recon = (df["Hospital Name"].fillna("") + ", " + df["Street/Locality"].fillna("") + ", "
         + df["Habitation"].fillna("") + ", " + df["Block"].fillna("") + ", "
         + df["City/District"].fillna("") + ", " + df["State"].fillna("") + ", "
         + df["Country"].fillna("") + ", " + df["Pincode"].fillna(""))
print("  exact match to Formatted Address:", (recon == df["Formatted Address"]).sum(), "/", N)
mm = df[recon != df["Formatted Address"]]
if len(mm):
    print("  sample mismatch idx:", mm.index[:3].tolist())
    for i in mm.index[:2]:
        print("    recon:", recon[i][:160]); print("    actual:", df.loc[i, "Formatted Address"][:160])

print("\n### 3. Pincode vs address_py pincode ###")
apy_pin = df["address_py"].fillna("").str.extract(r"\b(\d{6})\b")[0]
print("  address_py has 6-digit token:", apy_pin.notna().sum(), f"({100*apy_pin.notna().sum()/N:.2f}%)")
both = apy_pin.notna() & df["Pincode"].notna()
print("  agree where both present:", (apy_pin[both] == df["Pincode"][both]).sum(), "/", both.sum(),
      f"({100*(apy_pin[both]==df['Pincode'][both]).sum()/both.sum():.2f}%)")
# where address_py has no pin, is Pincode still populated?
print("  Pincode populated but address_py lacks 6-digit:", (df['Pincode'].notna() & apy_pin.isna()).sum())

print("\n### 4. Pincode validity ###")
p = df["Pincode"].dropna()
print("  all 6 chars & digits:", p.str.fullmatch(r"\d{6}").sum(), "/", len(p))
print("  leading zero (invalid for India):", p.str.startswith("0").sum())
print("  first-digit distribution:", Counter(p.str[0]).most_common())

print("\n### 5. GEO QUALITY ###")
lat = pd.to_numeric(df["LATITUDE"], errors="coerce")
lon = pd.to_numeric(df["LONGITUDE"], errors="coerce")
print("  lat parse fail:", lat.isna().sum(), " lon parse fail:", lon.isna().sum())
print("  lat min/max:", lat.min(), lat.max(), " lon min/max:", lon.min(), lon.max())
zero = ((lat == 0) | (lon == 0)).sum()
nullg = (lat.isna() | lon.isna()).sum()
inbox = ((lat >= 6) & (lat <= 38) & (lon >= 68) & (lon <= 98))
print("  in India bbox:", inbox.sum(), f"({100*inbox.sum()/N:.2f}%)")
print("  zero:", zero, " null:", nullg)
oob = (~inbox) & lat.notna() & lon.notna()
print("  out of bbox:", oob.sum())
if oob.sum():
    print(df.loc[oob, ["Sr. No. ", "STATE_NAME", "DISTRICT_NAME", "LATITUDE", "LONGITUDE"]].head(20).to_string())
swap = ((lon >= 6) & (lon <= 38) & (lat >= 68) & (lat <= 98)).sum()
print("  possibly swapped (lat/lon reversed & would be valid):", swap)
# decimal precision
prec = df["LATITUDE"].dropna().str.split(".").str[-1].str.len()
print("  lat decimal-places distribution:", Counter(prec).most_common(12))

print("\n### 6. DUPLICATES ###")
print("  exact dupes over ALL 24 cols:", df.duplicated().sum())
noSr = [c for c in df.columns if c != "Sr. No. "]
print("  exact dupes ignoring Sr. No.:", df[noSr].duplicated().sum())
key_ng = ["MASTER_FACILITY_DESC", "LATITUDE", "LONGITUDE"]
print("  dupes on (name, lat, lon):", df.duplicated(subset=key_ng).sum())
print("  dupes on (lat, lon):", df.duplicated(subset=["LATITUDE", "LONGITUDE"]).sum())
def norm(s): return s.fillna("").str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
nm = norm(df["MASTER_FACILITY_DESC"])
r4 = lat.round(4).astype(str) + "," + lon.round(4).astype(str)
r3 = lat.round(3).astype(str) + "," + lon.round(3).astype(str)
print("  near-dupe normname + latlon@4dp:", pd.DataFrame({"n": nm, "g": r4}).duplicated().sum())
print("  near-dupe normname + latlon@3dp:", pd.DataFrame({"n": nm, "g": r3}).duplicated().sum())
print("  near-dupe normname + district:", pd.DataFrame({"n": nm, "d": df["DISTRICT_NAME"]}).duplicated().sum())
print("  dupes on (HAB_CODE, normname):", pd.DataFrame({"h": df["HAB_CODE"], "n": nm}).duplicated().sum())

print("\n### 7. HAB_CODE as key / granularity ###")
h = df["HAB_CODE"]
print("  distinct HAB_CODE:", h.nunique(), "of", N, "rows -> unique?", h.is_unique)
vc = h.value_counts()
print("  rows in multi-row hab codes:", vc[vc > 1].sum(), "across", (vc > 1).sum(), "hab codes")
print("  max rows per hab code:", vc.max())
print("  HAB_CODE all digits:", h.dropna().str.fullmatch(r"\d+").sum(), "/", h.notna().sum())
print("  HAB_CODE length dist:", Counter(h.dropna().str.len()).most_common())
# does HAB_CODE collide across states?
g = df.groupby("HAB_CODE")[["STATE_NAME", "DISTRICT_NAME", "HABITATION_NAME"]].nunique()
print("  hab codes spanning >1 STATE:", (g["STATE_NAME"] > 1).sum())
print("  hab codes spanning >1 DISTRICT:", (g["DISTRICT_NAME"] > 1).sum())
print("  hab codes spanning >1 HABITATION_NAME:", (g["HABITATION_NAME"] > 1).sum())
print("\n  --- top repeated HAB_CODE detail (440318) ---")
print(df[df["HAB_CODE"] == "440318"][["Sr. No. ", "STATE_NAME", "DISTRICT_NAME", "BLOCK_NAME",
      "HABITATION_NAME", "MASTER_FACILITY_DESC", "LATITUDE", "LONGITUDE", "SUB_CATEGORY"]].head(50).to_string())

print("\n  --- a mid-multiplicity example ---")
mid = vc[vc == 3].index[:2]
for c in mid:
    print(df[df["HAB_CODE"] == c][["Sr. No. ", "STATE_NAME", "DISTRICT_NAME", "HABITATION_NAME",
          "MASTER_FACILITY_DESC", "ADDRESS", "LATITUDE", "LONGITUDE"]].to_string())

print("\n### 8. FILE_UPLOAD_DATE ###")
d = pd.to_datetime(df["FILE_UPLOAD_DATE"], format="%d-%b-%y", errors="coerce")
print("  parsed:", d.notna().sum(), " failed(non-null):", (df["FILE_UPLOAD_DATE"].notna() & d.isna()).sum(),
      " null:", df["FILE_UPLOAD_DATE"].isna().sum())
print("  range:", d.min(), "->", d.max())
print("  by year:", d.dt.year.value_counts().sort_index().to_dict())
print("  by year-month (top):", d.dt.to_period("M").value_counts().sort_index().to_dict())
print("  rows with null date, sample idx:", df.index[df["FILE_UPLOAD_DATE"].isna()][:10].tolist())

print("\n### 9. Granularity: one row = ? ###")
print("  distinct (STATE,DISTRICT,BLOCK,HABITATION_NAME):",
      df.duplicated(subset=["STATE_NAME","DISTRICT_NAME","BLOCK_NAME","HABITATION_NAME"]).pipe(lambda s: N - s.sum()))
print("  distinct (HAB_CODE, MASTER_FACILITY_DESC, LATITUDE, LONGITUDE):",
      N - df.duplicated(subset=["HAB_CODE","MASTER_FACILITY_DESC","LATITUDE","LONGITUDE"]).sum())
print("  Sr. No. numeric & contiguous?")
sn = pd.to_numeric(df["Sr. No. "], errors="coerce")
print("   min/max:", sn.min(), sn.max(), " n:", sn.notna().sum(), " unique:", sn.nunique(),
      " missing ints in 1..max:", len(set(range(1, int(sn.max())+1)) - set(sn.dropna().astype(int))))
missing = sorted(set(range(1, int(sn.max())+1)) - set(sn.dropna().astype(int)))
print("   first 20 missing serials:", missing[:20])
