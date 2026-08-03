"""Step 7: reliability of the 2396 fallback pincodes."""
import pandas as pd, numpy as np
SRC = "/Users/ankitraj2/asar master data/21_JULY_23_SRK_PMGSY_validated_homogenized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""]).dropna(how="all").reset_index(drop=True)
N=len(df)
apy_pin = df["address_py"].fillna("").str.extract(r"\b(\d{6})\b")[0]
trusted = apy_pin.notna()
print("trusted (pincode echoed by geocoder):", trusted.sum(), f"({100*trusted.sum()/N:.2f}%)")
print("fallback (pincode from unknown source):", (~trusted).sum(), f"({100*(~trusted).sum()/N:.2f}%)")

# per-district pincode prefix-3 sets built from trusted rows
key = df["STATE_NAME"]+"|"+df["DISTRICT_NAME"]
tr3 = df.loc[trusted].assign(k=key[trusted], p3=df.loc[trusted,"Pincode"].str[:3]).groupby("k")["p3"].apply(set)
tr2 = df.loc[trusted].assign(k=key[trusted], p2=df.loc[trusted,"Pincode"].str[:2]).groupby("k")["p2"].apply(set)
fb = df.loc[~trusted].copy(); fb["k"]=key[~trusted]
def chk(row, table, n):
    s = table.get(row["k"])
    if s is None: return None
    return row["Pincode"][:n] in s
ok3 = fb.apply(lambda r: chk(r, tr3, 3), axis=1)
ok2 = fb.apply(lambda r: chk(r, tr2, 2), axis=1)
print("\nfallback rows with a district reference available:", ok3.notna().sum())
print("  fallback pincode 3-digit prefix matches a trusted prefix in same district:", (ok3==True).sum(),
      f"({100*(ok3==True).sum()/ok3.notna().sum():.2f}%)")
print("  fallback pincode 2-digit prefix matches:", (ok2==True).sum(),
      f"({100*(ok2==True).sum()/ok2.notna().sum():.2f}%)")
print("  fallback rows FAILING the 2-digit district check:", (ok2==False).sum())
bad = fb[ok2==False]
print(bad[["Sr. No. ","STATE_NAME","DISTRICT_NAME","Pincode","address_py"]].head(12).to_string())

# same check on the trusted population, as a control (leave-one-out is overkill; use 2-digit)
ctrl = df.loc[trusted].assign(k=key[trusted])
ok2c = ctrl.apply(lambda r: chk(r, tr2, 2), axis=1)
print("\ncontrol: trusted rows passing same 2-digit district check:", (ok2c==True).sum(), "/", len(ctrl),
      f"({100*(ok2c==True).sum()/len(ctrl):.2f}%)")
