"""rd_bridge.py — asks the installed Red Dragon (~/.claude/skills/golden-dragon/scripts/rd.py) how it understands and routes
a request, for «التنين الذهبي»'s fusion router. Runs under the SYSTEM python (the frozen app calls it as a subprocess, so
rd.py's imports never have to be bundled), writes nothing: RED_DRAGON_HOME points to a fresh temp folder.

  python -X utf8 rd_bridge.py "<request>" [--exclude KEYS.json]   -> one JSON line:
     {"ok": true, "text": "<the request as understood>", "playbooks": [[score, id], ...], "version": "2.14.0"}
  As a module: route_info(text, exclude=None) -> the same dict (used by the evaluation, which hides the graded requests
  from the Red Dragon's example memory exactly like its own route_eval2.py does).
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

RD = Path(os.environ.get("RED_DRAGON_SKILL") or (Path.home() / ".claude" / "skills" / "golden-dragon")) / "scripts" / "rd.py"
_rd = None


def load():
    global _rd
    if _rd is None:
        os.environ["RED_DRAGON_HOME"] = tempfile.mkdtemp(prefix="gd-rd-")
        spec = importlib.util.spec_from_file_location("rd_for_gd", RD)
        mod = importlib.util.module_from_spec(spec)
        argv, sys.argv = sys.argv, [str(RD)]
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.argv = argv
        _rd = mod
    return _rd


def route_info(text, exclude=None, limit=6):
    rd = load()
    if exclude:
        rd.EX_EXCLUDE.update(exclude)
    u = rd.understand(text)
    pb, _ = rd.route(u["text"], limit=limit)
    ver = getattr(rd, "VERSION", "") or ""
    return {"ok": True, "text": u["text"], "playbooks": [[round(float(s), 3), p["id"]] for s, p in pb], "version": ver}


def keys_for(texts):
    rd = load()
    return [rd.ex_key(t) for t in texts]


def main(argv):
    if not argv:
        print(json.dumps({"ok": False, "error": "usage: rd_bridge.py <request> [--exclude KEYS.json]"}))
        return 2
    exclude = None
    if "--exclude" in argv:
        i = argv.index("--exclude")
        exclude = json.loads(Path(argv[i + 1]).read_text(encoding="utf-8"))
        argv = argv[:i] + argv[i + 2:]
    try:
        print(json.dumps(route_info(" ".join(argv), exclude), ensure_ascii=False))
        return 0
    except Exception as e:                                   # the router falls back to its own scoring
        print(json.dumps({"ok": False, "error": repr(e)[:300]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
