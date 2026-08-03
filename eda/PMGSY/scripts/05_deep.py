"""Step 5: fix earlier bugs + near-dupe quantification + ER readiness."""
import pandas as pd, numpy as np, re
from collections import Counter

SRC = "/Users/ankitraj2/asar master data/21_JULY_23_SRK_PMGSY_validated_homogenized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = df.dropna(how="all").reset_index(drop=True)
N = len(df)
lat = pd.to_numeric(df["LATITUDE"]); lon = pd.to_numeric(df["LONGITUDE"])

print("### A2. Formatted Address rule: drop Block when Block==Habitation ###")
def build2(r):
    parts = [r["Hospital Name"], r["Street/Locality"], r["Habitation"]]
    if r["Block"] != r["Habitation"]:
        parts.append(r["Block"])
    parts += [r["City/District"], r["State"], r["Country"], r["Pincode"]]
    return ", ".join("" if pd.isna(p) else p for p in parts)
b2 = df.apply(build2, axis=1)
print("  matches:", (b2 == df["Formatted Address"]).sum(), "/", N)
mm = df.index[b2 != df["Formatted Address"]]
print("  mismatches:", len(mm))
for i in mm[:5]:
    print("   built :", b2[i][:190]); print("   actual:", df.loc[i, "Formatted Address"][:190])

print("\n### F2. address_py state token (correct extraction) ###")
apy = df["address_py"].fillna("")
def st_from(a):
    p = [x.strip() for x in a.split(",")]
    p = [x for x in p if x]
    if p and p[-1] == "India": p = p[:-1]
    if p and re.fullmatch(r"\d{6}", p[-1]): p = p[:-1]
    return p[-1] if p else ""
apy_state = apy.map(st_from)
eq = apy_state.str.lower().str.replace(r"\s+", " ", regex=True) == df["STATE_NAME"].str.lower()
print("  geocoded state == STATE_NAME:", eq.sum(), f"({100*eq.sum()/N:.2f}%)")
print("  top mismatch pairs:", Counter(zip(df.loc[~eq,"STATE_NAME"], apy_state[~eq])).most_common(20))
def dt_from(a):
    m = re.search(r"([A-Za-z .'\-]+?)\s+District\b", a)
    return m.group(1).strip() if m else ""
apy_dist = apy.map(dt_from)
print("  address_py has an '<X> District' token:", (apy_dist != "").sum(), f"({100*(apy_dist!='').sum()/N:.2f}%)")
d_eq = apy_dist.str.lower() == df["DISTRICT_NAME"].str.lower()
print("  and it equals DISTRICT_NAME:", d_eq.sum(), f"({100*d_eq.sum()/N:.2f}%)")
print("  top district mismatches:", Counter(zip(df.loc[(apy_dist!='')&~d_eq,"DISTRICT_NAME"], apy_dist[(apy_dist!='')&~d_eq])).most_common(15))

print("\n### K. Dedup-artifact suffixes in MASTER_FACILITY_DESC ###")
suffix_digit = df["MASTER_FACILITY_DESC"].fillna("").str.contains(r"\s\d{1,2}$")
print("  names ending in ' <1-2 digits>':", suffix_digit.sum())
print("   e.g.", df.loc[suffix_digit,"MASTER_FACILITY_DESC"].head(12).tolist())
base = df["MASTER_FACILITY_DESC"].fillna("").str.replace(r"[\s\.]+\d{0,2}$","",regex=True).str.lower().str.replace(r"[^a-z0-9]","",regex=True)
grp = pd.DataFrame({"b": base, "h": df["HAB_CODE"]})
print("  rows collapsing on (HAB_CODE, name-stripped-of-numeric-suffix):", grp.duplicated().sum())

print("\n### L. Near-duplicate quantification (multiple definitions) ###")
def norm(s): return s.fillna("").str.lower().str.replace(r"[^a-z0-9]"," ",regex=True).str.replace(r"\s+"," ",regex=True).str.strip()
nm = norm(df["MASTER_FACILITY_DESC"])
defs = {
 "exact all cols": df.duplicated().sum(),
 "all cols except Sr. No.": df[[c for c in df.columns if c!="Sr. No. "]].duplicated().sum(),
 "(normname, lat, lon) exact": pd.DataFrame({"n":nm,"a":df.LATITUDE,"o":df.LONGITUDE}).duplicated().sum(),
 "(lat, lon) exact": df.duplicated(subset=["LATITUDE","LONGITUDE"]).sum(),
 "(normname, latlon@4dp ~11m)": pd.DataFrame({"n":nm,"g":lat.round(4).astype(str)+lon.round(4).astype(str)}).duplicated().sum(),
 "(normname, latlon@3dp ~111m)": pd.DataFrame({"n":nm,"g":lat.round(3).astype(str)+lon.round(3).astype(str)}).duplicated().sum(),
 "(normname, HAB_CODE)": pd.DataFrame({"n":nm,"h":df.HAB_CODE}).duplicated().sum(),
 "(normname, district)": pd.DataFrame({"n":nm,"d":df.DISTRICT_NAME}).duplicated().sum(),
 "(normname, block)": pd.DataFrame({"n":nm,"d":df.BLOCK_NAME}).duplicated().sum(),
 "(normname, state)": pd.DataFrame({"n":nm,"d":df.STATE_NAME}).duplicated().sum(),
 "(HAB_CODE, SUB_CATEGORY)": df.duplicated(subset=["HAB_CODE","SUB_CATEGORY"]).sum(),
}
for k,v in defs.items(): print(f"  {k:34s}: {v}")

