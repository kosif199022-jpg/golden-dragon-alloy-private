#!/usr/bin/env python3
"""Dragon Genius delivery gate: measure a rendered video before calling it done.

Checks (each PASS / FAIL / WARN / SKIP, with the measured value):
  streams     video present; audio present unless --no-audio
  codec       h264 video, aac audio (WARN otherwise)
  pix_fmt     yuv420p (FAIL otherwise: many players/socials break)
  even_dims   width and height even
  aspect      matches --aspect within 1% (if given)
  fps         constant frame rate (r_frame_rate == avg_frame_rate, WARN)
  duration    matches --expect within --dur-tol seconds (if given)
  av_sync     audio not longer than video (last words over black/cut)
  faststart   moov atom before mdat (MP4/MOV only)
  black       blackdetect: black at start/end or long black mid-file
  freeze      freezedetect: frozen picture >= 2 s (WARN)
  loudness    integrated LUFS within --lufs +/- --lufs-tol, true peak <= --tp
  silence     audio silence >= 3 s (WARN)

Exit code: 0 all pass (warnings allowed), 1 at least one FAIL, 2 bad input/tools.
Sources of the rules: FFmpeg docs (loudnorm, blackdetect), MoneyPrinterTurbo
(+0.1 s video over audio), OpenMontage ffmpeg skill (yuv420p, even dims,
faststart). Untrusted media is only read, never executed.
"""
import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys


