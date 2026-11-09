#!/usr/bin/env python
"""
Export the merged dataset to flat files.

The database is the deliverable; these are convenience copies for tools that
cannot read DuckDB. They are regenerated, never edited — edit the pipeline and
re-export.

    exports/facilities_merged.csv       323,359 rows, one per facility
    exports/facilities_merged.parquet   same, typed and ~10x smaller
    exports/source_record_map.csv       341,720 rows, record_uid -> facility_uid
    exports/dim_*.csv                   the vocabulary mappings, for review

Run:  .venv/bin/python eda/export.py
"""
import os

import duckdb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "db", "facilities_v1.duckdb")
OUT = os.path.join(ROOT, "exports")

os.makedirs(OUT, exist_ok=True)
con = duckdb.connect(DB, read_only=True)


def dump(query, name, fmt="csv"):
    path = os.path.join(OUT, f"{name}.{fmt}")
    opts = "(HEADER, DELIMITER ',')" if fmt == "csv" else "(FORMAT parquet, COMPRESSION zstd)"
    con.execute(f"COPY ({query}) TO '{path}' {opts}")
    n = con.execute(f"SELECT count(*) FROM ({query})").fetchone()[0]
    print(f"  {n:>9,} rows  {os.path.getsize(path) / 1e6:>7.1f} MB  {path}")


print(f"exporting from {DB}")
dump("SELECT * FROM v_facility ORDER BY state, district, name", "facilities_merged")
dump("SELECT * FROM v_facility ORDER BY state, district, name", "facilities_merged", "parquet")
dump("""SELECT record_uid, facility_uid, source_dataset, source_facility_id,
               name AS source_name, facility_type, district, latitude, longitude
        FROM v_source_record ORDER BY facility_uid""", "source_record_map")
dump("SELECT * FROM dim_district ORDER BY state_norm, district_canon, n_records DESC",
     "dim_district")
dump("SELECT * FROM dim_facility_type ORDER BY n_records DESC", "dim_facility_type")
dump("SELECT * FROM dim_ownership ORDER BY n_records DESC", "dim_ownership")
dump("""SELECT * FROM match_pair ORDER BY match_rule, facility_uid""", "match_pairs_audit")
con.close()
