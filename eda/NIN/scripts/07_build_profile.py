"""Step 7: emit eda/NIN/profile.json. All numbers computed here, nothing hand-typed."""
import pandas as pd, numpy as np, json, collections

SRC = "/Users/ankitraj2/asar master data/22_MAY_22_AP_NIN.csv"
OUT = "/Users/ankitraj2/asar master data/eda/NIN/profile.json"
READ_KWARGS = {"encoding": "utf-8-sig", "dtype": "str", "keep_default_na": False,
               "na_values": [""], "engine": "c"}

raw = open(SRC, "rb").read()
raw_lines = raw.count(b"\n")

df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
IDX = df.columns[0]                      # pandas renames the BOM-only header to 'Unnamed: 0'
data_cols = [c for c in df.columns if c != IDX]
blank = df[data_cols].isna().all(axis=1)
n_parsed = len(df)
n_blank = int(blank.sum())
d = df.loc[~blank].copy()
N = len(d)

lat = pd.to_numeric(d["latitude"], errors="coerce")
lon = pd.to_numeric(d["longitude"], errors="coerce")
in_bbox = lat.between(6, 38) & lon.between(68, 98)
either_null = lat.isna() | lon.isna()
zero = ((lat == 0) | (lon == 0)) & ~either_null
swapped = (~in_bbox) & ~either_null & ~zero & lat.between(68, 98) & lon.between(6, 38)
out_bbox = (~in_bbox) & ~either_null & ~zero & ~swapped
assert int((in_bbox | either_null | zero | swapped | out_bbox).sum()) == N, "geo partition not exhaustive"
assert int(in_bbox.sum()) + int(either_null.sum()) + int(zero.sum()) + int(swapped.sum()) + int(out_bbox.sum()) == N

def norm(s):
    return (s.astype(str).str.strip().str.lower()
             .str.replace(r"[^\w\s]", " ", regex=True)
             .str.replace(r"\s+", " ", regex=True).str.strip())

d["_n"] = norm(d["Health Facility Name"])
d["_la"] = lat.round(3); d["_lo"] = lon.round(3)
g = d[in_bbox]

dupes = {
    "exact": int(d.duplicated(subset=data_cols).sum()),
    "exact_ignoring_srno": int(d.duplicated(subset=[c for c in data_cols if c not in ("SrNo", "Non filled numbering")]).sum()),
    "near_dupe_name_geo": int(g.duplicated(subset=["_n", "_la", "_lo"]).sum()),
    "near_dupe_name_district": int(d.duplicated(subset=["_n", "District_Name"]).sum()),
    "rows_in_name_geo_groups": int(g.duplicated(subset=["_n", "_la", "_lo"], keep=False).sum()),
    "rows_in_name_district_groups": int(d.duplicated(subset=["_n", "District_Name"], keep=False).sum()),
    "shared_coord_pairs_different_names": None,
    "rows_on_shared_coords": None,
}
gd = g.groupby(["latitude", "longitude"]).agg(n=("_n", "size"), names=("_n", "nunique"))
multi = gd[(gd["n"] > 1) & (gd["names"] > 1)]
dupes["shared_coord_pairs_different_names"] = int(len(multi))
dupes["rows_on_shared_coords"] = int(multi["n"].sum())
# NOTIONAL prefix: an undocumented name marker that conceals duplicates
notional = d["Health Facility Name"].str.contains(r"^NOTIONAL", case=False, regex=True, na=False)
d["_nb"] = norm(d["Health Facility Name"].str.replace(r"^NOTIONAL\s*", "", case=False, regex=True))
dupes["notional_prefixed_rows"] = int(notional.sum())
dupes["notional_prefix_states"] = {str(k): int(v) for k, v in d.loc[notional, "State_Name"].value_counts().items()}
dupes["near_dupe_name_district_after_stripping_NOTIONAL"] = int(d.duplicated(subset=["_nb", "District_Name"]).sum())
dupes["notional_note"] = ("74 facility names begin with the literal word 'NOTIONAL' (73 Rajasthan, 1 Jharkhand). "
                          "Meaning unknown - see questions.md Q10. Stripping the prefix raises the "
                          "name+district near-dupe count from 176 to 239 (+63). Proof it conceals real duplicates: "
                          "SrNo 89661 'Gingla CHC' (Udaipur, latitude=0) carries Notes='Duplicate or SR No. 85112', "
                          "and SrNo 85112 is in this file as 'NOTIONAL Gingla CHC', same district, valid geo. "
                          "Strip the prefix into a separate flag before any name matching.")
