"""Per-column profile: dtype, nulls, distincts, examples, value_counts (<50 card),
numeric stats, text length distribution. Dumps JSON for later assembly."""
import json
import re

import numpy as np
import pandas as pd

SRC = "/Users/ankitraj2/asar master data/18_MAY_23_SRK_PMJAY_validated_and_standardized.csv"
OUT = "/Users/ankitraj2/asar master data/eda/PMJAY/scripts/02_columns.json"

df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
n = len(df)

# also a type-inferred read to learn what pandas would call each column
df_inf = pd.read_csv(SRC, encoding="utf-8-sig", low_memory=False)


def numeric_stats(s: pd.Series):
    v = pd.to_numeric(s, errors="coerce").dropna()
    if len(v) == 0:
        return None
    frac_numeric = len(v) / max(s.notna().sum(), 1)
    if frac_numeric < 0.9:
        return {"note": "not predominantly numeric", "frac_parseable": round(frac_numeric, 4)}
    q = v.quantile([0.01, 0.25, 0.5, 0.75, 0.99])
    return {
        "count": int(len(v)),
        "frac_parseable": round(frac_numeric, 4),
        "min": float(v.min()), "max": float(v.max()), "mean": float(v.mean()),
        "std": float(v.std()) if len(v) > 1 else 0.0,
        "p01": float(q.loc[0.01]), "p25": float(q.loc[0.25]), "p50": float(q.loc[0.5]),
        "p75": float(q.loc[0.75]), "p99": float(q.loc[0.99]),
        "n_zero": int((v == 0).sum()), "n_negative": int((v < 0).sum()),
    }


def text_stats(s: pd.Series):
    v = s.dropna().astype(str)
    if len(v) == 0:
        return None
    L = v.str.len()
    q = L.quantile([0.5, 0.9, 0.99])
    return {
        "len_min": int(L.min()), "len_max": int(L.max()), "len_mean": round(float(L.mean()), 2),
        "len_p50": int(q.loc[0.5]), "len_p90": int(q.loc[0.9]), "len_p99": int(q.loc[0.99]),
        "n_leading_trailing_ws": int((v != v.str.strip()).sum()),
        "n_internal_double_space": int(v.str.contains(r"  ").sum()),
        "n_nonascii": int(v.str.contains(r"[^\x00-\x7F]").sum()),
        "longest_example": v.loc[L.idxmax()][:300],
    }


cols = []
for c in df.columns:
    s = df[c]
    nn = int(s.notna().sum())
    nd = int(s.nunique(dropna=True))
    ex = s.dropna().unique()[:6].tolist()
    rec = {
        "name": c,
        "dtype_str_read": "object",
        "dtype_inferred": str(df_inf[c].dtype),
        "non_null": nn,
        "null_pct": round(100.0 * (n - nn) / n, 3),
        "n_distinct": nd,
        "examples": [str(x)[:200] for x in ex],
    }
    if nd < 50 and nd > 0:
        vc = s.value_counts(dropna=True)
        rec["value_counts"] = {str(k): int(v) for k, v in vc.items()}
    ns = numeric_stats(s)
    if ns:
        rec["numeric_stats"] = ns
    ts = text_stats(s)
    if ts:
        rec["text_stats"] = ts
    cols.append(rec)

with open(OUT, "w") as f:
    json.dump({"n_rows": n, "n_cols": len(df.columns), "columns": cols}, f, indent=2, default=str)

# human-readable summary table
print(f"{'#':>3} {'column':38} {'nn':>6} {'null%':>7} {'ndist':>7}  dtype_inf   examples")
for i, r in enumerate(cols):
    ex = " | ".join(r["examples"][:2])[:60]
    print(f"{i:>3} {r['name'][:38]:38} {r['non_null']:>6} {r['null_pct']:>7.2f} "
          f"{r['n_distinct']:>7}  {r['dtype_inferred']:<10} {ex}")
