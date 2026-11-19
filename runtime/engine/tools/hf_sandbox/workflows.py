#!/usr/bin/env python3
"""Read-only Higgsfield workflow catalog for KOSIF Black Dragon.

Only reads the bundled report-derived JSON; NEVER accesses HF or starts workloads.
Usage: workflows.py list [--json] | show NAME [--json] | route TASK [--json]
"""
import json
import pathlib
import sys

CATALOG = pathlib.Path(__file__).with_name("workflows.json")

def load():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert data["schema"] == "kosif.higgsfield.workflow-catalog.v1"
    return data

def route(task, entries):
    """Suggestions are purely lexical matches, NOT execution eligibility evidence."""
    needle = task.casefold()
    scores = []
    for entry in entries:
        if entry.get("alias_of"):
            continue
        score = sum((2 if len(k) >= 4 else 1) for k in entry["keywords"] if k.casefold() in needle)
        if score:
            scores.append((score, entry["name"]))
    scores.sort(key=lambda v: (-v[0], v[1]))
    return [name for _, name in scores[:6]]

def main(args=None):
    args = list(sys.argv[1:] if args is None else args)
    cmd = args.pop(0) if args else "list"
    json_mode = "--json" in args
    args = [a for a in args if a != "--json"]
    db = load()
    rows = db["workflows"]
    by_name = {r["name"]: r for r in rows}
    if cmd in ("list", "ls"):
        data = [{"name": r["name"], "readiness": r["readiness"], "alias_of": r["alias_of"], "paid_handoff_possible": r["paid_handoff_possible"]} for r in rows]
        if json_mode:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print("14 workflow entries — report-derived, not execution-tested; cost unverified:")
            for r in data:
                alias = " (alias of " + r["alias_of"] + ")" if r["alias_of"] else ""
                print(f"- {r['name']}: {r['readiness']}{alias}; paid handoff={r['paid_handoff_possible']}")
        return 0
    if cmd in ("show", "inspect"):
        if len(args) != 1 or args[0] not in by_name:
            print("usage: hf workflow NAME (see hf workflows)", file=sys.stderr)
            return 2
        print(json.dumps(by_name[args[0]], ensure_ascii=False, indent=2))
        return 0
    if cmd == "route":
        if not args:
            print("usage: hf route DESCRIPTION", file=sys.stderr)
            return 2
        suggestions = route(" ".join(args), rows)
        payload = {"suggestions": suggestions, "verified_execution": False, "cost_confirmed": False,
                   "note": "Catalog only. Check get_workflow_instructions and all dependencies inside live HF session. Require approval for billable calls."}
        if json_mode:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("اقتراحات من الفهرس فقط (لا تنفيذ ولا ضمان مجانية):")
            for name in suggestions:
                print("- " + name + " [" + by_name[name]["readiness"] + "]")
            if not suggestions:
                print("لا تطابق؛ ابدأ بفحص يدوي للتعليمات")
            print("أي توليد أو رفع أو استدعاء مدفوع يحتاج موافقة مسبقة والتحقق من الرصيد.")
        return 0
    print("usage: hf workflows | hf workflow NAME | hf route DESCRIPTION", file=sys.stderr)
    return 2

if __name__ == "__main__":
    sys.exit(main())
