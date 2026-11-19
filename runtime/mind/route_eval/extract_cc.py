"""Owner-typed messages from local Claude Code session logs (~/.claude/projects/*/*.jsonl), with the owner message before each.

    python -I -X utf8 extract_cc.py
Drops tool results, system/command wrappers, pasted long AI replies, duplicates and anything already in the 101 eval requests.
Writes fresh_cc.json: [{"fid", "src", "q", "prev"}].
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path.home() / ".claude" / "projects"
SKIP = re.compile(r"^\s*(<|\[Request interrupted|Caveat:|This session is being continued|Base directory for this skill|# |```)")


def text_of(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
        if any(isinstance(p, dict) and p.get("type") == "tool_result" for p in c):
            return ""
        return "\n".join(parts)
    return ""


def key(s):
    return re.sub(r"\s+", " ", s).strip()[:70]


evalk = {key(r["q"]) for r in json.loads((HERE / "owner_requests.json").read_text(encoding="utf-8"))}
appk = {key(r["q"]) for r in json.loads((HERE / "turns_all.json").read_text(encoding="utf-8"))} if (HERE / "turns_all.json").exists() else set()
rows, seen = [], set()
for f in sorted(ROOT.glob("*/*.jsonl")):
    prev = ""
    try:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        continue
    for ln in lines:
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("type") != "user" or r.get("isMeta") or r.get("isSidechain"):
            continue
        t = text_of(r.get("message") or {}).strip()
        if not t or SKIP.match(t) or "<command-" in t or "<system-reminder>" in t[:200]:
            continue
        if len(t) > 700 or not re.search(r"[؀-ۿ]", t):       # long pastes / pure English test prompts are not routing material
            prev = t[:300]
            continue
        k = key(t)
        if k in seen or k in evalk or k in appk:
            prev = t[:300]
            continue
        seen.add(k)
        rows.append({"src": f.parent.name[-24:] + "/" + f.stem[:8], "q": t[:500], "prev": prev})
        prev = t[:300]
for n, x in enumerate(rows):
    x["fid"] = n
(HERE / "fresh_cc.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
print(f"files={len(list(ROOT.glob('*/*.jsonl')))} fresh_owner_msgs={len(rows)}")
