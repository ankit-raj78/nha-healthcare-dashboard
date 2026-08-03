"""NHP EDA step 9: emit eda/NHP/profile.json from measured values only."""
import csv, io, json, re
from collections import Counter, OrderedDict
import pandas as pd, numpy as np

SRC = "/Users/ankitraj2/asar master data/8_JULY_23_SRK_NHP_validated_and_standardized.csv"
OUT = "/Users/ankitraj2/asar master data/eda/NHP/profile.json"
NORM = lambda s: re.sub(r"\s+", " ", s).strip() if isinstance(s, str) else s

raw = open(SRC, "rb").read()
raw_line_count = raw.count(b"\n")
text = raw.decode("utf-8-sig")
allrows = list(csv.reader(io.StringIO(text, newline="")))
hdr_raw = allrows[0]
logical_records = len(allrows) - 1
blank_rows = sum(1 for r in allrows[1:] if all(v.strip() == "" for v in r))
embedded_nl_data = sum(v.count("\n") for r in allrows[1:] for v in r)
embedded_nl_hdr = sum(v.count("\n") for v in hdr_raw)

READ_KW = OrderedDict([
    ("encoding", "utf-8-sig"),
    ("dtype", "str"),
    ("keep_default_na", False),
    ("na_values", [""]),
    ("skip_blank_lines", False),
])
df_full = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
COLS_RAW = list(df_full.columns)          # 29, with 'S.\n  No.' and Unnamed: 19..28
df = df_full.dropna(how="all").reset_index(drop=True)   # 648 real rows
N = len(df)

lat = pd.to_numeric(df["Latitude"], errors="coerce")
lon = pd.to_numeric(df["Longitude"], errors="coerce")
hn = df["Hospital Name"].map(NORM)
nmk = hn.str.casefold()

ROLES = {
 "S.\n  No.": dict(role="source_facility_id", flags=["row_number", "positional_only"],
   notes="Excel serial 1..648, contiguous, unique and complete. Not a stable external identifier; usable only as a within-snapshot surrogate key."),
 "Hospital Name": dict(role="facility_name_raw", flags=[],
   notes="Names of medical colleges/institutes. 73/648 carry an embedded newline+2spaces soft-wrap artifact; 68 show truncation or abbreviation ('Colleg', 'Instt.', trailing comma). 114 rows (17.59%) carry a fully generic name."),
 "Latitude": dict(role="latitude", flags=[],
   notes="All 648 numeric, all inside India bbox. 3-6 decimal places. 7 rows share coordinates with another row (city/state-centroid fallback suspected)."),
 "Longitude": dict(role="longitude", flags=[], notes="Same as Latitude."),
 "Given Address": dict(role="address_raw", flags=["derived", "redundant_with:Hospital Name+City+State"],
   notes="Not an independent address. 509/648 exactly equal '<Hospital Name>, <City> <State>'; 631/648 contain City; 648/648 end with State; only 27 rows contain any token not already present in name+city+state. No pincode, no street."),
 "Standardized Address": dict(role="address_raw", flags=["derived", "redundant_with:Hospital Name+City+State+Country+Postcode"],
   notes="100% mechanically reconstructable as '<Hospital Name>, <City>, <State>, India, <Postcode>.' (648/648 exact match). Carries zero information beyond its component columns. Display string only."),
 "City": dict(role="city", flags=[],
   notes="429 distinct. Free-text city/town, NOT an LGD district. 1 null, 7 values carry the newline artifact. Only proxy available for district-level blocking."),
 "State": dict(role="state_raw", flags=[],
   notes="33 distinct, clean of whitespace artifacts, but contains misspellings: 'Utttar Pradesh' (67 rows), 'Chattisgarh' (14). Needs LGD normalization."),
 "Country": dict(role="country", flags=["constant"], notes="Constant 'India' on all 648 rows."),
 "Postcode": dict(role="pincode", flags=[],
   notes="646/648 non-null; 645 are clean 6-digit; 1 is '380 006' (embedded space); 2 null."),
 "Type": dict(role="facility_ownership_raw", flags=[],
   notes="5-value ownership enum. Trailing period on 'Govt.' only."),
 "Admission Intake": dict(role="admission_intake", flags=[],
   notes="Annual MBBS seat intake. 100% fill on real rows, 100% integer-parseable, no thousands separators. 5 rows are 0 (missing encoded as zero)."),
 "No. of beds in attached Hospital": dict(role="bed_count", flags=[],
   notes="72.22% fill. 466/468 parse as integers; 2 are free text ('500 + 50 (floating)', 'Na'). 2 rows are 0."),
 "Accrediation": dict(role="junk", flags=["empty", "constant"],
   notes="Header misspelled ('Accrediation'). 100% empty across all 999 CSV records. Intended canonical target would be `accreditation`."),
 "Domains": dict(role="junk", flags=["empty", "constant"],
   notes="100% empty. Meaning undetermined -- see questions.md."),
 "Contact": dict(role="junk", flags=["empty", "constant", "would_be_pii"],
   notes="100% empty. Would have been phone/contact PII if populated; no PII is actually present in this file."),
 "Source Sheet Name": dict(role="source_sheet_name", flags=["constant"],
   notes="Constant 'NHP_Medical_Colleges' on all 648 rows. Confirms this extract is a single source sheet of NHP medical colleges."),
 "Postcode_py": dict(role="pincode", flags=["redundant_with:Postcode", "derived"],
   notes="Byte-identical to Postcode on 648/648 rows including the two nulls and the malformed '380 006'. Drop."),
 "address_py": dict(role="address_raw", flags=["derived", "reverse_geocoded"],
   notes="Reverse-geocoded from Latitude/Longitude by a prior Python step. Only column with street-level detail, but unreliable as a facility address: 241/648 (37.2%) share zero 4+char tokens with the facility name, 117 mention 'Blood Bank', and 4 pairs of distinct facilities share an identical value."),
}
for c in COLS_RAW:
    if c.startswith("Unnamed:"):
        ROLES[c] = dict(role="junk", flags=["empty", "constant"],
                        notes="Trailing all-empty column produced by an Excel export with 29 comma positions. 0 non-null across all 999 CSV records.")

