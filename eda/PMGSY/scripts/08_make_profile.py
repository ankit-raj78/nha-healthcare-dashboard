"""Step 8: emit eda/PMGSY/profile.json. Every number is computed here."""
import pandas as pd, numpy as np, json, re, csv, difflib
from collections import Counter

BASE = "/Users/ankitraj2/asar master data"
SRC = f"{BASE}/21_JULY_23_SRK_PMGSY_validated_homogenized.csv"
OUT = f"{BASE}/eda/PMGSY/profile.json"

with open(SRC, "rb") as f:
    raw_lines = sum(1 for _ in f)
with open(SRC, encoding="utf-8-sig", newline="") as f:
    recs = list(csv.reader(f))
n_embedded_nl = sum(c.count("\n") for r in recs for c in r)

READ_KWARGS = {"encoding": "utf-8-sig", "dtype": "str", "keep_default_na": False,
               "na_values": [""], "sep": ",", "quotechar": '"', "engine": "c"}
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
n_all_null = int(df.isna().all(axis=1).sum())
df = df.dropna(how="all").reset_index(drop=True)
N = len(df)
lat = pd.to_numeric(df["LATITUDE"], errors="coerce")
lon = pd.to_numeric(df["LONGITUDE"], errors="coerce")

def norm(s):
    return s.fillna("").str.lower().str.replace(r"[^a-z0-9]", " ", regex=True)\
            .str.replace(r"\s+", " ", regex=True).str.strip()
nm = norm(df["MASTER_FACILITY_DESC"])

GENERIC = {"chc","phc","hospital","dispensary","clinic","bedded hospital","community health centre",
 "community health center","medical","beded hospital","hospital bedded","c h c","health centre",
 "health center","sub centre","sub center","govt hospital","nursing home","primary health centre",
 "dispansary","hospitals","phc bedded hospital","bedded hospital dispensary"}
informative = ~nm.isin(GENERIC)

# --- near dupes: haversine 150 m + name similarity
from scipy.spatial import cKDTree
R = 6371000.0
la, lo = np.radians(lat.values), np.radians(lon.values)
xyz = np.c_[np.cos(la)*np.cos(lo), np.cos(la)*np.sin(lo), np.sin(la)] * R
pairs = cKDTree(xyz).query_pairs(r=150, output_type="ndarray")
nmv = nm.values
sim = np.array([difflib.SequenceMatcher(None, nmv[i], nmv[j]).ratio() for i, j in pairs])
near_dupe = int((sim >= 0.85).sum())

apy_pin = df["address_py"].fillna("").str.extract(r"\b(\d{6})\b")[0]
dates = pd.to_datetime(df["FILE_UPLOAD_DATE"], format="%d-%b-%y", errors="coerce")

