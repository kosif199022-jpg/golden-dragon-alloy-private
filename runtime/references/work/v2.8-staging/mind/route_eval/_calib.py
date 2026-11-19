"""Pick confidence thresholds on the dev dump: high must be >= 90% right, low should be clearly worse than mid."""
import itertools, json, sys
rows = []
for f in sys.argv[1:]:
    rows += [r for r in json.load(open(f, encoding="utf-8")) if r["s1"] >= 2]
print("routed rows:", len(rows), "right:", sum(r["good"] for r in rows))


def lab(r, hi, mid):
    gap = (r["s1"] - r["s2"]) / r["s1"]
    if r["s1"] >= hi[0] and gap >= hi[1]:
        return "high"
    if r["s1"] >= mid[0] and gap >= mid[1]:
        return "mid"
    return "low"


best = []
for h1, h2, m1, m2 in itertools.product([6, 8, 9, 10, 12, 15], [0.2, 0.3, 0.35, 0.45, 0.55], [3, 4, 5, 6], [0.05, 0.1, 0.15, 0.2, 0.3]):
    if m1 > h1 or m2 > h2:
        continue
    b = {"high": [0, 0], "mid": [0, 0], "low": [0, 0]}
    for r in rows:
        k = lab(r, (h1, h2), (m1, m2))
        b[k][0] += 1
        b[k][1] += r["good"]
    if min(v[0] for v in b.values()) < 12:
        continue
    acc = {k: v[1] / v[0] for k, v in b.items()}
    if acc["high"] < 0.9 or not (acc["high"] > acc["mid"] > acc["low"]):
        continue
    sep = (acc["mid"] - acc["low"]) + (acc["high"] - acc["mid"])
    best.append((sep + 0.3 * b["high"][0] / len(rows), (h1, h2), (m1, m2), {k: f"{v[1]}/{v[0]}={v[1] / v[0]:.0%}" for k, v in b.items()}))
best.sort(key=lambda x: -x[0])
for x in best[:8]:
    print(f"{x[0]:.3f} hi={x[1]} mid={x[2]} {x[3]}")
