"""Geo family: API Latitude/Longitude vs gmaps_Latitude/gmaps_Longitude,
gmaps_Accuracy, Auto Score. Fill rates, India-bbox validity, agreement, swaps."""
import numpy as np
import pandas as pd

SRC = "/Users/ankitraj2/asar master data/18_MAY_23_SRK_PMJAY_validated_and_standardized.csv"
df = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
n = len(df)

LAT_MIN, LAT_MAX = 6.0, 38.0
LON_MIN, LON_MAX = 68.0, 98.0

PAIRS = [("API Latitude", "API Longitude"), ("gmaps_Latitude", "gmaps_Longitude")]

num = {}
for a, b in PAIRS:
    num[a] = pd.to_numeric(df[a], errors="coerce")
    num[b] = pd.to_numeric(df[b], errors="coerce")

for a, b in PAIRS:
    lat, lon = num[a], num[b]
    print(f"\n===== {a} / {b} =====")
    print(f"non-null raw: {df[a].notna().sum()} / {df[b].notna().sum()}")
    print(f"parse to numeric: {lat.notna().sum()} / {lon.notna().sum()}")
    print(f"unparseable lat values: {df.loc[df[a].notna() & lat.isna(), a].unique()[:10].tolist()}")
    both = lat.notna() & lon.notna()
    zero = (lat == 0) | (lon == 0)
    zz = (lat == 0) & (lon == 0)
    inb = both & lat.between(LAT_MIN, LAT_MAX) & lon.between(LON_MIN, LON_MAX)
    swap = both & ~inb & lon.between(LAT_MIN, LAT_MAX) & lat.between(LON_MIN, LON_MAX)
    oob = both & ~inb & ~swap & ~zz
    print(f"both present     : {int(both.sum())} ({100*both.mean():.2f}%)")
    print(f"either exactly 0 : {int(zero.sum())}   both 0: {int(zz.sum())}")
    print(f"valid in India   : {int(inb.sum())} ({100*inb.mean():.2f}%)")
    print(f"possibly swapped : {int(swap.sum())}")
    print(f"out of bbox      : {int(oob.sum())}")
    print(f"null (either)    : {int((~both).sum())}")
    print(f"lat range {lat.min()} .. {lat.max()}   lon range {lon.min()} .. {lon.max()}")
    if oob.sum():
        print("  out-of-bbox examples (row, lat, lon, name, state):")
        for i in list(df.index[oob])[:10]:
            print(f"    {i}: {lat[i]}, {lon[i]} | {df.at[i,'Hospital Name'][:40]!r} | {df.at[i,'Manual state']}")
    if swap.sum():
        print("  swapped examples:")
        for i in list(df.index[swap])[:10]:
            print(f"    {i}: lat={lat[i]} lon={lon[i]} | {df.at[i,'Hospital Name'][:40]!r} | {df.at[i,'Manual state']}")
    # precision / rounding
    dec = df.loc[df[a].notna(), a].astype(str).str.split(".").str[-1].str.len()
    print(f"lat decimal places: p50={dec.median()} min={dec.min()} max={dec.max()}")
    lowprec = int((dec <= 2).sum())
    print(f"lat with <=2 decimals (low precision): {lowprec}")

# --- agreement between the two sources ----------------------------------
print("\n===== agreement API vs gmaps =====")
la, lo = num["API Latitude"], num["API Longitude"]
lg, lgo = num["gmaps_Latitude"], num["gmaps_Longitude"]
both = la.notna() & lo.notna() & lg.notna() & lgo.notna()
print("rows with both pairs numeric:", int(both.sum()))
print("exactly identical lat&lon:", int((both & (la == lg) & (lo == lgo)).sum()))

# haversine
R = 6371.0
def hav(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))

d = pd.Series(np.nan, index=df.index)
d[both] = hav(la[both], lo[both], lg[both], lgo[both])
print("\ndistance API<->gmaps (km) percentiles:")
print(d.describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]).to_string())
for thr in [0.1, 0.5, 1, 5, 25, 100, 500]:
    print(f"  <= {thr:>5} km: {int((d <= thr).sum()):>6} ({100*(d<=thr).sum()/int(both.sum()):.2f}% of comparable)")
