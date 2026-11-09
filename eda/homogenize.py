#!/usr/bin/env python
"""
Phase 2b — homogenization: turn the raw vocabularies in facilities_v0 into
controlled ones.

Three gaps from eda/03_GAP_REGISTER.md are closed here, all without external data:

  Gap 3  facility_type   56 raw strings   -> 22-value enum   (name-token derived)
         ownership       16 raw strings   -> 5-value enum
  Gap 2  district      1,051 raw variants -> clustered canon  (within-state fuzzy)

Nothing here matches records to each other; that is resolve.py. This module only
makes fields comparable, which is the precondition for matching.

Every mapping produced is written to a dim_* table so it is auditable and
correctable by hand — the enum is a decision, not a fact, and it should be
reviewable as one.
"""
import re

import pandas as pd
from rapidfuzz import fuzz

WS = re.compile(r"\s+")

# --------------------------------------------------------------- facility_type
# The enum. Ordered coarse -> specific; `classify_type` returns exactly one.
TYPES = [
    "SUB_CENTRE", "PHC", "CHC", "SUB_DISTRICT_HOSPITAL", "DISTRICT_HOSPITAL",
    "MEDICAL_COLLEGE", "HOSPITAL", "WELLNESS_CENTRE", "DISPENSARY", "CLINIC",
    "DENTAL", "AYUSH", "PHARMACY", "DIAGNOSTIC_LAB", "IMAGING_CENTRE",
    "DIALYSIS_CENTRE", "PHYSIOTHERAPY", "MATERNITY_HOME", "BLOOD_BANK",
    "BLOOD_STORAGE_UNIT", "OTHER", "UNKNOWN",
]

# Hard classes. Two records whose types fall in *different* classes are never the
# same real-world entity, however close their coordinates. A blood bank sited
# inside a hospital campus is still a different facility from the hospital.
TYPE_CLASS = {
    "BLOOD_BANK": "BLOOD", "BLOOD_STORAGE_UNIT": "BLOOD",
    "PHARMACY": "RETAIL",
    "DIAGNOSTIC_LAB": "DIAG", "IMAGING_CENTRE": "DIAG",
    "SUB_CENTRE": "CARE", "PHC": "CARE", "CHC": "CARE",
    "SUB_DISTRICT_HOSPITAL": "CARE", "DISTRICT_HOSPITAL": "CARE",
    "MEDICAL_COLLEGE": "CARE", "HOSPITAL": "CARE", "WELLNESS_CENTRE": "CARE",
    "DISPENSARY": "CARE", "CLINIC": "CARE", "MATERNITY_HOME": "CARE",
    "DENTAL": "CARE", "AYUSH": "CARE", "DIALYSIS_CENTRE": "CARE",
    "PHYSIOTHERAPY": "CARE",
}

# The public-health ladder. These tiers are *co-located by design* — a sub-centre
# sits beside the PHC it reports to — so proximity is not evidence that two of them
# are the same facility. Two records at different known rungs never merge.
# WELLNESS_CENTRE is deliberately excluded: under Ayushman Bharat, existing PHCs
# and sub-centres were relabelled HWCs, so HWC/PHC pairs are frequently the same
# building under two names and must stay mergeable.
PUBLIC_TIER = {
    "SUB_CENTRE": 1, "PHC": 2, "CHC": 3,
    "SUB_DISTRICT_HOSPITAL": 4, "DISTRICT_HOSPITAL": 5, "MEDICAL_COLLEGE": 6,
}

# Tier rank, used when a cluster's members disagree: the more specific label wins.
TYPE_RANK = {t: i for i, t in enumerate([
    "UNKNOWN", "OTHER", "CLINIC", "DISPENSARY", "WELLNESS_CENTRE", "SUB_CENTRE",
    "PHYSIOTHERAPY", "DENTAL", "AYUSH", "MATERNITY_HOME", "PHARMACY",
    "DIAGNOSTIC_LAB", "IMAGING_CENTRE", "DIALYSIS_CENTRE", "BLOOD_STORAGE_UNIT",
    "BLOOD_BANK", "PHC", "CHC", "HOSPITAL", "SUB_DISTRICT_HOSPITAL",
    "DISTRICT_HOSPITAL", "MEDICAL_COLLEGE",
])}

