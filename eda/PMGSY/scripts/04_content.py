"""Step 4: content quality — names, types, geocoder cross-check, PII, granularity proof."""
import pandas as pd, numpy as np, re
from collections import Counter

SRC = "/Users/ankitraj2/asar master data/21_JULY_23_SRK_PMGSY_validated_homogenized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = df.dropna(how="all").reset_index(drop=True)
N = len(df)
lat = pd.to_numeric(df["LATITUDE"]); lon = pd.to_numeric(df["LONGITUDE"])

print("### A. Formatted Address = consecutive-dedup concat? ###")
def build(r):
    parts = [r["Hospital Name"], r["Street/Locality"], r["Habitation"], r["Block"],
             r["City/District"], r["State"], r["Country"], r["Pincode"]]
    out = []
    for p in parts:
        p = "" if pd.isna(p) else p
        if out and out[-1] == p:
            continue
        out.append(p)
    return ", ".join(out)
b = df.apply(build, axis=1)
print("  consecutive-dedup concat matches:", (b == df["Formatted Address"]).sum(), "/", N)
mm = df.index[b != df["Formatted Address"]]
print("  remaining mismatches:", len(mm), "sample:", mm[:5].tolist())
for i in mm[:3]:
    print("   built :", b[i][:180]); print("   actual:", df.loc[i, "Formatted Address"][:180])

print("\n### B. Is one row one FACILITY or one habitation-facility LINK? ###")
def norm(s): return s.fillna("").str.lower().str.replace(r"[^a-z0-9]", "", regex=True).str.strip()
nm = norm(df["MASTER_FACILITY_DESC"])
print("  rows:", N, " distinct HAB_CODE:", df['HAB_CODE'].nunique(),
      " distinct (HAB_CODE,normname):", len(set(zip(df['HAB_CODE'], nm))))
print("  distinct exact (lat,lon) pairs:", len(set(zip(df['LATITUDE'], df['LONGITUDE']))))
# a real link table would repeat the same (name, geo) under different HAB_CODEs
g = pd.DataFrame({"n": nm, "lat": df["LATITUDE"], "lon": df["LONGITUDE"], "h": df["HAB_CODE"]})
gg = g.groupby(["n", "lat", "lon"])["h"].nunique()
print("  (normname,lat,lon) combos appearing under >1 HAB_CODE:", (gg > 1).sum())
gg2 = g.groupby(["lat", "lon"])["h"].nunique()
print("  (lat,lon) appearing under >1 HAB_CODE:", (gg2 > 1).sum())
dup_geo = df[df.duplicated(subset=["LATITUDE", "LONGITUDE"], keep=False)]
print("  rows sharing an exact (lat,lon):", len(dup_geo))
print(dup_geo.sort_values(["LATITUDE"])[["Sr. No. ","STATE_NAME","DISTRICT_NAME","HAB_CODE","HABITATION_NAME","MASTER_FACILITY_DESC","LATITUDE","LONGITUDE"]].head(30).to_string())

print("\n### C. How informative is MASTER_FACILITY_DESC? ###")
GENERIC = {"chc","phc","hospital","hospitals","dispensary","clinic","bedded hospital","beddedhospital",
 "community health centre","community health center","communityhealthcentre","communityhealthcenter",
 "primary health centre","primary health center","govt hospital","government hospital","nursing home",
 "sub centre","sub center","subcentre","hospital bedded","beded hospital","phc bedded hospital",
 "medical","health centre","health center","hospitl","hospitle","govt. hospital"}
gen_norm = {re.sub(r"[^a-z0-9]","",x) for x in GENERIC}
is_gen = nm.isin(gen_norm)
print("  rows whose whole name is a generic facility-type token:", is_gen.sum(), f"({100*is_gen.sum()/N:.2f}%)")
print("  top 25 generic values:", df.loc[is_gen,"MASTER_FACILITY_DESC"].value_counts().head(25).to_dict())
# name length / token count
tok = df["MASTER_FACILITY_DESC"].str.split().str.len()
print("  token-count dist:", Counter(tok).most_common(10))
print("  names with <=2 tokens:", (tok<=2).sum(), f"({100*(tok<=2).sum()/N:.2f}%)")
print("  distinct normalised names:", nm.nunique(), "vs raw distinct:", df["MASTER_FACILITY_DESC"].nunique())

