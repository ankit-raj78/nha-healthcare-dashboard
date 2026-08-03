#!/usr/bin/env python
"""
Deep dive + PHC-vs-CHC cross analysis.

    .venv/bin/python eda/PHC/scripts/deep_and_cross.py

Answers:
  - do BLOCK_ID / HAB_ID / FACILITY_ID form a shared namespace across the two files?
  - is a given BLOCK_ID / HAB_ID internally consistent with one state+district?
  - is any row present in both files (same facility)?
  - are FAC_CATEGO values disjoint?
  - geo internal consistency (distance from district median)
  - name-token leakage (PHC-named rows in CHC and vice versa)
Everything printed; no files written except a JSON side-car of cross stats.
"""
import json
import os
import re
import unicodedata

import numpy as np
import pandas as pd

ROOT = "/Users/ankitraj2/asar master data"
KW = dict(encoding="utf-8", dtype=str, keep_default_na=False, na_values=[], sep=",")


def norm_name(s):
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


phc = pd.read_csv(os.path.join(ROOT, "21_June_2024_AM_PHC.csv"), **KW)
chc = pd.read_csv(os.path.join(ROOT, "21_June_2024_AM_CHC.csv"), **KW)
for d in (phc, chc):
    d["_nn"] = d["FAC_DESC"].map(norm_name)
    d["_lon"] = pd.to_numeric(d["Longitude"])
    d["_lat"] = pd.to_numeric(d["Latitude"])

res = {}
P = print

P("=" * 90)
P("SCHEMA IDENTITY")
P("=" * 90)
P("PHC cols:", list(phc.columns[:9]))
P("CHC cols:", list(chc.columns[:9]))
P("identical column order & names:", list(phc.columns[:9]) == list(chc.columns[:9]))
res["schema_identical"] = list(phc.columns[:9]) == list(chc.columns[:9])

# ---------------------------------------------------------------- ID namespace
P("\n" + "=" * 90)
P("ID NAMESPACE: shared or colliding?")
P("=" * 90)
for c in ("FACILITY_ID", "HAB_ID", "BLOCK_ID"):
    a, b = set(phc[c]), set(chc[c])
    inter = a & b
    pa = pd.to_numeric(phc[c]); pb = pd.to_numeric(chc[c])
    P(f"\n--- {c} ---")
    P(f"  PHC distinct={len(a)}  range=[{int(pa.min())}, {int(pa.max())}]")
    P(f"  CHC distinct={len(b)}  range=[{int(pb.min())}, {int(pb.max())}]")
    P(f"  intersection size = {len(inter)}  "
      f"({round(100*len(inter)/len(b),2)}% of CHC distinct values)")
    res[f"{c}_phc_distinct"] = len(a)
    res[f"{c}_chc_distinct"] = len(b)
    res[f"{c}_intersection"] = len(inter)
    res[f"{c}_phc_range"] = [int(pa.min()), int(pa.max())]
    res[f"{c}_chc_range"] = [int(pb.min()), int(pb.max())]
    if inter and c != "BLOCK_ID":
        sample = sorted(inter)[:3]
        for s in sample:
            P(f"  collision on {c}={s}:")
            P("    PHC:", phc[phc[c] == s][["STATE_NAME", "DISTRICT_NAME", "BLOCK_ID",
                                            "HAB_ID", "FACILITY_ID", "FAC_DESC",
                                            "Longitude", "Latitude"]].to_string(index=False))
            P("    CHC:", chc[chc[c] == s][["STATE_NAME", "DISTRICT_NAME", "BLOCK_ID",
                                            "HAB_ID", "FACILITY_ID", "FAC_DESC",
                                            "Longitude", "Latitude"]].to_string(index=False))