# Ordered rules over the concatenated (type_raw + ' ' + name) text. First hit wins,
# so the specific patterns must precede the generic ones.
_TYPE_RULES = [
    ("BLOOD_STORAGE_UNIT", r"\bBSU\b|BLOOD\s*STORAGE"),
    ("BLOOD_BANK",         r"BLOOD\s*(BANK|CENTRE|CENTER)|\bBB\b"),
    ("MEDICAL_COLLEGE",    r"MEDICAL\s+COLLEGE|\bAIIMS\b|INSTITUTE OF MEDICAL|"
                           r"(AYURVEDA|HOMEOPATHY|UNANI|SIDDHA|DENTAL) COLLEGE|\bCOLLEGE\b"),
    ("DISTRICT_HOSPITAL",  r"DISTRICT\s+HOSPITAL|\bDH\b|CIVIL HOSPITAL|GENERAL HOSPITAL"),
    ("SUB_DISTRICT_HOSPITAL", r"SUB[\s-]*DISTRICT\s+HOSPITAL|\bSDH\b|"
                              r"SUB[\s-]*DIVISIONAL HOSPITAL|TALUKA HOSPITAL|REFERRAL HOSPITAL"),
    ("CHC",                r"COMMUNITY\s+HEALTH\s+(CENTRE|CENTER)|\bCHC\b|"
                           r"URBAN COMMUNITY HEALTH"),
    ("PHC",                r"PRIMARY\s+HEALTH\s+(CENTRE|CENTER|UNIT)|\bPHC\b|\bUPHC\b|"
                           r"MINI PHC|ADDITIONAL PHC"),
    ("SUB_CENTRE",         r"SUB[\s-]*(CENTRE|CENTER)|\bSC\b|\bHSC\b|HEALTH SUB"),
    ("WELLNESS_CENTRE",    r"WELLNESS|\bHWC\b|AAM AADMI (MOHALLA )?CLINIC|MOHALLA CLINIC"),
    ("DIALYSIS_CENTRE",    r"DIALYSIS"),
    ("PHYSIOTHERAPY",      r"PHYSIOTHERAP"),
    ("IMAGING_CENTRE",     r"IMAGING|RADIOLOG|\bMRI\b|\bCT SCAN\b|SONOGRAPH|CATH\s*LAB"),
    ("DIAGNOSTIC_LAB",     r"DIAGNOSTIC|PATHOLOG|\bLAB(ORATORY)?\b|COLLECTION CENTRE"),
    ("PHARMACY",           r"PHARMAC|\bCHEMIST\b|MEDICAL STORE|JAN AUSHADHI|DRUG STORE"),
    ("DENTAL",             r"DENTAL|DENTIST"),
    ("MATERNITY_HOME",     r"MATERNITY|POST\s*PARTUM|NURSING HOME"),
    ("AYUSH",              r"AYURVED|HOMEOPATH|HOMOEOPATH|UNANI|SIDDHA|\bYOGA\b|\bAYUSH\b"),
    ("HOSPITAL",           r"HOSPITAL|\bNURSING\b|BEDDED"),
    ("DISPENSARY",         r"DISPENSAR"),
    ("CLINIC",             r"CLINIC|POLYCLINIC|DAY CARE|DOCTOR|\bOPD\b"),
    ("OTHER",              r"OTHERS?"),
]
_TYPE_RULES = [(t, re.compile(p)) for t, p in _TYPE_RULES]

# Words that carry no identity — a name that is *only* these is not a name.
# Used both for type derivation and for the name-informativeness test in resolve.py.
GENERIC_NAME_WORDS = {
    "PRIMARY", "HEALTH", "CENTRE", "CENTER", "COMMUNITY", "SUB", "SUBCENTRE",
    "PHC", "CHC", "SC", "HSC", "UPHC", "PHU", "HWC", "WELLNESS", "AND",
    "HOSPITAL", "GOVT", "GOVERNMENT", "GENERAL", "CIVIL", "DISTRICT", "STATE",
    "CLINIC", "DISPENSARY", "MEDICAL", "UNIT", "NEW", "OLD", "MAIN", "THE",
    "OF", "DR", "SMT", "SHRI", "ADDITIONAL", "MINI", "URBAN", "RURAL", "BEDDED",
    "NURSING", "HOME", "CARE", "TRUST", "PVT", "LTD", "PRIVATE", "PUBLIC",
    "BLOOD", "BANK", "BSU", "STORAGE", "SERVICES", "SERVICE", "INDIA",
}


