"""Pull exact row indices + values for every defect cited in issues.md."""
import re

import numpy as np
import pandas as pd

SRC = "/Users/ankitraj2/asar master data/18_MAY_23_SRK_PMJAY_validated_and_standardized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
n = len(df)
la = pd.to_numeric(df["API Latitude"], errors="coerce")
lo = pd.to_numeric(df["API Longitude"], errors="coerce")
gla = pd.to_numeric(df["gmaps_Latitude"], errors="coerce")
glo = pd.to_numeric(df["gmaps_Longitude"], errors="coerce")

def show(lab, idx, cols, k=4):
    print(f"\n--- {lab} (n={len(idx)}) ---")
    for i in list(idx)[:k]:
        print(f"  row {i} (Sr No {df.at[i,'Sr No']}): " +
              " | ".join(f"{c}={df.at[i,c]!r}" for c in cols))

# 1 lat/lon in contact fields
F = re.compile(r"^-?\d{1,3}\.\d{3,}$")
sus = df.index[df["Hospital E-Mail"].fillna("").str.match(F) | df["Hospital Contact"].fillna("").str.match(F)]
show("lat/lon in E-Mail + Contact", sus, ["Hospital E-Mail", "Hospital Contact", "API Latitude", "API Longitude"])
print("  full index list:", list(sus))

# 2 S8/S9 loss
tok = lambda v: {t.strip() for t in str(v).split(",")} if pd.notna(v) else set()
loss = df.index[df["Specialities Empanelled"].apply(lambda v: bool(tok(v) & {"S8", "S9"}))]
show("S8/S9 present in text, absent from flags", loss,
     ["Specialities Empanelled"], 3)
i = loss[0]
print(f"    row {i}: flags set = {[c for c in df.columns if c.endswith('_emp') and df.at[i,c]=='1']}")

# 3 corrupt combined column
bad = df.index[df["Specialities_Upgraded_or_Empanelled"].fillna("").str.contains("-NA-", regex=False)]
show("corrupt Specialities_Upgraded_or_Empanelled", bad,
     ["Specialities Empanelled", "Specialities Upgraded", "Specialities_Upgraded_or_Empanelled"], 3)
noe = df.index[df["Specialities_Upgraded_or_Empanelled"].fillna("").str.contains(r"[MS]\d+[MS]\d+", regex=True)]
show("  concat with no delimiter", noe, ["Specialities_Upgraded_or_Empanelled"], 3)

# 4 gmaps out of India
gout = df.index[~(gla.between(6, 38) & glo.between(68, 98))]
show("gmaps point outside India", gout,
     ["Hospital Name", "Manual state", "gmaps_Latitude", "gmaps_Longitude", "gmaps_Accuracy"], 5)
print("  full index list:", list(gout))

# 5 API out of India
aout = df.index[~(la.between(6, 38) & lo.between(68, 98))]
show("API point outside India", aout,
     ["Hospital Name", "Manual state", "API Latitude", "API Longitude"], 5)

# 6 pincode sentinel 0 / US zips
pp = df["pincode_py"].astype(str)
show("pincode_py == '0'", df.index[pp == "0"], ["pincode_py", "Zipcode", "Manual state"], 3)
usz = df.index[~pp.str.fullmatch(r"\d{6}") & (pp != "0")]
show("pincode_py non-Indian", usz, ["pincode_py", "Manual state", "gmaps_Latitude", "gmaps_Longitude"], 5)
print("  full index list:", list(usz))

# 7 Manual District case inconsistency
d = df["Manual District"].dropna()
lower = df.index[df["Manual District"].notna() & ~df["Manual District"].fillna("").str.isupper()]
print(f"\n--- Manual District not uppercase (n={len(lower)}) ---")
print("  distinct values:", sorted(set(df.loc[lower, "Manual District"]))[:25])
# same district in both cases?
u = {x.upper() for x in d}
pairs = {x for x in d if not x.isupper() and x.upper() in set(d)}
print("  districts appearing in BOTH cases:", sorted(pairs)[:20])
vc = d.str.upper().value_counts()
mixed = [k for k in vc.index if len({x for x in d if x.upper() == k}) > 1]
print(f"  districts with >1 casing variant: {len(mixed)} e.g. "
      f"{ {k: sorted({x for x in d if x.upper()==k}) for k in mixed[:6]} }")

# 8 state disagreement
ms = df["Manual state"].fillna("").str.upper().str.strip()
st = df["State"].fillna("").str.upper().str.strip()
dis = df.index[(ms != st) & df["State"].notna()]
show("Manual state vs geocoder State disagreement", dis,
     ["Manual Hospital Name", "Manual state", "State", "City"], 4)

