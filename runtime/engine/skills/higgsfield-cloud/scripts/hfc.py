#!/usr/bin/env python3
"""hfc.py — the Windows side of the Higgsfield free-cloud skill. It never calls Higgsfield itself;
Claude calls the MCP tools (sandbox_exec, media_upload, media_confirm, balance) and this script does the
local work: packing, transfer, measuring, deciding, splitting, joining, bookkeeping.

  python -X utf8 hfc.py pack                      build dist/hfc-cloud-VER.tar.gz (upload it once, then set-url)
  python -X utf8 hfc.py install-cmd               the short sandbox_exec install command (needs set-url once)
  python -X utf8 hfc.py set-url URL               record the CloudFront URL of the uploaded toolkit tarball
  python -X utf8 hfc.py put FILE 'UPLOAD_URL'     upload a local file to a media_upload URL (prints HTTP + MB/s)
  python -X utf8 hfc.py pull URL OUT [--sha256 H] download a cloud result (atomic .part, sha256, MB/s)
  python -X utf8 hfc.py plan --task encode|whisper|html|download [...]   cloud vs local, with transfer time
  python -X utf8 hfc.py check TOOL [TOOL..]       free / paid / unknown for Higgsfield MCP tools (exit 3 = ask owner)
  python -X utf8 hfc.py split SRC --out DIR [--parts 8] [--cloud-share 0.7|auto] [--run-local] [enc opts]
  python -X utf8 hfc.py join DIR OUT              concat local+cloud parts, add source audio, verify frames
  python -X utf8 hfc.py ledger add BEFORE AFTER "note" | ledger show
  python -X utf8 hfc.py bench                     run cloud/bench.sh locally (Git Bash) for the speed table
  python -X utf8 hfc.py facts                     print data/measured.json (what was measured, when)
"""
import hashlib, io, json, os, shutil, subprocess, sys, tarfile, time
from fractions import Fraction

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOUD, DATA, DIST = (os.path.join(SKILL, d) for d in ("cloud", "data", "dist"))
VERSION = open(os.path.join(CLOUD, "VERSION"), encoding="utf-8").read().strip()
EXEC = {"hfc"}  # extensionless executables


def jload(name, default=None):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def jsave(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git_bash():
    for p in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe"):
        if os.path.exists(p):
            return p
    b = shutil.which("bash")
    if b and "system32" not in b.lower():  # never WSL's bash.exe
        return b
    sys.exit("hfc: Git Bash not found")


def fwd(p):
    return os.path.abspath(p).replace("\\", "/")


# ---------------------------------------------------------------- pack / install
def build_tar():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9) as tf:
        for root, dirs, files in os.walk(CLOUD):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for fn in sorted(f for f in files if not f.endswith((".pyc", ".pyo"))):
                full = os.path.join(root, fn); rel = os.path.relpath(full, CLOUD).replace("\\", "/")
                data = open(full, "rb").read().replace(b"\r\n", b"\n")  # bash dies on CRLF
                ti = tarfile.TarInfo(rel); ti.size = len(data); ti.mtime = 0; ti.uid = ti.gid = 0
                ti.mode = 0o755 if (fn in EXEC or fn.endswith((".sh", ".py", ".js"))) else 0o644
                tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()



def cmd_pack(args):
    os.makedirs(DIST, exist_ok=True)
    data = build_tar(); h = hashlib.sha256(data).hexdigest()
    tgz = os.path.join(DIST, f"hfc-cloud-{VERSION}.tar.gz"); open(tgz, "wb").write(data)
    info = jload("install.json", {}) or {}
    print(f"pack: {tgz} bytes={len(data)} sha256={h}")
    if info.get("sha256") != h or info.get("version") != VERSION:
        # Higgsfield's rule: bytes travel by presigned PUT from where they are, never as base64 pasted into commands.
        print(f"pack: NOT uploaded yet -> media_upload files=[{{filename:'hfc-cloud-{VERSION}.tar.gz'}}], "
              f"then: hfc.py put \"{tgz}\" 'UPLOAD_URL' --type application/octet-stream, media_confirm type=file, "
              "hfc.py set-url URL")
    else:
        print("pack: matches the uploaded tarball -> hfc.py install-cmd")


