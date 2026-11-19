"""Render the reel straight from the EDL: numpy composites every frame, libass draws the type, ffmpeg encodes.
Full renders split the frames over worker processes; stills render single moments plus a contact sheet."""
import json, math, multiprocessing as mp, os, re, subprocess, tempfile, time, zlib
from pathlib import Path

import numpy as np

from ..deliver import fit_audio
from ..media import ascii_path, exe, ffmpeg
from . import text as tx
from .compose import Renderer, bar_box, over
from .edl import build_plan
from .project import CFG, DATA, info


# ------------------------------------------------------------------------------------------------ texts
def insert_texts(I, w, h, accent):
    """Texts that live inside an insert (band words, UI labels, counters), in the insert's own time."""
    vis, kind, out = I["vis"], I["kind"], []
    label = lambda text, x, y, size, color="#FFFFFF", t0=0.0, **kw: out.append(
        dict(font="sub", text=text, x=x, y=y, size=size, color=color, anim="pop", t0=t0, t1=vis, **kw))
    if kind == "band":
        for ct in I.get("cut_txt") or []:
            out.append(dict(font=ct.get("font", "anton"), text=ct["text"], x=ct["x"], y=ct["y"], size=ct["size"], color=ct.get("color", "#FFFFFF"),
                            anim="build", glow=(ct.get("color", "") or "").upper() == accent.upper(), t0=(ct.get("t0") or 0) + 0.2, t1=vis,
                            front=bool(ct.get("front"))))
    elif kind == "cards":
        cs = I.get("cards") or []
        cw = w * 0.84 / max(len(cs), 1)
        chh, cyy = cw * 1.4, h * 0.55
        if I.get("title"):
            label(I["title"], w / 2, h * 0.12, 30, t0=0.05)
        for a, cd in enumerate(cs):
            at, xa = cd.get("t") or 0, w * 0.08 + cw * (a + 0.5)
            if cd.get("name"):
                out.append(dict(font="anton", text=cd["name"].upper(), x=xa, y=cyy + chh * 0.24, size=round(cw * 0.2), color="#FFFFFF",
                                anim="build", t0=at + 0.05, t1=vis))
            if cd.get("caption"):
                label(cd["caption"], xa, cyy + chh * 0.39, round(cw * 0.085), accent, at + 0.2)
    elif kind == "bar":
        E, d0, d1 = bar_box(I)
        vf, vt, suf = I.get("from", 100), I.get("to", 0), I.get("suffix", "%")
        label(I.get("label") or "ENERGY", E["bx"] + 70, E["by"] - 44, 36, t0=0)
        label("%d%s" % (vf, suf), E["bx"] + E["bw"] - 60, E["by"] - 44, 36, t0=0, counter=(d0, d1, vf, vt, suf))
    elif kind == "number":
        ny = I.get("y") or h * 0.5
        c0, c1 = I.get("count") or [0.1, 0.5]
        nf, nt, ns = I.get("from", 0), I.get("to", 100), I.get("suffix", "")
        if I.get("label"):
            label(I["label"], w / 2, ny - 110, 34, t0=0.04)
        out.append(dict(font="anton", text="%d%s" % (nt, ns), x=w / 2, y=ny + 5, size=150, color="#FFFFFF", anim="pop", t0=0.06, t1=vis,
                        counter=(c0, c1, nf, nt, ns)))
        if I.get("status"):
            label(I["status"], w / 2, ny + 110, 34, accent, c1)
    return out


def expand_counters(ts, fps):
    """A counter becomes one single-frame text per frame with the current number."""
    out = []
    for T in ts:
        if not T.get("counter"):
            out.append(T)
            continue
        a0, a1, v0, v1, suf = T["counter"]
        for k in range(int(T["t0"] * fps), int(math.ceil(T["t1"] * fps))):
            tt = k / fps
            out.append(dict(T, text="%d%s" % (round(tx.ramp(tt, a0, a1, v0, v1)), suf), t0=tt, t1=tt + 1.0 / fps,
                            anim="pop" if tt < T["t0"] + 0.08 else "none", fadeout=False, _offset=T["_offset"]))
    return out


