"""Blind routing evaluation: real owner requests, labels from an independent annotator, the router of a given rd.py.

    python -I -X utf8 route_eval.py RD_SCRIPTS_DIR [--split dev|test|all] [--show-misses N]
Memory is an empty temp home for every run (neutral trust), so versions are compared on the router alone.
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
scripts = Path(sys.argv[1])
split = sys.argv[sys.argv.index("--split") + 1] if "--split" in sys.argv else "all"
show = int(sys.argv[sys.argv.index("--show-misses") + 1]) if "--show-misses" in sys.argv else 0
os.environ["RED_DRAGON_HOME"] = tempfile.mkdtemp(prefix="rd-eval-")
spec = importlib.util.spec_from_file_location("rd_eval_mod", scripts / "rd.py")
rd = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0]]
spec.loader.exec_module(rd)

reqs = {r["id"]: r["q"] for r in json.loads((HERE / "owner_requests.json").read_text(encoding="utf-8"))}
labels = []
for i in range(1, 5):
    labels += json.loads((HERE / f"labels_{i}.json").read_text(encoding="utf-8"))
labels = sorted(labels, key=lambda x: x["id"])
if split == "dev":
    labels = [x for x in labels if x["id"] % 2 == 0]
elif split == "test":
    labels = [x for x in labels if x["id"] % 2 == 1]


def predict(q):
    u = rd.understand(q)
    pb, _ = rd.route(u["text"])
    ranked = [p["id"] for s, p in pb]
    top = ranked[0] if pb and pb[0][0] >= 2 else "none"
    return top, ranked[:3]


n = len(labels)
strict = lenient = hit3 = 0
misses = []
for x in labels:
    top, r3 = predict(reqs[x["id"]])
    ok = {x["best"], *x.get("ok", [])}
    strict += top == x["best"]
    lenient += top in ok
    hit3 += x["best"] in r3 or (x["best"] == "none" and top == "none")
    if top not in ok:
        misses.append((x["id"], x["best"], top, reqs[x["id"]][:90]))
print(f"{rd.VERSION}  split={split}  n={n}  top1 exact {strict / n:.0%}  top1 acceptable {lenient / n:.0%}  in top3 {hit3 / n:.0%}")
for m in misses[:show]:
    print(f"  #{m[0]:>3} want {m[1]:<15} got {m[2]:<15} {m[3]}")