# For colliding FACILITY_IDs, do the two rows describe the same place?
P("\n--- Do colliding FACILITY_IDs point at the same physical place? ---")
inter_fid = sorted(set(phc["FACILITY_ID"]) & set(chc["FACILITY_ID"]))
P(f"n colliding FACILITY_ID = {len(inter_fid)}")
if inter_fid:
    a = phc[phc["FACILITY_ID"].isin(inter_fid)].set_index("FACILITY_ID")
    b = chc[chc["FACILITY_ID"].isin(inter_fid)].set_index("FACILITY_ID")
    j = a.join(b, lsuffix="_p", rsuffix="_c")
    same_state = (j["STATE_NAME_p"] == j["STATE_NAME_c"])
    same_dist = (j["DISTRICT_NAME_p"] == j["DISTRICT_NAME_c"])
    same_pt = (j["Longitude_p"] == j["Longitude_c"]) & (j["Latitude_p"] == j["Latitude_c"])
    dkm = 111.0 * np.hypot(j["_lat_p"] - j["_lat_c"],
                           (j["_lon_p"] - j["_lon_c"]) * np.cos(np.radians(j["_lat_p"])))
    P(f"  same STATE_NAME:    {int(same_state.sum())}/{len(j)}")
    P(f"  same DISTRICT_NAME: {int(same_dist.sum())}/{len(j)}")
    P(f"  identical lon/lat:  {int(same_pt.sum())}/{len(j)}")
    P(f"  distance km: min={dkm.min():.2f} median={dkm.median():.2f} "
      f"mean={dkm.mean():.2f} max={dkm.max():.2f}")
    P(f"  within 1 km: {int((dkm < 1).sum())}   within 25 km: {int((dkm < 25).sum())}")
    res["colliding_fid_same_state"] = int(same_state.sum())
    res["colliding_fid_same_district"] = int(same_dist.sum())
    res["colliding_fid_identical_point"] = int(same_pt.sum())
    res["colliding_fid_median_km"] = round(float(dkm.median()), 2)
    P("\n  sample 8 collisions side by side:")
    P(j.head(8)[["STATE_NAME_p", "DISTRICT_NAME_p", "FAC_DESC_p", "Longitude_p", "Latitude_p",
                 "STATE_NAME_c", "DISTRICT_NAME_c", "FAC_DESC_c", "Longitude_c",
                 "Latitude_c"]].to_string())

# HAB_ID collisions - same habitation?
P("\n--- Colliding HAB_IDs: same habitation? ---")
inter_hab = sorted(set(phc["HAB_ID"]) & set(chc["HAB_ID"]))
P(f"n colliding HAB_ID = {len(inter_hab)}")
if inter_hab:
    ha = phc[phc["HAB_ID"].isin(inter_hab)].groupby("HAB_ID").first()
    hb = chc[chc["HAB_ID"].isin(inter_hab)].groupby("HAB_ID").first()
    hj = ha.join(hb, lsuffix="_p", rsuffix="_c")
    ss = (hj["STATE_NAME_p"] == hj["STATE_NAME_c"])
    sd = (hj["DISTRICT_NAME_p"] == hj["DISTRICT_NAME_c"])
    sb = (hj["BLOCK_ID_p"] == hj["BLOCK_ID_c"])
    dkm = 111.0 * np.hypot(hj["_lat_p"] - hj["_lat_c"],
                           (hj["_lon_p"] - hj["_lon_c"]) * np.cos(np.radians(hj["_lat_p"])))
    P(f"  same STATE:    {int(ss.sum())}/{len(hj)}")
    P(f"  same DISTRICT: {int(sd.sum())}/{len(hj)}")
    P(f"  same BLOCK_ID: {int(sb.sum())}/{len(hj)}")
    P(f"  distance km: median={dkm.median():.2f} p90={dkm.quantile(.9):.2f} max={dkm.max():.2f}")
    P(f"  within 10 km: {int((dkm < 10).sum())}/{len(hj)}")
    res["colliding_hab_same_district"] = int(sd.sum())
    res["colliding_hab_n"] = len(hj)
    res["colliding_hab_median_km"] = round(float(dkm.median()), 2)
    P("\n  sample 8:")
    P(hj.head(8)[["STATE_NAME_p", "DISTRICT_NAME_p", "BLOCK_ID_p", "FAC_DESC_p",
                  "STATE_NAME_c", "DISTRICT_NAME_c", "BLOCK_ID_c", "FAC_DESC_c"]].to_string())

