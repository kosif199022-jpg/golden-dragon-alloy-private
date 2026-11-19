"""Helpers of power_programs/formats_platforms.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from PIL import ImageDraw
from pathlib import Path
import json
import math
import numpy as np
import re
import subprocess
from .core import fx


def ff(*args, ok=True):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], capture_output=True, text=True)
    if ok and r.returncode:
        raise RuntimeError(r.stderr[-800:])
    return r


def ff_stderr(*args) -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *map(str, args)], capture_output=True, text=True).stderr


def probe(path, *extra) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", *extra, str(path)],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def vstream(p):
    return next(s for s in probe(p)["streams"] if s["codec_type"] == "video")


def frames_of(path, w, h, fmt="rgb24", ch=3):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", fmt, "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, ch) if ch > 1 else np.frombuffer(raw, np.uint8).reshape(-1, h, w)


def testclip(work, name="src.mp4", size="64x36", dur=1, rate=30, audio=False, src="testsrc2"):
    p = work / name
    args = ["-f", "lavfi", "-i", f"{src}=size={size}:rate={rate}:duration={dur}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=f=440:d={dur}:sample_rate=48000"]
    args += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    if audio:
        args += [*fx.fit_audio(round(dur * rate) / rate), "-c:a", "aac", "-b:a", "128k", "-frames:v", str(round(dur * rate))]
    ff(*args, p)
    return p


def lufs(path) -> tuple:
    err = ff_stderr("-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-")
    i = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])
    tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)[-1])
    return i, tp


def normalise(src, dst, target=-14.0):
    i, _ = lufs(src)
    ff("-i", src, "-af", f"volume={target - i:.2f}dB", "-c:a", "pcm_s16le", dst)
    return lufs(dst)


def atoms(path) -> list:
    data, out, i = Path(path).read_bytes(), [], 0
    while i + 8 <= len(data):
        size = int.from_bytes(data[i:i + 4], "big")
        out.append(data[i + 4:i + 8].decode("latin1"))
        if size < 8:
            break
        i += size
    return out


def save_json(work, name, obj):
    (work / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def contrast(a, b):
    def L(rgb): return 0.2126 * _lin(rgb[0]) + 0.7152 * _lin(rgb[1]) + 0.0722 * _lin(rgb[2])
    la, lb = sorted((L(a), L(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def clamp01(p): return max(0.0, min(1.0, p))


def power4_in_out(p): return 8 * p ** 4 if p < 0.5 else 1 - (-2 * p + 2) ** 4 / 2


def bar_height(W, H, ratio=2.39):
    return round((H - W / ratio) / 2)


def letterbox_reveal(t, D, start_cap=2.4, dur=2.2, h0=70):
    start = min(start_cap, 0.15 * D)
    return h0 * (1 - power4_in_out(clamp01((t - start) / dur)))


def stage_fit(vw, vh, sw=1920, sh=1080):
    s = min(vw / sw, vh / sh)
    return {"scale": s, "x": (vw - sw * s) / 2, "y": (vh - sh * s) / 2, "box": "letterbox" if vw / vh < sw / sh else "pillarbox" if vw / vh > sw / sh else "exact"}


SOCIAL = {"linkedin_post": (1200, 627, 100), "x_card": (1200, 675, 80), "ig_square": (1080, 1080, 108), "ig_landscape": (1080, 566, 80),
          "fb_post": (1200, 630, 100), "yt_thumb": (1280, 720, 72), "github_preview": (1280, 640, None)}


def safe_rect(name):
    w, h, m = SOCIAL[name]
    m = m if m is not None else round(0.1 * min(w, h))
    return (m, m, w - m, h - m)


def channel_art_safe(w=2560, h=1440, sw=1546, sh=423):
    return ((w - sw) / 2, (h - sh) / 2, (w + sw) / 2, (h + sh) / 2)


def caption_box(W, H, lines, vertical=True):
    m = 0.05
    x0, x1 = W * m, W * (1 - (0.12 if vertical else m))
    y_centre = H * 0.70
    lh = 0.035 * H
    y0 = y_centre - lines * lh / 2
    y1 = y_centre + lines * lh / 2
    limit = H * (0.80 if vertical else 1 - m)
    return {"box": (x0, y0, x1, y1), "ok": lines <= 2 and y1 <= limit and y0 >= H * m}


def density(mode, bullets):
    lo, hi = (1, 3) if mode == "narrated" else (4, 8)
    return lo <= len(bullets) <= hi


def vtt(cues):
    def ts(s): return f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{s % 60:06.3f}"
    return "WEBVTT\n\n" + "\n\n".join(f"{ts(a)} --> {ts(b)}\n{t}" for a, b, t in cues) + "\n"


def parse_vtt(text):
    out = []
    for m in re.finditer(r"(\d\d):(\d\d):(\d\d\.\d{3}) --> (\d\d):(\d\d):(\d\d\.\d{3})\n(.+)", text):
        g = m.groups()
        out.append((int(g[0]) * 3600 + int(g[1]) * 60 + float(g[2]), int(g[3]) * 3600 + int(g[4]) * 60 + float(g[5]), g[6]))
    return out


def subject_centre(frame):
    import cv2
    g = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    _, m = cv2.threshold(g, 200, 255, cv2.THRESH_BINARY)
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    x, y, w, h = cv2.boundingRect(max(cs, key=cv2.contourArea))
    return x + w / 2, y + h / 2


def shorts_plan(src_dur, peaks, length=60, handle=15):
    if src_dur < length + 2 * handle:
        return {"feasible": False, "need": length + 2 * handle}
    out = []
    for p in peaks:
        a = p - length / 2 - handle
        b = p + length / 2 + handle
        if a < 0 or b > src_dur:
            continue
        out.append((a, b))
    return {"feasible": True, "clips": out}


def hls(work, per_audio=True):
    d = work / ("hls" if per_audio else "hls_bad")
    d.mkdir(exist_ok=True)
    amap = ["-map", "0:a"] * 3 if per_audio else ["-map", "0:a"]
    args = ["-f", "lavfi", "-i", "testsrc2=size=96x54:rate=30:duration=8", "-f", "lavfi", "-i", "sine=d=8:sample_rate=48000",
            "-filter_complex", "[0:v]split=3[a][b][c];[a]scale=96:54[v0];[b]scale=64:36[v1];[c]scale=32:18[v2]",
            "-map", "[v0]", "-map", "[v1]", "-map", "[v2]"]
    args = args[:8] + args[8:]
    r = ff(*args, *["-map", "1:a"] * (3 if per_audio else 1), "-c:v", "libx264", "-preset", "ultrafast", "-g", 60, "-keyint_min", 60, "-sc_threshold", 0,
           "-b:v:0", "5000k", "-b:v:1", "2800k", "-b:v:2", "1400k", "-c:a", "aac", "-b:a", "96k",
           "-f", "hls", "-hls_time", 4, "-hls_playlist_type", "vod", "-master_pl_name", "master.m3u8",
           "-var_stream_map", "v:0,a:0 v:1,a:1 v:2,a:2", str(d / "v%v.m3u8"), ok=False)
    return d, r


def music_receipt_ok(r):
    if r.get("provider") == "elevenlabs" and r.get("plan") == "free" and r.get("use") == "commercial":
        return False
    return all(r.get(k) for k in ("provider", "plan", "rights", "rendered_at"))


def vstream_or_none(p):
    return probe(p)["streams"][0]["codec_name"]


PLATFORMS = {"tiktok": {"size": (1080, 1920), "max_s": 600, "max_mb": 287, "v": 12000, "a": 192},
             "reels": {"size": (1080, 1920), "max_s": 180, "max_mb": 250}, "shorts": {"size": (1080, 1920), "max_s": 180, "max_mb": 256},
             "youtube": {"size": (1920, 1080), "max_s": None, "max_mb": 2000, "v": 16000, "a": 256},
             "x": {"size": (1280, 720), "max_s": 140, "max_mb": 512, "v": 8000, "a": 160},
             "whatsapp": {"size": (720, 1280), "max_s": 30, "max_mb": 16, "v": 2200, "a": 96},
             "linkedin": {"size": (1080, 1080), "max_s": 600, "max_mb": 200, "v": 8000}, "snapchat": {"size": (1080, 1920), "max_s": 60, "max_mb": 32, "v": 6000, "a": 128}}


def platform_warnings(duration):
    return {p: [f"over {s['max_s']} s"] for p, s in PLATFORMS.items() if s["max_s"] and duration > s["max_s"]}


LIMITS = {"tiktok": {"chars": 4000, "secs": 600}, "reels": {"chars": 2200, "secs": 180, "tags": 5}, "x": {"chars": 280, "secs": 140, "images": 4},
          "linkedin": {"chars": 3000, "visible": 210}, "facebook": {"chars": 63206}}


def post_check(platform, caption, secs=0, tags=0, images=0):
    L, errs = LIMITS[platform], []
    if len(caption) > L["chars"]:
        errs.append("chars")
    if "secs" in L and secs > L["secs"]:
        errs.append("secs")
    if "tags" in L and tags > L["tags"]:
        errs.append("tags")
    if "images" in L and images > L["images"]:
        errs.append("images")
    return errs


CTA_WORDS = ("احفظ", "شارك", "علّق", "تابع", "save", "share", "comment", "follow")


def hook_type(line):
    if "?" in line or "؟" in line:
        return "question"
    if re.search(r"\d|[٠-٩]", line):
        return "number"
    if re.search(r"\b(but|not|لكن|ليس|لا)\b", line, re.I):
        return "contradiction"
    if re.search(r"(saved|doubled|وفّر|ضاعف|result)", line, re.I):
        return "result"
    return None


def post_rules(text):
    tags = re.findall(r"#\w+", text)
    lines = [l for l in text.splitlines() if l.strip()]
    ctas = sum(1 for w in CTA_WORDS if w in text.lower())
    return {"tags": len(tags) <= 5, "cta": ctas == 1, "hook": hook_type(lines[0]) is not None}


def envelope_ok(obj):
    need = {"title", "analysis", "confidence", "sources", "json", "next"}
    if not need <= set(obj):
        return False
    if not 0 <= obj["confidence"] <= 1 or not isinstance(obj["sources"], list):
        return False
    return {"tool_output", "prompts", "imageSpecs"} <= set(obj["json"])


def ab_valid(a, b):
    diff = [k for k in a if a[k] != b.get(k)]
    return len(diff) == 1, diff


def thumb_rules(thumb_text, title):
    words_t = set(re.findall(r"\w+", thumb_text.lower()))
    words_title = set(re.findall(r"\w+", title.lower()))
    return {"thumb_words": 1 <= len(thumb_text.split()) <= 3, "title_len": len(title) <= 60, "no_overlap": not (words_t & words_title)}


def mark(size):
    im = Image.new("RGBA", (size, size), (29, 24, 20, 255))
    d = ImageDraw.Draw(im)
    d.ellipse([size * 0.25, size * 0.25, size * 0.75, size * 0.75], fill=(232, 189, 118, 255))
    return im


def resolve_vars(css_vars, value):
    m = re.fullmatch(r"var\((--[\w-]+)\)", value.strip())
    if not m:
        return value
    if m.group(1) not in css_vars:
        raise KeyError(m.group(1))
    return resolve_vars(css_vars, css_vars[m.group(1)])


def export_fig(series, colour, work, fmt="png", scale=2, css_vars=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    try:
        col = resolve_vars(css_vars or {}, colour)
    except KeyError:
        fmt, col = "svg", "#000000"
    fig = plt.figure(figsize=(3, 2), dpi=50)
    plt.bar(range(len(series)), series, color=col)
    p = work / f"chart.{fmt}"
    fig.savefig(p, dpi=50 * scale if fmt == "png" else 50, format=fmt)
    plt.close(fig)
    return p


def colour_svg(img: Image.Image, scale=2):
    a = np.asarray(img.convert("RGB"))
    paths = []
    for col in np.unique(a.reshape(-1, 3), axis=0):
        mask = np.all(a == col, axis=2)
        d = []
        for y, x in zip(*np.nonzero(mask)):
            d.append(f"M{x * scale} {y * scale}h{scale}v{scale}h-{scale}z")
        paths.append(f'<path fill="#{col[0]:02x}{col[1]:02x}{col[2]:02x}" fill-rule="evenodd" d="{"".join(d)}"/>')
    h, w = a.shape[:2]
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w * scale} {h * scale}">' + "".join(paths) + "</svg>"


def painting(W, H):
    im = Image.new("RGB", (W, H), (250, 245, 235))
    d = ImageDraw.Draw(im)
    d.ellipse([W * .2, H * .2, W * .5, H * .7], fill=(200, 40, 40))
    d.rectangle([W * .55, H * .3, W * .85, H * .8], fill=(30, 60, 150))
    return im


def slides_of(doc):
    slides, cur = [], None
    for line in doc.splitlines():
        m = re.match(r"^(#{1,2})\s+(.*)", line)
        if m:
            cur = {"title": m.group(2), "level": len(m.group(1)), "body": []}
            slides.append(cur)
        elif line.strip() and cur:
            cur["body"].append(line.strip())
    return slides


CODE = {"hook": 60, "message": 120, "features": 180, "end": 240}


def ad_frame(slots, t):
    lab = next(l for a, b, l in slots if a <= t < b or (t == slots[-1][1] and l == slots[-1][2]))
    return np.full((9, 16), CODE[lab], np.uint8)


def cut_ok(cuts, lo=1.0, hi=2.0):
    gaps = np.diff(cuts)
    return bool(np.all((gaps >= lo - 1e-9) & (gaps <= hi + 1e-9)))


def cutdown(beats, target, grid=0.5):
    keep = list(beats)
    while sum(b["dur"] for b in keep) > target:
        opt = [b for b in keep if b["priority"] > 1]
        if not opt:
            raise ValueError("cannot reach target without dropping must-keep beats")
        keep.remove(max(opt, key=lambda b: (b["priority"], b["dur"])))
    extra = target - sum(b["dur"] for b in keep)
    keep[-1] = dict(keep[-1], dur=keep[-1]["dur"] + extra)
    t, out = 0.0, []
    for b in keep:
        out.append(dict(b, start=round(round(t / grid) * grid, 3)))
        t += b["dur"]
    return out


def atomise(md):
    chapters = re.findall(r"^## (.+)$", md, re.M)
    prose = "\n".join(l for l in md.splitlines() if not re.match(r"^(#|\d+\. )", l))
    stats = re.findall(r"[^.\n]*\d+%[^.\n]*", prose)
    steps = re.findall(r"^\d+\. (.+)$", md, re.M)
    concl = re.search(r"^## (?:Conclusion|الخلاصة)\n(.+)", md, re.M)
    return {"chapters": chapters, "pull_quotes": [s.strip() for s in stats], "segments": steps, "short": concl.group(1) if concl else None}


def standalone(script):
    return not re.search(r"as (discussed|mentioned) (above|earlier|before)|كما ذكرنا", script, re.I)


def words_fit(script, lo=20, hi=45, wps=3.3):
    n = len(script.split())
    return 80 <= n <= 150 and lo <= n / wps <= hi


def chapter_list(markers):
    def ts(s): return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"
    errs = []
    if len(markers) < 3:
        errs.append("fewer than 3")
    if markers[0][0] != 0:
        errs.append("first not 00:00")
    if any(b[0] - a[0] < 10 for a, b in zip(markers, markers[1:])):
        errs.append("closer than 10 s")
    return "\n".join(f"{ts(t)} {n}" for t, n in markers), errs


MG = {"MG-061": [(0, 0.9, "card1"), (0.9, 1.8, "card2"), (1.8, 2.7, "card3"), (2.7, 4, "topic")],
      "MG-062": [(0, 1.5, "question"), (1.5, 2.5, "split"), (2.5, 5, "answer")],
      "MG-063": [(0, 4, "tip1"), (4, 8, "tip2"), (8, 12, "tip3")],
      "MG-066": [(0, 2, "result"), (2, 3, "shrink"), (3, 8, "steps"), (8, 10, "back")]}


def phase(mg, t):
    for a, b, n in MG[mg]:
        if a <= t < b:
            return n
    return "end"


def word_mask_times(words, start, per=0.25):
    return [round(start + i * per, 3) for i in range(len(words))]


def loop_frame(i, N=30, W=32, H=18):
    t = i / N
    a = np.zeros((H, W), np.uint8)
    x = int(round((W - 4) * (0.5 + 0.5 * math.sin(2 * math.pi * t))))
    a[6:12, x:x + 4] = 255
    return a


def end_card_frame(t, D=6.0, W=108, H=192):
    top, bot = np.array((0x1b, 0x2a, 0x49)), np.array((0x0d, 0x1b, 0x2a))
    a = (top + (bot - top) * np.linspace(0, 1, H)[:, None]).round().astype(np.uint8)
    a = np.repeat(a[:, None, :], W, axis=1)
    p = clamp01(t / (D - 0.4))
    a[H - 6:H - 3, 8:8 + int(round((W - 16) * p))] = (0xE7, 0xB6, 0x5A)
    return a


def promo_layout(W=1080, H=1080, margin=80, arabic=True, product_h=0.45):
    text = (W - margin - 400, margin, W - margin, margin + 200) if arabic else (margin, margin, margin + 400, margin + 200)
    ph = product_h * H
    product = (W / 2 - ph / 2, H - margin - ph, W / 2 + ph / 2, H - margin)
    return {"text": text, "product": product, "ok": product_h >= 0.4 and text[1] >= margin and product[3] <= H - margin}


def spring_settle(k=180, c=14, m=1.0, fps=60):
    x, v, out = 0.0, 0.0, []
    for _ in range(fps * 2):
        for _ in range(20):
            a = (-k * (x - 1) - c * v) / m
            v += a / fps / 20
            x += v / fps / 20
        out.append(x)
    return np.array(out)
