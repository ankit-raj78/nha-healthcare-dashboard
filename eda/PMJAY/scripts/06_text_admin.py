"""Name family, address family lineage, admin geo, pincode, contact PII,
and the suspicious columns (Types of Employees, Test extract, is_RU, Hospital Type)."""
import re
from collections import Counter

import pandas as pd

SRC = "/Users/ankitraj2/asar master data/18_MAY_23_SRK_PMJAY_validated_and_standardized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
n = len(df)
norm = lambda s: s.fillna("").str.upper().str.replace(r"[^A-Z0-9]+", " ", regex=True).str.strip()

# ================= NAME FAMILY =================
print("=" * 70, "\nNAME FAMILY\n", "=" * 70)
a, b = df["Hospital Name"], df["Manual Hospital Name"]
print(f"Hospital Name        non-null={a.notna().sum()} distinct={a.nunique()}")
print(f"Manual Hospital Name non-null={b.notna().sum()} distinct={b.nunique()}")
print(f"exactly equal      : {int((a == b).sum())} ({100*(a==b).mean():.2f}%)")
na_, nb = norm(a), norm(b)
print(f"equal after normalise: {int((na_ == nb).sum())} ({100*(na_==nb).mean():.2f}%)")
print(f"case/punct-only diff : {int(((a != b) & (na_ == nb)).sum())}")
print(f"substantively differ : {int((na_ != nb).sum())} ({100*(na_!=nb).mean():.2f}%)")
print("\nexamples of substantive disagreement:")
for i in list(df.index[na_ != nb])[:12]:
    print(f"  row {i}: HN={a[i]!r}\n          MHN={b[i]!r}")
print("\nlength: Hospital Name p50=%d, Manual p50=%d" % (a.str.len().median(), b.str.len().median()))
# which is cleaner? count of ALLCAPS, digits, trailing junk
for lab, s in [("Hospital Name", a), ("Manual Hospital Name", b)]:
    v = s.dropna()
    print(f"  {lab}: all-upper={int(v.str.isupper().sum())} "
          f"contains digit={int(v.str.contains(r'\\d').sum())} "
          f"leading/trailing ws={int((v != v.str.strip()).sum())} "
          f"non-ascii={int(v.str.contains(r'[^\x00-\x7F]').sum())} "
          f"len>100={int((v.str.len()>100).sum())}")

# ================= ADDRESS FAMILY =================
print("\n" + "=" * 70, "\nADDRESS FAMILY\n", "=" * 70)
ADDR = ["Hospital Address", "Manual Hospital Address", "address_py", "Formatted Address",
        "Road", "Locality", "District", "City", "State", "Country", "Zipcode", "pincode_py"]
print(f"{'column':26} {'non_null':>8} {'fill%':>7} {'distinct':>9} {'len_p50':>8}")
for c in ADDR:
    s = df[c]
    L = s.dropna().astype(str).str.len()
    print(f"{c:26} {s.notna().sum():>8} {100*s.notna().mean():>6.2f}% {s.nunique():>9} "
          f"{(L.median() if len(L) else 0):>8.0f}")
print("\n-- pairwise equality among the 4 full-address columns --")
FULL = ["Hospital Address", "Manual Hospital Address", "address_py", "Formatted Address"]
for i in range(len(FULL)):
    for j in range(i + 1, len(FULL)):
        x, y = FULL[i], FULL[j]
        print(f"  {x:24} == {y:24}: exact {int((df[x]==df[y]).sum()):>6}  "
              f"norm {int((norm(df[x])==norm(df[y])).sum()):>6}")
print("\n-- does Hospital Address == Manual Hospital Address + ', India'? --")
mh = df["Manual Hospital Address"].fillna("")
ha = df["Hospital Address"].fillna("")
print("  HA == MHA + ', India':", int((ha == mh + ", India").sum()), "/", n)
print("  HA startswith MHA    :", sum(1 for x, y in zip(ha, mh) if y and x.startswith(y)))
print("  HA contains MHA      :", sum(1 for x, y in zip(ha, mh) if y and y in x))
print("\n-- sample rows, all address columns --")
for i in [0, 1, 500, 5000]:
    print(f"\n  row {i}:")
    for c in ADDR:
        print(f"    {c:26} = {df.at[i, c]!r}")

