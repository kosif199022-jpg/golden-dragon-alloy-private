"""Helpers of runners/fam_skills_part2.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import json
import re
import subprocess


FONTS = Path(__import__("os").environ.get("KOSIF_FONTS") or Path.home() / "kosif-tool" / ".claude" / "skills" / "kosif-superpowers" / "proofs" / "_shared" / "fonts")  # read-only asset in the old repo


CAIRO = FONTS / "Cairo[slnt,wght].ttf"


def jw(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def wt(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


def font(path=CAIRO, size=32):
    from PIL import ImageFont
    return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM)


def write_mp4(path, frames, fps=15):
    import numpy as np
    arr = [np.asarray(f, dtype=np.uint8) for f in frames]
    h, w = arr[0].shape[:2]
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "14",
                        "-pix_fmt", "yuv420p", str(path)], input=b"".join(a.tobytes() for a in arr),
                       capture_output=True, timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors="replace")[-300:])
    return Path(path)


def srt_time(t):
    ms = int(round(t * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def parse_srt(text):
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        a, b = lines[1].split(" --> ")
        f = lambda s: int(s[:2]) * 3600 + int(s[3:5]) * 60 + int(s[6:8]) + int(s[9:12]) / 1000
        out.append({"start": f(a), "end": f(b), "lines": lines[2:]})
    return out


def wrap_caption(words, max_chars=42, max_lines=2):
    """Greedy caption chunking: lines of at most max_chars, at most max_lines per caption."""
    caps, lines, cur = [], [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= max_chars:
            cur = (cur + " " + w).strip()
            continue
        lines.append(cur)
        cur = w
        if len(lines) == max_lines:
            caps.append(lines)
            lines = []
    if cur:
        lines.append(cur)
    if lines:
        caps.append(lines)
    return caps


def loudness(path):
    """Integrated loudness (LUFS) and true peak (dBTP) measured by ffmpeg's ebur128 filter."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=60)
    s = p.stderr[p.stderr.rfind("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", s).group(1))
    return i, tp


AR_DIAC = re.compile(r"[\u064B-\u0652\u0640]")


def ar_norm(t):
    t = AR_DIAC.sub("", t)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه")):
        t = t.replace(a, b)
    return t


def ar_syllables(line):
    """Count sung syllables in a fully vowelled Arabic line: one per short vowel, tanween or long vowel."""
    n = 0
    chars = list(line)
    for i, ch in enumerate(chars):
        if ch in "\u064E\u064F\u0650\u064B\u064C\u064D":  # fatha damma kasra + tanween
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            nn = chars[i + 2] if i + 2 < len(chars) else ""
            if nxt in "اوي" and ch in "\u064E\u064F\u0650" and nn != "\u0652":
                continue  # the long vowel is counted once (below); a vowel + sukun letter is a diphthong
            n += 1
        elif ch in "اى" and i > 0 and chars[i - 1] not in " ":
            n += 1
        elif ch in "وي" and i > 0 and chars[i - 1] in "\u064F\u0650":
            n += 1
    return n


PALETTE = {"outline": (24, 20, 37), "base": (62, 137, 72), "shadow": (38, 92, 66), "highlight": (99, 199, 77),
           "skin": (228, 166, 114), "eye": (255, 255, 255)}


def _sprite(direction, pose, size=32):
    from PIL import Image
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = im.load()
    P = PALETTE

    def rect(x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px[x, y] = c + (255,)
    leg = [0, 2, 0, -2][pose]
    rect(11, 8, 20, 17, P["base"])               # body
    rect(11, 8, 13, 10, P["highlight"])          # light from top-left
    rect(18, 14, 20, 17, P["shadow"])
    rect(12, 2, 19, 7, P["skin"])                # head
    ex = {"right": 17, "left": 13, "down": 15}[direction]
    px[ex, 4] = P["eye"] + (255,)
    rect(12, 18, 14, 25 + max(0, leg), P["shadow"])   # legs (pose moves them, sizes stay on model)
    rect(17, 18, 19, 25 - min(0, leg), P["shadow"])
    # 1px outline around every filled pixel
    filled = {(x, y) for y in range(size) for x in range(size) if px[x, y][3] == 255}
    for (x, y) in list(filled):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in filled and 0 <= q[0] < size and 0 <= q[1] < size:
                px[q] = P["outline"] + (255,)
    return im


FAKE_KEY = "sk" + "_" + "live" + "_" + "X" * 24


SEC_RULES = [
    ("secret-in-code", r"(sk_" r"live_|AK" r"IA)[A-Za-z0-9]{12,}", "S/I", 9.1, "confirmed", "move to environment / secret store and rotate"),
    ("sql-injection", r"execute\([^)]*[\"']\s*\+\s*\w+", "T", 9.8, "confirmed", "parameterised query"),
    ("weak-hash", r"hashlib\.(md5|sha1)\(", "I", 7.5, "confirmed", "scrypt/argon2 with salt"),
    ("missing-security-headers", r"def headers\((?:(?!Content-Security-Policy).)*?return resp", "I", 5.3, "probable", "add CSP and nosniff"),
]


def sec_scan(path):
    text = Path(path).read_text(encoding="utf-8")
    out = []
    for rid, rx, stride, cvss, conf, fix in SEC_RULES:
        for m in re.finditer(rx, text, re.S):
            out.append({"rule": rid, "file": Path(path).name, "line": text[:m.start()].count("\n") + 1, "stride": stride,
                        "cvss": cvss, "confidence": conf, "fix": fix})
    return out


def spring_sim(k, c, m=1.0, dt=1 / 10000, T=2.0):
    x, v, xs = 0.0, 0.0, []
    for _ in range(int(T / dt)):
        a = (-k * (x - 1) - c * v) / m
        v += a * dt
        x += v * dt
        xs.append(x)
    return xs


def settle_ms(xs, dt=1 / 10000, tol=0.02):
    for i in range(len(xs) - 1, -1, -1):
        if abs(xs[i] - 1) > tol:
            return (i + 1) * dt * 1000
    return 0.0


_AR1 = ["صفر", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة", "عشرة"]


_AR10 = {2: "عشرون", 3: "ثلاثون", 4: "أربعون", 5: "خمسون", 6: "ستون", 7: "سبعون", 8: "ثمانون", 9: "تسعون"}


_AR100 = {1: "مائة", 2: "مئتان", 3: "ثلاثمائة", 4: "أربعمائة", 5: "خمسمائة", 6: "ستمائة", 7: "سبعمائة", 8: "ثمانمائة", 9: "تسعمائة"}


def ar_words(n):
    """Cardinal number in Arabic words (masculine, nominative), 0..99999, as it is read aloud."""
    if n <= 10:
        return _AR1[n]
    if n == 11:
        return "أحد عشر"
    if n == 12:
        return "اثنا عشر"
    if n < 20:
        return _AR1[n - 10] + " عشر"
    if n < 100:
        o, t = n % 10, n // 10
        return (_AR1[o] + " و" if o else "") + _AR10[t]
    if n < 1000:
        h, r = divmod(n, 100)
        return _AR100[h] + (" و" + ar_words(r) if r else "")
    th, r = divmod(n, 1000)
    head = {1: "ألف", 2: "ألفان"}.get(th) or (ar_words(th) + (" آلاف" if th <= 10 else " ألفاً"))
    return head + (" و" + ar_words(r) if r else "")