def cmd_set_url(args):
    if not args:
        sys.exit("usage: hfc.py set-url URL")
    tgz = os.path.join(DIST, f"hfc-cloud-{VERSION}.tar.gz")
    if not os.path.exists(tgz):
        sys.exit("run pack first")
    jsave("install.json", {"version": VERSION, "url": args[0], "sha256": sha256(tgz), "set": time.strftime("%Y-%m-%d %H:%M")})
    print("set-url: saved data/install.json"); cmd_install_cmd([])


def cmd_install_cmd(args):
    info = jload("install.json", {}) or {}
    tgz = os.path.join(DIST, f"hfc-cloud-{VERSION}.tar.gz")
    if not info.get("url") or info.get("version") != VERSION or (os.path.exists(tgz) and sha256(tgz) != info.get("sha256")):
        sys.exit("install-cmd: no uploaded tarball for this version. Run pack, upload, set-url .")
    v, u, h = info["version"], info["url"], info["sha256"]
    print(f"[ \"$(cat ~/hfc/VERSION 2>/dev/null)\" = \"{v}\" ] && echo \"hfc {v} already installed\" || "
          f"{{ curl -fsSL --retry 3 '{u}' -o /tmp/hfc.tgz && echo \"{h}  /tmp/hfc.tgz\" | sha256sum -c --quiet - && "
          f"rm -rf ~/hfc && mkdir -p ~/hfc && tar xzf /tmp/hfc.tgz -C ~/hfc && echo \"hfc {v} installed\"; }}; ~/hfc/hfc doctor")


# ---------------------------------------------------------------- transfer
# Both directions use curl.exe (ships with Windows 10/11). Measured 2026-11-11: upload.higgsfield.ai sits behind
# Cloudflare and answers Python-urllib with 403 "error code: 1010"; Higgsfield's own instructions say curl.
MEDIA_CT = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".png": "image/png",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".mp3": "audio/mpeg", ".wav": "audio/wav",
            ".m4a": "audio/mp4"}


def curl_exe():
    for c in (r"C:\Windows\System32\curl.exe", shutil.which("curl.exe"), shutil.which("curl")):
        if c and os.path.exists(c):
            return c
    sys.exit("hfc: curl not found")


def cmd_put(args):
    # The presigned URL signs content-type AND if-none-match: send media_upload's content_type exactly + If-None-Match: *
    if len(args) < 2:
        sys.exit("usage: hfc.py put FILE 'UPLOAD_URL' [--type CONTENT_TYPE from media_upload]")
    path, url = args[0], args[1]; n = os.path.getsize(path)
    ct = args[args.index("--type") + 1] if "--type" in args else MEDIA_CT.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
    body = os.path.join(os.environ.get("TEMP", "."), "hfc_put_body.txt")
    r = subprocess.run([curl_exe(), "-sS", "-X", "PUT", "-H", f"Content-Type: {ct}", "-H", "If-None-Match: *",
                        "--upload-file", path, "--connect-timeout", "20", "--speed-limit", "10240", "--speed-time", "60",
                        "-o", body, "-w", "%{http_code} %{speed_upload} %{time_total}", url], capture_output=True, text=True)
    try:
        code, speed, tt = r.stdout.split()
    except ValueError:
        code, speed, tt = "000", "0", "0"
    print(f"put: {path} http={code} type={ct} bytes={n} s={float(tt):.1f} MBps={float(speed) / 1048576:.2f} sha256={sha256(path)}")
    if code != "200":
        print("put: " + (r.stderr.strip() or open(body, encoding="utf-8", errors="replace").read()[:300]))
        sys.exit(1)


def cmd_pull(args):
    if len(args) < 2:
        sys.exit("usage: hfc.py pull URL OUT [--sha256 H]")
    url, out = args[0], args[1]
    want = args[args.index("--sha256") + 1] if "--sha256" in args else None
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    part = out + ".part"
    r = subprocess.run([curl_exe(), "-fL", "-sS", "--retry", "5", "--retry-delay", "2", "--retry-all-errors", "-C", "-",
                        "--connect-timeout", "20", "-o", part, "-w", "%{http_code} %{speed_download} %{time_total}", url],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"pull: curl failed rc={r.returncode} {r.stderr.strip()[:300]} (partial kept: {part})")
    code, speed, tt = r.stdout.split()
    got = sha256(part)
    if want and want.lower() != got:
        sys.exit(f"pull: SHA256 MISMATCH got {got} want {want} (kept {part})")
    os.replace(part, out)
    print(f"pull: {out} http={code} bytes={os.path.getsize(out)} s={float(tt):.1f} MBps={float(speed) / 1048576:.2f} "
          f"sha256={got}{' (verified)' if want else ''}")


