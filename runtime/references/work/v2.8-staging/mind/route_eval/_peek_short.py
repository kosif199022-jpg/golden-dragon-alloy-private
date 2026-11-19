import importlib.util, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from wrappers_proposal import strip_wrappers
spec = importlib.util.spec_from_file_location("rdm", HERE.parent.parent / "scripts" / "rd.py")
rd = importlib.util.module_from_spec(spec); sys.argv = [sys.argv[0]]; spec.loader.exec_module(rd)
reqs = {r["id"]: r["q"] for r in json.loads((HERE / "owner_requests.json").read_text(encoding="utf-8"))}
ctx = json.loads((HERE / "context.json").read_text(encoding="utf-8"))
rows = []
for i in range(1, 5):
    for x in json.loads((HERE / f"labels_{i}.json").read_text(encoding="utf-8")):
        rows.append(("old", x["id"], reqs[x["id"]], ctx.get(str(x["id"]), ""), x["best"]))
fr = {r["fid"]: r for r in json.loads((HERE / "fresh_cc.json").read_text(encoding="utf-8"))}
for x in json.loads((HERE / "labels_fresh_consensus.json").read_text(encoding="utf-8")):
    if x["best"] != "skip":
        r = fr[x["fid"]]; rows.append(("cc", x["fid"], r["q"], r.get("prev", ""), x["best"]))
n = 0
for s, i, q, prev, best in rows:
    c, names = strip_wrappers(q)
    qp = [w for w in rd.tokens(c) if w not in rd.QSTOP]
    if len(qp) <= 3:
        n += 1
        print(f"{s}:{i:<3} {best:<14} q=«{' '.join(c.split())[:60]}» prev=«{' '.join(prev.split())[:45]}»")
print("short:", n, "of", len(rows))
