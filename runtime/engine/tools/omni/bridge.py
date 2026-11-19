#!/usr/bin/env python3
"""Black Dragon v10.17: Omni Analyst bridge — triage any digital target, no run, no network.

    python scripts/dragon.py tool omni doctor
    python scripts/dragon.py tool omni classify TARGET
    python scripts/dragon.py tool omni probe TARGET [--json]
    python scripts/dragon.py tool omni plan TARGET [--depth 0-3]
    python scripts/dragon.py tool omni report TARGET [--out FILE]
    python scripts/dragon.py tool omni hyp "h1" "h2" ...
    python scripts/dragon.py tool omni bayes PRIOR LR [LR...]

Wraps skills/omni-analyst/scripts/omni.py verbatim: classify from magic bytes,
a safe fingerprint (hashes, entropy, salient strings), a layered analysis plan
with ready commands, a report skeleton, a competing-hypotheses (ACH) matrix,
and Bayesian likelihood-ratio updates. It never runs the target or the network.
Retool/dragon paths in the plan output resolve from the home folder; override
with OMNI_RETOOL / OMNI_DRAGON_DIR / DRAGON_HOME.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OMNI = ROOT / "skills" / "omni-analyst" / "scripts" / "omni.py"
USAGE = __doc__
CMDS = {"classify", "probe", "plan", "report", "hyp", "bayes"}


def main(argv) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if argv[0] == "doctor":
        ok = OMNI.is_file()
        print(f"  [{'ok' if ok else '--'}] omni.py  (stdlib-only, no network, never runs the target)")
        return 0 if ok else 1
    if argv[0] not in CMDS:
        print(f"unknown subcommand: {argv[0]}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    if not OMNI.is_file():
        print("omni.py missing from the skill", file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, str(OMNI)] + argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
