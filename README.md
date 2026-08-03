# Indian Health Facility Data — queryable in natural language

Ten government health-facility datasets, profiled, harmonized, and loaded into a
DuckDB database you can query in plain English.

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # or: ant auth login

./launch.sh                                 # web dashboard
./ask.py "how many facilities are in Bihar?" # one-shot CLI
./ask.py --sql                              # interactive, showing the SQL
```

The model writes SQL; **DuckDB produces the numbers**. Aggregations are never
guessed by the LLM — that's why this is a hybrid text-to-SQL agent rather than a
vector RAG over the rows. Every answer shows the SQL it ran, so you can check it.

Model: `claude-opus-5` with adaptive thinking ($5 / $25 per MTok).

## Layout

| Path | What |
|---|---|
| `agent.py` | Shared core — schema card, SQL guardrails, model config |
| `dashboard.py` | Streamlit UI (chat, SQL audit trail, maps, CSV export) |
| `ask.py` | CLI |
| `launch.sh` | Builds the DB if missing, then starts the dashboard |
| `datasets/` | The 10 source CSVs — untracked, 124 MB |
| `eda/` | Per-dataset profiles, the plan, and the gap register |
| `eda/build_v0.py` | Ingests all 10 CSVs → `db/facilities_v0.duckdb` |
| `db/` | Built database — untracked, regenerate with the script above |
| `archive/` | Superseded prior work (see below) |

`ask.py` and `dashboard.py` both import `agent.py`, so the schema card and
guardrails cannot drift between the two interfaces.

Start with **[eda/00_PLAN.md](eda/00_PLAN.md)** for the architecture,
**[eda/02_PHASE1_FINDINGS.md](eda/02_PHASE1_FINDINGS.md)** for what the data
actually contains, and **[eda/03_GAP_REGISTER.md](eda/03_GAP_REGISTER.md)** for
what's missing and what to go fetch.

## The data

341,720 source records across 10 datasets:

```
NHA 261,905 · PHC 31,958 · PMGSY 13,700 · PMJAY 11,284 · NIN 10,327
CDAC_BB 5,678 · CHC 4,237 · CGHS 1,983 · NHP 648
```

Raw line counts were wrong for 5 of 6 datasets checked — embedded newlines,
blank-row blocks, and duplicated files inflated them by 8,100 rows before any
deduplication. NHA's 323,460 raw rows collapse to **258,756 real facilities**
once a `24/7` yes/no fan-out is removed.

**This is v0: harmonized and deduplicated within each source, but with no
cross-source entity resolution yet.** `count(*)` is an upper bound on source
records, not a facility count — at least 8,408 name+district groups span more
than one source. The agent is instructed to state this on every total.

## What it can and can't answer

Works: counts and rankings by state, source composition, ownership splits, blood
bank vs storage unit, geographic and radius queries, single-facility lookup.

Doesn't work yet:

- **Specialties.** The `M1`/`S7` codes have no codebook and only 7% of records
  carry any specialty at all. Needs the PM-JAY Health Benefit Package master.
- **Bed counts.** 0.1% populated.
- **True facility counts.** Needs entity resolution (Phase 3).

District-level numbers are approximate until the LGD crosswalk lands — there are
1,051 distinct district spellings for ~790 real districts.

**NHA state labels are unreliable.** Of 52 NHA rows labelled Goa, only 1 is
actually inside Goa; every other source is correct. NHA is 77% of all records, so
state-filtered queries inherit this. Scope beyond Goa is not yet established.

## Privacy

The agent binds to `v_facility`, a view that is PII-free by construction: NIN's
`Coder` column (internal staff names) is never ingested from the source CSV.

## Archived prior work

The earlier merge pipeline (`master_merger.py`, the Streamlit dashboards, and
`healthcare_master_dataset.csv`) is superseded and moved to `archive/`. It is
**not** used as a baseline — its output carried ~62K duplicate NHA rows and 351
phantom NHP rows, and its match rates were never validated. Code and reports are
zipped at `archive/prior_work_code.zip`; the bulk data sits under `archive/dirs`
(1.7 GB) and `archive/derived_data` (395 MB), deletable once you're satisfied
nothing is needed from them.
