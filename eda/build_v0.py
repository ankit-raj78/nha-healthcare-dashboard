#!/usr/bin/env python
"""
Build the v0 queryable database from the 10 source CSVs.

v0 = harmonized + deduplicated WITHIN each source, but NO cross-source entity
resolution. One row = one source record. The same real facility may appear in
several sources; `facility` counts are therefore UPPER BOUNDS until Phase 3.

Every ingest rule here traces to a finding in eda/<KEY>/ — see eda/02_PHASE1_FINDINGS.md.
"""
import json
import re
import warnings

import duckdb
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = "/Users/ankitraj2/asar master data/datasets"
DB = "/Users/ankitraj2/asar master data/db/facilities_v0.duckdb"

# --------------------------------------------------------------------------- utils
WS = re.compile(r"\s+")
NON_ALNUM = re.compile(r"[^A-Z0-9 ]")


def norm_text(s):
    if s is None:
        return None
    s = WS.sub(" ", str(s)).strip()
    return s or None


def norm_key(s):
    """Aggressive normalization for joins/blocking."""
    if s is None:
        return None
    s = NON_ALNUM.sub(" ", WS.sub(" ", str(s)).strip().upper())
    return WS.sub(" ", s).strip() or None


# State variants observed across all 10 datasets (eda/*/profile.json).
# Keys must be POST-norm_key form: uppercase, punctuation already stripped to spaces.
STATE_FIX = {
    "ANDAMAN NICOBAR": "ANDAMAN AND NICOBAR ISLANDS",
    "ANDAMAN NICOBAR ISLANDS": "ANDAMAN AND NICOBAR ISLANDS",
    "ANDAMAN AND NICOBAR": "ANDAMAN AND NICOBAR ISLANDS",
    "A N ISLANDS": "ANDAMAN AND NICOBAR ISLANDS",
    "JAMMU KASHMIR": "JAMMU AND KASHMIR",
    "TAMILNADU": "TAMIL NADU",
    "DADRA NAGAR HAVE": "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
    "DADRA NAGAR HAVELI": "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
    "DAMAN DIU": "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
    "THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU": "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
    "ANDRA PRADESH": "ANDHRA PRADESH",
    "CHATTISGARH": "CHHATTISGARH",
    "GUJRAT": "GUJARAT",
    "JAMMU AND KASMIR": "JAMMU AND KASHMIR",
    "JAMMU & KASHMIR": "JAMMU AND KASHMIR",
    "LAKSHWADEEP": "LAKSHADWEEP",
    "TELENGANA": "TELANGANA",
    "UTTTAR PRADESH": "UTTAR PRADESH",
    "UTTARANCHAL": "UTTARAKHAND",
    "ORISSA": "ODISHA",
    "PONDICHERRY": "PUDUCHERRY",
    "DELHI": "NCT OF DELHI",
    "NEW DELHI": "NCT OF DELHI",
    "DADRA & NAGAR HAVELI": "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
    "DADRA AND NAGAR HAVELI": "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
    "DAMAN AND DIU": "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
    "DAMAN & DIU": "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
}


def norm_state(s):
    k = norm_key(s)
    if not k or k in {"NA", "N", "NULL", "0"}:
        return None
    return STATE_FIX.get(k, k)


def to_float(s):
    try:
        v = float(str(s).strip())
        return v
    except Exception:
        return None


CANON = [
    "record_uid", "source_dataset", "source_facility_id",
    "facility_name_raw", "facility_name_norm",
    "address_raw", "state_raw", "state_norm", "district_raw", "district_norm",
    "block_raw", "village_raw", "city", "pincode",
    "latitude", "longitude",
    "facility_type_raw", "facility_ownership_raw",
    "phone", "email",
    "specialty_raw", "specialty_code_system",
    "bed_count", "is_24x7", "abdm_enabled",
    "source_snapshot_date",
]


