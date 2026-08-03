"""
Shared agent core for the health-facility database.

Both `ask.py` (CLI) and `dashboard.py` (Streamlit) import from here, so the
schema card, guardrails, and model choice can never drift between them.

Architecture: hybrid text-to-SQL. DuckDB produces every number; the model only
writes the SQL. See eda/00_PLAN.md for why this is not a vector RAG.
"""
import os

import anthropic
import duckdb
import pandas as pd
from anthropic import beta_tool

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "db", "facilities_v0.duckdb")

MODEL = "claude-opus-5"
MAX_TOKENS = 16000

# The agent binds to v_facility, never the base table — v_facility is PII-free by
# construction (NIN's `Coder` column of internal staff names is never ingested).
VIEW = "v_facility"

# Populated by run_sql during a turn so callers can show their work.
# Each entry: {"sql": str, "df": DataFrame | None, "error": str | None}
QUERY_LOG: list = []


def reset_log() -> None:
    QUERY_LOG.clear()


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

## Trap 5 — in NHA, `state` and the coordinates can disagree
Confirmed for Goa: of 52 NHA rows labelled GOA, only 1 is inside Goa's bounding
box; the rest scatter as far as Madhya Pradesh. Every other source is correct
for Goa. NHA is 77% of all records, so a state-filtered query mostly returns NHA
rows and inherits this.
=> For small states especially, sanity-check results against the coordinates,
and flag the disagreement to the user rather than reporting the count silently.
The scope beyond Goa is NOT yet established — do not claim it is or isn't
widespread; say it is confirmed for Goa and unquantified elsewhere.

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
- When a result is a list of places, prefer selecting latitude and longitude too
  so the caller can map it.
- Answer in prose, leading with the result. Keep it tight — the caller sees your
  SQL and result tables separately, so do not repeat them row by row.

{SCHEMA_CARD}
"""

_BANNED = ("insert", "update", "delete", "drop", "create", "attach", "copy", "install", "pragma")


def execute_sql(query: str) -> tuple[pd.DataFrame | None, str | None]:
    """Run a guarded read-only SELECT. Returns (dataframe, error)."""
    q = query.strip().rstrip(";")
    low = q.lower()
    if not (low.startswith("select") or low.startswith("with")):
        return None, "only SELECT / WITH queries are allowed."
    for banned in _BANNED:
        if f" {banned} " in f" {low} ":
            return None, f"'{banned}' is not permitted; this connection is read-only."
    try:
        con = duckdb.connect(DB, read_only=True)
        df = con.execute(q).df()
        con.close()
        return df, None
    except Exception as e:
        return None, str(e)


@beta_tool
def run_sql(query: str) -> str:
    """Run a read-only DuckDB SELECT against the facility database.

    Args:
        query: A single SELECT (or WITH ... SELECT) statement. Only `v_facility`
            may be queried. Results are truncated to 100 rows.
    """
    df, err = execute_sql(query)
    QUERY_LOG.append({"sql": query.strip(), "df": df, "error": err})
    if err:
        return f"SQL ERROR: {err}"
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


TOOLS = [run_sql, get_schema_card]


def build_client() -> anthropic.Anthropic:
    """Resolves ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile."""
    return anthropic.Anthropic()


def answer(client: anthropic.Anthropic, messages: list) -> tuple[str, list, list]:
    """Run one agent turn.

    Returns (reply_text, updated_messages, queries) where `queries` is the list
    of SQL statements executed this turn with their result frames.
    """
    reset_log()
    kwargs = dict(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        tools=TOOLS,
        messages=messages,
    )
    # Claude Opus 5's safety classifiers can decline a request; server-side
    # fallbacks re-run it on the recommended model within the same call.
    try:
        turns = list(client.beta.messages.tool_runner(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs))
    except anthropic.BadRequestError:
        turns = list(client.beta.messages.tool_runner(**kwargs))

    queries = list(QUERY_LOG)
    if not turns:
        return "(no response)", messages, queries

    final = turns[-1]
    if final.stop_reason == "refusal":
        return "This request was declined by safety classifiers.", messages, queries

    text = "\n".join(b.text for b in final.content if b.type == "text").strip()
    return (text or "(empty response)"), messages + [{"role": "assistant", "content": final.content}], queries


def db_stats() -> pd.DataFrame:
    """Per-source record counts, for the dashboard sidebar."""
    df, _ = execute_sql(
        "SELECT source_dataset AS source, count(*) AS records "
        "FROM v_facility GROUP BY 1 ORDER BY 2 DESC")
    return df if df is not None else pd.DataFrame()
