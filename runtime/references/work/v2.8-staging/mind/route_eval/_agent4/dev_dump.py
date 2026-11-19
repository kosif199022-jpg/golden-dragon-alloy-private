# -*- coding: utf-8 -*-
"""Agent4: dump DEV (even-id) examples only, grouped by best playbook. Odd ids are dropped at load."""
import json, os, sys, io
B = r"C:\Users\cinde\rd-staging\v2.8\mind\route_eval"
PB = r"C:\Users\cinde\rd-staging\v2.8\mind\playbooks.json"
OUT = os.path.join(B, "_agent4")

def load(p):
    with io.open(p, encoding="utf-8-sig") as f:
        return json.load(f)

def rows(x):
    if isinstance(x, dict):
        for k in ("items", "labels", "requests", "data", "rows"):
            if k in x and isinstance(x[k], list):
                return x[k]
        # dict keyed by id
        out = []
        for k, v in x.items():
            if isinstance(v, dict):
                d = dict(v); d.setdefault("_key", k); out.append(d)
            else:
                out.append({"_key": k, "_val": v})
        return out
    return x

def even(v):
    try:
        return int(v) % 2 == 0
    except Exception:
        return False

def getid(r, key):
    return r.get(key, r.get("_key"))

# ---- labels (filter odd FIRST) ----
old_lab = {}
for i in (1, 2, 3, 4):
    for r in rows(load(os.path.join(B, "labels_%d.json" % i))):
        rid = getid(r, "id")
        if not even(rid):
            continue
        old_lab[int(rid)] = r
fresh_lab = {}
for r in rows(load(os.path.join(B, "labels_fresh.json"))):
    rid = getid(r, "fid")
    if not even(rid):
        continue
    fresh_lab[int(rid)] = r

old_q = {}
for r in rows(load(os.path.join(B, "owner_requests.json"))):
    rid = getid(r, "id")
    if not even(rid):
        continue
    old_q[int(rid)] = r.get("q", r.get("_val"))
fresh_q = {}
for r in rows(load(os.path.join(B, "fresh_cc.json"))):
    rid = getid(r, "fid")
    if not even(rid):
        continue
    fresh_q[int(rid)] = r.get("q", r.get("_val"))

dev = {}
def add(src, rid, lab, q):
    best = lab.get("best", lab.get("_val"))
    if not best or best == "skip" or q is None:
        return
    dev.setdefault(best, []).append({"ref": "%s:%d" % (src, rid), "q": q, "ok": lab.get("ok")})
for rid, lab in sorted(old_lab.items()):
    add("old", rid, lab, old_q.get(rid))
for rid, lab in sorted(fresh_lab.items()):
    add("fresh", rid, lab, fresh_q.get(rid))

with io.open(os.path.join(OUT, "dev_by_playbook.json"), "w", encoding="utf-8") as f:
    json.dump(dev, f, ensure_ascii=False, indent=1)

pb = load(PB)
print("playbooks type:", type(pb).__name__, (list(pb.keys())[:8] if isinstance(pb, dict) else len(pb)))
print("old even labels:", len(old_lab), "fresh even labels:", len(fresh_lab))
print("old even q:", len(old_q), "fresh even q:", len(fresh_q))
for k, v in sorted(dev.items(), key=lambda kv: -len(kv[1])):
    print("%-22s %d" % (k, len(v)))

# readable text dump, trimmed
with io.open(os.path.join(OUT, "dev_dump.txt"), "w", encoding="utf-8") as f:
    for k, v in sorted(dev.items(), key=lambda kv: -len(kv[1])):
        f.write("\n===== %s (%d)\n" % (k, len(v)))
        for e in v:
            q = " ".join(str(e["q"]).split())
            f.write("[%s] %s\n" % (e["ref"], q[:230]))
