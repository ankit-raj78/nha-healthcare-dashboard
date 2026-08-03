"""NHA EDA step 2: per-column profile over ALL 323,460 rows.

Reads everything as string (dtype=str) so nothing is silently coerced, then
profiles each column. Emits eda/NHA/_col_profile.json (intermediate).
"""
import json
import re

import numpy as np
import pandas as pd

SRC = "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv"
OUT = "eda/NHA/scripts/intermediate/_col_profile.json"

# read everything as text; keep_default_na=False so we see '' vs literal 'NA'/'nan'
df = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)
N = len(df)
print("shape", df.shape)

cols = []
for c in df.columns:
    s = df[c]
    blank = s.eq("")
    nonnull = int((~blank).sum())
    vals = s[~blank]
    nd = int(vals.nunique())
    rec = {
        "name": c,
        "raw_dtype_as_str": "object(read as str)",
        "non_null": nonnull,
        "null_pct": round(100.0 * (N - nonnull) / N, 4),
        "n_distinct": nd,
        "examples": vals.drop_duplicates().head(6).tolist(),
    }
    # literal sentinel strings that pandas would normally treat as NaN
    sent = vals[vals.str.strip().str.lower().isin(
        ["nan", "na", "n/a", "none", "null", "-", "--", "nil", "0.0", "unknown"])]
    if len(sent):
        rec["sentinel_like_values"] = dict(sent.value_counts().head(10))
    if nd < 50:
        rec["value_counts"] = {str(k): int(v) for k, v in vals.value_counts().items()}
    else:
        rec["top_10"] = {str(k): int(v) for k, v in vals.value_counts().head(10).items()}
        L = vals.str.len()
        rec["str_len"] = {
            "min": int(L.min()), "max": int(L.max()),
            "mean": round(float(L.mean()), 2),
            "p50": int(L.quantile(.5)), "p95": int(L.quantile(.95)),
        }
    # numeric view if it parses
    num = pd.to_numeric(vals, errors="coerce")
    ok = int(num.notna().sum())
    if nonnull and ok / nonnull > 0.5:
        rec["numeric"] = {
            "parses_pct": round(100.0 * ok / nonnull, 3),
            "n_unparseable": int(nonnull - ok),
            "unparseable_examples": vals[num.isna()].drop_duplicates().head(8).tolist(),
            "min": float(num.min()), "max": float(num.max()),
            "mean": round(float(num.mean()), 6),
            "p01": float(num.quantile(.01)), "p25": float(num.quantile(.25)),
            "p50": float(num.quantile(.50)), "p75": float(num.quantile(.75)),
            "p99": float(num.quantile(.99)),
            "n_zero": int((num == 0).sum()),
            "n_negative": int((num < 0).sum()),
        }
    # whitespace / case hygiene
    rec["n_needs_strip"] = int((vals != vals.str.strip()).sum())
    if nd < 5000:
        low = vals.str.strip().str.lower()
        rec["n_distinct_after_strip_lower"] = int(low.nunique())
    cols.append(rec)
    print(f"  {c:28s} nn={nonnull:7d} nd={nd:7d}")

json.dump({"n_rows": N, "n_cols": df.shape[1], "columns": cols},
          open(OUT, "w"), indent=2, default=str)
print("wrote", OUT)