# ---------------------------------------------------------------- decide
def cmd_plan(args):
    import argparse
    ap = argparse.ArgumentParser(prog="hfc.py plan")
    ap.add_argument("--task", required=True, choices=["encode", "whisper", "html", "download"])
    ap.add_argument("--in-mb", type=float, default=0, help="local input that must be uploaded")
    ap.add_argument("--video-sec", type=float, default=0, help="output video seconds (encode/html)")
    ap.add_argument("--audio-sec", type=float, default=0, help="speech seconds (whisper)")
    ap.add_argument("--kind", default="reel", choices=["reel", "hd"], help="encode load: reel=9:16 slow, hd=16:9 medium")
    ap.add_argument("--out-mbps", type=float, default=12.0, help="expected output bitrate to download back")
    ap.add_argument("--fps", type=float, default=30); ap.add_argument("--dl-mb", type=float, default=0)
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--xl-a", type=float, help="this session's `hfc bench --quick` A seconds on XL (XL speed varies ~2x)")
    a = ap.parse_args(args)
    m = jload("measured.json")
    if not m:
        sys.exit("plan: data/measured.json missing — measure first (bench on both sides)")
    up, down = m["local"]["upload_MBps"], m["local"]["download_MBps"]
    key = "B_reel_slow_noise_s" if a.kind == "reel" else "A_1080p_medium_s"
    L = m["local"]["bench"][key] / 10.0; X = m["cloud_xl"]["bench"][key] / 10.0; S = m["cloud_standard"]["bench"][key] / 10.0
    if a.xl_a:  # scale the stored XL numbers to this session's allocation
        X *= a.xl_a / m["cloud_xl"]["bench"]["A_1080p_medium_s"]
    over = m.get("overhead_s", 15)
    out_mb = a.video_sec * a.out_mbps / 8
    rows = []
    if a.task == "encode":
        rows = [("local", a.video_sec * L, "no transfer"),
                ("cloud xl", a.in_mb / up + over + a.video_sec * X + out_mb / down, f"upload {a.in_mb:.0f}MB@{up}MB/s + download {out_mb:.0f}MB@{down}MB/s"),
                ("cloud standard", a.in_mb / up + over + a.video_sec * S + out_mb / down, "same transfer, slower CPU")]
        share = (1 / X) / (1 / X + 1 / L)
        hyb = max(a.in_mb / up + over + a.video_sec * share * X + out_mb * share / down, a.video_sec * (1 - share) * L) + 5
        rows.append((f"hybrid ({share:.0%} cloud)", hyb, "hfc.py split --cloud-share auto; only if the upload is already done or tiny"))
    elif a.task == "whisper":
        w = m.get("whisper", {}); r_cloud = w.get(f"{a.model}_rtf_xl"); r_loc = w.get(f"{a.model}_rtf_local")
        audio_mb = a.audio_sec * 4 / 1024  # 32 kbps opus extracted locally first
        if r_cloud: rows.append(("cloud xl", audio_mb / up + over + w.get("load_s", 10) + a.audio_sec * r_cloud, "upload only the extracted audio"))
        rows.append(("local", w.get("load_s_local", 18) + a.audio_sec * r_loc if r_loc else float("nan"), "measured" if r_loc else "not measured for this model"))
    elif a.task == "html":
        h = m.get("html2mp4", {}); frames = a.video_sec * a.fps
        if h.get("ms_per_frame_xl"):
            enc_per_s = h.get("encode_s", 5) / 6.0  # motion graphics encode fast; the noisy B bench would overstate it 14x
            out_mb = a.video_sec * 1.0 / 8  # clean graphics measured ~0.9 Mbps
            rows.append(("cloud xl", over + frames * h["ms_per_frame_xl"] / 1000 + a.video_sec * enc_per_s + out_mb / down,
                         "Chromium+fonts preinstalled, only the MP4 comes back"))
        rows.append(("local", float("nan"), "needs local Playwright/Chromium setup; not measured"))
    elif a.task == "download":
        cl = m.get("cloud_internet_MBps", 20)
        rows = [("local", a.dl_mb / down, f"{down} MB/s"),
                ("cloud, process there, bring back result", a.dl_mb / cl + over + out_mb / down, f"{cl} MB/s in the datacenter")]
    rows.sort(key=lambda r: (r[1] != r[1], r[1]))
    for name, sec, why in rows:
        print(f"  {name:28s} {'?' if sec != sec else f'{sec:7.0f} s'}   {why}")
    best = rows[0][0]
    risky = a.in_mb > m.get("safe_upload_mb", 50)
    if risky and best != "local":
        print(f"plan: RISK uploads > {m.get('safe_upload_mb', 50)} MB from this machine are unreliable "
              f"({m['local'].get('upload_note', '')}). Prefer local, or put the footage online first.")
        best = next(r[0] for r in rows if r[0] == "local") + " (cloud rows need a large upload)"
    print(f"plan: best = {best}   (numbers: data/measured.json, {m.get('as_of')}; XL speed varies ~2x: pass --xl-a)")


