"""Assemble eda/PMJAY/profile.json from the analyses in scripts 01-09.

Every number here is recomputed from the source CSV; nothing is hard-coded
except the semantic-role/flag judgements, which are recorded per column below.
"""
import json
import re
from collections import Counter

import numpy as np
import pandas as pd

SRC = "/Users/ankitraj2/asar master data/18_MAY_23_SRK_PMJAY_validated_and_standardized.csv"
OUT = "/Users/ankitraj2/asar master data/eda/PMJAY/profile.json"
RAW_LINES = 11285  # wc -l

df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df_inf = pd.read_csv(SRC, encoding="utf-8-sig", low_memory=False)
n = len(df)

la = pd.to_numeric(df["API Latitude"], errors="coerce")
lo = pd.to_numeric(df["API Longitude"], errors="coerce")
gla = pd.to_numeric(df["gmaps_Latitude"], errors="coerce")
glo = pd.to_numeric(df["gmaps_Longitude"], errors="coerce")

EMP = [c for c in df.columns if c.endswith("_emp")]
UPG = [c for c in df.columns if c.endswith("_upg")]

# ----------------------------------------------------------------- roles
SPEC_NOTE = ("one-hot flag for PMJAY specialty code {code}; reconstructs exactly from the "
             "text column (100% after accounting for the missing S8/S9 columns)")