# do geocoder components agree with each other / with manual?
print("\n-- 'State' (geocoder) vs 'Manual state' --")
ms, st = df["Manual state"].fillna(""), df["State"].fillna("")
print("  exact equal:", int((ms == st).sum()))
print("  equal upper:", int((ms.str.upper().str.strip() == st.str.upper().str.strip()).sum()))
agree = ms.str.upper().str.strip() == st.str.upper().str.strip()
both_present = df["Manual state"].notna() & df["State"].notna()
print(f"  of {int(both_present.sum())} rows with both: agree={int((agree&both_present).sum())} "
      f"({100*(agree&both_present).sum()/both_present.sum():.2f}%)")
print("  disagreement examples:")
for i in list(df.index[~agree & both_present])[:10]:
    print(f"    row {i}: Manual state={df.at[i,'Manual state']!r} State={df.at[i,'State']!r}")

print("\n-- 'District' (geocoder) vs 'Manual District' vs 'City' --")
md = df["Manual District"].fillna("").str.upper().str.strip()
gd = df["District"].fillna("").str.upper().str.strip().str.replace(r"\s+DISTRICT$", "", regex=True)
gc = df["City"].fillna("").str.upper().str.strip()
bp = df["Manual District"].notna() & df["District"].notna()
print(f"  rows with both Manual District and District: {int(bp.sum())}")
print(f"    agree (after stripping ' District'): {int(((md==gd)&bp).sum())}")
bpc = df["Manual District"].notna() & df["City"].notna()
print(f"  rows with both Manual District and City: {int(bpc.sum())}")
print(f"    agree: {int(((md==gc)&bpc).sum())} ({100*((md==gc)&bpc).sum()/bpc.sum():.2f}%)")
print("  City disagreement examples:")
for i in list(df.index[(md != gc) & bpc])[:10]:
    print(f"    row {i}: Manual District={df.at[i,'Manual District']!r} City={df.at[i,'City']!r}")

# ================= ADMIN GEO =================
print("\n" + "=" * 70, "\nADMIN GEO\n", "=" * 70)
print(f"Manual state: {df['Manual state'].nunique()} distinct, {df['Manual state'].isna().sum()} null")
print(df["Manual state"].value_counts(dropna=False).to_string())
print("\nManual state formatting: all upper?",
      bool(df["Manual state"].dropna().str.isupper().all()),
      "| any with stray whitespace:", int((df["Manual state"].dropna() != df["Manual state"].dropna().str.strip()).sum()))
print(f"\n'State' (geocoder): {df['State'].nunique()} distinct")
print(df["State"].value_counts(dropna=False).to_string())
print(f"\nManual District: {df['Manual District'].nunique()} distinct, "
      f"{df['Manual District'].isna().sum()} null")
print("  top 20:\n" + df["Manual District"].value_counts().head(20).to_string())
print("  all upper?", bool(df["Manual District"].dropna().str.isupper().all()))
dv = df["Manual District"].dropna()
print("  districts containing digits:", dv[dv.str.contains(r"\d")].unique()[:10].tolist())
print("  district w/ leading/trailing ws:", int((dv != dv.str.strip()).sum()))
print("  suspicious short districts:", sorted(set(dv[dv.str.len() <= 3])))

print(f"\n'District' (geocoder): {df['District'].nunique()} distinct, fill "
      f"{100*df['District'].notna().mean():.2f}%")
print(df["District"].value_counts().head(15).to_string())

# ================= PINCODE =================
print("\n" + "=" * 70, "\nPINCODE\n", "=" * 70)
for c in ["pincode_py", "Zipcode"]:
    s = df[c].dropna().astype(str).str.replace(r"\.0$", "", regex=True)
    print(f"\n{c}: non-null={df[c].notna().sum()} ({100*df[c].notna().mean():.2f}%) distinct={df[c].nunique()}")
    six = s.str.fullmatch(r"\d{6}")
    print(f"  exactly 6 digits: {int(six.sum())} / {len(s)}")
    print(f"  NOT 6 digits    : {int((~six).sum())} e.g. {s[~six].unique()[:15].tolist()}")
    valid = s[six]
    lead = valid.str[0]
    print(f"  leading digit distribution: {lead.value_counts().sort_index().to_dict()}")
    print(f"  leading digit 0 (invalid for India): {int((lead=='0').sum())}")
    print(f"  value range: {valid.min()} .. {valid.max()}")
