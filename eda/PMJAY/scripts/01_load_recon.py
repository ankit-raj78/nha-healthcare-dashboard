"""Establish the true shape of the PMJAY CSV before any profiling.

Checks: BOM, embedded newlines, row count vs wc -l, junk/unnamed columns,
trailing empty columns, dtype warnings, thousands separators.
"""
import csv
import io
import sys

import pandas as pd

SRC = "/Users/ankitraj2/asar master data/18_MAY_23_SRK_PMJAY_validated_and_standardized.csv"

out = []


def p(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    out.append(s)


# --- 1. raw byte level ---------------------------------------------------
with open(SRC, "rb") as f:
    head = f.read(4)
p("first 4 bytes:", head)
p("has utf-8 BOM:", head.startswith(b"\xef\xbb\xbf"))

with open(SRC, "rb") as f:
    raw = f.read()
p("file size bytes:", len(raw))
p("count of b'\\n':", raw.count(b"\n"))
p("count of b'\\r\\n':", raw.count(b"\r\n"))
p("count of b'\\r':", raw.count(b"\r"))
p("ends with newline:", raw.endswith(b"\n"))

# --- 2. physical lines vs logical csv records ---------------------------
with open(SRC, "r", encoding="utf-8-sig", newline="") as f:
    physical = sum(1 for _ in f)
p("physical lines (python readlines, universal newline):", physical)

with open(SRC, "r", encoding="utf-8-sig", newline="") as f:
    rdr = csv.reader(f)
    header = next(rdr)
    records = list(rdr)
p("csv.reader header len:", len(header))
p("csv.reader data records:", len(records))

# field-count histogram of records
from collections import Counter
fc = Counter(len(r) for r in records)
p("record field-count histogram:", dict(fc))

# which records contain embedded newlines?
emb = [i for i, r in enumerate(records) if any("\n" in c or "\r" in c for c in r)]
p("records containing embedded newline:", len(emb), "first few:", emb[:10])
for i in emb[:5]:
    for j, c in enumerate(records[i]):
        if "\n" in c or "\r" in c:
            p(f"   rec {i} col[{j}]={header[j]!r} value={c!r}")

# --- 3. header hygiene ---------------------------------------------------
p("header[0] repr:", repr(header[0]))
p("duplicate header names:", [k for k, v in Counter(header).items() if v > 1])
p("headers with leading/trailing whitespace:", [h for h in header if h != h.strip()])
p("empty header names:", [i for i, h in enumerate(header) if h.strip() == ""])

# --- 4. naive pandas read -----------------------------------------------
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    df_naive = pd.read_csv(SRC)
    p("naive read_csv warnings:", [str(x.message)[:200] for x in w])
p("naive shape:", df_naive.shape)
p("naive first col name repr:", repr(df_naive.columns[0]))
p("naive Unnamed cols:", [c for c in df_naive.columns if str(c).startswith("Unnamed")])

# --- 5. the read we recommend -------------------------------------------
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
p("recommended read shape:", df.shape)
p("recommended first col repr:", repr(df.columns[0]))

# all-empty columns
allnull = [c for c in df.columns if df[c].isna().all()]
p("all-null columns:", allnull)
# constant columns
const = {c: df[c].dropna().unique()[:1].tolist() for c in df.columns if df[c].nunique(dropna=True) == 1}
p("constant (1 distinct) columns:", const)

# --- 6. thousands separators / numeric-looking strings -------------------
import re
comma_num = {}
for c in df.columns:
    s = df[c].dropna().astype(str)
    hits = s[s.str.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?")]
    if len(hits):
        comma_num[c] = (len(hits), hits.head(3).tolist())
p("columns with thousands-separator numerics:", comma_num)

with open("/Users/ankitraj2/asar master data/eda/PMJAY/scripts/01_load_recon.out.txt", "w") as f:
    f.write("\n".join(out))
