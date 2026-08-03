"""CGHS EDA - step 2: per-column profile."""
import pandas as pd, numpy as np, json, re
from collections import Counter

pd.set_option("display.width", 250)
SRC = "/Users/ankitraj2/asar master data/18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
N = len(df)
print("shape", df.shape)

print("\n================ PER-COLUMN =================")
for c in df.columns:
    s = df[c]
    nn = s.notna().sum()
    nd = s.nunique(dropna=True)
    print(f"\n--- {c!r} | non_null={nn} ({100*nn/N:.2f}%) | distinct={nd}")
    ex = s.dropna().unique()[:5]
    print("   examples:", [str(x)[:90] for x in ex])
    if nd <= 50:
        vc = s.value_counts(dropna=False)
        print("   value_counts:")
        for k, v in vc.items():
            print(f"      {str(k)[:70]!r}: {v}")

print("\n================ SENTINELS =================")
SENT = ["-NA", "-NA-", "NA", "N/A", "NULL", "null", "None", "-", "nan", "0"]
for c in df.columns:
    hits = {t: int((df[c] == t).sum()) for t in SENT if (df[c] == t).sum() > 0}
    if hits:
        print(f"{c}: {hits}")