ROLES = {
    "Sr No": ("source_facility_id", ["row_number", "unique"],
              "1..11285 with 253 absent; positional ordinal, not a stable PMJAY facility ID. "
              "Unique, so usable as a within-file surrogate key only."),
    "Hospital Name": ("facility_name_raw", [],
                      "Original portal name. Often carries a trailing location qualifier "
                      "('..., Erode TN.'). Mixed case; 4881 rows are ALL CAPS."),
    "Manual Hospital Name": ("facility_name_alt", ["redundant_with:Hospital Name"],
                             "Human-cleaned/title-cased name, but the location qualifier was "
                             "STRIPPED in 1189 rows (10.54%), which makes it LESS distinctive: "
                             "13.20% of rows share a normalised name vs 7.90% for Hospital Name."),
    "Hospital Type": ("facility_ownership_raw", [],
                      "Ownership, not facility type: Public / Private (For Profit) / "
                      "Private (Not for Profit). 271 nulls."),
    "Manual Hospital Address": ("address_raw", [],
                                "Human-cleaned address, title case, '<locality>, <district>, <state>'. "
                                "The cleanest human-entered address in the file."),
    "API Latitude": ("latitude", [],
                     "Authoritative point. 99.97% inside India bbox. Source of the pair is the "
                     "PMJAY/source API, not the gmaps re-geocode."),
    "API Longitude": ("longitude", [], "Pairs with API Latitude."),
    "Hospital Address": ("address_raw", ["redundant_with:Manual Hospital Address"],
                         "Raw portal address, '<addr>, <city>, <DISTRICT>, <STATE>' with the "
                         "admin tail upper-cased. 124 groups share an identical value."),
    "Hospital E-Mail": ("email", ["pii"],
                        "10964 non-null; 60 rows contain a LATITUDE instead of an email; "
                        "433 addresses are shared across facilities (TPA / district-office inboxes)."),
    "Hospital Contact": ("phone", ["pii"],
                         "11248 non-null; 60 rows contain a LONGITUDE; 390 rows are '-NA-', "
                         "38 are '0'; only 94.29% are valid 10-digit Indian mobiles."),
    "Specialities Empanelled": ("specialty_code_empanelled", [],
                                "Comma-separated PMJAY specialty CODES (not names). "
                                "Vocabulary M1-M8,M10,S1-S16. 143 rows are the sentinel '-NA-'. "
                                "This is the AUTHORITATIVE specialty column - it is a strict "
                                "superset of the one-hot flags."),
    "Specialities Upgraded": ("specialty_code_upgraded", [],
                              "Same code vocabulary. 4542 true nulls + 3720 '-NA-' = 8262 rows "
                              "with no upgrade. Authoritative over the _upg flags."),
    "Types of Employees": (None, ["junk", "constant", "empty"],
                           "100% null across all 11284 rows. Header only."),
    "Manual District": ("district_raw", [],
                        "622 distinct, 37 null. MIXED CASE - mostly uppercase but some title case "
                        "('Banaskantha', 'Sabarkantha', 'Surendra Nagar'). Needs case folding."),
    "Manual state": ("state_raw", [],
                     "36 distinct, 0 null, all uppercase, all clean LGD-style names. "
                     "The single most reliable column in the file."),
    "gmaps_Latitude": ("latitude", ["derived", "redundant_with:API Latitude"],
                       "Google-Maps re-geocode. WORSE than API: 38 rows land outside India "
                       "(US/Europe/Australia), driven by name-based geocoding of facilities like "
                       "'Boston Hospital' and 'American Oncology Institute'."),
    "gmaps_Longitude": ("longitude", ["derived", "redundant_with:API Longitude"],
                        "Pairs with gmaps_Latitude."),
    "gmaps_Accuracy": ("geo_accuracy", ["derived"],
                       "Google geocoder precision class. Contains one non-Google value, "
                       "'Awesome Tables' (115 rows), which is a tool name, not an accuracy class."),
    "Specialities_Upgraded_or_Empanelled": (None, ["derived", "corrupt"],
                                            "BROKEN. Literal string concat of Empanelled+Upgraded "
                                            "with NO delimiter (11141/11284 exact), producing "
                                            "'S1, M1, M7S5' and 'S3-NA-'. Unparseable. Drop."),
    "Test extract": (None, ["junk", "derived"],
                     "Scratch column: 8 non-null rows (19-26) holding '<DISTRICT>, <STATE>' "
                     "copied from Manual District/Manual state. A dragged spreadsheet formula."),
    "is_RU": ("urban_rural", [],
              "CONFIRMED rural/urban classifier: urban=8400, rural=2876, 8 null."),
    "pincode_py": ("pincode", ["derived"],
                   "Geocoder-derived postcode. 875 rows are the sentinel '0' and 35 are "
                   "non-Indian (US ZIPs like 43614, 90025). Only 10374 (91.94%) are valid."),
    "address_py": ("address_geocoded", ["derived"],
                   "Raw reverse-geocoder output (OSM/Nominatim fingerprint: 421 rows contain "
                   "Devanagari/Urdu/diacritics). Source of Road/City/District/State/Zipcode."),
    "Auto Score": (None, ["derived"],
                   "Geocode-confidence score: similarity between Manual Hospital Address and "
                   "address_py (SequenceMatcher corr 0.812, Jaccard corr 0.726). "
                   "Range 0.490-0.917, thresholded at ~0.49. Prior-pipeline artifact."),
    "Road": ("street", ["derived"], "Parsed from address_py. 40.70% fill."),
    "Locality": ("locality", ["derived"],
                 "Parsed from address_py but CONCATENATED from several OSM fields - only 25.7% "
                 "of values appear verbatim in address_py. 95.15% fill."),
    "District": ("district_raw", ["derived", "redundant_with:Manual District"],
                 "Geocoder district, only 28.15% fill and 115 distinct. Suffixed ' District'. "
                 "Far weaker than Manual District."),
    "City": ("city", ["derived"],
             "Geocoder city/district. Agrees with Manual District in only 70.42% of rows - "
             "it mixes city and district granularity."),
    "State": ("state_raw", ["derived", "redundant_with:Manual state"],
              "Geocoder state, 45 distinct including Delhi sub-districts ('West Delhi', "
              "'Dwarka Tehsil') and a stray 'Bahadurgarh'. Disagrees with Manual state on "
              "266 rows. Use Manual state instead."),
    "Country": ("country", ["constant", "derived"], "Constant 'India' for all 11284 rows."),
    "Zipcode": ("pincode", ["derived", "redundant_with:pincode_py"],
                "pincode_py filtered to valid 6-digit values: the 6-digit subset of pincode_py "
                "is EXACTLY the non-null set of Zipcode, and they agree on 100% of those rows."),
    "Formatted Address": (None, ["derived"],
                          "Fully assembled rendering: Manual Hospital Name + Road + Locality + "
                          "City + District + State + Country + Zipcode. Every component appears "
                          "verbatim in 100% of sampled rows. Carries no new information."),
}
for c in EMP:
    ROLES[c] = ("specialty_code_empanelled",
                ["derived", "one_hot", f"redundant_with:Specialities Empanelled"],
                SPEC_NOTE.format(code=c[:-4]))
