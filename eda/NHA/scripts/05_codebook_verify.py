"""NHA EDA step 5: prove the flag->specialty-name bijection exactly.

For each M*/S*_emp column, test the set-equality:
    {rows where flag==1}  ==  {rows where token T appears in merged_specialties}
If that holds exactly for every column, the codebook is proven, not inferred.
"""
import json
import re

import pandas as pd

SRC = "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv"
df = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)

SPEC = sorted([c for c in df.columns if re.fullmatch(r"[MS]\d+_emp", c)],
              key=lambda c: (c[0], int(re.findall(r"\d+", c)[0])))
M = df[SPEC].replace("", "0").apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
ms = df["merged_specialties"]
tok_sets = ms.map(lambda s: {t.strip() for t in re.split(r"[|;,]", s) if t.strip()})

CAND = {
    "M1_emp": "General Medicine",
    "M2_emp": "Paediatric medical management",
    "M3_emp": "Neo-natal",
    "M4_emp": "Paediatric cancer",
    "M5_emp": "Medical Oncology",
    "M6_emp": "Radiation Oncology",
    "M7_emp": "Emergency Room Packages (Care requiring less than 12 hrs stay)",
    "M8_emp": "Mental Disorders Packages",
    "M10_emp": "OPD Diagnostic",
    "S1_emp": "General Surgery",
    "S2_emp": "Otorhinolaryngology",
    "S3_emp": "Opthalmology",
    "S4_emp": "Obstetrics & Gynaecology",
    "S5_emp": "Orthopaedics",
    "S6_emp": "Polytrauma",
    "S7_emp": "Urology",
    "S8_emp": "S8",
    "S9_emp": "S9",
    "S10_emp": "Plastic & reconstructive",
    "S11_emp": "Burns management",
    "S12_emp": "Cardiology",
    "S13_emp": "Cardio-thoracic & Vascular surgery",
    "S14_emp": "Paediatric surgery",
    "S15_emp": "Surgical Oncology",
    "S16_emp": "Oral and Maxillofacial Surgery",
}

R = {"bijection_test": {}, "all_exact": True}
for c, tok in CAND.items():
    flag = M[c] == 1
    tokp = tok_sets.map(lambda S, t=tok: t in S)
    exact = bool((flag == tokp).all())
    R["bijection_test"][c] = {
        "token": tok,
        "n_flag1": int(flag.sum()),
        "n_token_present": int(tokp.sum()),
        "flag1_and_token": int((flag & tokp).sum()),
        "flag1_not_token": int((flag & ~tokp).sum()),
        "token_not_flag1": int((~flag & tokp).sum()),
        "set_equality_exact": exact,
    }
    if not exact:
        R["all_exact"] = False

# --- S10 / S11 disambiguation ----------------------------------------------
R["s10_s11"] = {
    "columns_identical_rowwise": bool((M["S10_emp"] == M["S11_emp"]).all()),
    "n_disagree": int((M["S10_emp"] != M["S11_emp"]).sum()),
    "tokens_always_cooccur": bool(
        (tok_sets.map(lambda S: "Plastic & reconstructive" in S)
         == tok_sets.map(lambda S: "Burns management" in S)).all()),
    "note": ("If both are true, S10 vs S11 cannot be told apart from this dataset "
             "alone - the assignment above is by ordinal position only."),
}

# --- S8 / S9 raw storage ----------------------------------------------------
R["s8_s9_raw"] = {
    "S8_emp_distinct_raw": sorted(df["S8_emp"].unique().tolist()),
    "S9_emp_distinct_raw": sorted(df["S9_emp"].unique().tolist()),
    "S8_emp_n_blank": int(df["S8_emp"].eq("").sum()),
    "S9_emp_n_blank": int(df["S9_emp"].eq("").sum()),
    "S9_implies_S8": bool((M.loc[M["S9_emp"] == 1, "S8_emp"] == 1).all()),
    "note": ("S8_emp/S9_emp store blank instead of 0 for the negative case, unlike "
             "every other flag column which stores literal 0. merged_specialties "
             "carries the literal strings 'S8'/'S9' - the upstream decoder failed "
             "to resolve these two codes to names."),
}

# --- rows where merged_specialties is -NA- ---------------------------------
na = tok_sets.map(lambda S: "-NA-" in S)
R["na_token"] = {
    "n_rows": int(na.sum()),
    "all_have_zero_flags": bool((M[na.values].sum(axis=1) == 0).all()),
    "is_sole_token": bool(tok_sets[na].map(lambda S: S == {"-NA-"}).all()),
}

# --- does merged_specialties order match ordinal code order? ---------------
order = [CAND[c] for c in SPEC]
def canonical(s):
    S = {t.strip() for t in re.split(r"[|;,]", s) if t.strip()}
    return "|".join([t for t in order if t in S])
sel = ~ms.eq("") & ~na
recon = ms[sel].map(canonical)
R["merged_specialties_is_ordinal_join"] = {
    "n_tested": int(sel.sum()),
    "n_exact_string_match": int((recon == ms[sel]).sum()),
    "separator_inferred": "|",
    "mismatch_examples": [
        {"row": int(i), "actual": ms[i], "reconstructed": recon[i]}
        for i in recon.index[recon != ms[sel]][:5]],
}

json.dump(R, open("eda/NHA/scripts/intermediate/_codebook.json", "w"), indent=2, default=str)
print(json.dumps(R, indent=2, default=str))
