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
DB = os.path.join(HERE, "db", "facilities_v1.duckdb")

MODEL = "claude-opus-5"
MAX_TOKENS = 16000

# The agent binds to the two views, never the base tables. Both are PII-free by
# construction (NIN's `Coder` column of internal staff names is never ingested).
VIEWS = ("v_facility", "v_source_record")

# Populated by run_sql during a turn so callers can show their work.
# Each entry: {"sql": str, "df": DataFrame | None, "error": str | None}
QUERY_LOG: list = []


def reset_log() -> None:
    QUERY_LOG.clear()


SCHEMA_CARD = """
# facility database — schema card

Two read-only views:

- **`v_facility`** — 323,359 rows, ONE ROW PER RESOLVED FACILITY. Query this for
  counts, rankings, and anything about facilities.
- **`v_source_record`** — 341,720 rows, one per source record, with
  `facility_uid` linking back to `v_facility`. Query this for provenance
  ("which datasets list this?") and per-source questions.

## THE CAVEAT THAT GOVERNS EVERY TOTAL
Cross-source entity resolution HAS been run (v1), so `count(*)` on `v_facility`
is a facility count, not a record count. But the matcher is UNVALIDATED — there
is no hand-labeled pair set yet, so no precision/recall figure exists.

It is deliberately conservative: it merged 18,361 records (5.4%). Missed matches
are far more likely than false ones, so a total from `v_facility` is best read
as a SLIGHT OVER-COUNT — much closer to the truth than v0's 341,720, but still
an upper bound. Say this when you report a national or state total. Do not
present it as an exact census.

## v_facility columns (one row per facility)

| column | notes |
|---|---|
| facility_uid | PK, e.g. "F0012345" |
| name, name_norm | 100%. `name_core` is the name minus type words ('PHC KHERA' -> 'KHERA') |
| facility_type | 99.6% — CONTROLLED ENUM, see below |
| type_class | CARE / BLOOD / DIAG / RETAIL — coarse grouping |
| ownership | GOVERNMENT 160688 · PRIVATE_FOR_PROFIT 112091 · UNKNOWN 47490 · PRIVATE_NOT_FOR_PROFIT 1975 · PPP 1115 |
| state | 100%, 36 values, UPPERCASE ('BIHAR', 'TAMIL NADU', 'NCT OF DELHI') |
| district | 99.9%, clustered to 914 canonical spellings (see Trap 2) |
| block, village, city, pincode | sparse; pincode 10.5% |
| latitude, longitude, geo_trust | position is the median of the cluster's trusted points; geo_trust true on 83.0% |
| phone, email, address | phone 4.4% (only digits that are actually dialable are kept) |
| specialty_raw, specialty_code_system | 7% — see Trap 3 |
| bed_count | 0.1% — effectively unusable |
| n_source_records, n_sources, sources | e.g. n_sources=3, sources='CGHS,NHA,PMJAY' |
| resolution_status | SINGLE_SOURCE 309868 · MERGED_CROSS_SOURCE 13479 · REVIEW_LARGE_CLUSTER 12 |
| first_snapshot, last_snapshot | date range of the contributing sources |

## v_source_record columns (provenance)
`record_uid`, `facility_uid`, `source_dataset`, `source_facility_id`, plus the
raw and canonical forms of each field: `facility_type_raw` vs `facility_type`,
`district_raw` vs `district`, `facility_ownership_raw` vs `ownership`.
Source sizes: NHA 261905 · PHC 31958 · PMGSY 13700 · PMJAY 11284 · NIN 10327 ·
CDAC_BB 5678 · CHC 4237 · CGHS 1983 · NHP 648.

## Trap 1 — facility_type is now an enum; use `=`, not LIKE
SUB_CENTRE 86587 · PHC 52053 · HOSPITAL 44568 · PHARMACY 29659 ·
WELLNESS_CENTRE 28123 · CLINIC 17904 · CHC 13974 · DIAGNOSTIC_LAB 10878 ·
DISPENSARY 7686 · AYUSH 6951 · MATERNITY_HOME 5452 · DENTAL 5319 ·
BLOOD_BANK 3400 · DISTRICT_HOSPITAL 2978 · MEDICAL_COLLEGE 2183 ·
BLOOD_STORAGE_UNIT 1473 · UNKNOWN 1256 · OTHER 858 ·
SUB_DISTRICT_HOSPITAL 761 · IMAGING_CENTRE 722 · PHYSIOTHERAPY 344 ·
DIALYSIS_CENTRE 230
The label is derived from NAME TOKENS first (70% of rows), source type column
second, because the source columns are unreliable — PHC/CHC carry the filename
tier (~4% leak) and NHP's was a constant. `WELLNESS_CENTRE` is mostly PHCs and
sub-centres relabelled as HWCs under Ayushman Bharat, so counting "PHCs" may
warrant including it; mention that rather than silently choosing.

## Trap 2 — district is clustered, not authoritative
1,051 raw spellings were clustered within state to 914 canonical values
(KASARGOD -> KASARAGOD). India has ~790 districts, so ~120 spellings are still
unmerged — clustering catches typos, not renames (Gurgaon/Gurugram,
Allahabad/Prayagraj are still separate). District counts remain APPROXIMATE and
you should say so. `v_source_record.district_raw` holds the original.

## Trap 3 — specialties are undecoded AND nearly absent
`specialty_raw` holds opaque codes (`M1`, `S7`, …). There is no codebook: the
meaning of each code is UNKNOWN. Only 23,615 records (7.0%) carry any specialty
at all, and NHA's column is populated on just 4% of its rows.
=> You CANNOT answer "which hospitals offer cardiology". Say so directly and
explain that the PM-JAY Health Benefit Package specialty master is needed.
Never guess what a code means.

## Trap 4 — geo
Use `geo_trust` for anything spatial. 17% of facilities fail it (centroid
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
   SELECT ownership, count(*) FROM v_facility GROUP BY 1 ORDER BY 2 DESC;

Q: How many CHCs are there?
   SELECT count(*) FROM v_facility WHERE facility_type = 'CHC';

Q: Which facilities are confirmed by more than one source?
   SELECT sources, count(*) n FROM v_facility WHERE n_sources > 1
   GROUP BY 1 ORDER BY 2 DESC;

Q: Which datasets list a particular facility, and what did each call it?
   SELECT s.source_dataset, s.name, s.facility_type_raw
   FROM v_source_record s JOIN v_facility f USING (facility_uid)
   WHERE f.name ILIKE '%devamatha%';

Q: How much did resolution actually collapse, per source?
   SELECT source_dataset, count(*) records, count(DISTINCT facility_uid) facilities
   FROM v_source_record GROUP BY 1 ORDER BY 2 DESC;

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
        query: A single SELECT (or WITH ... SELECT) statement. Query
            `v_facility` (one row per resolved facility) and `v_source_record`
            (provenance); they join on `facility_uid`. Results are truncated to
            100 rows.
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
    """Per-source record counts and the facilities they resolve to, for the sidebar."""
    df, _ = execute_sql(
        "SELECT source_dataset AS source, count(*) AS records, "
        "       count(DISTINCT facility_uid) AS facilities "
        "FROM v_source_record GROUP BY 1 ORDER BY 2 DESC")
    return df if df is not None else pd.DataFrame()


def resolution_summary() -> dict:
    """Headline v1 numbers for the dashboard."""
    df, _ = execute_sql(
        "SELECT (SELECT count(*) FROM v_source_record) AS records, "
        "       (SELECT count(*) FROM v_facility) AS facilities, "
        "       (SELECT count(*) FROM v_facility WHERE n_sources > 1) AS multi_source")
    return df.iloc[0].to_dict() if df is not None and not df.empty else {}
