"""Offline test of krita_draw._watch (no Krita needed): python -X utf8 test_watch.py"""
import json, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent))
import krita_draw as kd

W = 'import json,sys,time,os; json.dump({"steps":[],"ok":True,"seconds":1.0}, open(os.path.join(os.getcwd(),"result.json"),"w"))'
cases = {
    "hang after finish": (W + "; time.sleep(60)", 20, lambda c, s: c.startswith("finished") and s < 6),
    "clean exit": (W, 20, lambda c, s: c == 0 and s < 5),
    "hang, never finished": ("import time; time.sleep(60)", 3, lambda c, s: c == "timeout" and 2.5 < s < 6),
}
bad = 0
for name, (code, timeout, want) in cases.items():
    job = Path(tempfile.mkdtemp(prefix="kd_watch_"))
    c, err, secs = kd._watch([sys.executable, "-c", code], job, timeout, grace=2)
    ok = want(c, secs)
    bad += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}: code={c!r} secs={secs} stderr_file_left={(job / 'krita_stderr.txt').exists()}")
print("all pass" if not bad else f"{bad} failed")
sys.exit(bad)