# ---------------------------------------------------------------- cost gate
def cmd_check(args):
    t = jload("tools.json", {})
    worst = 0
    for tool in args:
        n = tool.split("__")[-1]
        rec = next((r for r in t.get("tools", []) if r["name"] == n), None)
        if rec is None:
            cls = "paid?" if any(k in n for k in t.get("paid_hints", [])) else "unknown"
            print(f"{n}: {cls} -> needs the owner's explicit yes with the price"); worst = 3; continue
        print(f"{n}: {rec['class']} — {rec.get('evidence', '')}")
        if rec["class"] != "free":
            worst = 3
    sys.exit(worst)


# ---------------------------------------------------------------- hybrid split / join
def probe_frames(src):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                        "stream=r_frame_rate,avg_frame_rate,nb_read_packets", "-of", "json", src], capture_output=True, text=True)
    s = json.loads(r.stdout)["streams"][0]
    r_, a_ = Fraction(s["r_frame_rate"]), Fraction(s.get("avg_frame_rate") or s["r_frame_rate"])
    if a_ and abs(float(r_ - a_)) / float(r_) > 0.01:  # mp4 timestamp rounding gives ~0.03 % — not VFR
        print(f"split: WARNING variable frame rate ({s['avg_frame_rate']} avg vs {s['r_frame_rate']}); "
              "frame-exact parts assume CFR — convert first with enc --fps N")
    return int(s["nb_read_packets"]), s["r_frame_rate"]


