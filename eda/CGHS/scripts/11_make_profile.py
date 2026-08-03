"""CGHS EDA - step 11: emit eda/CGHS/profile.json from verified numbers."""
import pandas as pd, numpy as np, json, re
from collections import Counter, OrderedDict

ROOT = "/Users/ankitraj2/asar master data"
SRC = f"{ROOT}/18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv"
OUT = f"{ROOT}/eda/CGHS/profile.json"
READ_KWARGS = {"encoding": "utf-8-sig", "dtype": "str", "keep_default_na": False, "na_values": [""]}
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
N = len(df)
raw_lines = open(SRC, "rb").read().count(b"\n")

lat = pd.to_numeric(df["Latitude"]); lon = pd.to_numeric(df["Longitude"])
inbox = lat.between(6, 38) & lon.between(68, 98)
pair = df["Latitude"] + "," + df["Longitude"]
vc_pair = pair.value_counts()

def nname(s):
    s = s.upper(); s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\b(PVT|PRIVATE|LTD|LIMITED|THE|AND|A|UNIT|OF)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()
nn = df["Hospital_Name"].map(nname)
geo3 = lat.round(3).astype(str) + "," + lon.round(3).astype(str)

# ---------------- column metadata ----------------
ROLE = {
 "Unnamed: 0":            ("junk", ["constant_free_index", "derived"],
    "Preserved pandas RangeIndex from an upstream frame. Monotonic increasing 0..2090 with 108 missing "
    "integers -> the upstream frame had 2091 rows and 108 were dropped before export. Unique here but "
    "meaningless as an entity key."),
 "Hospital_Id":           ("source_facility_id", [],
    "CGHS/HMIS application id. Unique across all 1983 rows. Structure: prefix HOSP (1901) or LAB (81) + "
    "state code digits + ownership letter (G/P/T, HOSP only) + application serial. One malformed value "
    "('17006035', row 1050) has no prefix."),
 "Hospital_Name":         ("facility_name_raw", [],
    "Facility name as typed by the applicant. Mixed case (1424 UPPER, 51 lower, 508 mixed), 36 rows with "
    "double spaces, 117 contain 'unit of' / corporate-entity suffixes. No non-ASCII."),
 "District":              ("district_raw", [],
    "Mostly UPPERCASE; 8 values in title case. 39 rows hold the sentinel '-NA-' (all ANDHRA PRADESH). "
    "101 distinct values incl. sentinel. 'RANGA REDDY' appears under both TELANGANA (14) and ANDHRA PRADESH (1)."),
 "State":                 ("state_raw", [],
    "24 distinct, all UPPERCASE, no sentinel/nulls. Uses 'NCT OF DELHI'. Covers only 24 states/UTs - "
    "no Himachal, Assam, Chandigarh, NE states other than Meghalaya/Tripura."),
 "Hospital_Contact":      ("phone", ["pii"],
    "Single phone number. 1941/1983 are valid 10-digit Indian mobiles (leading 6-9); 3 rows are literal '0', "
    "1 row is '-NA-', 38 rows null. 201 rows share a number with another row (max reuse: 9810423972 x10) - "
    "chain / corporate-group hospitals."),
 "Specialities_Selected": ("specialty_list", ["multi_value"],
    "Comma-delimited multi-value code list, trailing comma on every non-null value, leading comma on 383 rows. "
    "47 distinct tokens across TWO mutually exclusive codebooks (see coded_vocabularies): a 22-code "
    "2-letter family and a 24-code M#/S# family. No row mixes families. 280 rows repeat a token within the row."),
 "Hospital_Type":         ("facility_ownership_raw", [],
    "Ownership. 517 rows (26.07%) null; part of that is structural (80 of the 81 LAB-prefixed rows and all 3 "
    "'T'-letter rows are null). Disagrees with the Hospital_Id ownership letter on 8 rows (5 G-rows typed Private, 3 P-rows typed Public)."),
 "Empanelment_Type":      ("empanelment_type", [],
    "Which scheme(s) the facility is empanelled under. Binary."),
 "Submitted_Date":        ("junk", ["constant"],
    "Constant literal '-NA' on all 1983 rows. Carries no information; the source column was blanked before export."),
 "Status_Updated_Date":   ("junk", ["constant"],
    "Constant literal '-NA' on all 1983 rows. Carries no information."),
 "Application_Status":    ("empanelment_status", ["constant"],
    "Constant 'Hospital Approved for Empanelment' on all 1983 rows. The file is a pre-filtered "
    "approved-only slice, so the column is informative about the dataset but not about any row."),
 "OnBoarded_For_Convergence_Scheme": ("scheme_membership", [],
    "Yes/No flag for the CGHS-PMJAY convergence onboarding. Note it does NOT agree with Empanelment_Type: "
    "1015 'Yes' vs only 69 'PMJAY and CGHS'."),
 "Address":               ("address_raw", ["redundant_with:Hospital_Name+District+State", "derived"],
    "NOT a street address. It is the literal concatenation Hospital_Name + ', ' + District + ', ' + State - "
    "byte-identical on 1875/1983 rows (94.55%) and identical on 1983/1983 rows (100%) once whitespace is "
    "collapsed (the 108 exceptions carry a stray space before the first comma). Zero incremental information "
    "over the three source columns."),
 "Latitude":              ("latitude", ["derived"],
    "Forward-geocoded from the synthetic Address string (not surveyed). 100% populated, no zeros, "
    "1776 distinct pairs; 109 rows sit on one of 10 coordinates shared by >=5 rows, which are administrative "
    "centroids (e.g. 15.9128998/79.7399875 = Andhra Pradesh state centroid, 37 rows)."),
 "Longitude":             ("longitude", ["derived"],
    "Same provenance as Latitude. Two rows carry US coordinates (negative longitude)."),
 "Postcode_py":           ("pincode", ["derived"],
    "Extracted from address_py, not from the source registry - it is a substring of address_py in 1935/1935 "
    "non-null rows. 1934 are 6-digit; 1 is '3302' (row 220, a US ZIP 03302 with the leading zero eaten by a "
    "numeric cast). 48 rows null. The '_py' suffix marks it as a Python-pipeline output."),
 "address_py":            ("address_raw", ["derived", "geo_source:reverse_geocode"],
    "Reverse-geocoded address string for (Latitude, Longitude), Nominatim/OSM formatted "
    "('..., <District> District, <State>, <PIN>, India'). 1981/1983 end in 'India'. This is the only "
    "real street-level address text in the file, but it describes the geocode result, not the registry record."),
}
DERIVED_NOTES = {
 "Levenshtein Distance":     "= 1 - OSA_edit_distance(Address, address_py)/max(len). Reproduced exactly on 1983/1983 rows. A SIMILARITY despite the name.",
 "Jaro Wrinkler Distance":   "= JaroWinkler.similarity(Address, address_py). Reproduced exactly on 1983/1983 rows. A SIMILARITY despite the name.",
 "Jaccard Distance":         "= bag-of-CHARACTERS Jaccard similarity of (Address, address_py): |multiset intersection| / (len(a)+len(b)-intersection). Exact on 1983/1983 rows. Character-multiset, not token - so it is dominated by casing and length, not by address content.",
 "Cosine Distance":          "= bag-of-CHARACTERS cosine similarity: intersection/sqrt(len(a)*len(b)). Exact on 1983/1983 rows.",
 "Monge Elkan Distance":     "Range 0.00218-0.01341, far below the [0,1] range a real Monge-Elkan similarity occupies. Not reproduced by any standard Monge-Elkan variant tried (best: comma-token Jaro ME divided by len(Address), r=0.81, no exact rows). Correlates -0.63 with len(Address) - looks like a length-divided / buggy implementation. UNRESOLVED.",
 "BWTRLENCD Distance":       "= 1 - NCD(Address, address_py) where the compressor is Burrows-Wheeler transform followed by run-length encoding: (C(a)+C(b)-C(ab))/max(C(a),C(b)). Reproduced exactly on 1931/1983 rows (97.4%), r=0.9985; residual rows presumably differ in BWT sentinel/tie-break. Takes negative values on 1129 rows and is exactly 0 on 259 rows.",
 "Monge Elkan Distance*10":  "Exactly 10 x 'Monge Elkan Distance' (max abs deviation 5e-9). Fully redundant.",
 "Auto Score":               "Exactly affine in three of the other columns: 0.1867386636*Levenshtein + 0.1975256764*JaroWinkler + 0.6157356594*MongeElkan*10 + 0.4287057853 (R^2=1.0, max residual 9.0e-10; the three weights sum to 1.000000). Jaccard, Cosine and BWTRLENCD contribute nothing. No documented threshold; range is narrow [0.5351, 0.7189].",
}

