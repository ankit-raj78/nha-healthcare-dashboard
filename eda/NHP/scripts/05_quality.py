"""NHP EDA step 5: geo, postcode, numerics, duplicates, addresses, PK."""
import csv, io, re, json
from collections import Counter
import pandas as pd
import numpy as np

SRC = "/Users/ankitraj2/asar master data/8_JULY_23_SRK_NHP_validated_and_standardized.csv"
NORM = lambda s: re.sub(r"\s+", " ", s).strip() if isinstance(s, str) else s

df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = df.rename(columns={"S.\n  No.": "S. No."})
df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")])
df = df.dropna(how="all").reset_index(drop=True)
print("rows after dropping all-blank:", len(df), "cols:", len(df.columns))

# --- whitespace rule verification ---
raw = open(SRC, "rb").read().decode("utf-8-sig")
print("\n[whitespace rule] occurrences of '\\n  ' (LF + 2 spaces):", raw.count("\n  "))
print("[whitespace rule] total embedded LF in fields (from step1): 349 + 1 header")
# double spaces NOT preceded by newline, across all text cells
bad = 0
for c in df.columns:
    for v in df[c].dropna():
        for m in re.finditer(r"  +", v):
            if m.start() == 0 or v[m.start()-1] != "\n":
                bad += 1
print("[whitespace rule] runs of 2+ spaces NOT immediately after a newline:", bad)
nbsp = sum(int(bool(re.search(r"[\xa0​\t]", v))) for c in df.columns for v in df[c].dropna())
print("[whitespace rule] cells containing NBSP/zero-width/tab:", nbsp)

# --- geo ---
lat = pd.to_numeric(df["Latitude"], errors="coerce")
lon = pd.to_numeric(df["Longitude"], errors="coerce")
print("\n=== GEO ===")
print("Latitude parse failures (non-null but non-numeric):",
      int((df["Latitude"].notna() & lat.isna()).sum()))
print("Longitude parse failures:", int((df["Longitude"].notna() & lon.isna()).sum()))
print("lat null:", int(lat.isna().sum()), " lon null:", int(lon.isna().sum()))
print("lat describe:\n", lat.describe())
print("lon describe:\n", lon.describe())
both = lat.notna() & lon.notna()
zero = ((lat == 0) | (lon == 0))
inbox = (lat.between(6, 38)) & (lon.between(68, 98))
print("rows with both lat+lon:", int(both.sum()))
print("zero coords:", int((both & zero).sum()))
print("inside India bbox:", int(inbox.sum()))
oob = both & ~inbox & ~zero
print("out of bbox (non-zero):", int(oob.sum()))
print(df.loc[oob, ["S. No.", "Hospital Name", "Latitude", "Longitude", "State"]].to_string())
swapped = both & ~inbox & lon.between(6, 38) & lat.between(68, 98)
print("possibly swapped:", int(swapped.sum()))
# duplicate coordinate pairs
pairs = list(zip(lat[both], lon[both]))
dupc = Counter(pairs)
print("duplicate coord pairs (n>1):", sum(1 for k, v in dupc.items() if v > 1),
      "covering rows:", sum(v for k, v in dupc.items() if v > 1))
print("top dup coords:", dupc.most_common(5))
# precision
dec = df.loc[both, "Latitude"].apply(lambda s: len(s.split(".")[1]) if "." in s else 0)
print("lat decimal places distribution:", dict(Counter(dec)))

# --- postcode ---
print("\n=== POSTCODE ===")
for c in ["Postcode", "Postcode_py"]:
    s = df[c].dropna()
    print(f"{c}: non_null={len(s)}")
    print("   6-digit:", int(s.str.fullmatch(r"\d{6}").sum()))
    print("   not 6-digit:", sorted(set(s[~s.str.fullmatch(r"\d{6}", na=False)]))[:20])
    lead = s.str.fullmatch(r"\d{6}") & s.str.startswith("0")
    print("   leading zero:", int(lead.sum()))
eqm = df["Postcode"].fillna("<NA>") == df["Postcode_py"].fillna("<NA>")
print("Postcode == Postcode_py:", int(eqm.sum()), "/", len(df))
print("mismatches:")
print(df.loc[~eqm, ["S. No.", "Hospital Name", "Postcode", "Postcode_py"]].head(10).to_string())

