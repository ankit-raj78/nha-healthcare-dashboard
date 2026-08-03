"""NHA EDA step 11: assemble eda/NHA/profile.json from the intermediates."""
import json
import re

import pandas as pd

BASE = "eda/NHA/"
INT = "eda/NHA/scripts/intermediate/"
col = json.load(open(INT + "_col_profile.json"))
fam = json.load(open(INT + "_families.json"))
spec = json.load(open(INT + "_specialties.json"))
cb = json.load(open(INT + "_codebook.json"))
dge = json.load(open(INT + "_dupes_geo_er.json"))
anat = json.load(open(INT + "_dupe_anatomy.json"))
x247 = json.load(open(INT + "_24x7.json"))
gaps = json.load(open(INT + "_gaps.json"))
dadj = json.load(open(INT + "_district_adj.json"))

CODEBOOK = {c: v["token"] for c, v in cb["bijection_test"].items()}

# semantic role + flags + notes, decided per column
ROLE = {
 "Facility ID": ("source_facility_id", [],
   "NHA/HFR facility identifier. NOT unique: 62,300 ids repeat over 127,004 rows "
   "(max 220). 93.7% of the repeated groups are a 24/7 yes/no fan-out, not distinct "
   "facilities. 258,756 distinct ids."),
 "hospital_name": ("facility_name_raw", [],
   "Uppercase free text. 23 blank, 426 of length<=3, 129 obvious test/dummy records. "
   "217,163 distinct."),
 "Name verifier": ("record_status", ["derived", "redundant_with:Address verifier",
   "redundant_with:Facility Type verifier", "redundant_with:Ownership verifier"],
   "NOT a person. Traffic-light quality tier Green/Orange/Blue. Byte-identical to the "
   "other three verifier columns on all 323,460 rows."),
 "Address": ("address_raw", [],
   "Machine-assembled single free-text string '<premise>, <locality> <district>, "
   "<State> - <PIN>'. 0 blank. 323,456/323,460 end in '- <6-digit pin>'. No parsed "
   "components exist in this dataset."),
 "Address verifier": ("record_status", ["derived", "redundant_with:Name verifier"],
   "Byte-identical duplicate of Name verifier."),
 "Google Maps Link": (None, ["derived", "redundant_with:Latitude",
   "redundant_with:Longitude"],
   "Not a URL. It is the bare string '<lat>,<lon>'. 0 rows start with http. Agrees with "
   "Latitude/Longitude to 4dp on 323,439/323,440 comparable rows (max deviation 1.1e-14 "
   "deg). Retains the raw pre-cleaning string, so it is useful only as forensic evidence "
   "of the 20 malformed coordinates."),
 "Facility Type": ("facility_type_raw", [],
   "37 clean values, no case/whitespace variants. Dominated by Sub Centre (107,643) and "
   "Hospital (56,799); includes Pharmacy (41,290) and Diagnostic Laboratory (14,865), "
   "which are not care-delivery facilities."),
 "Facility Type verifier": ("record_status", ["derived", "redundant_with:Name verifier"],
   "Byte-identical duplicate of Name verifier."),
 "Ownership": ("facility_ownership_raw", [],
   "3 clean values: Government 178,537 / Private 143,346 / Public-Private-Partnership 1,577."),
 "Ownership verifier": ("record_status", ["derived", "redundant_with:Name verifier"],
   "Byte-identical duplicate of Name verifier."),
 "ABDM Enabled": ("abdm_enabled", [],
   "Clean Yes/No. Yes 74,240 (22.95%)."),
 "Latitude": ("latitude", [],
   "Stored as text; 12 rows unparseable (LTR marks, degree symbols, DMS-style dotted "
   "strings). 40 rows have |lat|>90. 63,594 rows carry 15 decimal places (float64 "
   "round-trip noise)."),
 "Longitude": ("longitude", [],
   "Stored as text; 10 rows unparseable. 41 rows have |lon|>180."),
 "24/7": ("is_24x7", ["unreliable"],
   "UNUSABLE AS-IS. 58,370 facilities (22.56% of distinct ids) carry BOTH yes and no on "
   "different rows of the same Facility ID. This column is the axis of the row fan-out."),
 "State_name": ("state_raw", ["redundant_with:new_state_name"],
   "34 distinct, mixed-case 'and'. Differs from new_state_name only in casing plus "
   "'Andaman and Nicobar' vs 'Andaman And Nicobar Islands' (238 rows)."),
 "District_name": ("district_raw", ["redundant_with:new_district_name"],
   "643 distinct, lowercase. Includes the literal sentinel 'Not Found' (2 rows). "
   "Disagrees with new_district_name on 867 rows."),
 "new_state_name": ("state_raw", [],
   "34 distinct, Title Case. AUTHORITATIVE - it is 1:1 with state_code (LGD)."),
 "state_code": ("state_lgd_code", [],
   "Confirmed LGD state code: 1:1 with new_state_name across all 34 values and matches "
   "the published LGD numbering exactly. Read as float ('35.0') - cast to int. Codes 19 "
   "(West Bengal) and 31 (Lakshadweep) are absent: those states have ZERO rows."),
 "new_district_name": ("district_raw", [],
   "615 distinct, Title Case. Perfectly 1:1 with district_code (615<->615, no district "
   "maps to 2 codes and no code maps to 2 names). Internally consistent but WRONG on the "
   "867 rows where it disagrees with District_name."),
 "district_code": ("district_lgd_code", [],
   "615 distinct, 1:1 with new_district_name. Consistent with LGD district-code ranges "
   "but NOT independently verified against an LGD reference file. Read as float."),
 "merged_specialties": ("specialty_list", [],
   "THE CODEBOOK. Pipe/comma-delimited specialty names. Non-blank on 16,282 rows (5.03%). "
   "26 distinct tokens. Decodes the 25 M*/S*_emp flag columns by exact set-equality."),
}
for c, tok in CODEBOOK.items():
    ROLE[c] = ("specialty_code_empanelled", ["binary_flag"],
               f"Binary 0/1 flag. Decodes to '{tok}' - proven by exact set-equality with "
               f"merged_specialties on all 323,460 rows.")
