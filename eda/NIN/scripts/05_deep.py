"""Step 5: Notes content, SrNo semantics, Excel artifacts, ER readiness, PII scan."""
import pandas as pd, numpy as np, re, json
pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 120)

SRC = "/Users/ankitraj2/asar master data/22_MAY_22_AP_NIN.csv"
READ = dict(encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = pd.read_csv(SRC, **READ)
IDX = df.columns[0]
data_cols = [c for c in df.columns if c != IDX]
d = df.loc[~df[data_cols].isna().all(axis=1)].copy()
N = len(d)

print("=== NOTES: complete distinct list with counts ===")
print(d["Notes"].str.strip().value_counts().to_string())
nt = d["Notes"].str.strip().str.lower()
nf = nt.isin(["nf", "not found"]) | nt.str.startswith("nf,", na=False) | nt.str.startswith("nf ", na=False)
print("\n'not found'-family notes:", int(nf.sum()))
print("'listed as' notes:", int(nt.str.contains("listed as|labelled as|label as", na=False).sum()))
print("Notes rows that also have a Manual Health Facility Name:", int((d['Notes'].notna() & d['Manual Health Facility Name'].notna()).sum()))
print("\nNotes vs geo validity:")
lat = pd.to_numeric(d["latitude"], errors="coerce"); lon = pd.to_numeric(d["longitude"], errors="coerce")
in_bbox = lat.between(6, 38) & lon.between(68, 98)
print("  NF rows with valid geo:", int((nf & in_bbox).sum()), "of", int(nf.sum()))
print("  NF rows with lat==0:", int((nf & (lat == 0)).sum()))
print("\n'NF' rows sample:")
print(d.loc[nf, ["Health Facility Name", "Manual Health Facility Name", "Notes", "latitude", "longitude", "State_Name"]].head(12).to_string())

print("\n=== SrNo semantics ===")
sr = pd.to_numeric(d["SrNo"], errors="coerce")
print("min/max:", int(sr.min()), int(sr.max()), "| n rows:", N, "| coverage of 1..max:", f"{N/sr.max()*100:.2f}%")
print("monotonic increasing with file order:", bool(sr.is_monotonic_increasing))
print("SrNo quantiles:", sr.quantile([0, .1, .25, .5, .75, .9, 1]).astype(int).to_dict())
print("gaps: largest 10 consecutive-row jumps:")
j = sr.diff().sort_values(ascending=False).head(10)
print(j.to_string())
# does SrNo block correlate with state?
d["_srbin"] = pd.cut(sr, bins=[0, 1000, 5000, 20000, 50000, 100000, 200000])
print(pd.crosstab(d["_srbin"], d["State_Name"]).T.sort_values(by=d["_srbin"].cat.categories[0], ascending=False).head(12).to_string())

print("\n=== Excel / export artifacts ===")
for c in data_cols:
    s = d[c].dropna()
    bad = s[s.str.contains(r"#REF!|#N/A|#VALUE!|#DIV/0!|#NAME\?", regex=True, na=False)]
    if len(bad):
        print(f"  {c}: {len(bad)} excel-error values -> {bad.value_counts().to_dict()}  rows {bad.index.tolist()[:5]}")
print("  literal '\\N' (MySQL NULL marker) total cells:", int(sum((d[c] == "\\N").sum() for c in data_cols)))
print("  cells containing literal backslash-n newline:", int(sum(d[c].str.contains(r"\\\n", regex=True, na=False).sum() for c in data_cols)))

print("\n=== PII scan ===")
ll = d["landline_number"].dropna().str.strip()
digits = ll.str.replace(r"\D", "", regex=True)
print("landline_number: non-null", len(ll))
print("  digit-length distribution:", digits.str.len().value_counts().sort_index().head(20).to_dict())
mob = digits[(digits.str.len() == 10) & digits.str[0].isin(list("6789"))]
print("  looks like a 10-digit MOBILE number:", len(mob), f"({len(mob)/len(ll)*100:.1f}% of non-null)")
print("  contains multiple numbers (comma/slash):", int(ll.str.contains(r"[,/]", na=False).sum()))
print("  examples:", ll.sample(8, random_state=3).tolist())
# email
for c in data_cols:
    n = int(d[c].str.contains(r"[\w\.]+@[\w\.]+", regex=True, na=False).sum())
    if n: print(f"  emails in {c}: {n}")
# person-name-looking cols
print("  Coder distinct raw:", sorted(d['Coder'].dropna().unique().tolist()))
print("  'Dr.' in facility name:", int(d['Health Facility Name'].str.contains(r"\bDr\.?\b", case=False, regex=True, na=False).sum()))
print("   examples:", d.loc[d['Health Facility Name'].str.contains(r"\bDr\.?\b", case=False, na=False), 'Health Facility Name'].head(6).tolist())

print("\n=== ER readiness ===")
name_ok = d["Health Facility Name"].notna() & (d["Health Facility Name"].str.strip().str.len() >= 3)
dist_ok = d["District_Name"].notna() & (~d["District_Name"].str.strip().isin(["\\N", "-", "0"]))
geo_ok = in_bbox
print("has usable name:", int(name_ok.sum()), f"{name_ok.mean()*100:.2f}%")
print("has usable district:", int(dist_ok.sum()), f"{dist_ok.mean()*100:.2f}%")
print("has valid geo:", int(geo_ok.sum()), f"{geo_ok.mean()*100:.2f}%")
print("has pincode:", int(d['pincode'].notna().sum()), f"{d['pincode'].notna().mean()*100:.2f}%")
full = name_ok & dist_ok & geo_ok
print("name+district+geo all present:", int(full.sum()), f"{full.mean()*100:.2f}%")
print("name+district (no geo required):", int((name_ok & dist_ok).sum()), f"{(name_ok & dist_ok).mean()*100:.2f}%")
unmatch = ~(name_ok & dist_ok)
print("unmatchable (missing name or district):", int(unmatch.sum()), f"{unmatch.mean()*100:.2f}%")
# generic/uninformative names
gen = d["Health Facility Name"].str.strip().str.lower().isin(
    ["community health center", "community health centre", "chc", "phc", "primary health center",
     "primary health centre", "sadar hospital", "district hospital", "civil hospital", "government hospital",
     "govt hospital", "others", "sub district hospital", "dispensary"])
print("purely generic facility names (no place token):", int(gen.sum()), f"{gen.mean()*100:.2f}%")
# name is just a place name (no facility keyword)
kw = r"hospital|health|chc|phc|uhc|sdh|dispensar|clinic|centre|center|nursing|medical|maternity|ppu|hosp|aspatal|asptl"
nokw = ~d["Health Facility Name"].str.contains(kw, case=False, regex=True, na=False)
print("names with NO facility-type keyword (bare place names):", int(nokw.sum()), f"{nokw.mean()*100:.2f}%")
print("  examples:", d.loc[nokw, "Health Facility Name"].head(15).tolist())

print("\n=== the 13 near-exact dupes (ignoring SrNo/NFN) ===")
nokey = [c for c in data_cols if c not in ("SrNo", "Non filled numbering")]
dup = d[d.duplicated(subset=nokey, keep=False)].sort_values(nokey[:3])
print(dup[["SrNo", "Health Facility Name", "State_Name", "District_Name", "latitude", "longitude", "Facility Type"]].to_string())

print("\n=== Facility Type x State (sanity) ===")
print(d["Facility Type"].value_counts().to_dict())
print("\n=== state naming anomalies ===")
print("Telengana (misspelling of Telangana):", int((d['State_Name'] == 'Telengana').sum()))
print("Kerala rows (suspiciously 1):", d.loc[d['State_Name'] == 'Kerala', ['Health Facility Name','District_Name','Facility Type','latitude','longitude']].to_string())
