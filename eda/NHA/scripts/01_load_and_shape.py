"""NHA EDA step 1: establish the true shape of the file.

Reports raw byte-level facts (BOM, trailing newline), csv-module row/field counts,
and the pandas read that reproduces them. Writes nothing but stdout.
"""
import csv
import io
import json
from collections import Counter

import pandas as pd

SRC = "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv"

out = {}

# --- byte-level facts -------------------------------------------------------
with open(SRC, "rb") as fh:
    head = fh.read(8)
    fh.seek(-2, io.SEEK_END)
    tail = fh.read()
out["starts_with_utf8_bom"] = head.startswith(b"\xef\xbb\xbf")
out["first_8_bytes"] = repr(head)
out["last_2_bytes"] = repr(tail)
out["ends_with_newline"] = tail.endswith(b"\n")

# --- csv-module ground truth ------------------------------------------------
with open(SRC, newline="", encoding="utf-8") as fh:
    rdr = csv.reader(fh)
    header = next(rdr)
    widths = Counter()
    n = 0
    for row in rdr:
        n += 1
        widths[len(row)] += 1
out["n_header_cols"] = len(header)
out["header"] = header
out["csv_data_rows"] = n
out["field_width_distribution"] = dict(widths)

# newline count (== wc -l)
with open(SRC, "rb") as fh:
    nl = 0
    while True:
        b = fh.read(1 << 22)
        if not b:
            break
        nl += b.count(b"\n")
out["wc_l"] = nl

# --- pandas, naive ----------------------------------------------------------
naive = pd.read_csv(SRC, low_memory=False)
out["pandas_naive_shape"] = list(naive.shape)
out["pandas_naive_dtypes"] = {c: str(t) for c, t in naive.dtypes.items()}
out["unnamed_cols"] = [c for c in naive.columns if str(c).startswith("Unnamed")]
out["all_null_cols"] = [c for c in naive.columns if naive[c].isna().all()]
out["constant_cols"] = [
    c for c in naive.columns if naive[c].nunique(dropna=True) <= 1
]

print(json.dumps(out, indent=2, default=str))