ROLE["S8_emp"] = ("specialty_code_empanelled", ["binary_flag", "undecoded"],
  "Binary flag stored as '1.0'/BLANK (not 0) - 319,370 blanks. merged_specialties carries "
  "the literal string 'S8', so the upstream decoder failed on this code. Specialty name UNKNOWN.")
ROLE["S9_emp"] = ("specialty_code_empanelled", ["binary_flag", "undecoded"],
  "Binary flag stored as '1.0'/BLANK - 319,837 blanks. merged_specialties carries the "
  "literal string 'S9'. Specialty name UNKNOWN. S9=1 always implies S8=1.")
ROLE["S10_emp"] = ("specialty_code_empanelled", ["binary_flag", "ambiguous"],
  "Binary flag. S10_emp and S11_emp are byte-identical on all rows and their two tokens "
  "('Plastic & reconstructive', 'Burns management') always co-occur, so which column is "
  "which cannot be determined from this dataset. Assigned by ordinal position only.")
ROLE["S11_emp"] = ("specialty_code_empanelled", ["binary_flag", "ambiguous"],
  "See S10_emp - identical column, assignment by ordinal position only.")
ROLE["M10_emp"] = ("specialty_code_empanelled", ["binary_flag", "near_constant"],
  "Binary flag decoding to 'OPD Diagnostic'. Positive on only 4 rows of 323,460.")