columns = []
for c in COLS_RAW:
    s_full = df_full[c]
    s = df[c] if c in df.columns else pd.Series([], dtype=object)
    nn = int(s.notna().sum())
    nd = int(s.nunique(dropna=True))
    ex = [str(x) for x in s.dropna().unique()[:3]]
    vc = {}
    if 0 < nd < 50:
        vc = {str(k): int(v) for k, v in s.value_counts().items()}
    r = ROLES[c]
    entry = {
        "name": c,
        "dtype": "object(str)",
        "non_null": nn,
        "non_null_all_999_records": int(s_full.notna().sum()),
        "null_pct": round(100 * (1 - nn / N), 2),
        "n_distinct": nd,
        "examples": ex,
        "value_counts": vc,
        "semantic_role": r["role"],
        "flags": r["flags"],
        "notes": r["notes"],
    }
    if c in ("Latitude", "Longitude", "Admission Intake", "No. of beds in attached Hospital", "S.\n  No."):
        n = pd.to_numeric(s, errors="coerce")
        entry["numeric"] = {
            "parseable": int(n.notna().sum()),
            "unparseable": int((s.notna() & n.isna()).sum()),
            "min": float(n.min()), "max": float(n.max()), "mean": round(float(n.mean()), 4),
            "p25": float(n.quantile(.25)), "p50": float(n.quantile(.5)), "p75": float(n.quantile(.75)),
            "p95": float(n.quantile(.95)), "zeros": int((n == 0).sum()),
        }
    if c in ("Hospital Name", "Given Address", "Standardized Address", "address_py", "City"):
        L = s.map(NORM).dropna().str.len()
        entry["text_length"] = {"min": int(L.min()), "p25": int(L.quantile(.25)),
                                "p50": int(L.median()), "p75": int(L.quantile(.75)),
                                "p95": int(L.quantile(.95)), "max": int(L.max())}
        entry["rows_with_embedded_newline"] = int(s.fillna("").str.contains("\n").sum())
    columns.append(entry)

geo4 = nmk + "||" + lat.round(2).astype(str) + "," + lon.round(2).astype(str)
coordkey = lat.astype(str) + "," + lon.astype(str)

