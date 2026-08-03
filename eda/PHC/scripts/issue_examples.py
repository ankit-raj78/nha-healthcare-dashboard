#!/usr/bin/env python
"""Pull concrete row indices + values for every defect cited in issues.md.

    .venv/bin/python eda/PHC/scripts/issue_examples.py
"""
import os
import re
import unicodedata

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)
ROOT = "/Users/ankitraj2/asar master data"
KW = dict(encoding="utf-8", dtype=str, keep_default_na=False, na_values=[], sep=",")


def nn(s):
    s = unicodedata.normalize("NFKD", str(s).lower().strip())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


phc = pd.read_csv(os.path.join(ROOT, "21_June_2024_AM_PHC.csv"), **KW)
chc = pd.read_csv(os.path.join(ROOT, "21_June_2024_AM_CHC.csv"), **KW)
P = print

for label, d in (("PHC", phc), ("CHC", chc)):
    d["_nn"] = d.FAC_DESC.map(nn)
    d["_lon"] = pd.to_numeric(d.Longitude)
    d["_lat"] = pd.to_numeric(d.Latitude)
    n = len(d)
    P("\n" + "#" * 90)
    P(f"# {label}   n={n}")
    P("#" * 90)

    P("\n[A] repeated HAB_ID (same habitation, several facilities) - worst groups")
    vc = d.HAB_ID.value_counts()
    for h in vc[vc > 1].index[:4]:
        P(d[d.HAB_ID == h][["STATE_NAME", "DISTRICT_NAME", "BLOCK_ID", "HAB_ID",
                            "FACILITY_ID", "FAC_DESC", "Longitude", "Latitude"]].to_string())
    P(f"total rows with a repeated HAB_ID: {int(vc[vc>1].sum())} "
      f"({round(100*vc[vc>1].sum()/n,2)}%) over {int((vc>1).sum())} HAB_IDs")

    P("\n[B] near-dupes: same normalised name + identical coordinate")
    k = d._nn + "|" + d.Longitude + "|" + d.Latitude
    grp = k[k.duplicated(keep=False)]
    for key in grp.unique()[:6]:
        P(d[k == key][["STATE_NAME", "DISTRICT_NAME", "HAB_ID", "FACILITY_ID",
                       "FAC_DESC", "Longitude", "Latitude"]].to_string())
    P(f"rows involved: {len(grp)}")

    P("\n[C] near-dupes: same normalised name + coordinate within ~110 m (3dp)")
    k3 = d._nn + "|" + d._lon.round(3).astype(str) + "|" + d._lat.round(3).astype(str)
    g3 = k3[k3.duplicated(keep=False)]
    for key in g3.unique()[:6]:
        P(d[k3 == key][["STATE_NAME", "DISTRICT_NAME", "HAB_ID", "FACILITY_ID",
                        "FAC_DESC", "Longitude", "Latitude"]].to_string())
    P(f"rows involved: {len(g3)}  removable: {int(k3.duplicated().sum())}")

    P("\n[D] truncated DISTRICT_NAME (25 chars + '*')")
    t = d[d.DISTRICT_NAME.str.endswith("*")]
    P(t[["STATE_NAME", "DISTRICT_NAME", "FACILITY_ID"]].head(4).to_string())
    P(f"rows: {len(t)}")

    P("\n[E] FAC_DESC whitespace defects")
    ws = d[d.FAC_DESC != d.FAC_DESC.str.strip()]
    P("leading/trailing ws rows:", len(ws))
    P(ws[["FACILITY_ID", "FAC_DESC"]].head(6).assign(
        r=lambda x: x.FAC_DESC.map(repr)).to_string())
    ds = d[d.FAC_DESC.str.contains("  ")]
    P("double-space rows:", len(ds))
    P(ds[["FACILITY_ID", "FAC_DESC"]].head(4).assign(
        r=lambda x: x.FAC_DESC.map(repr)).to_string())
    cm = d[d.FAC_DESC.str.contains(",")]
    P("comma-in-name rows:", len(cm))
    P(cm[["FACILITY_ID", "FAC_DESC"]].head(4).to_string())

    P("\n[F] FAC_DESC that is unusable as a name (len<=3 or pure type word)")
    short = d[d.FAC_DESC.str.len() <= 3]
    P(f"len<=3: {len(short)} ({round(100*len(short)/n,2)}%)  distinct={short.FAC_DESC.nunique()}")
    P(short.FAC_DESC.value_counts().head(10).to_string())
    P("len<=2 rows:")
    P(d[d.FAC_DESC.str.len() <= 2][["STATE_NAME", "DISTRICT_NAME", "FACILITY_ID",
                                    "FAC_DESC"]].to_string())

    P("\n[G] tier leakage: rows whose name says SUB-CENTRE (different tier)")
    sub = d[d._nn.str.contains(r"\bsub\b|\bhsc\b|\bphsc\b|\bshc\b")]
    P(f"rows: {len(sub)} ({round(100*len(sub)/n,2)}%)")
    P(sub[["STATE_NAME", "DISTRICT_NAME", "FACILITY_ID", "FAC_DESC"]].head(8).to_string())

    P("\n[H] name-vs-file-label mismatch")
    if label == "PHC":
        m = d[d._nn.str.contains(r"\bchc\b|\bcommunity\b") & ~d._nn.str.contains(r"\bphc\b|\bprimary\b")]
    else:
        m = d[d._nn.str.contains(r"\bphc\b|\bprimary\b") & ~d._nn.str.contains(r"\bchc\b|\bcommunity\b")]
    P(f"rows: {len(m)}")
    P(m[["STATE_NAME", "DISTRICT_NAME", "FACILITY_ID", "FAC_DESC"]].to_string())

    P("\n[I] geo outliers > 100 km from own district median")
    g = d.groupby(["STATE_NAME", "DISTRICT_NAME"])[["_lon", "_lat"]].transform("median")
    dkm = 111.0 * np.hypot(d._lat - g._lat, (d._lon - g._lon) * np.cos(np.radians(d._lat)))
    o = d[dkm > 100].assign(km=dkm[dkm > 100].round(1))
    P(f"rows: {len(o)} ({round(100*len(o)/n,3)}%)")
    P(o[["STATE_NAME", "DISTRICT_NAME", "FACILITY_ID", "FAC_DESC",
         "Longitude", "Latitude", "km"]].sort_values("km", ascending=False).head(6).to_string())

    P("\n[J] low-precision coordinates (<=4 decimal places, ~>11 m grid)")
    dp = d.Longitude.str.extract(r"\.(\d+)$", expand=False).fillna("").str.len()
    lp = d[dp <= 4]
    P(f"rows: {len(lp)} ({round(100*len(lp)/n,2)}%)")
    P(lp[["STATE_NAME", "DISTRICT_NAME", "FACILITY_ID", "FAC_DESC",
          "Longitude", "Latitude"]].head(8).to_string())

    P("\n[K] placeholder district 'Unknown'")
    u = d[d.DISTRICT_NAME == "Unknown"]
    P(f"rows: {len(u)}; states={u.STATE_NAME.value_counts().to_dict()}; "
      f"BLOCK_IDs={sorted(u.BLOCK_ID.unique())}")
    P(f"lon range {u._lon.min():.4f}-{u._lon.max():.4f}, "
      f"lat range {u._lat.min():.4f}-{u._lat.max():.4f}" if len(u) else "")
    for st in u.STATE_NAME.unique():
        s = u[u.STATE_NAME == st]
        P(f"  {st}: n={len(s)} centroid=({s._lon.median():.4f},{s._lat.median():.4f}) "
          f"blocks={sorted(s.BLOCK_ID.unique())} habid_range="
          f"[{s.HAB_ID.astype(int).min()},{s.HAB_ID.astype(int).max()}]")

    P("\n[L] highest BLOCK_ID / HAB_ID rows (suspected late-appended districts)")
    hi = d.assign(b=d.BLOCK_ID.astype(int)).nlargest(6, "b")
    P(hi[["STATE_NAME", "DISTRICT_NAME", "BLOCK_ID", "HAB_ID", "FACILITY_ID",
          "FAC_DESC"]].to_string())

    P("\n[M] duplicate-ish name with only punctuation differing (trailing '.')")
    dot = d[d.FAC_DESC.str.endswith(".")]
    P(f"names ending in '.': {len(dot)}")
    P(dot[["STATE_NAME", "DISTRICT_NAME", "HAB_ID", "FACILITY_ID", "FAC_DESC"]].head(6).to_string())

    P("\n[N] state name deviating from LGD spelling")
    P(d[d.STATE_NAME == "Tamilnadu"].shape[0], "rows use 'Tamilnadu' (LGD: 'Tamil Nadu')")
    P(d[d.STATE_NAME == "Tamilnadu"][["STATE_NAME", "DISTRICT_NAME",
                                      "FACILITY_ID"]].head(3).to_string())

    P("\n[O] concatenated / no-space names")
    cc = d[d._nn.str.match(r"^[a-z]{12,}$")]
    P(f"rows: {len(cc)}")
    P(cc[["STATE_NAME", "DISTRICT_NAME", "FACILITY_ID", "FAC_DESC"]].head(8).to_string())

