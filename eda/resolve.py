#!/usr/bin/env python
"""
Phase 3 — cross-source entity resolution.

Turns 341,720 source records into one row per *real-world facility*, so that
`count(*)` stops being an upper bound (Gap 4).

Design, and why:

  Blocking is geo-primary.  Names are unusable on a large fraction of rows: 32,336
  records have a name that is nothing but its own facility type ('PRIMARY HEALTH
  CENTRE'), and 93 distinct facilities in Nanded district share that string. Any
  name+district matcher merges them into one. So geography proposes, name
  disposes.

  Matching is rule-based, not a single score threshold.  Every merge is stamped
  with the rule that caused it, so a wrong cluster can be traced to a rule and the
  rule can be changed. A tuned scalar score cannot be audited that way.

  Every rule is conservative by construction.  A false merge destroys a facility
  and is invisible in the output; a missed merge leaves the count too high and is
  visible as a duplicate. Given no labeled data, we take the visible error.

Precision/recall are NOT claimed here. eda/er_review_sample.csv is emitted for
hand-labeling; until that is labeled, the match rates below are unvalidated and
must be reported as such.
"""
import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

# ------------------------------------------------------------------ parameters
GEO_CELL = 0.01           # ~1.1 km blocking grid
MAX_BLOCK = 400           # blocks larger than this are split; leftovers reported
R_EARTH_KM = 6371.0

# Rule thresholds. Named so the report can quote them.
D_SAME_POINT = 0.05       # km — effectively the same coordinate
D_CLOSE = 0.50            # km
D_NEAR = 1.50             # km
D_GENERIC = 0.15          # km — the only distance at which a nameless row may merge
D_PHONE = 25.0            # km — a shared phone across more than this is a call centre
S_LOW, S_WEAK, S_NAME, S_STRONG, S_EXACT = 70, 60, 85, 92, 95