out = {
 "dataset_key": "NHA",
 "source_file": "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv",
 "read_kwargs": {
   "filepath_or_buffer": "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv",
   "encoding": "utf-8", "dtype": "str", "keep_default_na": False, "na_filter": False,
   "_comment": ("No BOM (file starts with 'Faci'). No embedded newlines, no Unnamed/index "
                "columns, no trailing empty columns, no thousands separators. Naive "
                "pd.read_csv gives the correct 323460x46 shape but silently coerces "
                "Latitude/Longitude to object and S8_emp/S9_emp to float; read as str and "
                "cast explicitly."),
 },
 "n_rows": 323460, "n_cols": 46, "raw_line_count": 323461,
 "row_count_explanation": (
   "wc -l reports 323461 = 1 header line + 323460 data rows; the file is newline-"
   "terminated. The csv module yields exactly 323460 data records, every one with exactly "
   "46 fields, so there are no embedded newlines and no ragged rows. The brief's stated "
   "323,461 rows is the wc -l count and is one too high."),
 "columns": [],
 "duplicates": {
   "exact": anat and dge["exact_dupes"]["n_fully_duplicated_rows_all46cols"],
   "exact_ignoring_facility_id": dge["exact_dupes"]["n_dupes_ignoring_facility_id"],
   "near_dupe_name_geo": dge["near_dupes"]["name_geo_4dp"]["n_redundant_rows"],
   "near_dupe_name_geo_3dp": dge["near_dupes"]["name_geo_3dp"]["n_redundant_rows"],
   "near_dupe_name_district": dge["near_dupes"]["name_district"]["n_redundant_rows"],
   "duplicated_facility_ids": fam["facility_id"]["n_ids_appearing_more_than_once"],
   "rows_in_duplicated_facility_ids": fam["facility_id"]["n_rows_involved_in_dup_ids"],
   "pct_redundant_name_geo": dge["near_dupes"]["name_geo_4dp"]["pct_redundant"],
   "method": (
     "exact = pandas .duplicated() over all 46 columns, full population. near_dupe = "
     "exact-match key on normalised name (NFKD->ascii, lowercase, non-alnum->space, "
     "collapse whitespace) + lat/lon rounded to 4 decimals (~11 m). NO SAMPLING - all "
     "323,460 rows. This is a blocking-key count, not fuzzy string matching, so it is a "
     "LOWER BOUND on true duplication."),
   "dominant_cause": (
     "93.69% of the 62,300 repeated Facility IDs are groups where 24/7 takes both 'yes' "
     "and 'no'. Dropping the 24/7 column and de-duplicating collapses 323,460 rows to "
     "261,905 (61,555 rows eliminated), after which only 3,146 ids remain repeated."),
 },
 "geo_quality": {
   "valid_in_india": dge["geo_detail"]["valid_in_india"],
   "null": dge["geo_detail"]["null_either"],
   "zero": dge["geo_detail"]["zero_zero"],
   "out_of_bbox": dge["geo_detail"]["out_of_bbox_nonnull_nonzero"],
   "possibly_swapped": dge["geo_detail"]["possibly_swapped"],
   "unparseable_latitude": fam["geo"]["lat_unparseable_nonblank"],
   "unparseable_longitude": fam["geo"]["lon_unparseable_nonblank"],
   "abs_lat_gt_90": dge["geo_detail"]["absurd_magnitude"]["n_abs_lat_gt_90"],
   "abs_lon_gt_180": dge["geo_detail"]["absurd_magnitude"]["n_abs_lon_gt_180"],
   "bbox_used": {"lat": [6, 38], "lon": [68, 98]},
   "shared_coordinate_fallback": {
     "n_distinct_coord_pairs": anat["shared_coords"]["n_distinct_coord_pairs"],
     "n_rows_sharing_a_coord_with_another_row":
        dge["near_dupes"]["exact_coord_pair_reuse"]["n_rows_sharing_a_coord_pair"],
     "n_coord_pairs_used_by_ge_50_rows": anat["shared_coords"]["n_pairs_shared_by_ge_50_rows"],
     "n_rows_at_such_coords": anat["shared_coords"]["n_rows_at_a_coord_shared_by_ge_50"],
     "worst": "26.917858,75.801292 is shared by 9,870 rows spanning 28 Rajasthan districts",
     "note": ("51.1% of rows share their exact coordinate pair with at least one other "
              "row. Many are district/city centroid fallbacks, not real facility points."),
   },
   "precision": {
     "n_rows_ge_12_decimals": gaps["coord_precision"]["n_ge_12_decimals"],
     "pct_ge_12_decimals": gaps["coord_precision"]["pct_ge_12_decimals"],
     "n_rows_le_2_decimals": gaps["coord_precision"]["n_le_2_decimals"],
   },
 },
 "candidate_primary_key": {
   "column": "Facility ID", "is_unique": False,
   "n_distinct": fam["facility_id"]["n_distinct"],
   "n_rows": 323460,
   "max_repeat": fam["facility_id"]["max_repeat"],
   "verdict": (
     "Facility ID is NOT a primary key of this file as delivered, but it IS the natural "
     "entity key: 62,298 of the 62,300 repeated-id groups carry the same hospital_name, "
     "and only 1 group spans two states. After collapsing the 24/7 fan-out it identifies "
     "258,756 facilities. Use (Facility ID) as the source entity key and treat the file "
     "as having a broken grain, not colliding ids."),
   "no_alternative_unique_column": True,
 },
 "coded_vocabularies": {
   "_codebook_status": "SOLVED - proven, not inferred",
   "_proof": (
     "For each of the 25 M*/S*_emp columns, the row set {flag==1} is EXACTLY equal to the "
     "row set {token present in merged_specialties} - zero rows in either symmetric "
     "difference, across all 323,460 rows. See scripts/05_codebook_verify.py."),
   "specialty_code_to_name": CODEBOOK,
   "unresolved_codes": {
     "S8": "merged_specialties carries the literal 'S8'; true specialty name unknown",
     "S9": "merged_specialties carries the literal 'S9'; true specialty name unknown",
   },
   "ambiguous_codes": {
     "S10/S11": ("'Plastic & reconstructive' and 'Burns management' - the two columns are "
                 "byte-identical so the S10<->S11 assignment is by ordinal position only"),
   },
   "absent_column": "M9_emp does not exist in the file (M1-M8 and M10 are present)",
   "Facility Type": sorted(json.loads(json.dumps(
     [c for c in col["columns"] if c["name"] == "Facility Type"][0]["value_counts"])).keys()),
   "Ownership": ["Government", "Private", "Public-Private-Partnership"],
   "ABDM Enabled": ["No", "Yes"],
   "24/7": ["no", "yes"],
   "verifier_colour": ["Blue", "Green", "Orange"],
   "state_code_lgd": {k: v[0] for k, v in fam["state_code_to_new_state"].items()},
 },
 "er_readiness": {
   "has_name": True,
   "has_name_pct": dge["er_readiness"]["has_name_pct"],
   "has_geo_pct": dge["er_readiness"]["has_valid_geo_pct"],
   "has_district": True,
   "has_district_pct": dge["er_readiness"]["has_district_pct"],
   "has_name_geo_district_pct": dge["er_readiness"]["has_all_three_pct"],
   "unmatchable_row_pct": dge["er_readiness"]["unmatchable_pct"],
   "blocking_key_viable": True,
   "notes": (
     "name+geo+district blocking is viable on 99.46% of rows. The real risk is not "
     "missing fields, it is FALSE geo precision: 51.1% of rows share an exact coordinate "
     "pair with another row and 6.86% sit on a coordinate shared by >=50 rows, so geo "
     "proximity alone will over-merge. Address is 100% populated and carries a 6-digit "
     "pincode on 323,454 rows - extract it, it is a better second blocking key than "
     "coordinates. No phone/email/website/registration-number column exists."),
 },
 "coverage_warning": {
   "states_with_zero_rows": ["West Bengal (LGD 19)", "Lakshadweep (LGD 31)"],
   "severely_undercounted_states": {
     "Odisha": 11, "Goa": 56, "Meghalaya": 96, "Sikkim": 173, "Manipur": 274,
     "Puducherry": 297, "Andaman And Nicobar Islands": 238, "Ladakh": 237,
     "Tamil Nadu": 2567, "Uttarakhand": 1568,
   },
   "note": ("This dataset is the project spine by volume but it is NOT a complete national "
            "register. Odisha has 11 rows and Tamil Nadu 2,567 against Uttar Pradesh's "
            "62,801. Do not compute national coverage statistics from it."),
 },
 "pii": {
   "columns_containing_pii": [],
   "note": ("No phone, email or dedicated person-name column. The four 'verifier' columns "
            "are colour tiers, not people. However hospital_name contains individual "
            "practitioner names on many rows (e.g. 'DR GAURAV MISHRA', 'DR K K GUPTA'), "
            "which is indirect personal data in a sole-practitioner context."),
 },
}

