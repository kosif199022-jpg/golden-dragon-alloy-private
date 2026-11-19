#!/usr/bin/env python3
"""Black Dragon v10.8 «الحارس» (care): the four things the owner kept asking about in our conversations.

    care.py play FILE... [--fix [--normalize]] [--out DIR] [--quick] [--json]   هل الفيديو هيشتغل على الآيفون/واتساب؟ ولو لأ صلّحه
    care.py status [--all] [--json]                               خلصت ولا لسه؟ الشغل الشغّال والمخلّص ومدته
    care.py last [N] [--json]                                     فين الملف؟ آخر الملفات اللي التنين طلّعها بمساراتها
    care.py resources [--json]                                    الذاكرة والهارد والمعالج: يستحمل رندر تقيل دلوقتي؟

Why each exists (from the conversation history, 2026-10-29 .. 2026-11-10):
  * play      — «الملف لا يعمل» and «اغنية شتا الرياض لا تعمل»: MP3 inside MP4 is silent on iPhone, 4:4:4 / 10-bit /
                odd sizes do not open on phones, a render killed half way leaves an MP4 without its index (moov).
  * status    — «خلصت ولا لسه» / «هل انتهيت» / «قدامك قد ايه» asked again and again during long renders.
  * last      — «فين مكان المهارة» / «اسم الملف ايه» / «مش لاقي البرنامج فين».
  * resources — background renders and installs were killed «because the system is running low on memory».
Nothing here deletes or overwrites a file: --fix always writes a new <name>_phone.mp4.
"""
import argparse, ctypes, json, os, platform, shutil, struct, subprocess, sys, time
from pathlib import Path

STATE = Path(os.environ.get("DRAGON_STATE") or (Path.home() / ".black-dragon"))
JOBS = STATE / "jobs.jsonl"
PHONE_VIDEO = {"h264"}
PHONE_AUDIO = {"aac"}
MP4_LIKE = (".mp4", ".m4v", ".mov")


# ----------------------------------------------------------------------------------------------------- helpers
def _exe(name):
    p = shutil.which(name)
    if p:
        return p
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet"
    for base in (root / "Links", root / "Packages"):
        hit = next(base.rglob(f"{name}.exe"), None) if base.exists() else None
        if hit:
            return str(hit)
    return None