print(f"  >  500 km: {int((d > 500).sum())}")
print("\nworst disagreements:")
for i in d.sort_values(ascending=False).head(8).index:
    print(f"  row {i}: {d[i]:.0f} km | API=({la[i]},{lo[i]}) gmaps=({lg[i]},{lgo[i]}) | "
          f"{df.at[i,'Hospital Name'][:35]!r} | {df.at[i,'Manual state']}")

# --- gmaps_Accuracy -----------------------------------------------------
print("\n===== gmaps_Accuracy =====")
print(df["gmaps_Accuracy"].value_counts(dropna=False).to_string())
print("\naccuracy vs India-bbox validity of gmaps point:")
gvalid = lg.between(LAT_MIN, LAT_MAX) & lgo.between(LON_MIN, LON_MAX)
print(pd.crosstab(df["gmaps_Accuracy"], gvalid, dropna=False).to_string())
print("\nmedian API<->gmaps distance by accuracy class:")
print(d.groupby(df["gmaps_Accuracy"]).describe(percentiles=[0.5])[["count", "50%", "mean", "max"]].to_string())

# --- Auto Score ---------------------------------------------------------
print("\n===== Auto Score =====")
sc = pd.to_numeric(df["Auto Score"], errors="coerce")
print(sc.describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).to_string())
print("n distinct:", sc.nunique(), " n exactly 1.0:", int((sc == 1).sum()), " n 0:", int((sc == 0).sum()))
print("in [0,1]:", int(sc.between(0, 1).sum()), "of", int(sc.notna().sum()))
print("\nAuto Score by gmaps_Accuracy:")
print(sc.groupby(df["gmaps_Accuracy"]).describe(percentiles=[0.5])[["count", "mean", "50%"]].to_string())
print("\ncorrelation Auto Score vs API<->gmaps distance:", round(float(sc.corr(d)), 4))
print("Auto Score bucket vs median distance:")
b = pd.cut(sc, [0, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0])
print(d.groupby(b, observed=True).agg(["count", "median", "mean"]).to_string())

# which source to trust: coverage of a "usable" point
api_ok = la.between(LAT_MIN, LAT_MAX) & lo.between(LON_MIN, LON_MAX)
gm_ok = gvalid
print("\n===== usable-point coverage =====")
print(f"API usable      : {int(api_ok.sum())} ({100*api_ok.mean():.2f}%)")
print(f"gmaps usable    : {int(gm_ok.sum())} ({100*gm_ok.mean():.2f}%)")
print(f"either usable   : {int((api_ok|gm_ok).sum())} ({100*(api_ok|gm_ok).mean():.2f}%)")
print(f"both usable     : {int((api_ok&gm_ok).sum())}")
print(f"neither usable  : {int((~api_ok&~gm_ok).sum())}")
print(f"only API usable : {int((api_ok&~gm_ok).sum())}")
print(f"only gmaps usable: {int((~api_ok&gm_ok).sum())}")
for i in list(df.index[~api_ok & ~gm_ok])[:10]:
    print(f"   neither row {i}: API=({la[i]},{lo[i]}) gmaps=({lg[i]},{lgo[i]}) {df.at[i,'Hospital Name'][:35]!r}")

# duplicated coordinate points (geocoder fallback to a centroid)
print("\n===== repeated coordinate points (centroid fallback smell) =====")
for a, b, lab in [("API Latitude", "API Longitude", "API"), ("gmaps_Latitude", "gmaps_Longitude", "gmaps")]:
    key = df[a].astype(str) + "," + df[b].astype(str)
    vc = key.value_counts()
    print(f"\n{lab}: distinct points={vc.size}, points used >1 time={(vc>1).sum()}, "
          f"rows sharing a point={int(vc[vc>1].sum())}")
    print(f"  top repeated points:\n{vc.head(8).to_string()}")
