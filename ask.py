#!/usr/bin/env python
"""
ask.py — natural-language querying over the Indian health-facility database.

    ./ask.py "how many ABDM-enabled facilities are in Bihar?"
    ./ask.py                 # interactive REPL

Architecture: hybrid text-to-SQL, not vector RAG. Counts and aggregations come
from DuckDB, not from the model — the model only writes the SQL. See
eda/00_PLAN.md for why.

Requires ANTHROPIC_API_KEY (or an `ant auth login` profile).
"""
import os
import sys
import textwrap

import anthropic
import duckdb
from anthropic import beta_tool

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "facilities_v0.duckdb")
MODEL = "claude-opus-5"

# The agent binds to v_facility, never to the base table — v_facility is PII-free
# by construction (NIN's `Coder` column of staff names is never ingested).
VIEW = "v_facility"

SCHEMA_CARD = """
# facility database — schema card

One table you may query: `v_facility` (341,720 rows). Read-only.

## THE CAVEAT THAT GOVERNS EVERY ANSWER
This is v0: harmonized and deduplicated WITHIN each source, but there is NO
cross-source entity resolution yet. A facility listed in both NHA and PMJAY is
two rows. At least 8,408 name+district groups already span multiple sources.

So `count(*)` is an UPPER BOUND ON SOURCE RECORDS, not a facility count.
Whenever you report a total, say so plainly. Never state a bare number as "the
number of hospitals in India".

## Columns

| column | notes |
|---|---|
| record_uid | PK, e.g. "NHA:12345" |
| source_dataset | NHA 261905 · PHC 31958 · PMGSY 13700 · PMJAY 11284 · NIN 10327 · CDAC_BB 5678 · CHC 4237 · CGHS 1983 · NHP 648 |
| source_facility_id | source's own ID, prefixed |
| name | 100% populated |
| name_norm | uppercased, punctuation stripped — USE THIS FOR MATCHING |
| address | 96% populated |
| state | 100%, normalized to 36 values, UPPERCASE (e.g. 'BIHAR', 'TAMIL NADU', 'NCT OF DELHI') |
| district | 99.8% but NOT normalized — 1,051 distinct values for ~790 real districts |
| block_raw, village_raw, city, pincode | sparse; pincode only 11% |
| latitude, longitude | 100% populated |
| facility_type | 96% but UNCONTROLLED VOCABULARY — see below |
| ownership | 82%; raw strings like 'Public', 'Private For-Profit', 'Govt.', 'Trust' |
| phone, email | 8.6% / sparse; CDAC_BB phones are largely corrupt |
| specialty_raw | only 7.0% — see below |
| specialty_code_system | 'PMJAY_MS' or 'CGHS_2L' |
| bed_count | 0.1% — effectively unusable |
| is_24x7, abdm_enabled | NHA only ('Yes'/'No') |
| source_snapshot_date | assigned from FILENAMES, not data. Sources span 2022-2025. |
| geo_in_bbox | boolean, inside India |
| geo_trust | boolean — in-bbox AND not centroid-stacked. 285,630 true (83.6%). |

## Trap 1 — facility_type spellings do not reconcile
The same tier appears under several strings. Always match with LIKE/ILIKE or an
IN-list covering the variants, never `= 'CHC'`:
  Sub Centre 96439 · Hospital 37797 · PHC 31958 · Pharmacy 29959 ·
  Primary Health Centre 22497 · Clinic/ Dispensary 21265 ·
  Health and Wellness Centre 17564 · Community Health Centre 12109 ·
  Diagnostic Laboratory 10143 · Bedded Hospital 7307 ·
  Community Health Center 4786 · CHC 4237 · BLOOD_BANK 4231 ·
  BLOOD_STORAGE_UNIT 1447 · MEDICAL_COLLEGE 648
PHC/CHC tier labels are themselves unreliable (~4% mislabelled — West Bengal's
CHC-equivalent is named "Block Primary Health Centre" and sits in the PHC file).

## Trap 2 — district is not normalized
e.g. KERALA has both 'KASARAGOD' (386) and 'KASARGOD' (11) — the same district.
District-level counts are APPROXIMATE. Say so when you report one.

## Trap 3 — specialties are undecoded AND nearly absent
`specialty_raw` holds opaque codes (`M1`, `S7`, …). There is no codebook: the
meaning of each code is UNKNOWN. Only 23,615 records (7.0%) carry any specialty
at all, and NHA's column is populated on just 4% of its rows.
=> You CANNOT answer "which hospitals offer cardiology". Say so directly and
explain that the PM-JAY Health Benefit Package specialty master is needed.
Never guess what a code means.

## Trap 4 — geo
Use `geo_trust` for anything spatial. 16.4% of records fail it (centroid
stacking, shared points, out-of-bbox). Distance: DuckDB has no PostGIS; use the
haversine formula in raw SQL.

## Worked examples

Q: How many facilities in Bihar?
   SELECT count(*) FROM v_facility WHERE state = 'BIHAR';

Q: Public vs private split
   SELECT CASE WHEN upper(ownership) LIKE '%PUBLIC%' OR upper(ownership) LIKE '%GOVT%'
                 OR upper(ownership) LIKE '%GOVERNMENT%' THEN 'PUBLIC'
               WHEN upper(ownership) LIKE '%PRIVATE%' OR upper(ownership) LIKE '%TRUST%'
                 THEN 'PRIVATE/TRUST' ELSE 'OTHER' END AS grp, count(*)
   FROM v_facility WHERE ownership IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;

Q: How many CHCs are there?   (note the spelling variants)
   SELECT count(*) FROM v_facility
   WHERE facility_type ILIKE '%community health cent%' OR facility_type = 'CHC';

Q: Which records look like cross-source duplicates?
   SELECT name_norm, district, count(DISTINCT source_dataset) n
   FROM v_facility WHERE name_norm IS NOT NULL AND district IS NOT NULL
   GROUP BY 1,2 HAVING count(DISTINCT source_dataset) > 1 ORDER BY 3 DESC;

Q: Facilities within 10km of a point (lat0, lon0)
   SELECT name, state, district,
          6371 * 2 * asin(sqrt(pow(sin(radians(latitude - {lat0})/2), 2)
            + cos(radians({lat0})) * cos(radians(latitude))
            * pow(sin(radians(longitude - {lon0})/2), 2))) AS km
   FROM v_facility WHERE geo_trust GROUP BY ALL HAVING km < 10 ORDER BY km;
"""