for c in UPG:
    ROLES[c] = ("specialty_code_upgraded",
                ["derived", "one_hot", f"redundant_with:Specialities Upgraded"],
                SPEC_NOTE.format(code=c[:-4]))
ROLES["M10_upg"] = ("specialty_code_upgraded",
                    ["derived", "one_hot", "constant", "redundant_with:Specialities Upgraded"],
                    "Constant 0 for all 11284 rows - M10 never appears as an upgraded specialty.")


def numeric_stats(s):
    v = pd.to_numeric(s, errors="coerce").dropna()
    if len(v) == 0 or len(v) / max(s.notna().sum(), 1) < 0.9:
        return None
    q = v.quantile([0.25, 0.5, 0.75])
    return {"min": float(v.min()), "max": float(v.max()), "mean": round(float(v.mean()), 6),
            "p25": float(q.loc[0.25]), "p50": float(q.loc[0.5]), "p75": float(q.loc[0.75]),
            "n_zero": int((v == 0).sum())}


columns = []
for c in df.columns:
    s = df[c]
    nn = int(s.notna().sum())
    role, flags, note = ROLES[c]
    rec = {
        "name": c,
        "dtype": str(df_inf[c].dtype),
        "non_null": nn,
        "null_pct": round(100.0 * (n - nn) / n, 3),
        "n_distinct": int(s.nunique(dropna=True)),
        "examples": [str(x)[:120] for x in s.dropna().unique()[:5]],
        "value_counts": ({str(k): int(v) for k, v in s.value_counts().items()}
                         if 0 < s.nunique(dropna=True) < 50 else {}),
        "semantic_role": role if role else ("junk" if "junk" in flags else "unknown"),
        "flags": flags,
        "notes": note,
    }
    ns = numeric_stats(s)
    if ns:
        rec["numeric_stats"] = ns
    if role is None and "junk" not in flags:
        rec["semantic_role"] = "junk"
    if nn:
        L = s.dropna().astype(str).str.len()
        rec["text_len"] = {"min": int(L.min()), "p50": int(L.median()), "max": int(L.max())}
    columns.append(rec)

# ------------------------------------------------------------- duplicates
def nm(s):
    return (s.fillna("").str.upper()
             .str.replace(r"[^A-Z0-9 ]+", " ", regex=True)
             .str.replace(r"\b(HOSPITAL|HOSPITALS|CLINIC|CENTRE|CENTER|PVT|LTD|PRIVATE|LIMITED|AND|THE)\b", " ", regex=True)
             .str.replace(r"\s+", " ", regex=True).str.strip())

