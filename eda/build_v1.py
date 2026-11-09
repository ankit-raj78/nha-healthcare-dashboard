#!/usr/bin/env python
"""
Build facilities_v1: homogenized vocabularies + cross-source entity resolution.

    v0  one row per SOURCE RECORD   count(*) = upper bound on facilities
    v1  one row per FACILITY        count(*) = a facility count, with a stated method

Reads db/facilities_v0.duckdb (never the raw CSVs — v0 owns ingest), writes
db/facilities_v1.duckdb. v0 is left untouched and stays rebuildable.

Run:  .venv/bin/python eda/build_v1.py
"""
import json
import os
import sys
import time

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import homogenize as H  # noqa: E402
import resolve as R  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DB = os.path.join(ROOT, "db", "facilities_v0.duckdb")
OUT_DB = os.path.join(ROOT, "db", "facilities_v1.duckdb")
EDA = os.path.join(ROOT, "eda")

# Field-level precedence when a cluster's members disagree: most recent snapshot
# wins. This is the only defensible ordering — we have no independent measure of
# per-source accuracy, and recency is the one property we can actually observe.
SOURCE_PRIORITY = {"CDAC_BB": 0, "NHA": 1, "PHC": 2, "CHC": 2, "CGHS": 3,
                   "PMGSY": 4, "NHP": 5, "PMJAY": 6, "NIN": 7}

t0 = time.time()


def step(msg):
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


# ------------------------------------------------------------------- 1. load
step("loading v0 …")
con = duckdb.connect(SRC_DB, read_only=True)
d = con.execute("""
    SELECT record_uid, source_dataset, source_facility_id,
           facility_name_raw, facility_name_norm, address_raw,
           state_norm, district_norm, block_raw, village_raw, city, pincode,
           latitude, longitude, facility_type_raw, facility_ownership_raw,
           phone, email, specialty_raw, specialty_code_system, bed_count,
           is_24x7, abdm_enabled, source_snapshot_date, geo_in_bbox, geo_trust
    FROM facility_source_record
""").fetchdf()
con.close()
step(f"  {len(d):,} source records")

# --------------------------------------------------------- 2. homogenize (Gap 3)
step("homogenizing facility_type and ownership …")
tc = [H.classify_type(t, n) for t, n in zip(d["facility_type_raw"], d["facility_name_raw"])]
d["type_canon"] = [x[0] for x in tc]
d["type_evidence"] = [x[1] for x in tc]
d["type_class"] = d["type_canon"].map(H.TYPE_CLASS)
d["tier"] = d["type_canon"].map(H.PUBLIC_TIER).astype(float)
d["ownership_canon"] = d["facility_ownership_raw"].map(H.classify_ownership)

dim_type = (d.groupby(["facility_type_raw", "type_canon", "type_evidence"], dropna=False)
            .size().reset_index(name="n_records").sort_values("n_records", ascending=False))
dim_own = (d.groupby(["facility_ownership_raw", "ownership_canon"], dropna=False)
           .size().reset_index(name="n_records").sort_values("n_records", ascending=False))
step(f"  facility_type: {d['facility_type_raw'].nunique()} raw -> "
     f"{d['type_canon'].nunique()} canonical "
     f"({(d['type_evidence'] == 'name').mean():.0%} decided by name tokens)")
step(f"  ownership:     {d['facility_ownership_raw'].nunique()} raw -> "
     f"{d['ownership_canon'].nunique()} canonical "
     f"({(d['ownership_canon'] != 'UNKNOWN').mean():.0%} resolved)")

# ----------------------------------------------------------- 3. district (Gap 2)
step("clustering district spellings within state …")
dim_district = H.build_district_map(d)
d["district_canon"] = H.apply_district_map(d, dim_district)
n_before, n_after = d["district_norm"].nunique(), d["district_canon"].nunique()
step(f"  district: {n_before:,} variants -> {n_after:,} canonical "
     f"({n_before - n_after:,} spellings absorbed)")

# ------------------------------------------------------------- 4. match keys
# Non-identifying tokens are learned from the corpus, not hand-listed: any token
# appearing in more than 500 records ('AYURVEDA', 'HOMOEO', 'GRAM') cannot single
# out a facility.
common = H.corpus_generic_tokens(d["facility_name_norm"].values)
step(f"  {len(common)} tokens are too common to identify a facility "
     f"(e.g. {', '.join(sorted(common)[:6])})")
