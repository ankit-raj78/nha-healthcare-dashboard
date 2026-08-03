"""CGHS EDA - step 9: full-dataset confirmation of BWTRLENCD + specialty family split + dupe examples."""
import pandas as pd, numpy as np, re
from collections import Counter
from rapidfuzz.distance import OSA, JaroWinkler

SRC = "/Users/ankitraj2/asar master data/18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
S = df[["Levenshtein Distance","BWTRLENCD Distance","Auto Score"]].apply(pd.to_numeric)
a = df["Address"].fillna(""); b = df["address_py"].fillna("")

def bwt(s):
    t = s + "\x03"
    return "".join(r[-1] for r in sorted(t[i:]+t[:i] for i in range(len(t))))
def rle_runs(s):
    out, i = [], 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]: j += 1
        n = j-i; out.append(s[i] if n == 1 else s[i]+str(n)); i = j
    return "".join(out)
Cc = lambda s: len(rle_runs(bwt(s)))

print("=== BWTRLENCD over ALL rows: 1 - NCD(BWT+RLE) ===")
vals = []
for x, y in zip(a, b):
    cx, cy, cxy = Cc(x), Cc(y), Cc(x+y)
    vals.append((cx+cy-cxy)/max(cx,cy))
vals = np.array(vals); tgt = S["BWTRLENCD Distance"].values
d = np.abs(vals-tgt)
print("  exact(<1e-8): %d/%d   max|diff|=%.6f   corr=%.6f" % (int((d<1e-8).sum()), len(df), d.max(), np.corrcoef(vals,tgt)[0,1]))
print("  mismatching rows:", np.where(d>=1e-8)[0][:20].tolist())

print("\n=== specialty family exclusivity (full) ===")
sp = df["Specialities_Selected"]
def fam(t):
    if t == "NA": return "NA"
    if re.fullmatch(r"[MS]\d+", t): return "NUM"
    if re.fullmatch(r"[A-Z]{2}", t): return "ALPHA"
    return "OTHER"
famrow, vocab_by_fam = {}, {"ALPHA": Counter(), "NUM": Counter(), "NA": Counter()}
for i, v in sp.dropna().items():
    ts = [x.strip() for x in v.split(",") if x.strip()]
    fs = set(fam(t) for t in ts)
    famrow[i] = "+".join(sorted(fs))
    for t in ts: vocab_by_fam[fam(t)][t] += 1
print("  rows by family set:", Counter(famrow.values()))
print("  rows containing BOTH ALPHA and NUM tokens:",
      sum(1 for k in famrow.values() if "ALPHA" in k and "NUM" in k))
print("\n  ALPHA vocabulary (%d codes):" % len(vocab_by_fam["ALPHA"]), sorted(vocab_by_fam["ALPHA"]))
print("  NUM vocabulary (%d codes):" % len(vocab_by_fam["NUM"]),
      sorted(vocab_by_fam["NUM"], key=lambda k: (k[0], int(k[1:]))))
print("  NA token occurrences:", dict(vocab_by_fam["NA"]))
fr = pd.Series(famrow)
print("\n  family x State (top):")
print(pd.crosstab(fr, df.loc[fr.index,"State"]).T.sort_values("alpha" if "alpha" in fr.unique() else fr.unique()[0], ascending=False).head(10).to_string())
print("\n  family x Hospital_Id prefix:")
pref = df["Hospital_Id"].str.extract(r"^([A-Z]+)")[0]
print(pd.crosstab(fr, pref.loc[fr.index]).to_string())
print("\n  family x OnBoarded_For_Convergence_Scheme:")
print(pd.crosstab(fr, df.loc[fr.index,"OnBoarded_For_Convergence_Scheme"]).to_string())

print("\n=== within-row duplicate specialty tokens ===")
dups = [(i, v) for i, v in sp.dropna().items()
        if len([x for x in v.split(",") if x.strip()]) != len(set(x.strip() for x in v.split(",") if x.strip()))]
print("  rows:", len(dups))
for i, v in dups[:4]:
    print(f"    row {i}: {v}")

print("\n=== duplicate / near-duplicate examples for issues.md ===")
core = ["Hospital_Name","District","State","Address","Latitude","Longitude"]
dmask = df.duplicated(subset=core, keep=False)
sub = df[dmask].sort_values(core)
print("  rows in exact (name,district,state,address,lat,lon) dupe groups:", int(dmask.sum()),
      " groups:", sub.groupby(core).ngroups)
for k, g in list(sub.groupby(core))[:6]:
    print(f"  * {k[0]!r} / {k[1]} / {k[2]}  lat={k[4]} lon={k[5]}")
    print(g[["Hospital_Id","Specialities_Selected","Hospital_Type","OnBoarded_For_Convergence_Scheme"]].to_string())

print("\n=== centroid coordinates identified ===")
pair = df["Latitude"] + "," + df["Longitude"]
vc = pair.value_counts()
for k, v in vc[vc >= 4].items():
    idx = df.index[pair == k]
    st = df.loc[idx, "State"].value_counts().to_dict()
    dis = df.loc[idx, "District"].value_counts().to_dict()
    print(f"  {k}  n={v}  states={st}  districts={list(dis)[:3]}")

print("\n=== rows whose reverse geocode landed outside India ===")
lat = pd.to_numeric(df["Latitude"]); lon = pd.to_numeric(df["Longitude"])
bad = df[~(lat.between(6,38) & lon.between(68,98))]
print(bad[["Hospital_Id","Hospital_Name","District","State","Latitude","Longitude","address_py"]].to_string())

print("\n=== pincode outlier ===")
print(df[df["Postcode_py"] == "3302"][["Hospital_Id","Hospital_Name","District","State","Postcode_py","address_py"]].to_string())

print("\n=== bad phone rows ===")
hc = df["Hospital_Contact"]
print(df[hc.isna() | ~hc.fillna("").str.match(r"^[6-9]\d{9}$")][["Hospital_Id","Hospital_Name","State","Hospital_Contact"]].head(20).to_string())
print("null phone:", int(hc.isna().sum()))

print("\n=== malformed Hospital_Id ===")
print(df[~df["Hospital_Id"].str.match(r"^(HOSP|LAB)")][["Hospital_Id","Hospital_Name","District","State"]].to_string())

print("\n=== Hospital_Name quality ===")
n = df["Hospital_Name"]
print("  leading/trailing whitespace:", int((n != n.str.strip()).sum()))
print("  double spaces:", int(n.str.contains("  ").sum()))
print("  ALL CAPS:", int((n == n.str.upper()).sum()), " all lower:", int((n == n.str.lower()).sum()),
      " mixed:", int(((n != n.str.upper()) & (n != n.str.lower())).sum()))
print("  contains non-ascii:", int(n.apply(lambda s: any(ord(c) > 127 for c in s)).sum()))
print("  shortest names:", n[n.str.len() <= 8].tolist())
print("  contains 'unit of':", int(n.str.lower().str.contains("unit of").sum()))
print("  address_py non-ascii rows:", int(df['address_py'].apply(lambda s: any(ord(c)>127 for c in str(s))).sum()))
