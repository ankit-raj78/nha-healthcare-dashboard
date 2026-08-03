"""CGHS EDA - step 7: remaining unknowns in the similarity block."""
import pandas as pd, numpy as np, re, zlib, bz2, lzma
from collections import Counter
from fractions import Fraction
import Levenshtein as lv
from rapidfuzz.distance import JaroWinkler

SRC = "/Users/ankitraj2/asar master data/18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
S = df[["Levenshtein Distance","Jaro Wrinkler Distance","Jaccard Distance","Cosine Distance",
        "Monge Elkan Distance","BWTRLENCD Distance","Monge Elkan Distance*10","Auto Score"]].apply(pd.to_numeric)
a = df["Address"].fillna(""); b = df["address_py"].fillna("")
la = a.str.len().values; lb = b.str.len().values

print("===== confirm Jaccard/Cosine = bag-of-CHARACTERS similarity =====")
jac, cos = [], []
for x, y in zip(a, b):
    P, Q = Counter(x), Counter(y)
    i = sum((P & Q).values()); nx, ny = len(x), len(y)
    jac.append(i/(nx+ny-i) if (nx+ny-i) else 0)
    cos.append(i/np.sqrt(nx*ny) if nx and ny else 0)
jac = np.array(jac); cos = np.array(cos)
print("  Jaccard: max|diff|=%.3e  exact(<1e-9) rows=%d/%d" % (np.abs(jac-S['Jaccard Distance']).max(),
      int((np.abs(jac-S['Jaccard Distance'])<1e-9).sum()), len(df)))
print("  Cosine : max|diff|=%.3e  exact(<1e-9) rows=%d/%d" % (np.abs(cos-S['Cosine Distance']).max(),
      int((np.abs(cos-S['Cosine Distance'])<1e-9).sum()), len(df)))
print("  row0: multiset inter=%d  jac=%.9f (reported %.9f)  cos=%.9f (reported %.9f)" % (
      sum((Counter(a[0]) & Counter(b[0])).values()), jac[0], S['Jaccard Distance'][0], cos[0], S['Cosine Distance'][0]))

print("\n===== the 11 Levenshtein rows that do NOT match 1-lev/max(len) =====")
levsim = np.array([1 - lv.distance(x,y)/max(len(x),len(y)) for x,y in zip(a,b)])
bad = np.where(np.abs(levsim - S['Levenshtein Distance']) > 1e-8)[0]
print("  n =", len(bad))
for i in bad:
    rep = S['Levenshtein Distance'][i]
    print(f"  row {i}: reported={rep:.9f} computed={levsim[i]:.9f} diff={rep-levsim[i]:+.6f} la={la[i]} lb={lb[i]}")
    print(f"      1-lev/len(Address)   = {1-lv.distance(a[i],b[i])/la[i]:.9f}")
    print(f"      1-lev/len(address_py)= {1-lv.distance(a[i],b[i])/lb[i]:.9f}")
    print(f"      lv.ratio             = {lv.ratio(a[i],b[i]):.9f}")
    print(f"      Address    : {a[i][:110]!r}")
    print(f"      address_py : {b[i][:110]!r}")
    # non-ascii?
    print(f"      non-ascii in Address: {[c for c in a[i] if ord(c)>127][:6]}  in address_py: {[c for c in b[i] if ord(c)>127][:6]}")

print("\n===== BWTRLENCD as Normalized Compression Distance (BWT+RLE) =====")
def bwt(s):
    s = s + "\x03"
    rot = sorted(s[i:] + s[:i] for i in range(len(s)))
    return "".join(r[-1] for r in rot)
def rle(s):
    out, i = [], 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]: j += 1
        out.append(s[i] + str(j-i)); i = j
    return "".join(out)
def C(s, mode):
    if mode == "bwt_rle": return len(rle(bwt(s)))
    if mode == "rle":     return len(rle(s))
    if mode == "zlib":    return len(zlib.compress(s.encode(), 9))
    if mode == "bz2":     return len(bz2.compress(s.encode(), 9))
    if mode == "lzma":    return len(lzma.compress(s.encode()))
    raise ValueError