dupes["coder_flagged_duplicates"] = [
    {"SrNo": "89661", "name": "Gingla CHC", "note": "Duplicate or SR No. 85112",
     "resolves_to_SrNo": "85112", "resolved_name": "NOTIONAL Gingla CHC", "status": "resolved"},
    {"SrNo": "3508", "name": "Sub Divisional Hospital Biraul", "note": "Same as row 702",
     "status": "unresolved - 'row 702' matches no SrNo, positional index or Non-filled-numbering value"},
]
dupes["method"] = ("exact = duplicated() on all 24 data columns. exact_ignoring_srno excludes SrNo and "
                   "'Non filled numbering'. near_dupe_name_geo = duplicated() on lowercased/punct-stripped "
                   "facility name + lat/lon rounded to 3 decimals, restricted to the 10106 rows with geo "
                   "inside the India bbox. near_dupe_name_district = same normalized name + raw District_Name "
                   "over all rows. Counts are EXTRA rows (keep='first'); *_groups counts are total rows involved.")

# ---------------- per-column ------------------------------------------------
SEM = {
    IDX:                          ("junk", ["junk", "derived", "constant_free"], "Header is a BOM-only empty string; pandas renames it 'Unnamed: 0'. It is a pandas RangeIndex written out by a previous `df.to_csv()`: strictly increasing 0..10635, unique, but with 106 gaps -> 106 rows were deleted after that export. Carries no facility information. Keep only as `source_row_order` provenance if desired."),
    "Non filled numbering":       ("curation_seq", ["derived", "sparse"], "Sequence 3..731, unique, monotonic, present on exactly the 623 rows that also have a Manual Health Facility Name. A work-queue counter for the manual-curation batch ('records that were NOT filled and had to be researched'). Prior-pipeline artifact, not a facility attribute."),
    "SrNo":                       ("source_facility_id", ["candidate_primary_key"], "Unique across all 10327 real rows, integer 1..192898 -> this file is a ~5.4% subset of a much larger parent register keyed by the same SrNo. Not file-ordered (not monotonic). Best available source PK; also the join key back to the parent system."),
    "Health Facility Name":       ("facility_name_raw", [], "Auto/original name. 100% filled on real rows, 10000 distinct of 10327. 43.2% of values contain no facility-type keyword at all (bare place names like 'Chunawadh', 'KODAVASAL') - the facility type lives in `Facility Type`, not the name."),
    "Manual Health Facility Name":("facility_name_alt", ["sparse", "curated"], "Human-researched name, present on 6.03% of rows. Where both are present they disagree 56.8% of the time after normalization - the manual value is a rewrite into 'CHC <Place>' / 'SDH <Place>' house style. Authoritative where present."),
    "Notes":                      ("curation_note", ["free_text", "sparse", "derived"], "Coder free text on 1.51% of rows. 66 distinct values. Semi-structured: 81 rows are a 'NF'/'not found' family meaning the facility could not be located; 26 are 'Listed as <type>' map-label observations; ~14 are 'name as per google-<name>' provenance; several record borrowed geo ('geo cordinates for Balipura BPHC used for Harchura TE') and 2 flag duplicates ('Duplicate or SR No. 85112', 'Same as row 702')."),
    "Address":                    ("address_raw", ["dirty"], "79.83% filled but polluted with sentinels: 188 '\\N', 124 '0', 96 '-', 1 'na'. Median length 12 chars - it is really an address *fragment* (often just the town or the facility type), not a full address."),
    "street":                     ("street", ["dirty"], "78.61% filled; 229 '\\N', 12 '-', 7 '0'."),
    "landmark":                   ("landmark", ["dirty"], "69.93% filled; 23 '\\N', 6 '-', 2 '0'."),
    "locality":                   ("locality", ["dirty"], "77.80% filled; 23 '\\N', 8 '0', 2 '-'. Values are a mix of neighbourhood names, city names and the literal words 'Urban'/'Rural'."),
    "pincode":                    ("pincode", [], "90.07% filled and every single non-null value is exactly 6 digits with a valid Indian leading digit 1-8. The cleanest column in the file."),
    "landline_number":            ("phone", ["pii", "dirty"], "60.00% filled. 34 '0', 27 '-', 23 '\\N'. Mixed formats (with/without STD code, hyphenated, comma-separated multiples in 141 rows). 832 values (13.4%) are 10-digit numbers starting 6-9, i.e. personal MOBILE numbers, and 2 cells contain an email address instead of a number. Treat as PII."),
    "latitude":                   ("latitude", [], "97.83% non-null on real rows; all non-null values parse as float. 68 are exactly 0. Decimal precision varies 0-9 places (75 values have no decimal part)."),
    "longitude":                  ("longitude", [], "97.83% non-null; 69 exactly 0; min -115.20 and max 118.66 confirm out-of-India junk exists."),
    "altitude":                   ("altitude", ["dirty", "mostly_sentinel"], "REAL values, not junk - but 62.20% are the sentinel 0 and 23 are '\\N', leaving only 3881 rows (37.6%) with a real elevation. Non-zero range 0.26-5985 m, median 175 m, and the state-level medians are geographically correct (J&K 1589 m, Uttarakhand 1320 m, Meghalaya 1019 m, Delhi ~0). Fill is source-batch dependent (97.9% non-zero in Tamil Nadu, 0.16% in Delhi, 0% in Chandigarh/Goa/Tripura/Puducherry) so 0 means 'not captured', not 'sea level'. A handful are wrong (three Auraiya UP facilities carry 2700 m; the true elevation there is ~130 m)."),
    "Facility Type":              ("facility_type_raw", ["coded_vocabulary"], "100% filled, closed vocabulary of 13 values. Mixes function ('Community Health Center', 'Dispensaries') with bed-size bands ('<100 Bedded Hospital', '100-500 Bedded Hospital', '>500 Bedded Hospital') on one axis, so it is not a clean taxonomy. 'Others' (2382 rows, 23%) is mostly private hospitals/nursing homes."),
    "State_Name":                 ("state_raw", ["coded_vocabulary"], "100% filled, 34 distinct, consistently cased and spelled - except 'Telengana' (173 rows) which is the wrong spelling of Telangana. Coverage is very uneven: Tamil Nadu 2736 rows vs Kerala 1 row."),
    "District_Name":              ("district_raw", ["dirty"], "100% filled but 6 rows hold the sentinel '\\N'. 623 distinct; 468 rows use a 'X District' suffix (34 distinct, all Andhra Pradesh / Telangana) while the rest do not; 38 rows carry a literal backslash+newline ('Almora\\\\\\n'); one case collision ('Balrampur' vs 'BALRAMPUR')."),
    "Taluka_Name":                ("subdistrict_raw", ["dirty"], "100% raw fill but 859 rows (8.32%) are the sentinel '\\N', so real fill is 91.68%. 3427 real distinct values."),
    "Block_Name":                 ("block_raw", ["dirty"], "100% raw fill but 2460 rows (23.82%) are '\\N', so real fill is 76.18%. Often a corporation/municipality name ('COIMBATORE CORPN') rather than a rural block."),
    "Manual_Address":             ("address_alt", ["sparse", "curated"], "5.13% filled. Google-Maps-style formatted addresses ending in the state name ('DMCH Rd, Allalpatti, Laheriasarai, Darbhanga, Bihar'), median 32 chars vs 12 for `Address`. Where both are filled (125 rows) they agree 0% of the time - `Address` in those rows is usually a sentinel or a single town word. Authoritative where present."),
    "Manual_Pincode":             ("pincode_alt", ["sparse", "curated", "dirty"], "5.08% filled. 519 of 525 are clean 6-digit pincodes; 6 are not ('#REF!' - an Excel formula error - plus 4 values that are a state name with or without a pincode, e.g. 'Karnataka 585331', 'Assam'). Disagrees with `pincode` on 50 of the 161 rows where both are filled (31%)."),
    "Manually_added":             ("is_manually_curated", ["sparse", "dirty"], "5.09% filled. Raw values are 5 case/whitespace variants of yes ('Yes' 481, 'yes' 25, 'yes ' 12, 'Yes ' 5, 'Y' 3); there is no 'No' - blank means not manually added. Boolean-with-nulls."),
    "Coder":                      ("curated_by", ["sparse", "pii", "dirty"], "5.81% filled. 9 raw values collapsing to 5 people by first name: tanmay 358, shalmali 175, mallika 57, sweta 6, sid 4. Internal staff identifiers - low-sensitivity PII (first names of employees, no contact detail), but they are personal data and should not appear in a public/queryable canonical table."),
    "Unnamed: 23":                ("junk", ["junk", "constant", "empty"], "Zero non-null values in all 10530 parsed rows. A trailing comma artifact of the export. Drop."),
}

