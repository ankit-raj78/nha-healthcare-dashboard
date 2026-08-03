"""CGHS EDA - step 4: id structure, geo quality, duplicates, address/text."""
import pandas as pd, numpy as np, re
from collections import Counter

SRC = "/Users/ankitraj2/asar master data/18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
N = len(df)

print("=========== Unnamed: 0 gaps ===========")
u = pd.to_numeric(df["Unnamed: 0"])
print("min", u.min(), "max", u.max(), "n", len(u), "unique", u.is_unique, "monotonic increasing:", u.is_monotonic_increasing)
missing = sorted(set(range(u.min(), u.max() + 1)) - set(u.tolist()))
print("missing integers in [min,max]:", len(missing), "first 25:", missing[:25])

print("\n=========== Hospital_Id structure (v2) ===========")
hid = df["Hospital_Id"]
m = hid.str.extract(r"^(HOSP|LAB)(\d+)([A-Z])(\d+)$")
print("HOSP/LAB + digits + LETTER + digits:", int(m[0].notna().sum()))
m2 = hid.str.extract(r"^(HOSP|LAB)(\d+)$")
print("prefix + digits only:", int(m2[0].notna().sum()))
print("prefix counts:", hid.str.extract(r"^([A-Z]+)")[0].value_counts().to_dict())
unmatched = hid[m[0].isna() & m2[0].isna()]
print("unmatched by either:", len(unmatched), unmatched.tolist()[:10])
lab = hid[hid.str.startswith("LAB")]
print("\nLAB rows:", len(lab), lab.tolist())
print("LAB rows Hospital_Name:", df.loc[lab.index, "Hospital_Name"].tolist())
print("LAB rows Hospital_Type:", df.loc[lab.index, "Hospital_Type"].tolist())
print("LAB rows Specialities:", df.loc[lab.index, "Specialities_Selected"].tolist())

# state-code segment vs State using full-length digits
seg = m[1].fillna(m2[1])
letter = m[2]
tmp = df.assign(code=seg, letter=letter)
print("\nletter counts (full):", tmp["letter"].value_counts(dropna=False).to_dict())
print("\ncode -> state purity:")
g = tmp.dropna(subset=["code"]).groupby("code")["State"]
for code, s in g:
    print(f"   {code}: n={len(s)} states={s.value_counts().to_dict()}")

print("\n=========== letter x Hospital_Type (full) ===========")
print(pd.crosstab(tmp["letter"], tmp["Hospital_Type"].fillna("<null>"), dropna=False))

print("\n=========== GEO ===========")
lat = pd.to_numeric(df["Latitude"], errors="coerce")
lon = pd.to_numeric(df["Longitude"], errors="coerce")
print("lat null:", int(lat.isna().sum()), "lon null:", int(lon.isna().sum()))
print("lat min/max:", lat.min(), lat.max(), " lon min/max:", lon.min(), lon.max())
zero = ((lat == 0) | (lon == 0))
print("zero coords:", int(zero.sum()))
inbox = lat.between(6, 38) & lon.between(68, 98)
print("inside India bbox (lat 6-38, lon 68-98):", int(inbox.sum()), f"{100*inbox.mean():.2f}%")
outb = ~inbox & lat.notna() & lon.notna()
print("outside bbox:", int(outb.sum()))
print(df.loc[outb, ["Hospital_Name", "State", "Latitude", "Longitude"]].to_string())
swapped = (~inbox) & lon.between(6, 38) & lat.between(68, 98)
print("possibly swapped (lon in lat range and vice versa):", int(swapped.sum()))
# precision
dec = df["Latitude"].str.split(".").str[1].fillna("").str.len()
print("lat decimal places dist:", dict(sorted(Counter(dec).items())))
# duplicated coord pairs
pair = df["Latitude"] + "," + df["Longitude"]
vc = pair.value_counts()
print("distinct coord pairs:", pair.nunique(), " pairs used by >1 row:", int((vc > 1).sum()),
      " rows sharing a coord with another row:", int(vc[vc > 1].sum()))
print("top shared coords:")
for k, v in vc.head(8).items():
    idx = df.index[pair == k][:3]
    print(f"   {k} x{v}  e.g. {df.loc[idx,'Hospital_Name'].tolist()} | {df.loc[idx,'District'].tolist()}")

