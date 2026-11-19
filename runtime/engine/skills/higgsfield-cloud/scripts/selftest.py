#!/usr/bin/env python3
"""selftest.py — offline self-test of the higgsfield-cloud skill on Windows (no Higgsfield calls, ~20 s).
Checks: bash syntax of every cloud script, qc PASS on a clean clip and FAIL on a broken one (black middle +
odd size + moov at end), sheet size limit, enc.sh frame-exact parts + concat equal the source frame count,
cost gate exit codes, plan output, pack determinism. Exit 0 = all good.
"""
import os, subprocess, sys, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__)); SKILL = os.path.dirname(HERE); CLOUD = os.path.join(SKILL, "cloud")
sys.path.insert(0, HERE)
import hfc  # noqa: E402

PY = sys.executable; BASH = hfc.git_bash(); ok = True


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


t = tempfile.mkdtemp(prefix="hfc_selftest_")
try:
    for f in ["hfc"] + [x for x in os.listdir(CLOUD) if x.endswith(".sh")]:
        r = run([BASH, "-n", hfc.fwd(os.path.join(CLOUD, f))]); check(f"bash -n {f}", r.returncode == 0, r.stderr[-200:])
    good, bad = os.path.join(t, "good.mp4"), os.path.join(t, "bad.mp4")
    run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=540x960:rate=30", "-f", "lavfi",
         "-i", "sine=f=440:r=48000", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-af", "volume=-12dB",
         "-movflags", "+faststart", good])
    run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
         "testsrc2=size=541x960:rate=30,drawbox=t=fill:c=black:enable='between(t,0.8,1.3)'", "-f", "lavfi", "-i",
         "sine=f=440:r=48000", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv444p", "-c:a", "aac", bad])
    qc = os.path.join(CLOUD, "qc.py")
    r = run([PY, "-X", "utf8", qc, good, "--w", "540", "--h", "960", "--fps", "30", "--dur", "2"])
    check("qc PASS on clean clip", r.returncode == 0, r.stdout[-300:])
    r = run([PY, "-X", "utf8", qc, bad, "--fps", "30", "--dur", "2"])
    check("qc FAIL on broken clip", r.returncode == 1 and "black inside" in r.stdout and "moov" in r.stdout, r.stdout[-400:])
    s = os.path.join(t, "s.jpg")
    r = run([PY, "-X", "utf8", os.path.join(CLOUD, "sheet.py"), good, "-o", s, "--n", "4"])
    check("sheet <= 480 KB", r.returncode == 0 and os.path.getsize(s) <= 480 * 1024, r.stderr[-200:])
    enc = hfc.fwd(os.path.join(CLOUD, "enc.sh")); parts = []
    for i, (a, n) in enumerate([(0, 23), (23, 37)]):
        p = os.path.join(t, f"p{i}.mp4"); parts.append(p)
        r = run([BASH, enc, hfc.fwd(good), hfc.fwd(p), "--start-frame", str(a), "--frames", str(n), "--preset", "veryfast"])
        check(f"enc part {i} ({n} frames)", r.returncode == 0 and f",{n}," in r.stdout, (r.stdout + r.stderr)[-300:])
    lst = os.path.join(t, "l.txt"); open(lst, "w").write("".join(f"file '{hfc.fwd(p)}'\n" for p in parts))
    j = os.path.join(t, "j.mp4")
    run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", j])
    fr, _ = hfc.probe_frames(j); check("parts concat = 60 frames", fr == 60, f"got {fr}")
    r = run([PY, "-X", "utf8", os.path.join(HERE, "hfc.py"), "check", "sandbox_exec"]); check("check free -> exit 0", r.returncode == 0)
    r = run([PY, "-X", "utf8", os.path.join(HERE, "hfc.py"), "check", "generate_video"]); check("check paid -> exit 3", r.returncode == 3)
    if os.path.exists(os.path.join(SKILL, "data", "measured.json")):
        r = run([PY, "-X", "utf8", os.path.join(HERE, "hfc.py"), "plan", "--task", "encode", "--in-mb", "300", "--video-sec", "60"])
        check("plan encode prints a best choice", "plan: best =" in r.stdout, r.stdout[-300:] + r.stderr[-300:])
    a, b = hfc.build_tar(), hfc.build_tar(); check("pack is deterministic", a == b)
finally:
    shutil.rmtree(t, ignore_errors=True)
    shutil.rmtree(os.path.join(HERE, "__pycache__"), ignore_errors=True)
print("SELFTEST", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
