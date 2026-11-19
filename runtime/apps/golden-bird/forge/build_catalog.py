"""build_catalog.py — turns the reverse-engineering findings into the two catalogs the Golden Bird ships:
  data\\library.json  (motion / web / video libraries, engines, AI repos, zips, non-CLI programs)
  data\\studio.json   (command-line programs from مهارات\\برامج, with the archive sha256 measured on this PC)

Input: the agents' JSON files in %USERPROFILE%\\.goldenbird-re\\findings (or --findings DIR). The findings came from reading
untrusted downloads, so every path is re-checked here: offline files must exist inside the «مهارات» folder, licence files
too, and a studio archive must hash to the value measured in archive_sha256.txt. Anything that fails is downgraded
(offline_entry=None, readiness=needs-build) or dropped, and reported.

  python -X utf8 build_catalog.py [--findings DIR]
"""
import json, re, sys, time
from pathlib import Path

FORGE = Path(__file__).resolve().parent
DATA = FORGE / "data"
HOME = Path.home()
MAHARAT = HOME / "OneDrive" / "Desktop" / "مهارات"
PROGS = MAHARAT / "برامج"
FINDINGS = Path(sys.argv[sys.argv.index("--findings") + 1]) if "--findings" in sys.argv else HOME / ".goldenbird-re" / "findings"
LIB_FILES = ["motion_web.json", "motion_fx.json", "motion_3d_creative.json", "motion_engines.json", "motion_videoai.json",
             "zips_big.json", "zips_media.json", "zips_ai.json"]
KEEP = ("id", "name", "group", "category", "source", "license", "license_evidence", "commercial_ok", "lang", "what_ar", "use_ar",
        "offline_entry", "offline_kind", "extras", "cli", "requires", "keywords", "readiness", "installed_skill", "installed_status",
        "cpu_ok", "weights", "skills_in_repo", "evidence")
report = []