def cmd_split(args):
    import argparse
    ap = argparse.ArgumentParser(prog="hfc.py split")
    ap.add_argument("src"); ap.add_argument("--out", required=True); ap.add_argument("--parts", type=int, default=8)
    ap.add_argument("--cloud-share", default="auto"); ap.add_argument("--run-local", action="store_true")
    ap.add_argument("--kind", default="reel", choices=["reel", "hd"])
    ap.add_argument("--enc", default="--preset slow --crf 18", help="options passed to enc for every part (same on both sides)")
    ap.add_argument("--xl-a", type=float, help="this session's `hfc bench --quick` A seconds on XL")
    a = ap.parse_args(args)
    frames, rfps = probe_frames(a.src)
    if a.cloud_share == "auto":
        m = jload("measured.json"); key = "B_reel_slow_noise_s" if a.kind == "reel" else "A_1080p_medium_s"
        L, X = m["local"]["bench"][key], m["cloud_xl"]["bench"][key]
        if a.xl_a:
            X *= a.xl_a / m["cloud_xl"]["bench"]["A_1080p_medium_s"]
        share = (1 / X) / (1 / X + 1 / L)
    else:
        share = float(a.cloud_share)
    step = -(-frames // a.parts); total = -(-frames // step)  # real part count (short videos give fewer)
    k = max(0, min(total, round(total * share)))           # the LAST k parts go to the cloud
    parts = []
    for i in range(total):
        s0 = i * step; n = min(step, frames - s0)
        parts.append({"i": i, "start": s0, "frames": n, "where": "cloud" if i >= total - k else "local",
                      "file": f"part_{i:02d}.mp4"})
    os.makedirs(a.out, exist_ok=True)
    plan = {"src": os.path.abspath(a.src), "fps": rfps, "frames": frames, "enc": a.enc, "parts": parts, "made": time.strftime("%F %T")}
    json.dump(plan, open(os.path.join(a.out, "plan.json"), "w", encoding="utf-8"), indent=1)
    name = os.path.basename(a.src)
    print(f"split: {frames} frames @ {rfps} -> {len(parts)} parts, cloud {sum(p['where'] == 'cloud' for p in parts)} "
          f"(share {share:.0%}) plan={os.path.join(a.out, 'plan.json')}")
    print("cloud (one sandbox_exec, size xl, background:true; source uploaded to ~/in/%s):" % name)
    cl = [p for p in parts if p["where"] == "cloud"]
    if cl:
        print("  cd ~ && " + " && ".join(f"~/hfc/hfc enc ~/in/{name} ~/out/{p['file']} --start-frame {p['start']} --frames {p['frames']} {a.enc}" for p in cl))
    loc = [p for p in parts if p["where"] == "local"]
    if a.run_local and loc:
        bash = git_bash(); t = time.time()
        for p in loc:
            cmd = [bash, fwd(os.path.join(CLOUD, "enc.sh")), fwd(a.src), fwd(os.path.join(a.out, p["file"])),
                   "--start-frame", str(p["start"]), "--frames", str(p["frames"])] + a.enc.split()
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            print("  local:", (r.stdout.strip().splitlines() or ["?"])[-1])
            if r.returncode:
                sys.exit("split: local part failed\n" + r.stderr[-800:])
        print(f"split: local parts done in {time.time() - t:.1f}s")


def cmd_join(args):
    if len(args) < 2:
        sys.exit("usage: hfc.py join DIR OUT")
    d, out = args[0], args[1]
    plan = json.load(open(os.path.join(d, "plan.json"), encoding="utf-8"))
    files = [os.path.join(d, p["file"]) for p in plan["parts"]]
    miss = [f for f in files if not os.path.exists(f)]
    if miss:
        sys.exit(f"join: missing parts {miss}")
    lst = os.path.join(d, "concat.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for x in files:
            f.write("file '%s'\n" % fwd(x).replace("'", r"'\''"))
    tmp = out + ".tmp.mp4"
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                        "-i", plan["src"], "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-ar", "48000", "-shortest", "-movflags", "+faststart", tmp], capture_output=True, text=True)
    if r.returncode:
        sys.exit("join: ffmpeg failed\n" + r.stderr[-800:])
    os.replace(tmp, out)
    got, _ = probe_frames(out)
    err = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", out, "-f", "null", "-"], capture_output=True, text=True).stderr
    ok = got == plan["frames"] and not err.strip()
    print(f"join: {out} frames={got}/{plan['frames']} decode_errors={len(err.strip().splitlines())} -> {'OK' if ok else 'CHECK'}")
    sys.exit(0 if ok else 1)


# ---------------------------------------------------------------- bookkeeping
def cmd_ledger(args):
    p = os.path.join(DATA, "ledger.jsonl")
    if args and args[0] == "add" and len(args) >= 3:
        b, a = float(args[1]), float(args[2]); note = " ".join(args[3:])
        rec = {"at": time.strftime("%Y-%m-%d %H:%M"), "before": b, "after": a, "delta": round(a - b, 2), "note": note}
        os.makedirs(DATA, exist_ok=True)
        open(p, "a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False) + "\n")
        print("ledger:", rec, "<- CREDITS WERE SPENT, stop and tell the owner" if rec["delta"] < 0 else "")
    else:
        if os.path.exists(p):
            print(open(p, encoding="utf-8").read().strip())
        else:
            print("ledger: empty")


def cmd_bench(args):
    r = subprocess.run([git_bash(), fwd(os.path.join(CLOUD, "bench.sh"))], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr[-500:])


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__); return
    c, rest = sys.argv[1], sys.argv[2:]
    fn = {"pack": cmd_pack, "install-cmd": cmd_install_cmd, "set-url": cmd_set_url, "put": cmd_put, "pull": cmd_pull,
          "plan": cmd_plan, "check": cmd_check, "split": cmd_split, "join": cmd_join, "ledger": cmd_ledger,
          "bench": cmd_bench, "facts": lambda a: print(json.dumps(jload("measured.json", {}), ensure_ascii=False, indent=1))}.get(c)
    if not fn:
        sys.exit(f"hfc.py: unknown command {c}")
    fn(rest)


if __name__ == "__main__":
    main()
