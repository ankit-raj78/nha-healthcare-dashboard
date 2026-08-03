"""CGHS EDA - step 8: Damerau check, BWT/ME variant search, signal test, specialty families, ER readiness."""
import pandas as pd, numpy as np, re, itertools
from collections import Counter
import Levenshtein as lv
from rapidfuzz.distance import JaroWinkler, DamerauLevenshtein, OSA
from sklearn.metrics import roc_auc_score

SRC = "/Users/ankitraj2/asar master data/18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
S = df[["Levenshtein Distance","Jaro Wrinkler Distance","Jaccard Distance","Cosine Distance",
        "Monge Elkan Distance","BWTRLENCD Distance","Monge Elkan Distance*10","Auto Score"]].apply(pd.to_numeric)
a = df["Address"].fillna(""); b = df["address_py"].fillna("")
la = a.str.len().values; lb = b.str.len().values
N = len(df)

print("===== 1. Levenshtein col = 1 - DamerauLevenshtein/max(len)? =====")
for name, fn in [("Levenshtein", lambda x,y: lv.distance(x,y)),
                 ("Damerau-Lev", lambda x,y: DamerauLevenshtein.distance(x,y)),
                 ("OSA",         lambda x,y: OSA.distance(x,y))]:
    v = np.array([1 - fn(x,y)/max(len(x),len(y)) for x,y in zip(a,b)])
    d = np.abs(v - S["Levenshtein Distance"])
    print(f"  {name:12s}: exact rows={int((d<1e-8).sum())}/{N}  max|diff|={d.max():.6f}")

print("\n===== 2. BWTRLENCD variant search (first 250 rows) =====")
def bwt(s, sent="\x03", pos="end"):
    t = s + sent if pos == "end" else sent + s
    rot = sorted(t[i:] + t[:i] for i in range(len(t)))
    return "".join(r[-1] for r in rot)
def rle_all(s):
    out, i = [], 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]: j += 1
        out.append(s[i] + str(j-i)); i = j
    return "".join(out)
def rle_runs(s):  # only encode runs >1
    out, i = [], 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]: j += 1
        n = j-i
        out.append(s[i] if n == 1 else s[i]+str(n)); i = j
    return "".join(out)
def rle_pairs(s):  # count of runs
    n, i = 0, 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]: j += 1
        n += 1; i = j
    return "x"*n

M = 250
tgt = S["BWTRLENCD Distance"].values[:M]
best = []
for enc_name, enc in [("bwt+rle_all", lambda s: len(rle_all(bwt(s)))),
                      ("bwt+rle_runs", lambda s: len(rle_runs(bwt(s)))),
                      ("bwt+nruns", lambda s: len(rle_pairs(bwt(s)))),
                      ("rle_all", lambda s: len(rle_all(s))),
                      ("nruns", lambda s: len(rle_pairs(s)))]:
    cx = np.array([enc(a[i]) for i in range(M)])
    cy = np.array([enc(b[i]) for i in range(M)])
    cxy = np.array([enc(a[i]+b[i]) for i in range(M)])
    cyx = np.array([enc(b[i]+a[i]) for i in range(M)])
    forms = {
        "ncd_xy": (cxy-np.minimum(cx,cy))/np.maximum(cx,cy),
        "ncd_yx": (cyx-np.minimum(cx,cy))/np.maximum(cx,cy),
        "1-ncd_xy": 1-(cxy-np.minimum(cx,cy))/np.maximum(cx,cy),
        "(cx-cy)/cx": (cx-cy)/cx, "(cx-cy)/cy": (cx-cy)/cy,
        "(cx-cy)/max": (cx-cy)/np.maximum(cx,cy),
        "(cxy-cx-cy)/max": (cxy-cx-cy)/np.maximum(cx,cy),
        "(cx+cy-cxy)/max": (cx+cy-cxy)/np.maximum(cx,cy),
        "(cx+cy-cxy)/cxy": (cx+cy-cxy)/cxy,
        "(cxy-max)/min": (cxy-np.maximum(cx,cy))/np.minimum(cx,cy),
        "1-cxy/(cx+cy)": 1-cxy/(cx+cy),
    }
    for fn, v in forms.items():
        best.append((int((np.abs(v-tgt)<1e-8).sum()), float(np.abs(v-tgt).max()),
                     float(np.corrcoef(v,tgt)[0,1]), enc_name, fn))
