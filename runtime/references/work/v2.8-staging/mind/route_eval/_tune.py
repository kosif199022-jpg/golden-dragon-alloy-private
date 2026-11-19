"""Grid-search the example-memory knobs on the DEV half only (old: ctx off, fresh: chat topic). Test rows stay hidden from memory.
python -I -X utf8 _tune.py"""
import importlib.util, itertools, json, os, sys, tempfile, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
os.environ["RED_DRAGON_HOME"] = tempfile.mkdtemp(prefix="rd-tune-")
spec = importlib.util.spec_from_file_location("rdt", HERE.parent.parent / "scripts" / "rd.py")
rd = importlib.util.module_from_spec(spec); sys.argv = [sys.argv[0]]; spec.loader.exec_module(rd)
reqs = {r["id"]: r["q"] for r in json.loads((HERE / "owner_requests.json").read_text(encoding="utf-8"))}
old = []
for i in range(1, 5):
    for x in json.loads((HERE / f"labels_{i}.json").read_text(encoding="utf-8")):
        old.append({"id": x["id"], "q": reqs[x["id"]], "best": x["best"], "ok": x.get("ok", [])})
fr = json.loads((HERE / "fresh_cc.json").read_text(encoding="utf-8"))
lab = {x["fid"]: x for x in json.loads((HERE / "labels_fresh_consensus.json").read_text(encoding="utf-8"))}
test_keys = {rd.ex_key(r["q"]) for r in old if r["id"] % 2} | {rd.ex_key(r["q"]) for r in fr if r["fid"] % 2}
for r in old + fr:
    r["u"] = rd.understand(r["q"])["text"]
    r["k"] = rd.ex_key(r["q"])
pbs = rd.playbooks()


def hide(k):
    rd.EX_EXCLUDE.clear(); rd.EX_EXCLUDE.update(test_keys); rd.EX_EXCLUDE.add(k)


def evaluate():
    res = {}
    n = ok = t1 = 0
    for r in old:
        if r["id"] % 2:
            continue
        hide(r["k"])
        pb, _ = rd.route(r["u"])
        top = pb[0][1]["id"] if pb and pb[0][0] >= 2 else "none"
        n += 1; ok += top in {r["best"], *r["ok"]}; t1 += top == r["best"]
    res["old"] = (t1 / n, ok / n)
    n = ok = t1 = 0
    topic, sess = {}, None
    for r in fr:
        if r["src"] != sess:
            topic, sess = {}, r["src"]
        hide(r["k"])
        x = lab.get(r["fid"])
        if x and x["best"] != "skip" and r["fid"] % 2 == 0:
            pb, _ = rd.route(r["u"], prev=dict(topic) if topic else None)
            top = pb[0][1]["id"] if pb and pb[0][0] >= 2 else "none"
            n += 1; ok += top in {x["best"], *x.get("ok", [])}; t1 += top == x["best"]
        topic = rd.topic_update(topic, rd._pb_scores(r["u"], pbs)[0])
    res["fresh"] = (t1 / n, ok / n)
    return res


grid = dict(EX_W=[6.0, 9.0, 12.0], EX_FLOOR=[0.3, 0.4], EX_P=[1.0, 2.0])
out, t0, keys = [], time.time(), list(grid)
for combo in itertools.product(*grid.values()):
    for k, v in zip(keys, combo):
        setattr(rd, k, v)
    e = evaluate()
    obj = (e["old"][1] * 51 + e["fresh"][1] * 109) / 160 + 0.5 * (e["old"][0] * 51 + e["fresh"][0] * 109) / 160
    out.append((obj, dict(zip(keys, combo)), e))
    print(f"{obj:.3f}  old t1/ok {e['old'][0]:.0%}/{e['old'][1]:.0%}  fresh(topic) {e['fresh'][0]:.0%}/{e['fresh'][1]:.0%}  {dict(zip(keys, combo))}", flush=True)
print(f"{len(out)} combos in {time.time() - t0:.0f}s; best: {max(out, key=lambda x: x[0])[1]}")