cols = []
for c in df.columns:
    s = df[c]
    nnull = int(s.notna().sum())
    nd = int(s.nunique(dropna=True))
    entry = OrderedDict()
    entry["name"] = c
    entry["dtype"] = "string(raw csv); " + ("int64" if c == "Unnamed: 0" else
                     "float64" if c in ("Latitude","Longitude","Postcode_py") or c in DERIVED_NOTES else "object")
    entry["non_null"] = nnull
    entry["null_pct"] = round(100 * (1 - nnull / N), 4)
    entry["n_distinct"] = nd
    entry["examples"] = [str(x) for x in s.dropna().unique()[:5]]
    entry["value_counts"] = ({str(k): int(v) for k, v in s.value_counts(dropna=False).items()}
                             if nd < 50 else {})
    if c in DERIVED_NOTES:
        entry["semantic_role"] = "derived"
        entry["flags"] = ["derived", "prior_pipeline_artifact",
                          "compares:Address~address_py"] + (["redundant_with:Monge Elkan Distance"]
                          if c == "Monge Elkan Distance*10" else [])
        entry["notes"] = DERIVED_NOTES[c]
        v = pd.to_numeric(s)
        entry["numeric_stats"] = {k: float(round(x, 9)) for k, x in
            {"min": v.min(), "p25": v.quantile(.25), "median": v.median(),
             "mean": v.mean(), "p75": v.quantile(.75), "max": v.max(), "std": v.std()}.items()}
    else:
        role, flags, note = ROLE[c]
        entry["semantic_role"] = role
        entry["flags"] = flags
        entry["notes"] = note
        if c in ("Latitude", "Longitude"):
            v = pd.to_numeric(s)
            entry["numeric_stats"] = {"min": float(v.min()), "max": float(v.max()),
                                      "mean": float(v.mean()), "median": float(v.median())}
        if c == "Unnamed: 0":
            v = pd.to_numeric(s)
            entry["numeric_stats"] = {"min": int(v.min()), "max": int(v.max()),
                                      "missing_integers_in_range": 108, "monotonic_increasing": True}
        if c == "Specialities_Selected":
            toks = [t.strip() for v_ in s.dropna() for t in v_.split(",") if t.strip()]
            entry["multivalue"] = {"delimiter": ",", "distinct_tokens": len(set(toks)),
                                   "total_tokens": len(toks),
                                   "tokens_per_row_min": 1, "tokens_per_row_max": 30,
                                   "tokens_per_row_mean": 7.64, "tokens_per_row_median": 3,
                                   "rows_with_trailing_delimiter": 1746,
                                   "rows_with_leading_delimiter": 383,
                                   "rows_with_intra_row_duplicate_tokens": 280}
    cols.append(entry)

