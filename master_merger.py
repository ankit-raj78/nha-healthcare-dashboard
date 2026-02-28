#!/usr/bin/env python3
"""
Master Healthcare Facility Dataset Merger
==========================================
Merges 9 healthcare CSV datasets into a single deduplicated master dataset
using geo-proximity (BallTree) + fuzzy name matching (rapidfuzz).
"""

import os
import re
import json
import uuid
import logging
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree
from rapidfuzz import fuzz
from unidecode import unidecode
from tqdm import tqdm

warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("master_merge.log", mode="w"),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

EARTH_RADIUS_KM = 6371.0
SEARCH_RADIUS_KM = 0.5  # 500 m
SEARCH_RADIUS_RAD = SEARCH_RADIUS_KM / EARTH_RADIUS_KM
TIGHT_RADIUS_KM = 0.1  # 100 m for generic names
TIGHT_RADIUS_RAD = TIGHT_RADIUS_KM / EARTH_RADIUS_KM
WIDE_RADIUS_KM = 1.0  # 1 km for medical colleges (NHP)
WIDE_RADIUS_RAD = WIDE_RADIUS_KM / EARTH_RADIUS_KM

NAME_SCORE_HIGH = 85
NAME_SCORE_MEDIUM = 70
NAME_SCORE_GENERIC = 95
NAME_SCORE_NO_GEO = 90

GENERIC_NAMES = {
    "HOSPITAL", "PHARMACY", "CLINIC", "DISPENSARY",
    "PRIMARY HEALTH CENTRE", "PRIMARY HEALTH CENTER",
    "COMMUNITY HEALTH CENTRE", "COMMUNITY HEALTH CENTER",
    "SUB HEALTH CENTER", "SUB HEALTH CENTRE", "SUB CENTRE",
    "HEALTH AND WELLNESS CENTER", "HEALTH AND WELLNESS CENTRE",
    "DENTAL CLINIC", "MEDICAL STORE", "HEALTH CENTER",
    "HEALTH CENTRE", "NURSING HOME",
}

SPECIALTY_EMP_COLS = [
    "M1_emp", "M2_emp", "M3_emp", "M4_emp", "M5_emp",
    "M6_emp", "M7_emp", "M8_emp", "M10_emp",
    "S1_emp", "S2_emp", "S3_emp", "S4_emp", "S5_emp",
    "S6_emp", "S7_emp", "S8_emp", "S9_emp", "S10_emp",
    "S11_emp", "S12_emp", "S13_emp", "S14_emp", "S15_emp", "S16_emp",
]

SPECIALTY_UPG_COLS = [
    "M1_upg", "M2_upg", "M3_upg", "M4_upg", "M5_upg",
    "M6_upg", "M7_upg", "M8_upg", "M10_upg",
    "S1_upg", "S2_upg", "S3_upg", "S4_upg", "S5_upg",
    "S6_upg", "S7_upg", "S10_upg", "S11_upg", "S12_upg",
    "S13_upg", "S14_upg", "S15_upg", "S16_upg",
]

SOURCE_FLAGS = [
    "in_nha", "in_phc", "in_pmgsy", "in_pmjay",
    "in_nin", "in_cdac_bb", "in_chc", "in_cghs", "in_nhp",
]

# ---------------------------------------------------------------------------
# File paths and column mappings
# ---------------------------------------------------------------------------
DATASET_FILES = {
    "NHA": "1_MAR_AR_2025_NHA_WITH_PMJAY_SPECIALITIES_WITH_CODES.csv",
    "PHC": "21_June_2024_AM_PHC.csv",
    "PMGSY": "21_JULY_23_SRK_PMGSY_validated_homogenized.csv",
    "PMJAY": "18_MAY_23_SRK_PMJAY_validated_and_standardized.csv",
    "NIN": "22_MAY_22_AP_NIN.csv",
    "CDAC_BB": "16_MAY_AR_CDAC_BB_DATASET.csv",
    "CHC": "21_June_2024_AM_CHC.csv",
    "CGHS": "18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv",
    "NHP": "8_JULY_23_SRK_NHP_validated_and_standardized.csv",
}