class InsertText:
    """Pre-renders an insert's texts once: per frame (x0, y0, rgba crop) or None, split into back/front groups."""

    def __init__(self, plan, F, cache):
        self.p, self.F, self.cache, self.done = plan, F, cache, {}

    def __call__(self, I, w, h):
        if I["id"] in self.done:
            return self.done[I["id"]]
        texts, fps, res = insert_texts(I, w, h, self.p["accent"]), self.p["fps"], {"back": [], "front": []}
        for grp in ("back", "front"):
            ts = [T for T in texts if bool(T.get("front")) == (grp == "front")]
            if not ts:
                continue
            for T in ts:
                T.setdefault("_uid", zlib.crc32(("%s|%s" % (I["id"], T["text"])).encode()) % 100000)
            tag = "%s_%s_%d" % (I["id"], grp, os.getpid())
            tx.measure(ts, self.p["fonts"], self.F, self.cache, fps, tag=tag)
            ap = os.path.join(self.cache, "ins_%s.ass" % tag)
            tx.write_ass(ap, expand_counters(ts, fps), w, h, fps, self.p["fonts"], self.F, 0.0, I["dur"])
            nfr = int(math.ceil(I["dur"] * fps))
            proc = tx.render_stream(ap, self.F.dir, w, h, fps, nfr)
            for _ in range(nfr):
                buf = proc.stdout.read(w * h * 4)
                if len(buf) < w * h * 4:
                    break
                a = np.frombuffer(buf, np.uint8).reshape(h, w, 4)
                ys = np.nonzero(a[:, :, 3].max(axis=1))[0]
                if not len(ys):
                    res[grp].append(None)
                    continue
                xs = np.nonzero(a[:, :, 3].max(axis=0))[0]
                res[grp].append((int(xs[0]), int(ys[0]), a[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1].astype(np.float32) / 255.0))
            proc.wait()
        self.done[I["id"]] = res
        return res


def text_groups(plan):
    """(name, texts) with stable animation seeds: front texts 0.., behind-the-head texts 5000.."""
    out = []
    for name, behind, base in (("front", False, 0), ("behind", True, 5000)):
        ts = [T for T in plan["text"] if bool(T.get("behind")) == behind]
        for i, T in enumerate(ts):
            T["_uid"] = base + i
        if ts:
            out.append((name, ts))
    return out


def prepare_text(plan, cache):
    """Measure every text; shrink lines wider than max_w and measure again. Returns notes."""
    F, notes = tx.Fonts(cache), []
    missing = [f for f in plan["fonts"].values() if f not in F.factor]
    if missing:
        notes.append("fonts not found for libass: " + ", ".join(missing))
    for name, ts in text_groups(plan):
        tx.measure(ts, plan["fonts"], F, cache, plan["fps"], tag=name)
        wide = [T for T in ts if T.get("fit", True) and T.get("_inkw", 0) > T.get("max_w", 0.89 * plan["W"])]
        for T in wide:
            T["size"] = int(T["size"] * T.get("max_w", 0.89 * plan["W"]) / T["_inkw"])
            notes.append('"%s" shrunk to size %d to fit the frame' % (T["text"].replace("\n", " ")[:30], T["size"]))
        if wide:
            tx.measure(wide, plan["fonts"], F, cache, plan["fps"], tag=name + "_fit")
    return notes


# ------------------------------------------------------------------------------------------------ workers
def work(args):
    """Render frames f0..f1 into an MP4 segment ('range'), or a list of frames into PNGs ('stills')."""
    plan_path, cache, frames, seg, mode, out_dir = args
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    F, R = tx.Fonts(cache), Renderer(plan)
    R.text_frames = InsertText(plan, F, cache)
    fps, W, H = plan["fps"], plan["W"], plan["H"]
    groups = text_groups(plan)

    def layers(t_from, t_to, n, tag):
        procs = {}
        for name, ts in groups:
            ap = os.path.join(cache, "%s_%s.ass" % (name, tag))
            tx.write_ass(ap, ts, W, H, fps, plan["fonts"], F, t_from, t_to)
            procs[name] = tx.render_stream(ap, F.dir, W, H, fps, n)
        return procs

    def rgba(proc):
        buf = proc.stdout.read(W * H * 4)
        return np.frombuffer(buf, np.uint8).reshape(H, W, 4).astype(np.float32) / 255.0 if len(buf) == W * H * 4 else None

    raw = ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H)]
    if mode == "range":
        f0, f1 = frames
        procs = layers(f0 / fps, f1 / fps, f1 - f0, "r%d" % f0)
        e = CFG["encode"]
        enc = subprocess.Popen([exe("ffmpeg"), "-v", "error", "-y", *raw, "-r", str(fps), "-i", "-", "-c:v", e["vcodec"], "-preset", e["preset"],
                                "-crf", str(e["crf"]), "-pix_fmt", e["pix_fmt"], "-color_primaries", e["color"], "-color_trc", e["color"],
                                "-colorspace", e["color"], seg], stdin=subprocess.PIPE)
        for k in range(f0, f1):
            lay = {name: rgba(pr) for name, pr in procs.items()}
            enc.stdin.write((R.frame(k / fps, lay.get("front"), lay.get("behind")) * 255 + 0.5).astype(np.uint8).tobytes())
        enc.stdin.close()
        enc.wait()
        for pr in procs.values():
            pr.wait()
    else:
        for k in frames:
            t = k / fps
            procs = layers(t, t + 1.0 / fps, 1, "s%d" % k)
            lay = {name: rgba(pr) for name, pr in procs.items()}
            for pr in procs.values():
                pr.wait()
            img = R.frame(t, lay.get("front"), lay.get("behind"))
            subprocess.run([exe("ffmpeg"), "-v", "error", "-y", *raw, "-i", "-", os.path.join(out_dir, "f_%07.2f.png" % t)],
                           input=(img * 255 + 0.5).astype(np.uint8).tobytes(), check=True)
    R.close()
    return seg


