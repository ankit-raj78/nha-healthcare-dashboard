"""Step 1: establish the correct read for 22_MAY_22_AP_NIN.csv."""
import csv, io, sys
import pandas as pd

SRC = "/Users/ankitraj2/asar master data/22_MAY_22_AP_NIN.csv"

# --- raw byte / line facts -------------------------------------------------
raw = open(SRC, "rb").read()
print("file bytes:", len(raw))
print("starts with UTF-8 BOM:", raw[:3] == b"\xef\xbb\xbf")
print("count b'\\r\\n':", raw.count(b"\r\n"))
print("count b'\\n':", raw.count(b"\n"))
print("count lone b'\\r' (not followed by \\n):", raw.count(b"\r") - raw.count(b"\r\n"))
print("ends with newline:", raw.endswith(b"\n"))

# wc -l counts \n bytes
print("wc -l equivalent:", raw.count(b"\n"))

# --- csv module logical row count (authoritative) --------------------------
with open(SRC, "r", encoding="utf-8-sig", newline="") as f:
    rdr = csv.reader(f)
    rows = list(rdr)
print("csv.reader total records (incl header):", len(rows))
print("header:", rows[0])
print("n header fields:", len(rows[0]))
from collections import Counter
widths = Counter(len(r) for r in rows[1:])
print("data row width distribution:", dict(widths))

# rows containing embedded newlines
emb = [(i, j, c) for i, r in enumerate(rows[1:], start=1) for j, c in enumerate(r) if "\n" in c or "\r" in c]
print("cells with embedded newline:", len(emb))
for i, j, c in emb[:10]:
    print("  record", i, "field", j, rows[0][j], repr(c[:120]))

# --- naive pandas read -----------------------------------------------------
naive = pd.read_csv(SRC)
print("\nnaive pd.read_csv shape:", naive.shape)
print("naive columns:", list(naive.columns))
print("naive dtypes:\n", naive.dtypes)

# --- chosen read -----------------------------------------------------------
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
print("\nchosen read shape:", df.shape)
print("chosen columns:", list(df.columns))
print("\nfirst col name repr:", repr(df.columns[0]))
print("last col name repr:", repr(df.columns[-1]))

print("\nhead:")
print(df.head(5).to_string())
print("\ntail:")
print(df.tail(5).to_string())