def haversine(lat1, lon1, lat2, lon2):
    p = np.pi / 180.0
    a = (np.sin((lat2 - lat1) * p / 2) ** 2
         + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * R_EARTH_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ------------------------------------------------------------------- blocking
def _pairs_from_blocks(keys, mask=None, max_block=MAX_BLOCK, label=""):
    """Yield candidate index pairs from equal-key blocks.

    Blocks over `max_block` are dropped rather than silently truncated, and the
    number of rows lost is returned so the caller can report it.
    """
    idx = np.arange(len(keys))
    if mask is not None:
        idx = idx[np.asarray(mask)]
    ks = pd.Series(np.asarray(keys)[idx], index=idx).dropna()
    ks = ks[ks.astype(str) != ""]
    out, dropped_rows, dropped_blocks = [], 0, 0
    for _, grp in ks.groupby(ks.values, sort=False):
        members = grp.index.values
        if len(members) < 2:
            continue
        if len(members) > max_block:
            dropped_rows += len(members)
            dropped_blocks += 1
            continue
        i, j = np.triu_indices(len(members), k=1)
        out.append(np.column_stack([members[i], members[j]]))
    pairs = np.vstack(out) if out else np.empty((0, 2), dtype=int)
    return pairs, {"block_pass": label, "oversized_blocks": dropped_blocks,
                   "rows_in_oversized_blocks": dropped_rows, "pairs": len(pairs)}


def candidate_pairs(d):
    """Five blocking passes, unioned. Each targets a different failure of the others."""
    n = len(d)
    lat, lon = d["latitude"].values, d["longitude"].values
    geo = d["geo_trust"].values.astype(bool) & np.isfinite(lat) & np.isfinite(lon)

    passes, stats = [], []

    # 1+2. Geo grid, and the same grid offset by half a cell. The offset pass is
    # what catches two records that sit 40 m apart but on opposite sides of a cell
    # boundary — a single grid silently misses those.
    for off, name in [(0.0, "geo_grid"), (GEO_CELL / 2, "geo_grid_offset")]:
        cell = np.where(
            geo,
            np.floor((lat + off) / GEO_CELL).astype("float64") * 1e6
            + np.floor((lon + off) / GEO_CELL).astype("float64"),
            np.nan)
        p, s = _pairs_from_blocks(cell, mask=geo, label=name)
        passes.append(p); stats.append(s)

    # 3. Name + district, for the 56,090 rows whose geo cannot be trusted.
    core = d["name_core"].fillna("").values
    informative = np.array([len(c) >= 5 for c in core])
    key = pd.Series(np.where(
        informative,
        d["state_norm"].fillna("") + "|" + d["district_canon"].fillna("") + "|"
        + pd.Series(core).str[:5],
        None))
    p, s = _pairs_from_blocks(key.values, label="name_district")
    passes.append(p); stats.append(s)

    # 4. Exact dialable phone — the only high-precision identifier in the data.
    p, s = _pairs_from_blocks(d["phone_key"].values, label="phone")
    passes.append(p); stats.append(s)

    # 5. Pincode + name prefix, for rows with a pincode but no usable geo.
    key = np.where(d["pincode_key"].notna().values & informative,
                   d["pincode_key"].fillna("").values + "|" + pd.Series(core).str[:4].values,
                   None)
    p, s = _pairs_from_blocks(key, label="pincode_name")
    passes.append(p); stats.append(s)

    allp = np.vstack([p for p in passes if len(p)])
    allp = np.unique(np.sort(allp, axis=1), axis=0)
    return allp, pd.DataFrame(stats), n


# -------------------------------------------------------------------- scoring
def score_pairs(d, pairs):
    """Score every candidate pair and apply the decision rules."""
    a, b = pairs[:, 0], pairs[:, 1]
    g = d.iloc[a].reset_index(drop=True), d.iloc[b].reset_index(drop=True)
    A, B = g

    dist = haversine(A["latitude"].values, A["longitude"].values,
                     B["latitude"].values, B["longitude"].values)
    both_geo = (A["geo_trust"].values.astype(bool) & B["geo_trust"].values.astype(bool)
                & np.isfinite(dist))
    dist = np.where(both_geo, dist, np.inf)

    # Name similarity on the identifying part of the name, falling back to the
    # full name when a core is absent on either side.
    ca, cb = A["name_core"].fillna("").values, B["name_core"].fillna("").values
    na, nb = A["name_norm"].fillna("").values, B["name_norm"].fillna("").values
    use_core = (np.char.str_len(ca.astype(str)) > 0) & (np.char.str_len(cb.astype(str)) > 0)
    xa = np.where(use_core, ca, na)
    xb = np.where(use_core, cb, nb)
    # token_sort_ratio, NOT token_set_ratio: the set variant scores 100 whenever one
    # token set is a subset of the other, so a core of 'AYURVEDA' matched
    # 'AYURVEDA VECHOOCHIRA' perfectly and chained 66 distinct dispensaries into
    # one facility. Subset agreement is not identity.
    sim = _cpdist(xa, xb)

    # How much identity each side's name actually carries. Both sides must clear
    # the bar a rule asks for — the weaker name governs.
    sa, sb = A["name_strength"].values, B["name_strength"].values
    strong = (sa == "STRONG") & (sb == "STRONG")
    medium = ((sa != "WEAK") & (sb != "WEAK")) & ~strong
    generic = (sa == "WEAK") | (sb == "WEAK")

    same_state = (A["state_norm"].values == B["state_norm"].values) & A["state_norm"].notna().values
    same_district = (same_state & (A["district_canon"].values == B["district_canon"].values)
                     & A["district_canon"].notna().values)
    same_pin = (A["pincode_key"].values == B["pincode_key"].values) & A["pincode_key"].notna().values
    same_phone = (A["phone_key"].values == B["phone_key"].values) & A["phone_key"].notna().values

    # Veto: different hard type classes are never the same facility. A blood bank
    # on a hospital campus shares the hospital's coordinate and must not absorb it.
    cla, clb = A["type_class"].values, B["type_class"].values
    known = pd.notna(cla) & pd.notna(clb)
    veto = known & (cla != clb)

    # Veto: different rungs of the public-health ladder. A sub-centre is built
    # next to its PHC, so 'KARAHALLI B SUBCENTER' 126 m from 'PHC KARAHALLI' is
    # two facilities, not one — and geo alone will always say otherwise.
    ta, tb = A["tier"].values, B["tier"].values
    veto |= np.isfinite(ta) & np.isfinite(tb) & (ta != tb)

    # Veto: two rows from the same source were already deduplicated within that
    # source by build_v0. Re-merging them here would silently undo that decision.
    veto |= (A["source_dataset"].values == B["source_dataset"].values)

    rule = np.full(len(pairs), "", dtype=object)

    def apply(name, cond):
        free = (rule == "") & ~veto
        rule[free & cond] = name

    # Order matters: the most specific evidence claims the pair first. Every rule
    # pairs a distance budget with a name-strength requirement — the further apart
    # two records are, the more the name has to carry.
    # A shared phone is strong evidence only nearby: a district health office
    # number appears against every CHC in the district, which merged two CHCs
    # 90 km apart in the first build.
    apply("R1_PHONE",       same_phone & (sim >= S_WEAK) & same_state
          & (~both_geo | (dist <= D_PHONE)))
    apply("R2_SAME_POINT",  (dist <= D_SAME_POINT) & (sim >= S_LOW) & ~generic)
    apply("R3_GEO_NAME",    (dist <= D_CLOSE) & (sim >= S_NAME) & strong)
    apply("R4_GEO_LOOSE",   (dist <= D_NEAR) & (sim >= S_EXACT) & strong)
    # A row whose name identifies nothing may only merge on a near-identical
    # coordinate, and only when the type agrees exactly.
    apply("R5_GEO_GENERIC", (dist <= D_GENERIC) & generic
          & (A["type_canon"].values == B["type_canon"].values))
    # One weak-but-present name (a single short token like 'CHITTAR'): treat it as
    # corroboration of a coincident point, never as evidence at distance.
    apply("R6_GEO_MEDIUM",  (dist <= D_GENERIC) & medium & (sim >= S_NAME))
    # No usable geo on at least one side: demand an almost-exact, long, specific
    # name inside one district.
    apply("R7_NAME_DIST",   ~both_geo & same_district & (sim >= S_EXACT) & strong
          & (np.char.str_len(ca.astype(str)) >= 10))
    apply("R8_PIN_NAME",    ~both_geo & same_pin & (sim >= S_EXACT) & strong)

    return pd.DataFrame({
        "i": a, "j": b, "name_sim": sim, "dist_km": np.where(np.isfinite(dist), dist, np.nan),
        "same_state": same_state, "same_district": same_district,
        "same_pincode": same_pin, "same_phone": same_phone,
        "generic_name": generic, "type_veto": veto, "match_rule": rule,
    })


def _cpdist(xa, xb):
    """Elementwise fuzzy similarity, multithreaded when the installed rapidfuzz
    supports it."""
    try:
        return np.asarray(process.cpdist(list(xa), list(xb),
                                         scorer=fuzz.token_sort_ratio, workers=-1),
                          dtype=float)
    except AttributeError:
        return np.array([fuzz.token_sort_ratio(p, q) for p, q in zip(xa, xb)], dtype=float)


# ----------------------------------------------------------- transitive closure
class DSU:
    def __init__(self, n):
        self.p = list(range(n))
        self.r = [0] * n

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, x, y):
        a, b = self.find(x), self.find(y)
        if a == b:
            return False
        if self.r[a] < self.r[b]:
            a, b = b, a
        self.p[b] = a
        self.r[a] += self.r[a] == self.r[b]
        return True


def cluster(n, matched):
    """Transitive closure over accepted pairs -> a cluster id per record.

    Transitivity is a real risk: A~B and B~C forces A~C even where A and C would
    never have matched directly. Cluster sizes are reported so runaway chains are
    visible rather than assumed away.
    """
    dsu = DSU(n)
    for i, j in zip(matched["i"].values, matched["j"].values):
        dsu.union(int(i), int(j))
    return np.array([dsu.find(k) for k in range(n)])
