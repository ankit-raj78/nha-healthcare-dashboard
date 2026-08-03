"""Deep-dive on the specialty code family.

Questions:
 1. What is the complete distinct token vocabulary in the text columns?
 2. Do the M*_emp / S*_emp binary columns reconstruct exactly from `Specialities Empanelled`?
 3. Same for _upg vs `Specialities Upgraded`.
 4. Is `Specialities_Upgraded_or_Empanelled` a raw concatenation of the two text cols?
 5. Do the text columns DECODE the codes (i.e. contain human-readable specialty names)?
 6. How often does a facility have _emp but not _upg, and vice versa?
"""
import re
from collections import Counter

import pandas as pd

SRC = "/Users/ankitraj2/asar master data/18_MAY_23_SRK_PMJAY_validated_and_standardized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
n = len(df)

EMP_COLS = [c for c in df.columns if c.endswith("_emp")]
UPG_COLS = [c for c in df.columns if c.endswith("_upg")]
print("n _emp cols:", len(EMP_COLS), EMP_COLS)
print("n _upg cols:", len(UPG_COLS), UPG_COLS)

# which M/S indices exist / are missing
def idxset(cols, suf):
    return sorted({c[:-len(suf)] for c in cols})
print("emp code names:", idxset(EMP_COLS, "_emp"))
print("upg code names:", idxset(UPG_COLS, "_upg"))
print("emp set == upg set:", set(idxset(EMP_COLS, "_emp")) == set(idxset(UPG_COLS, "_upg")))

print("\n=== binary column value domains ===")
doms = Counter()
for c in EMP_COLS + UPG_COLS:
    doms[tuple(sorted(df[c].dropna().unique().tolist()))] += 1
print(doms)

# --- 1/5. text column token vocabulary ----------------------------------
print("\n=== text column raw distinct values (top) ===")
for c in ["Specialities Empanelled", "Specialities Upgraded", "Specialities_Upgraded_or_Empanelled"]:
    vc = df[c].value_counts()
    print(f"\n-- {c}: non-null={df[c].notna().sum()} distinct={df[c].nunique()}")
    print(vc.head(10).to_string())

def tokens(val):
    if pd.isna(val):
        return []
    return [t.strip() for t in str(val).split(",") if t.strip()]

for c in ["Specialities Empanelled", "Specialities Upgraded"]:
    tk = Counter()
    for v in df[c]:
        tk.update(tokens(v))
    print(f"\n=== token vocabulary of {c} ({len(tk)} distinct tokens) ===")
    for t, k in sorted(tk.items(), key=lambda x: -x[1]):
        print(f"   {t!r:16} {k}")

# do any tokens look like words rather than codes?
CODE_RE = re.compile(r"^[MS]\d{1,2}$")
for c in ["Specialities Empanelled", "Specialities Upgraded"]:
    bad = Counter()
    for v in df[c]:
        for t in tokens(v):
            if not CODE_RE.match(t):
                bad[t] += 1
    print(f"\nnon-code tokens in {c}: {dict(bad)}")

# --- 2/3. reconstruction check ------------------------------------------
print("\n=== reconstruction: text col vs binary flags ===")
for textcol, cols, suf in [("Specialities Empanelled", EMP_COLS, "_emp"),
                           ("Specialities Upgraded", UPG_COLS, "_upg")]:
    flags = df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    from_flags = flags.apply(lambda r: frozenset(c[:-len(suf)] for c in cols if r[c] == 1), axis=1)
    from_text = df[textcol].apply(lambda v: frozenset(t for t in tokens(v) if CODE_RE.match(t)))
    match = from_flags == from_text
    print(f"\n{textcol} vs {suf} flags: exact set match {match.sum()}/{n} = {100*match.mean():.3f}%")
    mism = df.index[~match]
    print("  mismatches:", len(mism))
    for i in list(mism)[:8]:
        print(f"   row {i}: text={df.at[i, textcol]!r} -> {sorted(from_text[i])} | flags={sorted(from_flags[i])}")
    # is text a superset/subset of flags?
    sup = sum(1 for i in mism if from_text[i] > from_flags[i])
    sub = sum(1 for i in mism if from_text[i] < from_flags[i])
    print(f"  of mismatches: text superset of flags={sup}, text subset of flags={sub}")

