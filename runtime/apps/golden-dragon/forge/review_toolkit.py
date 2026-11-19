"""Read-only review of analysis/thinking_toolkit.json (schema, cited sources exist, protocol ids resolve)."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / "analysis" / "thinking_toolkit.json").read_text(encoding="utf-8"))
tools = d["tools"]
ids = {t["id"] for t in tools}
allowed = {"understand", "plan", "decide", "analyze", "debug", "estimate", "create", "review", "communicate", "learn"}
print("keys:", sorted(d))
print("tools:", len(tools), "| protocol steps:", len(d.get("protocol_ar", [])),
      "| dropped:", len(d.get("dropped", [])), "| sources:", len(d.get("sources_read", [])))

problems = []
for t in tools:
    if not t.get("steps_ar") or not t.get("use_when") or not set(t["use_when"]) <= allowed:
        problems.append(("schema", t.get("id")))
    for s in t.get("steps_ar", []):
        if len(s.split()) > 25:
            problems.append(("long-step", t["id"], len(s.split())))
print("schema problems:", problems)

# protocol step -> tool ids referenced must exist
proto = d.get("protocol_ar", [])
unknown = []
for step in proto:
    txt = step if isinstance(step, str) else json.dumps(step, ensure_ascii=False)
    for m in re.findall(r"[a-z][a-z0-9]+(?:-[a-z0-9]+)+", txt):
        if m not in ids:
            unknown.append(m)
print("protocol ids not in tools:", sorted(set(unknown)))

# cited source paths must exist
PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s,;)\]]+|~[\\/][^\s,;)\]]+|\.claude[\\/]skills[\\/][^\s,;)\]]+")
home = Path.home()
missing = []
for t in tools:
    src = t.get("source", "")
    srcs = src if isinstance(src, list) else [src]
    for s in srcs:
        for p in PATH_RE.findall(str(s)):
            p = p.rstrip(".`'\"")
            if p.startswith("~"):
                q = home / p[2:]
            elif p.startswith(".claude"):
                q = home / p
            else:
                q = Path(p)
            if not q.exists():
                missing.append((t["id"], p[:90]))
print("cited paths not found:", len(missing))
for m in missing[:12]:
    print("   ", m)

print()
for t in tools:
    src = t.get("source", "")
    first = (src[0] if isinstance(src, list) and src else str(src))
    print(f" - {t['id']:28} | {', '.join(t['use_when'])[:34]:34} | {first[:80]}")
print("\nPROTOCOL:")
for s in proto:
    print("  ", (s if isinstance(s, str) else json.dumps(s, ensure_ascii=False))[:170])
print("\nDROPPED (first 13):")
for x in d.get("dropped", [])[:13]:
    print("  ", (x if isinstance(x, str) else json.dumps(x, ensure_ascii=False))[:150])
sys.exit(1 if problems else 0)
