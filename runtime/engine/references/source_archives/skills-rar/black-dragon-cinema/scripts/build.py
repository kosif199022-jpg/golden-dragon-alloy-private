"""Build one Mayar film from films/<name>.json:
1) extract every footage shot as graded 1080x1920 frames, 2) write films/<name>/index.html with the spec,
3) render with kosif-tool render_html (seek driver), 4) cut + master the song (and any voice), 5) mux to MP4.

usage: python build.py <name> [--stills 1,5,9] [--preview] [--skip-extract]
"""
import json, os, subprocess, sys, shutil
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

MONTAGE = Path(r"C:\Users\cinde\OneDrive\Desktop\المونتاج")
# Work dir must be OUTSIDE OneDrive (frames are gigabytes) and ASCII-only (ffmpeg filter paths, file:// URLs).
B = Path(os.environ.get("BDC_WORK", r"C:\Users\cinde\bdc_work"))
REFS = Path(os.environ.get("BDC_REFS", str(MONTAGE / "01_raw" / "refs")))        # source clips, matched by id substring
AUDIO = Path(os.environ.get("BDC_AUDIO", str(MONTAGE / "02_music")))            # songs (wav) named in spec.audio.song
DELIVER = Path(os.environ.get("BDC_DELIVER", str(MONTAGE / "05_output")))       # final MP4s land here
KIT = Path(os.environ.get("BDC_KIT", str(MONTAGE / "_kit")))
KOSIF = Path(os.environ.get("KOSIF_ROOT", r"C:\Users\cinde\kosif-tool"))      # has tools/render_html.cjs + node_modules
HERE = Path(__file__).resolve().parent


def setup_work():
    """First run: copy the engine, the kit's LUTs and the Arabic/Latin fonts into the ASCII work dir."""
    for d in ("films", "shots", "out", "luts", "fonts"):
        (B / d).mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "engine.js", B / "engine.js")   # always refresh the engine
    for cube in (KIT / "LUTs").glob("*.cube"):
        if not (B / "luts" / cube.name).exists():
            shutil.copy2(cube, B / "luts" / cube.name)
    want = {"ArefRuqaa-Bold.ttf", "Cairo-900.ttf", "Cairo-700.ttf", "Amiri-Bold.ttf", "ElMessiri-700.ttf",
            "Tajawal-Black.ttf", "ReemKufi-700.ttf", "InstrumentSerif-Italic.ttf"}
    for ttf in (KIT / "Fonts").rglob("*.ttf"):
        if ttf.name in want and not (B / "fonts" / ttf.name).exists():
            shutil.copy2(ttf, B / "fonts" / ttf.name)


def run(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode:
        sys.exit(f"FAILED: {' '.join(map(str, cmd))[:300]}")
    return r


def src_of(cid):
    return next(REFS.glob(f"*{cid}*.mp4"))


def extract(name, i, shot):
    out = B / "shots" / f"{name}_{i:02d}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    c = shot.get("crop", {})
    z, cx, cy = c.get("z", 1.0), c.get("cx", 0.5), c.get("cy", 0.5)
    lut = (B / "luts" / f"{shot.get('lut', '01_Cinematic')}.cube").as_posix().replace(":", "\\:")
    grade = shot.get("grade", "eq=contrast=1.06:saturation=1.05")
    need = shot["d"] * shot.get("speed", 1) + 0.4
    pre = ""
    if shot.get("delogo"):  # remove channel logos / burned-in subtitles, rects in source fractions [x, y, w, h]
        iw, ih = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                          "stream=width,height", "-of", "csv=p=0", str(src_of(shot["src"]))],
                                         capture_output=True, text=True).stdout.strip().split(",")[:2])
        for x, y, w, h in shot["delogo"]:
            X, Y = max(1, int(x * iw)), max(1, int(y * ih))
            Wd, Hd = min(int(w * iw), iw - X - 1), min(int(h * ih), ih - Y - 1)
            pre += f"delogo=x={X}:y={Y}:w={Wd}:h={Hd},"
    vf = pre + (f"crop=w='min(iw,ih*9/16)/{z}':h='min(iw,ih*9/16)/{z}*16/9':"
          f"x='(iw-min(iw,ih*9/16)/{z})*{cx}':y='(ih-min(iw,ih*9/16)/{z}*16/9)*{cy}',"
          f"scale=1080:1920:flags=lanczos,unsharp=5:5:0.5,lut3d=file='{lut}':interp=tetrahedral,{grade},fps=30")
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(shot["in"]), "-i", str(src_of(shot["src"])), "-t", f"{need:.3f}",
         "-vf", vf, "-q:v", "2", str(out / "%05d.jpg")])
    return out, len(list(out.glob("*.jpg")))


