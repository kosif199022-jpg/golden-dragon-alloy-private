"""Back up the installed red-dragon parts that change, copy the staging files listed in _copy_list.txt, verify every copy by sha256.
    python -I -X utf8 _install.py            dry run (backup only)
    python -I -X utf8 _install.py --apply    backup + copy + verify
"""
import datetime, hashlib, json, shutil, sys, zipfile
from pathlib import Path

ST = Path(__file__).resolve().parent
INST = Path.home() / ".claude" / "skills" / "red-dragon"
BK_DIR = ST.parent / "backups"
APPLY = "--apply" in sys.argv
lst = [ln.strip() for ln in (ST / "_copy_list.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


BK_DIR.mkdir(parents=True, exist_ok=True)
ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
_v = next((ln.split('"')[1] for ln in (INST / "scripts" / "rd.py").read_text(encoding="utf-8").splitlines() if ln.startswith("VERSION =")), "x")
bk = BK_DIR / f"red-dragon-v{_v}-installed-parts-{ts}.zip"
n = 0
with zipfile.ZipFile(bk, "w", zipfile.ZIP_DEFLATED) as z:
    for part in ("scripts", "mind", "references", "SKILL.md"):
        base = INST / part
        files = [base] if base.is_file() else [f for f in base.rglob("*") if f.is_file() and "__pycache__" not in f.parts]
        for f in files:
            z.write(f, f.relative_to(INST).as_posix())
            n += 1
with zipfile.ZipFile(bk) as z:
    bad = z.testzip()
print(json.dumps({"backup": str(bk), "files": n, "mb": round(bk.stat().st_size / 1e6, 1), "testzip": bad or "ok"}, ensure_ascii=False))
if bad:
    raise SystemExit("backup zip is broken: nothing copied")
if not APPLY:
    print(f"dry run: would copy {len(lst)} files")
    raise SystemExit(0)
done, mismatch = [], []
for rel in lst:
    src, dst = ST / rel, INST / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    (done if sha(src) == sha(dst) else mismatch).append(rel)
print(json.dumps({"copied": len(done), "mismatch": mismatch}, ensure_ascii=False))
