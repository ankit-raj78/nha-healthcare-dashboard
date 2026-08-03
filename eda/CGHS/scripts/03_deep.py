"""CGHS EDA - step 3: districts, specialties, ids, dates, geo, dupes."""
import pandas as pd, numpy as np, re, json
from collections import Counter

SRC = "/Users/ankitraj2/asar master data/18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
N = len(df)

print("=========== Unnamed: 0 ===========")
u = pd.to_numeric(df["Unnamed: 0"])
print("min", u.min(), "max", u.max(), "is 0..N-1 exactly:", bool((u.values == np.arange(N)).all()))

print("\n=========== Hospital_Id ===========")
hid = df["Hospital_Id"]
print("unique:", hid.is_unique, "n_distinct:", hid.nunique())
print("length dist:", Counter(hid.str.len()))
pat = hid.str.extract(r"^(HOSP)(\d{2})([A-Z])(\d+)$")
print("regex ^HOSP\\d{2}[A-Z]\\d+$ match:", int(pat[0].notna().sum()), "/", N)
print("non-matching examples:", hid[pat[0].isna()].head(10).tolist())
print("2-digit segment (state code?) counts:", dict(sorted(Counter(pat[1].dropna()).items())))
print("letter segment counts:", dict(Counter(pat[2].dropna())))
# cross-tab letter vs Hospital_Type
ct = pd.crosstab(pat[2], df["Hospital_Type"], dropna=False)
print("\nletter x Hospital_Type:\n", ct)
# 2-digit vs State (LGD state code check)
cs = df.assign(code=pat[1]).groupby("code")["State"].agg(lambda x: x.value_counts().index[0] + " (" + str(len(x)) + ")")
print("\ncode -> dominant state:\n", cs.to_string())
# purity
grp = df.assign(code=pat[1]).groupby("code")["State"].nunique()
print("\ncodes mapping to >1 state:", dict(grp[grp > 1]))

print("\n=========== District ===========")
dd = df["District"].value_counts()
print("n_distinct:", df["District"].nunique())
print(dd.to_string())

print("\n=========== Specialities_Selected ===========")
sp = df["Specialities_Selected"]
print("null:", int(sp.isna().sum()), f"({100*sp.isna().mean():.2f}%)")
# delimiter detection
delims = {d: int(sp.dropna().str.contains(re.escape(d)).sum()) for d in [",", ";", "|", "/", "-"]}
print("delimiter presence counts:", delims)
toks_all = []
per_row_tokens = []
for v in sp.dropna():
    t = [x.strip() for x in v.split(",")]
    t = [x for x in t if x != ""]
    per_row_tokens.append(t)
    toks_all.extend(t)
vocab = Counter(toks_all)
print("total tokens:", len(toks_all), "distinct tokens:", len(vocab))
print("leading-comma rows:", int(sp.dropna().str.startswith(",").sum()))
print("trailing-comma rows:", int(sp.dropna().str.endswith(",").sum()))
print("rows with duplicate tokens within row:", sum(1 for t in per_row_tokens if len(t) != len(set(t))))
print("tokens per row: min %d max %d mean %.2f median %d" % (
    min(len(t) for t in per_row_tokens), max(len(t) for t in per_row_tokens),
    np.mean([len(t) for t in per_row_tokens]), np.median([len(t) for t in per_row_tokens])))
print("\nFULL VOCAB (token: n_rows_containing):")
rowcount = Counter()
for t in per_row_tokens:
    for x in set(t):
        rowcount[x] += 1
def sortkey(k):
    m = re.match(r"^([A-Za-z]+)(\d*)$", k)
    return (m.group(1), int(m.group(2)) if m.group(2) else -1) if m else ("ZZZ", 0)
for k in sorted(vocab, key=sortkey):
    print(f"   {k}: occ={vocab[k]} rows={rowcount[k]}")
# token shape families
fam = Counter(re.sub(r"\d+", "#", k) for k in vocab)
print("\ntoken shape families:", dict(fam))
print("distinct raw specialty strings:", sp.nunique())

print("\n=========== Dates ===========")
for c in ["Submitted_Date", "Status_Updated_Date"]:
    print(c, "distinct:", df[c].unique().tolist())

print("\n=========== Postcode_py ===========")
pc = df["Postcode_py"]
print("null:", int(pc.isna().sum()))
nn = pc.dropna()
print("all numeric-string:", bool(nn.str.match(r"^\d+$").all()))
print("length dist:", Counter(nn.str.len()))
bad = nn[~nn.str.match(r"^[1-9]\d{5}$")]
print("not 6-digit-starting-1-9:", len(bad), bad.head(20).tolist())
print("first-digit dist:", dict(sorted(Counter(nn.str[0]).items())))

print("\n=========== Hospital_Contact (PII) ===========")
hc = df["Hospital_Contact"].dropna()
print("length dist:", dict(sorted(Counter(hc.str.len()).items())))
print("pure 10-digit indian mobile (6-9 lead):", int(hc.str.match(r"^[6-9]\d{9}$").sum()))
print("non-10-digit examples:", hc[~hc.str.match(r"^\d{10}$")].head(20).tolist())
print("duplicate phone numbers (value shared by >1 row):",
      int(hc.duplicated(keep=False).sum()))
print("top repeated phones:", hc.value_counts().head(8).to_dict())
