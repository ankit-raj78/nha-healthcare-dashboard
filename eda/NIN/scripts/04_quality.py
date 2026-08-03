"""Step 4: sentinels, geo quality, pincode validity, altitude, auto-vs-manual pairs, duplicates."""
import pandas as pd, numpy as np, re, json
pd.set_option("display.width", 260)

SRC = "/Users/ankitraj2/asar master data/22_MAY_22_AP_NIN.csv"
READ = dict(encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = pd.read_csv(SRC, **READ)
IDX = df.columns[0]
data_cols = [c for c in df.columns if c != IDX]
d = df.loc[~df[data_cols].isna().all(axis=1)].copy()
N = len(d)
print("N =", N)

# ---------------- sentinel audit -------------------------------------------
SENT = [r"\N", "-", "0", "NA", "N/A", "na", "null", "NULL", "nan", ""]
print("\n=== sentinel-value counts per column ===")
rows = []
for c in data_cols:
    s = d[c]
    counts = {v: int((s == v).sum()) for v in SENT if (s == v).sum() > 0}
    ws = int((s.notna() & (s.str.strip() == "")).sum())
    if counts or ws:
        rows.append((c, counts, ws))
for c, counts, ws in rows:
    print(f"  {c:30s} {counts}  whitespace_only={ws}")

# has leading/trailing whitespace
print("\n=== columns with untrimmed whitespace ===")
for c in data_cols:
    n = int((d[c].notna() & (d[c] != d[c].str.strip())).sum())
    if n:
        print(f"  {c:30s} {n}")

# ---------------- geo -------------------------------------------------------
print("\n=== latitude / longitude ===")
lat = pd.to_numeric(d["latitude"], errors="coerce")
lon = pd.to_numeric(d["longitude"], errors="coerce")
print("lat raw non-null:", int(d["latitude"].notna().sum()), "numeric-parseable:", int(lat.notna().sum()))
print("lon raw non-null:", int(d["longitude"].notna().sum()), "numeric-parseable:", int(lon.notna().sum()))
bad_lat = d.loc[d["latitude"].notna() & lat.isna(), ["latitude", "longitude"]]
print("non-numeric latitude values:", bad_lat["latitude"].value_counts().to_dict())
bad_lon = d.loc[d["longitude"].notna() & lon.isna(), ["latitude", "longitude"]]
print("non-numeric longitude values:", bad_lon["longitude"].value_counts().to_dict())
print("lat describe:\n", lat.describe(percentiles=[.01, .05, .5, .95, .99]).to_string())
print("lon describe:\n", lon.describe(percentiles=[.01, .05, .5, .95, .99]).to_string())

both_null = (lat.isna() & lon.isna())
either_null = (lat.isna() | lon.isna())
zero = ((lat == 0) | (lon == 0))
in_bbox = lat.between(6, 38) & lon.between(68, 98)
swapped = (~in_bbox) & lat.between(68, 98) & lon.between(6, 38)
out_bbox = (~in_bbox) & (~either_null) & (~zero) & (~swapped)
print("\nboth null:", int(both_null.sum()))
print("either null (incl unparseable):", int(either_null.sum()))
print("exact zero in lat or lon:", int(zero.sum()))
print("valid in India bbox:", int(in_bbox.sum()), f"({in_bbox.mean()*100:.2f}%)")
print("possibly swapped:", int(swapped.sum()))
print("out of bbox (non-null, non-zero, non-swapped):", int(out_bbox.sum()))
print("\nout-of-bbox examples:")
print(d.loc[out_bbox, ["Health Facility Name", "latitude", "longitude", "State_Name", "District_Name"]].head(15).to_string())
print("\nswapped examples:")
print(d.loc[swapped, ["Health Facility Name", "latitude", "longitude", "State_Name"]].head(10).to_string())

# precision of coords
dec = d.loc[lat.notna(), "latitude"].str.split(".").str[1].fillna("").str.len()
print("\nlatitude decimal-place distribution:", dec.value_counts().sort_index().to_dict())

# duplicated coordinate pairs (shared/copied geo)
pair = d.loc[in_bbox, ["latitude", "longitude"]].astype(str).agg("|".join, axis=1)
pvc = pair.value_counts()
print("\ndistinct valid coord pairs:", pvc.size, "| rows sharing a pair with >=2 rows:", int(pvc[pvc > 1].sum()))
print("top repeated coord pairs:", pvc.head(8).to_dict())

# ---------------- altitude --------------------------------------------------
print("\n=== altitude ===")
alt_raw = d["altitude"]
alt = pd.to_numeric(alt_raw, errors="coerce")
print("non-null raw:", int(alt_raw.notna().sum()), "numeric:", int(alt.notna().sum()))
print("non-numeric values:", alt_raw[alt.isna()].value_counts().to_dict())
print("zero:", int((alt == 0).sum()), f"({(alt==0).mean()*100:.2f}%)")
print("negative:", int((alt < 0).sum()))
nz = alt[alt != 0].dropna()
print("non-zero count:", len(nz))
print(nz.describe(percentiles=[.01, .05, .5, .95, .99]).to_string())
print("altitude>9000 (impossible):", int((alt > 9000).sum()), alt[alt > 9000].tolist()[:10])
# does altitude correlate with geo presence?
print("altitude==0 & valid geo:", int(((alt == 0) & in_bbox).sum()))
print("altitude!=0 & valid geo:", int(((alt != 0) & in_bbox).sum()))
# sanity: highest-altitude rows
top = d.assign(_a=alt).nlargest(8, "_a")[["Health Facility Name", "State_Name", "District_Name", "altitude", "latitude", "longitude"]]
print("highest altitudes:\n", top.to_string())

# ---------------- pincode ---------------------------------------------------
print("\n=== pincode validity ===")
for col in ["pincode", "Manual_Pincode"]:
    s = d[col].dropna().astype(str).str.strip()
    six = s.str.fullmatch(r"\d{6}")
    print(f"{col}: non-null={len(s)}  6-digit={int(six.sum())}  not-6-digit={int((~six).sum())}")
    print("   bad values:", s[~six].value_counts().head(10).to_dict())
    ok = s[six]
    print("   leading digit 0 (invalid for India):", int((ok.str[0] == "0").sum()))
    print("   first-digit distribution:", ok.str[0].value_counts().sort_index().to_dict())

# ---------------- auto vs manual pairs --------------------------------------
print("\n=== AUTO vs MANUAL field pairs ===")
pairs = [("Health Facility Name", "Manual Health Facility Name"),
         ("Address", "Manual_Address"),
         ("pincode", "Manual_Pincode")]
def norm(s):
    return (s.astype(str).str.strip().str.lower()
             .str.replace(r"[^\w\s]", " ", regex=True)
             .str.replace(r"\s+", " ", regex=True).str.strip())
for a, m in pairs:
    A, M = d[a], d[m]
    both = A.notna() & M.notna()
    print(f"\n{a}  vs  {m}")
    print(f"  auto filled  : {int(A.notna().sum())} ({A.notna().mean()*100:.2f}%)")
    print(f"  manual filled: {int(M.notna().sum())} ({M.notna().mean()*100:.2f}%)")
    print(f"  both filled  : {int(both.sum())}")
    print(f"  manual only (auto null): {int((M.notna() & A.isna()).sum())}")
    print(f"  auto only    : {int((A.notna() & M.isna()).sum())}")
    if both.sum():
        exact = (A[both] == M[both]).sum()
        nrm = (norm(A[both]) == norm(M[both])).sum()
        print(f"  identical (exact): {int(exact)} ({exact/both.sum()*100:.2f}% of both-filled)")
        print(f"  identical (normalized): {int(nrm)} ({nrm/both.sum()*100:.2f}%)")
        print(f"  DISAGREE (normalized): {int(both.sum() - nrm)} ({(both.sum()-nrm)/both.sum()*100:.2f}%)")
        dis = d.loc[both & (norm(A) != norm(M)), [a, m]]
        print("  disagreement examples:")
        print(dis.head(12).to_string())
    # is auto a sentinel where manual is filled?
    junk = M.notna() & A.isin(["\\N", "-", "0", "1"])
    print(f"  rows where manual filled and auto is a sentinel (\\N,-,0,1): {int(junk.sum())}")

# ---------------- Manually_added / Coder ------------------------------------
print("\n=== curation workflow ===")
ma = d["Manually_added"].str.strip().str.lower()
print("Manually_added normalized:", ma.value_counts(dropna=False).to_dict())
print("fraction manually added (of all rows):", f"{ma.notna().mean()*100:.2f}%")
co = d["Coder"].str.strip().str.lower()
print("Coder normalized:", co.value_counts(dropna=False).to_dict())
print("distinct coders (normalized):", sorted(co.dropna().unique()))
print("\ncross-tab Coder x Manually_added:")
print(pd.crosstab(co, ma, dropna=False).to_string())
print("\ncoverage overlap of curation markers:")
mk = pd.DataFrame({"NFN": d["Non filled numbering"].notna(), "MHFN": d["Manual Health Facility Name"].notna(),
                   "MAddr": d["Manual_Address"].notna(), "MPin": d["Manual_Pincode"].notna(),
                   "MA": d["Manually_added"].notna(), "Coder": d["Coder"].notna(),
                   "Notes": d["Notes"].notna()})
print(mk.sum().to_dict())
print("any curation marker:", int(mk.any(axis=1).sum()))
print("NFN set == MHFN set:", bool((mk["NFN"] == mk["MHFN"]).all()))
print("combo counts:")
print(mk.value_counts().head(15).to_string())

# ---------------- duplicates ------------------------------------------------
print("\n=== duplicates ===")
core = [c for c in data_cols]
print("exact dupes on ALL data columns:", int(d.duplicated(subset=core).sum()))
nokey = [c for c in data_cols if c not in ("SrNo", "Non filled numbering")]
print("exact dupes ignoring SrNo/NFN:", int(d.duplicated(subset=nokey).sum()))
d["_n"] = norm(d["Health Facility Name"])
for keys, label in [(["_n"], "name only"),
                    (["_n", "District_Name"], "name+district"),
                    (["_n", "latitude", "longitude"], "name+geo"),
                    (["_n", "District_Name", "State_Name"], "name+district+state"),
                    (["latitude", "longitude"], "geo only")]:
    sub = d.dropna(subset=[k for k in keys if k in d.columns])
    n = int(sub.duplicated(subset=keys).sum())
    print(f"  dupes on {label}: {n} ({n/N*100:.2f}%)")
dd = d[d.duplicated(subset=["_n", "District_Name"], keep=False)].sort_values(["_n"])
print("\nexample name+district dupe groups:")
print(dd[["Health Facility Name", "District_Name", "State_Name", "latitude", "longitude", "Facility Type", "SrNo"]].head(20).to_string())

# ---------------- primary key ----------------------------------------------
print("\n=== primary key candidates ===")
for c in [IDX, "SrNo", "Non filled numbering"]:
    s = df[c] if c == IDX else d[c]
    ss = d[c]
    print(f"  {c}: non_null={int(ss.notna().sum())}/{N}  unique_among_nonnull={bool(ss.dropna().is_unique)}  n_distinct={ss.nunique()}")

# ---------------- admin hierarchy -------------------------------------------
print("\n=== admin hierarchy real fill (excluding \\N sentinel) ===")
for c in ["State_Name", "District_Name", "Taluka_Name", "Block_Name"]:
    s = d[c]
    real = s.notna() & (~s.str.strip().isin(["\\N", "-", "0", ""]))
    print(f"  {c}: raw non-null={int(s.notna().sum())} ({s.notna().mean()*100:.2f}%)  real={int(real.sum())} ({real.mean()*100:.2f}%)  distinct_real={s[real].nunique()}")
print("\nState_Name exact distinct list:")
print(json.dumps(sorted(d['State_Name'].dropna().unique().tolist()), ensure_ascii=False))
print("\nDistrict_Name sentinel/dirty check:")
dn = d["District_Name"]
print("  contains backslash-n literal:", int(dn.str.contains(r"\\", regex=True, na=False).sum()))
print("  contains newline:", int(dn.str.contains("\n", na=False).sum()))
print("  values w/ embedded newline:", dn[dn.str.contains("\n", na=False)].unique()[:10].tolist())
print("  trailing 'District' suffix:", int(dn.str.contains(r"District$", na=False).sum()))
print("  examples of those:", dn[dn.str.contains(r"District$", na=False)].unique()[:10].tolist())
print("\nnumber of distinct districts per state (top 8):")
print(d.groupby("State_Name")["District_Name"].nunique().sort_values(ascending=False).head(8).to_string())
