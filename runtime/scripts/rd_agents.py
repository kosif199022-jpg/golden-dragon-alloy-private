#!/usr/bin/env python3
"""Red Dragon subagents: install the cheap Haiku worker (agents/*.md) into Claude Code.

  list                      what agents ship with Red Dragon
  install [--dest DIR] [--dry-run]   copy to ~/.claude/agents (default). A different existing file is backed up to *.bak first
  check                     frontmatter is valid (name, description, model, tools)
"""
import argparse, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "agents"


def front(p):
    t = p.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", t, re.S)
    if not m:
        return {}
    return {k.strip(): v.strip() for k, v in (l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)}


def agents():
    return sorted(SRC.glob("*.md"))


def check():
    bad = []
    for p in agents():
        f = front(p)
        for k in ("name", "description", "model", "tools"):
            if not f.get(k):
                bad.append(f"{p.name}: مفيش {k}")
        if f.get("name") != p.stem:
            bad.append(f"{p.name}: الاسم {f.get('name')} ≠ اسم الملف")
        if f.get("model") not in ("haiku", "sonnet", "opus", "inherit"):
            bad.append(f"{p.name}: موديل غريب {f.get('model')}")
        if re.search(r"\b(WebFetch|Edit)\b", f.get("tools", "")) and f.get("model") == "haiku":
            bad.append(f"{p.name}: العامل الرخيص مايتديش أدوات نت أو تعديل")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("list")
    s = sp.add_parser("install"); s.add_argument("--dest", default=str(Path.home() / ".claude" / "agents")); s.add_argument("--dry-run", action="store_true")
    sp.add_parser("check")
    a = ap.parse_args()
    if a.cmd == "list":
        for p in agents():
            f = front(p)
            print(f"{f.get('name')} · موديل {f.get('model')} · أدوات {f.get('tools')}\n    {f.get('description', '')[:160]}")
    elif a.cmd == "check":
        bad = check()
        print("✅ agents ok" if not bad else "\n".join("❌ " + b for b in bad))
        sys.exit(1 if bad else 0)
    else:
        bad = check()
        if bad:
            sys.exit("\n".join("❌ " + b for b in bad))
        dest = Path(a.dest)
        for p in agents():
            d = dest / p.name
            same = d.is_file() and d.read_bytes() == p.read_bytes()
            act = "نفس النسخة، اتساب" if same else ("هيتبدّل (والقديم ← .bak)" if d.exists() else "جديد")
            print(f"{p.name} ← {d}: {act}")
            if a.dry_run or same:
                continue
            dest.mkdir(parents=True, exist_ok=True)
            if d.exists():
                shutil.copy2(d, d.with_suffix(".md.bak"))
            shutil.copy2(p, d)
        if not a.dry_run:
            print("خلاص. افتح جلسة Claude Code جديدة (أو /agents) عشان يظهر.")


if __name__ == "__main__":
    main()
