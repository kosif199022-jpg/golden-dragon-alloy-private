import json, os, re, sys
from collections import Counter, defaultdict
from common import *
freq = Counter(); ex = defaultdict(list); nchar = 0; stats = Counter()
for f, fld, c in sentences():
    stats[(f, fld)] += 1; nchar += len(c)
    for ln in lines(c):
        for w in WORD.findall(ln):
            freq[w] += 1
            if len(ex[w]) < 2 and ln[:80] not in ex[w]:
                ex[w].append(ln[:80])
print(dict(stats), "chars", nchar, "types", len(freq), "tokens", sum(freq.values()))
def strip(w):
    for p in ("وال", "بال", "فال", "لل", "ال", "و", "ب", "ل", "ف"):
        if w.startswith(p) and len(w) - len(p) >= 3:
            return w[len(p):]
    return w
def dl(a, b):
    if abs(len(a) - len(b)) > 1: return 9
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1): d[i][0] = i
    for j in range(lb + 1): d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            c = a[i - 1] != b[j - 1]
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]
NORM = str.maketrans("أإآىة", "اااية")
common = [w for w, n in freq.items() if n >= 3 and len(w) >= 4]
out = []
for w, n in freq.items():
    if n > 2 or len(w) < 4: continue
    best = None
    for c in common:
        if c == w or c.translate(NORM) == w.translate(NORM): continue
        if dl(w, c) == 1 and freq[c] >= 3 * n:
            if best is None or freq[c] > freq[best]: best = c
    dbl = re.search(r"(.)\1", w) is not None
    if best or dbl:
        out.append((w, n, best, freq.get(best, 0), ex[w][0]))
out.sort(key=lambda x: -x[3])
json.dump({"freq": freq, "ex": ex}, open(os.path.join(R, "_agent2", "freq.json"), "w", encoding="utf-8"), ensure_ascii=False)
with open(os.path.join(R, "_agent2", "candidates.tsv"), "w", encoding="utf-8") as fo:
    for r in out:
        fo.write("\t".join(map(str, r)) + "\n")
print("candidates", len(out))
for r in out[:int(sys.argv[1]) if len(sys.argv) > 1 else 0]:
    print(f"{r[0]} <- {r[2]}({r[3]}) | {r[4][:55]}")