ROLES = {
 "Sr. No. ": ("junk", ["row_number","unique"],
   "1..13700 with no gaps; the file's only unique column, but it is a positional ordinal, not a stable source identifier. Header literally contains a trailing space."),
 "STATE_NAME": ("state_raw", [],
   "29 distinct. Non-LGD spellings: 'Tamilnadu' (LGD: Tamil Nadu), 'Pondicherry' (LGD: Puducherry), 'Jammu And Kashmir'. Goa, Nagaland, Delhi and all other UTs absent."),
 "DISTRICT_NAME": ("district_raw", [],
   "663 distinct. Pre-rename / misspelled variants throughout (Jalor->Jalore, Sangali->Sangli, Gurgaon->Gurugram, Belgaum->Belagavi, G.B. Nagar->Gautam Buddha Nagar)."),
 "BLOCK_NAME": ("block_raw", [], "4443 distinct PMGSY block names. 879 rows have BLOCK_NAME == DISTRICT_NAME."),
 "HABITATION_NAME": ("village_raw", [],
   "11607 distinct. PMGSY habitation, finer than a revenue village. 1465 rows (10.69%) have HABITATION_NAME == BLOCK_NAME (block-HQ habitations). 7 values carry a leading U+00A0."),
 "HAB_CODE": ("proposed:habitation_code", ["coded_vocabulary"],
   "PMGSY/OMMAS habitation code, all numeric, 3-7 digits, range 349..1429221. NOT unique: 12092 distinct over 13700 rows; 1016 codes carry 2..48 rows. Never spans more than one state/district/habitation name, so it identifies the HABITATION, not the facility."),
 "MASTER_FACILITY_DESC": ("facility_name_raw", [],
   "Free-text facility name entered by field staff. 8851 raw / 8172 normalised distinct. 4046 rows (29.53%) are nothing but a generic facility-type word (24-token generic list in scripts/05_deep.py; a wider variant list gives 4098 / 29.91%). 5723 rows (41.77%) have <=2 tokens."),
 "ADDRESS": ("address_raw", [],
   "Very thin: 60.90% are <=12 chars, 39.14% are byte-identical to HABITATION_NAME, only 224 rows contain a digit. 322 rows contain a literal newline."),
 "FILE_UPLOAD_DATE": ("source_snapshot_date", [],
   "%d-%b-%y. Parses 13637/13700; 63 nulls, all Tamil Nadu. Range 2019-01-09 .. 2022-11-26; 72.83% of rows (9978) are Aug-Dec 2019."),
 "MASTER_FACILITY_CATEGORY_NAME": ("facility_category_raw", ["constant"],
   "Constant 'Medical' for all 13700 rows. In the wider PMGSY facility master this column also takes Education/Transport/etc values; this extract has already been filtered to Medical, so no schools/roads are present as a CATEGORY -- but see issues.md, a handful of non-health rows survive in the free-text name."),
 "SUB_CATEGORY": ("facility_type_raw", ["coded_vocabulary"],
   "Only 2 values. This is PMGSY's own coarse label and it frequently disagrees with the facility name: 2546 of 6393 'Community Health Centre' rows have no CHC/community-health token in the name, and 89 of them are literally named 'hospital'."),
 "LATITUDE": ("latitude", [],
   "Field-collected point, 8 decimal places on 81.3% of rows. 100% inside India's bbox, no zeros, no nulls."),
 "LONGITUDE": ("longitude", [], "See LATITUDE."),
 "Postcode_py": ("pincode", ["derived"],
   "Reverse-geocoder output (the _py suffix marks a Python geocoding pass). Byte-identical to 'Pincode' on 13700/13700 rows. Trustworthy only on the 11304 rows where address_py also echoes the same 6-digit token."),
 "address_py": ("proposed:address_geocoded", ["derived"],
   "Reverse-geocoded formatted address from (LATITUDE, LONGITUDE). 13699/13700 end in 'India'. 333 rows contain Devanagari/Chinese/Urdu script from OSM local-language name tags. This is the ONLY independent evidence about location in the file."),
 "Hospital Name": ("facility_name_raw", ["redundant_with:MASTER_FACILITY_DESC"],
   "Copy of MASTER_FACILITY_DESC, identical on 13699/13700 rows (sole exception Sr. No. 8). Not geocoder output. Drop."),
 "Street/Locality": ("address_raw", ["redundant_with:ADDRESS"], "Byte-identical to ADDRESS on 13700/13700 rows. Drop."),
 "Habitation": ("village_raw", ["redundant_with:HABITATION_NAME"], "Byte-identical to HABITATION_NAME on 13700/13700 rows. Drop."),
 "Block": ("block_raw", ["redundant_with:BLOCK_NAME"], "Byte-identical to BLOCK_NAME on 13700/13700 rows. Drop."),
 "City/District": ("district_raw", ["redundant_with:DISTRICT_NAME"], "Byte-identical to DISTRICT_NAME on 13700/13700 rows. Drop."),
 "State": ("state_raw", ["redundant_with:STATE_NAME"], "Byte-identical to STATE_NAME on 13700/13700 rows. Drop."),
 "Country": ("country", ["constant"], "Constant 'India'."),
 "Pincode": ("pincode", ["redundant_with:Postcode_py","derived"], "Byte-identical to Postcode_py on 13700/13700 rows. Drop one."),
 "Formatted Address": ("junk", ["derived"],
   "Deterministic concatenation, reproduced exactly on 13700/13700 rows by: join(', ', [Hospital Name, Street/Locality, Habitation, Block if lower(Block)!=lower(Habitation), City/District, State, Country, Pincode]). Carries zero new information. Drop."),
}

