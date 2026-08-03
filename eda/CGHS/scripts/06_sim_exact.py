"""CGHS EDA - step 6: pin the exact definitions of the similarity block."""
import pandas as pd, numpy as np, re, itertools
import Levenshtein as lv
from rapidfuzz.distance import JaroWinkler, Jaro

SRC = "/Users/ankitraj2/asar master data/18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
SIM = ["Levenshtein Distance","Jaro Wrinkler Distance","Jaccard Distance","Cosine Distance",
       "Monge Elkan Distance","BWTRLENCD Distance","Monge Elkan Distance*10","Auto Score"]
S = df[SIM].apply(pd.to_numeric)
a = df["Address"].fillna(""); b = df["address_py"].fillna("")

print("======= 1. Levenshtein column is a SIMILARITY on (Address, address_py) =======")
lev_sim = np.array([1 - lv.distance(x,y)/max(len(x),len(y)) if max(len(x),len(y)) else 1.0 for x,y in zip(a,b)])
d = np.abs(lev_sim - S["Levenshtein Distance"])
print(f"  1 - lev/max(len): max|diff|={d.max():.3e}  rows within 1e-8: {int((d<1e-8).sum())}/{len(d)}")

print("\n======= 2. Jaro-Winkler column is JW SIMILARITY on (Address, address_py) =======")
jw_sim = np.array([JaroWinkler.similarity(x,y) for x,y in zip(a,b)])
d = np.abs(jw_sim - S["Jaro Wrinkler Distance"])
print(f"  JaroWinkler.similarity: max|diff|={d.max():.3e}  rows within 1e-8: {int((d<1e-8).sum())}/{len(d)}")
jaro_sim = np.array([Jaro.similarity(x,y) for x,y in zip(a,b)])
print(f"  plain Jaro.similarity : max|diff|={np.abs(jaro_sim-S['Jaro Wrinkler Distance']).max():.3e}")

print("\n======= 3. Jaccard / Cosine: brute-force tokenizations =======")
def toks(s, mode):
    if mode == "chars":        return list(s)
    if mode == "chars_lower":  return list(s.lower())
    if mode == "ws":           return s.split()
    if mode == "ws_lower":     return s.lower().split()
    if mode == "alnum":        return re.findall(r"[A-Za-z0-9]+", s)
    if mode == "alnum_lower":  return re.findall(r"[a-z0-9]+", s.lower())
    if mode == "comma":        return [t.strip() for t in s.split(",")]
    if mode.startswith("qg"):
        k = int(mode[2]); t = s
        return [t[i:i+k] for i in range(len(t)-k+1)]
    if mode.startswith("lqg"):
        k = int(mode[3]); t = s.lower()
        return [t[i:i+k] for i in range(len(t)-k+1)]
    raise ValueError(mode)

MODES = ["chars","chars_lower","ws","ws_lower","alnum","alnum_lower","comma",
         "qg2","qg3","qg4","lqg2","lqg3","lqg4"]
target_j = S["Jaccard Distance"].values
target_c = S["Cosine Distance"].values
best = []
for mode in MODES:
    for setmode in ["set","bag"]:
        js, cs = [], []
        for x, y in zip(a, b):
            X, Y = toks(x, mode), toks(y, mode)
            if setmode == "set":
                P, Q = set(X), set(Y)
                inter = len(P & Q); nx, ny = len(P), len(Q)
            else:
                from collections import Counter
                P, Q = Counter(X), Counter(Y)
                inter = sum((P & Q).values()); nx, ny = sum(P.values()), sum(Q.values())
            uni = nx + ny - inter
            js.append(inter/uni if uni else 0.0)
            cs.append(inter/np.sqrt(nx*ny) if nx and ny else 0.0)
        js = np.array(js); cs = np.array(cs)
        for label, arr, tgt in [("JAC-sim", js, target_j), ("JAC-dist", 1-js, target_j),
                                ("COS-sim", cs, target_c), ("COS-dist", 1-cs, target_c)]:
            md = np.abs(arr - tgt).max()
            best.append((md, mode, setmode, label, float(np.corrcoef(arr,tgt)[0,1])))
best.sort()
print("  top 12 (lowest max abs diff):")
for md, mode, sm, label, corr in best[:12]:
    print(f"    max|diff|={md:.6f} corr={corr:+.4f}  {label} tok={mode} {sm}")

print("\n  row 0 diagnostics: Jaccard reported=%.9f  Cosine reported=%.9f" % (target_j[0], target_c[0]))
for mode in MODES:
    X, Y = set(toks(a[0], mode)), set(toks(b[0], mode))
    i = len(X & Y); u = len(X | Y)
    print(f"    {mode:12s} |X|={len(X):4d} |Y|={len(Y):4d} inter={i:4d} jac={i/u:.6f} cos={i/np.sqrt(len(X)*len(Y)):.6f}")

