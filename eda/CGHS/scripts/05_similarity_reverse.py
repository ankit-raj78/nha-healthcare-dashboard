"""CGHS EDA - step 5: reverse-engineer cols 19-26 (the string-similarity block)."""
import pandas as pd, numpy as np, re, itertools
import Levenshtein as lv
from rapidfuzz.distance import JaroWinkler
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer

SRC = "/Users/ankitraj2/asar master data/18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
SIM = ["Levenshtein Distance", "Jaro Wrinkler Distance", "Jaccard Distance", "Cosine Distance",
       "Monge Elkan Distance", "BWTRLENCD Distance", "Monge Elkan Distance*10", "Auto Score"]
S = df[SIM].apply(pd.to_numeric)

print("======== descriptive stats ========")
print(S.describe(percentiles=[.01,.05,.25,.5,.75,.95,.99]).T.to_string())
print("\nnegative-value counts:")
print((S < 0).sum().to_string())
print("\nvalues > 1 counts:")
print((S > 1).sum().to_string())

print("\n======== algebraic relations ========")
me, me10 = S["Monge Elkan Distance"], S["Monge Elkan Distance*10"]
print("max|ME*10 - ME10| =", float((me*10 - me10).abs().max()))
print("corr(ME, ME10) =", float(me.corr(me10)))

print("\n---- Auto Score as linear combo of the other 7 ----")
X = S[["Levenshtein Distance","Jaro Wrinkler Distance","Jaccard Distance","Cosine Distance",
       "Monge Elkan Distance","BWTRLENCD Distance","Monge Elkan Distance*10"]].values
y = S["Auto Score"].values
A = np.hstack([X, np.ones((len(X),1))])
coef, res, rank, sv = np.linalg.lstsq(A, y, rcond=None)
pred = A @ coef
print("coefficients:", dict(zip(["Lev","JW","Jac","Cos","ME","BWT","ME10","intercept"], np.round(coef,6))))
print("R^2 =", 1 - ((y-pred)**2).sum()/((y-y.mean())**2).sum(), " max abs resid:", np.abs(y-pred).max())

# without ME10 (collinear with ME)
cols5 = ["Levenshtein Distance","Jaro Wrinkler Distance","Jaccard Distance","Cosine Distance","BWTRLENCD Distance","Monge Elkan Distance*10"]
A2 = np.hstack([S[cols5].values, np.ones((len(S),1))])
c2, *_ = np.linalg.lstsq(A2, y, rcond=None)
p2 = A2 @ c2
print("\nfit on", cols5)
print("coefficients:", dict(zip(cols5+["intercept"], np.round(c2,6))))
print("R^2 =", 1-((y-p2)**2).sum()/((y-y.mean())**2).sum(), " max abs resid:", np.abs(y-p2).max())

# simple mean hypotheses
for combo in [
    ["Levenshtein Distance","Jaro Wrinkler Distance","Jaccard Distance","Cosine Distance","Monge Elkan Distance*10","BWTRLENCD Distance"],
    ["Levenshtein Distance","Jaro Wrinkler Distance","Jaccard Distance","Cosine Distance","Monge Elkan Distance*10"],
    ["Levenshtein Distance","Jaro Wrinkler Distance","Jaccard Distance","Cosine Distance","Monge Elkan Distance","BWTRLENCD Distance"],
]:
    d = (S[combo].mean(axis=1) - y).abs().max()
    print(f"mean({len(combo)} cols {combo[-2:]}) max abs diff to Auto Score: {d:.8f}")

print("\n======== which two fields were compared? ========")
a = df["Address"].fillna("")
b = df["address_py"].fillna("")
n = df["Hospital_Name"].fillna("")

def norm_lev(x, y):
    if max(len(x), len(y)) == 0: return 0.0
    return lv.distance(x, y) / max(len(x), len(y))

pairs = {
    "Address vs address_py": (a, b),
    "Hospital_Name vs address_py": (n, b),
    "Hospital_Name vs Address": (n, a),
    "Address.lower vs address_py.lower": (a.str.lower(), b.str.lower()),
}
for label, (x, y_) in pairs.items():
    lev = np.array([norm_lev(p, q) for p, q in zip(x, y_)])
    jw  = np.array([JaroWinkler.distance(p, q) for p, q in zip(x, y_)])
    print(f"\n-- {label}")
    print(f"   normalized-Levenshtein: corr={np.corrcoef(lev, S['Levenshtein Distance'])[0,1]:.4f}  "
          f"max|diff|={np.abs(lev-S['Levenshtein Distance']).max():.6f} mean|diff|={np.abs(lev-S['Levenshtein Distance']).mean():.6f}")
    print(f"   JaroWinkler distance  : corr={np.corrcoef(jw, S['Jaro Wrinkler Distance'])[0,1]:.4f}  "
          f"max|diff|={np.abs(jw-S['Jaro Wrinkler Distance']).max():.6f} mean|diff|={np.abs(jw-S['Jaro Wrinkler Distance']).mean():.6f}")

