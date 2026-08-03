"""NHP EDA step 6: content semantics — is this medical colleges? ER readiness."""
import re, json
from collections import Counter
import pandas as pd, numpy as np

SRC = "/Users/ankitraj2/asar master data/8_JULY_23_SRK_NHP_validated_and_standardized.csv"
NORM = lambda s: re.sub(r"\s+", " ", s).strip() if isinstance(s, str) else s
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = df.rename(columns={"S.\n  No.": "S. No."}).drop(
    columns=[c for c in df.columns if c.startswith("Unnamed")]).dropna(how="all").reset_index(drop=True)
hn = df["Hospital Name"].map(NORM)

print("=== facility-type evidence from Hospital Name (n=%d) ===" % len(hn))
pats = {
    "medical college": r"medical college",
    "college (any)": r"\bcollege\b",
    "institute of medical sciences": r"institute of medical sciences",
    "AIIMS": r"all india institute of medical sciences|\bAIIMS\b",
    "academy": r"\bacademy\b",
    "institute (any)": r"\binstitut",
    "university": r"\buniversity\b",
    "school of medicine": r"school of medic",
    "hospital": r"\bhospital\b",
    "ESIC": r"\bESIC\b|employees state insurance",
    "dental": r"\bdental\b",
    "ayurved/homoeo/unani": r"ayurved|homoeo|homeo|unani|siddha",
}
for k, p in pats.items():
    print(f"   {k:32s} {int(hn.str.contains(p, case=False, regex=True).sum()):4d}"
          f"  ({100*hn.str.contains(p, case=False, regex=True).mean():.1f}%)")
none_of = ~hn.str.contains(r"college|institut|academy|university|school of medic|\bAIIMS\b|ESIC",
                           case=False, regex=True)
print("   names matching NONE of college/institute/academy/university/school:", int(none_of.sum()))
print("   examples:", list(hn[none_of].head(20)))

print("\n=== Admission Intake sanity (MBBS seat intake?) ===")
ai = pd.to_numeric(df["Admission Intake"], errors="coerce")
print("  values:", dict(sorted(Counter(ai.dropna().astype(int)).items())))
print("  multiples of 50:", int((ai % 50 == 0).sum()), "of", int(ai.notna().sum()))
print("  rows with intake==0:", int((ai == 0).sum()))
print(df.loc[ai == 0, ["S. No.", "Hospital Name", "State", "Type"]].to_string())

print("\n=== beds ===")
bd = pd.to_numeric(df["No. of beds in attached Hospital"], errors="coerce")
print("  fill:", int(df["No. of beds in attached Hospital"].notna().sum()), "/", len(df),
      f"({100*df['No. of beds in attached Hospital'].notna().mean():.2f}%)")
print("  numeric-parseable:", int(bd.notna().sum()))
print("  percentiles:", {q: float(bd.quantile(q)) for q in [0, .05, .25, .5, .75, .95, .99, 1]})
print("  beds==0 rows:")
print(df.loc[bd == 0, ["S. No.", "Hospital Name", "State", "Admission Intake"]].to_string())
print("  top 5 beds:")
print(df.loc[bd.nlargest(5).index, ["S. No.", "Hospital Name", "No. of beds in attached Hospital"]].to_string())
print("  bad values rows:")
bad = df["No. of beds in attached Hospital"].notna() & bd.isna()
print(df.loc[bad, ["S. No.", "Hospital Name", "No. of beds in attached Hospital"]].to_string())
print("  beds/intake ratio p50:", float((bd/ai).median()))
print("  rows where beds < intake:", int((bd < ai).sum()))

print("\n=== fill rate for the 3 all-empty columns (verify) ===")
for c in ["Accrediation", "Domains", "Contact"]:
    ser = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False)[c]
    print(f"   {c}: distinct raw values = {set(ser.unique())}  non-blank={int((ser.str.strip()!='').sum())}")

print("\n=== STATE list (exact, normalized) ===")
st = df["State"].map(NORM)
for k, v in st.value_counts().items():
    print(f"   {v:4d}  {k!r}")
print("distinct:", st.nunique())

print("\n=== address_py duplicates ===")
ap = df["address_py"].map(NORM)
d = ap[ap.duplicated(keep=False)].sort_values()
print(df.loc[d.index, ["S. No.", "Hospital Name", "City", "address_py"]].to_string()[:3000])

print("\n=== Standardized Address structure ===")
sa = df["Standardized Address"].map(NORM)
print("  commas per value:", dict(Counter(sa.str.count(",")).most_common()))
print("  matches '<name>, <city>, <state>, India, <pin>.':",
      int(sa.str.match(r"^.+, .+, .+, India, \d{3} ?\d{3}\.$").sum()))
print("  examples of NON-matching:")
nm = ~sa.str.match(r"^.+, .+, .+, India, \d{3} ?\d{3}\.$")
print(list(sa[nm].head(5)))

print("\n=== ER readiness ===")
lat = pd.to_numeric(df["Latitude"], errors="coerce"); lon = pd.to_numeric(df["Longitude"], errors="coerce")
geo_ok = lat.between(6, 38) & lon.between(68, 98)
print("  has_name:", int(hn.notna().sum()), "/", len(df))
print("  has usable geo:", int(geo_ok.sum()), f"({100*geo_ok.mean():.2f}%)")
print("  has state:", int(df['State'].notna().sum()))
print("  has city:", int(df['City'].notna().sum()))
print("  has pincode(6d):", int(df['Postcode'].dropna().str.replace(' ','').str.fullmatch(r'\d{6}').sum()))
print("  has DISTRICT column:", "District" in df.columns)
unmatchable = (~geo_ok) & (df["City"].isna())
print("  rows with neither geo nor city (unmatchable):", int(unmatchable.sum()))
generic = hn.str.casefold().isin({"government medical college", "medical college", "esic",
                                  "all india institute of medical sciences",
                                  "gmers medical college", "autonomous state medical college",
                                  "autonomous state medical college society"})
print("  rows with a GENERIC (non-discriminating) name:", int(generic.sum()),
      f"({100*generic.mean():.2f}%)")
print("  of those, how many still have unique geo:", int((generic & geo_ok).sum()))