# BLOCK_ID consistency
P("\n--- BLOCK_ID: does one BLOCK_ID map to exactly one (state, district)? ---")
both = pd.concat([phc.assign(_src="PHC"), chc.assign(_src="CHC")], ignore_index=True)
for label, d in (("PHC", phc), ("CHC", chc), ("UNION", both)):
    g = d.groupby("BLOCK_ID").agg(n_state=("STATE_NAME", "nunique"),
                                  n_dist=("DISTRICT_NAME", "nunique"))
    P(f"  {label:6s} n_blocks={len(g):5d}  "
      f"blocks spanning >1 state={int((g.n_state > 1).sum()):5d}  "
      f">1 district={int((g.n_dist > 1).sum()):5d}")
    res[f"block_multistate_{label}"] = int((g.n_state > 1).sum())
    res[f"block_multidistrict_{label}"] = int((g.n_dist > 1).sum())
    res[f"n_blocks_{label}"] = int(len(g))

gb = both.groupby("BLOCK_ID").agg(n_state=("STATE_NAME", "nunique"))
bad = gb[gb.n_state > 1].index[:5]
for b in bad:
    P(f"\n  BLOCK_ID={b} spans states:")
    P(both[both["BLOCK_ID"] == b][["_src", "STATE_NAME", "DISTRICT_NAME", "HAB_ID",
                                   "FACILITY_ID", "FAC_DESC"]].to_string(index=False))

P("\n--- HAB_ID: does one HAB_ID map to exactly one district? ---")
gh = both.groupby("HAB_ID").agg(n_state=("STATE_NAME", "nunique"),
                                n_dist=("DISTRICT_NAME", "nunique"),
                                n_block=("BLOCK_ID", "nunique"), n=("FAC_DESC", "size"))
P(f"  UNION n_hab={len(gh)}  spanning >1 state={int((gh.n_state>1).sum())}  "
  f">1 district={int((gh.n_dist>1).sum())}  >1 block={int((gh.n_block>1).sum())}")
res["hab_multidistrict_UNION"] = int((gh.n_dist > 1).sum())
res["hab_multiblock_UNION"] = int((gh.n_block > 1).sum())

# ---------------------------------------------------------------- row overlap
P("\n" + "=" * 90)
P("ROW OVERLAP BETWEEN FILES")
P("=" * 90)
cols9 = list(phc.columns[:9])
merged = phc[cols9].merge(chc[cols9], how="inner", on=cols9)
P(f"exact 9-column row overlap: {len(merged)}")
res["exact_row_overlap"] = int(len(merged))

for key, label in (
    (["Longitude", "Latitude"], "identical coordinate"),
    (["FACILITY_ID"], "FACILITY_ID"),
    (["HAB_ID"], "HAB_ID"),
    (["HAB_ID", "Longitude", "Latitude"], "HAB_ID + coordinate"),
    (["DISTRICT_NAME", "_nn"], "district + normalised name"),
):
    n = len(set(map(tuple, phc[key].values)) & set(map(tuple, chc[key].values)))
    P(f"  shared on {label:32s}: {n}")
    res[f"overlap_{label.replace(' ', '_')}"] = int(n)

# identical coordinate detail
sp = set(map(tuple, phc[["Longitude", "Latitude"]].values))
sc = set(map(tuple, chc[["Longitude", "Latitude"]].values))
common_pts = sp & sc
P(f"\ncoordinate-identical rows detail (n={len(common_pts)}):")
for pt in sorted(common_pts)[:10]:
    m1 = phc[(phc.Longitude == pt[0]) & (phc.Latitude == pt[1])]
    m2 = chc[(chc.Longitude == pt[0]) & (chc.Latitude == pt[1])]
    P(f"  point {pt}")
    P("    PHC:", m1[["STATE_NAME", "DISTRICT_NAME", "HAB_ID", "FACILITY_ID",
                      "FAC_DESC"]].to_string(index=False, header=False))
    P("    CHC:", m2[["STATE_NAME", "DISTRICT_NAME", "HAB_ID", "FACILITY_ID",
                      "FAC_DESC"]].to_string(index=False, header=False))

# near-coincident points (within ~110 m)
P("\nnear-coincident (rounded 3dp ~110m) point overlap:")
p3 = set(zip(phc._lon.round(3), phc._lat.round(3)))
c3 = set(zip(chc._lon.round(3), chc._lat.round(3)))
P(f"  {len(p3 & c3)} shared 3dp cells")
res["overlap_points_3dp"] = int(len(p3 & c3))
p2 = set(zip(phc._lon.round(2), phc._lat.round(2)))
c2 = set(zip(chc._lon.round(2), chc._lat.round(2)))
P(f"  {len(p2 & c2)} shared 2dp cells (~1.1 km) out of {len(c2)} CHC cells")
res["overlap_points_2dp"] = int(len(p2 & c2))

