"""V75 `rose.py pen-math selftest`: measures every guarantee of the Living Pen numerical core
(living_pen/numerics.py, built from Atkinson & Han 2009). Read-only; prints JSON; exit 1 if any check fails."""
from __future__ import annotations
import json


def handle(a):
    from living_pen import numerics
    r = numerics.selftest()
    print(json.dumps(r, ensure_ascii=False, indent=1 if a.pretty else None, default=float))
    return 0 if r["all_ok"] else 1


def register(sub):
    p = sub.add_parser("pen-math", help="V75 Living Pen numerical core: measured guarantees (read-only)")
    p.add_argument("action", choices=["selftest"])
    p.add_argument("--pretty", action="store_true")
    p.set_defaults(ext_func=handle)