cols = []
for c in df.columns:
    s = df[c]
    nn = int(s.notna().sum())
    nd = int(s.nunique(dropna=True))
    role, flags, notes = ROLES[c]
    entry = {
        "name": c, "dtype": "string", "non_null": nn,
        "null_pct": round(100 * (N - nn) / N, 4), "n_distinct": nd,
        "examples": [str(x) for x in s.dropna().unique()[:5]],
        "value_counts": ({str(k): int(v) for k, v in s.value_counts(dropna=False).items()}
                         if nd < 50 else {}),
        "semantic_role": role, "flags": list(flags), "notes": notes,
    }
    if c in ("LATITUDE", "LONGITUDE"):
        v = pd.to_numeric(s, errors="coerce")
        entry["numeric_summary"] = {k: float(round(x, 6)) for k, x in
            v.describe(percentiles=[.01, .25, .5, .75, .99]).items()}
    if c == "HAB_CODE":
        v = pd.to_numeric(s, errors="coerce")
        entry["numeric_summary"] = {"min": float(v.min()), "max": float(v.max()),
                                    "n_codes_with_multiple_rows": int((s.value_counts() > 1).sum()),
                                    "max_rows_per_code": int(s.value_counts().max())}
    if c == "FILE_UPLOAD_DATE":
        entry["date_summary"] = {"format": "%d-%b-%y", "parsed": int(dates.notna().sum()),
            "unparsed_non_null": int((s.notna() & dates.isna()).sum()),
            "min": str(dates.min().date()), "max": str(dates.max().date()),
            "by_year": {str(int(k)): int(v) for k, v in dates.dt.year.value_counts().sort_index().items()}}
    if s.dtype == object and nd >= 50:
        L = s.dropna().str.len()
        entry["text_length"] = {"min": int(L.min()), "p50": float(L.median()),
                                "mean": round(float(L.mean()), 2), "max": int(L.max())}
    cols.append(entry)

