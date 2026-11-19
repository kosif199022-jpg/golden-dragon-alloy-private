"""Does a decayed topic of the whole conversation beat the single previous message? fresh set, DEV half only."""
import importlib.util, json, os, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
os.environ["RED_DRAGON_HOME"] = tempfile.mkdtemp(prefix="rd-topic-")
spec = importlib.util.spec_from_file_location("rdp", HERE.parent.parent / "scripts" / "rd.py")
rd = importlib.util.module_from_spec(spec); sys.argv = [sys.argv[0]]; spec.loader.exec_module(rd)
fr = json.loads((HERE / "fresh_cc.json").read_text(encoding="utf-8"))
lab = {x["fid"]: x for x in json.loads((HERE / "labels_fresh_consensus.json").read_text(encoding="utf-8"))}
reqs = {r["id"]: r["q"] for r in json.loads((HERE / "owner_requests.json").read_text(encoding="utf-8"))}
test_keys = {rd.ex_key(r["q"]) for r in fr if r["fid"] % 2 == 1}
for i in range(1, 5):
    for x in json.loads((HERE / f"labels_{i}.json").read_text(encoding="utf-8")):
        if x["id"] % 2 == 1:
            test_keys.add(rd.ex_key(reqs[x["id"]]))
pbs = rd.playbooks()
for r in fr:
    r["u"] = rd.understand(r["q"])["text"]
    r["k"] = rd.ex_key(r["q"])
    rd.EX_EXCLUDE.clear(); rd.EX_EXCLUDE.update(test_keys); rd.EX_EXCLUDE.add(r["k"])
    r["s"], r["kind"] = rd._pb_scores(r["u"], pbs)


def run(decay, cap):
    ok = t1 = n = 0
    topic, sess = {}, None
    for r in fr:
        if r["src"] != sess:
            topic, sess = {}, r["src"]
        x = lab.get(r["fid"])
        if x and x["best"] != "skip" and r["fid"] % 2 == 0:
            rd.EX_EXCLUDE.clear(); rd.EX_EXCLUDE.update(test_keys); rd.EX_EXCLUDE.add(r["k"])
            pb, _ = rd.route(r["u"], prev=dict(topic) if topic else None)
            top = pb[0][1]["id"] if pb and pb[0][0] >= 2 else "none"
            n += 1; ok += top in {x["best"], *x.get("ok", [])}; t1 += top == x["best"]
        s = {k: v for k, v in r["s"].items() if k != "none"}
        m = max(s.values(), default=0.0)
        if m > cap:
            s = {k: v * cap / m for k, v in s.items()}
        topic = {k: decay * topic.get(k, 0.0) + s.get(k, 0.0) for k in set(topic) | set(s)} if decay > 0 else s
        topic = {k: v for k, v in topic.items() if v > 0.05}
    return t1 / n, ok / n, n


for decay in (0.0, 0.3, 0.5, 0.7):
    for cap in (10.0, 20.0, 1e9):
        a, b, n = run(decay, cap)
        print(f"decay={decay} cap={cap:g}  n={n} top1 {a:.0%} ok {b:.0%}")