profile = OrderedDict()
profile["dataset_key"] = "CGHS"
profile["source_file"] = "18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv"
profile["read_kwargs"] = READ_KWARGS
profile["read_notes"] = (
    "File is UTF-8 with a BOM and CRLF line endings; a naive pd.read_csv() leaves the BOM on the first "
    "header name ('\\ufeffUnnamed: 0'), so encoding='utf-8-sig' is required. There are NO embedded newlines "
    "inside quoted fields and every record has exactly 26 fields, so csv.reader and pandas agree on the row "
    "count. dtype=str + keep_default_na=False + na_values=[''] is recommended so that Postcode_py keeps its "
    "leading zeros and '-NA'/'-NA-' sentinels stay visible instead of being silently cast.")
profile["n_rows"] = N
profile["n_cols"] = df.shape[1]
profile["raw_line_count"] = raw_lines
profile["row_count_explanation"] = (
    f"wc -l reports {raw_lines} because the file has {raw_lines} newline-terminated physical lines: 1 header "
    f"+ {N} data records, and it ends with a trailing CRLF. There are no embedded newlines "
    "(csv.reader returns 1984 records, all exactly 26 fields wide), so the true data shape is 1983 x 26, "
    "not 1984 x 26.")
profile["sentinels"] = {"-NA": ["Submitted_Date (1983)", "Status_Updated_Date (1983)"],
                        "-NA-": ["District (39)", "Hospital_Contact (1)"],
                        "0": ["Hospital_Contact (3)"],
                        "NA": ["Specialities_Selected token (33 rows)"]}
