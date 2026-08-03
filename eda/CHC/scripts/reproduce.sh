#!/bin/sh
# Reproduce every number in eda/CHC/.
#
# PHC and CHC share a byte-identical 9-column schema and were profiled together in
# one session, so the analysis scripts live in eda/PHC/scripts/ and are parameterised
# by dataset key. This script runs them for CHC. Nothing here writes to the source CSVs.
#
#   sh eda/CHC/scripts/reproduce.sh
set -e
cd "/Users/ankitraj2/asar master data"

# 1. Per-column profile -> eda/CHC/profile.json  (+ a full report on stdout)
.venv/bin/python eda/PHC/scripts/profile_phc_chc.py CHC

# 2. Deep dive + PHC<->CHC cross analysis -> eda/PHC/cross_stats.json
#    (ID namespace, row overlap, FAC_CATEGO, geo consistency, ER blocking simulation)
.venv/bin/python eda/PHC/scripts/deep_and_cross.py

# 3. Concrete row indices and values for every defect cited in issues.md
.venv/bin/python eda/PHC/scripts/issue_examples.py

# 4. Patch profile.json into the final contract shape (roles, flags, er_readiness,
#    tier_reliability, cross_file). Recomputes every figure from the CSVs.
.venv/bin/python eda/PHC/scripts/finalize_profiles.py