# 9 phone placeholders
ph = df["Hospital Contact"]
show("placeholder phone '-NA-'", df.index[ph == "-NA-"], ["Hospital Name", "Hospital Contact"], 2)
show("placeholder phone '9898989898'", df.index[ph == "9898989898"], ["Hospital Name", "Hospital Contact"], 2)
show("placeholder phone '0'", df.index[ph == "0"], ["Hospital Name", "Hospital Contact"], 2)

# 10 shared emails
em = df["Hospital E-Mail"]
show("shared TPA email", df.index[em == "nithia.d@vidalhealthtpa.com"],
     ["Hospital Name", "Manual District", "Hospital E-Mail"], 3)

# 11 typo email
show("typo'd email domain", df.index[em.fillna("").str.contains("gmaul", na=False)],
     ["Hospital Name", "Hospital E-Mail"], 3)

# 12 Test extract
show("Test extract scratch column", df.index[df["Test extract"].notna()],
     ["Test extract", "Manual District", "Manual state"], 8)

# 13 gmaps_Accuracy bad class
show("gmaps_Accuracy == 'Awesome Tables'", df.index[df["gmaps_Accuracy"] == "Awesome Tables"],
     ["Hospital Name", "gmaps_Accuracy"], 3)

# 14 Hospital Type null
show("Hospital Type null", df.index[df["Hospital Type"].isna()], ["Hospital Name", "Manual state"], 3)

# 15 is_RU null
show("is_RU null", df.index[df["is_RU"].isna()], ["Hospital Name", "Manual state"], 8)

# 16 Manual District null
show("Manual District null", df.index[df["Manual District"].isna()],
     ["Hospital Name", "Manual state", "City"], 4)
print("  full index list:", list(df.index[df["Manual District"].isna()]))

# 17 duplicate pair with differing specialties
print("\n--- confirmed duplicate pair, specialties differ ---")
for i in [6749, 6750, 8203, 8204]:
    print(f"  row {i} (Sr No {df.at[i,'Sr No']}): {df.at[i,'Hospital Name']!r}")
    print(f"      emp={df.at[i,'Specialities Empanelled']!r}")
    print(f"      email={df.at[i,'Hospital E-Mail']!r} type={df.at[i,'Hospital Type']!r}")

# 18 name truncation
print("\n--- Manual Hospital Name truncation ---")
for i in [20, 41, 10248, 10249]:
    print(f"  row {i}: HN={df.at[i,'Hospital Name']!r} MHN={df.at[i,'Manual Hospital Name']!r}")

# 19 Sr No gap
print("\n--- Sr No gap ---")
print("  row 251 Sr No =", df.at[251, "Sr No"], "| row 252 Sr No =", df.at[252, "Sr No"])

# 20 ALL CAPS names
u = df.index[df["Hospital Name"].fillna("").str.isupper()]
show("ALL CAPS Hospital Name", u, ["Hospital Name", "Manual Hospital Name"], 3)

# 21 empty specialty rows
E = df[[c for c in df.columns if c.endswith("_emp")]].apply(pd.to_numeric, errors="coerce").fillna(0)
show("no empanelled specialty at all", df.index[df["Specialities Empanelled"] == "-NA-"],
     ["Hospital Name", "Specialities Empanelled", "Specialities Upgraded"], 3)

# 22 pincode/state mismatch
print("\n--- pincode first digit inconsistent with Manual state ---")
FIRST = {"1": {"DELHI","HARYANA","PUNJAB","HIMACHAL PRADESH","JAMMU AND KASHMIR","CHANDIGARH","NCT OF DELHI"},
         "2": {"UTTAR PRADESH","UTTARAKHAND"}, "3": {"RAJASTHAN","GUJARAT","DAMAN AND DIU","DADRA AND NAGAR HAVELI"},
         "4": {"MAHARASHTRA","MADHYA PRADESH","CHHATTISGARH","GOA"}, "5": {"ANDHRA PRADESH","KARNATAKA","TELANGANA"},
         "6": {"TAMIL NADU","KERALA","PUDUCHERRY","LAKSHADWEEP"},
         "7": {"WEST BENGAL","ODISHA","ASSAM","SIKKIM","ARUNACHAL PRADESH","NAGALAND","MANIPUR","MIZORAM","TRIPURA","MEGHALAYA","ANDAMAN AND NICOBAR ISLANDS"},
         "8": {"BIHAR","JHARKHAND"}}
c = 0
for i in df.index[pp.str.fullmatch(r"\d{6}")]:
    d0, s = pp[i][0], df.at[i, "Manual state"]
    if d0 in FIRST and s not in FIRST[d0]:
        print(f"  row {i}: pincode={pp[i]} Manual state={s!r} City={df.at[i,'City']!r} "
              f"API=({df.at[i,'API Latitude']},{df.at[i,'API Longitude']})")
        c += 1
        if c >= 5:
            break