# Each mapping: {original_col: unified_col}
COLUMN_MAPS = {
    "NHA": {
        "Facility ID": "source_id",
        "hospital_name": "facility_name",
        "Address": "address",
        "Latitude": "latitude",
        "Longitude": "longitude",
        "State_name": "state",
        "District_name": "district",
        "new_state_name": "_nha_std_state",
        "state_code": "state_code",
        "new_district_name": "_nha_std_district",
        "district_code": "district_code",
        "Facility Type": "facility_type",
        "Ownership": "ownership",
        "ABDM Enabled": "abdm_enabled",
        "24/7": "is_24x7",
        "merged_specialties": "specialties",
    },
    "PHC": {
        "STATE_NAME": "state",
        "DISTRICT_NAME": "district",
        "FACILITY_ID": "source_id",
        "FAC_DESC": "facility_name",
        "Latitude": "latitude",
        "Longitude": "longitude",
    },
    "PMGSY": {
        "STATE_NAME": "state",
        "DISTRICT_NAME": "district",
        "BLOCK_NAME": "_block",
        "MASTER_FACILITY_DESC": "facility_name",
        "ADDRESS": "address",
        "SUB_CATEGORY": "facility_subtype",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "Pincode": "pincode",
        "Formatted Address": "_formatted_addr",
    },
    "PMJAY": {
        "Hospital Name": "facility_name",
        "Hospital Type": "ownership",
        "API Latitude": "latitude",
        "API Longitude": "longitude",
        "Manual Hospital Address": "address",
        "Hospital E-Mail": "email",
        "Hospital Contact": "phone",
        "Specialities Empanelled": "_specialties_emp",
        "Specialities Upgraded": "_specialties_upg",
        "Manual District": "district",
        "Manual state": "state",
        "gmaps_Latitude": "_gmaps_lat",
        "gmaps_Longitude": "_gmaps_lon",
        "pincode_py": "pincode",
        "Formatted Address": "_formatted_addr",
    },
    "NIN": {
        "Health Facility Name": "facility_name",
        "Address": "address",
        "pincode": "pincode",
        "landline_number": "phone",
        "latitude": "latitude",
        "longitude": "longitude",
        "Facility Type": "facility_type",
        "State_Name": "state",
        "District_Name": "district",
        "Taluka_Name": "_taluka",
        "Block_Name": "_block",
    },
    "CDAC_BB": {
        "Name": "facility_name",
        "State": "state",
        "District": "district",
        "Address": "address",
        "Latitude": "latitude",
        "Longitude": "longitude",
        "Phone": "phone",
        "Email": "email",
        "Category": "ownership",
        "new_latitude": "_cdac_corrected_lat",
        "new_longitude": "_cdac_corrected_lon",
    },
    "CHC": {
        "STATE_NAME": "state",
        "DISTRICT_NAME": "district",
        "FACILITY_ID": "source_id",
        "FAC_DESC": "facility_name",
        "Latitude": "latitude",
        "Longitude": "longitude",
    },
    "CGHS": {
        "Hospital_Id": "source_id",
        "Hospital_Name": "facility_name",
        "District": "district",
        "State": "state",
        "Hospital_Contact": "phone",
        "Specialities_Selected": "specialties",
        "Hospital_Type": "ownership",
        "Address": "address",
        "Latitude": "latitude",
        "Longitude": "longitude",
        "Postcode_py": "pincode",
    },
    "NHP": {
        "Hospital Name": "facility_name",
        "Latitude": "latitude",
        "Longitude": "longitude",
        "Standardized Address": "address",
        "City": "_city",
        "State": "state",
        "Postcode": "pincode",
        "Type": "ownership",
        "No. of beds in attached Hospital": "num_beds",
        "Contact": "phone",
    },
}

