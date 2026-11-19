#!/usr/bin/env python3
"""qc.py FILE [--w W --h H] [--fps F] [--dur SEC] [--dur-tol 0.10] [--lufs -14 --lufs-tol 1.5] [--tp -1.0]
             [--no-audio] [--max-mbps 25] [--black-ok 0.5] [--json]
Delivery gate for any MP4/MOV (any size, not only 9:16). Independent of whatever produced the file.
Checks: decodes with zero errors, video stream, even dimensions, yuv420p, faststart (moov before mdat),
expected size/fps/duration/frame count, black stretches inside (ignores the first/last --black-ok seconds),
audio present + integrated loudness/true peak, average bitrate. Exit 0 PASS, 1 FAIL, 2 cannot check.
Runs the same on the sandbox and on Windows (needs ffmpeg/ffprobe on PATH).
"""
import argparse, json, os, re, struct, subprocess, sys


def probe(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", f],
                       capture_output=True, text=True)
    return json.loads(r.stdout or "{}")


def moov_first(f):
    try:
        with open(f, "rb") as fh:
            pos, size_all = 0, os.path.getsize(f)
            while pos < size_all:
                fh.seek(pos); hdr = fh.read(16)
                if len(hdr) < 8: return None
                sz, typ = struct.unpack(">I4s", hdr[:8])
                if sz == 1: sz = struct.unpack(">Q", hdr[8:16])[0]
                if typ == b"moov": return True
                if typ == b"mdat": return False
                if sz < 8: return None
                pos += sz
    except OSError:
        return None
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file"); ap.add_argument("--w", type=int); ap.add_argument("--h", type=int)
    ap.add_argument("--fps", type=float); ap.add_argument("--dur", type=float); ap.add_argument("--dur-tol", type=float, default=0.10)
    ap.add_argument("--lufs", type=float); ap.add_argument("--lufs-tol", type=float, default=1.5)
    ap.add_argument("--tp", type=float, default=-1.0); ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--max-mbps", type=float, default=25.0); ap.add_argument("--black-ok", type=float, default=0.5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not os.path.isfile(a.file):
        print(f"qc: no file {a.file}"); sys.exit(2)
    p = probe(a.file)
    vs = [s for s in p.get("streams", []) if s.get("codec_type") == "video"]
    au = [s for s in p.get("streams", []) if s.get("codec_type") == "audio"]
    res, fails, warns = {}, [], []
    if not vs:
        print("qc: FAIL no video stream"); sys.exit(1)
    v = vs[0]; w, h = v.get("width"), v.get("height")
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1").split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    dur = float(p.get("format", {}).get("duration") or v.get("duration") or 0)
    size = os.path.getsize(a.file); mbps = size * 8 / dur / 1e6 if dur else 0
    res.update(file=a.file, w=w, h=h, codec=v.get("codec_name"), pix_fmt=v.get("pix_fmt"), fps=round(fps, 3),
               duration=round(dur, 3), mbps=round(mbps, 2), mb=round(size / 1048576, 1), audio=bool(au))

    # one decode pass: errors + black + loudness
    vf = "blackdetect=d=0.1:pix_th=0.10"
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "level+info", "-i", a.file]
    if au and not a.no_audio:
        cmd += ["-filter_complex", f"[0:v:0]{vf}[v];[0:a:0]ebur128=peak=true[a]", "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v:0", "-vf", vf]
    cmd += ["-f", "null", "-"]
    err = subprocess.run(cmd, capture_output=True, text=True, errors="replace").stderr
    dec_err = [l for l in err.splitlines() if "[error]" in l or "[fatal]" in l]
    frames = None
    m = re.findall(r"frame=\s*(\d+)", err)
    if m: frames = int(m[-1])
    blacks = [(float(s), float(e)) for s, e in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)]
    inner = [(s, e) for s, e in blacks if s > a.black_ok and e < dur - a.black_ok]
    I = re.findall(r"I:\s+(-?[\d.]+|-inf) LUFS", err); TP = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", err)
    res.update(frames=frames, decode_errors=len(dec_err), black_inside=inner,
               lufs=float(I[-1]) if I and I[-1] != "-inf" else None, true_peak=float(TP[-1]) if TP and TP[-1] != "-inf" else None,
               faststart=moov_first(a.file) if a.file.lower().endswith((".mp4", ".mov", ".m4v")) else None)

    if dec_err: fails.append(f"decode errors: {len(dec_err)} (first: {dec_err[0][-120:]})")
    if w % 2 or h % 2: fails.append(f"odd dimensions {w}x{h}")
    if v.get("pix_fmt") not in ("yuv420p", "yuvj420p"): warns.append(f"pix_fmt {v.get('pix_fmt')} (phones/socials want yuv420p)")
    if res["faststart"] is False: fails.append("moov atom at the end (add -movflags +faststart)")
    if a.w and a.h and (w, h) != (a.w, a.h): fails.append(f"size {w}x{h} != {a.w}x{a.h}")
    if a.fps and abs(fps - a.fps) > 0.01: fails.append(f"fps {fps:.3f} != {a.fps}")
    if a.dur is not None and abs(dur - a.dur) > a.dur_tol: fails.append(f"duration {dur:.3f}s != {a.dur}s ±{a.dur_tol}")
    if a.dur is not None and a.fps and frames is not None and frames != round(a.dur * a.fps):
        fails.append(f"frames {frames} != {round(a.dur * a.fps)}")
    if inner: fails.append(f"black inside: {inner[:3]}")
    if not a.no_audio:
        if not au: fails.append("no audio stream (use --no-audio if intended)")
        else:
            if a.lufs is not None and (res["lufs"] is None or abs(res["lufs"] - a.lufs) > a.lufs_tol):
                fails.append(f"loudness {res['lufs']} LUFS != {a.lufs} ±{a.lufs_tol}")
            if res["true_peak"] is not None and res["true_peak"] > a.tp:
                fails.append(f"true peak {res['true_peak']} dBFS > {a.tp} (audio-only pass with -c:v copy)")
    if mbps > a.max_mbps: warns.append(f"{mbps:.1f} Mbps average (> {a.max_mbps}); socials re-compress heavy files")
    res.update(passed=not fails, fails=fails, warns=warns)
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"QC {a.file}: {w}x{h} {res['codec']}/{res['pix_fmt']} {fps:.3f}fps {dur:.3f}s frames={frames} "
              f"audio={'yes' if au else 'no'} I={res['lufs']} TP={res['true_peak']} {res['mb']}MB {mbps:.1f}Mbps "
              f"faststart={res['faststart']} decode_err={len(dec_err)} black_inside={len(inner)}")
        for x in fails: print("  FAIL", x)
        for x in warns: print("  WARN", x)
        print("PASS" if not fails else "FAIL")
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