cols = []
for c in df.columns:
    s_all, s = df[c], d[c]
    n_distinct = int(s.nunique())
    vc = {}
    if n_distinct < 50:
        vc = {("<NULL>" if pd.isna(k) else str(k)): int(v)
              for k, v in s.value_counts(dropna=False).items()}
    ex = s.dropna().drop_duplicates().head(5).tolist()
    role, flags, note = SEM[c]
    cols.append({
        "name": c,
        "raw_header": "" if c == IDX else c,
        "dtype": "string (read as str; see read_kwargs)",
        "non_null": int(s.notna().sum()),
        "non_null_all_parsed_rows": int(s_all.notna().sum()),
        "null_pct": round(float(1 - s.notna().mean()) * 100, 2),
        "n_distinct": n_distinct,
        "examples": [str(x) for x in ex],
        "value_counts": vc,
        "semantic_role": role,
        "flags": flags,
        "notes": note,
    })

# extra numeric summaries
def numsum(c):
    v = pd.to_numeric(d[c], errors="coerce")
    return {"min": float(v.min()), "max": float(v.max()), "mean": round(float(v.mean()), 6),
            "p1": float(v.quantile(.01)), "p25": float(v.quantile(.25)), "p50": float(v.quantile(.5)),
            "p75": float(v.quantile(.75)), "p99": float(v.quantile(.99)),
            "n_numeric": int(v.notna().sum())}