# --- per-column records -----------------------------------------------------
for c in col["columns"]:
    name = c["name"]
    role, flags, note = ROLE.get(name, ("unknown", [], ""))
    rec = {
      "name": name,
      "dtype": "float64" if name in ("state_code", "district_code", "S8_emp", "S9_emp")
               else ("int64" if (re.fullmatch(r"[MS]\d+_emp", name)
                                 or name == "Facility ID") else "object"),
      "dtype_note": "as produced by naive pd.read_csv; profiled as str",
      "non_null": c["non_null"],
      "null_pct": c["null_pct"],
      "n_distinct": c["n_distinct"],
      "examples": c["examples"],
      "value_counts": c.get("value_counts", {}),
      "semantic_role": role if role else "drop",
      "flags": flags,
      "notes": note,
    }
    if "top_10" in c:
        rec["top_10"] = c["top_10"]
    if "str_len" in c:
        rec["str_len"] = c["str_len"]
    if "numeric" in c:
        rec["numeric"] = {k: v for k, v in c["numeric"].items()
                          if k not in ("unparseable_examples",)}
    if name in CODEBOOK:
        rec["decodes_to"] = CODEBOOK[name]
        rec["n_positive"] = spec["per_column_positive_count"][name]
    out["columns"].append(rec)

assert len(out["columns"]) == 46
json.dump(out, open(BASE + "profile.json", "w"), indent=2, ensure_ascii=False)
print("wrote", BASE + "profile.json", "cols:", len(out["columns"]))