def classify_type(type_raw, name_raw, source_dataset=None):
    """Derive the controlled facility_type.

    Name tokens outrank the source's own type column, because the source column is
    demonstrably unreliable: PHC/CHC carry the filename tier (4.1% leak, findings
    §3) and NHP's is a constant injected at ingest.
    """
    name = _up(name_raw)
    traw = _up(type_raw)

    # Name first — it is the more trustworthy signal where the two disagree.
    for t, pat in _TYPE_RULES:
        if pat.search(name):
            return t, "name"
    for t, pat in _TYPE_RULES:
        if pat.search(traw):
            return t, "type_column"
    if traw:
        return "OTHER", "type_column_unmatched"
    return "UNKNOWN", "none"


def _up(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return WS.sub(" ", re.sub(r"[^A-Za-z0-9 ]", " ", str(v))).strip().upper()


# ------------------------------------------------------------------ ownership
_OWN_RULES = [
    ("PPP",                     r"PARTNERSHIP|\bPPP\b"),
    ("PRIVATE_NOT_FOR_PROFIT",  r"NOT\s*FOR\s*PROFIT|CHARITABLE|TRUST|SOCIETY|"
                                r"RED CROSS|\bNGO\b|VOL"),
    ("PRIVATE_FOR_PROFIT",      r"PRIVATE|\bPVT\b|FOR\s*PROFIT|CORPORATE"),
    ("GOVERNMENT",              r"GOV|PUBLIC|STATE|CENTRAL|MUNICIPAL|\bESI\b|RAILWAY|"
                                r"DEFENCE|ARMY|AUTONOMOUS"),
]
_OWN_RULES = [(t, re.compile(p)) for t, p in _OWN_RULES]
OWNERSHIPS = ["GOVERNMENT", "PRIVATE_FOR_PROFIT", "PRIVATE_NOT_FOR_PROFIT", "PPP", "UNKNOWN"]


def classify_ownership(raw):
    s = _up(raw)
    if not s or s in {"NAN", "NA", "NONE", "NULL"}:
        return "UNKNOWN"
    for t, pat in _OWN_RULES:
        if pat.search(s):
            return t
    return "UNKNOWN"


# ------------------------------------------------------------------- district
# Tokens that must agree exactly for two spellings to be the same district.
# Without this guard NORTH GOA / SOUTH GOA merge at ratio 89, and
# PURBA BARDHAMAN / PASCHIM BARDHAMAN at 82.
DIRECTIONAL = {
    "NORTH", "SOUTH", "EAST", "WEST", "CENTRAL", "UPPER", "LOWER", "NEW", "OLD",
    "PURBA", "PASCHIM", "PURBI", "PASCHIMI", "DAKSHIN", "DAKSHINA", "UTTAR",
    "UTTARA", "PURVI", "MADHYA", "INNER", "OUTER", "GREATER", "NORTHERN",
    "SOUTHERN", "EASTERN", "WESTERN", "RURAL", "URBAN",
}
_DISTRICT_NOISE = re.compile(r"\b(DISTRICT|DISTT|DIST|ZILLA|ZILA|JILA)\b")
_NUM = re.compile(r"\d+")
# 86, not 90. Genuine variants cluster at 86-89 (AHMEDABAD/AHMADABAD,
# MARIGAON/MORIGAON, ANANTAPUR/ANANTHPUR) and every pair the drop from 90 to 86
# newly merges was checked by hand: 20 variants, 571 records, no false merges.
# The guards above — not the threshold — are what keep BANGALORE R/U,
# WARANGAL URBAN/RURAL and SAGAR/AGAR apart.
DISTRICT_SIM_THRESHOLD = 86


def _district_stem(s):
    """Strip the noise words that vary freely, keep everything that identifies."""
    s = _DISTRICT_NOISE.sub(" ", _up(s))
    return WS.sub(" ", s).strip()


def _district_guard(a, b):
    """True when a and b are allowed to be the same district."""
    ta, tb = set(a.split()), set(b.split())
    if (ta & DIRECTIONAL) != (tb & DIRECTIONAL):
        return False
    if set(_NUM.findall(a)) != set(_NUM.findall(b)):
        return False
    # Single-letter tokens are abbreviations that change the referent, not typos:
    # BANGALORE R and BANGALORE U are Bengaluru Rural and Bengaluru Urban, two
    # districts, and they sit at similarity 90 to plain BANGALORE.
    if {t for t in ta if len(t) == 1} != {t for t in tb if len(t) == 1}:
        return False
    return a[:1] == b[:1]  # a first-letter change is a different name, not a typo


def build_district_map(df, threshold=DISTRICT_SIM_THRESHOLD):
    """Cluster district spellings within each state.

    Greedy leader clustering, variants visited most-frequent-first, so the
    canonical form is always the most common spelling in that state. Clustering is
    strictly within-state: BIJAPUR exists in both Karnataka and Chhattisgarh and
    they are different districts.

    Returns a DataFrame: state_norm, district_norm, district_canon, n_records,
    is_canonical, similarity.
    """
    rows = []
    src = df[["state_norm", "district_norm"]].dropna()
    counts = src.value_counts().reset_index(name="n")
    for state, grp in counts.groupby("state_norm", sort=False):
        leaders = []  # (stem, canon_label)
        for _, r in grp.sort_values("n", ascending=False).iterrows():
            variant, stem = r["district_norm"], _district_stem(r["district_norm"])
            if not stem:
                rows.append((state, variant, variant, r["n"], True, 100.0))
                continue
            best, best_score = None, 0.0
            for lstem, lcanon in leaders:
                if not _district_guard(stem, lstem):
                    continue
                sc = fuzz.token_sort_ratio(stem, lstem)
                if sc > best_score:
                    best, best_score = lcanon, sc
            if best is not None and best_score >= threshold:
                rows.append((state, variant, best, r["n"], False, best_score))
            else:
                leaders.append((stem, variant))
                rows.append((state, variant, variant, r["n"], True, 100.0))
    return pd.DataFrame(rows, columns=[
        "state_norm", "district_norm", "district_canon", "n_records",
        "is_canonical", "similarity"])


def apply_district_map(df, dmap):
    key = df["state_norm"].fillna("") + "|" + df["district_norm"].fillna("")
    lut = dict(zip(dmap["state_norm"] + "|" + dmap["district_norm"], dmap["district_canon"]))
    return key.map(lut).where(df["district_norm"].notna())


# ------------------------------------------------------------------ name_core
_NAME_NOISE = re.compile(r"[^A-Z0-9 ]")

# A token this common cannot identify a facility. Derived from the corpus rather
# than hand-listed, because the hand list will always miss something: the first
# build missed AYURVEDA, and 'AYURVEDA' alone then matched every ayurveda
# dispensary in a district to every other one.
CORPUS_TOKEN_MAX = 500


def corpus_generic_tokens(names, max_df=CORPUS_TOKEN_MAX):
    """Tokens appearing in more than `max_df` records — non-identifying by frequency."""
    from collections import Counter
    cnt = Counter()
    for n in names:
        if n:
            cnt.update(set(_NAME_NOISE.sub(" ", str(n)).split()))
    return {t for t, c in cnt.items() if c > max_df}


def name_core(name_norm, extra_generic=frozenset()):
    """The identifying part of a name: everything that is not a type or filler word.

    'PRIMARY HEALTH CENTRE KHERA' -> 'KHERA'.  'PRIMARY HEALTH CENTRE' -> ''.
    An empty core means the name distinguishes nothing, and 32,336 records are in
    that position — matching them on name is how you merge 93 distinct PHCs in
    Nanded district into one.
    """
    if not name_norm:
        return ""
    toks = [t for t in _NAME_NOISE.sub(" ", str(name_norm)).split()
            if len(t) > 2 and t not in GENERIC_NAME_WORDS and t not in extra_generic]
    return " ".join(toks)


# Name strength governs which matching rules a record is eligible for. The failure
# mode being defended against is a one-token core ('CHITTAR') matching every
# facility in Chittar to every other, so a single short token is deliberately
# not enough to merge on at distance.
STRONG, MEDIUM, WEAK = "STRONG", "MEDIUM", "WEAK"


def name_strength(core):
    if not core:
        return WEAK
    toks = core.split()
    if len(toks) >= 2 or len(toks[0]) >= 9:
        return STRONG
    if len(toks[0]) >= 4:
        return MEDIUM
    return WEAK