SYSTEM = f"""You answer questions about a database of Indian government health-facility
records by writing DuckDB SQL and running it with the `run_sql` tool.

Rules:
- Every number you report must come from a query you actually ran. Never estimate.
- Call `get_schema_card` before your first query in a session.
- If a query errors, read the error and fix the SQL rather than giving up.
- Report the caveats that apply to the specific answer — especially the v0
  no-entity-resolution caveat on any total, and the district-normalization
  caveat on any district-level breakdown.
- If a question cannot be answered from this data (specialties, bed counts, true
  deduplicated facility counts), say so plainly and explain what is missing.
  Do not substitute a number that answers a different question.
- Answer in prose, leading with the result. Show the SQL only if asked or if it
  materially clarifies what was counted.

{SCHEMA_CARD}
"""


@beta_tool
def run_sql(query: str) -> str:
    """Run a read-only DuckDB SELECT against the facility database.

    Args:
        query: A single SELECT (or WITH ... SELECT) statement. Only `v_facility`
            may be queried. Results are truncated to 100 rows.
    """
    q = query.strip().rstrip(";")
    low = q.lower()
    if not (low.startswith("select") or low.startswith("with")):
        return "ERROR: only SELECT / WITH queries are allowed."
    for banned in ("insert", "update", "delete", "drop", "create", "attach", "copy", "install"):
        if f" {banned} " in f" {low} ":
            return f"ERROR: '{banned}' is not permitted; this connection is read-only."
    try:
        con = duckdb.connect(DB, read_only=True)
        df = con.execute(q).df()
        con.close()
    except Exception as e:  # surfaced back to the model so it can repair the SQL
        return f"SQL ERROR: {e}"
    if df.empty:
        return "0 rows."
    out = df.head(100).to_string(index=False)
    if len(df) > 100:
        out += f"\n… {len(df):,} rows total, showing first 100."
    return out


@beta_tool
def get_schema_card() -> str:
    """Return the schema, column semantics, known data-quality traps, and example queries."""
    return SCHEMA_CARD


def build_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def ask(client: anthropic.Anthropic, question: str, history: list) -> list:
    history = history + [{"role": "user", "content": question}]
    kwargs = dict(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        tools=[run_sql, get_schema_card],
        messages=history,
    )
    # Claude Opus 5's safety classifiers can decline a request; server-side
    # fallbacks re-run it on the recommended model in the same call.
    try:
        runner = client.beta.messages.tool_runner(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
        )
        messages = list(runner)
    except anthropic.BadRequestError:
        runner = client.beta.messages.tool_runner(**kwargs)
        messages = list(runner)

    final = messages[-1] if messages else None
    if final is None:
        print("(no response)")
        return history
    if final.stop_reason == "refusal":
        print("The request was declined by safety classifiers.")
        return history

    text = "\n".join(b.text for b in final.content if b.type == "text").strip()
    print(textwrap.fill(text, width=100, replace_whitespace=False) if text else "(empty response)")
    return history + [{"role": "assistant", "content": final.content}]


def main() -> None:
    if not os.path.exists(DB):
        sys.exit(f"Database not found at {DB}\nBuild it first:  .venv/bin/python eda/build_v0.py")
    try:
        client = build_client()
    except Exception as e:
        sys.exit(f"Could not create an Anthropic client: {e}\n"
                 "Set ANTHROPIC_API_KEY, or run `ant auth login`.")

    if len(sys.argv) > 1:
        ask(client, " ".join(sys.argv[1:]), [])
        return

    print("Ask about the facility database. Ctrl-C or 'exit' to quit.\n")
    history: list = []
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if q.lower() in {"exit", "quit"}:
            return
        if not q:
            continue
        history = ask(client, q, history)


if __name__ == "__main__":
    main()