# --- 4. is the combined column a raw concat? ----------------------------
print("\n=== Specialities_Upgraded_or_Empanelled provenance ===")
e = df["Specialities Empanelled"].fillna("")
u = df["Specialities Upgraded"].fillna("")
comb = df["Specialities_Upgraded_or_Empanelled"]
concat_eu = (e + u)
concat_ue = (u + e)
print("equals E+U (naive concat):", int((comb.fillna("") == concat_eu).sum()), "/", n)
print("equals U+E:", int((comb.fillna("") == concat_ue).sum()), "/", n)
concat_comma = (e + ", " + u).str.strip(", ")
print("equals E+', '+U:", int((comb.fillna("") == concat_comma).sum()), "/", n)
print("comb null count:", int(comb.isna().sum()))
print("\nrows where comb is null: E/U values")
for i in list(df.index[comb.isna()])[:5]:
    print(f"   row {i}: E={df.at[i,'Specialities Empanelled']!r} U={df.at[i,'Specialities Upgraded']!r}")
print("\nsample comb vs parts:")
for i in range(6):
    print(f"   row {i}: E={e[i]!r} U={u[i]!r} -> comb={comb[i]!r}")

# --- 6. emp vs upg co-occurrence ----------------------------------------
print("\n=== empanelled vs upgraded coverage ===")
E = df[EMP_COLS].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
U = df[UPG_COLS].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
has_e = E.sum(axis=1) > 0
has_u = U.sum(axis=1) > 0
print(f"has any _emp=1: {has_e.sum()} ({100*has_e.mean():.2f}%)")
print(f"has any _upg=1: {has_u.sum()} ({100*has_u.mean():.2f}%)")
print(f"both: {(has_e & has_u).sum()}   emp-only: {(has_e & ~has_u).sum()}   "
      f"upg-only: {(~has_e & has_u).sum()}   neither: {(~has_e & ~has_u).sum()}")
print(f"\n_emp count per row: mean={E.sum(axis=1).mean():.2f} max={E.sum(axis=1).max()} "
      f"min={E.sum(axis=1).min()}")
print(f"_upg count per row: mean={U.sum(axis=1).mean():.2f} max={U.sum(axis=1).max()} "
      f"min={U.sum(axis=1).min()}")

# is upg always a subset of emp?
codes = idxset(EMP_COLS, "_emp")
Ev = E.rename(columns=lambda c: c[:-4])[codes].values
Uv = U.rename(columns=lambda c: c[:-4])[codes].values
subset = ((Uv <= Ev).all(axis=1))
print(f"\n_upg ⊆ _emp per row: {subset.sum()}/{n} = {100*subset.mean():.2f}%")
viol = (~subset).nonzero()[0]
print("rows violating subset:", len(viol), "first:", viol[:5].tolist())
for i in viol[:5]:
    print(f"   row {i}: emp={sorted(c for c in codes if Ev[i][codes.index(c)]==1)} "
          f"upg={sorted(c for c in codes if Uv[i][codes.index(c)]==1)}")

# per-code prevalence
print("\n=== per-code prevalence (emp / upg) ===")
print(f"{'code':6} {'emp=1':>7} {'emp%':>7} {'upg=1':>7} {'upg%':>7}")
for c in codes:
    ec = int(E[c + "_emp"].sum()); uc = int(U[c + "_upg"].sum())
    print(f"{c:6} {ec:>7} {100*ec/n:>6.2f}% {uc:>7} {100*uc/n:>6.2f}%")
