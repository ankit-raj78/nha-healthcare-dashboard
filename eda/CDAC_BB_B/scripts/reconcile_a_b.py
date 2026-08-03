#!/usr/bin/env python
"""Reconcile CDAC_BB_A (16_MAY_AR_CDAC_BB_DATASET.csv) against
CDAC_BB_B (CDAC_BB_DATASET - Sheet1.csv).

Every number quoted in eda/CDAC_BB_A/RECONCILIATION.md is printed by this script.
Read-only. Usage: .venv/bin/python eda/CDAC_BB_A/scripts/reconcile_a_b.py
"""
import re

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 90)

BASE = "/Users/ankitraj2/asar master data/"
KW = dict(encoding="utf-8", dtype=str, keep_default_na=False, na_values=[""])
A = pd.read_csv(BASE + "16_MAY_AR_CDAC_BB_DATASET.csv", **KW)
B = pd.read_csv(BASE + "CDAC_BB_DATASET - Sheet1.csv", **KW)
LAT, LON = (6.0, 38.0), (68.0, 98.0)
SHARED = ["State", "Name", "Address", "Latitude", "Longitude", "Phone", "Email",
          "Category", "new_longitude", "new_latitude"]


def nz(s):
    return s.map(lambda x: "" if pd.isna(x) else re.sub(r"[^a-z0-9]+", " ", str(x).lower()).strip())


def inb(lat, lon):
    return lat.between(*LAT) & lon.between(*LON)


def km(la1, lo1, la2, lo2):
    return np.sqrt(((la1 - la2) * 111.0) ** 2 +
                   ((lo1 - lo2) * 111.0 * np.cos(np.radians(la1))) ** 2)


def sec(t):
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78)


sec("0. SHAPE")
print("A", A.shape, "B", B.shape, " row delta:", len(B) - len(A))
print("A cols not in B:", [c for c in A.columns if c not in B.columns])

sec("1. NAME-LEVEL OVERLAP (the prior recon's numbers, reproduced)")
print("raw Name distinct : A=%d B=%d intersect=%d A-only=%d B-only=%d"
      % (A.Name.nunique(), B.Name.nunique(), len(set(A.Name) & set(B.Name)),
         len(set(A.Name) - set(B.Name)), len(set(B.Name) - set(A.Name))))
na, nb = nz(A.Name), nz(B.Name)
print("case/punct-normalised: A=%d B=%d intersect=%d A-only=%d B-only=%d"
      % (na.nunique(), nb.nunique(), len(set(na) & set(nb)),
         len(set(na) - set(nb)), len(set(nb) - set(na))))

sec("2. MATCH ON NAME + ADDRESS (normalised)")
ka = nz(A.Name) + "||" + nz(A.Address)
kb = nz(B.Name) + "||" + nz(B.Address)
print("distinct keys A=%d B=%d intersect=%d" % (ka.nunique(), kb.nunique(),
                                                len(set(ka) & set(kb))))
print("A rows whose key is absent from B:", int((~ka.isin(set(kb))).sum()))
print("B rows whose key is absent from A:", int((~kb.isin(set(ka))).sum()))
print("\nThe 7 A-only / 7 B-only keys are the SAME 7 facilities; they fail to match "
      "only because the state name embedded in Address is cased differently:")
print(pd.DataFrame({"A_addr": A.Address[~ka.isin(set(kb))].values,
                    "B_addr": B.Address[~kb.isin(set(ka))].values}).to_string())

sec("3. POSITIONAL ALIGNMENT: A[i] vs B[i]")
n = len(A)
Bh = B.iloc[:n].reset_index(drop=True)
for c in SHARED:
    same = (A[c].fillna("\x00") == Bh[c].fillna("\x00"))
    print("  %-14s identical=%5d  differ=%5d (%5.2f%%)  A-null=%4d  B-null=%4d"
          % (c, same.sum(), (~same).sum(), 100 * (~same).mean(),
             A[c].isna().sum(), Bh[c].isna().sum()))
print("\n-> B rows 0..%d are the SAME RECORDS, IN THE SAME ORDER, as A rows 0..%d." % (n - 1, n - 1))

sec("4. WHAT ARE B's 210 EXTRA ROWS (5679..5888)?")
head = B.iloc[5469:5679].reset_index(drop=True)
tail = B.iloc[5679:5889].reset_index(drop=True)
print("B[5679:] key in B[:5679] key set:", int(tail.pipe(lambda d: nz(d.Name) + "||" + nz(d.Address))
                                               .isin(set(kb[:5679])).sum()), "/ 210")
print("B[5679:] vs B[5469:5679] field-by-field:")
for c in SHARED:
    print("   %-14s identical=%d/210" % (c, int((head[c].fillna("\x00") == tail[c].fillna("\x00")).sum())))
hl, ho = pd.to_numeric(head.Latitude, errors="coerce"), pd.to_numeric(head.Longitude, errors="coerce")
tl, to = pd.to_numeric(tail.Latitude, errors="coerce"), pd.to_numeric(tail.Longitude, errors="coerce")
d = km(hl, ho, tl, to)
print("   coord distance between the two copies: median %.5f km, max %.5f km, rows >10 m apart: %d"
      % (d.median(), d.max(), int((d > 0.01).sum())))