def frame(df, key, **cols):
    """Assemble a canonical frame from column expressions."""
    out = pd.DataFrame(index=df.index)
    for c in CANON:
        out[c] = None
    for c, v in cols.items():
        out[c] = v
    out["source_dataset"] = key
    out["record_uid"] = [f"{key}:{i}" for i in range(len(df))]
    out["facility_name_norm"] = out["facility_name_raw"].map(norm_key)
    out["state_norm"] = out["state_raw"].map(norm_state)
    out["district_norm"] = out["district_raw"].map(norm_key)
    for c in ("latitude", "longitude", "bed_count"):
        out[c] = out[c].map(to_float) if out[c].notna().any() else None
    for c in CANON:
        if c not in ("latitude", "longitude", "bed_count"):
            out[c] = out[c].map(norm_text) if out[c].notna().any() else None
    return out[CANON]


def rd(fn, **kw):
    kw.setdefault("dtype", str)
    kw.setdefault("keep_default_na", False)
    kw.setdefault("na_values", [""])
    return pd.read_csv(f"{ROOT}/{fn}", **kw)


frames, stats = [], {}


def add(key, df, raw_rows, note=""):
    frames.append(df)
    stats[key] = {"raw_rows": raw_rows, "loaded": len(df), "note": note}
    print(f"  {key:10} {raw_rows:>7} raw -> {len(df):>7} loaded   {note}")


print("Building v0 …")

# ---------------------------------------------------------------------------- NHA
# Grain fix: 62,300 Facility IDs fan out across rows, 93.7% a 24/7 yes/no split.
d = rd("1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv", encoding="utf-8", na_filter=False)
raw = len(d)
d = d.drop_duplicates(subset=[c for c in d.columns if c != "24/7"]).reset_index(drop=True)
add("NHA", frame(
    d, "NHA",
    source_facility_id="NHA:" + d["Facility ID"].astype(str),
    facility_name_raw=d["hospital_name"], address_raw=d["Address"],
    state_raw=d["new_state_name"].where(d["new_state_name"].astype(bool), d["State_name"]),
    district_raw=d["new_district_name"].where(d["new_district_name"].astype(bool), d["District_name"]),
    latitude=d["Latitude"], longitude=d["Longitude"],
    facility_type_raw=d["Facility Type"], facility_ownership_raw=d["Ownership"],
    specialty_raw=d["merged_specialties"], specialty_code_system="PMJAY_MS",
    is_24x7=d["24/7"], abdm_enabled=d["ABDM Enabled"],
    source_snapshot_date="2025-03-01",
), raw, "collapsed 24/7 fan-out")

# -------------------------------------------------------------------------- PMJAY
d = rd("18_MAY_23_SRK_PMJAY_validated_and_standardized.csv", encoding="utf-8-sig")
raw = len(d)
add("PMJAY", frame(
    d, "PMJAY",
    source_facility_id="PMJAY:" + d["Sr No"].astype(str),
    facility_name_raw=d["Manual Hospital Name"].fillna(d["Hospital Name"]),
    address_raw=d["Manual Hospital Address"].fillna(d["Hospital Address"]),
    state_raw=d["Manual state"], district_raw=d["Manual District"],
    city=d["City"], pincode=d["Zipcode"].fillna(d["pincode_py"]),
    latitude=d["API Latitude"], longitude=d["API Longitude"],
    facility_ownership_raw=d["Hospital Type"],
    phone=d["Hospital Contact"], email=d["Hospital E-Mail"],
    specialty_raw=d["Specialities Empanelled"], specialty_code_system="PMJAY_MS",
    source_snapshot_date="2023-05-18",
), raw)

