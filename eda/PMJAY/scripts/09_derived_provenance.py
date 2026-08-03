"""Determine what 'Auto Score' scores, and whether 'Formatted Address' is
assembled from the parsed components."""
import difflib
import re

import numpy as np
import pandas as pd

SRC = "/Users/ankitraj2/asar master data/18_MAY_23_SRK_PMJAY_validated_and_standardized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
n = len(df)
rng = np.random.default_rng(0)
samp = rng.choice(n, 600, replace=False)

sc = pd.to_numeric(df["Auto Score"], errors="coerce")

def ratio(a, b):
    return difflib.SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()

print("=" * 70, "\nAUTO SCORE: what does it score?\n", "=" * 70)
CANDS = [
    ("Hospital Name", "Formatted Address"),
    ("Manual Hospital Name", "Formatted Address"),
    ("Hospital Name", "address_py"),
    ("Manual Hospital Name", "address_py"),
    ("Hospital Address", "address_py"),
    ("Manual Hospital Address", "address_py"),
    ("Hospital Address", "Formatted Address"),
    ("Manual Hospital Address", "Formatted Address"),
    ("Hospital Name", "Locality"),
    ("Hospital Name", "Manual Hospital Name"),
]
print(f"{'pair':56} {'corr':>7} {'mean_ratio':>11} {'mean_score':>11}")
for a, b in CANDS:
    r = pd.Series([ratio(df.at[i, a], df.at[i, b]) for i in samp], index=samp)
    c = r.corr(sc.loc[samp])
    print(f"{a+' vs '+b:56} {c:>7.3f} {r.mean():>11.3f} {sc.loc[samp].mean():>11.3f}")

# maybe it is a token-set / jaccard score
def jac(a, b):
    ta = set(re.findall(r"[a-z0-9]+", str(a).lower()))
    tb = set(re.findall(r"[a-z0-9]+", str(b).lower()))
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0

print("\njaccard variants:")
for a, b in CANDS:
    r = pd.Series([jac(df.at[i, a], df.at[i, b]) for i in samp], index=samp)
    print(f"  {a+' vs '+b:56} corr={r.corr(sc.loc[samp]):>7.3f} mean={r.mean():.3f}")

print("\nAuto Score distribution shape:")
print("  min", sc.min(), "max", sc.max())
print("  n < 0.49:", int((sc < 0.49).sum()), " n >= 0.5:", int((sc >= 0.5).sum()))
print("  histogram:", np.histogram(sc.dropna(), bins=10)[0].tolist())
print("  decimals in raw string:",
      df["Auto Score"].dropna().astype(str).str.split(".").str[-1].str.len().value_counts().head().to_dict())

print("\n" + "=" * 70, "\nFORMATTED ADDRESS: assembled from components?\n", "=" * 70)
comp = ["Road", "Locality", "City", "District", "State", "Country", "Zipcode"]
hits = {c: 0 for c in comp}
present = {c: 0 for c in comp}
for i in samp:
    fa = str(df.at[i, "Formatted Address"])
    for c in comp:
        v = df.at[i, c]
        if pd.notna(v):
            present[c] += 1
            vv = str(v).replace(".0", "") if c == "Zipcode" else str(v)
            if vv in fa:
                hits[c] += 1
print(f"{'component':12} {'present':>8} {'contained in Formatted Address':>32}")
for c in comp:
    pc = 100 * hits[c] / present[c] if present[c] else 0
    print(f"{c:12} {present[c]:>8} {hits[c]:>10} ({pc:.1f}%)")

# does Formatted Address start with a facility name not in any component?
print("\nFormatted Address vs Manual Hospital Name (first segment):")
first = df["Formatted Address"].fillna("").str.split(",").str[0].str.strip()
mhn = df["Manual Hospital Name"].fillna("").str.strip()
print("  first segment == Manual Hospital Name:", int((first.str.lower() == mhn.str.lower()).sum()))
print("  first segment == Hospital Name       :",
      int((first.str.lower() == df["Hospital Name"].fillna("").str.strip().str.lower()).sum()))
r = pd.Series([ratio(first[i], mhn[i]) for i in samp])
print(f"  mean similarity(first segment, Manual Hospital Name) = {r.mean():.3f}")

print("\naddress_py vs components:")
hits2 = {c: 0 for c in comp}
for i in samp:
    ap = str(df.at[i, "address_py"])
    for c in comp:
        v = df.at[i, c]
        if pd.notna(v):
            vv = str(v).replace(".0", "") if c == "Zipcode" else str(v)
            if vv in ap:
                hits2[c] += 1
for c in comp:
    pc = 100 * hits2[c] / present[c] if present[c] else 0
    print(f"  {c:12} contained in address_py: {hits2[c]:>5} ({pc:.1f}%)")

# non-ascii / transliteration in geocoder outputs -> confirms OSM/Nominatim
print("\nnon-ASCII content (geocoder fingerprint):")
for c in ["Hospital Address", "Manual Hospital Address", "address_py", "Formatted Address",
          "Locality", "Road", "City", "State"]:
    v = df[c].dropna().astype(str)
    na = v.str.contains(r"[^\x00-\x7F]")
    print(f"  {c:26}: {int(na.sum()):>5} rows non-ASCII  e.g. {v[na].head(2).tolist()[:2]}")
