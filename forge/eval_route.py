"""Measure the blended router on the owner's real requests (mind/route_eval fresh set, two blind annotators).

    python -I -X utf8 forge/eval_route.py --split dev            # tune here only
    python -I -X utf8 forge/eval_route.py --split test --once     # report once, no tuning after

Same rows, labels, topic and example-memory hiding as runtime/mind/route_eval/route_eval2.py (--set fresh --topic):
  rd     the measured router alone (runtime/scripts/rd.py)
  kb     the unified knowledge alone, raw request text (what a cloud session without runtime/ gets)
  kb+u   the unified knowledge on rd.understand() text (keyboard/dictation decoded)
  blend  reciprocal-rank fusion of rd and kb+u; rd's «none» (chat) decision is kept
Metrics as in route_eval2: top1 exact / acceptable (best or ok) / best in top 3.
"""
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import alloy  # noqa: E402

os.environ["RED_DRAGON_HOME"] = tempfile.mkdtemp(prefix="alloy-eval-")   # never touch the real memory
HERE = ROOT / "runtime" / "mind" / "route_eval"
RD = ROOT / "runtime" / "scripts" / "rd.py"
args = sys.argv[1:]
split = args[args.index("--split") + 1] if "--split" in args else "dev"
K = float(args[args.index("--k") + 1]) if "--k" in args else 2.0
W = float(args[args.index("--w") + 1]) if "--w" in args else 0.5

sys.path.insert(0, str(RD.parent))
spec = importlib.util.spec_from_file_location("rd", RD)
rd = importlib.util.module_from_spec(spec)
_argv, sys.argv = sys.argv, [sys.argv[0]]
spec.loader.exec_module(rd)
sys.argv = _argv
has_mem = hasattr(rd, "EX_EXCLUDE") and hasattr(rd, "ex_key")


def load(part):
    fr = {r["fid"]: r for r in json.loads((HERE / "fresh_cc.json").read_text(encoding="utf-8"))}
    rows = []
    for x in json.loads((HERE / "labels_fresh_consensus.json").read_text(encoding="utf-8")):
        if x["best"] == "skip":
            continue
        r = fr[x["fid"]]
        rows.append({"id": x["fid"], "q": r["q"], "best": x["best"], "ok": [o for o in x.get("ok", []) if o != "skip"]})
    rows.sort(key=lambda r: r["id"])
    return [r for r in rows if r["id"] % 2 == (0 if part == "dev" else 1)]


def load_old_test():
    reqs = {r["id"]: r["q"] for r in json.loads((HERE / "owner_requests.json").read_text(encoding="utf-8"))}
    out = []
    for i in range(1, 5):
        for x in json.loads((HERE / f"labels_{i}.json").read_text(encoding="utf-8")):
            if x["id"] % 2 == 1:
                out.append(reqs[x["id"]])
    return out


TEST_KEYS = {rd.ex_key(q) for q in [r["q"] for r in load("test")] + load_old_test()} if has_mem else set()
TOPIC = {}
_pbs, _sess, _t = rd.playbooks(), None, {}
for _r in json.loads((HERE / "fresh_cc.json").read_text(encoding="utf-8")):
    if _r["src"] != _sess:
        _sess, _t = _r["src"], {}
    TOPIC[_r["fid"]] = dict(_t)
    if has_mem:
        rd.EX_EXCLUDE.clear(); rd.EX_EXCLUDE.update(TEST_KEYS); rd.EX_EXCLUDE.add(rd.ex_key(_r["q"]))
    _t = rd.topic_update(_t, rd._pb_scores(rd.understand(_r["q"])["text"], _pbs)[0])

BRACKET = re.compile(r"^\[[^\]]{0,6000}\]\s*$", re.M | re.S)
PB_IDS = {p["id"] for p in _pbs}


def kb_rank(text):
    clean = BRACKET.sub(" ", text)
    ids = [r["id"].split(":", 1)[1] for r in alloy.search(clean[:1500], ["road"], 8)]
    return [i for i in ids if i in PB_IDS][:5]


def score(rows, preds):
    n = len(rows)
    s = l = h = 0
    for r, (top, r3) in zip(rows, preds):
        ok = {r["best"], *r["ok"]}
        s += top == r["best"]
        l += top in ok
        h += r["best"] in r3 or (r["best"] == "none" and top == "none")
    return f"{s / n:.0%} / {l / n:.0%} / {h / n:.0%}", (s, l, h, n)


rows = load(split)
P = {"rd": [], "kb": [], "kb+u": [], "blend": []}
for r in rows:
    if has_mem:
        rd.EX_EXCLUDE.clear(); rd.EX_EXCLUDE.update(TEST_KEYS); rd.EX_EXCLUDE.add(rd.ex_key(r["q"]))
    u = rd.understand(r["q"])
    topic = TOPIC.get(r["id"])
    pb, _ = rd.route(u["text"], prev=topic) if topic else rd.route(u["text"])
    ranked = [p["id"] for s, p in pb]
    none = not (pb and pb[0][0] >= 2)
    top = "none" if none else ranked[0]
    P["rd"].append((top, ranked[:3]))
    k1 = kb_rank(r["q"])
    P["kb"].append((k1[0] if k1 else "none", k1[:3]))
    k2 = kb_rank(u["text"])
    P["kb+u"].append((k2[0] if k2 else "none", k2[:3]))
    fused = {}
    for i, x in enumerate(ranked[:5]):
        fused[x] = fused.get(x, 0) + 1 / (K + i + 1)
    for i, x in enumerate(k2[:5]):
        fused[x] = fused.get(x, 0) + W / (K + i + 1)
    order = sorted(fused, key=lambda x: -fused[x])
    P["blend"].append(("none" if none else order[0], order[:3]))

print(f"fresh set · split={split} · n={len(rows)} · rd v{rd.VERSION} · k={K} w={W}   (top1 exact / acceptable / in top 3)")
out = {}
for name, preds in P.items():
    txt, raw = score(rows, preds)
    out[name] = raw
    print(f"  {name:<6} {txt}")
road_rows = [i for i, r in enumerate(rows) if r["best"] != "none"]
print(f"  — only requests that have a road (n={len(road_rows)}):")
for name in ("rd", "kb", "kb+u", "blend"):
    txt, raw = score([rows[i] for i in road_rows], [P[name][i] for i in road_rows])
    print(f"    {name:<6} {txt}")
if "--json" in args:
    print(json.dumps(out))
