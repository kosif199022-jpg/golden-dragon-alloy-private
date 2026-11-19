#!/usr/bin/env python3
"""reference-lock (قفل المرجع): «نفس الخط» و«نفس الألوان» يعني نفسهم بالظبط، مش حاجة شبههم.

  lock NAME FILE... [--color "#hex"]... [--font "Family"]... [--text "نص ظاهر في المرجع" --crop x,y,w,h]
        يستخرج من المرجع الألوان (hex) والخطوط ويقفلهم في ~/.red-dragon/refs/NAME/lock.json
  show NAME            القيود كنص جاهز يتحط في الخطة أو البرومبت أو الكود
  verify NAME OUT...   [--text … --crop …] [--tol 10] [--allow "#hex"]  يقيس الناتج قدام القفل. 0 = مطابق، 1 = مش مطابق، 2 = محتاج عين
  fontmatch IMAGE --text "…" [--crop x,y,w,h] [--fonts-dir DIR]   يرتّب الخطوط المتثبتة حسب الشبه بالنص في الصورة
  list · selftest

المرجع ممكن يكون: صورة، فيديو (5 فريمات)، PDF، CSS/HTML/SVG/ASS/JSON (ألوان وخطوط بالحرف)، أو ملف خط .ttf/.otf.
ألوان وخطوط الملفات النصية «مؤكدة». خط الصورة «مرشّح» لحد ما يتأكد بالعين أو من صاحب الشغل. ممنوع البديل من غير ما يقول.
"""
import argparse, hashlib, json, math, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HOME = Path(os.environ.get("RED_DRAGON_HOME") or Path.home() / ".red-dragon") / "refs"
IMG = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
VID = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
TXT = {".css", ".html", ".htm", ".svg", ".ass", ".ssa", ".json", ".txt", ".md", ".js", ".jsx", ".tsx", ".ts", ".xml", ".srt", ".vtt", ".py"}
FONTF = {".ttf", ".otf", ".ttc", ".woff", ".woff2"}


# ------------------------------------------------------------------ colour maths
def hx(rgb):
    return "#%02X%02X%02X" % tuple(int(round(c)) for c in rgb[:3])


def rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lab(c):
    def f(u):
        u /= 255.0
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in c)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    t = lambda v: v ** (1 / 3) if v > 0.008856 else 7.787 * v + 16 / 116
    fx, fy, fz = t(x), t(y), t(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def de(a, b):
    """ΔE (CIE76). تحت 2: العين ماتفرقش. تحت 10: نفس اللون بعد ضغط الصورة. فوق 15: لون تاني."""
    return math.dist(lab(rgb(a) if isinstance(a, str) else a), lab(rgb(b) if isinstance(b, str) else b))


def palette_img(im, k=8):
    from PIL import Image
    im = im.convert("RGB")
    im.thumbnail((240, 240))
    q = im.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    tot = sum(c for c, _ in counts)
    out = []
    for c, i in counts:
        col = hx(pal[i * 3:i * 3 + 3])
        for o in out:                                   # merge near-duplicates
            if de(o["hex"], col) < 6:
                o["share"] += c / tot
                break
        else:
            out.append({"hex": col, "share": c / tot})
    for o in out:
        o["share"] = round(o["share"], 3)
    return sorted(out, key=lambda o: -o["share"])


def frames(path, n=5):
    tmp = Path(tempfile.mkdtemp(prefix="reflock-"))
    try:
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                 capture_output=True, text=True).stdout.strip() or 0)
    except Exception:
        d = 0
    outs = []
    for i in range(n):
        t = d * (i + 0.5) / n if d else 0
        f = tmp / f"f{i}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", str(f)], capture_output=True)
        if f.is_file():
            outs.append(f)
        if not d:
            break
    return outs


def pdf_pages(path):
    tmp = Path(tempfile.mkdtemp(prefix="reflock-"))
    subprocess.run(["pdftoppm", "-r", "40", "-l", "3", "-png", str(path), str(tmp / "p")], capture_output=True)
    return sorted(tmp.glob("p*.png"))


def merge_palettes(pals):
    out = []
    for pal in pals:
        for c in pal:
            for o in out:
                if de(o["hex"], c["hex"]) < 6:
                    o["share"] += c["share"] / len(pals)
                    break
            else:
                out.append({"hex": c["hex"], "share": c["share"] / len(pals)})
    for o in out:
        o["share"] = round(o["share"], 3)
    return sorted(out, key=lambda o: -o["share"])


