#!/usr/bin/env bash
# Launch the natural-language health-facility dashboard.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f db/facilities_v0.duckdb ]; then
  echo "Database missing — building it first…"
  .venv/bin/python eda/build_v0.py
fi

if [ ! -f db/facilities_v1.duckdb ] || [ db/facilities_v0.duckdb -nt db/facilities_v1.duckdb ]; then
  echo "Resolving entities (v1)…"
  .venv/bin/python eda/build_v1.py
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ ! -d "$HOME/.config/anthropic" ]; then
  echo "warning: ANTHROPIC_API_KEY is not set and no 'ant auth login' profile found."
  echo "         The dashboard will load, but queries will fail until you set one."
  echo
fi

exec .venv/bin/streamlit run dashboard.py "$@"