# ---------------------------------------------------------------- FAC_CATEGO
P("\n" + "=" * 90)
P("FAC_CATEGO")
P("=" * 90)
P("PHC:", phc.FAC_CATEGO.value_counts().to_dict())
P("CHC:", chc.FAC_CATEGO.value_counts().to_dict())
P("disjoint:", set(phc.FAC_CATEGO) & set(chc.FAC_CATEGO) == set())
res["fac_catego_phc"] = sorted(set(phc.FAC_CATEGO))
res["fac_catego_chc"] = sorted(set(chc.FAC_CATEGO))
res["fac_catego_disjoint"] = bool(set(phc.FAC_CATEGO).isdisjoint(set(chc.FAC_CATEGO)))

# ---------------------------------------------------------------- name leakage
P("\n" + "=" * 90)
P("NAME/TYPE LEAKAGE (is the file's own label reliable?)")
P("=" * 90)


def tokflags(d):
    n = d["_nn"]
    return pd.DataFrame({
        "phc_like": n.str.contains(r"\b(?:phc|primary)\b", regex=True),
        "chc_like": n.str.contains(r"\b(?:chc|community)\b", regex=True),
        "subcentre": n.str.contains(r"\bsub\b|\bsc\b|\bhsc\b"),
        "hospital": n.str.contains(r"\bhospital\b"),
        "dispensary": n.str.contains(r"\bdispensar"),
        "wellness": n.str.contains(r"wellness|hwc|ayushman"),
        "urban": n.str.contains(r"\buphc\b|\burban\b"),
        "ayush": n.str.contains(r"ayurved|homeo|unani|siddha|ayush"),
        "veterinary": n.str.contains(r"veterinar|animal"),
        "school": n.str.contains(r"school|vidyalay|college"),
        "anganwadi": n.str.contains(r"anganwadi|aanganwadi"),
    })


for label, d in (("PHC", phc), ("CHC", chc)):
    tf = tokflags(d)
    P(f"\n{label} (n={len(d)}):")
    for c in tf.columns:
        P(f"  {c:12s} {int(tf[c].sum()):6d}  ({round(100*tf[c].mean(),2)}%)")
    res[f"{label}_name_tokens"] = {c: int(tf[c].sum()) for c in tf.columns}

P("\nPHC rows whose name says CHC/community (sample 15):")
tfp = tokflags(phc)
P(phc[tfp["chc_like"] & ~tfp["phc_like"]][["STATE_NAME", "DISTRICT_NAME", "FACILITY_ID",
                                           "FAC_DESC"]].head(15).to_string(index=False))
P(f"count = {int((tfp['chc_like'] & ~tfp['phc_like']).sum())}")
res["PHC_rows_named_chc_only"] = int((tfp["chc_like"] & ~tfp["phc_like"]).sum())

P("\nCHC rows whose name says PHC/primary (sample 15):")
tfc = tokflags(chc)
P(chc[tfc["phc_like"] & ~tfc["chc_like"]][["STATE_NAME", "DISTRICT_NAME", "FACILITY_ID",
                                           "FAC_DESC"]].head(15).to_string(index=False))
P(f"count = {int((tfc['phc_like'] & ~tfc['chc_like']).sum())}")
res["CHC_rows_named_phc_only"] = int((tfc["phc_like"] & ~tfc["chc_like"]).sum())

P("\nrows whose name matches NEITHER phc-like nor chc-like:")
for label, tf, d in (("PHC", tfp, phc), ("CHC", tfc, chc)):
    m = ~tf["phc_like"] & ~tf["chc_like"]
    P(f"  {label}: {int(m.sum())} ({round(100*m.mean(),2)}%)")
    P("   sample:", d[m]["FAC_DESC"].head(20).tolist())
    res[f"{label}_name_neither"] = int(m.sum())

