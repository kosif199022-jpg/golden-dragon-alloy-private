#!/usr/bin/env python3
"""Black Dragon v10.17: Dragon Genius bridge — delivery gate + transcript QA.

    python scripts/dragon.py tool genius doctor
    python scripts/dragon.py tool genius gate OUT.mp4 --aspect 9:16 --expect 30
    python scripts/dragon.py tool genius qa captions.srt --fps 30

Wraps skills/dragon-genius/scripts/{media_gate.py,transcript_qa.py} verbatim.
`gate` measures a finished video (duration, audio codec, yuv420p, even dims,
faststart, black/freeze, LUFS, true peak) and needs ffprobe/ffmpeg on PATH.
`qa` checks a transcript/caption file (CPS, line length, noise ratio, order)
and is stdlib-only. Neither renders, downloads, or calls the network.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "dragon-genius"
GATE = SKILL / "scripts" / "media_gate.py"
QA = SKILL / "scripts" / "transcript_qa.py"
USAGE = __doc__


def doctor() -> int:
    checks = {
        "media_gate.py": GATE.is_file(),
        "transcript_qa.py": QA.is_file(),
        "ffprobe": bool(shutil.which("ffprobe")),
        "ffmpeg": bool(shutil.which("ffmpeg")),
    }
    for name, ok in checks.items():
        print(f"  [{'ok' if ok else '--'}] {name}")
    print("gate needs ffprobe/ffmpeg; qa is stdlib-only. No render, no network.")
    return 0 if GATE.is_file() and QA.is_file() else 1


def main(argv) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "doctor":
        return doctor()
    if cmd == "gate":
        if not GATE.is_file():
            print("media_gate.py missing from the skill", file=sys.stderr)
            return 1
        return subprocess.call([sys.executable, str(GATE)] + rest)
    if cmd == "qa":
        if not QA.is_file():
            print("transcript_qa.py missing from the skill", file=sys.stderr)
            return 1
        return subprocess.call([sys.executable, str(QA)] + rest)
    print(f"unknown subcommand: {cmd}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