def _probe(path):
    ff = _exe("ffprobe")
    if not ff:
        raise FileNotFoundError("ffprobe not found (winget install -e --id Gyan.FFmpeg)")
    r = subprocess.run([ff, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if r.returncode:
        raise ValueError(r.stderr.strip()[-400:] or "ffprobe failed")
    return json.loads(r.stdout or "{}")


def top_atoms(path, limit=64):
    """Top-level MP4 boxes in file order: [(type, offset, size)]. Pure file read, no ffmpeg."""
    out, size = [], Path(path).stat().st_size
    with open(path, "rb") as f:
        off = 0
        while off + 8 <= size and len(out) < limit:
            f.seek(off)
            head = f.read(16)
            if len(head) < 8:
                break
            n, typ = struct.unpack(">I4s", head[:8])
            if n == 1 and len(head) >= 16:
                n = struct.unpack(">Q", head[8:16])[0]
            elif n == 0:
                n = size - off
            try:
                typ = typ.decode("latin-1")
            except Exception:  # noqa: BLE001
                typ = "????"
            out.append((typ, off, n))
            if n < 8:
                break
            off += n
    return out


def _decode_errors(path, seconds=None):
    ff = _exe("ffmpeg")
    if not ff:
        return None
    args = [ff, "-hide_banner", "-v", "error", "-i", str(path)]
    if seconds:
        args += ["-t", str(seconds)]
    args += ["-map", "0:v?", "-map", "0:a?", "-f", "null", "-"]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    lines = [x for x in (r.stderr or "").splitlines() if x.strip()]
    return lines[:8] if (lines or r.returncode) else []


# ----------------------------------------------------------------------------------------------------- play
def play_check(path, quick=False):
    """Phone / WhatsApp / iPhone playability. Returns {ok, errors, warnings, fix: {video, audio, faststart}}."""
    p = Path(path)
    r = {"path": str(p), "errors": [], "warnings": [], "fix": {"video": False, "audio": False, "faststart": False}}
    if not p.is_file():
        r["errors"].append("الملف مش موجود")
        return {**r, "ok": False}
    r["bytes"] = p.stat().st_size
    if r["bytes"] == 0:
        r["errors"].append("الملف فاضي (0 بايت): الرندر ما كتبش حاجة")
        return {**r, "ok": False}
    ext = p.suffix.lower()
    if ext in MP4_LIKE:
        atoms = [a[0] for a in top_atoms(p)]
        r["atoms"] = atoms[:12]
        if "moov" not in atoms:
            r["errors"].append("مفيش فهرس moov: الملف ناقص (الرندر اتقطع أو لسه شغّال). ده مش هيتصلّح بإعادة تغليف؛ "
                               "اعمل الرندر تاني")
            return {**r, "ok": False, "fixable": False}
        if "mdat" in atoms and atoms.index("moov") > atoms.index("mdat"):
            r["warnings"].append("مش faststart: على النت وواتساب الفيديو مش هيبدأ غير بعد ما يتحمّل كله")
            r["fix"]["faststart"] = True
    try:
        j = _probe(p)
    except Exception as e:  # noqa: BLE001
        r["errors"].append(f"ffprobe مش قادر يقرا الملف: {e}")
        return {**r, "ok": False, "fixable": False}
    streams = j.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    r["duration_s"] = round(float(j.get("format", {}).get("duration") or 0), 3)
    if v:
        r["video"] = {k: v.get(k) for k in ("codec_name", "profile", "pix_fmt", "width", "height", "codec_tag_string", "r_frame_rate")}
        codec, pix, prof = v.get("codec_name"), v.get("pix_fmt") or "", (v.get("profile") or "")
        w, h = int(v.get("width") or 0), int(v.get("height") or 0)
        if codec == "hevc":
            if (v.get("codec_tag_string") or "").lower() != "hvc1":
                r["errors"].append("HEVC من غير وسم hvc1: الآيفون مش هيشغّله")
                r["fix"]["video"] = True
            else:
                r["warnings"].append("HEVC: الآيفون تمام، بس أندرويد قديم وواتساب ويب ممكن ما يشغّلوش (H.264 أضمن)")
        elif codec not in PHONE_VIDEO:
            r["errors"].append(f"كوديك الفيديو {codec}: الموبايل وواتساب محتاجين H.264")
            r["fix"]["video"] = True
        if pix not in ("yuv420p", "yuvj420p"):
            r["errors"].append(f"pix_fmt {pix}: لازم yuv420p (4:4:4 و10-bit مش بيشتغلوا على الموبايل)")
            r["fix"]["video"] = True
        if any(x in prof for x in ("4:4:4", "High 10", "4:2:2")):
            r["errors"].append(f"بروفايل {prof}: مش مدعوم على الموبايل")
            r["fix"]["video"] = True
        if w % 2 or h % 2:
            r["errors"].append(f"الأبعاد {w}x{h} فردية: H.264 على الموبايل محتاج أبعاد زوجية")
            r["fix"]["video"] = True
        if max(w, h) > 4096:
            r["warnings"].append(f"{w}x{h} أكبر من 4K: واتساب وإنستجرام هيضغطوه جامد")
    if a:
        r["audio"] = {k: a.get(k) for k in ("codec_name", "sample_rate", "channels")}
        if ext in MP4_LIKE and a.get("codec_name") not in PHONE_AUDIO:
            extra = " (ده بالظبط سبب «الأغنية مش شغالة» في شتا الرياض)" if a.get("codec_name") == "mp3" else ""
            r["errors"].append(f"الصوت {a.get('codec_name')} جوه MP4: بيطلع ساكت على الآيفون، لازم AAC{extra}")
            r["fix"]["audio"] = True
        sr = int(a.get("sample_rate") or 0)
        if sr and sr not in (44100, 48000):
            r["warnings"].append(f"تردد الصوت {sr} Hz: الأضمن 48000")
            r["fix"]["audio"] = r["fix"]["audio"] or ext in MP4_LIKE
    elif v:
        r["warnings"].append("مفيش صوت خالص في الفيديو (لو فيه أغنية أو كلام يبقى المكساج ما اتدمجش)")
    if not v and not a:
        r["errors"].append("مفيش ولا مسار فيديو ولا صوت")
    if not quick and not r["errors"]:
        errs = _decode_errors(p)
        if errs:
            r["errors"].append("فك الملف لآخره طلّع أخطاء (ملف تالف أو ناقص): " + " | ".join(errs[:3]))
            r["fixable"] = False
        elif errs is None:
            r["warnings"].append("ffmpeg مش موجود: ما اتعملش فك كامل للتأكد")
    r["ok"] = not r["errors"]
    r.setdefault("fixable", any(r["fix"].values()))
    return r


def measure_loudness(path):
    """Pass 1 of EBU R128 loudnorm: {'input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset'} or None."""
    ff = _exe("ffmpeg")
    if not ff:
        return None
    r = subprocess.run([ff, "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0", "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    txt = r.stderr or ""
    i = txt.rfind("{")
    try:
        return json.loads(txt[i:txt.rfind("}") + 1]) if i >= 0 else None
    except ValueError:
        return None


def play_fix(path, out_dir=None, normalize=False):
    """New <stem>_phone.mp4: copy what is fine, re-encode only what is not. Never touches the original.
    normalize=True also brings the audio to the owner's mix target (-14 LUFS, true peak -1.5 dBTP) with two-pass
    loudnorm (the «شتا الرياض» master was -8.7 LUFS / +0.3 dBTP)."""
    p = Path(path)
    chk = play_check(p, quick=True)
    if normalize and chk.get("audio") and "moov" in (chk.get("atoms") or ["moov"]):
        chk["fix"]["audio"] = True
        chk["fixable"] = True
    if not chk.get("fixable") or not any(chk["fix"].values()):
        return None, chk
    out = Path(out_dir or p.parent) / f"{p.stem}_phone.mp4"
    n = 2
    while out.exists():
        out = out.with_name(f"{p.stem}_phone{n}.mp4"); n += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    ff = _exe("ffmpeg")
    if not ff:
        chk["errors"].append("ffmpeg missing: cannot repair")
        return None, chk
    args = [ff, "-hide_banner", "-v", "error", "-n", "-i", str(p), "-map", "0:v:0?", "-map", "0:a:0?"]
    if chk["fix"]["video"]:
        args += ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p",
                 "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-color_primaries", "bt709", "-color_trc", "bt709",
                 "-colorspace", "bt709"]
    else:
        args += ["-c:v", "copy"]
        if (chk.get("video") or {}).get("codec_name") == "hevc":
            args += ["-tag:v", "hvc1"]
    if chk.get("audio"):
        args += ["-c:a", "aac", "-b:a", "320k", "-ar", "48000"] if chk["fix"]["audio"] else ["-c:a", "copy"]
        if normalize:
            m = measure_loudness(p)
            if m:
                chk["loudness_before"] = {"lufs": float(m["input_i"]), "true_peak": float(m["input_tp"])}
                args += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:"
                         f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
                         f"measured_thresh={m['input_thresh']}:offset={m['target_offset']},aresample=48000"]
            else:
                args += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000"]
    args += ["-movflags", "+faststart", str(out)]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if r.returncode:
        chk["errors"].append("التصليح فشل: " + (r.stderr or "")[-300:])
        return None, chk
    after = play_check(out)
    if normalize and chk.get("audio"):
        m = measure_loudness(out)
        if m:
            after["loudness_after"] = {"lufs": float(m["input_i"]), "true_peak": float(m["input_tp"])}
            after["loudness_before"] = chk.get("loudness_before")
    return out, after


def _say(r):
    head = "✅ هيشتغل على الموبايل" if r["ok"] else "❌ مش هيشتغل كويس"
    lines = [f"{head}: {r['path']}"]
    v, a = r.get("video") or {}, r.get("audio") or {}
    if v:
        lines.append(f"   فيديو {v.get('codec_name')} {v.get('width')}x{v.get('height')} {v.get('pix_fmt')}"
                     + (f" · صوت {a.get('codec_name')} {a.get('sample_rate')}Hz" if a else " · من غير صوت")
                     + (f" · {r.get('duration_s')}ث" if r.get("duration_s") else ""))
    lines += [f"   ✗ {e}" for e in r["errors"]] + [f"   ! {w}" for w in r["warnings"]]
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------------- jobs
def _alive(pid):
    if not pid:
        return False
    if platform.system() == "Windows":
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def read_jobs():
    jobs = {}
    if not JOBS.exists():
        return []
    for ln in JOBS.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        jobs.setdefault(d["id"], {}).update(d)
    out = list(jobs.values())
    for j in out:
        if "end" not in j:
            j["state"] = "running" if _alive(j.get("pid")) else "stopped"
        else:
            j["state"] = "done" if j.get("exit") == 0 else "failed"
    return sorted(out, key=lambda j: j.get("start", 0))


def _fmt_secs(s):
    s = int(s or 0)
    return f"{s // 3600}س {s % 3600 // 60}د" if s >= 3600 else (f"{s // 60}د {s % 60}ث" if s >= 60 else f"{s}ث")


STATE_AR = {"running": "⏳ شغّال", "done": "✅ خلص", "failed": "❌ فشل", "stopped": "⛔ وقف من غير ما يخلص"}


def status(show_all=False):
    jobs = read_jobs()
    now = time.time()
    running = [j for j in jobs if j["state"] == "running"]
    recent = [j for j in jobs if j["state"] != "running"][-(50 if show_all else 8):]
    return running, recent, now


def last_outputs(n=10):
    files = []
    for j in reversed(read_jobs()):
        for f in j.get("outputs", []):
            if f not in files and Path(f).exists():
                files.append(f)
        if len(files) >= n:
            break
    return files[:n]


# ----------------------------------------------------------------------------------------------------- resources
def memory():
    if platform.system() == "Windows":
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS(); m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullTotalPhys, m.ullAvailPhys
    try:
        info = dict(ln.split(":", 1) for ln in Path("/proc/meminfo").read_text().splitlines())
        kb = lambda k: int(info[k].split()[0]) * 1024
        return kb("MemTotal"), kb("MemAvailable")
    except (OSError, KeyError, ValueError):
        return 0, 0


def resources(path="."):
    total, avail = memory()
    du = shutil.disk_usage(Path(path).resolve().anchor or path)
    gb = lambda b: round(b / 2**30, 1)
    cpus = os.cpu_count() or 1
    gpu = None
    smi = shutil.which("nvidia-smi")
    if smi:
        r = subprocess.run([smi, "--query-gpu=name,memory.free,memory.total", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=8)
        gpu = r.stdout.strip() or None
    # one render/whisper worker needs roughly 1.5 GB; keep 1 GB for Windows itself
    workers = max(1, min(cpus // 2 or 1, int(max(0.0, gb(avail) - 1.0) // 1.5) or 1))
    level = "ok" if gb(avail) >= 4 else ("tight" if gb(avail) >= 1.5 else "low")
    advice = {"ok": "تمام: يستحمل رندر تقيل.",
              "tight": "الذاكرة ضيقة: شغّل حاجة تقيلة واحدة بس في المرة، واقفل كروم/البرامج الكبيرة قبل الرندر.",
              "low": "الذاكرة قليلة جدًا: الرندر أو التحميل التقيل ممكن ويندوز يقفله. اقفل برامج الأول."}[level]
    return {"ram_total_gb": gb(total), "ram_free_gb": gb(avail), "disk_free_gb": gb(du.free), "cpus": cpus,
            "gpu": gpu, "workers": workers, "level": level, "advice": advice}


# ----------------------------------------------------------------------------------------------------- CLI
def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="care", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("play"); pl.add_argument("files", nargs="+"); pl.add_argument("--fix", action="store_true")
    pl.add_argument("--out"); pl.add_argument("--quick", action="store_true"); pl.add_argument("--json", action="store_true")
    pl.add_argument("--normalize", action="store_true", help="with --fix: audio to -14 LUFS / -1.5 dBTP (two-pass)")
    st = sub.add_parser("status"); st.add_argument("--all", action="store_true"); st.add_argument("--json", action="store_true")
    la = sub.add_parser("last"); la.add_argument("n", nargs="?", type=int, default=10); la.add_argument("--json", action="store_true")
    rs = sub.add_parser("resources"); rs.add_argument("--json", action="store_true"); rs.add_argument("--path", default=".")
    a = ap.parse_args(argv)

    if a.cmd == "play":
        rows, bad = [], 0
        for f in a.files:
            r = play_check(f, quick=a.quick)
            if a.fix and (not r["ok"] or a.normalize or any(r.get("fix", {}).values())):
                out, r2 = play_fix(f, a.out, normalize=a.normalize)
                r["fixed"] = str(out) if out else None
                r["fixed_check"] = r2 if out else None
            rows.append(r)
            ok_now = r["ok"] or (r.get("fixed_check") or {}).get("ok")
            bad += 0 if ok_now else 1
        if a.json:
            print(json.dumps(rows, ensure_ascii=False, indent=1))
        else:
            for r in rows:
                print(_say(r))
                if r.get("fixed"):
                    print(f"   🔧 نسخة متصلّحة: {r['fixed']}\n" + _say(r["fixed_check"]).replace("\n", "\n   "))
                    lb, la = r["fixed_check"].get("loudness_before"), r["fixed_check"].get("loudness_after")
                    if lb and la:
                        print(f"   🔊 علو الصوت: {lb['lufs']} LUFS / ذروة {lb['true_peak']} dBTP ← "
                              f"{la['lufs']} LUFS / ذروة {la['true_peak']} dBTP")
                elif not r["ok"] and not a.fix and r.get("fixable"):
                    print("   ← شغّل نفس الأمر بـ --fix يعمل نسخة _phone.mp4 جنبه (الأصل مش هيتلمس)")
        return 1 if bad else 0
    if a.cmd == "status":
        running, recent, now = status(a.all)
        if a.json:
            print(json.dumps({"running": running, "recent": recent}, ensure_ascii=False, indent=1)); return 0
        if not running and not recent:
            print("مفيش شغل متسجّل لسه."); return 0
        print("⏳ شغّال دلوقتي:" if running else "مفيش حاجة شغّالة دلوقتي ✅")
        for j in running:
            print(f"   {' '.join(j['argv'])[:90]}  · بقاله {_fmt_secs(now - j['start'])}  · pid {j.get('pid')}")
        if recent:
            print("آخر الشغل:")
        for j in recent:
            dur = _fmt_secs((j.get("end") or now) - j["start"])
            print(f"   {STATE_AR[j['state']]}  {' '.join(j['argv'])[:80]}  · {dur}")
            for o in j.get("outputs", [])[:3]:
                print(f"      → {o}")
        return 0
    if a.cmd == "last":
        files = last_outputs(a.n)
        if a.json:
            print(json.dumps(files, ensure_ascii=False, indent=1)); return 0
        if not files:
            print("لسه مفيش ملفات متسجّلة من التنين (بتتسجّل من v10.8 وطالع).")
        for i, f in enumerate(files, 1):
            print(f"{i}. {f}")
        return 0
    if a.cmd == "resources":
        r = resources(a.path)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=1)); return 0
        print(f"الذاكرة: فاضي {r['ram_free_gb']} من {r['ram_total_gb']} GB · الهارد فاضي {r['disk_free_gb']} GB · "
              f"{r['cpus']} أنوية" + (f" · GPU {r['gpu']}" if r["gpu"] else ""))
        print(f"عدد الشغّالين المناسب دلوقتي: {r['workers']}\n{r['advice']}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