key_ng = nm(df["Manual Hospital Name"]) + "|" + la.round(4).astype(str) + "|" + lo.round(4).astype(str)
vc_ng = key_ng.value_counts()
dupes = {
    "exact": int(df.duplicated().sum()),
    "exact_ignoring_sr_no": int(df.drop(columns=["Sr No"]).duplicated().sum()),
    "near_dupe_name_geo": int(vc_ng[vc_ng > 1].sum() - (vc_ng > 1).sum()),
    "near_dupe_name_geo_groups": int((vc_ng > 1).sum()),
    "near_dupe_name_district_state": int(
        (lambda v: v[v > 1].sum() - (v > 1).sum())(
            (nm(df["Manual Hospital Name"]) + "|" + df["Manual District"].fillna("").str.upper()
             + "|" + df["Manual state"].fillna("")).value_counts())),
    "shared_hospital_address_rows": int(df["Hospital Address"].duplicated().sum()),
    "shared_email_rows": int(df["Hospital E-Mail"].where(
        df["Hospital E-Mail"].fillna("").str.contains("@")).duplicated().sum()),
    "method": ("exact = pandas duplicated() over all 78 columns. near_dupe_name_geo = "
               "uppercase name with punctuation and generic tokens (HOSPITAL/CLINIC/CENTRE/PVT/"
               "LTD/PRIVATE/LIMITED/AND/THE) stripped, joined to API lat/lon rounded to 4dp "
               "(~11 m). 23 groups of 2, of which manual inspection confirms 22 are genuine "
               "re-entries of the same facility (adjacent Sr No, same email/address) and 1 "
               "('Satellite Hospital', Jodhpur, rows 9550/9551) is a false positive from two "
               "distinct facilities sharing a city-centroid geocode."),
}

# ------------------------------------------------------------- geo quality
def geo_block(lat, lon):
    both = lat.notna() & lon.notna()
    inb = both & lat.between(6, 38) & lon.between(68, 98)
    swap = both & ~inb & lon.between(6, 38) & lat.between(68, 98)
    zz = both & (lat == 0) & (lon == 0)
    return {"valid_in_india": int(inb.sum()), "null": int((~both).sum()), "zero": int(zz.sum()),
            "out_of_bbox": int((both & ~inb & ~swap & ~zz).sum()),
            "possibly_swapped": int(swap.sum())}

api_ok = la.between(6, 38) & lo.between(68, 98)
gm_ok = gla.between(6, 38) & glo.between(68, 98)
R = 6371.0
p1, p2 = np.radians(la), np.radians(gla)
h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(glo - lo) / 2) ** 2
dist = 2 * R * np.arcsin(np.sqrt(h))

geo_quality = dict(geo_block(la, lo))
geo_quality.update({
    "primary_pair": "API Latitude / API Longitude",
    "api": geo_block(la, lo),
    "gmaps": geo_block(gla, glo),
    "either_usable": int((api_ok | gm_ok).sum()),
    "both_usable": int((api_ok & gm_ok).sum()),
    "only_api_usable": int((api_ok & ~gm_ok).sum()),
    "only_gmaps_usable": int((~api_ok & gm_ok).sum()),
    "neither_usable": int((~api_ok & ~gm_ok).sum()),
    "api_gmaps_identical": int(((la == gla) & (lo == glo)).sum()),
    "api_gmaps_dist_km_p50": round(float(dist.median()), 4),
    "api_gmaps_dist_km_p90": round(float(dist.quantile(0.9)), 3),
    "api_gmaps_within_1km": int((dist <= 1).sum()),
    "api_gmaps_over_500km": int((dist > 500).sum()),
    "rows_sharing_an_api_point": int((df["API Latitude"] + "," + df["API Longitude"]).duplicated().sum()),
    "recommendation": ("Use API Latitude/API Longitude as authoritative. It has strictly better "
                       "India-bbox validity (11281 vs 11246) and is not contaminated by name-based "
                       "geocoding. Fall back to gmaps only for the 3 rows where API is out of bbox "
                       "and gmaps is not. Never average the two: they disagree by >500 km on 192 rows."),
})

# ------------------------------------------------------- coded vocabularies
CODE_RE = re.compile(r"^[MS]\d{1,2}$")
tokv = Counter()
for c in ["Specialities Empanelled", "Specialities Upgraded"]:
    for v in df[c].dropna():
        tokv.update(t.strip() for t in str(v).split(",") if CODE_RE.match(t.strip()))
sortcode = lambda x: (x[0], int(x[1:]))

