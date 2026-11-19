"""Every owner message from the app chat archive, in order, with the message before it.

    python -I -X utf8 extract_turns.py [CHAT_LIBRARY]
Writes turns_all.json (all owner messages with prev) and context.json (prev message for each of the 101 eval ids),
and fresh_candidates.json (owner messages that are NOT in the 101: material for a new blind set).
"""
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("APPDATA", "")) / "BlackDragon" / "chat_library"
USER = "🧑 المستخدم:"
MARK = re.compile(r"^(🧑|⚙|🤖|🐉|🔴|💬|📎|✅|❌|#|\(المحادثة)")


def turns(path):
    out, cur = [], None
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.startswith(USER):
            if cur is not None:
                out.append(cur.strip())
            cur = ln[len(USER):].strip()
        elif cur is not None:
            if MARK.match(ln) or ln.startswith("   ↳") or ln.startswith(" |"):
                out.append(cur.strip())
                cur = None
            else:
                cur += "\n" + ln
    if cur is not None:
        out.append(cur.strip())
    return [t for t in out if t]


def key(s):
    return re.sub(r"\s+", " ", s).strip()[:120]


rows = []
for f in sorted(LIB.glob("c*.md")):
    ts = turns(f)
    for i, t in enumerate(ts):
        rows.append({"src": f.name, "i": i, "q": t, "prev": ts[i - 1] if i else ""})

reqs = json.loads((HERE / "owner_requests.json").read_text(encoding="utf-8"))
ctx, used = {}, set()
for r in reqs:
    k = key(r["q"])
    cands = [x for x in rows if x["src"] == r["src"] and (key(x["q"]).startswith(k[:60]) or k.startswith(key(x["q"])[:60]))]
    if not cands:
        cands = [x for x in rows if key(x["q"])[:60] == k[:60]]
    if cands:
        ctx[r["id"]] = cands[0]["prev"][:400]
        used.add((cands[0]["src"], cands[0]["i"]))
evalkeys = {key(r["q"])[:60] for r in reqs}
fresh = [x for x in rows if (x["src"], x["i"]) not in used and key(x["q"])[:60] not in evalkeys and len(x["q"]) >= 6]
seen, uniq = set(), []
for x in fresh:
    k = key(x["q"])[:80]
    if k in seen:
        continue
    seen.add(k)
    uniq.append(x)
(HERE / "turns_all.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
(HERE / "context.json").write_text(json.dumps(ctx, ensure_ascii=False, indent=0), encoding="utf-8")
(HERE / "fresh_candidates.json").write_text(json.dumps([{"fid": n, "src": x["src"], "q": x["q"][:500], "prev": x["prev"][:300]} for n, x in enumerate(uniq)], ensure_ascii=False, indent=0), encoding="utf-8")
print(f"chats={len(list(LIB.glob('c*.md')))} owner_msgs={len(rows)} eval_with_context={len(ctx)}/{len(reqs)} with_nonempty_prev={sum(1 for v in ctx.values() if v)} fresh_unique={len(uniq)}")
