"""CGHS EDA - step 10: is the digit block inside Hospital_Id an LGD state code?"""
import pandas as pd, re
SRC = "/Users/ankitraj2/asar master data/18_SEPTEMBER_23_SRK_CGHS_Correct_Data.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
m = df["Hospital_Id"].str.extract(r"^HOSP(\d+)([A-Z])(\d+)$")
df["_code"] = m[0]; df["_letter"] = m[1]
LGD = {"1":"Jammu & Kashmir","2":"Himachal Pradesh","3":"Punjab","4":"Chandigarh","5":"Uttarakhand",
       "6":"Haryana","7":"NCT of Delhi","8":"Rajasthan","9":"Uttar Pradesh","10":"Bihar","11":"Sikkim",
       "12":"Arunachal Pradesh","13":"Nagaland","14":"Manipur","15":"Mizoram","16":"Tripura",
       "17":"Meghalaya","18":"Assam","19":"West Bengal","20":"Jharkhand","21":"Odisha","22":"Chhattisgarh",
       "23":"Madhya Pradesh","24":"Gujarat","25":"Daman & Diu","26":"D&N Haveli","27":"Maharashtra",
       "28":"Andhra Pradesh","29":"Karnataka","30":"Goa","31":"Lakshadweep","32":"Kerala","33":"Tamil Nadu",
       "34":"Puducherry","35":"A&N Islands","36":"Telangana","37":"Ladakh"}
print("code -> LGD name vs State column")
for code, g in df.dropna(subset=["_code"]).groupby("_code", key=None) if False else sorted(df.dropna(subset=["_code"]).groupby("_code"), key=lambda t: int(t[0])):
    print(f"  {code:>2s} LGD={LGD.get(code,'?'):<18s} n={len(g):<4d} State={g['State'].value_counts().to_dict()}")
print("\ncode 4 rows (LGD=Chandigarh) districts:")
print(df[df["_code"]=="4"][["Hospital_Id","Hospital_Name","District","State"]].head(20).to_string())
print("\ncode 37 row (LGD=Ladakh):")
print(df[df["_code"]=="37"][["Hospital_Id","Hospital_Name","District","State","Latitude","Longitude","address_py"]].to_string())
print("\ncode 36 rows labelled ANDHRA PRADESH:")
print(df[(df["_code"]=="36") & (df["State"]=="ANDHRA PRADESH")][["Hospital_Id","Hospital_Name","District","State"]].to_string())
print("\ncode 7 rows not NCT OF DELHI:")
print(df[(df["_code"]=="7") & (df["State"]!="NCT OF DELHI")][["Hospital_Id","Hospital_Name","District","State"]].to_string())
print("\nLAB-id embedded code -> State (first 2-3 digits):")
lab = df[df["Hospital_Id"].str.startswith("LAB")].copy()
for k in [1,2]:
    lab["c"] = lab["Hospital_Id"].str[3:3+k]
print("\nletter segment meaning check: letter x Hospital_Type")
print(pd.crosstab(df["_letter"], df["Hospital_Type"].fillna("<null>")).to_string())
print("\nletter T rows:")
print(df[df["_letter"]=="T"][["Hospital_Id","Hospital_Name","District","State","Hospital_Type"]].to_string())
print("\nletter G rows sample:")
print(df[df["_letter"]=="G"][["Hospital_Id","Hospital_Name","Hospital_Type"]].head(12).to_string())