def _run(jobs, workers):
    if workers <= 1 or len(jobs) == 1:
        return [work(j) for j in jobs]
    with mp.Pool(len(jobs)) as pool:
        return pool.map(work, jobs)


def _setup(edl):
    plan = build_plan(edl)
    cache = tempfile.mkdtemp(prefix="reel_")
    notes = prepare_text(plan, cache)
    plan_path = os.path.join(cache, "plan.json")
    Path(plan_path).write_text(json.dumps(plan, default=lambda o: None), encoding="utf-8")
    return plan, cache, plan_path, notes, int(round(plan["dur"] * plan["fps"]))


def default_workers():
    return max(1, min(8, (os.cpu_count() or 4) - 2))


def _filter_path(p):
    return "'" + Path(p).as_posix().replace(":", "\\:") + "'"


def contact_sheet(files, dst):
    """All stills side by side (8 per row), each labelled with its time."""
    cw, ch = CFG["sheet"]["cell"]
    cols = min(CFG["sheet"]["cols"], len(files))
    rows = (len(files) + cols - 1) // cols
    font = _filter_path(ascii_path(DATA / "fonts" / "Anton-Regular.ttf"))   # v10.15: Arabic skill folder broke drawtext
    fl = "".join("[%d:v]scale=%d:%d,drawtext=text=%s:x=6:y=6:fontsize=24:fontcolor=yellow:box=1:boxcolor=black@0.6:fontfile=%s[v%d];"
                 % (i, cw, ch, Path(f).name[2:-4].lstrip("0") or "0", font, i) for i, f in enumerate(files))
    pads = cols * rows - len(files)
    fl += "".join("color=black:s=%dx%d:d=1[p%d];" % (cw, ch, p) for p in range(pads))
    lay = "|".join("%d_%d" % ((k % cols) * cw, (k // cols) * ch) for k in range(cols * rows))
    fl += "".join("[v%d]" % i for i in range(len(files))) + "".join("[p%d]" % p for p in range(pads)) + \
        ("xstack=inputs=%d:layout=%s" % (cols * rows, lay) if cols * rows > 1 else "null") + ",format=yuvj420p"
    ffmpeg(*[a for f in files for a in ("-i", f)], "-filter_complex", fl, "-frames:v", 1, dst)
    return dst


def stills(edl, times, out_dir=None, workers=None):
    """PNG stills at the given program seconds + sheet.jpg. Returns the sheet path."""
    plan, cache, plan_path, notes, nfr = _setup(edl)
    out_dir = out_dir or os.path.join(plan["P"], "qa", "stills_" + time.strftime("%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)
    ks = [min(nfr - 1, int(round(t * plan["fps"]))) for t in times]
    workers = workers or default_workers()
    chunks = [ks[i::workers] for i in range(min(workers, len(ks)))]
    _run([(plan_path, cache, ch, None, "stills", out_dir) for ch in chunks], workers)
    files = sorted(os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.startswith("f_") and f.endswith(".png"))
    return dict(sheet=contact_sheet(files, os.path.join(out_dir, "sheet.jpg")), stills=files, notes=notes)


def ebur128(path):
    err = subprocess.run([exe("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a", "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="ignore", stdin=subprocess.DEVNULL).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    return float(m[-1]) if m else None


def render(edl, out=None, workers=None):
    """The full reel: H.264 CRF 12 BT.709 + the program audio as AAC 320k. Returns facts about the file."""
    t_start = time.time()
    plan, cache, plan_path, notes, nfr = _setup(edl)
    out = os.path.abspath(out or os.path.join(plan["P"], "render", plan["name"] + ".mp4"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    nw = max(1, workers or default_workers())
    bounds = [round(nfr * i / nw) for i in range(nw + 1)]
    segs = _run([(plan_path, cache, (bounds[i], bounds[i + 1]), os.path.join(cache, "seg_%02d.mp4" % i), "range", None)
                 for i in range(nw)], nw)
    lst = Path(cache) / "segs.txt"
    lst.write_text("".join("file '%s'\n" % Path(s).as_posix() for s in segs), encoding="utf-8")
    e = CFG["encode"]
    # exact length: all nfr frames, the program audio padded/trimmed to nfr / fps (no -shortest)
    ffmpeg("-nostdin", "-f", "concat", "-safe", 0, "-i", lst, "-i", plan["audio"], "-map", "0:v", "-map", "1:a", "-c:v", "copy",
           "-frames:v", nfr, "-af", fit_audio(nfr / plan["fps"]),
           "-c:a", e["acodec"], "-b:a", e["abitrate"], "-ar", e["ar"], "-movflags", "+faststart", out)
    m = info(out)
    return dict(out=out, w=m["w"], h=m["h"], fps=m["fps"], dur=m["dur"], audio=m["audio"], lufs=ebur128(out), frames=nfr,
                seconds=round(time.time() - t_start, 1), notes=notes)