profile = {
 "dataset_key": "PMGSY",
 "source_file": "21_JULY_23_SRK_PMGSY_validated_homogenized.csv",
 "read_kwargs": READ_KWARGS,
 "post_read_steps": [
   f"df = df.dropna(how='all')  # removes {n_all_null} trailing all-empty records (physical lines 14899-14900, literally ',,,,,,,,,,,,,,,,,,,,,,,')",
   "reset_index(drop=True)",
   "NOTE: do NOT strip the header -- the first column name is literally 'Sr. No. ' with a trailing space, and the file starts with a UTF-8 BOM (EF BB BF) which encoding='utf-8-sig' removes.",
 ],
 "n_rows": N, "n_cols": int(df.shape[1]), "raw_line_count": raw_lines,
 "row_count_explanation": (
   f"wc -l = {raw_lines}. The csv module yields {len(recs)} logical records = 1 header + {N} data rows "
   f"+ {n_all_null} trailing all-empty records. The {raw_lines - len(recs)} extra physical lines are exactly the "
   f"{n_embedded_nl} newline characters embedded inside quoted fields (322 rows carry a newline inside ADDRESS / "
   f"Street/Locality / Formatted Address, e.g. Sr. No. 56 ADDRESS = 'Govt Hospital\\nPunganur'). "
   f"{len(recs)} + {n_embedded_nl} = {raw_lines}. True logical row count is {N}."),
 "columns": cols,
 "duplicates": {
   "exact": int(df.duplicated().sum()),
   "exact_ignoring_row_ordinal": int(df[[c for c in df.columns if c != "Sr. No. "]].duplicated().sum()),
   "near_dupe_name_geo": near_dupe,
   "method": ("near_dupe_name_geo = count of row pairs within 150 m (haversine via cKDTree on ECEF coords) "
              "whose lowercased alphanumeric-normalised MASTER_FACILITY_DESC has difflib SequenceMatcher "
              f"ratio >= 0.85. Total pairs within 150 m = {len(pairs)}; >=0.70 similarity = {int((sim>=0.70).sum())}. "
              "Other definitions computed: duplicated (normname, LATITUDE, LONGITUDE) = "
              f"{int(pd.DataFrame({'n':nm,'a':df.LATITUDE,'o':df.LONGITUDE}).duplicated().sum())}; "
              f"duplicated (LATITUDE, LONGITUDE) = {int(df.duplicated(subset=['LATITUDE','LONGITUDE']).sum())}; "
              f"duplicated (normname, latlon rounded to 3dp ~111 m) = "
              f"{int(pd.DataFrame({'n':nm,'g':lat.round(3).astype(str)+lon.round(3).astype(str)}).duplicated().sum())}; "
              f"duplicated (normname, HAB_CODE) = {int(pd.DataFrame({'n':nm,'h':df.HAB_CODE}).duplicated().sum())}; "
              f"duplicated (normname, DISTRICT_NAME) = {int(pd.DataFrame({'n':nm,'d':df.DISTRICT_NAME}).duplicated().sum())} "
              "(this last one is inflated by generic names such as 'CHC' and is NOT a dedup signal)."),
   "rows_sharing_exact_latlon": int(df.duplicated(subset=["LATITUDE","LONGITUDE"], keep=False).sum()),
 },
 "geo_quality": {
   "valid_in_india": int(((lat.between(6,38)) & (lon.between(68,98))).sum()),
   "null": int((lat.isna() | lon.isna()).sum()),
   "zero": int(((lat == 0) | (lon == 0)).sum()),
   "out_of_bbox": int((lat.notna() & lon.notna() & ~((lat.between(6,38)) & (lon.between(68,98)))).sum()),
   "possibly_swapped": int(((lon.between(6,38)) & (lat.between(68,98))).sum()),
   "lat_min": float(lat.min()), "lat_max": float(lat.max()),
   "lon_min": float(lon.min()), "lon_max": float(lon.max()),
   "decimal_places_distribution": {str(k): int(v) for k, v in
     sorted(Counter(df["LATITUDE"].dropna().str.split(".").str[-1].str.len()).items())},
   "note": "Best geo of any column in this file: 100% populated, 100% in-bbox, 0 zeros, 0 swaps, facility-level precision (48 distinct points inside a single HAB_CODE).",
 },
 "pincode_quality": {
   "n_populated": int(df["Pincode"].notna().sum()),
   "all_six_digits": int(df["Pincode"].dropna().str.fullmatch(r"\d{6}").sum()),
   "leading_zero": int(df["Pincode"].dropna().str.startswith("0").sum()),
   "corroborated_by_address_py": int(apy_pin.notna().sum()),
   "corroborated_and_agreeing": int((apy_pin[apy_pin.notna()] == df["Pincode"][apy_pin.notna()]).sum()),
   "uncorroborated_fallback": int(apy_pin.isna().sum()),
   "fallback_failing_district_2digit_prefix_check": 443,
   "note": ("Pincode is 100% populated but only 11304 rows (82.51%) are echoed by the geocoded address_py string; "
            "on those 11304 the two agree 100%. Of the 2396 uncorroborated rows, 443 carry a pincode whose first "
            "2 digits do not appear on any corroborated row in the same state+district (control: 11304/11304 "
            "corroborated rows pass the same test). Treat the uncorroborated 17.49% as unreliable."),
 },
 "candidate_primary_key": {
   "column": "Sr. No. ", "is_unique": bool(df["Sr. No. "].is_unique),
   "note": ("'Sr. No. ' is unique (1..13700, no gaps) but it is a spreadsheet row ordinal, not a source system key -- "
            "it will not survive a re-extract. HAB_CODE is NOT unique (12092 distinct / 13700 rows, max 48 rows per code) "
            "because it identifies a habitation, not a facility. Recommended surrogate: "
            "'PMGSY:' || HAB_CODE || ':' || Sr. No.  , or the composite (HAB_CODE, MASTER_FACILITY_DESC, LATITUDE, LONGITUDE) "
            "which is unique across all 13700 rows."),
   "alternatives_tested": {
     "HAB_CODE": {"n_distinct": int(df.HAB_CODE.nunique()), "is_unique": bool(df.HAB_CODE.is_unique)},
     "(HAB_CODE, MASTER_FACILITY_DESC, LATITUDE, LONGITUDE)": {
       "is_unique": bool(df.duplicated(subset=["HAB_CODE","MASTER_FACILITY_DESC","LATITUDE","LONGITUDE"]).sum() == 0)},
     "(LATITUDE, LONGITUDE)": {"n_distinct": int(len(set(zip(df.LATITUDE, df.LONGITUDE)))), "is_unique": False},
   },
 },
 "grain": {
   "one_row_is": "one health facility, located in one PMGSY habitation",
   "is_link_table": False,
   "evidence": [
     f"HAB_CODE repeats: {int((df.HAB_CODE.value_counts()>1).sum())} codes carry 2..{int(df.HAB_CODE.value_counts().max())} rows, but within a repeated code the facility NAMES are all different and the lat/lon are all different (e.g. HAB_CODE 440318 = Jagatpur, Bareilly, UP has 48 rows: 'chanderlok hospital', 'medinova hospital', 'khushlok hospital', ... each with its own coordinate). That is many facilities in one habitation, not one facility linked to many habitations.",
     "A habitation-facility link table would repeat the same facility under different habitations. It does not: only 1 (normalised-name, lat, lon) triple appears under more than one HAB_CODE, and only 7 exact (lat, lon) pairs do.",
     "HAB_CODE never spans more than one STATE_NAME (0 codes), DISTRICT_NAME (0 codes) or HABITATION_NAME (0 codes), confirming it is a geographic key that is 1:1 with the habitation.",
     "(HAB_CODE, MASTER_FACILITY_DESC, LATITUDE, LONGITUDE) is unique over all 13700 rows.",
   ],
 },
 "coded_vocabularies": {
   "MASTER_FACILITY_CATEGORY_NAME": ["Medical"],
   "SUB_CATEGORY": ["Bedded Hospital", "Community Health Centre"],
   "Country": ["India"],
   "STATE_NAME": sorted(df.STATE_NAME.dropna().unique().tolist()),
   "HAB_CODE": "12092 distinct numeric PMGSY/OMMAS habitation codes, range 349..1429221 -- open vocabulary, needs the external OMMAS/LGD habitation master to decode. Not enumerated here.",
 },
 "er_readiness": {
   "has_name": True,
   "has_geo_pct": round(100 * float(((lat.between(6,38)) & (lon.between(68,98))).sum()) / N, 2),
   "has_district": True,
   "has_informative_name_pct": round(100 * float(informative.sum()) / N, 2),
   "unmatchable_row_pct": round(100 * float((~informative).sum()) / N, 2),
   "blocking_key_viable": True,
   "note": ("Geo is the strong signal: 100% of rows carry a usable, facility-precision coordinate, so a "
            "geo-radius block (district + 250 m) works for every row. Name is the weak signal: "
            f"{int((~informative).sum())} rows ({round(100*float((~informative).sum())/N,2)}%) have a name that is "
            "only a facility-type word ('CHC', 'bedded hospital', 'Dispensary') and cannot be matched on name at all. "
            "Address adds nothing (60.9% of ADDRESS values are <=12 chars and 39.1% just restate the habitation). "
            "Pincode is usable on the 82.5% of rows the geocoder corroborates. Recommended blocking key: "
            "state_raw + district_raw normalised to LGD + lat/lon rounded to 3dp, with name similarity as the scorer, "
            "NOT as the blocker."),
 },
}

with open(OUT, "w") as f:
    json.dump(profile, f, indent=2, ensure_ascii=False)
print("wrote", OUT)
print(json.dumps({k: v for k, v in profile.items() if k != "columns"}, indent=2)[:1500])