print("\n### D. Are all rows health facilities? keyword scan ###")
low = df["MASTER_FACILITY_DESC"].str.lower().fillna("")
pats = {"school": r"\bschool|vidyalaya|pathshala|college of educ|primary school|junior high",
        "anganwadi": r"anganwadi|aanganwadi|angan wadi",
        "road/bridge": r"\bbridge\b|\broad work|culvert|\bpwd\b",
        "panchayat/office": r"panchayat|gram sabha|block office|tehsil|police station",
        "bank/market": r"\bbank\b|market|mandi",
        "veterinary": r"veterinar|pashu|animal husband",
        "ayush": r"ayurved|homeo|unani|siddha|ayush",
        "college": r"medical college|nursing college|institute of medical",
        "lab/pharmacy": r"path\s?lab|diagnostic|medical store|pharmac",
        "healthish": r"hospital|health|chc|phc|clinic|dispensar|nursing|medical|aspatal|asptal|swasthya|arogya|hosp"}
for k, p in pats.items():
    m = low.str.contains(p, regex=True, na=False)
    print(f"  {k:18s}: {m.sum():5d}")
    if k in ("school","anganwadi","road/bridge","panchayat/office","bank/market","veterinary") and m.sum():
        print("      e.g.", df.loc[m,["Sr. No. ","MASTER_FACILITY_DESC","SUB_CATEGORY"]].head(8).to_dict("records"))
nonhealth = ~low.str.contains(pats["healthish"], regex=True, na=False)
print("  rows with NO health keyword in name:", nonhealth.sum(), f"({100*nonhealth.sum()/N:.2f}%)")
print("  sample of those:", df.loc[nonhealth,"MASTER_FACILITY_DESC"].value_counts().head(30).to_dict())

print("\n### E. SUB_CATEGORY vs name agreement ###")
looks_chc = low.str.contains(r"\bchc\b|community health|comm.* health", regex=True, na=False)
print("  SUB_CATEGORY=CHC & name mentions CHC/community health:",
      ((df.SUB_CATEGORY=="Community Health Centre") & looks_chc).sum(), "of",
      (df.SUB_CATEGORY=="Community Health Centre").sum())
print("  SUB_CATEGORY=Bedded Hospital & name mentions CHC/community health:",
      ((df.SUB_CATEGORY=="Bedded Hospital") & looks_chc).sum(), "of",
      (df.SUB_CATEGORY=="Bedded Hospital").sum())
print("  cross-tab sample of Community Health Centre names:",
      df.loc[df.SUB_CATEGORY=="Community Health Centre","MASTER_FACILITY_DESC"].value_counts().head(15).to_dict())
print("  cross-tab sample of Bedded Hospital names:",
      df.loc[df.SUB_CATEGORY=="Bedded Hospital","MASTER_FACILITY_DESC"].value_counts().head(15).to_dict())

print("\n### F. Geocoder cross-check: address_py vs STATE/DISTRICT ###")
apy = df["address_py"].fillna("")
st_ok = [apy.iloc[i].lower().find(str(df["STATE_NAME"].iloc[i]).lower()) >= 0 for i in range(N)]
print("  address_py contains STATE_NAME verbatim:", sum(st_ok), f"({100*sum(st_ok)/N:.2f}%)")
dt_ok = [apy.iloc[i].lower().find(str(df["DISTRICT_NAME"].iloc[i]).lower()) >= 0 for i in range(N)]
print("  address_py contains DISTRICT_NAME verbatim:", sum(dt_ok), f"({100*sum(dt_ok)/N:.2f}%)")
print("  address_py ends with 'India':", apy.str.strip().str.endswith("India").sum())
print("  address_py that are suspiciously short (<20 chars):", (apy.str.len()<20).sum())
print("   e.g.", apy[apy.str.len()<20].value_counts().head(10).to_dict())
# state extracted from address_py (2nd-to-last-ish token)
def st_from(a):
    parts=[p.strip() for p in a.split(",")]
    return parts[-2] if len(parts)>=2 and parts[-1]=="India" else (parts[-3] if len(parts)>=3 else "")