def audio(name, spec, dur):
    a = spec["audio"]
    out = B / "out" / f"{name}_mix.wav"
    inputs, filt, labels = [], [], []
    song = AUDIO / a["song"]
    inputs += ["-ss", str(a["start"]), "-t", f"{dur + 0.5:.3f}", "-i", str(song)]
    delay = int(a.get("songAt", 0) * 1000)
    fo_start = dur - a.get("fadeOut", 2.5)
    filt.append(f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={a.get('songGain', 1.0)},"
                f"afade=t=in:d={a.get('fadeIn', 0.4)},afade=t=out:st={fo_start - a.get('songAt', 0):.3f}:d={a.get('fadeOut', 2.5)},"
                f"adelay={delay}|{delay}[song]")
    labels.append("[song]")
    for k, v in enumerate(a.get("voices", []), start=1):
        inputs += ["-ss", str(v["in"]), "-t", str(v["d"]), "-i", str(src_of(v["src"]))]
        dl = int(v["at"] * 1000)
        filt.append(f"[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={v.get('gain', 1.0)},"
                    f"afade=t=in:d=0.15,afade=t=out:st={v['d'] - 0.4:.3f}:d=0.4,adelay={dl}|{dl}[v{k}]")
        labels.append(f"[v{k}]")
    tail = f"atrim=0:{dur:.3f},loudnorm=I=-14:TP=-1.0:LRA=11[out]"
    if len(labels) > 1:
        # her voice leads: the song ducks under it (sidechain), then both are mixed
        vox = labels[1:]
        filt.append(f"{''.join(vox)}amix=inputs={len(vox)}:normalize=0:duration=longest,apad=whole_dur={dur:.3f},asplit[vox][voxsc]")
        filt.append("[song][voxsc]sidechaincompress=threshold=0.015:ratio=10:attack=15:release=450:makeup=1[songd]")
        filt.append(f"[songd][vox]amix=inputs=2:normalize=0:duration=longest,{tail}")
    else:
        filt.append(f"[song]{tail}")
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]",
         "-ar", "48000", "-c:a", "pcm_s24le", str(out)])
    return out


def main():
    name = sys.argv[1]
    args = sys.argv[2:]
    setup_work()
    spec_path = B / "films" / f"{name}.json"
    if not spec_path.exists():
        sys.exit(f"write the film spec first: {spec_path} (start from templates/*.json)")
    spec = json.load(open(spec_path, encoding="utf-8"))
    dur = spec["duration"]
    # shot start times: each shot starts where the previous ended
    t = 0.0
    for i, s in enumerate(spec["shots"]):
        s["t"] = round(t, 3); t += s["d"]
        if s.get("type", "clip") == "clip":
            s["type"] = "clip"
            if "--skip-extract" in args and (B / "shots" / f"{name}_{i:02d}").exists():
                d = B / "shots" / f"{name}_{i:02d}"; n = len(list(d.glob("*.jpg")))
            else:
                d, n = extract(name, i, s)
            s["dir"] = f"../../shots/{name}_{i:02d}"; s["frames"] = n
            print(f"shot {i:02d} {s['src']} @{s['in']}s {s['d']}s -> {n} frames", flush=True)
    if abs(t - dur) > 0.05:
        print(f"note: shots add up to {t:.2f}s, duration is {dur}s", flush=True)
    page = B / "films" / name
    page.mkdir(parents=True, exist_ok=True)
    fonts_js = B / "fonts.js"
    if not fonts_js.exists():
        import base64
        data = {f.name: base64.b64encode(f.read_bytes()).decode() for f in (B / "fonts").glob("*.ttf")}
        fonts_js.write_text("window.FONTDATA=" + json.dumps(data) + ";", encoding="utf-8")
    (page / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:#000}canvas{display:block}</style>"
        "<canvas id=c width=1080 height=1920></canvas>"
        f"<script>window.SPEC={json.dumps(spec, ensure_ascii=False)};</script>"
        "<script src=../../fonts.js></script><script src=../../engine.js></script>",
        encoding="utf-8")
    render = ["node", str(KOSIF / "tools" / "render_html.cjs"), "--in", str(page / "index.html"),
              "--width", "1080", "--height", "1920", "--fps", "30", "--mode", "seek", "--duration", str(dur)]
    if "--stills" in args:
        times = args[args.index("--stills") + 1]
        run(render + ["--out", str(B / "out" / f"{name}_stills.mp4"), "--stills", times,
                      "--stills-dir", str(B / "out" / f"{name}_stills")], cwd=KOSIF)
        return
    mix = audio(name, spec, dur)
    silent = B / "out" / f"{name}_video.mp4"
    extra = ["--preview"] if "--preview" in args else []
    if "--remux" not in args:  # --remux: keep the rendered picture, rebuild only the audio and the final mux
        run(render + ["--out", str(silent)] + extra, cwd=KOSIF)
    final = DELIVER / f"{spec['title']}.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(mix), "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", str(final)])
    print("DONE", final, flush=True)


if __name__ == "__main__":
    main()
