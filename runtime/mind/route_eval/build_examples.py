"""Build the router's data files from the blind-labelled sets (run from anywhere; writes into ../ = mind/).

  mind/route_examples.jsonl   one row per labelled owner request: {"q", "pb", "src", "key"}
      kept: requests that stand on their own (>= 4 content words, or the label is none/status, or there was no previous message);
      dropped: short follow-ups whose label came from the previous message («حل المشكلة» → whatever was open), and anything that looks like a secret.
  mind/translit.json          Arabic spellings of English tool words (agent 1, reviewed)
  mind/dictation.json         + the voice-typing slips agent 1 found in the archives (two rejected: اللسة, في كروب)
"""
import importlib.util, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIND = HERE.parent
spec = importlib.util.spec_from_file_location("rdb", MIND.parent / "scripts" / "rd.py")
rd = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0]]
spec.loader.exec_module(rd)
SECRET = re.compile(r"(sk-ant-|sk-[A-Za-z0-9]{24,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|password\s*[:=]|باسورد\s*[:=])", re.I)

# ---------------------------------------------------------------- dictation + translit first (understand() uses dictation)
prop = json.loads((HERE / "proposals_dictation.json").read_text(encoding="utf-8"))
dic_f = MIND / "dictation.json"
dic = json.loads(dic_f.read_text(encoding="utf-8"))
added = 0
for bad, good in prop["fix"].items():
    if bad in ("اللسة", "في كروب") or bad in dic:
        continue
    dic[bad] = good
    added += 1
dic_f.write_text(json.dumps(dic, ensure_ascii=False, indent=1), encoding="utf-8")
tr = {"_doc": "Arabic spelling of an English tool word -> the English word(s). rd.py translit(): a request word may meet a trigger in either spelling (max, never double)."}
for k, v in prop["translit"].items():
    tr[k] = "claude cloud" if "كلاود" in k else v
tr.update({"ديزني": "disney", "لديزني": "disney", "جيتهاب": "github", "جيت هاب": "github", "بايثون": "python", "فوتوشوب": "photoshop", "يوتيوب": "youtube", "تيك توك": "tiktok"})
(MIND / "translit.json").write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")
rd.DICTATION.clear()
rd.DICTATION.update(dic)
print(f"dictation: +{added} → {len(dic)}   translit: {len(tr) - 1}")

# ---------------------------------------------------------------- examples
reqs = {r["id"]: r["q"] for r in json.loads((HERE / "owner_requests.json").read_text(encoding="utf-8"))}
ctx = json.loads((HERE / "context.json").read_text(encoding="utf-8"))
rows = []
for i in range(1, 5):
    for x in json.loads((HERE / f"labels_{i}.json").read_text(encoding="utf-8")):
        rows.append((f"old:{x['id']}", reqs[x["id"]], ctx.get(str(x["id"]), ""), x["best"]))
fr = {r["fid"]: r for r in json.loads((HERE / "fresh_cc.json").read_text(encoding="utf-8"))}
for x in json.loads((HERE / "labels_fresh_consensus.json").read_text(encoding="utf-8")):
    if x["best"] != "skip":
        r = fr[x["fid"]]
        rows.append((f"cc:{x['fid']}", r["q"], r.get("prev", ""), x["best"]))
out, drop = [], {"secret": 0, "empty": 0, "follow-up": 0}
for src, q, prev, best in rows:
    if SECRET.search(q):
        drop["secret"] += 1
        continue
    u = rd.understand(q)["text"]
    qp = [w for w in rd.tokens(u) if w not in rd.QSTOP]
    if not qp:
        drop["empty"] += 1
        continue
    if len(qp) < 4 and best not in ("none", "status") and prev.strip():
        drop["follow-up"] += 1
        continue
    out.append({"q": " ".join(u.split())[:500], "pb": best, "src": src, "key": rd.ex_key(q)})
(MIND / "route_examples.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
print(f"examples: {len(out)} kept of {len(rows)}  dropped {drop}")