d["name_core"] = d["facility_name_norm"].fillna("").map(lambda s: H.name_core(s, common))
d["name_strength"] = d["name_core"].map(H.name_strength)
# A pincode is only a key if it is a real 6-digit Indian PIN starting 1-8.
pin = d["pincode"].astype(str).str.extract(r"(\d{6})", expand=False)
d["pincode_key"] = pin.where(pin.str[0].isin(list("12345678")))
# CDAC_BB's phone column is 91.6% populated but only 15.7% dialable — 3,611 values
# were destroyed by Excel scientific notation. Keep only 10-digit mobiles/landlines
# that begin with a valid Indian leading digit.
ph = d["phone"].astype(str).str.replace(r"\D", "", regex=True)
ph = ph.str[-10:].where(ph.str.len() >= 10)
d["phone_key"] = ph.where(ph.str[0].isin(list("6789")))
d["state_norm"] = d["state_norm"].astype("object")
step(f"  usable keys: name_core {(d['name_core'].str.len() > 0).mean():.1%} · "
     f"pincode {d['pincode_key'].notna().mean():.1%} · "
     f"phone {d['phone_key'].notna().mean():.1%}")

# ------------------------------------------------------- 5. entity resolution
step("blocking …")
block_df = d.rename(columns={"facility_name_norm": "name_norm"})[[
    "source_dataset", "name_norm", "name_core", "name_strength", "state_norm",
    "district_canon", "type_canon", "type_class", "tier", "latitude", "longitude",
    "geo_trust", "pincode_key", "phone_key"]]
pairs, block_stats, _ = R.candidate_pairs(block_df)
print(block_stats.to_string(index=False))
step(f"  {len(pairs):,} distinct candidate pairs")

step("scoring …")
scored = R.score_pairs(block_df, pairs)
matched = scored[scored["match_rule"] != ""]
step(f"  {len(matched):,} accepted ({len(matched) / max(len(scored), 1):.1%} of candidates)")
print(matched["match_rule"].value_counts().to_string())

step("transitive closure …")
cid = R.cluster(len(d), matched)
d["cluster_id"] = cid
sizes = pd.Series(cid).value_counts()
d["facility_uid"] = ("F" + pd.Series(pd.factorize(cid)[0] + 1).astype(str).str.zfill(7)).values
step(f"  {sizes.size:,} facilities from {len(d):,} records "
     f"({len(d) - sizes.size:,} records absorbed, {1 - sizes.size / len(d):.1%} reduction)")
step(f"  cluster sizes: max {sizes.max()} · "
     f"{(sizes > 5).sum():,} clusters over 5 · {(sizes > 10).sum():,} over 10")

# ------------------------------------------------------- 6. canonical facility
step("building the facility table …")
d["prio"] = d["source_dataset"].map(SOURCE_PRIORITY).fillna(99).astype(int)
d["type_rank"] = d["type_canon"].map(H.TYPE_RANK).fillna(0).astype(int)

# Name: the most informative one in the cluster, ties broken by recency.
nm = d.assign(core_len=d["name_core"].str.len()).sort_values(
    ["cluster_id", "core_len", "prio"], ascending=[True, False, True])
name_pick = nm.groupby("cluster_id", sort=False).first()[
    ["facility_name_raw", "facility_name_norm", "name_core"]]

# Everything else: first non-null in precedence order (pandas .first() skips NaN).
by_prio = d.sort_values(["cluster_id", "prio"])
first_cols = ["address_raw", "city", "pincode_key", "phone_key", "email",
              "block_raw", "village_raw", "specialty_raw", "specialty_code_system",
              "is_24x7", "abdm_enabled"]
firsts = by_prio.groupby("cluster_id", sort=False)[first_cols].first()


def _mode(s):
    m = s.dropna()
    return m.mode().iloc[0] if len(m) else None


geo = d[d["geo_trust"].astype(bool)]
geo_pos = geo.groupby("cluster_id")[["latitude", "longitude"]].median()
any_pos = d.groupby("cluster_id")[["latitude", "longitude"]].median()
pos = geo_pos.reindex(any_pos.index).fillna(any_pos)

