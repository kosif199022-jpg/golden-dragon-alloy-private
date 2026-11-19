#!/usr/bin/env python3
"""codekit: the 12 "video from code" tools, as one toolbox for the Black Dragon.

Four lines (the metro map from the reel):
  1. builds the video : Remotion, HyperFrames, Motion Canvas
  2. shapes           : Three.js, Manim, Rough.js
  3. motion           : GSAP, anime.js, mo.js
  4. audio and file   : WhisperX, auto-editor, FFmpeg

Commands:
  status [--json]                    what is here, where, which version, which licence
  map                                the metro map in Arabic, one "use it when" line per tool
  install NAME|all [--dest DIR] [--run] [--allow-large]
                                     print the install commands; run them only with --run
  demo NAME OUT_DIR [--title TEXT]   write a tiny seek-driven demo page (or print the command)
  vendor-gsap DEST                   copy gsap.min.js from your installed npm copy

Python standard library only. Probing is read-only. Nothing is installed, downloaded
or spent unless you pass --run.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor"
DEMOS = HERE / "demos"
MIN_FREE_MB = 250
GSAP_LICENCE_URL = "https://gsap.com/standard-license"

LINES = {
    1: ("بيبني الفيديو", "builds the video"),
    2: ("الأشكال", "shapes"),
    3: ("الحركة", "motion"),
    4: ("الصوت والملف", "audio and file"),
}

DRAGON_ENGINE = "محرك التنين نفسه (صفحة HTML بتتحرك بالـ seek وتتصور MP4) + `tool mono`"

# kind: vendored (file in vendor/), npm (node_modules), pip (installed distribution), bin (program on PATH)
TOOLS = [
    {"id": "remotion", "line": 1, "name": "Remotion", "kind": "npm", "pkg": "remotion",
     "use": "فيديو كامل بكود React",
     "when": "استخدمه لما الفيديو كله مكوّنات React وعايز مشروع فيديو كبير يتعدّل بالكود.",
     "licence": "Remotion License: مجاني للأفراد وللشركات لحد 3 أشخاص، وأكبر من كده برخصة مدفوعة",
     "equiv": DRAGON_ENGINE,
     "install": [["npm", "install", "remotion", "@remotion/cli", "@remotion/bundler", "react", "react-dom"]],
     "size": "حوالي 300-500 ميجا مع المتصفح اللي بينزّله أول رندر"},
    {"id": "hyperframes", "line": 1, "name": "HyperFrames", "kind": "npm", "pkg": "hyperframes",
     "use": "فيديو من صفحات HTML",
     "when": "استخدمه لما عايز تركيبة HTML جاهزة برندر MP4 وفحص (lint / check) من سطر الأوامر.",
     "licence": "Apache-2.0 (مفتوح المصدر)",
     "equiv": DRAGON_ENGINE,
     "install": [["npm", "install", "hyperframes"]],
     "size": "عشرات الميجات"},
    {"id": "motion-canvas", "line": 1, "name": "Motion Canvas", "kind": "npm", "pkg": "@motion-canvas/core",
     "use": "شرح متحرك بكود TypeScript",
     "when": "استخدمه لشرح تقني خطوة بخطوة (generators) مع محرّر بيعرض الخط الزمني.",
     "licence": "MIT (مفتوح المصدر)",
     "equiv": DRAGON_ENGINE,
     "install": [["npm", "install", "@motion-canvas/core", "@motion-canvas/2d",
                  "@motion-canvas/vite-plugin", "@motion-canvas/ui", "vite"]],
     "size": "حوالي 150 ميجا مع vite"},
    {"id": "three", "line": 2, "name": "Three.js", "kind": "vendored", "pkg": "three",
     "file": "three/three.min.js", "licence_file": "three/LICENSE", "version": "0.187.0",
     "use": "مجسمات ثلاثية الأبعاد في المتصفح",
     "when": "استخدمه لما اللقطة فيها مجسم 3D أو كاميرا بتلف أو إضاءة حقيقية.",
     "licence": "MIT (مفتوح المصدر)", "equiv": "",
     "install": [["npm", "install", "three"]], "size": "النسخة المرفقة 730 كيلو"},
    {"id": "manim", "line": 2, "name": "Manim", "kind": "pip", "pkg": "manim",
     "use": "رسوم رياضية ومعادلات متحركة (بايثون)",
     "when": "استخدمه لشرح رياضة أو فيزياء: معادلات، منحنيات، تحويل شكل لشكل.",
     "licence": "MIT (مفتوح المصدر)",
     "equiv": "أدوات الفيزياء والرياضة في التنين (tools/physics_math)",
     "install": [["pip", "install", "manim"]],
     "size": "حوالي 200-300 ميجا، ومحتاج مكتبات pango و cairo و ffmpeg؛ يتسطّب على جهازك"},
    {"id": "rough", "line": 2, "name": "Rough.js", "kind": "vendored", "pkg": "roughjs",
     "file": "roughjs/rough.js", "licence_file": "roughjs/LICENSE", "version": "4.6.6",
     "use": "أشكال مرسومة كأنها بالإيد",
     "when": "استخدمه لما عايز خط اسكتش أو سبورة: مربعات ودواير وأسهم مهزوزة.",
     "licence": "MIT (مفتوح المصدر)", "equiv": "",
     "install": [["npm", "install", "roughjs"]], "size": "النسخة المرفقة 28 كيلو"},
    {"id": "gsap", "line": 3, "name": "GSAP", "kind": "npm", "pkg": "gsap",
     "use": "خط زمني للحركة في الصفحة",
     "when": "استخدمه لما الحركة متسلسلة ودقيقة: دخول، تتابع، إيقاع على الكلام.",
     "licence": "مجاني للكل برخصة GSAP القياسية بدون مقابل (مش مفتوح المصدر): " + GSAP_LICENCE_URL,
     "equiv": "", "install": [["npm", "install", "gsap"]],
     "size": "حوالي 6 ميجا؛ مش مرفق هنا، انسخه بأمر vendor-gsap"},
    {"id": "anime", "line": 3, "name": "anime.js", "kind": "vendored", "pkg": "animejs",
     "file": "animejs/anime.umd.min.js", "licence_file": "animejs/LICENSE.md", "version": "4.5.0",
     "use": "حركة خفيفة لعناصر الصفحة و SVG",
     "when": "استخدمه لحركات بسيطة وسريعة: stagger، رسم خط SVG، أرقام بتعدّ.",
     "licence": "MIT (مفتوح المصدر)", "equiv": "",
     "install": [["npm", "install", "animejs"]], "size": "النسخة المرفقة 118 كيلو"},
    {"id": "mojs", "line": 3, "name": "mo.js", "kind": "vendored", "pkg": "@mojs/core",
     "file": "mojs/mo.umd.js", "licence_file": "mojs/LICENSE.md", "version": "1.3.0",
     "use": "فرقعات وأشكال موشن جاهزة",
     "when": "استخدمه للمسة: burst، دايرة بتتفتح، شرارة عند ظهور كلمة.",
     "licence": "MIT (مفتوح المصدر)", "equiv": "",
     "install": [["npm", "install", "@mojs/core"]], "size": "النسخة المرفقة 121 كيلو"},
    {"id": "whisperx", "line": 4, "name": "WhisperX", "kind": "pip", "pkg": "whisperx",
     "use": "توقيت كل كلمة في الصوت",
     "when": "استخدمه لما عايز كابشن كلمة بكلمة بتوقيت مظبوط ومين بيتكلم.",
     "licence": "BSD-2-Clause (مفتوح المصدر)",
     "equiv": "faster-whisper (محرك WhisperX نفسه) بتوقيت الكلمات: word_timestamps=True",
     "fallback_pip": "faster-whisper",
     "install": [["pip", "install", "whisperx"]], "large": True,
     "size": "كبير: بينزّل torch (حوالي 2-5 جيجا)؛ يتسطّب على جهازك بس، ومش هيتنفذ من غير --run و --allow-large"},
    {"id": "auto-editor", "line": 4, "name": "auto-editor", "kind": "pip", "pkg": "auto-editor",
     "bin": "auto-editor",
     "use": "قص السكتات من التسجيل",
     "when": "استخدمه لقص السكوت من تسجيل كلام، وسيب هامش (--margin) عشان الكلام مايتقطّعش.",
     "licence": "Unlicense (ملكية عامة)", "equiv": "",
     "install": [["pip", "install", "auto-editor"]], "size": "حوالي 50 ميجا"},
    {"id": "ffmpeg", "line": 4, "name": "FFmpeg", "kind": "bin", "bin": "ffmpeg",
     "use": "تحويل وتقطيع ودمج الصوت والفيديو",
     "when": "استخدمه لأي حاجة في الملف نفسه: ترميز، قص، دمج صوت، استخراج فريمات.",
     "licence": "LGPL/GPL (مفتوح المصدر)",
     "equiv": "معيار التصدير بتاع التنين بيتنفذ بيه",
     "install": [], "size": "Windows: winget install Gyan.FFmpeg — Linux: apt install ffmpeg"},
]

ALIASES = {
    "three.js": "three", "threejs": "three", "anime.js": "anime", "animejs": "anime",
    "mo.js": "mojs", "@mojs/core": "mojs", "rough.js": "rough", "roughjs": "rough",
    "motion_canvas": "motion-canvas", "motioncanvas": "motion-canvas", "@motion-canvas/core": "motion-canvas",
    "auto_editor": "auto-editor", "autoeditor": "auto-editor", "whisper": "whisperx",
}

CAVEATS = [
    "auto-editor: لو قصّيت كل سكتة الكلام هيطلع متقطّع؛ سيب هامش (--margin 0.3sec مثلاً).",
    "Remotion: مجاني للأفراد وللشركات لحد 3 أشخاص بس.",
    "GSAP: مجاني للكل (رخصة قياسية بدون مقابل)، بس مش مفتوح المصدر؛ عشان كده مش مرفق هنا.",
    "الباقي كله مفتوح المصدر.",
]

BROWSER_DEMOS = {
    # id: (demo page, library file name next to the page, default Arabic title)
    "three": ("three_demo.html", "three.min.js", "مجسم بيلف"),
    "anime": ("anime_demo.html", "anime.umd.min.js", "حركة خفيفة"),
    "mojs": ("mojs_demo.html", "mo.umd.js", "فرقعة موشن"),
    "rough": ("rough_demo.html", "rough.js", "رسم بالإيد"),
    "gsap": ("gsap_demo.html", "gsap.min.js", "خط زمني"),
}


def say(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:  # an old Windows console code page
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))


def tool(name: str):
    key = ALIASES.get(name.strip().lower(), name.strip().lower())
    for t in TOOLS:
        if t["id"] == key:
            return t
    return None


# ---------------------------------------------------------------- read-only probes

def node_roots(extra=()):
    """Every node_modules folder worth looking in: KOSIF_NODE_MODULES, then upwards from cwd and from here."""
    seen, out = set(), []

    def add(p):
        try:
            p = Path(p)
            key = str(p.resolve())
            if key not in seen and p.is_dir():
                seen.add(key)
                out.append(p)
        except OSError:
            pass

    for e in extra:
        add(Path(e) / "node_modules")
        add(e)
    for e in os.environ.get("KOSIF_NODE_MODULES", "").split(os.pathsep):
        if e:
            add(e)
    for start in (Path.cwd(), HERE):
        for d in (start, *start.parents):
            add(d / "node_modules")
    return [p for p in out if p.name == "node_modules"]


def npm_find(pkg: str, extra=(), only_extra=False):
    roots = node_roots(extra)
    if only_extra:  # the caller named a folder: look there and nowhere else
        named = {str(Path(e).resolve()) for e in extra} | {str((Path(e) / "node_modules").resolve()) for e in extra}
        roots = [r for r in roots if str(r.resolve()) in named]
    for root in roots:
        pj = root.joinpath(*pkg.split("/")) / "package.json"
        try:
            if pj.is_file():
                meta = json.loads(pj.read_text(encoding="utf-8"))
                return pj.parent, str(meta.get("version", "?"))
        except (OSError, ValueError):
            continue
    return None, None


def pip_version(dist: str):
    try:
        from importlib import metadata
        return metadata.version(dist)
    except Exception:
        return None


def bin_version(exe: str):
    path = shutil.which(exe)
    if not path:
        return None, None
    version = "?"
    if exe == "ffmpeg":  # the only one we start: it answers at once and writes nothing
        try:
            out = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10,
                                 encoding="utf-8", errors="replace").stdout
            m = re.search(r"ffmpeg version (\S+)", out)
            version = m.group(1) if m else "?"
        except (OSError, subprocess.SubprocessError):
            pass
    return path, version


def probe(t: dict) -> dict:
    row = {"id": t["id"], "line": t["line"], "line_name": LINES[t["line"]][0], "name": t["name"],
           "use": t["use"], "licence": t["licence"], "equivalent": t.get("equiv", ""),
           "found": False, "how": "مش متسطّب هنا", "where": "", "version": ""}
    try:
        if t["kind"] == "vendored":
            f = VENDOR / t["file"]
            if f.is_file():
                row.update(found=True, how="مرفق (vendored)", where=str(f), version=t["version"])
            else:
                d, v = npm_find(t["pkg"])
                if d:
                    row.update(found=True, how="node_modules", where=str(d), version=v)
        elif t["kind"] == "npm":
            d, v = npm_find(t["pkg"])
            if d:
                row.update(found=True, how="node_modules", where=str(d), version=v)
                if t["id"] == "remotion" and not npm_find("@remotion/cli")[0]:
                    row["note"] = "المكتبة موجودة بس @remotion/cli (أمر الرندر) مش متسطّب"
        elif t["kind"] == "pip":
            v = pip_version(t["pkg"])
            if v:
                row.update(found=True, how="pip", where=t["pkg"], version=v)
            elif t.get("bin") and shutil.which(t["bin"]):
                row.update(found=True, how="برنامج على PATH", where=shutil.which(t["bin"]), version="?")
            fb = t.get("fallback_pip")
            if fb and not row["found"]:
                fv = pip_version(fb)
                row["note"] = (f"البديل الشغال هنا: {fb} {fv}" if fv
                               else f"البديل {fb} كمان مش متسطّب (pip install {fb})")
                row["fallback"] = {"name": fb, "version": fv or ""}
        elif t["kind"] == "bin":
            p, v = bin_version(t["bin"])
            if p:
                row.update(found=True, how="برنامج على PATH", where=p, version=v)
    except Exception as exc:  # a probe must never break the report
        row["note"] = f"تعذّر الفحص: {exc.__class__.__name__}"
    return row


# ---------------------------------------------------------------- commands

def cmd_status(args) -> int:
    rows = [probe(t) for t in TOOLS]
    if args.json:
        data = {"schema": "kosif.codekit.status.v1", "count": len(rows),
                "lines": [{"line": n, "title_ar": LINES[n][0], "title_en": LINES[n][1],
                           "tools": [r["id"] for r in rows if r["line"] == n]} for n in sorted(LINES)],
                "tools": rows, "caveats": CAVEATS}
        say(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    say("عدّة فيديو الكود — 12 أداة على 4 خطوط")
    for n in sorted(LINES):
        say(f"\nالخط {n}: {LINES[n][0]}")
        for r in (r for r in rows if r["line"] == n):
            mark = "موجود" if r["found"] else "ناقص"
            ver = f" {r['version']}" if r["version"] else ""
            say(f"  [{mark}] {r['name']}{ver} — {r['use']}")
            say(f"      الطريقة: {r['how']}" + (f" ← {r['where']}" if r["where"] else ""))
            say(f"      الرخصة: {r['licence']}")
            if r["equivalent"]:
                say(f"      بديل التنين: {r['equivalent']}")
            if r.get("note"):
                say(f"      ملحوظة: {r['note']}")
    missing = [r["name"] for r in rows if not r["found"]]
    say("\nالناقص: " + ("، ".join(missing) if missing else "مفيش") +
        ("  (شوف: codekit.py install all)" if missing else ""))
    return 0


def cmd_map(_args) -> int:
    say("خريطة المترو: فيديو كامل من الكود")
    for n in sorted(LINES):
        names = " · ".join(t["name"] for t in TOOLS if t["line"] == n)
        say(f"\nالخط {n} — {LINES[n][0]}: {names}")
        for t in (t for t in TOOLS if t["line"] == n):
            say(f"  • {t['name']}: {t['when']}")
    say("\nخد بالك:")
    for c in CAVEATS:
        say(f"  - {c}")
    return 0


def real_command(cmd, dest):
    """Turn a display command into what would really run on this machine."""
    if cmd[0] == "pip":
        return [sys.executable, "-m", "pip", *cmd[1:]]
    if cmd[0] == "npm":
        exe = shutil.which("npm") or "npm"  # npm.cmd on Windows
        return [exe, cmd[1], "--prefix", str(dest), *cmd[2:]] if dest else [exe, *cmd[1:]]
    return list(cmd)


def free_mb(path) -> int:
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    return shutil.disk_usage(str(p)).free // (1024 * 1024)


def cmd_install(args) -> int:
    if args.name.lower() == "all":
        wanted = [t for t in TOOLS if not probe(t)["found"]]
        if not wanted:
            say("كل الأدوات موجودة، مفيش حاجة تتسطّب.")
            return 0
    else:
        t = tool(args.name)
        if not t:
            say(f"مش عارف الأداة دي: {args.name}. الأسماء: " + ", ".join(x["id"] for x in TOOLS))
            return 2
        wanted = [t]
    dest = Path(args.dest).resolve() if args.dest else None
    rc = 0
    for t in wanted:
        state = probe(t)
        say(f"\n{t['name']} — {'موجود ' + state['version'] if state['found'] else 'ناقص'}")
        say(f"  الحجم/ملاحظات: {t['size']}")
        if not t["install"]:
            say("  مفيش أمر npm/pip ليه؛ سطّبه من مدير الحزم بتاع النظام.")
            continue
        for cmd in t["install"]:
            shown = " ".join(real_command(cmd, dest) if dest and cmd[0] == "npm" else cmd)
            say(f"  الأمر: {shown}")
            if not args.run:
                continue
            if t.get("large") and not args.allow_large:
                say("  متنفّذش: الأداة دي كبيرة (torch). لو متأكد زوّد --allow-large، والأفضل على جهازك.")
                continue
            where = dest or Path.cwd()
            left = free_mb(where)
            if left < MIN_FREE_MB:
                say(f"  متنفّذش: المساحة الفاضية {left} ميجا بس (الحد الأدنى {MIN_FREE_MB}).")
                rc = 1
                continue
            if dest:
                dest.mkdir(parents=True, exist_ok=True)
            done = subprocess.run(real_command(cmd, dest))
            say(f"  النتيجة: {'تمام' if done.returncode == 0 else 'فشل (كود %d)' % done.returncode}")
            rc = rc or done.returncode
    if not args.run:
        say("\nده عرض بس: مفيش أي أمر اتنفّذ. للتنفيذ زوّد --run.")
    return rc


def gsap_source(extra=()):
    d, v = npm_find("gsap", extra, only_extra=bool(extra))
    if d and (d / "dist" / "gsap.min.js").is_file():
        return d / "dist" / "gsap.min.js", v
    return None, None


def cmd_vendor_gsap(args) -> int:
    src, v = gsap_source([args.source] if args.source else ())
    if not src:
        say("مش لاقي نسخة GSAP متسطّبة. سطّبها الأول: npm install gsap  (أو حدّد --from مجلد node_modules)")
        return 1
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest / "gsap.min.js")
    say(f"اتنسخ GSAP {v}: {dest / 'gsap.min.js'}")
    say(f"الرخصة: رخصة GSAP القياسية بدون مقابل (مش مفتوح المصدر) — {GSAP_LICENCE_URL}")
    return 0


def write_browser_demo(name: str, out: Path, title) -> int:
    page, lib, default_title = BROWSER_DEMOS[name]
    if name == "gsap":
        src, _v = gsap_source()
        if not src:
            say("GSAP مش متسطّب هنا، فمفيش ديمو. سطّبه: npm install gsap ثم أعد الأمر.")
            return 1
    else:
        src = VENDOR / tool(name)["file"]
        if not src.is_file():
            say(f"الملف المرفق ناقص: {src}")
            return 1
    out.mkdir(parents=True, exist_ok=True)
    text = (DEMOS / page).read_text(encoding="utf-8")
    text = text.replace("{{TITLE}}", html.escape(default_title if title is None else title))
    (out / page).write_text(text, encoding="utf-8", newline="\n")
    shutil.copyfile(src, out / lib)
    if name == "gsap":
        say(f"رخصة GSAP: {GSAP_LICENCE_URL}")
    else:
        lic = VENDOR / tool(name)["licence_file"]
        shutil.copyfile(lic, out / f"{lib}.LICENSE.txt")
    say(f"الصفحة: {out / page}")
    say(f"المكتبة جنبها: {out / lib}")
    say("تجربة (صورتين): node tools/render_html.cjs --in " + str(out / page) +
        " --out " + str(out / name) + " --stills 0.5,1.5")
    return 0


def cmd_demo(args) -> int:
    t = tool(args.name)
    if not t:
        say(f"مش عارف الأداة دي: {args.name}. الأسماء: " + ", ".join(x["id"] for x in TOOLS))
        return 2
    name, out = t["id"], Path(args.out_dir)
    if name in BROWSER_DEMOS:
        return write_browser_demo(name, out, args.title)
    if name == "manim":
        out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DEMOS / "manim_scene.py", out / "manim_scene.py")
        say(f"المشهد: {out / 'manim_scene.py'}")
        say("الرندر (على جهاز عليه Manim): manim -qh --fps 30 -r 1080,1920 manim_scene.py CodekitScene")
        if not pip_version("manim"):
            say("Manim مش متسطّب هنا: pip install manim (على جهازك).")
        return 0
    if name == "auto-editor":
        say("قص السكتات بهامش آمن (الكلام مايتقطّعش):")
        say("  auto-editor in.mp4 --margin 0.3sec --edit audio:threshold=0.04 --no-open -o out.mp4")
        say("الهامش بيسيب 0.3 ثانية قبل وبعد كل كلام. كبّره (0.5sec) لو الكلام لسه مخنوق.")
        say("معاينة من غير قص (أرقام بس): auto-editor in.mp4 --margin 0.3sec --edit audio:threshold=0.04 --preview")
        return 0
    if name == "remotion":
        d, v = npm_find("remotion")
        say("مشروع جديد: npx create-video@latest my-video")
        say("رندر: npx remotion render src/index.ts MyComp out.mp4")
        say(f"في الريبو: {'remotion ' + v + ' في ' + str(d) if d else 'مش متسطّب'}؛ وفيه starters/remotion.")
        say("الرخصة: مجاني للأفراد وللشركات لحد 3 أشخاص.")
        return 0
    if name == "hyperframes":
        d, v = npm_find("hyperframes")
        say("مشروع جديد: npx hyperframes init my-video")
        say("فحص ورندر: npx hyperframes check  ثم  npx hyperframes render")
        say(f"في الريبو: {'hyperframes ' + v + ' في ' + str(d) if d else 'مش متسطّب'}.")
        return 0
    if name == "motion-canvas":
        d, v = npm_find("@motion-canvas/core")
        say("مشروع جديد: npm init @motion-canvas@latest")
        say("تشغيل المحرّر: npm start   (الرندر من زرار RENDER في المحرّر)")
        say(f"هنا: {'@motion-canvas/core ' + v + ' في ' + str(d) if d else 'مش متسطّب (codekit.py install motion-canvas)'}.")
        return 0
    if name == "whisperx":
        say("على جهازك (بعد pip install whisperx):")
        say("  whisperx audio.wav --language ar --output_format json")
        say("البديل الشغال من غير torch (faster-whisper، توقيت كل كلمة):")
        say('  python -c "from faster_whisper import WhisperModel as M; s,_=M(\'small\').transcribe('
            '\'audio.wav\', word_timestamps=True); [print(w.start, w.end, w.word) for x in s for w in x.words]"')
        return 0
    if name == "ffmpeg":
        say("تصدير بمعيار التنين (1080x1920، 30 فريم، H.264 CRF 17، الصوت زي ما هو):")
        say("  ffmpeg -i in.mp4 -c:v libx264 -profile:v high -preset slow -crf 17 -r 30 -pix_fmt yuv420p "
            "-c:a copy -movflags +faststart out.mp4")
        return 0
    return 2


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="codekit.py", description="12 video-from-code tools for the Black Dragon")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("status", help="what is installed, where, version, licence")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("map", help="the 4-line metro map in Arabic")
    p.set_defaults(fn=cmd_map)
    p = sub.add_parser("install", help="print install commands (run only with --run)")
    p.add_argument("name")
    p.add_argument("--dest", help="folder for npm packages (npm --prefix)")
    p.add_argument("--run", action="store_true", help="really run the commands")
    p.add_argument("--allow-large", action="store_true", help="also allow torch-sized installs (WhisperX)")
    p.set_defaults(fn=cmd_install)
    p = sub.add_parser("demo", help="write a tiny demo (or print the command)")
    p.add_argument("name")
    p.add_argument("out_dir")
    p.add_argument("--title", help="Arabic title on the page (empty string for none)")
    p.set_defaults(fn=cmd_demo)
    p = sub.add_parser("vendor-gsap", help="copy gsap.min.js from an installed npm copy")
    p.add_argument("dest")
    p.add_argument("--from", dest="source", help="a node_modules folder (or its parent) that has gsap")
    p.set_defaults(fn=cmd_vendor_gsap)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
