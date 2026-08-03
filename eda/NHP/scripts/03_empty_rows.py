"""NHP EDA step 3: investigate the 351 apparently-blank rows."""
import csv, io
import pandas as pd

SRC = "/Users/ankitraj2/asar master data/8_JULY_23_SRK_NHP_validated_and_standardized.csv"
text = open(SRC, "rb").read().decode("utf-8-sig")
rows = list(csv.reader(io.StringIO(text, newline="")))
hdr, data = rows[0], rows[1:]

blank_idx = [i for i, r in enumerate(data) if all(v.strip() == "" for v in r)]
print("fully-blank logical data rows:", len(blank_idx))
print("first blank at 0-based data index:", blank_idx[0] if blank_idx else None)
print("last non-blank at:", max(i for i in range(len(data)) if i not in set(blank_idx)))
print("blank indices contiguous?", blank_idx == list(range(blank_idx[0], blank_idx[0] + len(blank_idx))))
print("range:", blank_idx[0], "..", blank_idx[-1])

# what does a blank row look like raw?
print("\nraw repr of blank row 0:", repr(data[blank_idx[0]])[:200])

# any row partially filled?
part = [i for i, r in enumerate(data)
        if any(v.strip() for v in r) and not r[1].strip()]
print("\nrows with SOME content but empty Hospital Name:", len(part), part[:10])

# non-blank count
nonblank = [i for i, r in enumerate(data) if any(v.strip() for v in r)]
print("non-blank logical data rows:", len(nonblank))

# check the tail of the file bytes
raw = open(SRC, "rb").read()
print("\nlast 300 bytes:", raw[-300:])
