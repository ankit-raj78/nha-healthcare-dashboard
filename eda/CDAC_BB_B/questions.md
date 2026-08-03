# CDAC_BB_B — open questions for a human or an external source

Each item states what I could not determine from the file, what I checked, and what specific
answer would unblock the harmonisation step. Questions Q-3 … Q-10 in
`eda/CDAC_BB_A/questions.md` (geocoder provenance, `Holy Cross Hospital` ownership conflict, the
`Red Cross` category, `BSU`/`BSC`, the name-embedded abbreviation vocabulary, repeated
coordinates) apply verbatim to this file too — the underlying records are the same. The questions
below are the ones **specific to this file**.

---

## Q-B1 · Why does this file exist, and which one is the sanctioned export?

**What I found:** rows 0–5678 of this file are the same records in the same order as
`16_MAY_AR_CDAC_BB_DATASET.csv` (CDAC_BB_A) rows 0–5678, and rows 5679–5888 are a verbatim
re-append of this file's own rows 5469–5678. It contains **zero facilities** that CDAC_BB_A does
not contain. Yet its mtime is 2025-11-23, five months *after* CDAC_BB_A's (2025-06-20), and its
filename (`- Sheet1`) says it was exported from a Google Sheet.

Neither file is a clean parent of the other: this file has better `Name`/`Address`/`Email` casing
and the correct `Serchhip` spelling, while CDAC_BB_A has correct state spellings, the Sikkim
labels, complete coordinates, and two district columns. Both descend from a common ancestor via
different edits.

**What I need:** which of these two files (if either) is the one the data owner considers
authoritative, and whether the Google Sheet still exists — because the *ancestor* would be
strictly better than either descendant. If the sheet is live, re-exporting it may make this whole
reconciliation moot.

---

## Q-B2 · Was the 210-row duplication (rows 5679–5888) intentional?

The tail block is byte-identical to rows 5469–5678 in every field except `Latitude`/`Longitude`,
where the tail copy has more decimal places for the *same point* (median separation **0.4 metres**,
max 0.75 m). That reads like someone re-pasted the block to restore precision lost to a
spreadsheet display rounding — and then forgot to delete the rounded copy.

**What I need:** confirmation that the tail copy is the intended one, so I can recommend
"keep 5679–5888, drop 5469–5678" rather than the reverse. If nobody knows, the 0.4 m difference
is immaterial and either copy will do — but I will not assert intent I cannot verify.

---

## Q-B3 · How did Sikkim become Rajasthan, and are there other silent relabels?

Rows 3716–3720 carry `State = "Rajasthan"` but are unambiguously Sikkim facilities (their
`Address` fields say `East Sikkim`, `west sikkim`). Rows 3711–3715 are genuine Rajasthan rows, so
this looks like a fill-down that overran by five rows at a sort boundary.

I checked every other state's block by cross-referencing the positional `State` mapping against
CDAC_BB_A and found **no other** relabel: the remaining 36 A→B state mappings are one-to-one. But
that check only works because CDAC_BB_A exists as a reference. If a fill-down error also affected
the *common ancestor*, both files would carry it and I would not detect it.

**What I need:** a spot-check of a few states' blood-centre counts against the live e-RaktKosh
portal — specifically Rajasthan (383 expected) and any state where the counts here differ from
another source.

---

## Q-B4 · Where did the `District` and `dist_name` columns go?

CDAC_BB_A has two district columns; this file has none. `District` is recoverable by parsing the
trailing `Dist. <X>` token from `Address` (works for 5,888/5,889 rows, and reproduces CDAC_BB_A's
`District` for 5,677/5,679 shared rows). `dist_name` — the **legacy/LGD district alias** — is not:
it matches the parsed address token for only 5,040/5,679 rows, so 639 aliases exist nowhere in
this file.

**What I need:** whether `District`/`dist_name` were *added* to CDAC_BB_A by a later enrichment
step (in which case they may exist as a separate lookup we should use directly), or *dropped* from
this file during the Google Sheet export. If they were added, the enrichment's source matters —
`dist_name` is the field we would use for LGD-code joins, and I cannot assess its authority
without knowing where it came from.

---

## Q-B5 · Are the 25 missing coordinates missing upstream, or lost in this export?

Rows 875, 911, 917, 1458, 1470, 1471, 1495, 1515, 1610, 1772, 2803, 2825, 3805, 3995, 4008, 4016,
4041, 4094, 4132, 4267, 4271, 4274, 5279, 5394, 5428 have null `Latitude` *and* `Longitude`. All
25 are BSU/RH rows, concentrated in Tamil Nadu (10), Karnataka (7), Gujarat (3) and West Bengal (3).
CDAC_BB_A has a valid in-India coordinate for all 25.

**What I need:** whether CDAC_BB_A's values for these rows came from the portal (in which case
this file simply lost them, and A is authoritative) or from a later geocoding pass (in which case
they should be flagged `geo_source = derived` rather than treated as source truth). I could not
determine this: A's values for these rows are at 8-decimal precision, which is characteristic of a
geocoder, but so are 29 other rows in A that this file also carries.