agg = d.groupby("cluster_id").agg(
    n_source_records=("record_uid", "size"),
    n_sources=("source_dataset", "nunique"),
    sources=("source_dataset", lambda s: ",".join(sorted(set(s)))),
    state=("state_norm", _mode),
    district=("district_canon", _mode),
    type_rank=("type_rank", "max"),
    ownership=("ownership_canon", lambda s: _mode(s[s != "UNKNOWN"]) or "UNKNOWN"),
    bed_count=("bed_count", "max"),
    any_geo_trust=("geo_trust", "max"),
    first_snapshot=("source_snapshot_date", "min"),
    last_snapshot=("source_snapshot_date", "max"),
)
RANK_TO_TYPE = {v: k for k, v in H.TYPE_RANK.items()}
facility = (agg.join(name_pick).join(firsts).join(pos).reset_index())
facility["facility_type"] = facility["type_rank"].map(RANK_TO_TYPE)
facility["type_class"] = facility["facility_type"].map(H.TYPE_CLASS)
facility["facility_uid"] = d.drop_duplicates("cluster_id").set_index("cluster_id")[
    "facility_uid"].reindex(facility["cluster_id"]).values
# A large cluster is almost always a transitive chain, not a facility with many
# records. Flag them rather than quietly shipping them as facts.
LARGE_CLUSTER = 8
facility["resolution_status"] = np.select(
    [facility["n_source_records"] > LARGE_CLUSTER, facility["n_sources"] > 1],
    ["REVIEW_LARGE_CLUSTER", "MERGED_CROSS_SOURCE"], default="SINGLE_SOURCE")
facility = facility.rename(columns={
    "facility_name_raw": "name", "facility_name_norm": "name_norm",
    "address_raw": "address", "pincode_key": "pincode", "phone_key": "phone",
    "block_raw": "block", "village_raw": "village"})[[
        "facility_uid", "name", "name_norm", "name_core", "facility_type", "type_class",
        "ownership", "state", "district", "block", "village", "city", "pincode",
        "latitude", "longitude", "any_geo_trust", "phone", "email", "address",
        "bed_count", "specialty_raw", "specialty_code_system", "is_24x7", "abdm_enabled",
        "n_source_records", "n_sources", "sources", "resolution_status",
        "first_snapshot", "last_snapshot"]]

step(f"  {len(facility):,} facilities · "
     f"{(facility.n_sources > 1).sum():,} confirmed by more than one source")

# ------------------------------------------------------------ 7. audit trail
link = d[["record_uid", "facility_uid", "source_dataset", "source_facility_id",
          "facility_name_raw", "facility_name_norm", "name_core", "address_raw",
          "state_norm", "district_norm", "district_canon", "city", "pincode_key",
          "latitude", "longitude", "geo_in_bbox", "geo_trust",
          "facility_type_raw", "type_canon", "type_class", "type_evidence",
          "facility_ownership_raw", "ownership_canon", "phone", "phone_key", "email",
          "specialty_raw", "specialty_code_system", "bed_count", "is_24x7",
          "abdm_enabled", "source_snapshot_date"]].copy()

uid = d["facility_uid"].values
mp = matched.copy()
mp["facility_uid"] = uid[mp["i"].values]
mp["record_uid_a"] = d["record_uid"].values[mp["i"].values]
mp["record_uid_b"] = d["record_uid"].values[mp["j"].values]
match_pair = mp[["facility_uid", "record_uid_a", "record_uid_b", "match_rule",
                 "name_sim", "dist_km", "same_state", "same_district",
                 "same_pincode", "same_phone", "generic_name"]]

# ------------------------------------------------- 8. hand-labeling sample (Gap 4)
# Without labeled pairs there is no precision figure, and the previous merge
# failed exactly there. Stratify so a reviewer sees each rule and the rejects
# nearest the boundary, not a random draw dominated by easy cases.
rng = np.random.default_rng(20260810)


def _sample(frame, n, bucket):
    if frame.empty:
        return frame.assign(review_bucket=bucket, label="")
    take = frame.sample(min(n, len(frame)), random_state=7)
    return take.assign(review_bucket=bucket, label="")


near_miss = scored[(scored["match_rule"] == "")
                   & (scored["dist_km"] <= R.D_CLOSE)
                   & scored["name_sim"].between(70, R.S_NAME)]
veto_close = scored[scored["type_veto"] & (scored["dist_km"] <= R.D_SAME_POINT)]
review = pd.concat(
    [_sample(matched[matched["match_rule"] == r], 25, f"accept:{r}")
     for r in sorted(matched["match_rule"].unique())]
    + [_sample(near_miss, 60, "reject:near_miss"),
       _sample(veto_close, 25, "reject:type_veto")])