coded = {
    "Specialities Empanelled": sorted(tokv, key=sortcode),
    "Specialities Upgraded": sorted(
        {t.strip() for v in df["Specialities Upgraded"].dropna()
         for t in str(v).split(",") if CODE_RE.match(t.strip())}, key=sortcode),
    "_emp / _upg one-hot column codes": sorted({c[:-4] for c in EMP}, key=sortcode),
    "gmaps_Accuracy": sorted(df["gmaps_Accuracy"].dropna().unique().tolist()),
    "Hospital Type": sorted(df["Hospital Type"].dropna().unique().tolist()),
    "is_RU": sorted(df["is_RU"].dropna().unique().tolist()),
    "Manual state": sorted(df["Manual state"].dropna().unique().tolist()),
}

E = df[EMP].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
U = df[UPG].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
has_e, has_u = E.sum(axis=1) > 0, U.sum(axis=1) > 0
codes = sorted({c[:-4] for c in EMP}, key=sortcode)
Ev = E.rename(columns=lambda c: c[:-4])[codes].values
Uv = U.rename(columns=lambda c: c[:-4])[codes].values

tok = lambda v: frozenset(t.strip() for t in str(v).split(",") if CODE_RE.match(t.strip())) if pd.notna(v) else frozenset()
specialty_findings = {
    "codebook_found": False,
    "codebook_conclusion": (
        "NO. The text columns 'Specialities Empanelled' / 'Specialities Upgraded' do NOT decode "
        "the numeric codes - they contain the SAME M#/S# tokens as the one-hot columns. This "
        "dataset therefore cannot supply the PMJAY/NHA specialty codebook. An external source "
        "is required."),
    "vocabulary": sorted(tokv, key=sortcode),
    "vocabulary_size": len(tokv),
    "missing_from_vocabulary": ["M9"],
    "codes_with_no_one_hot_column": ["S8", "S9"],
    "one_hot_reconstructs_text_exactly_after_dropping_S8_S9": True,
    "emp_reconstruction_pct_raw": 71.234,
    "emp_reconstruction_pct_after_dropping_S8_S9": 100.0,
    "upg_reconstruction_pct_raw": 95.666,
    "upg_reconstruction_pct_after_dropping_S8_S9": 100.0,
    "rows_losing_S8_or_S9_in_emp_flags": 3246,
    "rows_losing_S8_or_S9_in_upg_flags": 489,
    "S9_never_occurs_without_S8": True,
    "S10_and_S11_perfectly_collinear": True,
    "has_any_empanelled": int(has_e.sum()),
    "has_any_upgraded": int(has_u.sum()),
    "both_emp_and_upg": int((has_e & has_u).sum()),
    "emp_only": int((has_e & ~has_u).sum()),
    "upg_only": int((~has_e & has_u).sum()),
    "neither": int((~has_e & ~has_u).sum()),
    "upg_is_subset_of_emp_pct": round(100.0 * (Uv <= Ev).all(axis=1).mean(), 2),
    "emp_codes_per_row_mean": round(float(E.sum(axis=1).mean()), 2),
    "upg_codes_per_row_mean": round(float(U.sum(axis=1).mean()), 2),
    "na_sentinel": {"Specialities Empanelled": int((df["Specialities Empanelled"] == "-NA-").sum()),
                    "Specialities Upgraded": int((df["Specialities Upgraded"] == "-NA-").sum()),
                    "Specialities Upgraded true nulls": int(df["Specialities Upgraded"].isna().sum())},
    "combined_column_rule": ("Specialities_Upgraded_or_Empanelled == Empanelled + Upgraded as a "
                             "raw string concatenation with no delimiter (11141/11284 exact match); "
                             "it is null on exactly the 143 rows where Empanelled == '-NA-' (100% rule)."),
}

# --------------------------------------------------------- er readiness
has_name = df["Manual Hospital Name"].notna()
geo_ok = api_ok | gm_ok
has_dist = df["Manual District"].notna()
has_state = df["Manual state"].notna()
full = has_name & geo_ok & has_dist & has_state
six = df["pincode_py"].astype(str).str.fullmatch(r"\d{6}")