profile["columns"] = cols
profile["duplicates"] = {
    "exact": 0,
    "exact_ignoring_index_col": 0,
    "near_dupe_name_geo": 28,
    "method": ("exact = df.duplicated() over all 26 columns (also 0 after dropping 'Unnamed: 0'). "
               "near_dupe_name_geo = df.duplicated(subset=[normalized_name, lat/lon rounded to 3dp]) where "
               "normalized_name = uppercase, non-alphanumerics -> space, drop tokens "
               "{PVT,PRIVATE,LTD,LIMITED,THE,AND,A,UNIT,OF}, collapse whitespace. 3dp ~ 110 m."),
    "other_keys": {
        "duplicated(Hospital_Name)": 68,
        "duplicated(Hospital_Name, State)": 37,
        "duplicated(Hospital_Name, District, State)": 20,
        "duplicated(normalized_name)": 115,
        "duplicated(normalized_name, State)": 53,
        "duplicated(Hospital_Name, District, State, Address, Latitude, Longitude)": 17,
        "duplicated(Latitude, Longitude)": 207},
    "notes": ("32 rows fall into 15 groups that are identical on (name, district, state, address, lat, lon) "
              "but carry different Hospital_Id and different Specialities_Selected - i.e. the same physical "
              "facility filed multiple empanelment applications, one per specialty batch or per codebook "
              "version. Example: 'Aditya Super Speciality Hospital & Trauma Centre', JABALPUR - "
              "HOSP23P120251 (M5,S10,S11,S3) and HOSP23P128502 (21 two-letter codes).")}
profile["geo_quality"] = {
    "valid_in_india": int(inbox.sum()),
    "valid_in_india_pct": round(100 * float(inbox.mean()), 4),
    "null": 0,
    "zero": int(((lat == 0) | (lon == 0)).sum()),
    "out_of_bbox": int((~inbox).sum()),
    "possibly_swapped": 0,
    "bbox_used": {"lat": [6, 38], "lon": [68, 98]},
    "lat_range": [float(lat.min()), float(lat.max())],
    "lon_range": [float(lon.min()), float(lon.max())],
    "distinct_coordinate_pairs": int(pair.nunique()),
    "rows_sharing_a_coordinate": int(vc_pair[vc_pair > 1].sum()),
    "rows_on_coordinate_shared_by_5plus_rows": int((pair.map(vc_pair) >= 5).sum()),
    "geocode_provenance": ("Coordinates are forward-geocoded from the synthetic Address string "
                           "('Name, District, State'). Where the geocoder could not resolve the name it fell "
                           "back to a district or state centroid, so 111 rows share 17 centroid coordinates. "
                           "The two out-of-bbox rows resolved to the United States "
                           "(row 220 -> Concord, New Hampshire; row 1319 -> Bedford County, Tennessee)."),
    "usable_precise_geo_rows": int((inbox & (pair.map(vc_pair) < 5)).sum()),
    "usable_precise_geo_pct": round(100 * float((inbox & (pair.map(vc_pair) < 5)).mean()), 4)}
profile["candidate_primary_key"] = {
    "column": "Hospital_Id", "is_unique": True, "n_distinct": 1983, "null_count": 0,
    "notes": ("Unique and complete, and it is a real upstream application id (not a row number), so it is the "
              "correct source_facility_id. It is an APPLICATION id, not a facility id: 15 groups of rows are "
              "the same facility under different Hospital_Ids. 'Unnamed: 0' is also unique but is a discarded "
              "pandas index and must not be used.")}
alpha = ["BM","ER","IN","MC","MG","MN","MO","MP","MR","SB","SC","SE","SG","SL","SM","SN","SO","SP","SS","ST","SU","SV"]
num = ["M1","M2","M3","M4","M5","M6","M7","M8"] + [f"S{i}" for i in range(1, 17)]
profile["coded_vocabularies"] = {
    "Specialities_Selected__all_tokens": sorted(set(alpha + num + ["NA"])),
    "Specialities_Selected__family_A_two_letter": alpha,
    "Specialities_Selected__family_B_numeric": num,
    "Specialities_Selected__sentinel_tokens": ["NA"],
    "Hospital_Id__prefix": ["HOSP", "LAB"],
    "Hospital_Id__ownership_letter": ["G", "P", "T"],
    "Hospital_Id__state_code": sorted(set(df["Hospital_Id"].str.extract(r"^HOSP(\d+)[A-Z]\d+$")[0].dropna()),
                                      key=int),
    "State": sorted(df["State"].unique().tolist()),
    "Hospital_Type": sorted(df["Hospital_Type"].dropna().unique().tolist()),
    "Empanelment_Type": sorted(df["Empanelment_Type"].unique().tolist()),
    "Application_Status": sorted(df["Application_Status"].unique().tolist()),
    "OnBoarded_For_Convergence_Scheme": sorted(df["OnBoarded_For_Convergence_Scheme"].unique().tolist())}