# ---------------------------------------------------------------- geo consistency
P("\n" + "=" * 90)
P("GEO INTERNAL CONSISTENCY (distance from own district median point)")
P("=" * 90)
for label, d in (("PHC", phc), ("CHC", chc)):
    g = d.groupby(["STATE_NAME", "DISTRICT_NAME"])[["_lon", "_lat"]].transform("median")
    dkm = 111.0 * np.hypot(d["_lat"] - g["_lat"],
                           (d["_lon"] - g["_lon"]) * np.cos(np.radians(d["_lat"])))
    P(f"\n{label}: distance from district median (km)")
    P("  " + str({f"p{int(q*100)}": round(float(dkm.quantile(q)), 1)
                  for q in (0.5, 0.9, 0.99)}) + f" max={dkm.max():.1f}")
    for thr in (100, 200, 500):
        P(f"  > {thr} km from own district median: {int((dkm > thr).sum())}")
        res[f"{label}_geo_gt{thr}km_from_district_median"] = int((dkm > thr).sum())
    worst = dkm.nlargest(8).index
    P("  worst offenders:")
    P(d.loc[worst, ["STATE_NAME", "DISTRICT_NAME", "FACILITY_ID", "FAC_DESC",
                    "Longitude", "Latitude"]].assign(km=dkm[worst].round(0)).to_string(index=False))

# state-level: point inside claimed state? use union-derived state median as crude proxy
P("\nSTATE-LEVEL: rows > 600 km from own state median point")
for label, d in (("PHC", phc), ("CHC", chc)):
    g = d.groupby("STATE_NAME")[["_lon", "_lat"]].transform("median")
    dkm = 111.0 * np.hypot(d["_lat"] - g["_lat"],
                           (d["_lon"] - g["_lon"]) * np.cos(np.radians(d["_lat"])))
    P(f"  {label}: {int((dkm > 600).sum())} rows")
    res[f"{label}_geo_gt600km_from_state_median"] = int((dkm > 600).sum())

# ---------------------------------------------------------------- 'Unknown' district
P("\n" + "=" * 90)
P("'Unknown' DISTRICT_NAME and other placeholder-looking values")
P("=" * 90)
for label, d in (("PHC", phc), ("CHC", chc)):
    m = d["DISTRICT_NAME"].str.lower().isin(["unknown", "na", "n/a", "null", "-", ""])
    P(f"{label}: {int(m.sum())} rows with placeholder district")
    P(d[m][["STATE_NAME", "DISTRICT_NAME", "BLOCK_ID", "HAB_ID", "FACILITY_ID",
            "FAC_DESC", "Longitude", "Latitude"]].to_string(index=False))
    res[f"{label}_placeholder_district_rows"] = int(m.sum())
    # single-character / ultra-short names
    s = d["FAC_DESC"].str.len() <= 2
    P(f"{label}: FAC_DESC length <=2 : {int(s.sum())}")
    P(d[s][["STATE_NAME", "DISTRICT_NAME", "FACILITY_ID", "FAC_DESC"]].to_string(index=False))
    res[f"{label}_name_len_le2"] = int(s.sum())

# ---------------------------------------------------------------- state naming
P("\n" + "=" * 90)
P("STATE NAME vocabulary comparison / LGD deviations")
P("=" * 90)
sp_, sc_ = set(phc.STATE_NAME), set(chc.STATE_NAME)
P("PHC-only states:", sorted(sp_ - sc_))
P("CHC-only states:", sorted(sc_ - sp_))
P("shared:", len(sp_ & sc_))
LGD36 = {
    "Andaman And Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar",
    "Chandigarh", "Chhattisgarh", "Dadra And Nagar Haveli And Daman And Diu", "Delhi", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jammu And Kashmir", "Jharkhand", "Karnataka",
    "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
}
P("\nstates in files NOT matching the 36 LGD state/UT names verbatim:")
P("  PHC:", sorted(sp_ - LGD36))
P("  CHC:", sorted(sc_ - LGD36))
P("\nLGD states/UTs entirely ABSENT from PHC:", sorted(LGD36 - sp_))
P("LGD states/UTs entirely ABSENT from CHC:", sorted(LGD36 - sc_))
res["states_absent_PHC"] = sorted(LGD36 - sp_)
res["states_absent_CHC"] = sorted(LGD36 - sc_)
res["states_nonstandard_PHC"] = sorted(sp_ - LGD36)
res["states_nonstandard_CHC"] = sorted(sc_ - LGD36)