def run(cmd, timeout=900):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def frac(s):
    try:
        if "/" in s:
            a, b = s.split("/")
            return float(a) / float(b) if float(b) else 0.0
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def mp4_faststart(path):
    """Return True if moov precedes mdat, False if after, None if not found."""
    try:
        with open(path, "rb") as f:
            size_total = os.path.getsize(path)
            pos = 0
            while pos < size_total:
                f.seek(pos)
                hdr = f.read(8)
                if len(hdr) < 8:
                    return None
                size, typ = struct.unpack(">I4s", hdr)
                if size == 1:
                    size = struct.unpack(">Q", f.read(8))[0]
                elif size == 0:
                    size = size_total - pos
                if typ == b"moov":
                    return True
                if typ == b"mdat":
                    return False
                if size < 8:
                    return None
                pos += size
    except OSError:
        return None
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--aspect", help="e.g. 9:16, 16:9, 1:1")
    ap.add_argument("--expect", type=float, help="expected duration in seconds")
    ap.add_argument("--dur-tol", type=float, default=0.15)
    ap.add_argument("--lufs", type=float, default=-14.0)
    ap.add_argument("--lufs-tol", type=float, default=1.5)
    ap.add_argument("--tp", type=float, default=-1.0, help="max true peak dBTP")
    ap.add_argument("--no-audio", action="store_true", help="silent video is expected")
    ap.add_argument("--black-th", type=float, default=0.10, help="blackdetect pix_th")
    ap.add_argument("--quick", action="store_true", help="skip black/freeze/loudness scans")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not os.path.isfile(a.file):
        print(f"ERROR: file not found: {a.file}", file=sys.stderr)
        return 2
    for t in ("ffprobe", "ffmpeg"):
        if not shutil.which(t):
            print(f"ERROR: {t} not on PATH", file=sys.stderr)
            return 2

    res = []

    def add(name, status, value, note=""):
        res.append({"check": name, "status": status, "value": value, "note": note})

    rc, out, err = run(["ffprobe", "-v", "error", "-print_format", "json",
                        "-show_format", "-show_streams", a.file])
    if rc != 0:
        print(f"ERROR: ffprobe failed: {err.strip()[:300]}", file=sys.stderr)
        return 2
    info = json.loads(out)
    vs = [s for s in info.get("streams", []) if s.get("codec_type") == "video"
          and not s.get("disposition", {}).get("attached_pic")]
    as_ = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    fmt_dur = frac(info.get("format", {}).get("duration", "0"))

    # streams
    if not vs:
        add("streams", "FAIL", "no video stream")
    elif not as_ and not a.no_audio:
        add("streams", "FAIL", "video only, no audio", "use --no-audio if intended")
    else:
        add("streams", "PASS", f"{len(vs)} video, {len(as_)} audio")
    if not vs:
        return report(res, a)
    v = vs[0]
    w, h = int(v.get("width", 0)), int(v.get("height", 0))

    # codec
    vc = v.get("codec_name")
    ac = as_[0].get("codec_name") if as_ else None
    ok = vc == "h264" and (ac in (None, "aac"))
    add("codec", "PASS" if ok else "WARN", f"video={vc} audio={ac}",
        "" if ok else "h264+aac is the safest for socials")

    # pix_fmt
    pf = v.get("pix_fmt")
    add("pix_fmt", "PASS" if pf == "yuv420p" else "FAIL", pf,
        "" if pf == "yuv420p" else "add -pix_fmt yuv420p")

    # even dims
    add("even_dims", "PASS" if w % 2 == 0 and h % 2 == 0 else "FAIL", f"{w}x{h}",
        "" if w % 2 == 0 and h % 2 == 0 else "scale=trunc(iw/2)*2:trunc(ih/2)*2")

    # aspect
    if a.aspect:
        try:
            aw, ah = (float(x) for x in a.aspect.split(":"))
            sar = frac(v.get("sample_aspect_ratio", "1:1").replace(":", "/")) or 1.0
            real = (w * sar) / h if h else 0
            want = aw / ah
            okk = abs(real - want) / want <= 0.01
            add("aspect", "PASS" if okk else "FAIL", f"{real:.4f} (want {want:.4f})")
        except ValueError:
            add("aspect", "SKIP", a.aspect, "bad --aspect format")

    # fps constant
    rfr, afr = frac(v.get("r_frame_rate", "0")), frac(v.get("avg_frame_rate", "0"))
    cfr = rfr > 0 and afr > 0 and abs(rfr - afr) / rfr < 0.01
    add("fps", "PASS" if cfr else "WARN", f"r={rfr:.3f} avg={afr:.3f}",
        "" if cfr else "variable frame rate: convert to CFR before Remotion/HyperFrames/editing")

    # durations
    vdur = frac(v.get("duration", "0")) or fmt_dur
    adur = frac(as_[0].get("duration", "0")) if as_ else 0.0
    if a.expect is not None:
        d = abs(fmt_dur - a.expect)
        add("duration", "PASS" if d <= a.dur_tol else "FAIL",
            f"{fmt_dur:.3f}s (want {a.expect:.3f}±{a.dur_tol})")
    else:
        add("duration", "PASS", f"{fmt_dur:.3f}s")
    if as_:
        gap = adur - vdur
        if gap > 0.05:
            add("av_sync", "FAIL", f"audio {adur:.3f}s > video {vdur:.3f}s",
                "pad video (+0.1s) then trim: last words would play over black/cut")
        elif gap < -1.0:
            add("av_sync", "WARN", f"video {vdur:.3f}s, audio {adur:.3f}s",
                "audio ends >1s before picture")
        else:
            add("av_sync", "PASS", f"video {vdur:.3f}s / audio {adur:.3f}s")

    # faststart
    if os.path.splitext(a.file)[1].lower() in (".mp4", ".mov", ".m4v"):
        fs = mp4_faststart(a.file)
        add("faststart", {True: "PASS", False: "WARN", None: "SKIP"}[fs],
            {True: "moov first", False: "moov after mdat", None: "unknown"}[fs],
            "" if fs else "-movflags +faststart for web/social upload")

    if not a.quick:
        # black + freeze in one decode pass
        rc, _, err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.file, "-an",
                          "-vf", f"blackdetect=d=0.05:pix_th={a.black_th},freezedetect=n=0.003:d=2",
                          "-f", "null", "-"])
        blacks = [(float(s), float(e)) for s, e in
                  re.findall(r"black_start:([\d.]+)\s+black_end:([\d.]+)", err)]
        bad = []
        for s, e in blacks:
            if s <= 0.05:
                bad.append(f"start {s:.2f}-{e:.2f}")
            elif e >= fmt_dur - 0.1:
                bad.append(f"end {s:.2f}-{e:.2f}")
            elif e - s >= 0.5:
                bad.append(f"mid {s:.2f}-{e:.2f}")
        if bad:
            add("black", "FAIL", "; ".join(bad[:6]),
                "black at start = viewers scroll away; intentional fade? accept consciously")
        else:
            add("black", "PASS", f"{len(blacks)} short black spans" if blacks else "none")
        freezes = re.findall(r"freeze_start:\s*([\d.]+)", err)
        freeze_d = re.findall(r"freeze_duration:\s*([\d.]+)", err)
        if freezes:
            add("freeze", "WARN", ", ".join(f"{float(s):.2f}s({float(d):.1f}s)"
                                            for s, d in zip(freezes, freeze_d)),
                "frozen picture >=2s: intended hold?")
        else:
            add("freeze", "PASS", "none")

        if as_:
            rc, _, err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.file, "-vn",
                              "-af", "silencedetect=n=-50dB:d=3,loudnorm=print_format=json",
                              "-f", "null", "-"])
            m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
            if m:
                ln = json.loads(m.group(0))
                I, TP = float(ln["input_i"]), float(ln["input_tp"])
                lra = float(ln["input_lra"])
                st = "PASS"
                notes = []
                if abs(I - a.lufs) > a.lufs_tol:
                    st = "FAIL"
                    notes.append(f"two-pass loudnorm I={a.lufs}:TP={a.tp}:linear=true")
                if TP > a.tp + 0.05:
                    st = "FAIL"
                    notes.append("true peak too high")
                add("loudness", st, f"I={I:.1f} LUFS, TP={TP:.1f} dBTP, LRA={lra:.1f}",
                    "; ".join(notes))
            else:
                add("loudness", "SKIP", "could not parse loudnorm output")
            sil = re.findall(r"silence_start:\s*([\d.]+)", err)
            if sil:
                add("silence", "WARN", ", ".join(f"{float(s):.1f}s" for s in sil[:6]),
                    "silence >=3s: dropout or intended?")
            else:
                add("silence", "PASS", "none >=3s")

    return report(res, a)


def report(res, a):
    fails = [r for r in res if r["status"] == "FAIL"]
    verdict = "FAIL" if fails else "PASS"
    if a.json:
        print(json.dumps({"file": a.file, "verdict": verdict, "checks": res},
                         ensure_ascii=False, indent=1))
    else:
        print(f"media_gate: {os.path.basename(a.file)}")
        for r in res:
            line = f"  [{r['status']:<4}] {r['check']:<10} {r['value']}"
            if r["note"]:
                line += f"  -> {r['note']}"
            print(line)
        print(f"VERDICT: {verdict}" + (f" ({len(fails)} fail)" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