# proximity near-dupe: same block + within ~100m + similar name
print("\n  --- proximity clusters: same HAB_CODE, <150m apart ---")
try:
    from scipy.spatial import cKDTree
    R=6371000.0
    la=np.radians(lat.values); lo=np.radians(lon.values)
    xyz=np.c_[np.cos(la)*np.cos(lo), np.cos(la)*np.sin(lo), np.sin(la)]*R
    t=cKDTree(xyz)
    pairs=t.query_pairs(r=150, output_type='ndarray')
    print("   pairs within 150m (any):", len(pairs))
    same_hab=(df.HAB_CODE.values[pairs[:,0]]==df.HAB_CODE.values[pairs[:,1]])
    print("   of which same HAB_CODE:", same_hab.sum())
    nmv=nm.values
    import difflib
    sim=np.array([difflib.SequenceMatcher(None,nmv[i],nmv[j]).ratio() for i,j in pairs])
    print("   within 150m AND name similarity>=0.85:", int((sim>=0.85).sum()))
    print("   within 150m AND name similarity>=0.70:", int((sim>=0.70).sum()))
    idx=np.argsort(-sim)[:15]
    for k in idx:
        i,j=pairs[k]
        print(f"    sim={sim[k]:.2f} [{df.loc[i,'Sr. No. ']}] {df.loc[i,'MASTER_FACILITY_DESC'][:55]!r} <-> [{df.loc[j,'Sr. No. ']}] {df.loc[j,'MASTER_FACILITY_DESC'][:55]!r} ({df.loc[i,'DISTRICT_NAME']})")
except ImportError as e:
    print("   scipy unavailable:", e)

print("\n### M. HABITATION_NAME == BLOCK_NAME (block HQ rows) ###")
print("  equal:", (df.HABITATION_NAME.str.lower()==df.BLOCK_NAME.str.lower()).sum(),
      f"({100*(df.HABITATION_NAME.str.lower()==df.BLOCK_NAME.str.lower()).sum()/N:.2f}%)")
print("  BLOCK_NAME == DISTRICT_NAME:", (df.BLOCK_NAME.str.lower()==df.DISTRICT_NAME.str.lower()).sum())

print("\n### N. ER readiness ###")
has_geo = (lat.notna()&lon.notna()&(lat.between(6,38))&(lon.between(68,98)))
informative_name = ~nm.isin({re.sub(r'[^a-z0-9 ]','',x) for x in
   ["chc","phc","hospital","dispensary","clinic","bedded hospital","community health centre",
    "community health center","medical","beded hospital","hospital bedded","c h c","health centre",
    "health center","sub centre","sub center","govt hospital","nursing home","primary health centre",
    "dispansary","hospitals","phc bedded hospital","bedded hospital dispensary"]})
print("  has non-null name:", df.MASTER_FACILITY_DESC.notna().sum(), f"({100*df.MASTER_FACILITY_DESC.notna().sum()/N:.2f}%)")
print("  has valid geo:", has_geo.sum(), f"({100*has_geo.sum()/N:.2f}%)")
print("  has district:", df.DISTRICT_NAME.notna().sum())
print("  informative (non-generic) name:", informative_name.sum(), f"({100*informative_name.sum()/N:.2f}%)")
print("  name+geo+district all usable:", (informative_name&has_geo&df.DISTRICT_NAME.notna()).sum(),
      f"({100*(informative_name&has_geo&df.DISTRICT_NAME.notna()).sum()/N:.2f}%)")
print("  UNMATCHABLE by name (generic name only, must rely on geo):", (~informative_name).sum(),
      f"({100*(~informative_name).sum()/N:.2f}%)")

print("\n### O. FILE_UPLOAD_DATE nulls — where? ###")
nulls = df[df.FILE_UPLOAD_DATE.isna()]
print("  n:", len(nulls))
print("  by state:", nulls.STATE_NAME.value_counts().to_dict())
print("  Sr. No. range:", nulls["Sr. No. "].astype(int).min(), "-", nulls["Sr. No. "].astype(int).max())
print("  by district:", nulls.DISTRICT_NAME.value_counts().head(10).to_dict())

print("\n### P. Pincode plausibility vs state first-digit ###")
FD = {"1":{"Delhi","Haryana","Punjab","Himachal Pradesh","Jammu And Kashmir","Chandigarh","Ladakh"},
      "2":{"Uttar Pradesh","Uttarakhand"},
      "3":{"Rajasthan","Gujarat"},
      "4":{"Chhattisgarh","Madhya Pradesh","Maharashtra","Goa"},
      "5":{"Andhra Pradesh","Karnataka","Telangana"},
      "6":{"Tamilnadu","Kerala","Pondicherry"},
      "7":{"West Bengal","Odisha","Arunachal Pradesh","Assam","Manipur","Meghalaya","Mizoram",
           "Nagaland","Sikkim","Tripura"},
      "8":{"Bihar","Jharkhand"},
      "9":{"APS"}}
fd = df.Pincode.str[0]
ok = [ (df.STATE_NAME.iloc[i] in FD.get(fd.iloc[i], set())) for i in range(N) ]
print("  pincode first digit consistent with state:", sum(ok), f"({100*sum(ok)/N:.2f}%)")
bad = df[[not o for o in ok]]
print("  inconsistent examples:", bad[["Sr. No. ","STATE_NAME","DISTRICT_NAME","Pincode","address_py"]].head(10).to_dict("records"))
print("  inconsistent by state:", bad.STATE_NAME.value_counts().head(12).to_dict())