# ------------------------------------------------------------------ text sources: exact values
def text_colors(t):
    cols = []
    for m in re.finditer(r"(?<![\w&])#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", t):
        cols.append(hx(rgb(m.group(1))))
    for m in re.finditer(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})", t):
        cols.append(hx(tuple(int(x) for x in m.groups())))
    for m in re.finditer(r"&H([0-9A-Fa-f]{2})?([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})&?", t):   # ASS is &HAABBGGRR
        b, g, r = (int(x, 16) for x in m.groups()[1:])
        cols.append(hx((r, g, b)))
    seen, out = set(), []
    for c in cols:
        if c not in seen:
            seen.add(c)
            out.append({"hex": c, "share": round(cols.count(c) / len(cols), 3), "exact": True})
    return sorted(out, key=lambda o: -o["share"])


GENERIC = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "inherit", "initial", "unset", "ui-sans-serif", "ui-serif", "-apple-system", "blinkmacsystemfont"}


def text_fonts(t):
    fams = []
    for m in re.finditer(r"font-family\s*[:=]\s*([\"']?)([^;\"'>}\n]+)", t, re.I):
        fams += [x.strip().strip("\"'") for x in m.group(2).split(",")]
    fams += re.findall(r"\"(?:fontFamily|fFamily|font_family|fontName)\"\s*:\s*\"([^\"]+)\"", t)
    for m in re.finditer(r"^Style:\s*[^,]*,([^,]+),", t, re.M):          # ASS: Style: Name,Fontname,...
        fams.append(m.group(1).strip())
    for m in re.finditer(r"\\fn([^\\}]+)", t):                               # ASS override {\fnName}
        fams.append(m.group(1).strip())
    out = []
    for f in fams:
        if f and f.lower() not in GENERIC and f not in out and not f.startswith("var("):
            out.append(f)
    return out