print("\n======= 4. Monge-Elkan =======")
me = S["Monge Elkan Distance"]
print("  range:", me.min(), me.max(), " (all <0.014 -> not a real Monge-Elkan similarity, which lives in [0,1])")
# ME vs 1/len?
la, lb = a.str.len().values, b.str.len().values
for label, arr in [("1/len(address_py)", 1/lb), ("1/len(Address)", 1/la),
                   ("1/(la+lb)", 1/(la+lb)), ("1/max", 1/np.maximum(la,lb))]:
    print(f"    corr(ME, {label}) = {np.corrcoef(me, arr)[0,1]:+.4f}  max|diff|={np.abs(me-arr).max():.6f}")
ntok_b = np.array([len(re.findall(r'[A-Za-z0-9]+', x)) for x in b])
ntok_a = np.array([len(re.findall(r'[A-Za-z0-9]+', x)) for x in a])
print(f"    corr(ME, ntok_a/ (la*lb)) = {np.corrcoef(me, ntok_a/(la*lb))[0,1]:+.4f}")
print(f"    corr(ME, lev_sim/lb)      = {np.corrcoef(me, lev_sim/lb)[0,1]:+.4f}")
print(f"    corr(ME, lev_sim/la)      = {np.corrcoef(me, lev_sim/la)[0,1]:+.4f}")
print(f"    corr(ME, jw_sim/lb)       = {np.corrcoef(me, jw_sim/lb)[0,1]:+.4f}")
print(f"    corr(ME, 1/ntok_b)        = {np.corrcoef(me, 1/ntok_b)[0,1]:+.4f}")

print("\n======= 5. BWTRLENCD =======")
bw = S["BWTRLENCD Distance"].values
cands = {
    "(la-lb)/la": (la-lb)/la, "(la-lb)/lb": (la-lb)/lb,
    "(lb-la)/la": (lb-la)/la, "(lb-la)/lb": (lb-la)/lb,
    "(la-lb)/max": (la-lb)/np.maximum(la,lb), "(la-lb)/(la+lb)": (la-lb)/(la+lb),
    "1-la/lb": 1-la/lb, "1-lb/la": 1-lb/la,
}
for k, v in cands.items():
    print(f"    corr(BWT, {k:18s}) = {np.corrcoef(bw, v)[0,1]:+.4f} max|diff|={np.abs(bw-v).max():.4f}")
# 259 exact zeros -> look at those rows
z = np.where(bw == 0)[0]
print("  zero-BWT rows: n=%d; len(Address) vs len(address_py) for first 10:" % len(z))
for i in z[:10]:
    print(f"    row {i}: la={la[i]} lb={lb[i]} lev_sim={lev_sim[i]:.4f}")
print("  among zero-BWT rows, la==lb:", int((la[z]==lb[z]).sum()))
# word counts
wa = np.array([len(x.split()) for x in a]); wb = np.array([len(x.split()) for x in b])
print("  among zero-BWT rows, wordcount equal:", int((wa[z]==wb[z]).sum()))
for k, v in {"(wa-wb)/wa": (wa-wb)/wa, "(wa-wb)/wb": (wa-wb)/wb,
             "(wa-wb)/max(w)": (wa-wb)/np.maximum(wa,wb)}.items():
    print(f"    corr(BWT, {k:16s}) = {np.corrcoef(bw, v)[0,1]:+.4f} max|diff|={np.abs(bw-v).max():.4f}")
# comma-token counts
ca = np.array([len(x.split(',')) for x in a]); cb = np.array([len(x.split(',')) for x in b])
print("  among zero-BWT rows, comma-token count equal:", int((ca[z]==cb[z]).sum()))

print("\n======= 6. Auto Score exact affine form =======")
cols3 = ["Levenshtein Distance","Jaro Wrinkler Distance","Monge Elkan Distance*10"]
A = np.hstack([S[cols3].values, np.ones((len(S),1))])
coef, res, rank, sv = np.linalg.lstsq(A, S["Auto Score"].values, rcond=None)
pred = A @ coef
print("  rank:", rank, "coef:", dict(zip(cols3+["const"], np.round(coef,9))))
print("  sum of 3 weights:", coef[:3].sum())
print("  R^2:", 1-((S['Auto Score']-pred)**2).sum()/((S['Auto Score']-S['Auto Score'].mean())**2).sum(),
      " max abs resid:", np.abs(S['Auto Score']-pred).max())
# Try all 6-subsets to find the minimal exact set
from itertools import combinations
base = ["Levenshtein Distance","Jaro Wrinkler Distance","Jaccard Distance","Cosine Distance",
        "Monge Elkan Distance*10","BWTRLENCD Distance"]
print("\n  minimal exact subsets (max resid < 1e-6):")
for k in range(1, 5):
    for cc in combinations(base, k):
        Ak = np.hstack([S[list(cc)].values, np.ones((len(S),1))])
        ck, *_ = np.linalg.lstsq(Ak, S["Auto Score"].values, rcond=None)
        r = np.abs(S["Auto Score"].values - Ak@ck).max()
        if r < 1e-6:
            print(f"    {cc} -> max resid {r:.2e} coef {np.round(ck,8)}")
# equal-weight mean of similarity-form columns?
print("\n  mean(Lev, JW, Jac, Cos, ME10, BWT):", float((S[base].mean(axis=1) - S['Auto Score']).abs().max()))
print("  mean(Lev, JW, ME10):", float((S[cols3].mean(axis=1) - S['Auto Score']).abs().max()))