print("\n-- row 0 manual check")
print("Address   :", repr(a[0]), "len", len(a[0]))
print("address_py:", repr(b[0]), "len", len(b[0]))
print("lv.distance:", lv.distance(a[0], b[0]), "/ max len", max(len(a[0]),len(b[0])), "=", lv.distance(a[0],b[0])/max(len(a[0]),len(b[0])))
print("reported Levenshtein Distance:", S['Levenshtein Distance'][0])
print("lv ratio-based:", 1-lv.ratio(a[0],b[0]))
print("lv.distance/sum len:", lv.distance(a[0],b[0])/(len(a[0])+len(b[0])))
print("JW distance:", JaroWinkler.distance(a[0],b[0]), " reported:", S['Jaro Wrinkler Distance'][0])
print("JW similarity:", JaroWinkler.similarity(a[0],b[0]))

print("\n======== token-set Jaccard / Cosine check (Address vs address_py) ========")
def tokset(s): return set(re.findall(r"[a-z0-9]+", s.lower()))
jac_sim, jac_dist, cos_sim = [], [], []
for p, q in zip(a, b):
    P, Q = tokset(p), tokset(q)
    u = len(P | Q)
    inter = len(P & Q)
    js = inter/u if u else 0
    jac_sim.append(js); jac_dist.append(1-js)
    cos_sim.append(inter/np.sqrt(len(P)*len(Q)) if P and Q else 0)
jac_sim = np.array(jac_sim); jac_dist = np.array(jac_dist); cos_sim = np.array(cos_sim)
for name, arr in [("token jaccard sim", jac_sim), ("token jaccard dist", jac_dist)]:
    print(f"{name}: corr w/ 'Jaccard Distance' = {np.corrcoef(arr, S['Jaccard Distance'])[0,1]:.4f} max|diff|={np.abs(arr-S['Jaccard Distance']).max():.4f}")
for name, arr in [("token cosine sim", cos_sim), ("token cosine dist", 1-cos_sim)]:
    print(f"{name}: corr w/ 'Cosine Distance' = {np.corrcoef(arr, S['Cosine Distance'])[0,1]:.4f} max|diff|={np.abs(arr-S['Cosine Distance']).max():.4f}")

# char 2-gram jaccard
def ng(s, k=2):
    s = s.lower(); return set(s[i:i+k] for i in range(len(s)-k+1))
jg = np.array([1 - (len(ng(p)&ng(q))/len(ng(p)|ng(q)) if ng(p)|ng(q) else 0) for p,q in zip(a,b)])
print(f"char-2gram jaccard dist: corr w/ 'Jaccard Distance' = {np.corrcoef(jg, S['Jaccard Distance'])[0,1]:.4f} max|diff|={np.abs(jg-S['Jaccard Distance']).max():.4f}")

print("\n======== BWTRLENCD ========")
bw = S["BWTRLENCD Distance"]
print("negatives:", int((bw<0).sum()), "zeros:", int((bw==0).sum()), "positives:", int((bw>0).sum()))
lendiff = (a.str.len() - b.str.len())
maxlen = np.maximum(a.str.len(), b.str.len())
print("corr(BWT, (lenA-lenB)/maxlen):", float(np.corrcoef(bw, lendiff/maxlen)[0,1]))
print("corr(BWT, (lenB-lenA)/maxlen):", float(np.corrcoef(bw, -lendiff/maxlen)[0,1]))
print("max|BWT - (lenA-lenB)/lenB|:", float(np.abs(bw - lendiff/b.str.len()).max()))
print("corr(BWT, 1/len):", float(np.corrcoef(bw, 1/maxlen)[0,1]))

print("\n======== signal test: do the metrics separate good vs bad geocodes? ========")
# rows landing on a shared 'centroid' coordinate (>=5 rows same coord) are suspect geocodes
pair = df["Latitude"] + "," + df["Longitude"]
vc = pair.value_counts()
centroid_rows = pair.map(vc) >= 5
print("rows on a coord shared by >=5 rows:", int(centroid_rows.sum()))
for c in SIM:
    print(f"   {c:26s} centroid-mean={S.loc[centroid_rows,c].mean():.4f}  other-mean={S.loc[~centroid_rows,c].mean():.4f}")
# correlation of Auto Score with an independent 'is the geocode right' proxy:
# does address_py's state token match State?
statetok = df.apply(lambda r: str(r["State"]).lower().replace("nct of ","") in str(r["address_py"]).lower(), axis=1)
print("\naddress_py mentions the State value:", int(statetok.sum()), f"({100*statetok.mean():.1f}%)")
for c in SIM:
    print(f"   {c:26s} state-match-mean={S.loc[statetok,c].mean():.4f}  mismatch-mean={S.loc[~statetok,c].mean():.4f}")
print("\nAuto Score AUC vs state-match:")
from sklearn.metrics import roc_auc_score
for c in SIM:
    try:
        print(f"   {c:26s} AUC={roc_auc_score(statetok.astype(int), S[c]):.4f}")
    except Exception as e:
        print(c, e)
print("\nSIM correlation matrix:")
print(S.corr().round(3).to_string())