apy_state = apy.map(st_from)
mismatch_state = (apy_state.str.lower() != df["STATE_NAME"].str.lower())
print("  rows where geocoded state token != STATE_NAME:", mismatch_state.sum())
print("   top mismatch pairs:", Counter(zip(df.loc[mismatch_state,"STATE_NAME"], apy_state[mismatch_state])).most_common(15))

print("\n### G. ADDRESS quality ###")
addr = df["ADDRESS"].fillna("")
same_as_hab = (addr.str.lower().str.strip() == df["HABITATION_NAME"].str.lower().str.strip())
print("  ADDRESS identical (case-insens) to HABITATION_NAME:", same_as_hab.sum(), f"({100*same_as_hab.sum()/N:.2f}%)")
same_as_blk = (addr.str.lower().str.strip() == df["BLOCK_NAME"].str.lower().str.strip())
print("  ADDRESS identical to BLOCK_NAME:", same_as_blk.sum())
print("  ADDRESS len<=12:", (addr.str.len()<=12).sum(), f"({100*(addr.str.len()<=12).sum()/N:.2f}%)")
print("  ADDRESS containing a digit:", addr.str.contains(r"\d").sum())
print("  ADDRESS with embedded newline:", addr.str.contains("\n").sum())

print("\n### H. PII / contact scan across all text cols ###")
phone = re.compile(r"(?<!\d)(?:\+?91[\-\s]?)?[6-9]\d{9}(?!\d)")
email = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
for c in df.columns:
    s = df[c].fillna("").astype(str)
    ph = s.str.contains(phone).sum(); em = s.str.contains(email).sum()
    if ph or em:
        print(f"  {c}: phone-like={ph} email-like={em}")
        print("    e.g.", s[s.str.contains(phone)|s.str.contains(email)].head(4).tolist())
drname = low.str.contains(r"\bdr\.?\s|\bdoctor\b", regex=True, na=False)
print("  facility names containing a personal 'Dr <name>' pattern:", drname.sum(), f"({100*drname.sum()/N:.2f}%)")
print("   e.g.", df.loc[drname,"MASTER_FACILITY_DESC"].head(6).tolist())

print("\n### I. Whitespace / casing / encoding hygiene ###")
for c in df.columns:
    s = df[c].dropna().astype(str)
    lead = (s != s.str.strip()).sum()
    dbl = s.str.contains(r"\s{2,}").sum()
    nonascii = s.str.contains(r"[^\x00-\x7F]").sum()
    if lead or dbl or nonascii:
        print(f"  {c}: untrimmed={lead} double-space={dbl} non-ascii={nonascii}")
        if nonascii:
            print("    non-ascii e.g.", s[s.str.contains(r'[^\x00-\x7F]')].head(3).tolist())

print("\n### J. State/District spelling ###")
print("  distinct STATE_NAME (sorted):")
for s in sorted(df["STATE_NAME"].dropna().unique()): print("   ", repr(s))
print("  districts with digits or odd chars:",
      df.loc[df["DISTRICT_NAME"].fillna("").str.contains(r"[^A-Za-z .'()\-&]"), "DISTRICT_NAME"].unique()[:20])
print("  ALL-CAPS district names:", sorted({d for d in df['DISTRICT_NAME'].dropna().unique() if d.isupper()})[:20])
print("  n districts per state:", df.groupby("STATE_NAME")["DISTRICT_NAME"].nunique().sort_values(ascending=False).to_dict())