best.sort(key=lambda t: (-t[0], t[1]))
for ex, md, cr, en, fn in best[:10]:
    print(f"  exact={ex:3d}/{M} max|diff|={md:.4f} corr={cr:+.4f}  {en} :: {fn}")

print("\n  BWT value structure: is each value k/L for small integer k?")
bw = S["BWTRLENCD Distance"].values
for i in range(6):
    v = bw[i]
    if v == 0: print(f"    row {i}: 0"); continue
    print(f"    row {i}: {v:.9f}  1/v={1/v:.4f}  la={la[i]} lb={lb[i]}")

print("\n===== 3. Monge-Elkan variant search =====")
def tok(s, mode):
    if mode=="alnum": return re.findall(r"[A-Za-z0-9]+", s)
    if mode=="ws": return s.split()
    if mode=="comma": return [t.strip() for t in s.split(",") if t.strip()]
rep = S["Monge Elkan Distance"].values
rows = []
for tm in ["alnum","ws","comma"]:
    for inner_name, inner in [("jw", JaroWinkler.similarity),
                              ("lev", lambda p,q: 1-lv.distance(p,q)/max(len(p),len(q),1)),
                              ("jaro", lambda p,q: lv.jaro(p,q))]:
        vals = []
        for x, y in zip(a, b):
            P, Q = tok(x,tm), tok(y,tm)
            if not P or not Q: vals.append(0.0); continue
            vals.append(np.mean([max(inner(p,q) for q in Q) for p in P]))
        vals = np.array(vals)
        for dn, div in [("1",1),("la",la),("lb",lb),("la*lb",la*lb),("la+lb",la+lb),
                        ("nP*nQ", np.array([len(tok(x,tm)) for x in a])*np.array([max(len(tok(y,tm)),1) for y in b]))]:
            v = vals/div
            rows.append((int((np.abs(v-rep)<1e-9).sum()), float(np.abs(v-rep).max()),
                         float(np.corrcoef(v,rep)[0,1]), tm, inner_name, dn))
rows.sort(key=lambda t: (-t[0], t[1]))
for ex, md, cr, tm, inn, dn in rows[:8]:
    print(f"  exact={ex}/{N} max|diff|={md:.6f} corr={cr:+.4f}  tok={tm} inner={inn} /{dn}")

print("\n===== 4. Do the similarity columns carry usable signal? =====")
pair = df["Latitude"] + "," + df["Longitude"]
vc = pair.value_counts()
lab_centroid = (pair.map(vc) >= 5).astype(int)          # 1 = suspect (geocoder fell back)
dist_in_py = df.apply(lambda r: str(r["District"]).lower().split("(")[0].strip() in str(r["address_py"]).lower(), axis=1).astype(int)
state_in_py = df.apply(lambda r: str(r["State"]).lower().replace("nct of ","") in str(r["address_py"]).lower(), axis=1).astype(int)
name_tok_hit = df.apply(lambda r: len(set(re.findall(r"[a-z]{4,}", str(r["Hospital_Name"]).lower())) &
                                       set(re.findall(r"[a-z]{4,}", str(r["address_py"]).lower()))) > 0, axis=1).astype(int)
print("  labels: centroid-fallback n=%d | district-in-address_py n=%d | state-in-address_py n=%d | name-token-hit n=%d"
      % (lab_centroid.sum(), dist_in_py.sum(), state_in_py.sum(), name_tok_hit.sum()))
print("  AUC of each metric against each label (0.5 = no signal):")
print("  %-26s %8s %8s %8s %8s" % ("metric","centroid","district","state","name_hit"))
for c in S.columns:
    print("  %-26s %8.3f %8.3f %8.3f %8.3f" % (c,
        roc_auc_score(lab_centroid, S[c]), roc_auc_score(dist_in_py, S[c]),
        roc_auc_score(state_in_py, S[c]), roc_auc_score(name_tok_hit, S[c])))