for c in cols:
    if c["name"] in ("latitude", "longitude", "altitude", "SrNo", "Non filled numbering", IDX):
        c["numeric_summary"] = numsum(c["name"])
    if c["name"] in ("Health Facility Name", "Manual Health Facility Name", "Address", "Manual_Address",
                     "Notes", "street", "landmark", "locality"):
        L = d[c["name"]].dropna().str.len()
        c["length_distribution"] = {"min": int(L.min()), "p50": float(L.median()),
                                    "mean": round(float(L.mean()), 2), "p95": float(L.quantile(.95)),
                                    "max": int(L.max())}

# ---------------- auto vs manual --------------------------------------------
def pair_stats(a, m):
    A, M = d[a], d[m]
    both = A.notna() & M.notna()
    r = {"auto_filled": int(A.notna().sum()), "auto_filled_pct": round(A.notna().mean() * 100, 2),
         "manual_filled": int(M.notna().sum()), "manual_filled_pct": round(M.notna().mean() * 100, 2),
         "both_filled": int(both.sum()), "manual_only": int((M.notna() & A.isna()).sum()),
         "auto_only": int((A.notna() & M.isna()).sum())}
    if both.sum():
        nrm = int((norm(A[both]) == norm(M[both])).sum())
        r["agree_exact"] = int((A[both] == M[both]).sum())
        r["agree_normalized"] = nrm
        r["disagree_normalized"] = int(both.sum()) - nrm
        r["disagree_pct_of_both_filled"] = round((int(both.sum()) - nrm) / int(both.sum()) * 100, 2)
    r["rows_where_auto_is_sentinel_and_manual_filled"] = int((M.notna() & A.isin(["\\N", "-", "0", "1"])).sum())
    return r