# --- numerics unique to this dataset ---
print("\n=== NUMERIC FIELDS ===")
for c in ["Admission Intake", "No. of beds in attached Hospital", "S. No."]:
    s = df[c]
    n = pd.to_numeric(s, errors="coerce")
    print(f"\n{c}: non_null={int(s.notna().sum())} parse_fail={int((s.notna()&n.isna()).sum())}")
    bad = s[s.notna() & n.isna()]
    if len(bad): print("   unparseable values:", list(bad.unique())[:20])
    print("   ", n.describe().to_dict())
    print("   zeros:", int((n == 0).sum()), " has thousands sep:",
          int(s.dropna().str.contains(",").sum()))

# --- Type / enum ---
print("\n=== TYPE enum ===")
print(df["Type"].value_counts(dropna=False).to_dict())

# --- duplicates ---
print("\n=== DUPLICATES ===")
core = [c for c in df.columns if c != "S. No."]
print("exact dupe rows (all cols incl S. No.):", int(df.duplicated().sum()))
print("exact dupe rows (excl S. No.):", int(df.duplicated(subset=core).sum()))
nm = df["Hospital Name"].map(NORM).str.casefold()
print("duplicate normalized names:", int(nm.duplicated().sum()))
vc = nm.value_counts()
print("names appearing >1 time:", int((vc > 1).sum()))
print("\ntop repeated names:")
for k, v in vc[vc > 1].head(15).items():
    print(f"   {v}x  {k!r}")
# name+state
ns = nm + "||" + df["State"].fillna("").map(NORM).str.casefold()
print("\ndupes on (norm_name, state):", int(ns.duplicated().sum()))
# name + rounded geo
geo4 = lat.round(4).astype(str) + "," + lon.round(4).astype(str)
ng = nm + "||" + geo4
print("dupes on (norm_name, geo@4dp):", int(ng.duplicated().sum()))
ng2 = nm + "||" + lat.round(2).astype(str) + "," + lon.round(2).astype(str)
print("dupes on (norm_name, geo@2dp):", int(ng2.duplicated().sum()))
print("\nsample repeated (name,state) groups:")
g = df.assign(_nm=nm, _st=df["State"]).groupby(["_nm", "_st"]).size()
for (a, b), v in g[g > 1].head(10).items():
    print(f"   {v}x {a!r} / {b!r}")

# --- addresses ---
print("\n=== ADDRESS COLUMNS ===")
for c in ["Given Address", "Standardized Address", "address_py"]:
    s = df[c]
    L = s.dropna().map(NORM).str.len()
    print(f"{c}: non_null={int(s.notna().sum())} ({100*s.notna().mean():.2f}%) "
          f"distinct={int(s.nunique())} len_min={L.min()} p50={int(L.median())} "
          f"max={L.max()} mean={L.mean():.1f}")
    # does it contain a pincode?
    print("    contains 6-digit pin:", int(s.dropna().str.contains(r"\b\d{6}\b", regex=True).sum()),
          " contains 'India':", int(s.dropna().str.contains("India").sum()),
          " ends with '.':", int(s.dropna().str.endswith(".").sum()))
# is Given Address == name + city + state?
ga = df["Given Address"].map(NORM)
hn = df["Hospital Name"].map(NORM)
sa = df["Standardized Address"].map(NORM)
ap = df["address_py"].map(NORM)
sw = lambda col: sum(1 for a, n in zip(col.fillna(""), hn.fillna("\x00")) if a.startswith(n))
print("Given Address startswith Hospital Name:", sw(ga))
print("Standardized Address startswith Hospital Name:", sw(sa))
print("address_py startswith Hospital Name:", sw(ap))
print("address_py contains Postcode value:",
      int(sum(1 for a, p in zip(ap.fillna(""), df["Postcode"].fillna("")) if p and p in a)))

# --- PK candidates ---
print("\n=== PRIMARY KEY CANDIDATES ===")
for c in df.columns:
    s = df[c]
    if s.notna().all() and s.nunique() == len(df):
        print("   UNIQUE + complete:", c)
for c in ["S. No.", "Hospital Name", "Given Address", "Standardized Address", "address_py"]:
    print(f"   {c}: distinct={df[c].nunique()} / non_null={int(df[c].notna().sum())} / rows={len(df)}")
sn = pd.to_numeric(df["S. No."], errors="coerce")
print("   S. No. is 1..N contiguous:", bool((sn.values == np.arange(1, len(df)+1)).all()))

# --- city/state consistency ---
print("\n=== CITY ===")
print("distinct cities:", df["City"].nunique(), " nulls:", int(df["City"].isna().sum()))
print(df["City"].map(NORM).value_counts().head(15).to_dict())
