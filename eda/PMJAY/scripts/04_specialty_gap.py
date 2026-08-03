"""Pin down exactly why the binary flags disagree with the text columns,
and check suspicious code co-occurrence (S10/S11, S8/S9)."""
import re
from collections import Counter

import pandas as pd

SRC = "/Users/ankitraj2/asar master data/18_MAY_23_SRK_PMJAY_validated_and_standardized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
n = len(df)
CODE_RE = re.compile(r"^[MS]\d{1,2}$")
tok = lambda v: frozenset(t.strip() for t in str(v).split(",") if CODE_RE.match(t.strip())) if pd.notna(v) else frozenset()

EMP = [c for c in df.columns if c.endswith("_emp")]
UPG = [c for c in df.columns if c.endswith("_upg")]
flagcodes = {c[:-4] for c in EMP}

# full vocabulary across BOTH text columns
allvocab = Counter()
for c in ["Specialities Empanelled", "Specialities Upgraded"]:
    for v in df[c]:
        allvocab.update(tok(v))
print("text vocabulary:", sorted(allvocab, key=lambda x: (x[0], int(x[1:]))))
print("flag column codes:", sorted(flagcodes, key=lambda x: (x[0], int(x[1:]))))
print("IN TEXT BUT NO FLAG COLUMN:", sorted(set(allvocab) - flagcodes))
print("FLAG COLUMN BUT NEVER IN TEXT:", sorted(flagcodes - set(allvocab)))

for textcol, cols, suf in [("Specialities Empanelled", EMP, "_emp"),
                           ("Specialities Upgraded", UPG, "_upg")]:
    F = df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    from_flags = F.apply(lambda r: frozenset(c[:-len(suf)] for c in cols if r[c] == 1), axis=1)
    from_text = df[textcol].apply(tok)
    diff = [from_text[i] - from_flags[i] for i in df.index]
    lost = Counter()
    for d in diff:
        lost.update(d)
    print(f"\n{suf}: codes present in text but flag=0 -> {dict(lost)}")
    # after removing S8/S9 from text, does it reconcile?
    drop = set(allvocab) - flagcodes
    recon = [(from_text[i] - drop) == from_flags[i] for i in df.index]
    print(f"  after dropping {sorted(drop)} from text, exact match: "
          f"{sum(recon)}/{n} = {100*sum(recon)/n:.3f}%")
    bad = [i for i, ok in zip(df.index, recon) if not ok]
    print("  residual mismatches:", len(bad), bad[:5])
    for i in bad[:5]:
        print(f"    row {i}: text={sorted(from_text[i])} flags={sorted(from_flags[i])}")

# how many rows lose information because S8/S9 have no flag column?
for textcol, suf in [("Specialities Empanelled", "_emp"), ("Specialities Upgraded", "_upg")]:
    t = df[textcol].apply(tok)
    aff = t.apply(lambda s: bool(s & {"S8", "S9"}))
    print(f"\nrows whose {textcol} mentions S8 or S9: {aff.sum()} ({100*aff.mean():.2f}%)")

# co-occurrence checks
print("\n=== suspicious co-occurrence ===")
for a, b in [("S10", "S11"), ("S8", "S9")]:
    for textcol in ["Specialities Empanelled", "Specialities Upgraded"]:
        t = df[textcol].apply(tok)
        ha, hb = t.apply(lambda s: a in s), t.apply(lambda s: b in s)
        print(f"{textcol}: {a}={ha.sum()} {b}={hb.sum()} both={(ha&hb).sum()} "
              f"{a}only={(ha&~hb).sum()} {b}only={(hb&~ha).sum()}")

# '-NA-' semantics
print("\n=== '-NA-' sentinel ===")
for c in ["Specialities Empanelled", "Specialities Upgraded"]:
    isna_tok = df[c].fillna("").str.contains("-NA-", regex=False)
    only = df[c].fillna("").str.strip() == "-NA-"
    print(f"{c}: contains '-NA-'={isna_tok.sum()}, value is exactly '-NA-'={only.sum()}, "
          f"true null={df[c].isna().sum()}")
    mixed = df.index[isna_tok & ~only]
    print(f"   '-NA-' mixed with real codes: {len(mixed)} e.g. "
          f"{[df.at[i,c] for i in list(mixed)[:3]]}")

# does '-NA-' in empanelled coincide with all-zero flags?
E = df[EMP].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
na_e = df["Specialities Empanelled"].fillna("").str.strip() == "-NA-"
print(f"\nrows with Empanelled=='-NA-': {na_e.sum()}, of which all _emp flags 0: "
      f"{(na_e & (E.sum(axis=1) == 0)).sum()}")
print(f"rows with all _emp flags 0: {(E.sum(axis=1)==0).sum()}")
for i in list(df.index[E.sum(axis=1) == 0])[:8]:
    print(f"   row {i}: E-text={df.at[i,'Specialities Empanelled']!r}")

# combined column reconstruction rule
e = df["Specialities Empanelled"].fillna("")
u = df["Specialities Upgraded"].fillna("")
comb = df["Specialities_Upgraded_or_Empanelled"]
print("\n=== combined col: exact rule ===")
print("comb == E+U where both non-null:", int((comb.fillna("") == (e + u)).sum()), "/", n)
print("comb null exactly when E=='-NA-':",
      int((comb.isna() == (df['Specialities Empanelled'].fillna('').str.strip() == '-NA-')).sum()), "/", n)
print("count E=='-NA-':", int((e.str.strip() == '-NA-').sum()), " count comb null:", int(comb.isna().sum()))
# tokens recoverable from comb?
badtok = Counter()
for v in comb.dropna():
    for t in str(v).split(","):
        t = t.strip()
        if not CODE_RE.match(t):
            badtok[t] += 1
print("non-code tokens in combined col (top 15):", badtok.most_common(15))
