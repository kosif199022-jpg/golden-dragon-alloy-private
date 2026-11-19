"""Routing evaluation v2: two independent blind sets, optional conversation context, honest example memory.

    python -I -X utf8 route_eval2.py RD_SCRIPTS_DIR [--set old|fresh|both] [--split dev|test|all] [--ctx] [--show-misses N] [--calib] [--novel] [--json]

Sets
  old    the 101 requests from the app archive (labels_1..4, annotated blind for v2.6, WITHOUT the previous message:
         a bare «كمل» / «جرب» is labelled none there, so judge this set with --ctx off)
  fresh  221 owner messages from local Claude Code sessions (labels_fresh_consensus.json: two blind annotators who saw the
         previous message; 'skip' rows dropped). Judge this set with --ctx on.
Splits: dev = even id, test = odd id, all = both. Tune on dev, report test.
Example memory (mind/route_examples.jsonl), so a version is never graded on requests it has memorised:
  test  every test request of BOTH sets is hidden from the memory
  dev   every test request is hidden too, and each dev request is also hidden while it is graded (leave-one-out)
  all   leave-one-out only
--novel  also report the graded requests that have no near-duplicate (cosine >= 0.8) left in the memory
--json   one JSON line per set (used by rd.py selftest as the anti-regression gate)
--topic  fresh set: the router gets the decayed topic of every earlier message of the same session (what brief() keeps
         in MEM/last_turn.json), each history message scored with itself hidden from the memory; old set: same as --ctx
"""
import importlib.util
import inspect
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
args = sys.argv[1:]
scripts = Path(args[0])
opt = lambda k, d: args[args.index(k) + 1] if k in args else d
which, split, show = opt("--set", "both"), opt("--split", "all"), int(opt("--show-misses", "0"))
use_ctx, calib, novel, as_json, use_topic = "--ctx" in args or "--topic" in args, "--calib" in args, "--novel" in args, "--json" in args, "--topic" in args
os.environ["RED_DRAGON_HOME"] = tempfile.mkdtemp(prefix="rd-eval-")
spec = importlib.util.spec_from_file_location("rd_eval_mod", scripts / "rd.py")
rd = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0]]
spec.loader.exec_module(rd)
takes_prev = "prev" in inspect.signature(rd.route).parameters
has_mem = hasattr(rd, "EX_EXCLUDE") and hasattr(rd, "ex_key")


def load(name, part):
    rows = []
    if name == "old":
        reqs = {r["id"]: r["q"] for r in json.loads((HERE / "owner_requests.json").read_text(encoding="utf-8"))}
        ctx = json.loads((HERE / "context.json").read_text(encoding="utf-8")) if (HERE / "context.json").exists() else {}
        for i in range(1, 5):
            for x in json.loads((HERE / f"labels_{i}.json").read_text(encoding="utf-8")):
                rows.append({"id": x["id"], "q": reqs[x["id"]], "prev": ctx.get(str(x["id"]), ""), "best": x["best"], "ok": x.get("ok", [])})
    else:
        fr = {r["fid"]: r for r in json.loads((HERE / "fresh_cc.json").read_text(encoding="utf-8"))}
        lab = HERE / "labels_fresh_consensus.json"          # two blind annotators (86% agree on top-1); best = annotator A, ok = A.ok + B.best + B.ok
        if not lab.exists():
            lab = HERE / "labels_fresh.json"
        for x in json.loads(lab.read_text(encoding="utf-8")):
            if x["best"] == "skip":
                continue
            r = fr[x["fid"]]
            rows.append({"id": x["fid"], "q": r["q"], "prev": r.get("prev", ""), "best": x["best"], "ok": [o for o in x.get("ok", []) if o != "skip"]})
    rows.sort(key=lambda r: r["id"])
    if part == "dev":
        rows = [r for r in rows if r["id"] % 2 == 0]
    elif part == "test":
        rows = [r for r in rows if r["id"] % 2 == 1]
    return rows


TEST_KEYS = set()
LASTS = [0.0, 0.0]
dump = [] if "--dump" in args else None
if has_mem and split in ("dev", "test"):
    TEST_KEYS = {rd.ex_key(r["q"]) for s in ("old", "fresh") for r in load(s, "test")}