profile["coded_vocabulary_notes"] = {
    "Specialities_Selected": ("47 distinct tokens in two MUTUALLY EXCLUSIVE families - 968 rows use only the "
        "22 two-letter codes, 745 rows use only the 24 M#/S# codes, 33 rows use two-letter codes plus a "
        "literal 'NA'; zero rows mix the families. Neither codebook's expansion is present in this file. "
        "The split is not random: 204 of the 303 Delhi rows that carry specialties use the numeric family while "
        "299 of the 316 such UP rows use the two-letter family, "
        "two-letter family, so it most likely reflects two different CGHS application-form vintages."),
    "Hospital_Id__state_code": ("Matches LGD/Census-2011 state codes on 24 of the 26 observed values "
        "(3=Punjab, 7=Delhi, 9=UP, 19=West Bengal, 27=Maharashtra, 36=Telangana, ...). Two disagree: code 4 "
        "(LGD=Chandigarh) is carried by 17 rows whose District is Amritsar/Jalandhar/S.A.S Nagar and State is "
        "PUNJAB, and code 37 (LGD=Ladakh) is carried by 1 Delhi row. Likely a CGHS administrative-city code "
        "that coincides with LGD for most states."),
    "Hospital_Id__ownership_letter": ("G correlates with Hospital_Type='Public' (29/35 non-null), P with "
        "Private (1426/1429 non-null), T appears on 3 Gujarat trust-run hospitals whose Hospital_Type is null. "
        "Reading G=Government, P=Private, T=Trust is consistent with the data but is not documented anywhere "
        "in the file.")}
profile["provenance"] = {
    "source_snapshot_date": None,
    "snapshot_date_available": False,
    "reason": ("Both date columns (Submitted_Date, Status_Updated_Date) are the constant literal '-NA' on all "
               "1983 rows, so no per-row or dataset-level date can be derived from the data. The only date "
               "signal is the filename token '18_SEPTEMBER_23' -> 2023-09-18, which should be treated as an "
               "externally-asserted snapshot date, not a measured one."),
    "filename_implied_date": "2023-09-18"}
has_name = df["Hospital_Name"].notna() & (df["Hospital_Name"].str.strip() != "")
has_dist = df["District"].notna() & (df["District"] != "-NA-")
profile["er_readiness"] = {
    "has_name": True,
    "has_name_pct": round(100 * float(has_name.mean()), 4),
    "has_geo_pct": round(100 * float(inbox.mean()), 4),
    "has_trustworthy_geo_pct": round(100 * float((inbox & (pair.map(vc_pair) < 5)).mean()), 4),
    "has_district": True,
    "has_district_pct": round(100 * float(has_dist.mean()), 4),
    "has_state_pct": 100.0,
    "has_pincode_pct": round(100 * float(df["Postcode_py"].notna().mean()), 4),
    "unmatchable_row_pct": round(100 * float((~(has_name & has_dist & inbox)).mean()), 4),
    "blocking_key_viable": True,
    "blocking_key_notes": ("(state, district, normalized_name) is viable for 1944/1983 rows (98.03%). The 39 "
        "rows with District='-NA-' are all ANDHRA PRADESH and 37 of them also sit on the AP state centroid, so "
        "they must fall back to (state, name) blocking. (lat, lon) alone is NOT a safe blocking key: 111 rows "
        "sit on 10 administrative centroids. Pincode from Postcode_py is derived from the geocode, so it "
        "inherits the same error and must not be treated as an independent match signal."),
    "unmatchable_rows_definition": "rows lacking any of: non-empty name, a District other than '-NA-', in-bbox coordinates"}
profile["dataset_summary"] = {
    "program": "Central Government Health Scheme (CGHS) hospital/diagnostic-lab empanelment registry",
    "entity_grain": "one empanelment APPLICATION (Hospital_Id), not one facility",
    "row_scope": "approved empanelments only (Application_Status constant)",
    "facility_kinds": {"HOSP-prefixed (hospitals/clinics)": 1901, "LAB-prefixed (diagnostic labs/imaging centres)": 81,
                       "malformed id": 1},
    "columns_from_source_registry": 12,
    "columns_added_by_a_prior_python_pipeline": 14,
    "prior_pipeline_columns": ["Unnamed: 0", "Address", "Latitude", "Longitude", "Postcode_py", "address_py",
        "Levenshtein Distance", "Jaro Wrinkler Distance", "Jaccard Distance", "Cosine Distance",
        "Monge Elkan Distance", "BWTRLENCD Distance", "Monge Elkan Distance*10", "Auto Score"]}

with open(OUT, "w") as f:
    json.dump(profile, f, indent=2, ensure_ascii=False)
print("wrote", OUT, len(json.dumps(profile)), "bytes")
print(json.dumps({k: v for k, v in profile.items() if k != "columns"}, indent=2)[:200])