sub = df.index[:400]  # BWT is O(n^2 log n); sample for speed
for mode in ["bwt_rle", "rle", "bz2", "zlib"]:
    for form in ["ncd", "ncd_min_over_max", "diff_ratio"]:
        vals = []
        for i in sub:
            x, y = a[i], b[i]
            cx, cy, cxy = C(x, mode), C(y, mode), C(x+y, mode)
            if form == "ncd":
                v = (cxy - min(cx,cy)) / max(cx,cy)
            elif form == "ncd_min_over_max":
                v = (cxy - max(cx,cy)) / min(cx,cy)
            else:
                v = (cx - cy) / max(cx, cy)
            vals.append(v)
        vals = np.array(vals); tgt = S['BWTRLENCD Distance'].values[:len(sub)]
        print(f"  {mode:8s} {form:18s} corr={np.corrcoef(vals,tgt)[0,1]:+.4f} max|diff|={np.abs(vals-tgt).max():.4f} "
              f"exact={int((np.abs(vals-tgt)<1e-9).sum())}")
# 1 - NCD forms
for mode in ["bwt_rle", "rle"]:
    vals = []
    for i in sub:
        x, y = a[i], b[i]
        cx, cy, cxy = C(x, mode), C(y, mode), C(x+y, mode)
        vals.append(1 - (cxy - min(cx,cy))/max(cx,cy))
    vals = np.array(vals); tgt = S['BWTRLENCD Distance'].values[:len(sub)]
    print(f"  {mode:8s} 1-NCD              corr={np.corrcoef(vals,tgt)[0,1]:+.4f} max|diff|={np.abs(vals-tgt).max():.4f} "
          f"exact={int((np.abs(vals-tgt)<1e-9).sum())}")

print("\n===== Monge-Elkan: real ME vs reported =====")
def tok(s): return re.findall(r"[A-Za-z0-9]+", s)
me_jw, me_lev = [], []
for x, y in zip(a, b):
    P, Q = tok(x), tok(y)
    if not P or not Q:
        me_jw.append(0); me_lev.append(0); continue
    me_jw.append(np.mean([max(JaroWinkler.similarity(p,q) for q in Q) for p in P]))
    me_lev.append(np.mean([max(1-lv.distance(p,q)/max(len(p),len(q)) for q in Q) for p in P]))
me_jw = np.array(me_jw); me_lev = np.array(me_lev)
rep = S['Monge Elkan Distance'].values
for name, arr in [("ME(JW inner)", me_jw), ("ME(Lev inner)", me_lev)]:
    print(f"  {name}: mean={arr.mean():.4f} corr w/ reported={np.corrcoef(arr,rep)[0,1]:+.4f}")
    for div, dn in [(la,"len(Address)"), (lb,"len(address_py)"), (la*lb,"la*lb"),
                    (np.array([len(tok(x)) for x in a])*np.array([len(tok(y)) for y in b]), "ntokA*ntokB")]:
        v = arr/div
        print(f"      /{dn:16s} corr={np.corrcoef(v,rep)[0,1]:+.4f} max|diff|={np.abs(v-rep).max():.6f} exact={int((np.abs(v-rep)<1e-9).sum())}")
# maybe ME = ME10/10 only; and ME10 itself is the real quantity. check ME10 vs real ME
print("  reported ME*10 mean:", S['Monge Elkan Distance*10'].mean())

print("\n===== Auto Score: hunt for clean weights =====")
cols3 = ["Levenshtein Distance","Jaro Wrinkler Distance","Monge Elkan Distance*10"]
A = np.hstack([S[cols3].values, np.ones((len(S),1))])
coef, *_ = np.linalg.lstsq(A, S["Auto Score"].values, rcond=None)
print("  weights:", [f"{c:.10f}" for c in coef])
print("  sum of 3:", f"{coef[:3].sum():.12f}")
for c in coef:
    f = Fraction(c).limit_denominator(1000)
    print(f"   {c:.10f} ~ {f} ({float(f):.10f})")
# scaled forms
print("\n  Auto Score min/max:", S['Auto Score'].min(), S['Auto Score'].max())
raw = 0.186738664*S['Levenshtein Distance'] + 0.197525676*S['Jaro Wrinkler Distance'] + 0.615735659*S['Monge Elkan Distance*10']
print("  weighted-avg part range:", raw.min(), raw.max(), " + const 0.428705785")
# is const maybe 3/7? 0.4285714
print("  3/7 =", 3/7, " diff from const:", 0.428705785-3/7)