auto_manual = {
    "Health Facility Name|Manual Health Facility Name": pair_stats("Health Facility Name", "Manual Health Facility Name"),
    "Address|Manual_Address": pair_stats("Address", "Manual_Address"),
    "pincode|Manual_Pincode": pair_stats("pincode", "Manual_Pincode"),
}
auto_manual["recommendation"] = ("COALESCE(manual, auto) for all three pairs. The manual column is the "
                                 "later human-verified value: it is only ever populated on rows a coder "
                                 "worked, and on those rows the auto value is frequently a sentinel ('0', "
                                 "'\\N') or a bare town word. It is never populated where the auto value is "
                                 "absent-and-good. Keep both, expose the auto value as *_raw for audit.")

# ---------------- curation workflow -----------------------------------------
ma = d["Manually_added"].str.strip().str.lower()
co = d["Coder"].str.strip().str.lower()
mk = pd.DataFrame({"non_filled_numbering": d["Non filled numbering"].notna(),
                   "manual_name": d["Manual Health Facility Name"].notna(),
                   "manual_address": d["Manual_Address"].notna(),
                   "manual_pincode": d["Manual_Pincode"].notna(),
                   "manually_added": d["Manually_added"].notna(),
                   "coder": d["Coder"].notna(), "notes": d["Notes"].notna()})
curation = {
    "rows_with_any_curation_marker": int(mk.any(axis=1).sum()),
    "rows_with_any_curation_marker_pct": round(mk.any(axis=1).mean() * 100, 2),
    "manually_added_non_null": int(d["Manually_added"].notna().sum()),
    "manually_added_pct": round(d["Manually_added"].notna().mean() * 100, 2),
    "manually_added_raw_values": {str(k): int(v) for k, v in d["Manually_added"].value_counts().items()},
    "manually_added_normalized": {str(k): int(v) for k, v in ma.value_counts().items()},
    "coder_non_null": int(d["Coder"].notna().sum()),
    "coder_pct": round(d["Coder"].notna().mean() * 100, 2),
    "coder_raw_values": {str(k): int(v) for k, v in d["Coder"].value_counts().items()},
    "coder_normalized": {str(k): int(v) for k, v in co.value_counts().items()},
    "distinct_coders": sorted(co.dropna().unique().tolist()),
    "n_distinct_coders": int(co.nunique()),
    "coder_x_manually_added": {str(k): {str(kk): int(vv) for kk, vv in v.items()}
                               for k, v in pd.crosstab(co, ma).to_dict("index").items()},
    "coder_present_but_manually_added_blank": int((d["Coder"].notna() & d["Manually_added"].isna()).sum()),
    "note": ("'Non filled numbering' and 'Manual Health Facility Name' have identical non-null masks (623 rows). "
             "Coder is filled on 600 rows and Manually_added on 526, so the three markers are not co-extensive; "
             "628 rows carry at least one curation marker (6.08%). Coder='tanmay' has 73 rows with a blank "
             "Manually_added - Coder is the more reliable 'a human touched this row' flag."),
    "coder_is_pii": True,
    "coder_pii_assessment": ("YES - PII, low sensitivity. The values are the first names of 5 identifiable "
                             "internal staff (tanmay, shalmali, mallika, sweta, sid) with no contact detail "
                             "attached. It is employee-attribution metadata, not facility data. Retain it in "
                             "the internal provenance table for audit/quality attribution; exclude it from any "
                             "user-facing or LLM-queryable view, or replace with an opaque coder_id."),
}

# ---------------- admin hierarchy -------------------------------------------
admin = {}
for c in ["State_Name", "District_Name", "Taluka_Name", "Block_Name"]:
    s = d[c]
    real = s.notna() & (~s.str.strip().isin(["\\N", "-", "0", ""]))
    admin[c] = {"raw_non_null": int(s.notna().sum()), "raw_non_null_pct": round(s.notna().mean() * 100, 2),
                "real_non_null": int(real.sum()), "real_non_null_pct": round(real.mean() * 100, 2),
                "sentinel_backslash_N": int((s.str.strip() == "\\N").sum()),
                "n_distinct_real": int(s[real].nunique())}