# --------------------------------------------------------------------------- CGHS
d = rd("18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv", encoding="utf-8-sig")
raw = len(d)
spec = d["Specialities_Selected"].fillna("")
sysm = spec.map(lambda v: "PMJAY_MS" if re.search(r"\b[MS]\d", str(v)) else ("CGHS_2L" if str(v).strip() else None))
add("CGHS", frame(
    d, "CGHS",
    source_facility_id="CGHS:" + d["Hospital_Id"].astype(str),
    facility_name_raw=d["Hospital_Name"], address_raw=d["address_py"],
    state_raw=d["State"], district_raw=d["District"], pincode=d["Postcode_py"],
    latitude=d["Latitude"], longitude=d["Longitude"],
    facility_ownership_raw=d["Hospital_Type"], phone=d["Hospital_Contact"],
    specialty_raw=d["Specialities_Selected"], specialty_code_system=sysm,
    source_snapshot_date="2023-09-18",
), raw, "two specialty code systems")

# ---------------------------------------------------------------------------- NIN
d = rd("22_MAY_22_AP_NIN.csv", encoding="utf-8-sig")
raw = len(d)
d = d[~d[d.columns[1:]].isna().all(axis=1)].reset_index(drop=True)  # 203 blanks, 3 interior
nm = d["Manual Health Facility Name"].fillna(d["Health Facility Name"])
nm = nm.str.replace(r"^NOTIONAL\s+", "", regex=True)
add("NIN", frame(
    d, "NIN",
    source_facility_id="NIN:" + d["SrNo"].astype(str),
    facility_name_raw=nm, address_raw=d["Manual_Address"].fillna(d["Address"]),
    state_raw=d["State_Name"], district_raw=d["District_Name"],
    block_raw=d["Block_Name"], city=d["locality"],
    pincode=d["Manual_Pincode"].fillna(d["pincode"]),
    latitude=d["latitude"], longitude=d["longitude"],
    facility_type_raw=d["Facility Type"], phone=d["landline_number"],
    source_snapshot_date="2022-05-22",
), raw, "dropped 203 blank rows; stripped NOTIONAL prefix")

# -------------------------------------------------------------------------- PMGSY
d = rd("21_JULY_23_SRK_PMGSY_validated_homogenized.csv", encoding="utf-8-sig")
raw = len(d)
d = d[~d[d.columns[1:]].isna().all(axis=1)].reset_index(drop=True)
add("PMGSY", frame(
    d, "PMGSY",
    source_facility_id="PMGSY:" + d["Sr. No. "].astype(str),
    facility_name_raw=d["MASTER_FACILITY_DESC"], address_raw=d["ADDRESS"],
    state_raw=d["STATE_NAME"], district_raw=d["DISTRICT_NAME"],
    block_raw=d["BLOCK_NAME"], village_raw=d["HABITATION_NAME"],
    pincode=d["Postcode_py"], latitude=d["LATITUDE"], longitude=d["LONGITUDE"],
    facility_type_raw=d["SUB_CATEGORY"],
    source_snapshot_date=d["FILE_UPLOAD_DATE"],
), raw)

# ----------------------------------------------------------------------- PHC / CHC
for key, fn in [("PHC", "21_June_2024_AM_PHC.csv"), ("CHC", "21_June_2024_AM_CHC.csv")]:
    d = rd(fn, encoding="utf-8")
    raw = len(d)
    add(key, frame(
        d, key,
        source_facility_id=f"{key}:" + d["FACILITY_ID"].astype(str),
        facility_name_raw=d["FAC_DESC"],
        state_raw=d["STATE_NAME"], district_raw=d["DISTRICT_NAME"],
        latitude=d["Latitude"], longitude=d["Longitude"],
        facility_type_raw=key,  # tier is filename-only and leaks — see findings §3
        source_snapshot_date="2024-06-21",
    ), raw, "tier label unreliable (4.1% leak)")

# ---------------------------------------------------------------------------- NHP
d = rd("8_JULY_23_SRK_NHP_validated_and_standardized.csv", encoding="utf-8-sig")
raw = len(d)
d = d[d["Hospital Name"].notna()].reset_index(drop=True)  # 351 trailing blanks
for c in ("Hospital Name", "Given Address", "City", "State"):
    d[c] = d[c].map(lambda v: WS.sub(" ", str(v)).strip() if pd.notna(v) else v)
