"""Step 9: geo-vs-declared-state consistency using each state's own median centroid."""
import pandas as pd, numpy as np
pd.set_option("display.width", 250)
SRC = "/Users/ankitraj2/asar master data/22_MAY_22_AP_NIN.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
IDX = df.columns[0]; data_cols = [c for c in df.columns if c != IDX]
d = df.loc[~df[data_cols].isna().all(axis=1)].copy()
lat = pd.to_numeric(d["latitude"], errors="coerce"); lon = pd.to_numeric(d["longitude"], errors="coerce")
ok = lat.between(6, 38) & lon.between(68, 98)
g = d[ok].copy(); g["la"] = lat[ok]; g["lo"] = lon[ok]
cen = g.groupby("State_Name")[["la", "lo"]].median().rename(columns={"la": "cla", "lo": "clo"})
g = g.join(cen, on="State_Name")
# great-circle km
R = 6371.0
p1, p2 = np.radians(g["la"]), np.radians(g["cla"])
dl = np.radians(g["lo"] - g["clo"]); dp = p2 - p1
a = np.sin(dp/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
g["km"] = 2*R*np.arcsin(np.sqrt(a))
print("rows with valid bbox geo:", len(g))
for t in [300, 500, 800, 1200]:
    n = int((g["km"] > t).sum())
    print(f"  > {t} km from their own state's median centroid: {n} ({n/len(g)*100:.2f}%)")
print("\nworst 15:")
print(g.nlargest(15, "km")[["SrNo","Health Facility Name","State_Name","District_Name","latitude","longitude","km"]].to_string())
print("\nper-state count of rows >500km from own centroid:")
s = g[g["km"] > 500].groupby("State_Name").size().sort_values(ascending=False)
print(s.to_string())
