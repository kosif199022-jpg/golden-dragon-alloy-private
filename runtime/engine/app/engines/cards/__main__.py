"""python -m engines.cards list [--family X] [--status data] | run <id> | run --family X | stats"""
import json
import sys

from . import cards, run, stats


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    argv = list(sys.argv[1:] if argv is None else argv)
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None  # noqa: E731
    cmd = argv[0] if argv else "stats"
    if cmd == "list":
        fam, status = opt("--family"), opt("--status")
        for r in cards().values():
            if (not fam or r["family"] == fam) and (not status or r["status"] == status):
                print("%-28s %-11s %-28s %s" % (r["id"], r["status"], r["family"], r["title"][:70]))
        return 0
    if cmd == "stats":
        print(json.dumps(stats(), ensure_ascii=False, indent=1))
        return 0
    if cmd == "run":
        fam = opt("--family")
        ids = [r["id"] for r in cards().values() if r["family"] == fam and r["status"] in ("data", "custom")] if fam else argv[1:2]
        if not ids:
            print("usage: python -m engines.cards run <id> | run --family X", file=sys.stderr)
            return 2
        bad = 0
        for cid in ids:
            res = run(cid)
            bad += res["verdict"] != "executed"
            if fam:
                print("%-24s %-9s %6ss %s" % (cid, res["verdict"], res.get("seconds", ""), res.get("reason", "")[:90]))
            else:
                print(json.dumps(res, ensure_ascii=False, indent=1))
        if fam:
            print("%d/%d executed" % (len(ids) - bad, len(ids)))
        return 0 if not bad else 3
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