# ---------------------------------------------------------------------------
# State name standardisation
# ---------------------------------------------------------------------------
STATE_NORMALIZATION = {
    "ANDAMAN & NICOBAR": "Andaman And Nicobar Islands",
    "ANDAMAN & NICOBAR ISLANDS": "Andaman And Nicobar Islands",
    "ANDAMAN AND NICOBAR": "Andaman And Nicobar Islands",
    "ANDAMAN AND NICOBAR ISLANDS": "Andaman And Nicobar Islands",
    "A & N ISLANDS": "Andaman And Nicobar Islands",
    "ANDHRA PRADESH": "Andhra Pradesh",
    "ARUNACHAL PRADESH": "Arunachal Pradesh",
    "ASSAM": "Assam",
    "BIHAR": "Bihar",
    "CHANDIGARH": "Chandigarh",
    "CHATTISGARH": "Chhattisgarh",
    "CHHATTISGARH": "Chhattisgarh",
    "DADRA & NAGAR HAVE": "Dadra And Nagar Haveli And Daman And Diu",
    "DADRA & NAGAR HAVELI": "Dadra And Nagar Haveli And Daman And Diu",
    "DADRA AND NAGAR HAVELI": "Dadra And Nagar Haveli And Daman And Diu",
    "DAMAN & DIU": "Dadra And Nagar Haveli And Daman And Diu",
    "DAMAN AND DIU": "Dadra And Nagar Haveli And Daman And Diu",
    "THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU": "Dadra And Nagar Haveli And Daman And Diu",
    "DADRA & NAGAR HAVELI AND DAMAN & DIU": "Dadra And Nagar Haveli And Daman And Diu",
    "DADRA AND NAGAR HAVELI AND DAMAN AND DIU": "Dadra And Nagar Haveli And Daman And Diu",
    "DNH AND DD": "Dadra And Nagar Haveli And Daman And Diu",
    "D & N HAVELI": "Dadra And Nagar Haveli And Daman And Diu",
    "DELHI": "Delhi",
    "NCT OF DELHI": "Delhi",
    "NEW DELHI": "Delhi",
    "GOA": "Goa",
    "GUJARAT": "Gujarat",
    "HARYANA": "Haryana",
    "HIMACHAL PRADESH": "Himachal Pradesh",
    "JAMMU & KASHMIR": "Jammu And Kashmir",
    "JAMMU AND KASHMIR": "Jammu And Kashmir",
    "JHARKHAND": "Jharkhand",
    "KARNATAKA": "Karnataka",
    "KERALA": "Kerala",
    "LADAKH": "Ladakh",
    "LAKSHADWEEP": "Lakshadweep",
    "MADHYA PRADESH": "Madhya Pradesh",
    "MAHARASHTRA": "Maharashtra",
    "MANIPUR": "Manipur",
    "MEGHALAYA": "Meghalaya",
    "MIZORAM": "Mizoram",
    "NAGALAND": "Nagaland",
    "ODISHA": "Odisha",
    "ORISSA": "Odisha",
    "PONDICHERRY": "Puducherry",
    "PUDUCHERRY": "Puducherry",
    "PUNJAB": "Punjab",
    "RAJASTHAN": "Rajasthan",
    "SIKKIM": "Sikkim",
    "TAMILNADU": "Tamil Nadu",
    "TAMIL NADU": "Tamil Nadu",
    "TELANGANA": "Telangana",
    "TELENGANA": "Telangana",
    "TRIPURA": "Tripura",
    "UTTAR PRADESH": "Uttar Pradesh",
    "UTTTAR PRADESH": "Uttar Pradesh",
    "UTTARAKHAND": "Uttarakhand",
    "WEST BENGAL": "West Bengal",
}

# ---------------------------------------------------------------------------
# Facility type standardisation
# ---------------------------------------------------------------------------
FACILITY_TYPE_MAP = {
    "Sub Centre": "Sub Centre",
    "Hospital": "Hospital",
    "Pharmacy": "Pharmacy",
    "Primary Health Centre": "Primary Health Centre",
    "Clinic/ Dispensary": "Clinic/Dispensary",
    "Health and Wellness Centre": "Health And Wellness Centre",
    "Community Health Centre": "Community Health Centre",
    "Medical College": "Medical College",
    "Diagnostic Laboratory": "Diagnostic Laboratory",
    "Imaging Center": "Imaging Center",
    "Dental Clinic": "Dental Clinic",
    "Dental Hospital": "Dental Hospital",
    # AYUSH
    "Ayurveda Hospital/ Nursing Home": "AYUSH Hospital",
    "Ayurveda Dispensary/ Clinic/ Polyclinic (OPD only)": "AYUSH Dispensary",
    "Homeopathy Dispensary/ Clinic/ Polyclinic (OPD only)": "AYUSH Dispensary",
    "Homeopathy Hospital/ Nursing Home": "AYUSH Hospital",
    "Unani Dispensary/ Clinic/ Polyclinic (OPD only)": "AYUSH Dispensary",
    "Unani Hospital/ Nursing Home": "AYUSH Hospital",
    "Yoga and Naturopathy Dispensary/ Clinic/ Polyclinic (OPD only)": "AYUSH Dispensary",
    "Yoga and Naturopathy Hospital/ Nursing Home": "AYUSH Hospital",
    "Siddha Hospital/Nursing Home": "AYUSH Hospital",
    "Siddha Dispensary/Clinic/Polyclinic (OPD only)": "AYUSH Dispensary",
    "Sowa-Rigpa Hospital/ Nursing Home": "AYUSH Hospital",
    "Sowa-Rigpa Dispensary/ Clinic/ Polyclinic (OPD only)": "AYUSH Dispensary",
    # CHC/PHC FAC_DESC
    "Community health centre": "Community Health Centre",
    "Primary health sub centre": "Sub Centre",
    "Primary health centre": "Primary Health Centre",
    # PMGSY SUB_CATEGORY
    "Bedded Hospital": "Hospital",
    # NIN
    "Community Health Center": "Community Health Centre",
    "Sub-District Hospital": "Sub-District Hospital",
    "Dispensaries": "Dispensary",
    "District Hospital": "District Hospital",
    "<100 Bedded Hospital": "Hospital",
    "Medical Colleges Hospital": "Medical College",
    "Civil Hospital/General Hospital": "Hospital",
    "Maternity Home": "Maternity Home",
    "Post Partum Unit": "Other",
    "Referral Hospital": "Referral Hospital",
    "100-500 Bedded Hospital": "Hospital",
    ">500 Bedded Hospital": "Hospital",
    "Others": "Other",
}