# ---- cross-file examples ----
P("\n" + "#" * 90)
P("# CROSS: the 21 rows present verbatim in BOTH files")
P("#" * 90)
cols9 = list(phc.columns[:9])
both = phc[cols9].merge(chc[cols9], on=cols9, how="inner")
P(both.to_string())

P("\n# CROSS: 376 shared HAB_IDs -> same habitation served by a PHC and a CHC")
sh = sorted(set(phc.HAB_ID) & set(chc.HAB_ID))
a = phc[phc.HAB_ID.isin(sh)].groupby("HAB_ID").first()
b = chc[chc.HAB_ID.isin(sh)].groupby("HAB_ID").first()
j = a.join(b, lsuffix="_p", rsuffix="_c")
dkm = 111.0 * np.hypot(j._lat_p - j._lat_c, (j._lon_p - j._lon_c) * np.cos(np.radians(j._lat_p)))
P("distance distribution km:", {f"p{int(q*100)}": round(float(dkm.quantile(q)), 3)
                                for q in (.1, .25, .5, .75, .9, .99)}, "max", round(dkm.max(), 2))
P("shared-HAB pairs at exactly the same coordinate:", int((dkm == 0).sum()))
P("within 100 m:", int((dkm < 0.1).sum()), " within 1 km:", int((dkm < 1).sum()))
P("\nthe 11 pairs >10 km apart despite sharing HAB_ID:")
far = j[dkm > 10].assign(km=dkm[dkm > 10].round(1))
P(far[["STATE_NAME_p", "DISTRICT_NAME_p", "BLOCK_ID_p", "FAC_DESC_p", "Longitude_p",
       "Latitude_p", "FAC_DESC_c", "Longitude_c", "Latitude_c", "km"]].to_string())
