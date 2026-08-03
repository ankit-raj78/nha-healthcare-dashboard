"""Field-shift/misalignment, Sr No gap, pincode<->Zipcode relationship,
duplicate detection (exact + near-dupe on name/geo), and ER readiness."""
import re
from collections import Counter

import numpy as np
import pandas as pd

SRC = "/Users/ankitraj2/asar master data/18_MAY_23_SRK_PMJAY_validated_and_standardized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
n = len(df)

# ============ 1. Sr No gap ============
print("=" * 70, "\nSr No\n", "=" * 70)
sr = pd.to_numeric(df["Sr No"])
missing = sorted(set(range(1, int(sr.max()) + 1)) - set(sr.astype(int)))
print("max:", int(sr.max()), "n rows:", n, "missing values in 1..max:", missing)
print("is monotonic increasing:", bool(sr.is_monotonic_increasing))
neigh = df.index[sr.astype(int).isin([m - 1 for m in missing] + [m + 1 for m in missing])]
for i in list(neigh)[:6]:
    print(f"  row {i}: Sr No={df.at[i,'Sr No']} name={df.at[i,'Hospital Name'][:45]!r}")

# ============ 2. field shift / misalignment ============
print("\n" + "=" * 70, "\nFIELD SHIFT / MISALIGNMENT\n", "=" * 70)
FLOATLIKE = re.compile(r"^-?\d{1,3}\.\d{3,}$")
em_bad = df["Hospital E-Mail"].fillna("").str.match(FLOATLIKE)
ph_bad = df["Hospital Contact"].fillna("").str.match(FLOATLIKE)
print(f"E-Mail that is a bare decimal number : {int(em_bad.sum())}")
print(f"Contact that is a bare decimal number: {int(ph_bad.sum())}")
print(f"both on same row                     : {int((em_bad & ph_bad).sum())}")
print(f"either                               : {int((em_bad | ph_bad).sum())}")
sus = df.index[em_bad | ph_bad]
print("\nDo those decimals look like the row's own lat/lon?")
la = pd.to_numeric(df["API Latitude"], errors="coerce")
lo = pd.to_numeric(df["API Longitude"], errors="coerce")
emv = pd.to_numeric(df["Hospital E-Mail"], errors="coerce")
phv = pd.to_numeric(df["Hospital Contact"], errors="coerce")
chk = df.index[em_bad & ph_bad]
close_lat = (emv[chk] - la[chk]).abs() < 1.0
close_lon = (phv[chk] - lo[chk]).abs() < 1.0
print(f"  of {len(chk)} rows with both numeric: email≈API lat (<1 deg): {int(close_lat.sum())}, "
      f"contact≈API lon (<1 deg): {int(close_lon.sum())}")
print("\n  full row dump for first 4 suspects (key columns):")
KEY = ["Sr No", "Hospital Name", "Manual Hospital Name", "Hospital Type", "Manual Hospital Address",
       "API Latitude", "API Longitude", "Hospital Address", "Hospital E-Mail", "Hospital Contact",
       "Specialities Empanelled", "Manual District", "Manual state"]
for i in list(sus)[:4]:
    print(f"\n  --- row {i} ---")
    for c in KEY:
        print(f"    {c:26} = {df.at[i, c]!r}")

# do the suspect rows also have a shifted specialty column?
print("\n  suspect rows: value of 'Specialities Empanelled' (should be codes):")
for i in list(sus)[:10]:
    print(f"    row {i}: {df.at[i,'Specialities Empanelled']!r}")

# ============ 3. pincode_py vs Zipcode ============
print("\n" + "=" * 70, "\nPINCODE LINEAGE\n", "=" * 70)
pp = df["pincode_py"].astype(str)
six = pp.str.fullmatch(r"\d{6}")
zn = df["Zipcode"].notna()
print("pincode_py 6-digit:", int(six.sum()), " Zipcode non-null:", int(zn.sum()))
print("6-digit set == Zipcode-present set:", bool((six == zn).all()))
print("rows where they differ:", int((six != zn).sum()))
bad = df.index[~six]
print(f"\nnon-6-digit pincode_py: {len(bad)}")
print("  value '0':", int((pp == "0").sum()))
usz = pp[~six & (pp != "0")]
print("  US-ZIP-looking (5 digit) :", int(usz.str.fullmatch(r"\d{5}").sum()))
print("  4-digit or other         :", int((~usz.str.fullmatch(r"\d{5}")).sum()),
      usz[~usz.str.fullmatch(r"\d{5}")].unique()[:12].tolist())