def _tool(cmd):
    """stdout of a helper (fontconfig / poppler), or "" when it isn't installed. v3.3.1: on Windows without fontconfig,
    the Fonts-folder fallback called fc-scan and crashed with FileNotFoundError instead of using the file name."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def font_file_family(p):
    return (_tool(["fc-scan", "--format", "%{family[0]}\n", str(p)]).strip().splitlines() or [Path(p).stem])[0]


def pdf_fonts(p):
    out = []
    for line in _tool(["pdffonts", str(p)]).splitlines()[2:]:
        n = line.split()[0] if line.split() else ""
        n = re.sub(r"^[A-Z]{6}\+", "", n)                                    # subset prefix
        if n and n not in out:
            out.append(n)
    return out


def installed(family):
    return (_tool(["fc-list", f":family={family}", "file"]).strip().splitlines() or [""])[0].rstrip(":").strip()


# ------------------------------------------------------------------ font matching from pixels
def _bin(im):
    from PIL import Image
    import numpy as np
    g = np.asarray(im.convert("L"), dtype=float)
    border = np.concatenate([g[0], g[-1], g[:, 0], g[:, -1]]).mean()
    thr = (g.min() + g.max()) / 2
    ink = g < thr if border > thr else g > thr
    ys, xs = np.nonzero(ink)
    if not len(xs):
        return None
    return ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _render(text, font_file, h):
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(font_file, max(8, int(h * 1.6)))
    kw = {}
    try:
        from PIL import features
        if features.check("raqm") and re.search(r"[؀-ۿ]", text):
            kw = {"direction": "rtl", "language": "ar"}
    except Exception:
        pass
    box = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f, **kw)
    im = Image.new("L", (box[2] - box[0] + 40, box[3] - box[1] + 40), 255)
    ImageDraw.Draw(im).text((20 - box[0], 20 - box[1]), text, font=f, fill=0, **kw)
    return im


def _score(a, b):
    from PIL import Image
    import numpy as np
    H, W = 64, max(8, int(64 * a.shape[1] / a.shape[0]))
    ra = np.asarray(Image.fromarray(a.astype("uint8") * 255).resize((W, H))) > 127
    rb = np.asarray(Image.fromarray(b.astype("uint8") * 255).resize((W, H))) > 127
    from PIL import ImageFilter
    ba = np.asarray(Image.fromarray(ra.astype("uint8") * 255).filter(ImageFilter.GaussianBlur(1.5)), dtype=float)
    bb = np.asarray(Image.fromarray(rb.astype("uint8") * 255).filter(ImageFilter.GaussianBlur(1.5)), dtype=float)
    ba, bb = ba - ba.mean(), bb - bb.mean()
    iou = max(0.0, float((ba * bb).sum() / max(1e-9, math.sqrt((ba * ba).sum() * (bb * bb).sum()))))   # blurred correlation, robust to anti-aliasing
    ar = abs(math.log((a.shape[1] / a.shape[0]) / (b.shape[1] / b.shape[0])))   # width/height ratio
    return round(float(iou * math.exp(-1.5 * ar)), 4)


def font_candidates(text, extra_dirs=()):
    files = {}
    q = ":lang=ar" if re.search(r"[؀-ۿ]", text) else ""
    try:
        out = subprocess.run(["fc-list", q or ":", "family", "style", "file"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace").stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    for line in out.splitlines():
        # Windows paths carry a drive colon ("C:/WINDOWS/fonts/x.ttf: Family"), so split after the extension
        m = re.match(r"^(.+?\.(?:ttf|otf|ttc))\s*:\s*(.*)$", line.strip(), re.I)
        if m:
            files.setdefault(m.group(1), m.group(2).split(":")[0].split(",")[0].strip())
    if not files and os.name == "nt":
        extra_dirs = tuple(extra_dirs) + tuple(d for d in (Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
                                                           Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts") if d.is_dir())
    for d in extra_dirs:
        for fp in Path(d).rglob("*"):
            if fp.suffix.lower() in (".ttf", ".otf", ".ttc"):
                files.setdefault(str(fp), font_file_family(fp))
    return files


def fontmatch(image, text, crop=None, extra_dirs=(), top=5):
    from PIL import Image
    im = Image.open(image)
    if crop:
        x, y, w, h = crop
        im = im.crop((x, y, x + w, y + h))
    ink = _bin(im)
    if ink is None:
        return []
    res = []
    for fp, fam in font_candidates(text, extra_dirs).items():
        try:
            r = _bin(_render(text, fp, ink.shape[0]))
        except Exception:
            continue
        if r is not None:
            res.append({"family": fam, "file": fp, "score": _score(ink, r)})
    best = {}
    for r in sorted(res, key=lambda r: -r["score"]):
        best.setdefault(r["family"], r)
    return sorted(best.values(), key=lambda r: -r["score"])[:top]


def parse_crop(s):
    return tuple(int(v) for v in s.split(",")) if s else None


# ------------------------------------------------------------------ extract
def extract(paths, text=None, crop=None, extra_dirs=()):
    colors, fonts, notes = [], [], []
    raster_pals = []
    for p in map(Path, paths):
        ext = p.suffix.lower()
        if ext in FONTF:
            fonts.append({"family": font_file_family(p), "file": str(p), "status": "مؤكد", "source": p.name})
        elif ext in TXT:
            t = p.read_text(encoding="utf-8", errors="replace")
            colors += [dict(c, source=p.name) for c in text_colors(t)]
            fonts += [{"family": f, "file": installed(f), "status": "مؤكد", "source": p.name} for f in text_fonts(t)]
        elif ext == ".pdf":
            fonts += [{"family": f, "file": installed(f), "status": "مؤكد", "source": p.name} for f in pdf_fonts(p)]
            raster_pals.append((p.name, merge_palettes([palette_img(__import__("PIL.Image").Image.open(f)) for f in pdf_pages(p)] or [[]])))
        elif ext in IMG or ext in VID:
            from PIL import Image
            fr = [p] if ext in IMG else frames(p)
            raster_pals.append((p.name, merge_palettes([palette_img(Image.open(f)) for f in fr]) if fr else []))
            if text and fr:
                c = fontmatch(fr[0], text, crop, extra_dirs)
                if c:
                    fonts.append({"family": c[0]["family"], "file": c[0]["file"], "status": "مرشّح", "score": c[0]["score"],
                                  "others": [f"{x['family']} ({x['score']})" for x in c[1:4]], "source": p.name})
                    notes.append(f"خط {p.name} اتعرف بالشبه مش بالاسم: {c[0]['family']} ({c[0]['score']}). أكّده بالعين أو اسأل صاحب الشغل قبل ما تكمّل.")
            elif not text:
                notes.append(f"{p.name}: صورة/فيديو. الخط مايتعرفش من غير --text \"النص اللي فيها\" (و --crop لو فيه نصوص كتير). ماتخمّنش خط.")
        else:
            notes.append(f"{p.name}: نوع مش معروف، اتساب.")
    for name, pal in raster_pals:
        colors += [{"hex": c["hex"], "share": c["share"], "exact": False, "source": name} for c in pal if c["share"] >= 0.02]
    for f in fonts:
        if not f.get("file"):
            notes.append(f"الخط «{f['family']}» مش متثبت هنا. هاته (من صاحب الشغل أو fonts fetch). ممنوع تحط بداله خط تاني.")
    return colors, fonts, notes


def sha(p):
    try:
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
    except Exception:
        return ""


def cmd_lock(a):
    colors, fonts, notes = extract(a.files, a.text, parse_crop(a.crop), a.fonts_dir or ())
    colors = [{"hex": hx(rgb(c)), "share": 1.0, "exact": True, "source": "صاحب الشغل"} for c in a.color] + colors
    fonts = [{"family": f, "file": installed(f), "status": "مؤكد", "source": "صاحب الشغل"} for f in a.font] + fonts
    lock = {"name": a.name, "refs": [{"path": str(Path(p).resolve()), "sha": sha(p)} for p in a.files], "colors": colors,
            "fonts": fonts, "text": a.text, "crop": a.crop, "notes": notes}
    d = HOME / a.name
    d.mkdir(parents=True, exist_ok=True)
    (d / "lock.json").write_text(json.dumps(lock, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.json:
        print(json.dumps(lock, ensure_ascii=False, indent=1))
    else:
        print(render(lock))
        print(f"\n🔒 اتقفل: {d / 'lock.json'}")


def load(name):
    p = HOME / name / "lock.json" if not str(name).endswith(".json") else Path(name)
    if not p.is_file():
        sys.exit(f"مفيش قفل باسم {name}. اعمل الأول: reflock.py lock {name} <المرجع>")
    return json.loads(p.read_text(encoding="utf-8"))


def render(lock):
    L = [f"## 🔒 قيود المرجع «{lock['name']}» (إلزامية، مش اقتراح)"]
    if lock["fonts"]:
        L.append("**الخط:**")
        for f in lock["fonts"]:
            st = f["status"] + (f" · شبه {f['score']} · بدائل محتملة: {', '.join(f.get('others', []))}" if f.get("score") is not None else "")
            L.append(f"- `{f['family']}` ({st}) ← {f['file'] or 'مش متثبت: هاته الأول'}")
    else:
        L.append("**الخط:** مااتعرفش من المرجع. اسأل صاحب الشغل عن اسمه أو هات النص اللي فيه. ماتختارش خط من عندك.")
    if lock["colors"]:
        L.append("**الألوان (hex بالظبط):**")
        for c in lock["colors"][:12]:
            L.append(f"- `{c['hex']}` · {round(c['share'] * 100)}% · {'بالحرف' if c.get('exact') else 'من البكسل'} · {c['source']}")
    L += ["**القواعد:**",
          "- استخدم الـ hex والخط دول بالاسم في الكود أو البرومبت. ممنوع «قريب منه» أو «نفس الإحساس».",
          "- لو حاجة مش متاحة (خط مش متثبت، لون مش ظاهر)، قول وقف واسأل. ماتبدّلش في السكات.",
          f"- قبل ما تقول «خلص»: `rd.py ref verify {lock['name']} <الناتج>` لازم يرجع ✅."]
    L += [f"- ⚠ {n}" for n in lock.get("notes", [])]
    return "\n".join(L)


def cmd_show(a):
    print(render(load(a.name)))


def verify(lock, outs, text=None, crop=None, tol=10.0, allow=(), extra_dirs=()):
    colors, fonts, _ = extract(outs, None, None)
    raster = [c for c in colors if not c.get("exact")]
    exact = [c for c in colors if c.get("exact")]
    fails, warns, oks = [], [], []
    want = [c for c in lock["colors"] if c.get("exact") or c["share"] >= 0.05]
    for c in want:
        pool = (exact + raster) if exact else raster
        if not pool:
            warns.append(f"اللون {c['hex']}: مالقيتش ألوان في الناتج أقيس عليها")
            continue
        best = min(pool, key=lambda o: de(o["hex"], c["hex"]))
        d = de(best["hex"], c["hex"])
        lim = 0.5 if (c.get("exact") and best.get("exact")) else tol
        (oks if d <= lim else fails).append(f"اللون {c['hex']}: أقرب حاجة في الناتج {best['hex']} (ΔE {d:.1f}، الحد {lim})")
    for o in (exact if exact else raster):
        if o.get("share", 0) >= (0.0 if o.get("exact") else 0.08):
            d = min((de(o["hex"], c["hex"]) for c in lock["colors"]), default=99)
            if d > 15 and not any(de(o["hex"], x) <= 6 for x in allow):
                fails.append(f"لون جديد مش في المرجع: {o['hex']} ({round(o['share'] * 100)}%، أقرب لون مقفول على بعد ΔE {d:.0f}). لو مقصود: --allow \"{o['hex']}\"")
    lf = [f["family"].lower() for f in lock["fonts"]]
    if lf:
        if fonts:
            for f in fonts:
                (oks if f["family"].lower() in lf else fails).append(f"الخط في الناتج «{f['family']}» " + ("= المرجع" if f["family"].lower() in lf else f"≠ المرجع ({', '.join(x['family'] for x in lock['fonts'])})"))
        elif text and any(Path(p).suffix.lower() in IMG | VID for p in outs):
            p = Path(outs[0])
            img = p if p.suffix.lower() in IMG else (frames(p) or [None])[0]
            c = fontmatch(img, text, crop, extra_dirs) if img else []
            if c and c[0]["family"].lower() in lf:
                oks.append(f"الخط في الصورة أقرب لـ «{c[0]['family']}» ({c[0]['score']}) = المرجع")
            else:
                fails.append(f"الخط في الصورة أقرب لـ «{c[0]['family'] if c else '؟'}» مش «{lock['fonts'][0]['family']}»")
        else:
            warns.append("الخط: الناتج صورة/فيديو. شغّل تاني بـ --text \"النص اللي فيه\" --crop x,y,w,h، أو بُص بعينك وقارن الحروف المميزة (ك، ه، ي، الأرقام)")
    code = 1 if fails else (2 if warns else 0)
    return {"ok": code == 0, "code": code, "fails": fails, "warns": warns, "oks": oks}


def cmd_verify(a):
    lock = load(a.name)
    r = verify(lock, a.outputs, a.text or lock.get("text"), parse_crop(a.crop or lock.get("crop")), a.tol, [hx(rgb(x)) for x in a.allow], a.fonts_dir or ())
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print({0: "✅ مطابق للمرجع", 1: "❌ مش مطابق للمرجع: صلّح قبل التسليم", 2: "⚠ محتاج عين: فيه حاجة ماتقاستش"}[r["code"]])
        for x in r["fails"]:
            print("  ❌", x)
        for x in r["warns"]:
            print("  ⚠", x)
        for x in r["oks"]:
            print("  ✓", x)
    if r["fails"]:
        HOME.mkdir(parents=True, exist_ok=True)
        with open(HOME / "misses.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"lock": a.name, "outputs": a.outputs, "fails": r["fails"]}, ensure_ascii=False) + "\n")
    sys.exit(r["code"])


def cmd_fontmatch(a):
    r = fontmatch(a.image, a.text, parse_crop(a.crop), a.fonts_dir or ())
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else "\n".join(f"{i}. {x['family']} — {x['score']} — {x['file']}" for i, x in enumerate(r, 1)) or "مالقيتش نص في الصورة")


def cmd_list(a):
    for d in sorted(HOME.glob("*/lock.json")):
        l = json.loads(d.read_text(encoding="utf-8"))
        print(f"{l['name']}: {len(l['colors'])} لون، خطوط: {', '.join(f['family'] for f in l['fonts']) or '—'}")


def cmd_selftest(a):
    from PIL import Image, ImageDraw
    global HOME
    tmp = Path(tempfile.mkdtemp(prefix="reflock-st-"))
    HOME = tmp / "refs"
    ok, bad = 0, []

    def t(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)
    cands = font_candidates("Hello")
    fams = {}
    for fp, fam in cands.items():
        fams.setdefault(fam, fp)
    picks = list(fams.items())[:4]
    t("fonts available", len(picks) >= 2)
    txt = "Red Dragon 2026"
    ref = tmp / "ref.png"
    im = Image.new("RGB", (900, 300), "#1B2A49")
    ImageDraw.Draw(im).rectangle((0, 220, 900, 300), fill="#E63946")
    tim = _render(txt, picks[0][1], 45).convert("L")
    im.paste(Image.new("RGB", tim.size, "#F1FAEE"), (60, 40), tim.point(lambda v: 255 - v))
    im.save(ref)
    colors, fonts, _ = extract([ref], txt, (40, 20, 820, 180))
    t("palette has navy", any(de(c["hex"], "#1B2A49") < 6 for c in colors))
    t("palette has red", any(de(c["hex"], "#E63946") < 6 for c in colors))
    t("font from pixels = rendered font", bool(fonts) and fonts[0]["family"] == picks[0][0])
    css = tmp / "brand.css"
    css.write_text("body{font-family:'DejaVu Sans',sans-serif;color:#1b2a49;background:rgb(230,57,70)}", encoding="utf-8")
    c2, f2, _ = extract([css])
    t("css exact colours", [c["hex"] for c in c2] == ["#1B2A49", "#E63946"])
    t("css font", [f["family"] for f in f2] == ["DejaVu Sans"])
    ass = tmp / "subs.ass"
    ass.write_text("Style: Default,Cairo,60,&H00EEFAF1,&H000000FF\n", encoding="utf-8")
    c3, f3, _ = extract([ass])
    t("ass font + BGR colour", f3 and f3[0]["family"] == "Cairo" and c3[0]["hex"] == "#F1FAEE")
    lock = {"name": "t", "colors": [dict(c, exact=False) for c in colors], "fonts": fonts, "text": txt, "crop": None}
    t("same image passes", verify(lock, [ref], txt, (40, 20, 820, 180))["code"] == 0)
    off = tmp / "off.png"
    im2 = Image.new("RGB", (900, 300), "#2E7D32")
    ImageDraw.Draw(im2).rectangle((0, 220, 900, 300), fill="#E63946")
    im2.paste(Image.new("RGB", tim.size, "#F1FAEE"), (60, 40), tim.point(lambda v: 255 - v))
    im2.save(off)
    r = verify(lock, [off], txt, (40, 20, 820, 180))
    t("changed background fails", r["code"] == 1 and any("#1B2A49" in x for x in r["fails"]))
    other = tmp / "other.png"
    im3 = Image.new("RGB", (900, 300), "#1B2A49")
    ImageDraw.Draw(im3).rectangle((0, 220, 900, 300), fill="#E63946")
    tim3 = _render(txt, picks[1][1], 45).convert("L")
    im3.paste(Image.new("RGB", tim3.size, "#F1FAEE"), (60, 40), tim3.point(lambda v: 255 - v))
    im3.save(other)
    t("different font fails", verify(lock, [other], txt, (40, 20, 820, 180))["code"] == 1)
    css_out = tmp / "out.css"
    css_out.write_text("h1{font-family:'Arial';color:#1B2A4A}", encoding="utf-8")
    lk2 = {"name": "c", "colors": c2, "fonts": f2}
    r2 = verify(lk2, [css_out])
    t("css near-colour + wrong font fail", r2["code"] == 1 and len(r2["fails"]) >= 2)
    shutil.rmtree(tmp, ignore_errors=True)
    total = ok + len(bad)
    print(f"{ok}/{total} reference-lock checks" + (f" · فشل: {', '.join(bad)}" if bad else ""))
    sys.exit(0 if not bad else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("lock"); s.add_argument("name"); s.add_argument("files", nargs="*")
    s.add_argument("--color", action="append", default=[]); s.add_argument("--font", action="append", default=[])
    s.add_argument("--text"); s.add_argument("--crop"); s.add_argument("--fonts-dir", action="append"); s.add_argument("--json", action="store_true")
    s.set_defaults(f=cmd_lock)
    s = sub.add_parser("show"); s.add_argument("name"); s.set_defaults(f=cmd_show)
    s = sub.add_parser("verify"); s.add_argument("name"); s.add_argument("outputs", nargs="+"); s.add_argument("--text"); s.add_argument("--crop")
    s.add_argument("--tol", type=float, default=10.0); s.add_argument("--allow", action="append", default=[]); s.add_argument("--fonts-dir", action="append")
    s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_verify)
    s = sub.add_parser("fontmatch"); s.add_argument("image"); s.add_argument("--text", required=True); s.add_argument("--crop")
    s.add_argument("--fonts-dir", action="append"); s.add_argument("--json", action="store_true"); s.set_defaults(f=cmd_fontmatch)
    s = sub.add_parser("list"); s.set_defaults(f=cmd_list)
    s = sub.add_parser("selftest"); s.set_defaults(f=cmd_selftest)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
