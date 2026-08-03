import re
import pandas as pd, numpy as np
from collections import Counter
SRC = "/Users/ankitraj2/asar master data/8_JULY_23_SRK_NHP_validated_and_standardized.csv"
NORM = lambda s: re.sub(r"\s+", " ", s).strip() if isinstance(s, str) else s
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = df.rename(columns={"S.\n  No.": "S. No."}).drop(
    columns=[c for c in df.columns if c.startswith("Unnamed")]).dropna(how="all").reset_index(drop=True)
ap = df["address_py"].map(NORM)
print("rows 569,613 address_py:", repr(ap[569]), "|", repr(ap[613]))
print("shortest address_py:", ap.str.len().nsmallest(6).to_dict())
print(df.loc[ap.str.len().nsmallest(6).index, ["S. No.","Hospital Name","address_py"]].to_string())

lat = pd.to_numeric(df["Latitude"]); lon = pd.to_numeric(df["Longitude"])
print("\nrows with <=3 decimal places on lat (low precision):")
dec = df["Latitude"].str.split(".").str[1].str.len()
print(df.loc[dec <= 3, ["S. No.","Hospital Name","City","State","Latitude","Longitude"]].to_string())

# is Given Address == NAME + ' ' + City + ' ' + State (i.e. derived, not an independent address)?
hn = df["Hospital Name"].map(NORM); ga = df["Given Address"].map(NORM)
city = df["City"].map(NORM).fillna(""); st = df["State"].map(NORM)
recon = (hn + ", " + city + " " + st).str.replace(r"\s+"," ",regex=True)
print("\nGiven Address reconstructable as 'name, city state':",
      int((ga.str.casefold() == recon.str.casefold()).sum()), "/", len(df))
recon2 = (hn + " " + city + " " + st).str.replace(r"\s+"," ",regex=True)
print("Given Address == 'name city state' (no comma):",
      int((ga.str.casefold() == recon2.str.casefold()).sum()))
print("Given Address contains City:", int(sum(1 for a,c in zip(ga,city) if c and c.casefold() in a.casefold())))
print("Given Address ends with State:", int(sum(1 for a,s in zip(ga,st) if a.casefold().endswith(s.casefold()))))
print("Given Address adds tokens beyond name+city+state:",
      int(sum(1 for a,n,c,s in zip(ga,hn,city,st)
              if set(re.findall(r"[a-z]{3,}", a.casefold())) -
                 set(re.findall(r"[a-z]{3,}", (n+" "+c+" "+s).casefold()))) ))

# Standardized Address reconstructable?
sa = df["Standardized Address"].map(NORM); pc = df["Postcode"].map(NORM).fillna("")
recon3 = (hn + ", " + city + ", " + st + ", India, " + pc + ".").str.replace(r"\s+"," ",regex=True)
print("Standardized Address == 'name, city, state, India, pin.':",
      int((sa.str.casefold() == recon3.str.casefold()).sum()), "/", len(df))

print("\n=== length distributions (normalized) ===")
for c in ["Hospital Name","Given Address","Standardized Address","address_py","City","State"]:
    L = df[c].map(NORM).dropna().str.len()
    print(f"  {c}: min={L.min()} p25={int(L.quantile(.25))} p50={int(L.median())} p75={int(L.quantile(.75))} p95={int(L.quantile(.95))} max={L.max()}")

print("\n=== PII scan ===")
allt = df.astype(str).agg(" ".join, axis=1)
print("  cells matching email:", int(allt.str.contains(r"[\w.]+@[\w.]+\.\w+", regex=True).sum()))
print("  cells matching 10-digit phone:", int(allt.str.contains(r"\b[6-9]\d{9}\b", regex=True).sum()))
print("  cells matching http:", int(allt.str.contains(r"https?://", regex=True).sum()))