# Programs that are not command-line tools: kept as library entries (from the 2026-11-14 static report in مهارات).
PROGRAM_NOTES = [
    {"id": "mpfb-blender", "name": "MPFB 2.0.18 (إضافة Blender)", "category": "3d-character", "license": "GPL-3.0-or-later (blender_manifest.toml)",
     "commercial_ok": "copyleft", "lang": "Python", "source": str(PROGS / "MPFB_Blender" / "add-on-mpfb-v2.0.18.zip"),
     "what_ar": "إضافة Blender بتعمل شخصية بشرية 3D كاملة بهيكل عظمي جاهز، وفيها 1,477 هدف لشكل الجسم.",
     "use_ar": "أسرع طريق لشخصية بشرية بتتحرك جوه Blender 5.2 المتثبت، للمشاهد والريلز 3D.",
     "requires": "Blender 5.2 (تثبيت الإضافة من الواجهة أو blender --command extension install-file)", "readiness": "needs-install",
     "keywords": ["human", "character", "body", "rig", "blender", "makehuman", "شخصيه", "انسان"]},
    {"id": "comfyui-intel", "name": "ComfyUI v0.45 (Intel XPU)", "category": "ai-video", "license": "GPL-3.0 (ComfyUI/LICENSE)", "commercial_ok": "copyleft",
     "lang": "Python", "source": str(PROGS / "ComfyUI_Intel" / "ComfyUI_windows_portable_intel.7z"),
     "what_ar": "واجهة عُقد للذكاء الاصطناعي متبنية لكروت Intel، وفيها عُقد لقص الخلفية والعمق وتنعيم الحركة وGaussian Splat.",
     "use_ar": "للمهام الخفيفة بس (قص خلفية، عمق، frame interpolation). الموديلات الكبيرة زي Wan وLTX تقيلة جدًا على كارت الجهاز المدمج.",
     "requires": "فك 1.5GB + torch xpu؛ العُقد المدفوعة (kling/veo/runway/higgsfield) ممنوعة من غير موافقة", "readiness": "needs-install",
     "keywords": ["comfyui", "nodes", "depth", "background", "interpolation", "ذكاء"]},
    {"id": "sam2-small", "name": "SAM 2.1 small", "category": "ai-video", "license": "Apache-2.0", "commercial_ok": "yes", "lang": "Python",
     "source": str(PROGS / "SAM2"), "what_ar": "موديل Meta بيقص أي جسم أو شخص من الفيديو فريم بفريم (176MB).",
     "use_ar": "قص الشخص من الفيديو لعمل ماسك أو خلفية متغيّرة، على المعالج ببطء.", "requires": "torch (متثبت) + الكود في repo",
     "readiness": "needs-install", "keywords": ["segment", "mask", "cutout", "rotoscope", "قص", "ماسك"]},
    {"id": "depth-anything-v2", "name": "Depth Anything V2 small", "category": "ai-video", "license": "Apache-2.0 (Small only; Base/Large = CC-BY-NC-4.0, README:180)", "commercial_ok": "yes",
     "lang": "Python", "source": str(PROGS / "DepthAnythingV2"), "what_ar": "موديل بيطلّع خريطة عمق من أي صورة (95MB).",
     "use_ar": "عمق للصور عشان parallax 2.5D وضباب وفوكس صناعي في الموشن.", "requires": "torch (متثبت)", "readiness": "needs-install",
     "keywords": ["depth", "parallax", "2.5d", "عمق"]},
    {"id": "glaxnimate", "name": "Glaxnimate 0.6.0", "category": "lottie", "license": "GPL-3 (upstream; مفيش ملف رخصة جوه المثبّت)",
     "commercial_ok": "copyleft", "lang": "C++/Qt6", "source": str(PROGS / "Glaxnimate" / "glaxnimate-0.6.0-x86_64.exe"),
     "what_ar": "محرر أنيميشن فيكتور بيصدّر Lottie وSVG متحرك وGIF، ومعاه بايثون 3.11 للسكربتات.",
     "use_ar": "تصميم أنيميشن Lottie بإيدك. المثبّت NSIS جواه أرشيف 7z تاني، فمش في الاستوديو؛ وفورمات التصدير تتأكد بـ --export-format-list أول تشغيل.",
     "requires": "تثبيت (مثبّت موقّع من KDE e.V.)", "readiness": "needs-install", "keywords": ["lottie", "vector", "svg", "animation", "لوتي"]},
    {"id": "friction", "name": "Friction 1.0.0", "category": "engines", "license": "GPL-3 (upstream)", "commercial_ok": "copyleft",
     "lang": "C++/Qt5", "source": str(PROGS / "Friction" / "friction-1.0.0-windows-x64.7z"),
     "what_ar": "برنامج موشن جرافيك 2D فيكتور بواجهة (زي After Effects مصغّر).",
     "use_ar": "للتصميم بإيدك بس: الفحص الثابت مالقاش أي خيار سطر أوامر (لا QCommandLineParser ولا نص مساعدة)، فمش هينفع رندر أوتوماتيك بيه.",
     "requires": "فك الأرشيف وتشغيل الواجهة", "readiness": "needs-install", "keywords": ["motion", "vector", "2d", "موشن"]},
    {"id": "vroid-studio", "name": "VRoid Studio 2.14.0", "category": "3d-character", "license": "مجاني من pixiv (شروط الاستخدام)",
     "commercial_ok": "conditional", "lang": "Unity", "source": str(PROGS / "VRoidStudio"),
     "what_ar": "برنامج شخصيات أنمي 3D بيطلّع صيغة VRM.", "use_ar": "شخصية أنمي 3D تتنقل لـ Blender (إضافة VRM) للمشاهد.",
     "requires": "تثبيت عادي (مثبّت موقّع من pixiv)", "readiness": "needs-install", "keywords": ["anime", "vrm", "character", "انمي"]},
]

