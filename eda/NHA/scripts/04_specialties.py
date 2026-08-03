"""NHA EDA step 4: the M*/S*_emp coded specialty vocabulary and merged_specialties.

Goal: determine the encoding, whether merged_specialties decodes the codes, and
extract the codebook if one is inferable.
"""
import json
import re
from collections import Counter

import numpy as np
import pandas as pd

SRC = "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv"
df = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)
N = len(df)

SPEC = [c for c in df.columns if re.fullmatch(r"[MS]\d+_emp", c)]
# canonical order M1..M10, S1..S16
SPEC = sorted(SPEC, key=lambda c: (c[0], int(re.findall(r"\d+", c)[0])))
R = {"spec_columns": SPEC, "n_spec_columns": len(SPEC),
     "missing_from_M1_M10": [f"M{i}_emp" for i in range(1, 11)
                             if f"M{i}_emp" not in SPEC],
     "missing_from_S1_S16": [f"S{i}_emp" for i in range(1, 17)
                             if f"S{i}_emp" not in SPEC]}

R["per_column"] = {}
for c in SPEC:
    vc = df[c].value_counts()
    R["per_column"][c] = {
        "distinct_raw_values": sorted(df[c].unique().tolist()),
        "value_counts": {str(k): int(v) for k, v in vc.items()},
        "n_blank": int(df[c].eq("").sum()),
    }

# treat blank as 0 for the flag matrix
M = df[SPEC].replace("", "0").apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
R["global_distinct_values_across_all_spec_cols"] = sorted(
    set(np.unique(M.values).tolist()))
rowsum = M.sum(axis=1)
R["n_specialties_per_row"] = {
    "hist": {str(k): int(v) for k, v in rowsum.value_counts().sort_index().items()},
    "n_rows_with_zero_specialties": int((rowsum == 0).sum()),
    "n_rows_with_any_specialty": int((rowsum > 0).sum()),
    "pct_rows_with_any": round(100.0 * (rowsum > 0).sum() / N, 3),
    "max": int(rowsum.max()), "mean_when_any": round(float(rowsum[rowsum > 0].mean()), 3),
}
R["per_column_positive_count"] = {c: int(M[c].sum()) for c in SPEC}

# --- merged_specialties -----------------------------------------------------
ms = df["merged_specialties"]
has_ms = ~ms.eq("")
R["merged_specialties"] = {
    "n_non_blank": int(has_ms.sum()),
    "pct_non_blank": round(100.0 * has_ms.sum() / N, 3),
    "n_distinct": int(ms[has_ms].nunique()),
    "examples": ms[has_ms].drop_duplicates().head(15).tolist(),
    "overlap_with_flags": {
        "ms_and_flags": int((has_ms & (rowsum > 0)).sum()),
        "ms_only": int((has_ms & (rowsum == 0)).sum()),
        "flags_only": int((~has_ms & (rowsum > 0)).sum()),
        "neither": int((~has_ms & (rowsum == 0)).sum()),
    },
}
# split merged_specialties into atomic tokens
def toks(s):
    return [t.strip() for t in re.split(r"[|;,]", s) if t.strip()]
tok_counter = Counter()
ntok = []
for v in ms[has_ms]:
    t = toks(v)
    ntok.append(len(t))
    tok_counter.update(t)
R["merged_specialties"]["n_distinct_tokens"] = len(tok_counter)
R["merged_specialties"]["token_counts"] = {k: int(v) for k, v in tok_counter.most_common(80)}
R["merged_specialties"]["tokens_per_row_hist"] = {
    str(k): int(v) for k, v in pd.Series(ntok).value_counts().sort_index().items()}

# --- THE DECODE TEST --------------------------------------------------------
# For each spec column, what tokens appear in merged_specialties on rows where
# that flag == 1? If the flag decodes to exactly one token, we have the codebook.
decode = {}
for c in SPEC:
    sel = (M[c] == 1) & has_ms
    n = int(sel.sum())
    cnt = Counter()
    for v in ms[sel]:
        cnt.update(toks(v))
    decode[c] = {
        "n_rows_flag1_with_merged_specialties": n,
        "n_rows_flag1_total": int((M[c] == 1).sum()),
        "top_tokens": {k: int(v) for k, v in cnt.most_common(8)},
        "top_token_coverage_pct": round(100.0 * cnt.most_common(1)[0][1] / n, 2) if n and cnt else None,
    }
R["decode_attempt_flag_to_token"] = decode

# Inverse: for each token, which flag columns are ~always 1 when the token present?
inv = {}
tok_series = ms.map(lambda s: set(toks(s)) if s else set())
for tok, cnt in tok_counter.most_common(60):
    sel = tok_series.map(lambda S: tok in S)
    n = int(sel.sum())
    rates = {c: round(float(M.loc[sel, c].mean()), 4) for c in SPEC}
    best = sorted(rates.items(), key=lambda kv: -kv[1])[:4]
    inv[tok] = {"n_rows": n, "top_flag_rates": dict(best)}
R["decode_attempt_token_to_flag"] = inv

# co-occurrence: how many rows per exact flag-pattern
pat = M.astype(str).agg("".join, axis=1)
R["flag_pattern"] = {
    "n_distinct_patterns": int(pat.nunique()),
    "top_patterns": {k: int(v) for k, v in pat.value_counts().head(15).items()},
    "column_order_for_pattern": SPEC,
}
# pairwise correlation of flags (top pairs)
corr = M.corr()
pairs = []
for i, a in enumerate(SPEC):
    for b in SPEC[i + 1:]:
        v = corr.loc[a, b]
        if pd.notna(v):
            pairs.append((round(float(v), 3), a, b))
pairs.sort(reverse=True)
R["top_flag_correlations"] = [{"r": p[0], "a": p[1], "b": p[2]} for p in pairs[:15]]

json.dump(R, open("eda/NHA/scripts/intermediate/_specialties.json", "w"), indent=2, default=str)
print(json.dumps({k: R[k] for k in
                  ["spec_columns", "missing_from_M1_M10", "missing_from_S1_S16",
                   "global_distinct_values_across_all_spec_cols",
                   "n_specialties_per_row", "per_column_positive_count"]},
                 indent=2, default=str))
print("MERGED:", json.dumps(R["merged_specialties"]["overlap_with_flags"], indent=1))
print("n_distinct_tokens", R["merged_specialties"]["n_distinct_tokens"])
