"""NHP EDA step 7: concrete row examples for issues.md + address_py provenance."""
import re
import pandas as pd, numpy as np
from collections import Counter

SRC = "/Users/ankitraj2/asar master data/8_JULY_23_SRK_NHP_validated_and_standardized.csv"
NORM = lambda s: re.sub(r"\s+", " ", s).strip() if isinstance(s, str) else s
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
df = df.rename(columns={"S.\n  No.": "S. No."}).drop(
    columns=[c for c in df.columns if c.startswith("Unnamed")]).dropna(how="all").reset_index(drop=True)
lat = pd.to_numeric(df["Latitude"], errors="coerce"); lon = pd.to_numeric(df["Longitude"], errors="coerce")

print("=== rows sharing identical coordinates ===")
key = lat.astype(str) + "," + lon.astype(str)
d = key[key.duplicated(keep=False)]
print(df.loc[d.index, ["S. No.", "Hospital Name", "City", "State", "Latitude", "Longitude"]].to_string())

print("\n=== rows with identical address_py: do they share coords? ===")
ap = df["address_py"].map(NORM)
d2 = ap[ap.duplicated(keep=False)]
print(df.loc[d2.index, ["S. No.", "Hospital Name", "Latitude", "Longitude"]].to_string())

print("\n=== null / anomalous Postcode & City rows ===")
print(df.loc[df["Postcode"].isna(), ["S. No.", "Hospital Name", "City", "State",
                                      "Standardized Address"]].to_string())
print(df.loc[df["City"].isna(), ["S. No.", "Hospital Name", "State", "Postcode",
                                  "Given Address"]].to_string())
print(df.loc[df["Postcode"].fillna("").str.contains(" "),
             ["S. No.", "Hospital Name", "Postcode", "Postcode_py"]].to_string())

print("\n=== address_py provenance: how often does it name a DIFFERENT institution? ===")
print("  address_py contains 'Blood Bank':", int(ap.str.contains("Blood Bank", case=False).sum()))
print("  address_py contains 'Hospital':", int(ap.str.contains("Hospital", case=False).sum()))
print("  address_py has no letters before first comma matching name token:",)
# token overlap between name and address_py
def overlap(a, b):
    ta = set(re.findall(r"[a-z]{4,}", a.casefold())); tb = set(re.findall(r"[a-z]{4,}", b.casefold()))
    return len(ta & tb) / max(len(ta), 1)
hn = df["Hospital Name"].map(NORM)
ov = [overlap(n, a) for n, a in zip(hn, ap)]
ov = pd.Series(ov)
print("  name->address_py token overlap: mean=%.3f  ==0: %d  <0.25: %d  >=0.5: %d" % (
    ov.mean(), int((ov == 0).sum()), int((ov < 0.25).sum()), int((ov >= 0.5).sum())))
ovs = pd.Series([overlap(n, a) for n, a in zip(hn, df["Standardized Address"].map(NORM))])
print("  name->Standardized Address overlap: mean=%.3f ==0: %d" % (ovs.mean(), int((ovs==0).sum())))

print("\n=== Given Address vs Standardized Address: what does standardization add? ===")
ga = df["Given Address"].map(NORM); sa = df["Standardized Address"].map(NORM)
print("  identical:", int((ga == sa).sum()))
print("  SA longer than GA:", int((sa.str.len() > ga.str.len()).sum()))
for i in [1, 5, 100, 400]:
    print(f"   row {i}: GA={ga[i]!r}\n           SA={sa[i]!r}\n           AP={ap[i]!r}")

print("\n=== names with obvious truncation/typos (ER hazard) ===")
trunc = hn[hn.str.contains(r"Colleg$|Instt\.|Med\. Col|Centr$|Institut$|Scienc$|,$", regex=True)]
print(len(trunc)); print(trunc.head(20).to_string())

print("\n=== trailing-period on Type ===")
print(Counter(df["Type"]))

print("\n=== physical-line indices of a multi-line record (for issues.md) ===")
raw = open(SRC, "rb").read().decode("utf-8-sig")
lines = raw.split("\r\n")
print("  physical CRLF-delimited records:", len(lines))
print("  record 1 (0-based after header) repr:", repr(lines[1])[:260])