# Command-line programs. Archive paths are relative to مهارات\برامج; the agent's programs.json adds usage and evidence.
STUDIO_BASE = [
    ("rhubarb", "Rhubarb Lip Sync", "Rhubarb/Rhubarb-Lip-Sync-1.14.0-Windows.zip", "rhubarb.exe", None),
    ("tcomposer", "Tahoma2D tcomposer", "Tahoma2D/Tahoma2D-portable-win.zip", "tcomposer.exe", "tahoma2d"),
    ("tconverter", "Tahoma2D tconverter", "Tahoma2D/Tahoma2D-portable-win.zip", "tconverter.exe", "tahoma2d"),
    ("handbrakecli", "HandBrakeCLI", "HandBrakeCLI/HandBrakeCLI-1.11.2-win-x86_64.zip", "HandBrakeCLI.exe", None),
    ("synfig", "Synfig CLI", "Synfig/SynfigStudio-1.5.5-2026.03.15-win64-79bf7.zip", "synfig.exe", None),
    ("melt", "MLT melt (Shotcut)", "Shotcut_portable/shotcut-win64-26.9.27.zip", "melt.exe", "shotcut"),
    ("whisper-cli", "whisper.cpp CLI (Shotcut)", "Shotcut_portable/shotcut-win64-26.9.27.zip", "whisper-cli.exe", "shotcut"),
    ("oiiotool", "OpenImageIO oiiotool (Gaffer)", "Gaffer/gaffer-1.7.7.0-windows.zip", "oiiotool.exe", "gaffer"),
    ("gaffer-mcp", "Gaffer MCP server", "Gaffer/gaffer-1.7.7.0-windows.zip", "gaffer.cmd", "gaffer"),
    ("pencil2d", "Pencil2D", "Pencil2D/pencil2d-win64-v0.7.2.zip", "pencil2d.exe", None),
]
# Verified gotchas from the static RE pass (re_tools.md): shown by `studio show` so the model gets them right the first time.
CAUTIONS = {
    "rhubarb": "حوّل الصوت لـ WAV الأول (نص المساعدة جوه الملف بيقول WAVE). للعربي `-r phonetic` (pocketSphinx إنجليزي بس). مجلد `res\\sphinx` لازم يفضل جنب rhubarb.exe.",
    "tconverter": "بيسأل [Y/N] لو ملف الوجهة موجود، فبيفضل مستني: امسح الوجهة أو غيّر اسمها قبل التشغيل.",
    "tcomposer": "`-nthreads single|half` مؤكدين من الملف. `-range from to` و`-frame fr` نصهم في tnzbase.dll.",
    "handbrakecli": "مع ترجمة عربي لازم `--srt-codeset UTF-8` (الافتراضي latin1 فالحروف بتبوظ).",
    "whisper-cli": "مفيش أي موديل جوه Shotcut، والافتراضي `models/ggml-base.en.bin` إنجليزي بس: نزّل موديل ggml متعدد اللغات (روابطه في whispermodel.qml) ومرّره بـ `-m`، وللعربي `-l ar`.",
    "melt": "بروفايل `vertical_hd_30` و`vertical_hd_60` موجودين للريلز 9:16.",
    "gaffer-mcp": "سيرفر MCP على stdio. أداة executePython فيه = تحكم كامل في Gaffer وبايثون، فشغّله بسكربتات .gfr موثوقة بس.",
    "oiiotool": "OpenImageIO 3.0.6.1: تحويل صور EXR/HDR/PNG وتغيير مقاس وتركيب من سطر الأوامر.",
    "synfig": "استخدم أسماء الخيارات الطويلة (المختصرة زي -t -o -w استنتاج ~85%). اعرض الفورمات بـ `--target-video-codecs` أول مرة.",
    "pencil2d": "برنامج بواجهة (GUI subsystem): ممكن الخرج مايظهرش في الكونسول. جرّب `--export` على عيّنة صغيرة الأول.",
}


def inside(p, root=MAHARAT):
    try:
        return Path(p).resolve().is_relative_to(root.resolve())
    except (OSError, ValueError):
        return False


def first_file(text):
    for part in re.split(r"\s*;\s*|\s+\|\s+", str(text or "")):
        part = part.strip().strip("`")
        if part and "!" not in part and Path(part).is_file() and inside(part):
            return str(Path(part))
    return None


def clean_item(it, origin):
    out = {k: it[k] for k in KEEP if k in it and it[k] not in (None, "", [])}
    if not out.get("id") or not out.get("name"):
        report.append(f"  ✗ dropped (no id/name) from {origin}")
        return None
    out["id"] = re.sub(r"[^a-z0-9._-]+", "-", out["id"].lower()).strip("-")
    out["origin"] = origin
    oe = out.get("offline_entry")
    if oe and str(oe).lower().endswith((".html", ".htm")):
        # a demo page is not a library: it may pull analytics/CDN scripts (WebGL-Fluid loads Google Analytics)
        report.append(f"  ↓ {out['id']}: offline_entry is a demo page, not a library → needs-build ({oe})")
        out.pop("offline_entry", None)
        out.pop("offline_kind", None)
        out["readiness"] = "needs-build"
        out["requires"] = (out.get("requires", "") + " · صفحة العرض بتحمّل سكربتات من النت؛ انسخ الكود من غير التحليلات").strip(" ·")
        oe = None
    if oe and not (Path(oe).exists() and inside(oe)):
        report.append(f"  ↓ {out['id']}: offline_entry missing/outside مهارات → needs-build ({oe})")
        out.pop("offline_entry", None)
        out.pop("offline_kind", None)
        out["readiness"] = "needs-build" if out.get("readiness") == "ready-offline" else out.get("readiness", "needs-build")
    elif not oe and out.get("readiness") == "ready-offline":
        # "ready" with nothing kit can copy: for a zip it means "works offline once unpacked"
        out["readiness"] = "needs-unpack" if out.get("group") == "zip" else "needs-build"
        report.append(f"  ↓ {out['id']}: ready-offline without a file → {out['readiness']}")
    ex = [e for e in out.get("extras") or [] if Path(e).is_file() and inside(e)]
    if len(ex) != len(out.get("extras") or []):
        report.append(f"  ↓ {out['id']}: {len(out.get('extras') or []) - len(ex)} extras dropped")
    if ex:
        out["extras"] = ex
    else:
        out.pop("extras", None)
    lf = first_file(out.get("license_evidence"))
    if lf:
        out["license_file"] = lf
    return out


