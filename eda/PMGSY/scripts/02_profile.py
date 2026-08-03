"""Step 2: full column profile."""
import pandas as pd, numpy as np, csv, json, re
from collections import Counter

SRC = "/Users/ankitraj2/asar master data/21_JULY_23_SRK_PMGSY_validated_homogenized.csv"
pd.set_option("display.width", 250)

with open(SRC, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f))
nl_chars = sum(c.count("\n") for r in rows for c in r)
print("total embedded \\n chars:", nl_chars)
with open(SRC, "rb") as f:
    raw = f.read()
print("file ends with newline:", raw.endswith(b"\n"))

df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = df.dropna(how="all").reset_index(drop=True)
print("SHAPE", df.shape)

for c in df.columns:
    s = df[c]
    nn = s.notna().sum()
    nd = s.nunique(dropna=True)
    print("=" * 90)
    print(f"COL {c!r} | non_null={nn} ({100*nn/len(df):.2f}%) | distinct={nd}")
    ex = s.dropna().unique()[:5]
    print("  examples:", [str(x)[:90] for x in ex])
    if nd < 60:
        vc = s.value_counts(dropna=False)
        print("  value_counts:")
        for k, v in vc.items():
            print(f"    {k!r}: {v}")
    else:
        print("  top10:", s.value_counts().head(10).to_dict())
        L = s.dropna().str.len()
        print(f"  len min/med/mean/max = {L.min()}/{L.median()}/{L.mean():.1f}/{L.max()}")
