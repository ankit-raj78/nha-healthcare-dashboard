"""CGHS EDA - step 1: establish the true shape / correct read."""
import pandas as pd, csv, io, sys

SRC = "/Users/ankitraj2/asar master data/18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv"

raw = open(SRC, "rb").read()
print("file bytes:", len(raw))
print("BOM:", raw[:3])
print("CRLF count:", raw.count(b"\r\n"), "LF count:", raw.count(b"\n"))

# naive read
naive = pd.read_csv(SRC)
print("\nNAIVE pd.read_csv ->", naive.shape)
print("naive columns:", list(naive.columns)[:3])

# BOM-aware read
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
print("\nutf-8-sig dtype=str ->", df.shape)
print("columns:", list(df.columns))

# raw csv reader row count (handles embedded newlines)
with open(SRC, newline="", encoding="utf-8-sig") as f:
    rows = list(csv.reader(f))
print("\ncsv.reader total records (incl header):", len(rows))
widths = {}
for r in rows:
    widths[len(r)] = widths.get(len(r), 0) + 1
print("record width histogram:", widths)

# any embedded newlines inside fields?
emb = 0
for i, r in enumerate(rows[1:]):
    for c in r:
        if "\n" in c or "\r" in c:
            emb += 1
print("fields containing embedded newline:", emb)

# trailing all-empty columns?
for c in df.columns:
    if df[c].isna().all():
        print("ALL-NULL COLUMN:", repr(c))

print("\ndtypes from naive read:")
print(naive.dtypes.to_string())