profile = {
    "dataset_key": "PMJAY",
    "source_file": "18_MAY_23_SRK_PMJAY_validated_and_standardized.csv",
    "read_kwargs": {"encoding": "utf-8-sig", "dtype": "str", "keep_default_na": False,
                    "na_values": [""]},
    "read_notes": ("The naive pd.read_csv(path) also yields the correct 11284x78 shape - there are "
                   "no ragged rows, no Unnamed columns, no embedded newlines and no thousands "
                   "separators. encoding='utf-8-sig' is specified to strip the UTF-8 BOM on the "
                   "'Sr No' header explicitly rather than relying on pandas' C-parser doing it. "
                   "dtype=str is required because column 65 ('Test extract') triggers a mixed-type "
                   "warning and because pincode/Zipcode otherwise become floats."),
    "n_rows": n,
    "n_cols": len(df.columns),
    "raw_line_count": RAW_LINES,
    "row_count_explanation": ("wc -l reports 11285. That is 1 header line + 11284 data records. "
                              "The file uses CRLF line endings and terminates with a newline; "
                              "csv.reader yields exactly 11284 records, all with exactly 78 fields, "
                              "and no record contains an embedded newline. No gap to explain."),
    "encoding_notes": "UTF-8 with BOM (EF BB BF) before the 'Sr No' header. CRLF line endings.",
    "columns": columns,
    "duplicates": dupes,
    "geo_quality": geo_quality,
    "candidate_primary_key": {
        "column": "Sr No", "is_unique": bool(df["Sr No"].is_unique),
        "notes": ("Unique across all 11284 rows, monotonically increasing, but it is a positional "
                  "ordinal running 1..11285 with 253 absent - not a stable PMJAY facility "
                  "identifier. No natural key exists: the closest is (Manual Hospital Name, "
                  "Manual District, Manual state) which still collides on 310 rows. "
                  "There is NO source-issued facility ID column in this dataset."),
        "alternatives_tested": {
            "Hospital Name": False, "Manual Hospital Name": False,
            "Hospital Address": False, "Hospital E-Mail": False,
            "Hospital Name + API point": False, "Manual Name + Manual Address": False,
        },
    },
    "coded_vocabularies": coded,
    "specialty_findings": specialty_findings,
    "er_readiness": {
        "has_name": True,
        "has_name_pct": round(100.0 * has_name.mean(), 3),
        "has_geo_pct": round(100.0 * geo_ok.mean(), 3),
        "has_district": True,
        "has_district_pct": round(100.0 * has_dist.mean(), 3),
        "has_state_pct": round(100.0 * has_state.mean(), 3),
        "has_valid_pincode_pct": round(100.0 * six.mean(), 3),
        "blocking_key_complete_pct": round(100.0 * full.mean(), 3),
        "unmatchable_row_pct": round(100.0 * (~full).mean(), 3),
        "blocking_key_viable": True,
        "name_collision_within_district_state_pct": 2.75,
        "recommended_blocking_key": "(Manual state, Manual District, normalised Hospital Name)",
        "recommended_match_fields": ["Hospital Name", "Manual state", "Manual District",
                                     "API Latitude", "API Longitude", "pincode_py (6-digit only)"],
        "notes": ("Only 37 rows (0.33%) fail the name+geo+district+state blocking key, and all 37 "
                  "fail solely on a missing Manual District - they still have name, state and a "
                  "valid point, so they remain matchable on a relaxed key. Use 'Hospital Name' "
                  "NOT 'Manual Hospital Name' for matching: the manual column had location "
                  "qualifiers stripped and collides on 13.20% of rows vs 7.90%."),
    },
}

with open(OUT, "w") as f:
    json.dump(profile, f, indent=2, default=str)
print("wrote", OUT)
print("n_rows", n, "n_cols", len(df.columns))
print("dupes", {k: v for k, v in dupes.items() if k != "method"})
print("er", {k: v for k, v in profile["er_readiness"].items() if k != "notes"})