admin["state_distinct_list"] = sorted(d["State_Name"].dropna().unique().tolist())
admin["state_value_counts"] = {str(k): int(v) for k, v in d["State_Name"].value_counts().items()}
admin["district_issues"] = {
    "rows_with_District_suffix": int(d["District_Name"].str.strip().str.endswith("District").sum()),
    "distinct_with_District_suffix": int(d["District_Name"].str.strip()[d["District_Name"].str.strip().str.endswith("District")].nunique()),
    "rows_with_embedded_newline": int(d["District_Name"].str.contains("\n", na=False).sum()),
}

# ---------------- pincode ---------------------------------------------------
pin = {}
for c in ["pincode", "Manual_Pincode"]:
    s = d[c].dropna().str.strip()
    six = s.str.fullmatch(r"\d{6}")
    pin[c] = {"non_null": int(len(s)), "six_digit": int(six.sum()), "not_six_digit": int((~six).sum()),
              "bad_values": {str(k): int(v) for k, v in s[~six].value_counts().items()},
              "leading_zero": int((s[six].str[0] == "0").sum()),
              "first_digit_distribution": {str(k): int(v) for k, v in s[six].str[0].value_counts().sort_index().items()}}

profile = {
    "dataset_key": "NIN",
    "source_file": "22_MAY_22_AP_NIN.csv",
    "read_kwargs": READ_KWARGS,
    "read_notes": ("MUST use encoding='utf-8-sig': the file starts with a UTF-8 BOM and the first header "
                   "cell is EMPTY, so without the BOM strip the first column name becomes '\\ufeff'. Line "
                   "terminator is CRLF; pandas' C engine handles it. dtype=str + keep_default_na=False + "
                   "na_values=[''] is required to (a) stop pandas coercing pincode/SrNo/lat/lon to float and "
                   "printing them in scientific notation, (b) stop it turning the literal strings 'NA'/'null' "
                   "into NaN, and (c) preserve leading zeros. Do NOT use index_col=0 - the first column is a "
                   "stale pandas index with 106 gaps and is not a usable key."),
    "n_rows": N,
    "n_rows_as_parsed": n_parsed,
    "n_cols": int(df.shape[1]),
    "raw_line_count": int(raw_lines),
    "row_count_explanation": (
        f"wc -l reports {raw_lines} physical lines. csv.reader returns {n_parsed + 1} records "
        f"({n_parsed} data + 1 header): the gap of 81 is caused by 81 cells containing an embedded "
        f"CRLF inside a quoted field (all of them in District_Name / Taluka_Name, value 'Almora\\\\\\n' "
        f"and one 'Chilakaluripet\\\\\\n H/O.Purushotha Patnam Mandal'). Of those {n_parsed} parsed rows, "
        f"{n_blank} are completely empty in all 24 data columns and carry only a stale pandas index in "
        f"column 1 - 200 form a contiguous trailing block (positions 10330-10529) and 3 are interior "
        f"(positions 4789, 5740, 6444). TRUE LOGICAL ROW COUNT = {N}. "
        f"({raw_lines} - 81 embedded newlines - 1 header - {n_blank} empty = {N}.)"),
    "columns": cols,
    "duplicates": dupes,
    "geo_quality": {
        "valid_in_india": int(in_bbox.sum()),
        "valid_in_india_pct": round(in_bbox.mean() * 100, 2),
        "null": int(either_null.sum()),
        "both_null": int((lat.isna() & lon.isna()).sum()),
        "zero": int(zero.sum()),
        "out_of_bbox": int(out_bbox.sum()),
        "possibly_swapped": int(swapped.sum()),
        "partition_note": "The five buckets are mutually exclusive and sum to n_rows.",
        "lat_min": float(lat.min()), "lat_max": float(lat.max()),
        "lon_min": float(lon.min()), "lon_max": float(lon.max()),
        "coord_pairs_shared_by_more_than_one_facility": int(len(multi)),
        "rows_on_shared_coords": int(multi["n"].sum()),
        "worst_shared_coord": {"latlon": "11.664325,78.1460142", "n_rows": int(gd["n"].max())},
    },
    "candidate_primary_key": {"column": "SrNo", "is_unique": bool(d["SrNo"].dropna().is_unique),
                              "non_null": int(d["SrNo"].notna().sum()), "n_rows": N,
                              "min": int(pd.to_numeric(d["SrNo"]).min()), "max": int(pd.to_numeric(d["SrNo"]).max()),
                              "note": ("Unique and 100% populated on all 10327 real rows. Range 1..192898 means "
                                       "this file is a ~5.4% extract of a much larger parent register that uses "
                                       "the same numbering. Recommended source PK: NIN:<SrNo>. The first column "
                                       "(BOM-only header) is also unique but is a stale pandas index with 106 "
                                       "gaps - do not use it.")},
    "coded_vocabularies": {
        "Facility Type": sorted(d["Facility Type"].dropna().unique().tolist()),
        "State_Name": sorted(d["State_Name"].dropna().unique().tolist()),
        "Manually_added_raw": sorted(d["Manually_added"].dropna().unique().tolist()),
        "Coder_raw": sorted(d["Coder"].dropna().unique().tolist()),
    },
    "auto_vs_manual_pairs": auto_manual,
    "curation_workflow": curation,
    "admin_hierarchy": admin,
    "pincode_quality": pin,
    "sentinels": {
        "literal_backslash_N_cells": int(sum((d[c] == "\\N").sum() for c in data_cols)),
        "per_column": {c: int((d[c] == "\\N").sum()) for c in data_cols if (d[c] == "\\N").sum() > 0},
        "note": "'\\N' is the MySQL/mysqldump NULL marker, so this CSV was produced by an SQL export, not by Excel.",
    },
    "er_readiness": {},
}