print("\n  confound: correlation of each metric with raw string lengths")
for c in S.columns:
    print(f"  {c:26s} corr(len Address)={np.corrcoef(S[c],la)[0,1]:+.3f} corr(len address_py)={np.corrcoef(S[c],lb)[0,1]:+.3f}")

print("\n===== 5. Specialty code families =====")
sp = df["Specialities_Selected"]
def fam(t):
    if t == "NA": return "NA"
    if re.fullmatch(r"[MS]\d+", t): return "numeric(M#/S#)"
    if re.fullmatch(r"[A-Z]{2}", t): return "alpha(2-letter)"
    return "other"
rowfams = []
for v in sp.dropna():
    ts = [x.strip() for x in v.split(",") if x.strip()]
    rowfams.append(frozenset(fam(t) for t in ts))
print("  family combination per row:", Counter(map(lambda s: "+".join(sorted(s)), rowfams)))
# which family per state / hospital type
tmpf = pd.Series([("+".join(sorted(f))) for f in rowfams], index=sp.dropna().index)
print("\n  family x Empanelment_Type:")
print(pd.crosstab(tmpf, df.loc[tmpf.index, "Empanelment_Type"]).to_string())
print("\n  family x Hospital_Type:")
print(pd.crosstab(tmpf, df.loc[tmpf.index, "Hospital_Type"].fillna("<null>")).to_string())
print("\n  rows whose only token is 'NA':", int(sum(1 for v in sp.dropna() if set(x.strip() for x in v.split(',') if x.strip())=={'NA'})))
print("  effective specialty-null rows (null OR only 'NA'):",
      int(sp.isna().sum() + sum(1 for v in sp.dropna() if set(x.strip() for x in v.split(',') if x.strip())=={'NA'})))

print("\n===== 6. ER readiness =====")
lat = pd.to_numeric(df["Latitude"]); lon = pd.to_numeric(df["Longitude"])
inbox = lat.between(6,38) & lon.between(68,98)
good_geo = inbox & (pair.map(vc) < 5)
has_name = df["Hospital_Name"].notna() & (df["Hospital_Name"].str.strip() != "")
has_dist = df["District"].notna() & (df["District"] != "-NA-")
print(f"  has_name: {int(has_name.sum())} ({100*has_name.mean():.2f}%)")
print(f"  has_district (excl '-NA-'): {int(has_dist.sum())} ({100*has_dist.mean():.2f}%)")
print(f"  has_state: {int(df['State'].notna().sum())} (100%)")
print(f"  geo in India bbox: {int(inbox.sum())} ({100*inbox.mean():.2f}%)")
print(f"  geo in bbox AND not a shared-centroid coord (>=5 rows): {int(good_geo.sum())} ({100*good_geo.mean():.2f}%)")
print(f"  has pincode: {int(df['Postcode_py'].notna().sum())} ({100*df['Postcode_py'].notna().mean():.2f}%)")
unmatchable = ~(has_name & has_dist & inbox)
print(f"  rows lacking (name AND district AND in-bbox geo): {int(unmatchable.sum())} ({100*unmatchable.mean():.2f}%)")
unmatchable2 = ~(has_name & (has_dist | inbox))
print(f"  rows lacking name AND (district OR geo): {int(unmatchable2.sum())} ({100*unmatchable2.mean():.2f}%)")

print("\n===== 7. District vs State consistency & casing =====")
d = df["District"]
print("  districts not fully UPPERCASE:", sorted(set(d[d != d.str.upper()])))
print("  district-state pairs where district appears under >1 state:")
g = df.groupby("District")["State"].nunique()
for k in g[g > 1].index:
    print("   ", k, df[df["District"]==k]["State"].value_counts().to_dict())
print("\n  states not fully uppercase:", sorted(set(df['State'][df['State'] != df['State'].str.upper()])))
print("  '-NA-' district rows by state:", df[df['District']=='-NA-']['State'].value_counts().to_dict())