OWNERSHIP_MAP = {
    "Government": "Government",
    "Private": "Private",
    "Public-Private-Partnership": "PPP",
    "Govt.": "Government",
    "Trust": "Trust",
    "Society": "Trust",
    "Govt-Society": "Government",
    "Charitable/Vol": "Charitable",
    "Red Cross": "Charitable",
    "Private (For Profit)": "Private",
    "Private(For Profit)": "Private",
    "Public": "Government",
    "Govt": "Government",
}


# ===================================================================
# Helper functions
# ===================================================================

def clean_facility_name(name):
    """Normalise a facility name for matching."""
    if pd.isna(name):
        return ""
    name = str(name).upper().strip()
    name = unidecode(name)
    name = re.sub(r"[^A-Z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    for noise in ("PVT", "LTD", "LIMITED", "PRIVATE", "A UNIT OF"):
        name = name.replace(noise, "")
    return re.sub(r"\s+", " ", name).strip()


def standardize_state(raw):
    """Return canonical state name."""
    if pd.isna(raw):
        return ""
    key = str(raw).upper().strip()
    return STATE_NORMALIZATION.get(key, str(raw).strip().title())


def standardize_facility_type(raw):
    if pd.isna(raw):
        return ""
    return FACILITY_TYPE_MAP.get(str(raw).strip(), str(raw).strip())


def standardize_ownership(raw):
    if pd.isna(raw):
        return ""
    return OWNERSHIP_MAP.get(str(raw).strip(), str(raw).strip())


def is_generic_name(clean_name):
    return clean_name in GENERIC_NAMES


def token_overlap(a, b):
    """Quick Jaccard token overlap."""
    ta = set(a.split())
    tb = set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def haversine_km(lat1, lon1, lat2, lon2):
    """Haversine distance in km between two points."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


# ===================================================================
# Dataset Loader
# ===================================================================

class DatasetLoader:
    """Load and harmonise a single dataset."""

    def __init__(self, data_dir):
        self.data_dir = data_dir

    def load(self, ds_name):
        """Load dataset, rename columns, tag source."""
        filepath = os.path.join(self.data_dir, DATASET_FILES[ds_name])
        log.info("Loading %s from %s", ds_name, DATASET_FILES[ds_name])
        df = pd.read_csv(filepath, low_memory=False)
        log.info("  Loaded %d rows x %d cols", len(df), len(df.columns))

        col_map = COLUMN_MAPS[ds_name]

        # Keep specialty columns as-is
        rename = {}
        for orig, unified in col_map.items():
            if orig in df.columns:
                rename[orig] = unified
        df = df.rename(columns=rename)

        # Dataset-specific fixes
        df = self._apply_fixes(df, ds_name)

        # Add source tag
        df["source_datasets"] = ds_name

        # Clean facility name
        df["facility_name_clean"] = df["facility_name"].apply(clean_facility_name)

        # Standardise state
        df["state"] = df["state"].apply(standardize_state)

        # Standardise district
        if "district" in df.columns:
            df["district"] = df["district"].apply(
                lambda x: str(x).strip().title() if pd.notna(x) else ""
            )

        # Standardise facility_type and ownership
        if "facility_type" in df.columns:
            df["facility_type"] = df["facility_type"].apply(standardize_facility_type)
        if "ownership" in df.columns:
            df["ownership"] = df["ownership"].apply(standardize_ownership)

        # Ensure lat/lon are numeric
        for col in ("latitude", "longitude"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def _apply_fixes(self, df, ds_name):
        """Dataset-specific preprocessing."""
        if ds_name == "NHA":
            # Use pre-standardised state/district if main is missing
            if "_nha_std_state" in df.columns:
                mask = df["state"].isna() | (df["state"] == "")
                df.loc[mask, "state"] = df.loc[mask, "_nha_std_state"]
            if "_nha_std_district" in df.columns:
                mask = df["district"].isna() | (df["district"] == "")
                df.loc[mask, "district"] = df.loc[mask, "_nha_std_district"]
            df["in_nha"] = True

        elif ds_name == "CDAC_BB":
            # Use corrected coordinates when available
            if "_cdac_corrected_lat" in df.columns:
                mask = df["_cdac_corrected_lat"].notna()
                df.loc[mask, "latitude"] = df.loc[mask, "_cdac_corrected_lat"]
            if "_cdac_corrected_lon" in df.columns:
                mask = df["_cdac_corrected_lon"].notna()
                df.loc[mask, "longitude"] = df.loc[mask, "_cdac_corrected_lon"]
            df["facility_type"] = "Blood Bank"
            df["in_cdac_bb"] = True

        elif ds_name == "PMJAY":
            # Fall back to gmaps coordinates if API coords missing
            if "_gmaps_lat" in df.columns:
                mask = df["latitude"].isna()
                df.loc[mask, "latitude"] = df.loc[mask, "_gmaps_lat"]
            if "_gmaps_lon" in df.columns:
                mask = df["longitude"].isna()
                df.loc[mask, "longitude"] = df.loc[mask, "_gmaps_lon"]
            # Merge specialties
            parts = []
            for col in ("_specialties_emp", "_specialties_upg"):
                if col in df.columns:
                    parts.append(df[col].fillna(""))
            if parts:
                df["specialties"] = parts[0].str.cat(parts[1:], sep="|").str.strip("|")
            df["in_pmjay"] = True

        elif ds_name == "NHP":
            df["facility_type"] = "Medical College"
            df["in_nhp"] = True

        elif ds_name == "CHC":
            df["facility_type"] = "Community Health Centre"
            df["in_chc"] = True

        elif ds_name == "PHC":
            df["facility_type"] = "Primary Health Centre"
            df["in_phc"] = True

        elif ds_name == "PMGSY":
            df["in_pmgsy"] = True

        elif ds_name == "CGHS":
            df["in_cghs"] = True

        elif ds_name == "NIN":
            df["in_nin"] = True

        return df


# ===================================================================
# Spatial Matcher
# ===================================================================

class SpatialMatcher:
    """BallTree-based geo-proximity matcher, partitioned by state."""

    def __init__(self):
        self.trees = {}  # state -> (BallTree, base_indices_array)

    def build(self, base_df):
        """Build BallTree per state from the base dataframe."""
        self.trees = {}
        valid = base_df.dropna(subset=["latitude", "longitude"])
        for state, group in valid.groupby("state"):
            if len(group) == 0 or state == "":
                continue
            coords = np.radians(group[["latitude", "longitude"]].values)
            tree = BallTree(coords, metric="haversine")
            self.trees[state] = (tree, group.index.values)
        log.info("Built BallTrees for %d states", len(self.trees))

    def query(self, lat, lon, state, radius_rad=SEARCH_RADIUS_RAD):
        """Return base indices within radius for a given point and state."""
        if state not in self.trees:
            return np.array([], dtype=int)
        tree, base_indices = self.trees[state]
        point = np.radians([[lat, lon]])
        result = tree.query_radius(point, r=radius_rad)[0]
        if len(result) == 0:
            return np.array([], dtype=int)
        return base_indices[result]

    def batch_query(self, lats, lons, state, radius_rad=SEARCH_RADIUS_RAD):
        """Query multiple points at once. Returns list of arrays."""
        if state not in self.trees:
            return [np.array([], dtype=int)] * len(lats)
        tree, base_indices = self.trees[state]
        coords = np.radians(np.column_stack([lats, lons]))
        raw = tree.query_radius(coords, r=radius_rad)
        return [base_indices[r] if len(r) > 0 else np.array([], dtype=int) for r in raw]


# ===================================================================
# Master Merger
# ===================================================================

class MasterMerger:
    """Orchestrates the full merge pipeline."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.loader = DatasetLoader(data_dir)
        self.spatial = SpatialMatcher()
        self.master = None
        self.stats = {}
        self.sample_matches = []

    # ----- Step 1: Load NHA as base -----
    def load_base(self):
        log.info("=" * 60)
        log.info("STEP 1: Loading NHA as base dataset")
        self.master = self.loader.load("NHA")
        self.master["source_ids"] = self.master["source_id"].astype(str)
        log.info("Base loaded: %d rows", len(self.master))
        self.stats["NHA"] = {
            "loaded": len(self.master),
            "matched": 0,
            "new": len(self.master),
        }
        # Build initial spatial index
        self.spatial.build(self.master)

    # ----- Step 2: Merge secondary datasets -----
    def merge_dataset(self, ds_name):
        log.info("=" * 60)
        log.info("STEP: Merging %s into master", ds_name)

        incoming = self.loader.load(ds_name)
        n_incoming = len(incoming)
        log.info("Incoming: %d rows", n_incoming)

        # Determine search radius
        radius = SEARCH_RADIUS_RAD
        if ds_name == "NHP":
            radius = WIDE_RADIUS_RAD

        matched_count = 0
        unmatched_indices = []

        # Group by state for efficiency
        grouped = incoming.groupby("state")
        for state, group in tqdm(grouped, desc=f"Merging {ds_name}", unit="state"):
            if state == "":
                unmatched_indices.extend(group.index.tolist())
                continue

            # Filter rows with valid coordinates
            has_geo = group["latitude"].notna() & group["longitude"].notna()
            geo_group = group[has_geo]
            no_geo_group = group[~has_geo]

            # Batch spatial query for rows with coordinates
            if len(geo_group) > 0:
                candidates_list = self.spatial.batch_query(
                    geo_group["latitude"].values,
                    geo_group["longitude"].values,
                    state,
                    radius,
                )
                for iloc_idx, (df_idx, row) in enumerate(geo_group.iterrows()):
                    candidate_base_idxs = candidates_list[iloc_idx]
                    if len(candidate_base_idxs) == 0:
                        unmatched_indices.append(df_idx)
                        continue

                    match_idx = self._find_best_match(
                        row, candidate_base_idxs, ds_name
                    )
                    if match_idx is not None:
                        self._merge_row(match_idx, row, ds_name)
                        matched_count += 1
                    else:
                        unmatched_indices.append(df_idx)

            # Handle rows without coordinates — name-only matching
            if len(no_geo_group) > 0:
                for df_idx, row in no_geo_group.iterrows():
                    match_idx = self._name_only_match(row, state)
                    if match_idx is not None:
                        self._merge_row(match_idx, row, ds_name)
                        matched_count += 1
                    else:
                        unmatched_indices.append(df_idx)

        # Append unmatched rows as new entries
        new_rows = incoming.loc[unmatched_indices].copy()
        n_new = len(new_rows)
        if n_new > 0:
            self.master = pd.concat([self.master, new_rows], ignore_index=True)

        log.info(
            "%s: %d matched, %d new added (total master: %d)",
            ds_name, matched_count, n_new, len(self.master),
        )
        self.stats[ds_name] = {
            "loaded": n_incoming,
            "matched": matched_count,
            "new": n_new,
        }

        # Rebuild spatial index with new rows
        self.spatial.build(self.master)

    def _find_best_match(self, row, candidate_base_idxs, ds_name):
        """
        Among spatial candidates, find the best fuzzy name match.
        Returns base_idx or None.
        """
        inc_name = row.get("facility_name_clean", "")
        if not inc_name:
            return None

        inc_is_generic = is_generic_name(inc_name)
        inc_ftype = row.get("facility_type", "")

        best_idx = None
        best_score = 0
        best_dist = float("inf")

        for base_idx in candidate_base_idxs:
            base_name = self.master.at[base_idx, "facility_name_clean"]
            if not base_name:
                continue

            # Quick token overlap filter
            if token_overlap(inc_name, base_name) < 0.2:
                continue

            score = fuzz.token_sort_ratio(inc_name, base_name)
            dist = haversine_km(
                row["latitude"], row["longitude"],
                self.master.at[base_idx, "latitude"],
                self.master.at[base_idx, "longitude"],
            )

            # Decision logic
            is_match = False
            if inc_is_generic or is_generic_name(base_name):
                # Strict: very close + near-exact name
                if dist <= TIGHT_RADIUS_KM and score >= NAME_SCORE_GENERIC:
                    is_match = True
            elif score >= NAME_SCORE_HIGH:
                is_match = True
            elif score >= NAME_SCORE_MEDIUM:
                base_ftype = self.master.at[base_idx, "facility_type"] if "facility_type" in self.master.columns else ""
                if inc_ftype and base_ftype and inc_ftype == base_ftype:
                    is_match = True

            if is_match and (score > best_score or (score == best_score and dist < best_dist)):
                best_score = score
                best_dist = dist
                best_idx = base_idx

        # Log sample matches
        if best_idx is not None and len(self.sample_matches) < 200:
            self.sample_matches.append({
                "incoming_name": row.get("facility_name", ""),
                "base_name": self.master.at[best_idx, "facility_name"],
                "score": best_score,
                "distance_km": round(best_dist, 4),
                "state": row.get("state", ""),
                "source": ds_name,
            })

        return best_idx

    def _name_only_match(self, row, state):
        """
        For rows without coordinates, match by state + district + name.
        More conservative threshold.
        """
        inc_name = row.get("facility_name_clean", "")
        inc_district = row.get("district", "")
        if not inc_name or is_generic_name(inc_name):
            return None

        # Filter master to same state + district
        mask = self.master["state"] == state
        if inc_district:
            mask = mask & (self.master["district"] == inc_district)
        candidates = self.master[mask]
        if len(candidates) == 0:
            return None

        best_idx = None
        best_score = 0
        for base_idx, base_row in candidates.iterrows():
            base_name = base_row.get("facility_name_clean", "")
            if not base_name:
                continue
            score = fuzz.token_sort_ratio(inc_name, base_name)
            if score >= NAME_SCORE_NO_GEO and score > best_score:
                best_score = score
                best_idx = base_idx

        return best_idx

    def _merge_row(self, base_idx, incoming_row, source_name):
        """Merge incoming row's data into the master at base_idx."""
        # Append source
        existing_src = str(self.master.at[base_idx, "source_datasets"])
        if source_name not in existing_src:
            self.master.at[base_idx, "source_datasets"] = existing_src + "|" + source_name

        # Append source_id
        inc_id = incoming_row.get("source_id", "")
        if pd.notna(inc_id) and str(inc_id).strip():
            existing_ids = str(self.master.at[base_idx, "source_ids"]) if pd.notna(self.master.at[base_idx, "source_ids"]) else ""
            if str(inc_id) not in existing_ids:
                self.master.at[base_idx, "source_ids"] = (
                    (existing_ids + "|" + str(inc_id)).strip("|")
                )

        # Fill missing fields
        fill_cols = [
            "address", "pincode", "phone", "email",
            "num_beds", "abdm_enabled", "is_24x7",
            "facility_type", "facility_subtype", "ownership",
        ]
        for col in fill_cols:
            if col in incoming_row.index and pd.notna(incoming_row[col]):
                if col not in self.master.columns:
                    self.master[col] = np.nan
                if pd.isna(self.master.at[base_idx, col]) or str(self.master.at[base_idx, col]).strip() == "":
                    self.master.at[base_idx, col] = incoming_row[col]

        # Merge specialties (union)
        if "specialties" in incoming_row.index and pd.notna(incoming_row.get("specialties")):
            existing_spec = str(self.master.at[base_idx, "specialties"]) if pd.notna(self.master.at[base_idx, "specialties"]) else ""
            inc_spec = str(incoming_row["specialties"])
            merged = set(existing_spec.split("|")) | set(inc_spec.split("|"))
            merged.discard("")
            self.master.at[base_idx, "specialties"] = "|".join(sorted(merged))

        # Set source boolean flag
        flag = f"in_{source_name.lower()}"
        if flag not in self.master.columns:
            self.master[flag] = False
        self.master.at[base_idx, flag] = True

        # OR-merge specialty binary columns
        for col in SPECIALTY_EMP_COLS + SPECIALTY_UPG_COLS:
            if col in incoming_row.index and incoming_row.get(col) == 1:
                if col not in self.master.columns:
                    self.master[col] = np.nan
                self.master.at[base_idx, col] = 1

    # ----- Step 3: Post-processing -----
    def post_process(self):
        log.info("=" * 60)
        log.info("POST-PROCESSING")

        # Assign master_id
        self.master["master_id"] = [str(uuid.uuid4()) for _ in range(len(self.master))]

        # Ensure all source flags exist
        for flag in SOURCE_FLAGS:
            if flag not in self.master.columns:
                self.master[flag] = False
            self.master[flag] = self.master[flag].fillna(False).astype(bool)

        # Drop internal columns (prefixed with _)
        internal = [c for c in self.master.columns if c.startswith("_")]
        if internal:
            log.info("Dropping %d internal columns: %s", len(internal), internal)
            self.master.drop(columns=internal, inplace=True)

        # Drop unnamed columns
        unnamed = [c for c in self.master.columns if c.startswith("Unnamed")]
        if unnamed:
            self.master.drop(columns=unnamed, inplace=True)

        # Reorder columns: master_id first, then core, then flags, then rest
        core_cols = [
            "master_id", "source_datasets", "source_ids",
            "facility_name", "facility_name_clean",
            "latitude", "longitude",
            "state", "state_code", "district", "district_code",
            "address", "pincode",
            "facility_type", "facility_subtype", "ownership",
            "phone", "email",
            "specialties", "num_beds", "is_24x7", "abdm_enabled",
        ]
        flag_cols = SOURCE_FLAGS
        remaining = [c for c in self.master.columns if c not in core_cols + flag_cols]
        ordered = [c for c in core_cols if c in self.master.columns]
        ordered += [c for c in flag_cols if c in self.master.columns]
        ordered += remaining
        self.master = self.master[ordered]

        log.info("Final master: %d rows x %d cols", len(self.master), len(self.master.columns))

    # ----- Step 4: Validate -----
    def validate(self):
        log.info("=" * 60)
        log.info("VALIDATION")
        df = self.master
        issues = []

        # Row count
        if len(df) < 323460:
            issues.append(f"Row count {len(df)} < NHA base 323460!")
        log.info("Total rows: %d", len(df))

        # Lat/lon coverage
        lat_null = df["latitude"].isnull().sum()
        lon_null = df["longitude"].isnull().sum()
        log.info("Missing latitude: %d (%.1f%%)", lat_null, 100 * lat_null / len(df))
        log.info("Missing longitude: %d (%.1f%%)", lon_null, 100 * lon_null / len(df))

        # Source tracking
        no_source = df["source_datasets"].isnull().sum()
        if no_source > 0:
            issues.append(f"{no_source} rows have no source dataset")
        log.info("Rows without source: %d", no_source)

        # State coverage
        n_states = df["state"].nunique()
        log.info("Unique states/UTs: %d", n_states)

        # Per-source counts
        for flag in SOURCE_FLAGS:
            if flag in df.columns:
                count = df[flag].sum()
                log.info("  %s: %d records", flag, count)

        # Coordinate range (India bounding box)
        valid_geo = df.dropna(subset=["latitude", "longitude"])
        out_of_range = (
            (valid_geo["latitude"] < 6) | (valid_geo["latitude"] > 38)
            | (valid_geo["longitude"] < 68) | (valid_geo["longitude"] > 98)
        ).sum()
        log.info("Coordinates outside India bounding box: %d", out_of_range)

        if issues:
            for iss in issues:
                log.warning("ISSUE: %s", iss)
        else:
            log.info("All validations passed!")
        return issues

    # ----- Step 5: Export -----
    def export(self):
        out_csv = os.path.join(self.data_dir, "healthcare_master_dataset.csv")
        log.info("Exporting master dataset to %s", out_csv)
        self.master.to_csv(out_csv, index=False)
        log.info("Export done. File size: %.1f MB", os.path.getsize(out_csv) / 1e6)

        # Merge report
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_rows": len(self.master),
            "total_columns": len(self.master.columns),
            "per_dataset": self.stats,
        }
        report_path = os.path.join(self.data_dir, "merge_report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        log.info("Merge report: %s", report_path)

        # Sample matches
        if self.sample_matches:
            sample_df = pd.DataFrame(self.sample_matches)
            sample_path = os.path.join(self.data_dir, "sample_matches.csv")
            sample_df.to_csv(sample_path, index=False)
            log.info("Sample matches: %s (%d entries)", sample_path, len(sample_df))


# ===================================================================
# Main
# ===================================================================

def main():
    log.info("=" * 60)
    log.info("HEALTHCARE MASTER DATASET MERGER")
    log.info("=" * 60)

    merger = MasterMerger(DATA_DIR)

    # Step 1: Load NHA as base
    merger.load_base()

    # Step 2: Merge secondary datasets
    merge_order = ["PHC", "PMGSY", "PMJAY", "NIN", "CDAC_BB", "CHC", "CGHS", "NHP"]
    for ds_name in merge_order:
        merger.merge_dataset(ds_name)

    # Step 3: Post-process
    merger.post_process()

    # Step 4: Validate
    merger.validate()

    # Step 5: Export
    merger.export()

    log.info("=" * 60)
    log.info("DONE!")


if __name__ == "__main__":
    main()