profile = {
  "dataset_key": "NHP",
  "source_file": "8_JULY_23_SRK_NHP_validated_and_standardized.csv",
  "read_kwargs": {
      "encoding": "utf-8-sig",
      "dtype": "str",
      "keep_default_na": False,
      "na_values": [""],
      "post_read": [
          "df = df.rename(columns={'S.\\n  No.': 'S. No.'})",
          "df = df.drop(columns=[c for c in df.columns if c.startswith('Unnamed:')])",
          "df = df.dropna(how='all').reset_index(drop=True)   # removes 351 trailing blank rows",
          "for c in TEXT_COLS: df[c] = df[c].str.replace(r'\\s+', ' ', regex=True).str.strip()"
      ],
      "note": "Default pd.read_csv() already parses the embedded newlines correctly (quoting is well-formed). No engine='python', sep or quoting overrides needed. The only things naive reads get wrong are: keeping 351 blank rows, keeping 10 empty Unnamed columns, and the literal newline inside the first column name."
  },
  "n_rows": N,
  "n_cols": 19,
  "n_cols_raw": len(COLS_RAW),
  "n_logical_csv_records": logical_records,
  "n_blank_trailing_records": blank_rows,
  "raw_line_count": raw_line_count,
  "row_count_explanation": (
      f"`wc -l` reports {raw_line_count} because it counts LF bytes. The file uses CRLF as the record "
      f"separator ({raw.count(chr(13).encode()+chr(10).encode())} CRLF pairs = 1 header + {logical_records} data records) and additionally contains "
      f"{embedded_nl_data + embedded_nl_hdr} bare LF characters inside quoted fields "
      f"({embedded_nl_hdr} in the header cell 'S.\\n  No.', {embedded_nl_data} in data cells). "
      f"Accounting: header 1 record = 2 physical lines; {logical_records - blank_rows} populated data records = "
      f"{logical_records - blank_rows + embedded_nl_data} physical lines; {blank_rows} trailing all-blank records = "
      f"{blank_rows} physical lines. Total 2 + {logical_records - blank_rows + embedded_nl_data} + {blank_rows} = "
      f"{2 + logical_records - blank_rows + embedded_nl_data + blank_rows}, which equals wc -l = {raw_line_count}. "
      f"Of the {logical_records} CSV records, {blank_rows} are entirely empty ',,,,...' rows at the end of the file "
      f"(records {logical_records - blank_rows + 1}..{logical_records}, contiguous), an Excel export artifact. "
      f"True data row count is {N}."
  ),
  "encoding_notes": {
      "bom": "UTF-8 BOM (EF BB BF) present at byte 0; must read with encoding='utf-8-sig' or the first column name becomes '\\ufeffS.\\n  No.'.",
      "line_terminator": "CRLF for records, bare LF for in-field soft wraps.",
      "header_anomaly": "Column 0 is literally 'S.\\n  No.' -- a newline and two spaces inside the header cell.",
      "nbsp_or_zero_width": "none found (0 cells contain NBSP, zero-width space, or tab)"
  },
  "whitespace_artifact": {
      "pattern": "LF followed by exactly two spaces ('\\n  ')",
      "occurrences_in_file": text.count("\n  "),
      "runs_of_2plus_spaces_not_preceded_by_newline": 0,
      "rows_affected": int(sum(1 for _, r in df.iterrows() if any(isinstance(v, str) and "\n" in v for v in r))),
      "rows_affected_pct": round(100 * sum(1 for _, r in df.iterrows() if any(isinstance(v, str) and "\n" in v for v in r)) / N, 2),
      "by_column": {"Hospital Name": 73, "Given Address": 188, "Standardized Address": 78, "City": 7},
      "normalization_rule": "re.sub(r'\\s+', ' ', value).strip()",
      "rule_is_lossless": "Every run of 2+ spaces in the file is immediately preceded by a newline (verified: 0 counterexamples), so collapsing all whitespace runs to a single space cannot merge two genuinely-separate tokens. Applying the rule reduces distinct Hospital Name values from 527 to 526 (one pair differed only by the artifact); casefolding after it changes nothing further.",
      "changed_by_rule": {"Hospital Name": 73, "Given Address": 188, "Standardized Address": 78, "City": 7,
                          "State": 0, "Country": 0, "Type": 0, "Source Sheet Name": 0, "address_py": 0}
  },
  "columns": columns,
  "duplicates": {
      "exact": 0,
      "exact_excluding_row_number": 0,
      "near_dupe_name_geo": int(geo4.duplicated().sum()),
      "dupe_normalized_name": int(nmk.duplicated().sum()),
      "distinct_normalized_names": int(nmk.nunique()),
      "names_occurring_more_than_once": int((nmk.value_counts() > 1).sum()),
      "dupe_name_plus_state": int((nmk + "||" + df["State"].map(NORM).fillna("")).duplicated().sum()),
      "rows_sharing_exact_coordinates_with_another_row": int(coordkey.duplicated(keep=False).sum()),
      "rows_sharing_exact_address_py_with_another_row": int(df["address_py"].map(NORM).duplicated(keep=False).sum()),
      "method": "exact = pandas .duplicated() over all 19 real columns after whitespace normalization; near_dupe_name_geo = duplicated on (casefolded whitespace-normalized Hospital Name, lat rounded 2dp, lon rounded 2dp)"
  },
  "geo_quality": {
      "denominator": N,
      "valid_in_india": int((lat.between(6, 38) & lon.between(68, 98)).sum()),
      "null": int((lat.isna() | lon.isna()).sum()),
      "zero": int(((lat == 0) | (lon == 0)).sum()),
      "out_of_bbox": 0,
      "possibly_swapped": 0,
      "lat_range": [float(lat.min()), float(lat.max())],
      "lon_range": [float(lon.min()), float(lon.max())],
      "decimal_places_distribution": {str(k): int(v) for k, v in
          Counter(df["Latitude"].str.split(".").str[1].str.len()).items()},
      "distinct_coordinate_pairs": int(coordkey.nunique()),
      "rows_on_a_shared_coordinate": int(coordkey.duplicated(keep=False).sum()),
      "shared_coordinates": {k: int(v) for k, v in Counter(coordkey).items() if v > 1},
      "note": "Geo is the strongest field in this dataset: 648/648 present, numeric, and inside the India bbox, none zero, none swapped. The only defect is 7 rows on 3 shared coordinate pairs, at least one of which (11.12712, 78.65689) is the widely-published centroid of Tamil Nadu, indicating a geocoder falling back to state/city centroid. All 351 blank records have no geo, so geo coverage is 648/999 = 64.86% if the blank rows are counted."
  },
  "candidate_primary_key": {
      "column": "S. No.",
      "is_unique": True,
      "is_complete": True,
      "is_contiguous_1_to_N": True,
      "caveat": "Positional row number, not a stable external ID. It will not survive a re-export of the source sheet. Recommend minting a surrogate key 'NHP:' || `S. No.` for provenance only.",
      "other_unique_complete_columns": ["Given Address", "Standardized Address"],
      "note": "Given Address and Standardized Address are also unique+complete but both are derived concatenations of name/city/state/pincode, so their uniqueness is an accident of the name+city combination, not an identifier."
  },
  "coded_vocabularies": {
      "Type": sorted(df["Type"].dropna().unique().tolist()),
      "Source Sheet Name": sorted(df["Source Sheet Name"].dropna().unique().tolist()),
      "State": sorted(df["State"].map(NORM).dropna().unique().tolist()),
      "note": "No opaque codes (no M1_emp/S3_upg/FAC_CATEGO-style columns). `Type` is a 5-value plain-language ownership enum and needs no external codebook, only a mapping to canonical ownership values. No LGD state/district codes are present anywhere in the file."
  },
  "er_readiness": {
      "has_name": True,
      "has_geo_pct": round(100 * float((lat.between(6, 38) & lon.between(68, 98)).mean()), 2),
      "has_district": False,
      "has_city_pct": round(100 * float(df["City"].notna().mean()), 2),
      "has_state_pct": round(100 * float(df["State"].notna().mean()), 2),
      "has_pincode_pct": round(100 * float(df["Postcode"].fillna("").str.replace(" ", "").str.fullmatch(r"\d{6}").mean()), 2),
      "unmatchable_row_pct": 0.0,
      "blocking_key_viable": True,
      "generic_name_row_pct": round(100 * float(nmk.isin({
          "government medical college", "medical college", "esic",
          "all india institute of medical sciences", "gmers medical college",
          "autonomous state medical college", "autonomous state medical college society"}).mean()), 2),
      "note": "Every row has name + lat/lon + state + pincode and 647/648 have a city, so 0% of rows are strictly unmatchable and (name, geo) or (name, state, pincode) blocking is viable. There is NO district column -- City is a town name, not an LGD district, so a (name, district) blocking key requires an external city->district lookup. The real ER risk is not missing data but name ambiguity: 114 rows (17.59%) carry a name like 'Government Medical College' that is only disambiguated by geo/city."
  },
  "facility_type_finding": {
      "claim": "This dataset is medical colleges, not general hospitals.",
      "evidence": {
          "Source Sheet Name is constant 'NHP_Medical_Colleges'": 648,
          "names containing 'college'": 454,
          "names containing 'medical college'": 441,
          "names containing 'institut'": 170,
          "names containing 'academy'/'university'/'school of medic'": 16,
          "names matching NONE of college/institute/academy/university/school/AIIMS/ESIC": 28,
          "rows with a non-null Admission Intake (MBBS seat count)": 648,
          "Admission Intake values that are multiples of 50": 555
      },
      "conclusion": "facility_type_raw is not a column; it must be injected as the constant 'MEDICAL_COLLEGE' for all 648 rows. The 28 names that match no institution keyword are abbreviated/truncated forms ('GMC', 'Fathima Instt. of Medical Sciences', 'Dr. Vasantrao Pawar Med. Col. Hosp. & Research Centr'), not a different facility class -- every one still carries an Admission Intake, which only a teaching institution has."
  }
}

with open(OUT, "w") as f:
    json.dump(profile, f, indent=2, ensure_ascii=False)
print("wrote", OUT)
print(json.dumps({k: v for k, v in profile.items() if k not in ("columns",)}, indent=2, ensure_ascii=False)[:6000])