print("\npincode_py vs Zipcode agreement:")
p1 = df["pincode_py"].astype(str).str.replace(r"\.0$", "", regex=True)
p2 = df["Zipcode"].astype(str).str.replace(r"\.0$", "", regex=True)
bp = df["pincode_py"].notna() & df["Zipcode"].notna()
print(f"  both present={int(bp.sum())} equal={int(((p1==p2)&bp).sum())} "
      f"({100*((p1==p2)&bp).sum()/bp.sum():.2f}%)")
for i in list(df.index[(p1 != p2) & bp])[:8]:
    print(f"    row {i}: pincode_py={df.at[i,'pincode_py']!r} Zipcode={df.at[i,'Zipcode']!r}")

# ================= CONTACT / PII =================
print("\n" + "=" * 70, "\nCONTACT / PII\n", "=" * 70)
em = df["Hospital E-Mail"].dropna()
print(f"E-Mail: non-null={len(em)} distinct={em.nunique()}")
ok = em.str.fullmatch(r"[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}")
print(f"  RFC-ish valid: {int(ok.sum())}  invalid: {int((~ok).sum())}")
print(f"  invalid examples: {em[~ok].unique()[:12].tolist()}")
print(f"  duplicated emails (shared across facilities): "
      f"{int(em.duplicated().sum())}; top: {em.value_counts().head(5).to_dict()}")
print(f"  domains: {Counter(em[ok].str.split('@').str[-1].str.lower()).most_common(8)}")

ph = df["Hospital Contact"].dropna().astype(str)
print(f"\nContact: non-null={len(ph)} distinct={ph.nunique()}")
digits = ph.str.replace(r"\D", "", regex=True)
print(f"  digit-length distribution: {digits.str.len().value_counts().sort_index().to_dict()}")
ten = digits.str.fullmatch(r"[6-9]\d{9}")
print(f"  valid 10-digit Indian mobile: {int(ten.sum())} ({100*ten.mean():.2f}%)")
print(f"  non-conforming examples: {ph[~ten].unique()[:12].tolist()}")
print(f"  duplicated numbers: {int(ph.duplicated().sum())}; top: {ph.value_counts().head(5).to_dict()}")

# ================= SUSPICIOUS COLUMNS =================
print("\n" + "=" * 70, "\nSUSPICIOUS COLUMNS\n", "=" * 70)
print("-- Types of Employees --")
print(f"  non-null={df['Types of Employees'].notna().sum()} -> COMPLETELY EMPTY")

print("\n-- Test extract --")
te = df["Test extract"]
print(f"  non-null={te.notna().sum()} ({100*te.notna().mean():.4f}%)")
print("  all non-null rows:")
for i in list(df.index[te.notna()]):
    print(f"    row {i}: {te[i]!r} | Manual District={df.at[i,'Manual District']!r} "
          f"| Manual state={df.at[i,'Manual state']!r} | City={df.at[i,'City']!r} | State={df.at[i,'State']!r}")

print("\n-- is_RU --")
print(df["is_RU"].value_counts(dropna=False).to_string())
print(f"  null rows: {list(df.index[df['is_RU'].isna()])}")
for i in list(df.index[df["is_RU"].isna()]):
    print(f"    row {i}: {df.at[i,'Hospital Name'][:40]!r} state={df.at[i,'Manual state']!r}")

print("\n-- Hospital Type --")
print(df["Hospital Type"].value_counts(dropna=False).to_string())
print(f"  null: {df['Hospital Type'].isna().sum()} ({100*df['Hospital Type'].isna().mean():.2f}%)")

print("\n-- Country --")
print(df["Country"].value_counts(dropna=False).to_string())

# ================= Sr No =================
print("\n" + "=" * 70, "\nSr No\n", "=" * 70)
sr = df["Sr No"]
srn = pd.to_numeric(sr, errors="coerce")
print(f"  non-null={sr.notna().sum()} distinct={sr.nunique()} is_unique={sr.is_unique}")
print(f"  numeric parse ok={srn.notna().sum()} min={srn.min()} max={srn.max()}")
print(f"  is contiguous 1..n: {bool((srn.sort_values().values == range(1, n+1)).all())}")
print(f"  equals row index+1: {int((srn.values == df.index.values + 1).sum())}/{n}")
