"""Kinetic typography through libass (ffmpeg's `ass` filter): one event per frame per text, per-letter override tags.

  build  letters arrive in random order, stretched tall and spread wide, outline first then fill, in 2-frame steps
  soft   fades in from a blur with a slight grow        words  each word appears when it is spoken
  pop    118% -> 100% in 2 frames                       exit   display words dissolve letter by letter, others fade

(x, y) is the centre of the visible ink, measured once per text in a measurement pass.
Font sizes are design (em) sizes: libass sizes by the full line height, so sizes are scaled by the font's metrics.
"""
import json, math, os, random, struct, subprocess
from pathlib import Path

import numpy as np

from ..media import ascii_path, exe

DATA = Path(__file__).with_name("data")
STYLE = json.loads((DATA / "style.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ font files
def _offsets(data):
    if data[:4] == b"ttcf":
        n = struct.unpack(">I", data[8:12])[0]
        return list(struct.unpack(f">{n}I", data[12:12 + 4 * n]))
    return [0]


def _tables(data, off):
    num = struct.unpack(">H", data[off + 4:off + 6])[0]
    recs = [struct.unpack(">4sIII", data[off + 12 + 16 * i: off + 28 + 16 * i]) for i in range(num)]
    return {tag.decode("latin-1"): (o, ln) for tag, _, o, ln in recs}, recs


def faces(path):
    """Every face of a .ttf/.otf/.ttc: names and vertical metrics."""
    data = Path(path).read_bytes()
    res = []
    for off in _offsets(data):
        tb, _ = _tables(data, off)
        upm = struct.unpack(">H", data[tb["head"][0] + 18:tb["head"][0] + 20])[0]
        asc, desc = struct.unpack(">hh", data[tb["hhea"][0] + 4:tb["hhea"][0] + 8])
        win_a = win_d = None
        weight, italic = 400, False
        if "OS/2" in tb:
            b = data[tb["OS/2"][0]:sum(tb["OS/2"])]
            weight, italic = struct.unpack(">H", b[4:6])[0], bool(struct.unpack(">H", b[62:64])[0] & 1)
            win_a, win_d = struct.unpack(">HH", b[74:78])
        o = tb["name"][0]
        _, count, so = struct.unpack(">HHH", data[o:o + 6])
        names = {}
        for i in range(count):
            pid, _, _, nid, ln, no = struct.unpack(">HHHHHH", data[o + 6 + 12 * i:o + 18 + 12 * i])
            raw = data[o + so + no:o + so + no + ln]
            try:
                names.setdefault(nid, raw.decode("utf-16-be") if pid in (0, 3) else raw.decode("mac_roman"))
            except UnicodeDecodeError:
                pass
        res.append(dict(family=names.get(16) or names.get(1), ps=names.get(6), upm=upm, asc=asc, desc=desc,
                        win_asc=win_a, win_desc=win_d, weight=weight, italic=italic))
    return res


def libass_factor(f):
    """Multiply a design (em) size by this to get the libass font size."""
    h = f["win_asc"] + f["win_desc"] if f.get("win_asc") and f.get("win_desc") is not None and f["win_asc"] + f["win_desc"] > 0 \
        else f["asc"] - f["desc"]
    return h / float(f["upm"])


def split_faces(path, out_dir):
    """One .ttf per face (libass only loads the first face of a collection from a fonts folder)."""
    data = Path(path).read_bytes()
    for off, f in zip(_offsets(data), faces(path)):
        dst = Path(out_dir) / f"{f['ps']}.ttf"
        if not f["ps"] or dst.exists():
            continue
        _, recs = _tables(data, off)
        dirs, body, pos = bytearray(), bytearray(), 12 + 16 * len(recs)
        for tag, chk, o, ln in recs:
            dirs += struct.pack(">4sIII", tag, chk, pos + len(body), ln)
            body += data[o:o + ln] + b"\0" * ((4 - ln % 4) % 4)
        tmp = dst.with_suffix(f".{os.getpid()}.part")
        tmp.write_bytes(data[off:off + 12] + bytes(dirs) + bytes(body))
        os.replace(tmp, dst)


class Fonts:
    """A fonts folder for libass (bundled Anton, macOS faces when present, $REEL_FONT_FILES) + per-face size factors."""

    def __init__(self, cache):
        self.dir = os.path.join(cache, "fonts")
        os.makedirs(self.dir, exist_ok=True)
        extra = [p for p in os.environ.get("REEL_FONT_FILES", "").split(os.pathsep) if p]
        for src in [DATA / f for f in STYLE["font_files"]] + extra:
            if os.path.exists(src):
                split_faces(src, self.dir)
        self.factor, self.info = {}, {}
        for fn in sorted(os.listdir(self.dir)):
            if fn.lower().endswith((".ttf", ".otf", ".ttc")):
                for f in faces(os.path.join(self.dir, fn)):
                    if f["ps"]:
                        self.factor[f["ps"]] = libass_factor(f)
                        self.info[f["ps"]] = dict(family=f["family"] or f["ps"], weight=f["weight"], italic=f["italic"])

    def tags(self, ps):
        """libass finds faces by family: select family (style) + exact weight / italic (tags)."""
        i = self.info.get(ps)
        return "\\b%d\\i%d" % (i["weight"], 1 if i["italic"] else 0) if i else ""

    def header(self, W, H, fonts):
        styles = "\n".join("Style: %s,%s,60,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1"
                           % (k, self.info.get(ps, {}).get("family", ps)) for k, ps in fonts.items())
        return ("[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\nScaledBorderAndShadow: yes\nYCbCr Matrix: None\n\n"
                "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
                "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, "
                "Encoding\n%s\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n") % (W, H, styles)


# ------------------------------------------------------------------------------------------------ easing + helpers
def bez(u, i_out, i_in):
    """Keyframe-style temporal ease (speed 0, influence i_out / i_in) as a progress curve."""
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    x1, x2, s = i_out, 1 - i_in, u
    for _ in range(12):
        x = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3
        dx = 3 * (1 - s) ** 2 * x1 + 6 * (1 - s) * s * (x2 - x1) + 3 * s * s * (1 - x2)
        if abs(dx) < 1e-6:
            break
        s = min(1.0, max(0.0, s - (x - u) / dx))
    return 3 * (1 - s) * s * s + s ** 3


def ramp(t, t0, t1, v0, v1, ease=None):
    if t <= t0:
        return v0
    if t >= t1:
        return v1
    u = (t - t0) / (t1 - t0)
    return v0 + (v1 - v0) * (bez(u, ease, ease) if ease else u)


def hexcol(h):
    return h[5:7] + h[3:5] + h[1:3]                 # #RRGGBB -> BBGGRR


def a8(opacity):
    return "%02X" % int(round(255 * (1 - max(0.0, min(1.0, opacity)))))


def esc(ch):
    return {"{": "\\{", "}": "\\}", "\\": "\\\\"}.get(ch, ch)


def ass_time(t):
    cs = int(math.floor(t * 100 + 1e-6))
    return "%d:%02d:%02d.%02d" % (cs // 360000, (cs // 6000) % 60, (cs // 100) % 60, cs % 100)


def text_lines(text):
    """(first char index, line) per line."""
    out, i = [], 0
    for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        out.append((i, ln))
        i += len(ln) + 1
    return out


def tracking_px(T):
    """'tracking' is 1/1000 em like design tools (Anton default -10)."""
    return T.get("tracking", -10 if T["font"] == "anton" else 0) / 1000.0 * T["size"]


def _perm(rnd, n):
    order = list(range(n))
    rnd.shuffle(order)
    pos = [0] * n
    for p, i in enumerate(order):
        pos[i] = p
    return pos


# ------------------------------------------------------------------------------------------------ animation
class TextAnim:
    """One text item evaluated frame by frame."""

    def __init__(self, T, fps, uid):
        self.T, self.t0, self.t1 = T, T["t0"], T["t1"]
        self.chars = list(T["text"].replace("\r\n", "\n").replace("\r", "\n"))
        self.ns = [i for i, c in enumerate(self.chars) if not c.isspace()]
        n = len(self.ns)
        self.pos_build = _perm(random.Random(1000 + uid), n)
        self.pos_outline = _perm(random.Random(7000 + uid), n)
        self.pos_exit = _perm(random.Random(3000 + uid), n)
        self.steps = 3 if n <= 3 else (4 if n <= 6 else 5)
        self.stepT = 2.0 / fps
        self.ed = min(0.3, (self.t1 - self.t0) * 0.3)
        self.has_exit = T.get("fadeout", True) is not False and self.ed > 0.06
        self.words, cur = [], []
        for i, c in enumerate(self.chars + [" "]):
            if c.isspace():
                if cur:
                    self.words.append(cur)
                cur = []
            else:
                cur.append(i)

    def stepped(self, t, delay):
        k = math.floor((t - self.t0) / self.stepT + 1e-6) - delay
        return max(0.0, min(1.0, k / float(self.steps)))

    def state(self, t):
        """(layer, per-char params) at time t, or None when not visible."""
        T, a = self.T, self.T["anim"]
        if t < self.t0 - 1e-6 or t >= self.t1 - 1e-6:
            return None
        lay = dict(scale=100.0, opacity=1.0, blur=0.0)
        n = len(self.ns)
        ch = [dict(op=1.0, fill=1.0, sx=100.0, sy=100.0, sp=0.0, bord=0.0, blur=0.0) for _ in self.chars]
        if a == "build":
            lay["scale"] = ramp(t, self.t0, self.t1, 106, 100)
            s1, s2 = self.stepped(t, 0), self.stepped(t, 2)
            sw = max(2, round(T["size"] / 60.0))
            for j, i in enumerate(self.ns):
                a1 = max(0.0, min(1.0, (self.pos_build[j] + 1) - n * s1))
                a2 = max(0.0, min(1.0, (self.pos_outline[j] + 1) - n * s2))
                ch[i].update(op=ch[i]["op"] * (1 - a1), sx=100 - 40 * a1, sy=100 + 200 * a1, sp=0.18 * a1 * T["size"],
                             fill=1 - a2, bord=sw * a2)
        elif a == "words":
            lay["scale"] = ramp(t, self.t0, self.t0 + 0.12, 108, 100, 0.75)
            wt = T.get("wt") or []
            for w, idx in enumerate(self.words):
                if w < len(wt) and t < wt[w] - 1e-6:
                    for i in idx:
                        ch[i]["op"] = 0.0
        elif a == "pop":
            lay["scale"] = ramp(t, self.t0, self.t0 + 0.08, 118, 100)
        elif a == "soft":
            lay["opacity"] *= ramp(t, self.t0, self.t0 + 0.2, 0, 1)
            lay["blur"] = ramp(t, self.t0, self.t0 + 0.26, 30, 0)
            lay["scale"] = ramp(t, self.t0, self.t0 + 0.3, 94, 100, 0.8)
        if self.has_exit:
            if T["font"] != "sub" and not T.get("_rtl"):      # joined (Arabic) script never dissolves letter by letter
                e = ramp(t, self.t1 - self.ed, self.t1 - 0.02, 0, 1, 0.55)
                for j, i in enumerate(self.ns):
                    a3 = max(0.0, min(1.0, n * e - self.pos_exit[j]))
                    c = ch[i]
                    c["op"] *= 1 - a3
                    c["sx"] *= 1 + 0.16 * a3
                    c["sy"] *= 1 + 0.16 * a3
                    c["blur"] = 16 * a3
            else:
                lay["opacity"] *= ramp(t, self.t1 - 0.16, self.t1, 1, 0, 0.5)
        for (ta, va), (tb, vb) in zip(T.get("opacity_keys") or [], (T.get("opacity_keys") or [])[1:]):
            if ta <= t < tb:
                lay["opacity"] *= ramp(t, ta, tb, va, vb) / 100.0
        return lay, ch


def event_text(T, lay, ch, factor, colour, opacity_mul=1.0, blur_add=0.0, border_colour=None):
    """Event bodies, one per non-empty line, stacked with design-tool leading around (x, y)."""
    sc = lay["scale"] / 100.0
    trk = tracking_px(T)
    lines = text_lines("".join(T["_chars"]))
    base = T.get("_offset", (0.0, 0.0))
    offs = T.get("_offsets") or [base] * len(lines)
    lead = T.get("leading", 1.2 * T["size"])
    out = []
    for k, (i0, ln) in enumerate(lines):
        if not ln.strip():
            continue
        off = offs[k] if k < len(offs) and offs[k] is not None else base
        x = T["x"] - off[0] * sc
        y = T["y"] + (k - (len(lines) - 1) / 2.0) * lead * sc - off[1] * sc
        parts = ["{\\an5\\pos(%.1f,%.1f)%s\\fs%.2f\\1c&H%s&\\3c&H%s&\\shad0\\bord0}" % (
            x, y, T.get("_ftags", ""), T["size"] * factor, hexcol(colour), hexcol(border_colour or colour))]
        for j, char in enumerate(ln):
            c = ch[i0 + j]
            op = c["op"] * lay["opacity"] * opacity_mul
            parts.append("{\\1a&H%s&\\3a&H%s&\\fscx%.1f\\fscy%.1f\\fsp%.2f\\bord%.2f\\blur%.2f}%s" % (
                a8(op * c["fill"]), a8(op), c["sx"] * sc, c["sy"] * sc, (c["sp"] + trk) * sc, c["bord"] * sc,
                c["blur"] * 0.5 + lay["blur"] * 0.5 + blur_add, esc(char)))
        out.append("".join(parts))
    return out


def write_ass(path, texts, W, H, fps, fonts, F, t_from, t_to, glow_soft=11.0, shadow_soft=5.0):
    """Per-frame events of every text visible in [t_from, t_to); event times are local to t_from."""
    lines = [F.header(W, H, fonts)]
    f0, f1 = int(math.floor(t_from * fps + 1e-6)), int(math.ceil(t_to * fps - 1e-6))
    for uid, T in enumerate(texts):
        anim = T.get("_anim") or TextAnim(T, fps, T.get("_uid", uid))
        T["_anim"], T["_chars"] = anim, anim.chars
        fac = F.factor[fonts[T["font"]]]
        T["_ftags"] = F.tags(fonts[T["font"]])
        for k in range(max(f0, int(math.floor(T["t0"] * fps + 1e-6))), min(f1, int(math.ceil(T["t1"] * fps - 1e-6)))):
            st = anim.state(k / fps)
            if not st:
                continue
            lay, ch = st
            ts, te = ass_time((k - f0) / fps), ass_time((k - f0 + 1) / fps)
            evs = []
            if T.get("glow"):
                evs += [(0, b) for b in event_text(T, lay, ch, fac, T.get("glow_color", T["color"]), 0.75, glow_soft)]
            if T.get("shadow"):
                evs += [(0, b) for b in event_text(T, lay, ch, fac, "#000000", 0.45, shadow_soft, "#000000")]
            evs += [(1, b) for b in event_text(T, lay, ch, fac, T["color"])]
            lines += ["Dialogue: %d,%s,%s,%s,,0,0,0,,%s\n" % (layer, ts, te, T["font"], b) for layer, b in evs]
    Path(path).write_text("".join(lines), encoding="utf-8")


def _filter_path(p):
    return str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def render_stream(ass_path, fdir, W, H, fps, n_frames):
    """ffmpeg process emitting n_frames transparent RGBA frames (W x H) of a subtitle canvas."""
    src = "color=c=black@0.0:s=%dx%d:r=%s:d=%.5f,format=rgba" % (W, H, fps, (n_frames + 1) / fps)
    return subprocess.Popen([exe("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", src, "-vf",
                             "ass='%s':fontsdir='%s':alpha=1" % (_filter_path(ascii_path(ass_path)),
                                                                 _filter_path(ascii_path(fdir))),
                             "-frames:v", str(n_frames), "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                            stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)


def measure(texts, fonts, F, workdir, fps, tag="front"):
    """Ink-centre offset of every line relative to its \\pos (static, final state, 100%), and the ink width."""
    if not texts:
        return
    Wm, Hm = 3000, 1400
    lines, jobs = [F.header(Wm, Hm, fonts)], []
    for T in texts:
        for li, (_, ln) in enumerate(text_lines(T["text"])):
            if ln.strip():
                k = len(jobs)
                jobs.append((T, li))
                lines.append("Dialogue: 1,%s,%s,%s,,0,0,0,,{\\an5\\pos(%d,%d)%s\\fs%.2f\\fsp%.2f\\bord0\\shad0}%s\n" % (
                    ass_time(k / fps), ass_time((k + 1) / fps), T["font"], Wm // 2, Hm // 2, F.tags(fonts[T["font"]]),
                    T["size"] * F.factor[fonts[T["font"]]], tracking_px(T), "".join(esc(c) for c in ln)))
    p = os.path.join(workdir, f"measure_{tag}.ass")
    Path(p).write_text("".join(lines), encoding="utf-8")
    for T in texts:
        T["_offsets"] = [None] * len(text_lines(T["text"]))
        T.pop("_inkw", None)
    proc = render_stream(p, F.dir, Wm, Hm, fps, len(jobs))
    for T, li in jobs:
        a = np.frombuffer(proc.stdout.read(Wm * Hm * 4), np.uint8).reshape(Hm, Wm, 4)[:, :, 3]
        ys, xs = np.nonzero(a.max(axis=1) > 96)[0], np.nonzero(a.max(axis=0) > 96)[0]
        if len(ys) and len(xs):
            T["_offsets"][li] = ((xs[0] + xs[-1]) / 2.0 - Wm / 2, (ys[0] + ys[-1]) / 2.0 - Hm / 2)
            T["_inkw"] = max(T.get("_inkw", 0), int(xs[-1] - xs[0] + 1))
        else:
            T["_offsets"][li] = (0.0, 0.0)
    proc.wait()
    for T in texts:
        first = [o for o in T["_offsets"] if o is not None]
        T["_offset"] = first[0] if first else (0.0, 0.0)
