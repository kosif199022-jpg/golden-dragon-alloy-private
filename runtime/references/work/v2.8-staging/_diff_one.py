"""Show where two text files differ (context only, 80 chars around each change)."""
import difflib, sys
from pathlib import Path
a = Path(sys.argv[1]).read_text(encoding="utf-8", errors="ignore")
b = Path(sys.argv[2]).read_text(encoding="utf-8", errors="ignore")
print("len", len(a), len(b))
sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
n = 0
for op, i1, i2, j1, j2 in sm.get_opcodes():
    if op == "equal":
        continue
    n += 1
    if n <= 8:
        print(f"{op} @{i1}: …{a[max(0, i1 - 60):i1]}[{a[i1:i2][:60]}] → [{b[j1:j2][:60]}]…")
print("changes:", n)