add("NHP", frame(
    d, "NHP",
    source_facility_id="NHP:" + d[d.columns[0]].astype(str),
    facility_name_raw=d["Hospital Name"], address_raw=d["Given Address"],
    state_raw=d["State"], city=d["City"], pincode=d["Postcode"],
    latitude=d["Latitude"], longitude=d["Longitude"],
    facility_type_raw="MEDICAL_COLLEGE",  # constant — not a column
    facility_ownership_raw=d["Type"], bed_count=d["No. of beds in attached Hospital"],
    source_snapshot_date="2023-07-08",
), raw, "648 real rows; type injected as constant")

# ------------------------------------------------------------------------ CDAC_BB
# B is A re-appended (verified). Use A, patch text cols from B, drop new_* (transposed).
a = rd("16_MAY_AR_CDAC_BB_DATASET.csv", encoding="utf-8")
b = rd("CDAC_BB_DATASET - Sheet1.csv", encoding="utf-8")
raw = len(a) + len(b)
n = len(a)
for c in ("Name", "Address", "Email"):
    a[c] = b[c][:n].values
a = a.drop_duplicates().reset_index(drop=True)
is_bsu = a["Name"].str.contains("BSU", case=False, na=False)
add("CDAC_BB", frame(
    a, "CDAC_BB",
    facility_name_raw=a["Name"], address_raw=a["Address"],
    state_raw=a["State"], district_raw=a["District"],
    latitude=a["Latitude"], longitude=a["Longitude"],
    phone=a["Phone"], email=a["Email"],
    facility_type_raw=is_bsu.map({True: "BLOOD_STORAGE_UNIT", False: "BLOOD_BANK"}),
    facility_ownership_raw=a["Category"],
    source_snapshot_date="2025-05-16",
), raw, "B discarded as duplicate; BSU extracted from name")

# ------------------------------------------------------------------------- combine
m = pd.concat(frames, ignore_index=True)

# Geo trust — findings §2. in-bbox is necessary but nowhere near sufficient.
lat, lon = m["latitude"], m["longitude"]
m["geo_in_bbox"] = (lat.between(6, 38) & lon.between(68, 98)).fillna(False)
pt = m["latitude"].round(4).astype(str) + "," + m["longitude"].round(4).astype(str)
shared = pt.map(pt[m["geo_in_bbox"]].value_counts()).fillna(0)
m["geo_shared_point_n"] = shared.astype(int)
m["geo_trust"] = (
    m["geo_in_bbox"]
    & (m["geo_shared_point_n"] <= 2)
    & lat.notna() & (lat != 0) & (lon != 0)
)

print(f"\n  TOTAL {len(m):,} source records")
print(f"  geo in-bbox: {int(m.geo_in_bbox.sum()):,}  |  geo_trust=true: {int(m.geo_trust.sum()):,}")

con = duckdb.connect(DB)
con.execute("DROP TABLE IF EXISTS facility_source_record")
con.execute("CREATE TABLE facility_source_record AS SELECT * FROM m")
con.execute("""
    CREATE OR REPLACE VIEW v_facility AS
    SELECT record_uid, source_dataset, source_facility_id,
           facility_name_raw AS name, facility_name_norm AS name_norm,
           address_raw AS address, state_norm AS state, district_norm AS district,
           block_raw, village_raw, city, pincode, latitude, longitude,
           facility_type_raw AS facility_type, facility_ownership_raw AS ownership,
           phone, email, specialty_raw, specialty_code_system,
           bed_count, is_24x7, abdm_enabled, source_snapshot_date,
           geo_in_bbox, geo_trust
    FROM facility_source_record
""")  # PII-free by construction: NIN.Coder is never ingested
con.execute("DROP TABLE IF EXISTS build_stats")
con.execute("CREATE TABLE build_stats AS SELECT * FROM (SELECT ? AS payload)", [json.dumps(stats)])
con.close()
print(f"\n  wrote {DB}")