# state centroid-ish check: coord vs State consistency is hard w/o shapefile; do coarse
print("\n=========== Address / text ===========")
for c in ["Hospital_Name", "Address", "address_py"]:
    L = df[c].dropna().str.len()
    print(f"{c}: len min={L.min()} p25={L.quantile(.25):.0f} med={L.median():.0f} p75={L.quantile(.75):.0f} max={L.max()} mean={L.mean():.1f}")
# is Address == name + district + state?
recon = df["Hospital_Name"] + ", " + df["District"] + ", " + df["State"]
eq = (df["Address"].str.strip() == recon.str.strip())
print("Address == 'Name, District, State' exactly:", int(eq.sum()), f"({100*eq.mean():.2f}%)")
# normalized (collapse whitespace)
def norm(s): return s.str.replace(r"\s+", " ", regex=True).str.strip().str.upper()
eq2 = norm(df["Address"]) == norm(recon)
print("  ... after whitespace/case normalization:", int(eq2.sum()), f"({100*eq2.mean():.2f}%)")
print("  non-matching examples:")
for i in df.index[~eq2][:5]:
    print("    row", i, "| Address:", repr(df.at[i, "Address"])[:120])
    print("            | recon  :", repr(recon.at[i])[:120])
# address_py contains ", India"
print("address_py endswith 'India':", int(df['address_py'].str.rstrip().str.endswith('India').sum()))
print("address_py contains a 6-digit pincode:", int(df['address_py'].str.contains(r'\b\d{6}\b').sum()))
# does Postcode_py appear in address_py?
has = df.apply(lambda r: (pd.notna(r["Postcode_py"]) and str(r["Postcode_py"]) in str(r["address_py"])), axis=1)
print("Postcode_py substring of address_py:", int(has.sum()), "/", int(df['Postcode_py'].notna().sum()))

print("\n=========== DUPLICATES ===========")
print("exact dupes on ALL 26 cols:", int(df.duplicated().sum()))
noidx = df.drop(columns=["Unnamed: 0"])
print("exact dupes ignoring Unnamed: 0:", int(noidx.duplicated().sum()))
core = ["Hospital_Name", "District", "State", "Address", "Latitude", "Longitude"]
print("dupes on core business cols", core, ":", int(df.duplicated(subset=core).sum()))
print("dupes on Hospital_Name alone:", int(df.duplicated(subset=["Hospital_Name"]).sum()))
print("dupes on (Hospital_Name, State):", int(df.duplicated(subset=["Hospital_Name","State"]).sum()))
print("dupes on (Hospital_Name, District, State):", int(df.duplicated(subset=["Hospital_Name","District","State"]).sum()))
print("dupes on (Latitude, Longitude):", int(df.duplicated(subset=["Latitude","Longitude"]).sum()))

def nname(s):
    s = s.upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\b(PVT|PRIVATE|LTD|LIMITED|THE|AND|A|UNIT|OF)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
df["_nn"] = df["Hospital_Name"].map(nname)
print("dupes on normalized name:", int(df.duplicated(subset=["_nn"]).sum()))
print("dupes on (normalized name, State):", int(df.duplicated(subset=["_nn","State"]).sum()))
# near-dupe: same normalized name AND coords within ~500m
lat_r = lat.round(3); lon_r = lon.round(3)
df["_geo3"] = lat_r.astype(str) + "," + lon_r.astype(str)
nd = df.duplicated(subset=["_nn", "_geo3"])
print("near-dupe (norm name + coords rounded to 3dp ~110m):", int(nd.sum()))
nd2 = df.duplicated(subset=["_nn"]) & df.duplicated(subset=["_geo3"])
print("norm-name dupe AND geo dupe:", int(nd2.sum()))
print("\nexamples of normalized-name duplicate groups:")
gg = df[df.duplicated(subset=["_nn"], keep=False)].sort_values("_nn")
shown = 0
for k, grp in gg.groupby("_nn"):
    if shown >= 8: break
    print(f"  [{k}] n={len(grp)}")
    print(grp[["Hospital_Id","Hospital_Name","District","State","Latitude","Longitude"]].to_string(index=True))
    shown += 1
print("\ntotal normalized-name groups with >1 row:", gg["_nn"].nunique(), "covering", len(gg), "rows")
