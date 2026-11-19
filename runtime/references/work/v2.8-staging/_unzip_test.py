import datetime, json, os, subprocess, sys, tempfile, time, zipfile
from pathlib import Path
zp = Path.home() / "OneDrive" / "Desktop" / "red-dragon-v2.8.1.zip"
root = Path.home() / "rd-staging" / ("unzip-test-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
root.mkdir(parents=True)
with zipfile.ZipFile(zp) as z:
    tops = {n.split("/")[0] for n in z.namelist()}
    z.extractall(root)
skill = root / "red-dragon"
home = root / "_home"
home.mkdir()
env = {**os.environ, "RED_DRAGON_HOME": str(home), "PYTHONUTF8": "1"}
print(json.dumps({"dir": str(root), "top_folders": sorted(tops), "files": sum(1 for p in skill.rglob("*") if p.is_file()),
                  "lock_present": (skill / ".rd-lock.json").exists(), "manifest": json.loads((skill / "MANIFEST_SHA256.json").read_text(encoding="utf-8")).get("version")}, ensure_ascii=False))
for cmd in (["start"], ["selftest"]):
    t = time.time()
    r = subprocess.run([sys.executable, "-X", "utf8", str(skill / "scripts" / "rd.py"), *cmd], cwd=skill, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    print(f"== {cmd[0]}: exit {r.returncode}, {time.time()-t:.0f}s, {len(out)} chars")
    print(out[-1800:] if cmd[0] == "selftest" else out[:900])
print("home files:", sorted(p.name for p in home.rglob("*") if p.is_file())[:15])
