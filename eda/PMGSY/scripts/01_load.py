"""Step 1: establish true shape of the PMGSY CSV."""
import pandas as pd, csv, sys, json

SRC = "/Users/ankitraj2/asar master data/21_JULY_23_SRK_PMGSY_validated_homogenized.csv"

# raw physical line count
with open(SRC, "rb") as f:
    phys = sum(1 for _ in f)
print("physical lines:", phys)

# csv-module logical record count
with open(SRC, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f))
print("csv logical records (incl header):", len(rows))
hdr = rows[0]
print("header:", hdr)
print("n header cols:", len(hdr))
from collections import Counter
print("field-count distribution:", Counter(len(r) for r in rows))

# fully empty records
empty = [i for i, r in enumerate(rows) if all((c or "").strip() == "" for c in r)]
print("fully-empty records:", len(empty), "first:", empty[:3], "last:", empty[-3:] if empty else None)
# are they contiguous at the end?
if empty:
    print("empty are contiguous tail:", empty == list(range(empty[0], len(rows))))

df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
print("naive pandas shape:", df.shape)
print("all-null rows:", df.isna().all(axis=1).sum())
dfc = df.dropna(how="all")
print("after dropping all-null rows:", dfc.shape)
print("columns:", list(df.columns))
print("Unnamed cols:", [c for c in df.columns if c.startswith("Unnamed")])
# embedded newlines?
print("records with embedded newline in any field:",
      sum(1 for r in rows if any("\n" in (c or "") for c in r)))