TOPIC = {}
if use_topic and hasattr(rd, "topic_update"):
    _pbs, _sess, _t = rd.playbooks(), None, {}
    for _r in json.loads((HERE / "fresh_cc.json").read_text(encoding="utf-8")):
        if _r["src"] != _sess:
            _sess, _t = _r["src"], {}
        TOPIC[_r["fid"]] = dict(_t)
        if has_mem:
            rd.EX_EXCLUDE.clear()
            rd.EX_EXCLUDE.update(TEST_KEYS)
            rd.EX_EXCLUDE.add(rd.ex_key(_r["q"]))
        _t = rd.topic_update(_t, rd._pb_scores(rd.understand(_r["q"])["text"], _pbs)[0])


def predict(q, prev, topic=None):
    u = rd.understand(q)
    if topic:
        pb, _ = rd.route(u["text"], prev=topic)
    elif use_ctx and takes_prev and prev:
        pb, _ = rd.route(u["text"], prev=rd.understand(prev)["text"])
    else:
        pb, _ = rd.route(u["text"])
    ranked = [p["id"] for s, p in pb]
    top = ranked[0] if pb and pb[0][0] >= 2 else "none"
    conf = (rd.confidence(pb, rd._pb_scores(u["text"], rd.playbooks())[1]) if "kind" in inspect.signature(rd.confidence).parameters else rd.confidence(pb)) if hasattr(rd, "confidence") else None
    LASTS[:] = [pb[0][0] if pb else 0.0, pb[1][0] if len(pb) > 1 else 0.0]
    return top, ranked[:3], conf


def run(name):
    rows = load(name, split)
    n = len(rows)
    strict = lenient = hit3 = 0
    nov = [0, 0]
    misses, buckets = [], {}
    for r in rows:
        if has_mem:
            rd.EX_EXCLUDE.clear()
            rd.EX_EXCLUDE.update(TEST_KEYS)
            rd.EX_EXCLUDE.add(rd.ex_key(r["q"]))
        top, r3, conf = predict(r["q"], r["prev"], TOPIC.get(r["id"]) if name == "fresh" else None)
        ok = {r["best"], *r["ok"]}
        good = top in ok
        strict += top == r["best"]
        lenient += good
        hit3 += r["best"] in r3 or (r["best"] == "none" and top == "none")
        if novel and has_mem:
            near = rd.ex_near(rd.understand(r["q"])["text"], k=1, floor=0.0)
            if not near or near[0][0] < 0.8:
                nov[0] += 1
                nov[1] += good
        if dump is not None:
            dump.append({"set": name, "id": r["id"], "s1": LASTS[0], "s2": LASTS[1], "good": bool(good), "top": top})
        if conf:
            b = buckets.setdefault(conf, [0, 0])
            b[0] += 1
            b[1] += good
        if not good:
            misses.append((r["id"], r["best"], top, " ".join(rd.understand(r["q"])["text"].split())[:95]))
    res = {"version": rd.VERSION, "set": name, "split": split, "ctx": ("topic" if use_topic and name == "fresh" and TOPIC else bool(use_ctx and takes_prev)), "n": n,
           "top1": round(strict / n, 4), "ok": round(lenient / n, 4), "top3": round(hit3 / n, 4)}
    if nov[0]:
        res.update(novel_n=nov[0], novel_ok=round(nov[1] / nov[0], 4))
    if buckets:
        res["calib"] = {k: v for k, v in sorted(buckets.items())}
    if as_json:
        print(json.dumps(res, ensure_ascii=False))
        return res
    print(f"{rd.VERSION}  set={name:<5} split={split:<4} ctx={res['ctx'] if res['ctx'] == 'topic' else ('on' if res['ctx'] else 'off'):<5} n={n:<3}  top1 exact {strict / n:.0%}  acceptable {lenient / n:.0%}  in top3 {hit3 / n:.0%}"
          + (f"   novel(no near-dup) {nov[1]}/{nov[0]} = {nov[1] / nov[0]:.0%}" if nov[0] else ""))
    if calib and buckets:
        print("   confidence: " + "  ".join(f"{k}: {v[1]}/{v[0]} ({v[1] / v[0]:.0%})" for k, v in sorted(buckets.items())))
    for m in misses[:show]:
        print(f"   #{m[0]:>3} want {m[1]:<15} got {m[2]:<15} {m[3]}")
    return res


for s in (["old", "fresh"] if which == "both" else [which]):
    run(s)
if dump is not None:
    Path(opt("--dump", "dump.json")).write_text(json.dumps(dump), encoding="utf-8")