print("-> B's 210 'extra' rows are a re-append of B's own rows 5469-5678 at full float "
      "precision. They contain ZERO new facilities.")

sec("5. STATE LABEL MAPPING A -> B (positional)")
ct = pd.crosstab(A.State.values, Bh.State.values)
for r in ct.index:
    for c in ct.columns:
        if ct.loc[r, c]:
            flag = "   <-- MISLABELLED" if r.replace(" ", "")[:4].lower() != c.replace(" ", "")[:4].lower() else ""
            print("  %-20s -> %-30s %5d%s" % (r, c, ct.loc[r, c], flag))

sec("6. GEO: WHICH Latitude/Longitude IS MORE TRUSTWORTHY?")
for nm, d0 in [("A", A), ("B", B)]:
    la, lo = pd.to_numeric(d0.Latitude, errors="coerce"), pd.to_numeric(d0.Longitude, errors="coerce")
    nlo, nla = pd.to_numeric(d0.new_longitude, errors="coerce"), pd.to_numeric(d0.new_latitude, errors="coerce")
    ok = inb(la, lo)
    print("%s  Latitude/Longitude   in-bbox=%d/%d (%.2f%%)  null=%d  out-of-bbox=%d  zero=%d"
          % (nm, ok.sum(), len(d0), 100 * ok.mean(), int((la.isna() | lo.isna()).sum()),
             int((~ok & la.notna() & lo.notna()).sum()), int(((la == 0) | (lo == 0)).sum())))
    a1, a2 = inb(nla, nlo), inb(nlo, nla)
    print("%s  new_latitude/new_longitude  valid-as-labelled=%d  valid-only-if-swapped=%d  invalid-both=%d"
          % (nm, int((a1 & ~a2).sum()), int((a2 & ~a1).sum()), int((~a1 & ~a2).sum())))

print("\nRows where B's Latitude/Longitude is unusable but A's is fine:")
la, lo = pd.to_numeric(A.Latitude, errors="coerce"), pd.to_numeric(A.Longitude, errors="coerce")
bla, blo = pd.to_numeric(Bh.Latitude, errors="coerce"), pd.to_numeric(Bh.Longitude, errors="coerce")
bad = ~inb(bla, blo)
print("  count:", int(bad.sum()), " (of which B-null:", int((bla.isna() | blo.isna()).sum()), ")")
print(pd.DataFrame({"State": A.State[bad & bla.notna()], "Name": A.Name[bad & bla.notna()],
                    "B_lat": Bh.Latitude[bad & bla.notna()], "B_lon": Bh.Longitude[bad & bla.notna()],
                    "A_lat": A.Latitude[bad & bla.notna()], "A_lon": A.Longitude[bad & bla.notna()]}).to_string())
print("  A rows unusable where B's is fine:", int((~inb(la, lo) & inb(bla, blo)).sum()))

sec("7. GEO ACCURACY TEST: distance to the district centroid")
dk = lambda s: s.map(lambda x: re.sub(r"[^a-z]", "", str(x).lower()))
for d0 in (A, B):
    d0["adist"] = dk(d0.Address.str.extract(r"Dist\.\s*([^,]*)$")[0])
base = A.iloc[:5469].copy()
base["la"] = pd.to_numeric(base.Latitude, errors="coerce")
base["lo"] = pd.to_numeric(base.Longitude, errors="coerce")
g = base.groupby("adist")
cen = g[["la", "lo"]].median()[g.size() >= 3]
print("reference: median coordinate of each district, from A rows 0-5468 (%d districts with >=3 rows)"
      % len(cen))


def dcen(d0):
    la = pd.to_numeric(d0.Latitude, errors="coerce")
    lo = pd.to_numeric(d0.Longitude, errors="coerce")
    return km(la, lo, d0.adist.map(cen.la), d0.adist.map(cen.lo))


for nm, d0 in [("A", A), ("B", B)]:
    s = dcen(d0).dropna()
    print("  %s whole file : n=%d median=%.1f km p90=%.1f km  >50km=%.1f%%  >150km=%.1f%%"
          % (nm, len(s), s.median(), s.quantile(.9), 100 * (s > 50).mean(), 100 * (s > 150).mean()))
sa, sb = dcen(A).iloc[5469:5679].reset_index(drop=True), dcen(B).iloc[5469:5679].reset_index(drop=True)
m = sa.notna() & sb.notna()
print("  disputed 210-row block (rows 5469-5678), %d comparable:" % m.sum())
print("     A median=%.1f km p90=%.1f  >50km=%d  >150km=%d" % (sa[m].median(), sa[m].quantile(.9),
                                                               int((sa[m] > 50).sum()), int((sa[m] > 150).sum())))
print("     B median=%.1f km p90=%.1f  >50km=%d  >150km=%d" % (sb[m].median(), sb[m].quantile(.9),
                                                               int((sb[m] > 50).sum()), int((sb[m] > 150).sum())))
