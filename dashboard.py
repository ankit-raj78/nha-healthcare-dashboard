#!/usr/bin/env python
"""
Streamlit dashboard — natural-language querying over the health-facility database.

    ./launch.sh          (or)    .venv/bin/streamlit run dashboard.py

Every number shown comes from DuckDB. The model writes SQL; it does not compute
answers. The SQL it ran is always shown so you can check it.
"""
import os

import pandas as pd
import streamlit as st

import agent

st.set_page_config(page_title="Health Facility Explorer", page_icon="🏥", layout="wide")

# ------------------------------------------------------------------ styling
st.markdown("""
<style>
  .stChatMessage { background: transparent; }
  code { font-size: 0.85rem; }
  .caveat {
    border-left: 3px solid #d97706; padding: 0.6rem 0.9rem; border-radius: 4px;
    background: rgba(217,119,6,0.08); font-size: 0.88rem; line-height: 1.5;
  }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------- helpers
@st.cache_data(show_spinner=False)
def load_stats() -> pd.DataFrame:
    return agent.db_stats()


@st.cache_resource(show_spinner=False)
def get_client():
    return agent.build_client()


def has_geo(df: pd.DataFrame) -> bool:
    cols = {c.lower() for c in df.columns}
    return {"latitude", "longitude"}.issubset(cols) and len(df) <= 5000


def render_queries(queries: list) -> None:
    """Show the SQL the model ran, plus each result — this is the audit trail."""
    if not queries:
        return
    label = f"SQL executed ({len(queries)} quer{'y' if len(queries) == 1 else 'ies'})"
    with st.expander(label, expanded=False):
        for i, q in enumerate(queries, 1):
            st.code(q["sql"], language="sql")
            if q["error"]:
                st.warning(f"Query {i} errored — the model then repaired it: {q['error']}")
                continue
            df = q["df"]
            if df is None or df.empty:
                st.caption("0 rows.")
                continue
            st.dataframe(df.head(500), width="stretch", height=min(340, 40 + 28 * len(df)))
            if len(df) > 500:
                st.caption(f"{len(df):,} rows total; showing first 500.")
            if has_geo(df):
                pts = df.rename(columns={c: c.lower() for c in df.columns})
                pts = pts[["latitude", "longitude"]].dropna()
                if not pts.empty:
                    st.map(pts, size=20)
            st.download_button(
                "Download CSV", df.to_csv(index=False).encode(),
                file_name=f"query_{i}.csv", mime="text/csv", key=f"dl_{id(q)}_{i}")


# ---------------------------------------------------------------- preflight
if not os.path.exists(agent.DB):
    st.error(f"Database not found at `{agent.DB}`")
    st.code(".venv/bin/python eda/build_v0.py && .venv/bin/python eda/build_v1.py",
            language="bash")
    st.stop()

# ------------------------------------------------------------------- sidebar
with st.sidebar:
    st.subheader("Database")
    stats = load_stats()
    summary = agent.resolution_summary()
    c1, c2 = st.columns(2)
    c1.metric("Facilities", f"{int(summary.get('facilities', 0)):,}")
    c2.metric("Source records", f"{int(summary.get('records', 0)):,}")
    st.caption(f"{int(summary.get('multi_source', 0)):,} facilities are confirmed "
               "by more than one source.")
    st.dataframe(stats, width="stretch", hide_index=True,
                 column_config={
                     "records": st.column_config.NumberColumn(format="%d"),
                     "facilities": st.column_config.NumberColumn(format="%d")})

    st.caption(f"Model: `{agent.MODEL}`  ·  adaptive thinking")

    st.divider()
    st.subheader("Known limits")
    st.markdown("""
- **The matcher is unvalidated.** Entity resolution has run, but with no
  hand-labeled pairs there is no precision/recall figure. It is deliberately
  conservative, so totals are a slight over-count.
- **Districts are clustered, not authoritative.** 1,051 spellings → 914; India
  has ~790 districts, so renames (Gurgaon/Gurugram) are still split.
- **Specialties can't be answered.** The `M1`/`S7` codes have no codebook, and
  only 7% of records carry one at all.
- **Bed counts** are 0.1% populated.
""")
    st.caption("Detail: `eda/04_MERGE_REPORT.md` · `eda/03_GAP_REGISTER.md`")

    st.divider()
    if st.button("Clear conversation", width="stretch"):
        st.session_state.messages = []
        st.session_state.turns = []
        st.rerun()

# --------------------------------------------------------------------- main
st.title("🏥 Health Facility Explorer")
st.caption("Ask in plain English. DuckDB produces every number — the model only writes the SQL.")

st.markdown(
    '<div class="caveat"><b>v1 data.</b> 341,720 source records resolved to 323,359 '
    'facilities. The matcher is conservative and has no measured precision yet, so '
    'totals still lean high. The assistant states this where it matters.</div>',
    unsafe_allow_html=True)
st.write("")

if "messages" not in st.session_state:
    st.session_state.messages = []   # API-shaped history
    st.session_state.turns = []      # display history: (role, text, queries)

# Starter questions, shown only on an empty conversation
if not st.session_state.turns:
    st.markdown("**Try one of these**")
    examples = [
        "Which states have the most facilities?",
        "How many CHCs are there?",
        "Public vs private ownership split",
        "Blood banks vs blood storage units",
        "Which facilities are confirmed by more than one source?",
        "How much did entity resolution collapse each source?",
    ]
    cols = st.columns(3)
    for i, ex in enumerate(examples):
        if cols[i % 3].button(ex, key=f"ex{i}", width="stretch"):
            st.session_state.pending = ex
            st.rerun()

# Replay history
for role, text, queries in st.session_state.turns:
    with st.chat_message(role):
        st.markdown(text)
        if role == "assistant":
            render_queries(queries)

prompt = st.chat_input("e.g. how many 24x7 facilities are in Bihar?")
if "pending" in st.session_state:
    prompt = st.session_state.pop("pending")

if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.turns.append(("user", prompt, []))

    try:
        client = get_client()
    except Exception as e:
        st.error(f"Could not create an Anthropic client: {e}\n\n"
                 "Set `ANTHROPIC_API_KEY` in your environment, then restart.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant"):
        with st.spinner("Querying…"):
            try:
                text, msgs, queries = agent.answer(client, st.session_state.messages)
            except Exception as e:
                text, msgs, queries = f"**Request failed:** {e}", st.session_state.messages, []
        st.markdown(text)
        render_queries(queries)

    st.session_state.messages = msgs
    st.session_state.turns.append(("assistant", text, queries))
