"""Was the desktop-bridge patch (Desktop zip, 11:48) applied before v2.8, and does v2.8 rd.py keep its changes?"""
import difflib, hashlib, re, zipfile
from pathlib import Path

PZ = Path.home() / "OneDrive" / "Desktop" / "red-dragon-v2.7.1-blackdragon2-desktop-bridge-patch.zip"
INST = Path.home() / ".claude" / "skills" / "red-dragon"
BK = sorted((Path.home() / "rd-staging" / "backups").glob("red-dragon-v2.7.0-parts-*.zip"))[0]      # oldest = the installed before any v2.8 copy
z = zipfile.ZipFile(PZ)
print("== README-PATCH ==")
print(z.read("README-PATCH.md").decode("utf-8")[:1800])
p_rd = z.read("red-dragon/scripts/rd.py").decode("utf-8")
b_rd = zipfile.ZipFile(BK).read("scripts/rd.py").decode("utf-8")
i_rd = (INST / "scripts" / "rd.py").read_text(encoding="utf-8")
h = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]
print(f"\n== rd.py == patch {h(p_rd)} ({len(p_rd)}) · installed-before-v2.8 {h(b_rd)} ({len(b_rd)}) · now {h(i_rd)} ({len(i_rd)})")
print("patch VERSION:", re.search(r'VERSION = "([^"]+)"', p_rd).group(1), "· before-v2.8 VERSION:", re.search(r'VERSION = "([^"]+)"', b_rd).group(1))
d = [l for l in difflib.unified_diff(b_rd.splitlines(), p_rd.splitlines(), "before-v2.8", "patch", n=0, lineterm="") if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
print(f"lines patch adds/changes vs installed-before-v2.8: {len(d)}")
for l in d[:40]:
    print("  ", l[:160])
added = [l[1:].strip() for l in d if l.startswith("+") and l[1:].strip()]
kept = sum(1 for l in added if l in i_rd)
print(f"patch lines present in v2.8 rd.py now: {kept}/{len(added)}")
br = INST / "engine" / "skills" / "blackdragon-desktop-bridge"
print("bridge skill installed:", br.is_dir(), [f.relative_to(br).as_posix() for f in br.rglob("*") if f.is_file()] if br.is_dir() else "")
for n in z.namelist():
    if n.startswith("red-dragon/engine/"):
        t = INST / n[len("red-dragon/"):]
        print(" ", n[len("red-dragon/"):], "same" if t.is_file() and t.read_bytes() == z.read(n) else ("DIFFERENT" if t.is_file() else "MISSING"))
