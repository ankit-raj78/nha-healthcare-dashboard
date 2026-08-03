"""Step 2: structure of the two mystery leading columns, trailing empty block, per-column fill."""
import pandas as pd, numpy as np, json

SRC = "/Users/ankitraj2/asar master data/22_MAY_22_AP_NIN.csv"
READ = dict(encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = pd.read_csv(SRC, **READ)
df.columns = [c for c in df.columns]
IDX = df.columns[0]   # 'Unnamed: 0'  (was BOM-only empty name)
NFN = "Non filled numbering"

print("=== col0 (BOM-only header, pandas names it 'Unnamed: 0') ===")
s = pd.to_numeric(df[IDX], errors="coerce")
print("non-null:", s.notna().sum(), "of", len(df))
print("all integer-valued:", bool((s.dropna() % 1 == 0).all()))
print("min/max:", s.min(), s.max())
print("is strictly increasing:", bool(s.is_monotonic_increasing and s.is_unique))
print("n distinct:", s.nunique())
print("starts at 0:", s.iloc[0])
expected = set(range(int(s.min()), int(s.max()) + 1))
missing = sorted(expected - set(s.dropna().astype(int)))
print("gap count vs contiguous 0..max:", len(missing))
print("first 30 missing indices:", missing[:30])

print("\n=== 'Non filled numbering' ===")
n = pd.to_numeric(df[NFN], errors="coerce")
print("non-null:", df[NFN].notna().sum(), f"({df[NFN].notna().mean()*100:.2f}%)")
print("numeric-parseable non-null:", n.notna().sum())
print("min/max:", n.min(), n.max())
print("n distinct:", df[NFN].nunique())
print("is unique among non-null:", bool(df[NFN].dropna().is_unique))
print("monotonic among non-null:", bool(n.dropna().is_monotonic_increasing))
sub = df.loc[df[NFN].notna(), [IDX, NFN, "SrNo", "Health Facility Name", "Manually_added", "Coder"]]
print(sub.head(15).to_string())
print("...")
print(sub.tail(5).to_string())
# is 'Non filled numbering' a re-numbering of rows that had something missing?
print("\nrows w/ NFN filled: how many have blank Health Facility Name:",
      df.loc[df[NFN].notna(), "Health Facility Name"].isna().sum())
print("rows w/ NFN filled: Manually_added value counts:",
      df.loc[df[NFN].notna(), "Manually_added"].value_counts(dropna=False).to_dict())

print("\n=== SrNo ===")
sr = pd.to_numeric(df["SrNo"], errors="coerce")
print("non-null:", df["SrNo"].notna().sum(), f"({df['SrNo'].notna().mean()*100:.2f}%)")
print("numeric parse fails:", int(df["SrNo"].notna().sum() - sr.notna().sum()))
print("min/max:", sr.min(), sr.max())
print("n distinct:", df["SrNo"].nunique(), "unique among non-null:", bool(df["SrNo"].dropna().is_unique))
dupsr = df["SrNo"].dropna().value_counts()
print("dup SrNo values (top):", dupsr[dupsr > 1].head(10).to_dict())

print("\n=== fully-empty rows (all cols except col0) ===")
data_cols = [c for c in df.columns if c != IDX]
allblank = df[data_cols].isna().all(axis=1)
print("count fully-blank data rows:", int(allblank.sum()))
print("positions min/max:", int(allblank[allblank].index.min()), int(allblank[allblank].index.max()))
# contiguous trailing?
last_nonblank = (~allblank)[::-1].idxmax()
print("last non-blank positional index:", last_nonblank)
print("blank rows after last non-blank:", int(allblank.loc[last_nonblank+1:].sum()),
      "of", len(df) - last_nonblank - 1)
print("blank rows BEFORE last non-blank:", int(allblank.loc[:last_nonblank].sum()))
print("col0 range of trailing blanks:", df.loc[allblank, IDX].astype(int).min(), "-", df.loc[allblank, IDX].astype(int).max())

print("\n=== Unnamed: 23 ===")
u = df["Unnamed: 23"]
print("non-null:", u.notna().sum())
print(u.value_counts(dropna=False).head(10).to_dict())
print("rows where non-null:", df.index[u.notna()].tolist()[:20])

print("\n=== per-column fill (full frame vs. non-blank rows only) ===")
eff = df.loc[~allblank]
rows = []
for c in df.columns:
    rows.append((c, int(df[c].notna().sum()), round(df[c].notna().mean()*100, 2),
                 int(eff[c].notna().sum()), round(eff[c].notna().mean()*100, 2), int(df[c].nunique())))
print(pd.DataFrame(rows, columns=["col", "nn_all", "pct_all", "nn_eff", "pct_eff", "distinct"]).to_string())
print("\neffective rows (non fully-blank):", len(eff))
