"""Pack the alloy. One skill, two packings (same SKILL.md, same alloy.py, same kb — the skill detects which it is):

    python -I -X utf8 forge/pack.py OUT_DIR
  golden-dragon-alloy.skill          full: + runtime/ (engine room) + branches/   → the owner's laptop (Claude Code)
  golden-dragon-alloy-portable.zip   no runtime/ and no branches/ (their text is in kb) → claude.ai / cloud sessions

Both zips hold the folder golden-dragon-alloy/ at the top (what claude.ai and Claude Code expect).
__pycache__ is never packed. Each zip is re-opened and its file count and CRC checked before reporting.
"""
import os
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = ROOT.name
SKIP_DIRS = {"__pycache__", ".pytest_cache"}


def files(include_engine_room: bool):
    for dp, dn, fn in os.walk(ROOT):
        rel_dir = Path(dp).relative_to(ROOT).as_posix()
        dn[:] = sorted(d for d in dn if d not in SKIP_DIRS)
        if not include_engine_room and rel_dir == ".":
            dn[:] = [d for d in dn if d not in ("runtime", "branches")]
        for f in sorted(fn):
            yield Path(dp) / f, (f if rel_dir == "." else f"{rel_dir}/{f}")


def pack(out: Path, include_engine_room: bool) -> None:
    t = time.time()
    if out.exists():
        out.unlink()
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for full, rel in files(include_engine_room):
            z.write(full, f"{NAME}/{rel}")
            n += 1
    with zipfile.ZipFile(out) as z:
        bad = z.testzip()
        names = z.namelist()
    tops = {x.split("/", 1)[0] for x in names}
    skills = [x for x in names if x.endswith("/SKILL.md") and x.count("/") == 1]
    ok = bad is None and len(names) == n and tops == {NAME} and skills == [f"{NAME}/SKILL.md"]
    print(f"{'✓' if ok else '✗'} {out.name}: {n:,} files · {out.stat().st_size / 1e6:.1f} MB · top={sorted(tops)} · "
          f"crc={'ok' if bad is None else bad} · {time.time() - t:.0f}s")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    pack(out_dir / f"{NAME}-portable.zip", False)
    pack(out_dir / f"{NAME}.skill", True)
