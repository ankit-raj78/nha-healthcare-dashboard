"""NHP EDA step 4: quantify embedded newlines / doubled spaces in text fields
and validate an exact normalization rule."""
import csv, io, re, json
from collections import Counter

SRC = "/Users/ankitraj2/asar master data/8_JULY_23_SRK_NHP_validated_and_standardized.csv"
text = open(SRC, "rb").read().decode("utf-8-sig")
rows = list(csv.reader(io.StringIO(text, newline="")))
hdr = [h for h in rows[0]]
data = [r for r in rows[1:] if any(v.strip() for v in r)]
print("real data rows:", len(data))

TEXT_COLS = ["Hospital Name", "Given Address", "Standardized Address", "City",
             "State", "Country", "Type", "Source Sheet Name", "address_py"]
idx = {h: i for i, h in enumerate(hdr) if h}

def stats(colname):
    i = idx[colname]
    vals = [r[i] for r in data]
    nonempty = [v for v in vals if v.strip()]
    c = Counter()
    for v in nonempty:
        if "\n" in v: c["embedded_newline"] += 1
        if "\r" in v: c["embedded_cr"] += 1
        if re.search(r"  +", v): c["double_space"] += 1
        if re.search(r"[ \t]*\n[ \t]*", v): c["nl_with_pad"] += 1
        if v != v.strip(): c["untrimmed"] += 1
        if " " in v: c["nbsp"] += 1
        if re.search(r"\s,", v): c["space_before_comma"] += 1
        if v.endswith("."): c["trailing_period"] += 1
    return len(nonempty), dict(c)

print("\n=== whitespace anomaly counts (denominator = non-empty values) ===")
for c in TEXT_COLS:
    n, s = stats(c)
    print(f"{c!r}: n={n} {s}")

# Exact newline context: what are the surrounding chars?
print("\n=== exact context around each embedded newline ===")
ctx = Counter()
for r in data:
    for h in TEXT_COLS:
        v = r[idx[h]]
        for m in re.finditer(r"\n", v):
            a, b = m.start(), m.end()
            before = v[max(0, a-1):a]
            after = v[b:b+4]
            ctx[(repr(before), repr(after))] += 1
for k, v in ctx.most_common(20):
    print("   ", k, v)

# Proposed normalization: collapse ALL runs of whitespace to a single space, then strip.
NORM = lambda s: re.sub(r"\s+", " ", s).strip()

print("\n=== effect of NORM = re.sub(r'\\s+',' ',s).strip() ===")
for c in TEXT_COLS:
    i = idx[c]
    vals = [r[i] for r in data if r[i].strip()]
    changed = sum(1 for v in vals if NORM(v) != v)
    print(f"{c!r}: {changed}/{len(vals)} values changed ({100*changed/max(len(vals),1):.2f}%)")

# Does normalization collapse distinct names? (i.e. reveal duplicates)
hn = idx["Hospital Name"]
raw_names = [r[hn] for r in data if r[hn].strip()]
print("\nHospital Name: raw distinct =", len(set(raw_names)))
print("Hospital Name: NORM distinct =", len(set(NORM(v) for v in raw_names)))
print("Hospital Name: NORM+casefold distinct =", len(set(NORM(v).casefold() for v in raw_names)))

# examples of before/after
print("\n=== 6 example normalizations (Hospital Name) ===")
shown = 0
for k, r in enumerate(data):
    v = r[hn]
    if NORM(v) != v and shown < 6:
        print(f"  data_row_idx={k}: {v!r}\n      -> {NORM(v)!r}")
        shown += 1

print("\n=== 4 example normalizations (Given Address) ===")
ga = idx["Given Address"]
shown = 0
for k, r in enumerate(data):
    v = r[ga]
    if NORM(v) != v and shown < 4:
        print(f"  data_row_idx={k}: {v!r}\n      -> {NORM(v)!r}")
        shown += 1

# rows where ANY text field needs normalization
any_bad = sum(1 for r in data if any(r[idx[c]].strip() and NORM(r[idx[c]]) != r[idx[c]] for c in TEXT_COLS))
print("\nrows where >=1 text field needs normalization:", any_bad, f"({100*any_bad/len(data):.2f}%)")