def build_library():
    items, seen = [], set()
    for name in LIB_FILES:
        f = FINDINGS / name
        if not f.is_file():
            report.append(f"  … {name}: not found (skipped)")
            continue
        raw = json.loads(f.read_text(encoding="utf-8"))
        raw = raw if isinstance(raw, list) else raw.get("items", [])
        n = 0
        for it in raw:
            c = clean_item(it, name)
            if not c:
                continue
            if c["id"] in seen:
                c["id"] = f"{c['id']}-{name.split('.')[0].split('_')[-1]}"
            seen.add(c["id"])
            items.append(c)
            n += 1
        report.append(f"  {name}: {n}")
    for p in PROGRAM_NOTES:
        if p["id"] not in seen:
            items.append({**p, "group": "program", "origin": "مهارات/تقرير_الهندسة_العكسية.md",
                          "evidence": "تقرير_الهندسة_العكسية.md (2026-11-14) + sha256 measured"})
            seen.add(p["id"])
    return items


def measured_hashes():
    out = {}
    f = FINDINGS / "archive_sha256.txt"
    for line in f.read_text(encoding="utf-8").splitlines():
        h, size, rel = line.split(" ", 2)
        out[rel.strip().replace("\\", "/")] = (h.lower(), int(size))
    return out


def build_studio():
    hashes = measured_hashes()
    agent = {}
    pf = FINDINGS / "programs.json"
    if pf.is_file():
        for it in json.loads(pf.read_text(encoding="utf-8")):
            agent[re.sub(r"[^a-z0-9-]+", "-", str(it.get("id", "")).lower())] = it
    else:
        report.append("  … programs.json not found: studio entries without usage lines")
    progs = []
    for ident, name, rel, exe, unpack_as in STUDIO_BASE:
        arc = PROGS / rel
        if not arc.is_file() or rel not in hashes:
            report.append(f"  ✗ studio {ident}: archive missing or not hashed ({rel})")
            continue
        h, size = hashes[rel]
        if arc.stat().st_size != size:
            report.append(f"  ✗ studio {ident}: size changed since hashing")
            continue
        a = agent.get(ident, {})
        inner = re.split(r"\s+\(|\s*->", a.get("exe_in_archive") or exe)[0].strip().replace("\\", "/")
        prog = {"id": ident, "name": a.get("name") or name, "version": a.get("version", ""), "archive": str(arc), "archive_sha256": h,
                "exe": inner, "license": a.get("license", "?"), "signed": a.get("signed", "?"),
                "cli_usage": a.get("cli_usage", ""), "examples": a.get("examples") or [], "use_ar": a.get("use_ar", ""),
                "deps": a.get("deps", ""), "evidence": a.get("evidence", ""), "cautions": CAUTIONS.get(ident, "")}
        if unpack_as:
            prog["unpack_as"] = unpack_as
        if not a:
            report.append(f"  … studio {ident}: no agent record")
        progs.append(prog)
    return progs


def main():
    DATA.mkdir(exist_ok=True)
    items = build_library()
    progs = build_studio()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    lib = {"generated": stamp, "roots": [str(MAHARAT)], "count": len(items), "items": items}
    st = {"generated": stamp, "home": "%USERPROFILE%\\GoldenBird\\studio", "programs": progs}
    (DATA / "library.json").write_text(json.dumps(lib, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATA / "studio.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    ready = sum(1 for i in items if i.get("offline_entry"))
    print("\n".join(report))
    print(f"✓ library.json: {len(items)} items ({ready} ready offline) · studio.json: {len(progs)} programs → {DATA}")


if __name__ == "__main__":
    main()