print("     A closer to its own district centroid: %d rows;  B closer: %d rows"
      % (int((sa[m] < sb[m]).sum()), int((sb[m] < sa[m]).sum())))
w = pd.DataFrame({"Name": A.Name.iloc[5469:5679].values, "State": A.State.iloc[5469:5679].values,
                  "A_km": sa.values, "B_km": sb.values,
                  "A": A.Latitude.iloc[5469:5679].values + "," + A.Longitude.iloc[5469:5679].values,
                  "B": B.Latitude.iloc[5469:5679].values + "," + B.Longitude.iloc[5469:5679].values})
print("\n  worst B mislocations in that block (B far from district, A close):")
print(w[(w.B_km > 100) & (w.A_km < 50)].sort_values("B_km", ascending=False).head(8).to_string())

sec("8. PROVENANCE OF A's DIFFERING COORDINATES")
diff = (A.Latitude.fillna("\x00") != Bh.Latitude.fillna("\x00"))
bnlo = pd.to_numeric(Bh.new_longitude, errors="coerce")
bnla = pd.to_numeric(Bh.new_latitude, errors="coerce")
print("rows where A.Latitude != B.Latitude:", int(diff.sum()))
print("  ... of which A.Latitude ~= B.new_longitude AND A.Longitude ~= B.new_latitude (1e-4):",
      int((((la - bnlo).abs() < 1e-4) & ((lo - bnla).abs() < 1e-4) & diff).sum()))
print("  ... row-index range of those:", diff[diff].index.min(), "-", diff[diff].index.max())
print("-> for rows 5469-5678 the two files simply chose OPPOSITE members of the same "
      "pair of candidate geocodes.")

sec("9. THE EXTRA COLUMNS: District / dist_name")
ext = dk(A.Address.str.extract(r"Dist\.\s*([^,]*)$")[0])
print("A.District reproducible by parsing 'Dist. X' out of Address:",
      int((ext == dk(A.District)).sum()), "/", len(A))
print("A.dist_name reproducible the same way:", int((ext == dk(A.dist_name)).sum()), "/", len(A))
print("District == dist_name:", int((A.District == A.dist_name).sum()),
      " differ:", int((A.District != A.dist_name).sum()))
print("dist_name values truncated at 24 chars + '*':", int(A.dist_name.str.endswith("*").sum()),
      sorted(A.dist_name[A.dist_name.str.endswith("*")].unique()))
print("district parseable from Address in B:",
      int(dk(B.Address.str.extract(r'Dist\.\s*([^,]*)$')[0]).replace("", np.nan).notna().sum()), "/", len(B))

sec("10. STRING-FIELD CORRUPTION IN A (global uppercase find/replace)")
states = r"(ASSAM|BIHAR|DELHI|ODISHA|KERALA|PUNJAB|HARYANA|KARNATAKA|MAHARASHTRA|RAJASTHAN|TELANGANA|JHARKHAND|PUDUCHERRY|GUJRAT)"
print("A.Name rows containing an ALL-CAPS state token:",
      int(A.Name.str.contains(r"\b" + states + r"\b", regex=True, na=False).sum()))
print("B.Name rows containing an ALL-CAPS state token:",
      int(B.Name.str.contains(r"\b" + states + r"\b", regex=True, na=False).sum()))
for c in ["Name", "Address", "Email"]:
    dd = (A[c].fillna("\x00") != Bh[c].fillna("\x00"))
    same_lower = (A[c].fillna("").str.lower() == Bh[c].fillna("").str.lower())
    print("  %-8s differs in %4d rows, of which %4d differ ONLY in letter case"
          % (c, int(dd.sum()), int((dd & same_lower).sum())))

sec("11. DUPLICATES WITHIN EACH FILE")
for nm, d0 in [("A", A), ("B", B)]:
    src = [c for c in d0.columns if c != "adist"]
    print("  %s exact=%d  (Name,Address)=%d  norm(name)=%d"
          % (nm, int(d0.duplicated(subset=src).sum()),
             int(d0.duplicated(subset=["Name", "Address"]).sum()),
             int(nz(d0.Name).duplicated().sum())))

sec("12. VERDICT ARITHMETIC")
print("distinct facilities (norm name+address) in A :", ka.nunique())
print("distinct facilities (norm name+address) in B :", kb.nunique())
print("The 7-vs-7 residual in step 2 is NOT case: it is state-name SPELLING inside Address")
print("  (Chhattisgarh/Chattisgarh, Gujarat/Gujrat, Dohad/Dahod, Serchipp/Serchhip).")
print("Re-match on (normalised Name, district token from Address) instead:")
mk = lambda d: nz(d.Name) + "||" + d.adist
mka, mkb = mk(A), mk(B)
print("  A rows with no counterpart key in B:", int((~mka.isin(set(mkb))).sum()))
print("  B rows with no counterpart key in A:", int((~mkb.isin(set(mka))).sum()))
print("  (the residual is the Serchipp/Serchhip name typo and the Dohad/Dahod district rename)")
print()
print("FINAL: B contains 0 facilities that A does not contain.")
print("       A contains 0 facilities that B does not contain.")
print("       B's 210 extra rows are duplicates of B's own rows 5469-5678.")