# districts truncated at 25
P("\ntruncated district values (len==25 with trailing '*'):")
for label, d in (("PHC", phc), ("CHC", chc)):
    t = d[d.DISTRICT_NAME.str.endswith("*")]
    P(f"  {label}: {len(t)} rows, values={sorted(t.DISTRICT_NAME.unique())}")
    res[f"{label}_truncated_district_rows"] = int(len(t))

# ---------------------------------------------------------------- ER simulation
P("\n" + "=" * 90)
P("ER BLOCKING SIMULATION: how discriminative is (district, name)?")
P("=" * 90)
for label, d in (("PHC", phc), ("CHC", chc)):
    n = len(d)
    for keycols, kl in (
        (["STATE_NAME", "DISTRICT_NAME"], "state+district"),
        (["STATE_NAME", "DISTRICT_NAME", "_nn"], "state+district+name"),
        (["BLOCK_ID"], "block_id"),
        (["BLOCK_ID", "_nn"], "block_id+name"),
        (["HAB_ID"], "hab_id"),
    ):
        g = d.groupby(keycols).size()
        singles = int((g == 1).sum())
        P(f"  {label} {kl:24s} groups={len(g):6d}  singleton_groups={singles:6d}  "
          f"rows_in_singletons={singles} ({round(100*singles/n,2)}%)  "
          f"max_group={int(g.max())}")
        res[f"{label}_block_{kl.replace('+','_')}_singleton_pct"] = round(100 * singles / n, 2)

# geo blocking: how many rows have a unique 500 m cell
P("\ngeo-cell uniqueness (round to 2dp ~ 1.1 km):")
for label, d in (("PHC", phc), ("CHC", chc)):
    cell = list(zip(d._lon.round(2), d._lat.round(2)))
    vc = pd.Series(cell).value_counts()
    P(f"  {label}: {len(vc)} cells; rows in a singleton cell = "
      f"{int((vc==1).sum())} ({round(100*(vc==1).sum()/len(d),2)}%); max cell = {int(vc.max())}")
    res[f"{label}_geocell_singleton_pct"] = round(100 * (vc == 1).sum() / len(d), 2)

# what fraction of rows have a name that adds ANY information beyond the type
P("\nname informativeness after stripping type words:")
STRIP = re.compile(
    r"\b(?:phc|chc|primary|community|health|helth|heath|healt|hlth|centre|center|"
    r"cent|centr|ctr|cntr|sub|sc|hsc|phsc|hc|govt|government|hospital|hosp|care|"
    r"unit|new|the|of|and|comprehensive|rural|urban|main|public|additional|add|"
    r"referral|block|bphc|aphc|uphc|mphc|shc|hwc|wellness|dispensary|clinic|"
    r"cum|no|at|in|is|a|medical|comunity|cummunity|primery|primry|helath|"
    r"heath|hospitalc|building|bed|beded|bedded)\b")
for label, d in (("PHC", phc), ("CHC", chc)):
    resid = d["_nn"].str.replace(STRIP, " ", regex=True).str.replace(r"\d+", " ", regex=True)
    resid = resid.str.replace(r"\s+", " ", regex=True).str.strip()
    empt = resid.eq("")
    P(f"  {label}: {int(empt.sum())} rows ({round(100*empt.mean(),2)}%) have NO residual token "
      f"after removing facility-type words -> name carries zero place information")
    P("   sample residuals:", resid[~empt].head(15).tolist())
    res[f"{label}_pct_name_zero_information"] = round(100 * float(empt.mean()), 2)
    # of those with residual, is the residual unique within district?
    sub = d[~empt].copy()
    sub["_res"] = resid[~empt]
    g = sub.groupby(["STATE_NAME", "DISTRICT_NAME", "_res"]).size()
    P(f"   of the {len(sub)} rows WITH a residual place token, "
      f"{int((g==1).sum())} form a unique (state,district,residual) key "
      f"({round(100*(g==1).sum()/len(d),2)}% of all rows)")
    res[f"{label}_pct_rows_uniquely_keyed_by_district_plus_placeword"] = round(
        100 * (g == 1).sum() / len(d), 2)

P("\n" + "=" * 90)
P("CROSS STATS JSON")
P("=" * 90)
outp = os.path.join(ROOT, "eda", "PHC", "cross_stats.json")
with open(outp, "w") as fh:
    json.dump(res, fh, indent=2, default=str)
P(json.dumps(res, indent=2, default=str))
P(">>> wrote", outp)