review["name_a"] = d["facility_name_raw"].values[review["i"].values]
review["name_b"] = d["facility_name_raw"].values[review["j"].values]
review["src_a"] = d["source_dataset"].values[review["i"].values]
review["src_b"] = d["source_dataset"].values[review["j"].values]
review["type_a"] = d["type_canon"].values[review["i"].values]
review["type_b"] = d["type_canon"].values[review["j"].values]
review["district_a"] = d["district_canon"].values[review["i"].values]
review["district_b"] = d["district_canon"].values[review["j"].values]
review["uid_a"] = d["record_uid"].values[review["i"].values]
review["uid_b"] = d["record_uid"].values[review["j"].values]
review = review[["review_bucket", "label", "match_rule", "name_sim", "dist_km",
                 "name_a", "name_b", "src_a", "src_b", "type_a", "type_b",
                 "district_a", "district_b", "generic_name", "uid_a", "uid_b"]]
review_path = os.path.join(EDA, "er_review_sample.csv")
review.to_csv(review_path, index=False)
step(f"  wrote {len(review)} pairs for hand-labeling -> {review_path}")

# ------------------------------------------------------------------ 9. write
step("writing v1 …")
build_stats = {
    "source_records": int(len(d)),
    "facilities": int(len(facility)),
    "reduction_pct": round(100 * (1 - len(facility) / len(d)), 2),
    "multi_source_facilities": int((facility.n_sources > 1).sum()),
    "candidate_pairs": int(len(pairs)),
    "accepted_pairs": int(len(matched)),
    "rules": matched["match_rule"].value_counts().to_dict(),
    "blocking": block_stats.to_dict("records"),
    "district_variants_before": int(n_before),
    "district_variants_after": int(n_after),
    "facility_type_raw_values": int(d["facility_type_raw"].nunique()),
    "facility_type_canon_values": int(d["type_canon"].nunique()),
    "max_cluster_size": int(sizes.max()),
    "validated": False,
    "validation_note": ("No labeled pair set exists yet. Precision/recall are "
                        "UNMEASURED; eda/er_review_sample.csv is the input for that."),
}

if os.path.exists(OUT_DB):
    os.remove(OUT_DB)
out = duckdb.connect(OUT_DB)
out.register("facility_df", facility)
out.register("link_df", link)
out.register("pair_df", match_pair)
out.register("dim_district_df", dim_district)
out.register("dim_type_df", dim_type)
out.register("dim_own_df", dim_own)
out.execute("CREATE TABLE facility AS SELECT * FROM facility_df")
out.execute("CREATE TABLE facility_source_record AS SELECT * FROM link_df")
out.execute("CREATE TABLE match_pair AS SELECT * FROM pair_df")
out.execute("CREATE TABLE dim_district AS SELECT * FROM dim_district_df")
out.execute("CREATE TABLE dim_facility_type AS SELECT * FROM dim_type_df")
out.execute("CREATE TABLE dim_ownership AS SELECT * FROM dim_own_df")
out.execute("CREATE TABLE build_stats AS SELECT ? AS payload", [json.dumps(build_stats)])

# PII-free by construction: NIN's `Coder` column never enters v0, so it cannot
# reach v1. Both views are safe for the agent to bind to.
out.execute("""
    CREATE OR REPLACE VIEW v_facility AS
    SELECT facility_uid, name, name_norm, name_core, facility_type, type_class,
           ownership, state, district, block, village, city, pincode,
           latitude, longitude, any_geo_trust AS geo_trust, phone, email, address,
           bed_count, specialty_raw, specialty_code_system, is_24x7, abdm_enabled,
           n_source_records, n_sources, sources, resolution_status,
           first_snapshot, last_snapshot
    FROM facility
""")
out.execute("""
    CREATE OR REPLACE VIEW v_source_record AS
    SELECT record_uid, facility_uid, source_dataset, source_facility_id,
           facility_name_raw AS name, facility_name_norm AS name_norm, name_core,
           address_raw AS address, state_norm AS state,
           district_canon AS district, district_norm AS district_raw,
           city, pincode_key AS pincode, latitude, longitude, geo_in_bbox, geo_trust,
           facility_type_raw, type_canon AS facility_type, type_class, type_evidence,
           facility_ownership_raw, ownership_canon AS ownership,
           phone_key AS phone, email, specialty_raw, specialty_code_system,
           bed_count, is_24x7, abdm_enabled, source_snapshot_date
    FROM facility_source_record
""")
out.close()
step(f"wrote {OUT_DB}")
print(json.dumps({k: v for k, v in build_stats.items() if k != "blocking"}, indent=2))