gv = pd.to_numeric(df["gmaps_Latitude"], errors="coerce")
gvo = pd.to_numeric(df["gmaps_Longitude"], errors="coerce")
gm_out = ~(gv.between(6, 38) & gvo.between(68, 98))
print(f"\ngmaps point outside India bbox: {int(gm_out.sum())}")
print(f"  of those, pincode_py not 6-digit: {int((gm_out & ~six).sum())}")
print(f"  non-6-digit pincode rows whose gmaps IS in India: {int((~gm_out & ~six).sum())}")
print("\n  examples of non-6-digit pincode:")
for i in list(bad)[:8]:
    print(f"    row {i}: pincode_py={df.at[i,'pincode_py']!r} Zipcode={df.at[i,'Zipcode']!r} "
          f"gmaps=({df.at[i,'gmaps_Latitude']},{df.at[i,'gmaps_Longitude']}) "
          f"state={df.at[i,'Manual state']!r}")

# does pincode agree with state? (first digit -> region)
print("\npincode first-digit vs Manual state (spot check of impossible combos):")
FIRST = {"1": {"DELHI", "HARYANA", "PUNJAB", "HIMACHAL PRADESH", "JAMMU AND KASHMIR", "CHANDIGARH", "NCT OF DELHI", "LADAKH"},
         "2": {"UTTAR PRADESH", "UTTARAKHAND"},
         "3": {"RAJASTHAN", "GUJARAT", "DAMAN AND DIU", "DADRA AND NAGAR HAVELI"},
         "4": {"MAHARASHTRA", "MADHYA PRADESH", "CHHATTISGARH", "GOA"},
         "5": {"ANDHRA PRADESH", "KARNATAKA", "TELANGANA"},
         "6": {"TAMIL NADU", "KERALA", "PUDUCHERRY", "LAKSHADWEEP"},
         "7": {"WEST BENGAL", "ODISHA", "ASSAM", "SIKKIM", "ARUNACHAL PRADESH", "NAGALAND",
               "MANIPUR", "MIZORAM", "TRIPURA", "MEGHALAYA", "ANDAMAN AND NICOBAR ISLANDS"},
         "8": {"BIHAR", "JHARKHAND"}}
ok = tot = 0
badex = []
for i in df.index[six]:
    d = pp[i][0]
    st = df.at[i, "Manual state"]
    if d in FIRST:
        tot += 1
        if st in FIRST[d]:
            ok += 1
        elif len(badex) < 10:
            badex.append((i, pp[i], st))
print(f"  checked {tot}, consistent {ok} ({100*ok/tot:.2f}%), inconsistent {tot-ok}")
print("  examples:", badex)

# ============ 4. DUPLICATES ============
print("\n" + "=" * 70, "\nDUPLICATES\n", "=" * 70)
print("exact duplicate rows (all 78 cols):", int(df.duplicated().sum()))
nosr = df.drop(columns=["Sr No"])
print("exact duplicate rows ignoring Sr No :", int(nosr.duplicated().sum()))
d2 = df.index[nosr.duplicated(keep=False)]
print("  rows involved:", len(d2))
for i in list(d2)[:6]:
    print(f"    row {i}: Sr No={df.at[i,'Sr No']} {df.at[i,'Hospital Name'][:40]!r} "
          f"{df.at[i,'Manual District']!r}")

def nm(s):
    return (s.fillna("").str.upper()
             .str.replace(r"[^A-Z0-9 ]+", " ", regex=True)
             .str.replace(r"\b(HOSPITAL|HOSPITALS|CLINIC|CENTRE|CENTER|PVT|LTD|PRIVATE|LIMITED|AND|THE)\b", " ", regex=True)
             .str.replace(r"\s+", " ", regex=True).str.strip())

