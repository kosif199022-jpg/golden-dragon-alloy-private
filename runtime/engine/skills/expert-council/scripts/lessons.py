#!/usr/bin/env python3
"""Expert Council - lessons ledger (learning from mistakes across sessions).

Lessons are stored as JSON lines OUTSIDE the skill folder so they survive skill updates:
  default: ~/.claude/expert-council/lessons.jsonl   (override with EXPERT_COUNCIL_LESSONS)

Commands:
  add     --domain D --mistake "..." --lesson "..." [--trigger "..."] [--severity low|med|high] [--source user|self|test]
  search  "query words" [--domain D] [--limit N]       -> lessons relevant to a task (run at task start)
  list    [--domain D] [--limit N]                      -> newest first
  hit     <id>                                          -> mark a lesson as applied again (raises its weight)
  stats                                                 -> counts per domain
  export  [--domain D]                                  -> markdown digest (to paste into a brief)
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PATH = Path(os.environ.get("EXPERT_COUNCIL_LESSONS",
                           Path.home() / ".claude" / "expert-council" / "lessons.jsonl"))
SEV_W = {"low": 1, "med": 2, "high": 3}


def load():
    if not PATH.exists():
        return []
    out = []
    for line in PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def save_all(rows):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(PATH)


def tokens(s):
    return {t for t in re.findall(r"[\w؀-ۿ]+", (s or "").lower()) if len(t) > 1}


def score(row, q):
    text = " ".join(str(row.get(k, "")) for k in ("domain", "trigger", "mistake", "lesson"))
    overlap = len(q & tokens(text))
    if not overlap:
        return 0
    return overlap * 10 + SEV_W.get(row.get("severity", "med"), 2) * 2 + row.get("hits", 0)


def fmt(r):
    return (f"[{r['id']}] ({r['domain']}, {r.get('severity','med')}, hits={r.get('hits',0)}, {r['date']})\n"
            f"   when : {r.get('trigger') or '-'}\n"
            f"   wrong: {r['mistake']}\n"
            f"   RULE : {r['lesson']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--domain", required=True)
    a.add_argument("--mistake", required=True)
    a.add_argument("--lesson", required=True)
    a.add_argument("--trigger", default="")
    a.add_argument("--severity", choices=list(SEV_W), default="med")
    a.add_argument("--source", choices=["user", "self", "test"], default="self")
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--domain")
    s.add_argument("--limit", type=int, default=7)
    l = sub.add_parser("list")
    l.add_argument("--domain")
    l.add_argument("--limit", type=int, default=20)
    h = sub.add_parser("hit")
    h.add_argument("id", type=int)
    sub.add_parser("stats")
    e = sub.add_parser("export")
    e.add_argument("--domain")
    args = ap.parse_args()

    rows = load()
    if args.cmd == "add":
        dup = [r for r in rows if r["domain"] == args.domain and tokens(r["lesson"]) == tokens(args.lesson)]
        if dup:
            dup[0]["hits"] = dup[0].get("hits", 0) + 1
            save_all(rows)
            print(f"duplicate -> reinforced lesson {dup[0]['id']}")
            return 0
        r = {"id": max([x["id"] for x in rows], default=0) + 1, "date": dt.date.today().isoformat(),
             "domain": args.domain, "trigger": args.trigger, "mistake": args.mistake,
             "lesson": args.lesson, "severity": args.severity, "source": args.source, "hits": 0}
        rows.append(r)
        save_all(rows)
        print("saved:\n" + fmt(r))
    elif args.cmd == "search":
        q = tokens(args.query)
        pool = [r for r in rows if not args.domain or r["domain"] == args.domain]
        ranked = sorted(((score(r, q), r) for r in pool), key=lambda x: -x[0])
        ranked = [r for sc, r in ranked if sc > 0][: args.limit]
        # always surface high-severity lessons of the same domain
        if args.domain:
            for r in pool:
                if r.get("severity") == "high" and r not in ranked:
                    ranked.append(r)
        print("\n".join(fmt(r) for r in ranked) if ranked else "no relevant lessons yet")
    elif args.cmd == "list":
        pool = [r for r in rows if not args.domain or r["domain"] == args.domain]
        print("\n".join(fmt(r) for r in reversed(pool[-args.limit:])) or "empty")
    elif args.cmd == "hit":
        for r in rows:
            if r["id"] == args.id:
                r["hits"] = r.get("hits", 0) + 1
                save_all(rows)
                print(f"lesson {args.id} hits={r['hits']}")
                return 0
        print("not found")
        return 1
    elif args.cmd == "stats":
        c = {}
        for r in rows:
            c[r["domain"]] = c.get(r["domain"], 0) + 1
        print(f"file: {PATH}\ntotal: {len(rows)}")
        for d, n in sorted(c.items(), key=lambda x: -x[1]):
            print(f"  {d}: {n}")
    elif args.cmd == "export":
        pool = [r for r in rows if not args.domain or r["domain"] == args.domain]
        pool.sort(key=lambda r: (-SEV_W.get(r.get("severity", "med"), 2), -r.get("hits", 0)))
        print("# Lessons learned\n")
        for r in pool:
            print(f"- **[{r['domain']}]** {r['lesson']}  _(was: {r['mistake']})_")
    return 0


if __name__ == "__main__":
    sys.exit(main())
