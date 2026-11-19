"""Which graded requests changed between two route_eval2 --dump files: python _cmpdump.py BEFORE AFTER."""
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
a = {r["id"]: r for r in json.load(open(sys.argv[1], encoding="utf-8"))}
b = {r["id"]: r for r in json.load(open(sys.argv[2], encoding="utf-8"))}
ev = os.path.join(here, "mind", "route_eval")
fr = {r["fid"]: r for r in json.load(open(os.path.join(ev, "fresh_cc.json"), encoding="utf-8"))}
lab = {x["fid"]: x for x in json.load(open(os.path.join(ev, "labels_fresh_consensus.json"), encoding="utf-8"))}
n = gain = loss = 0
for i in a:
    if a[i].get("top") != b[i].get("top"):
        n += 1
        q, L = fr.get(i, {}), lab.get(i, {})
        gain += (not a[i]["good"]) and b[i]["good"]
        loss += a[i]["good"] and not b[i]["good"]
        print(f"id {i}: {a[i]['top']} ({'✓' if a[i]['good'] else '✗'}) → {b[i]['top']} ({'✓' if b[i]['good'] else '✗'}) · label {L.get('best')} ok={L.get('ok')}\n"
              f"   prev: {str(q.get('prev', ''))[:80]!r}\n   q:    {str(q.get('q', ''))[:80]!r}")
print(f"changed {n} · gained {gain} · lost {loss}")