for col in ["Hospital Name", "Manual Hospital Name"]:
    k = nm(df[col])
    print(f"\nnormalised {col}: distinct={k.nunique()} dup rows={int(k.duplicated().sum())}")

print("\n-- near dupes on (normalised name, rounded geo) --")
for prec, lab in [(4, "~11 m"), (3, "~110 m"), (2, "~1.1 km")]:
    key = nm(df["Manual Hospital Name"]) + "|" + la.round(prec).astype(str) + "|" + lo.round(prec).astype(str)
    print(f"  name + API geo @{prec}dp ({lab}): dup rows={int(key.duplicated().sum())} "
          f"groups={int((key.value_counts()>1).sum())}")

print("\n-- near dupes on (normalised name, district, state) --")
key = (nm(df["Manual Hospital Name"]) + "|" + df["Manual District"].fillna("").str.upper()
       + "|" + df["Manual state"].fillna(""))
print(f"  dup rows={int(key.duplicated().sum())} groups={int((key.value_counts()>1).sum())}")
grp = key.value_counts()
print("  largest groups:")
for g, c in grp.head(6).items():
    idx = list(df.index[key == g])[:4]
    print(f"    {c}x {g[:70]!r} rows={idx}")
    for i in idx[:3]:
        print(f"        row {i}: HN={df.at[i,'Hospital Name'][:45]!r} "
              f"lat={df.at[i,'API Latitude']} email={df.at[i,'Hospital E-Mail']}")

print("\n-- near dupes on geo alone (identical API point) --")
gkey = df["API Latitude"].astype(str) + "," + df["API Longitude"].astype(str)
print(f"  rows sharing an API point: {int(gkey.duplicated().sum())}")

# ============ 5. ER READINESS ============
print("\n" + "=" * 70, "\nER READINESS\n", "=" * 70)
has_name = df["Manual Hospital Name"].notna() & (df["Manual Hospital Name"].str.strip() != "")
api_ok = la.between(6, 38) & lo.between(68, 98)
gm_ok = gv.between(6, 38) & gvo.between(68, 98)
geo_ok = api_ok | gm_ok
has_dist = df["Manual District"].notna()
has_state = df["Manual state"].notna()
has_pin = six
print(f"has usable name          : {int(has_name.sum())} ({100*has_name.mean():.2f}%)")
print(f"has usable geo (API|gmaps): {int(geo_ok.sum())} ({100*geo_ok.mean():.2f}%)")
print(f"has district             : {int(has_dist.sum())} ({100*has_dist.mean():.2f}%)")
print(f"has state                : {int(has_state.sum())} ({100*has_state.mean():.2f}%)")
print(f"has valid 6-digit pincode: {int(has_pin.sum())} ({100*has_pin.mean():.2f}%)")
full = has_name & geo_ok & has_dist & has_state
print(f"\nname+geo+district+state (full blocking key): {int(full.sum())} ({100*full.mean():.2f}%)")
print(f"unmatchable (missing any of the four)      : {int((~full).sum())} ({100*(~full).mean():.2f}%)")
print(f"name+state only                            : {int((has_name&has_state).sum())} "
      f"({100*(has_name&has_state).mean():.2f}%)")
print("\nrows failing the blocking key, by which component:")
print(f"  no name    : {int((~has_name).sum())}")
print(f"  no geo     : {int((~geo_ok).sum())}")
print(f"  no district: {int((~has_dist).sum())}")
print(f"  no state   : {int((~has_state).sum())}")
for i in list(df.index[~full])[:8]:
    print(f"    row {i}: name={has_name[i]} geo={geo_ok[i]} dist={has_dist[i]} state={has_state[i]} "
          f"| {df.at[i,'Hospital Name'][:35]!r}")

# name distinctiveness for blocking
k = nm(df["Manual Hospital Name"])
vc = k.value_counts()
print(f"\nname distinctiveness: {int((vc==1).sum())} names unique, "
      f"{int((vc>1).sum())} names shared by >1 row")
print("  most generic names:", vc.head(8).to_dict())
print("  empty after normalisation:", int((k == "").sum()))
