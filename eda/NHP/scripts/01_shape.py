"""NHP EDA step 1: establish true shape, line counts, BOM, embedded newlines."""
import csv, io, json, os, sys
import pandas as pd

SRC = "/Users/ankitraj2/asar master data/8_JULY_23_SRK_NHP_validated_and_standardized.csv"

raw = open(SRC, "rb").read()
print("bytes:", len(raw))
print("starts with BOM:", raw[:3] == b"\xef\xbb\xbf")
print("count b'\\r\\n':", raw.count(b"\r\n"))
print("count b'\\n':", raw.count(b"\n"))
print("count lone \\n (not preceded by \\r):", raw.count(b"\n") - raw.count(b"\r\n"))
print("count lone \\r (not followed by \\n):", raw.count(b"\r") - raw.count(b"\r\n"))
print("ends with newline:", raw[-2:])

# wc -l counts \n bytes
print("wc -l equivalent:", raw.count(b"\n"))

text = raw.decode("utf-8-sig")
# python universal-newline splitlines
print("splitlines() count:", len(text.splitlines()))

# csv module logical rows
rdr = csv.reader(io.StringIO(text, newline=""))
rows = list(rdr)
print("csv.reader logical rows (incl header):", len(rows))
print("header:", repr(rows[0]))
print("header len:", len(rows[0]))
widths = {}
for r in rows[1:]:
    widths[len(r)] = widths.get(len(r), 0) + 1
print("data row widths:", widths)

# how many logical rows contain an embedded newline in ANY field
n_multiline = 0
field_nl = {}
for i, r in enumerate(rows[1:]):
    hit = False
    for j, v in enumerate(r):
        if "\n" in v or "\r" in v:
            hit = True
            field_nl[rows[0][j] if j < len(rows[0]) else f"col{j}"] = field_nl.get(rows[0][j] if j < len(rows[0]) else f"col{j}", 0) + 1
    if hit:
        n_multiline += 1
print("logical data rows containing an embedded newline:", n_multiline)
print("embedded-newline counts by column:", json.dumps(field_nl, indent=2))

# total number of extra physical lines contributed by embedded newlines
extra = 0
for r in rows[1:]:
    for v in r:
        extra += v.count("\n")
hdr_extra = sum(v.count("\n") for v in rows[0])
print("extra physical lines from embedded \\n in DATA:", extra)
print("extra physical lines from embedded \\n in HEADER:", hdr_extra)
print("check: 1 header logical + %d data logical + %d embedded = %d" % (
    len(rows) - 1, extra + hdr_extra, 1 + (len(rows) - 1) + extra + hdr_extra))
