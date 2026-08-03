"""NHP EDA step 2: per-column profile."""
import json, re, sys
import pandas as pd
import numpy as np

pd.set_option("display.width", 200)
SRC = "/Users/ankitraj2/asar master data/8_JULY_23_SRK_NHP_validated_and_standardized.csv"
READ_KW = dict(encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = pd.read_csv(SRC, **READ_KW)
print("shape:", df.shape)
print("columns:", list(df.columns))

print("\n=== emptiness of Unnamed cols ===")
for c in df.columns:
    if c.startswith("Unnamed"):
        nn = df[c].notna().sum()
        print(f"  {c}: non_null={nn}, unique_raw={df[c].astype(str).unique()[:5]}")

print("\n=== per column summary ===")
for c in df.columns:
    s = df[c]
    nn = int(s.notna().sum())
    nd = int(s.nunique(dropna=True))
    ex = [x for x in s.dropna().unique()[:3]]
    print(f"{c!r}: non_null={nn} ({100*nn/len(df):.2f}%) distinct={nd}")
    print(f"    ex: {ex}")

print("\n=== low-cardinality full value counts ===")
for c in df.columns:
    nd = df[c].nunique(dropna=True)
    if 0 < nd < 50:
        print(f"\n--- {c!r} (distinct={nd}) ---")
        vc = df[c].value_counts(dropna=False)
        for k, v in vc.items():
            print(f"    {k!r}: {v}")