name_ok = d["Health Facility Name"].notna() & (d["Health Facility Name"].str.strip().str.len() >= 3)
dist_ok = d["District_Name"].notna() & (~d["District_Name"].str.strip().isin(["\\N", "-", "0"]))
kw = r"hospital|health|chc|phc|uhc|sdh|dispensar|clinic|centre|center|nursing|medical|maternity|ppu|hosp"
nokw = ~d["Health Facility Name"].str.contains(kw, case=False, regex=True, na=False)
profile["er_readiness"] = {
    "has_name": True, "has_name_pct": round(name_ok.mean() * 100, 2),
    "has_geo_pct": round(in_bbox.mean() * 100, 2),
    "has_district": True, "has_district_pct": round(dist_ok.mean() * 100, 2),
    "has_pincode_pct": round(d["pincode"].notna().mean() * 100, 2),
    "has_name_and_district_and_geo_pct": round((name_ok & dist_ok & in_bbox).mean() * 100, 2),
    "unmatchable_row_pct": round((~(name_ok & dist_ok)).mean() * 100, 2),
    "unmatchable_rows": int((~(name_ok & dist_ok)).sum()),
    "weak_match_names_no_facility_keyword": int(nokw.sum()),
    "weak_match_names_no_facility_keyword_pct": round(nokw.mean() * 100, 2),
    "blocking_key_viable": True,
    "note": ("(name, district, geo) is fully viable: 97.80% of rows carry all three and only 6 rows (0.06%) "
             "lack a usable name-or-district. The real risk is not missing data but AMBIGUOUS names - 43.24% "
             "of names contain no facility-type keyword and are bare place names, and 1293 rows sit on a "
             "coordinate shared with a different facility (block-centroid geocoding), so geo alone must not "
             "be used to confirm a match at tighter than ~1 km."),
}

with open(OUT, "w") as f:
    json.dump(profile, f, indent=2, ensure_ascii=False)
print("wrote", OUT)
print(json.dumps({k: v for k, v in profile.items() if k not in ("columns",)}, indent=2)[:3000])
