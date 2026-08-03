"""Inspect the real near-dupe candidates, and quantify Manual Hospital Name truncation."""
import re

import numpy as np
import pandas as pd

SRC = "/Users/ankitraj2/asar master data/18_MAY_23_SRK_PMJAY_validated_and_standardized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
n = len(df)
la = pd.to_numeric(df["API Latitude"], errors="coerce")
lo = pd.to_numeric(df["API Longitude"], errors="coerce")

def nm(s):
    return (s.fillna("").str.upper()
             .str.replace(r"[^A-Z0-9 ]+", " ", regex=True)
             .str.replace(r"\b(HOSPITAL|HOSPITALS|CLINIC|CENTRE|CENTER|PVT|LTD|PRIVATE|LIMITED|AND|THE)\b", " ", regex=True)
             .str.replace(r"\s+", " ", regex=True).str.strip())

print("=" * 70, "\nNAME+GEO NEAR DUPES (the credible ones)\n", "=" * 70)
key = nm(df["Manual Hospital Name"]) + "|" + la.round(4).astype(str) + "|" + lo.round(4).astype(str)
vc = key.value_counts()
groups = vc[vc > 1]
print(f"groups={len(groups)}  rows involved={int(groups.sum())}  redundant rows={int(groups.sum()-len(groups))}")
for g in groups.index:
    idx = list(df.index[key == g])
    print(f"\n  group ({len(idx)} rows): {g[:80]}")
    for i in idx:
        print(f"    row {i} SrNo={df.at[i,'Sr No']:>6} | HN={df.at[i,'Hospital Name'][:48]!r}")
        print(f"             addr={str(df.at[i,'Manual Hospital Address'])[:60]!r} "
              f"email={df.at[i,'Hospital E-Mail']} type={df.at[i,'Hospital Type']}")
        print(f"             emp={str(df.at[i,'Specialities Empanelled'])[:60]!r}")

# strict: identical on raw Hospital Name + API point
print("\n" + "=" * 70, "\nSTRICTER DUPE KEYS\n", "=" * 70)
for lab, k in [
    ("raw Hospital Name + API point", df["Hospital Name"].fillna("") + "|" + df["API Latitude"].astype(str) + "|" + df["API Longitude"].astype(str)),
    ("raw Hospital Name + Manual Address", df["Hospital Name"].fillna("") + "|" + df["Manual Hospital Address"].fillna("")),
    ("Manual Name + Manual Address", df["Manual Hospital Name"].fillna("") + "|" + df["Manual Hospital Address"].fillna("")),
    ("Manual Name + district + state + API point", df["Manual Hospital Name"].fillna("") + "|" + df["Manual District"].fillna("") + "|" + df["Manual state"].fillna("") + "|" + df["API Latitude"].astype(str) + "|" + df["API Longitude"].astype(str)),
    ("Hospital Address exact", df["Hospital Address"].fillna("")),
    ("Hospital E-Mail exact (non-null, valid)", df["Hospital E-Mail"].where(df["Hospital E-Mail"].fillna("").str.contains("@"))),
]:
    d = k.duplicated().sum()
    v = k.value_counts()
    print(f"  {lab:44}: dup rows={int(d):>5} groups={int((v>1).sum()):>5}")

# ============ Manual Hospital Name truncation ============
print("\n" + "=" * 70, "\nManual Hospital Name TRUNCATION\n", "=" * 70)
hn = nm(df["Hospital Name"])
mhn = nm(df["Manual Hospital Name"])
print(f"tokens: Hospital Name mean={hn.str.split().str.len().mean():.2f} "
      f"Manual mean={mhn.str.split().str.len().mean():.2f}")
shorter = mhn.str.len() < hn.str.len()
print(f"Manual is shorter: {int(shorter.sum())} ({100*shorter.mean():.2f}%)")
prefix = [bool(h.startswith(m)) and h != m for h, m in zip(hn, mhn)]
print(f"Manual is a strict prefix of Hospital Name (normalised): {sum(prefix)} "
      f"({100*sum(prefix)/n:.2f}%)  -> location suffix dropped")
sub = [(m in h) and h != m for h, m in zip(hn, mhn)]
print(f"Manual is a strict substring of Hospital Name: {sum(sub)} ({100*sum(sub)/n:.2f}%)")
print("\nexamples of dropped location qualifier:")
c = 0
for i in df.index:
    if prefix[i] and len(hn[i]) - len(mhn[i]) > 5:
        print(f"  row {i}: HN={df.at[i,'Hospital Name']!r}\n          MHN={df.at[i,'Manual Hospital Name']!r}")
        c += 1
        if c >= 8:
            break
# distinctiveness comparison
for lab, s in [("Hospital Name", hn), ("Manual Hospital Name", mhn)]:
    v = s.value_counts()
    print(f"\n{lab}: distinct={s.nunique()} names_shared_by_gt1={int((v>1).sum())} "
          f"rows_on_shared_name={int(v[v>1].sum())} ({100*v[v>1].sum()/n:.2f}%)")

# ============ within-(district,state) name collision ============
print("\n" + "=" * 70, "\nBLOCKING VIABILITY: collisions inside (state,district)\n", "=" * 70)
for lab, s in [("Hospital Name", hn), ("Manual Hospital Name", mhn)]:
    k = s + "|" + df["Manual District"].fillna("").str.upper() + "|" + df["Manual state"].fillna("")
    v = k.value_counts()
    print(f"  {lab:22}: collision rows={int(v[v>1].sum())} ({100*v[v>1].sum()/n:.2f}%) groups={int((v>1).sum())}")

# how far apart are rows that collide on name+district+state?
k = mhn + "|" + df["Manual District"].fillna("").str.upper() + "|" + df["Manual state"].fillna("")
v = k.value_counts()
coll = v[v > 1].index
R = 6371.0
dists = []
for g in coll:
    idx = list(df.index[k == g])
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            i, j = idx[a], idx[b]
            if pd.notna(la[i]) and pd.notna(la[j]):
                p1, p2 = np.radians(la[i]), np.radians(la[j])
                dl = np.radians(lo[j] - lo[i])
                h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
                dists.append((2 * R * np.arcsin(np.sqrt(h)), i, j, g))
dists.sort()
print(f"\n  pairs colliding on name+district+state: {len(dists)}")
for thr in [0.1, 0.5, 1, 5, 20]:
    print(f"    within {thr:>4} km: {sum(1 for d in dists if d[0] <= thr)}")
print("  closest pairs (likely TRUE duplicates):")
for d, i, j, g in dists[:12]:
    print(f"    {d*1000:8.0f} m | rows {i},{j} | {df.at[i,'Hospital Name'][:38]!r} vs {df.at[j,'Hospital Name'][:38]!r}")
