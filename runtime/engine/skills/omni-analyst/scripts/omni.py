#!/usr/bin/env python3
"""omni.py — المحلل الشامل: يتعرّف على أي هدف رقمي، يطلّع بصمة سريعة، ويبني خطة تحليل بأوامر جاهزة.

الأوامر:
  classify <target>            يعرّف نوع الهدف (ملف/مجلد/رابط/دومين/IP/عملية)
  probe    <target> [--json]   بصمة آمنة سريعة: هاشات، magic، إنتروبي، نصوص لافتة (مابيشغّلش الهدف)
  plan     <target> [--depth 0-3]  خطة تحليل بالطبقات وبأوامر الأدوات المتثبتة على الجهاز
  report   <target> [--out FILE]   هيكل تقرير فاضي (دليل/استنتاج/مجهول) جاهز للملء
  hyp      "h1" "h2" ...        مصفوفة ACH فاضية للفرضيات المتنافسة
  bayes    <prior> <LR> [<LR>...]  تحديث احتمال بنسب الأرجحية (likelihood ratios)

مبيعملش أي اتصال بالنت، ومبيشغّلش الملف المحلَّل.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import math
import os
import re
import shutil
import sys
import zipfile
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RETOOL = os.environ.get("OMNI_RETOOL") or 'python "%s"' % (Path.home() / "re-tools" / "retool.py")
DRAGON_DIR = (os.environ.get("OMNI_DRAGON_DIR") or os.environ.get("DRAGON_HOME")
              or str(Path.home() / "OneDrive" / "Desktop" / "التنين الأسود"))

# ---------------------------------------------------------------- magic
MAGIC = [
    (b"MZ", "pe"),
    (b"\x7fELF", "elf"),
    (b"\xcf\xfa\xed\xfe", "macho"), (b"\xfe\xed\xfa\xcf", "macho"), (b"\xca\xfe\xba\xbe", "macho_or_class"),
    (b"dex\n", "dex"),
    (b"\x00asm", "wasm"),
    (b"PK\x03\x04", "zip"),
    (b"Rar!\x1a\x07", "rar"),
    (b"7z\xbc\xaf\x27\x1c", "7z"),
    (b"\x1f\x8b", "gzip"),
    (b"BZh", "bzip2"),
    (b"\xfd7zXZ\x00", "xz"),
    (b"(\xb5/\xfd", "zstd"),
    (b"%PDF", "pdf"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole"),
    (b"SQLite format 3\x00", "sqlite"),
    (b"GGUF", "gguf"),
    (b"\xd4\xc3\xb2\xa1", "pcap"), (b"\xa1\xb2\xc3\xd4", "pcap"), (b"\x0a\x0d\x0d\x0a", "pcapng"),
    (b"\x89PNG", "image"), (b"\xff\xd8\xff", "image"), (b"GIF8", "image"), (b"RIFF", "riff"),
    (b"ID3", "audio"), (b"fLaC", "audio"), (b"OggS", "audio"),
    (b"\x1aE\xdf\xa3", "video"),
    (b"MSCF", "cab"),
    (b"!<arch>", "ar"),
    (b"hsqs", "squashfs"),
    (b"\x27\x05\x19\x56", "uimage"),
    (b"\xd0\x0d\xfe\xed", "dtb"),
    (b"L\x00\x00\x00\x01\x14\x02\x00", "lnk"),
    (b"regf", "registry_hive"),
    (b"ElfFile\x00", "evtx"),
]
TEXT_EXT = {
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".ts": "javascript",
    ".py": "python_src", ".ps1": "script", ".bat": "script", ".cmd": "script", ".vbs": "script",
    ".sh": "script", ".html": "html", ".htm": "html", ".json": "data", ".csv": "data",
    ".xml": "data", ".yaml": "data", ".yml": "data", ".log": "log", ".md": "doc_text", ".txt": "doc_text",
    ".sql": "data", ".har": "har", ".eml": "email", ".msg": "email", ".svg": "image_svg",
}
MEDIA_EXT = {".mp4": "video", ".mov": "video", ".mkv": "video", ".webm": "video", ".avi": "video",
             ".mp3": "audio", ".wav": "audio", ".m4a": "audio", ".aac": "audio",
             ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image", ".heic": "image",
             ".tif": "image", ".psd": "image", ".blend": "blend"}
OFFICE_MACRO_EXT = {".docm", ".xlsm", ".pptm", ".doc", ".xls", ".ppt", ".dotm", ".xlam"}

INTERESTING = [
    ("url", re.compile(rb"https?://[\x21-\x7e]{4,200}")),
    ("ipv4", re.compile(rb"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
    ("email", re.compile(rb"[\w.+-]{2,64}@[\w-]{2,63}\.[\w.]{2,20}")),
    ("winpath", re.compile(rb"[A-Za-z]:\\\\?[\x20-\x7e]{3,160}")),
    ("registry", re.compile(rb"(?:HKEY_|HKLM|HKCU)[\\\x20-\x7e]{3,160}")),
    ("secret_like", re.compile(rb"(?:AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")),
    ("pdb", re.compile(rb"[\x20-\x7e]{3,200}\.pdb")),
]
PACKER_HINTS = {b"UPX0": "UPX", b"UPX!": "UPX", b".themida": "Themida", b".vmp0": "VMProtect",
                b"_MEIPASS": "PyInstaller", b"PYZ-00.pyz": "PyInstaller", b"pyi-runtime": "PyInstaller",
                b"Nuitka": "Nuitka", b"mscoree.dll": ".NET", b"_CorExeMain": ".NET",
                b"electron.asar": "Electron", b"app.asar": "Electron", b"Go build ID": "Go",
                b"rust_panic": "Rust", b"AutoIt": "AutoIt", b"Inno Setup": "Inno Setup",
                b"Nullsoft": "NSIS", b"7zS.sfx": "7z SFX", b"Enigma": "Enigma(?)"}


def entropy(b: bytes) -> float:
    if not b:
        return 0.0
    c = Counter(b)
    n = len(b)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def read_head(p: Path, n: int = 64) -> bytes:
    with open(p, "rb") as f:
        return f.read(n)


def sniff_file(p: Path) -> str:
    head = read_head(p)
    ext = p.suffix.lower()
    for sig, kind in MAGIC:
        if head.startswith(sig):
            if kind == "zip":
                return zip_subtype(p, ext)
            if kind == "riff":
                return "video" if head[8:12] in (b"AVI ",) else ("audio" if head[8:12] == b"WAVE" else "image")
            if kind == "ole":
                return "office_legacy"
            return kind
    if head[4:8] in (b"ftyp",):
        return "video"
    if ext in MEDIA_EXT:
        return MEDIA_EXT[ext]
    if ext in TEXT_EXT:
        return TEXT_EXT[ext]
    if ext == ".asar":
        return "asar"
    if ext == ".pyc":
        return "pyc"
    if ext in (".bin", ".img", ".fw", ".rom"):
        return "firmware"
    try:
        head.decode("utf-8")
        return "text"
    except UnicodeDecodeError:
        return "unknown_binary"


def zip_subtype(p: Path, ext: str) -> str:
    try:
        with zipfile.ZipFile(p) as z:
            names = set(z.namelist()[:5000])
    except Exception:
        return "zip"
    if "AndroidManifest.xml" in names or ext in (".apk", ".aab", ".xapk"):
        return "apk"
    if any(n.startswith("META-INF/MANIFEST.MF") for n in names) and ext in (".jar", ".war"):
        return "jar"
    if "[Content_Types].xml" in names:
        if ext in OFFICE_MACRO_EXT or any("vbaProject.bin" in n for n in names):
            return "office_macro"
        return "office"
    if "manifest.json" in names and ext in (".crx", ".xpi", ".zip"):
        return "browser_extension"
    if ext == ".ipa" or any(n.startswith("Payload/") for n in names):
        return "ipa"
    if ext == ".whl":
        return "python_wheel"
    if ext == ".nupkg":
        return "nupkg"
    return "zip"


def classify(target: str) -> dict:
    t = target.strip().strip('"')
    if re.match(r"^(?:pid:)?\d+$", t) and not Path(t).exists():
        return {"target": t, "family": "process", "kind": "process"}
    if re.match(r"^[a-z][a-z0-9+.-]*://", t, re.I):
        kind = "repo" if re.search(r"github\.com/[^/]+/[^/]+/?$", t) else "url"
        return {"target": t, "family": "web", "kind": kind}
    try:
        ipaddress.ip_address(t)
        return {"target": t, "family": "network", "kind": "ip"}
    except ValueError:
        pass
    p = Path(t)
    if p.is_dir():
        markers = {
            ".git": "git_repo", "package.json": "node_project", "pyproject.toml": "python_project",
            "requirements.txt": "python_project", "Cargo.toml": "rust_project", "go.mod": "go_project",
            "pom.xml": "java_project", "build.gradle": "java_project", "AndroidManifest.xml": "android_src",
        }
        found = [k for k, v in markers.items() if (p / k).exists()]
        kind = markers[found[0]] if found else "folder"
        if list(p.glob("*.sln")) or list(p.glob("*.csproj")):
            kind = "dotnet_project"
        return {"target": str(p.resolve()), "family": "codebase" if found or kind != "folder" else "folder",
                "kind": kind, "markers": found}
    if p.is_file():
        kind = sniff_file(p)
        fam = {
            "pe": "binary", "elf": "binary", "macho": "binary", "macho_or_class": "binary", "dex": "mobile",
            "apk": "mobile", "ipa": "mobile", "wasm": "web", "javascript": "web", "html": "web", "har": "web",
            "asar": "web", "browser_extension": "web", "pyc": "binary", "pdf": "document", "office": "document",
            "office_macro": "document", "office_legacy": "document", "email": "document", "lnk": "forensic",
            "registry_hive": "forensic", "evtx": "forensic", "pcap": "network", "pcapng": "network",
            "sqlite": "data", "data": "data", "log": "data", "gguf": "ai_model", "firmware": "firmware",
            "squashfs": "firmware", "uimage": "firmware", "dtb": "firmware", "image": "media", "video": "media",
            "audio": "media", "image_svg": "media", "blend": "media",
        }.get(kind, "archive" if kind in ("zip", "rar", "7z", "gzip", "bzip2", "xz", "zstd", "cab", "ar",
                                         "jar", "python_wheel", "nupkg") else "other")
        if p.suffix.lower() in (".safetensors", ".onnx", ".pt", ".pth", ".ckpt", ".tflite"):
            fam, kind = "ai_model", p.suffix.lower().lstrip(".")
        return {"target": str(p.resolve()), "family": fam, "kind": kind, "size": p.stat().st_size}
    if re.match(r"^(?=.{3,253}$)([a-z0-9-]+\.)+[a-z]{2,}$", t, re.I):
        return {"target": t, "family": "web", "kind": "domain"}
    return {"target": t, "family": "unknown", "kind": "unknown", "note": "مش ملف موجود ولا رابط ولا IP"}


def probe(target: str) -> dict:
    info = classify(target)
    p = Path(info["target"])
    if not p.is_file():
        if p.is_dir():
            files = [f for f in p.rglob("*") if f.is_file() and ".git" not in f.parts]
            exts = Counter(f.suffix.lower() or "(none)" for f in files)
            info.update(files=len(files), bytes=sum(f.stat().st_size for f in files[:200000]),
                        top_ext=exts.most_common(12))
        return info
    size = p.stat().st_size
    h = {k: hashlib.new(k) for k in ("md5", "sha1", "sha256")}
    sample = bytearray()
    ent_chunks = []
    with open(p, "rb") as f:
        while chunk := f.read(1 << 20):
            for v in h.values():
                v.update(chunk)
            if len(sample) < 32 << 20:
                sample += chunk
            ent_chunks.append(round(entropy(chunk[:65536]), 2))
    info["hashes"] = {k: v.hexdigest() for k, v in h.items()}
    info["entropy_overall"] = round(entropy(bytes(sample[:8 << 20])), 3)
    info["entropy_profile_1MB"] = ent_chunks[:40]
    info["entropy_verdict"] = ("مضغوط/متشفّر غالبًا" if info["entropy_overall"] > 7.2 else
                               "عادي" if info["entropy_overall"] > 4.5 else "نص أو بيانات متكررة")
    info["packer_hints"] = sorted({v for k, v in PACKER_HINTS.items() if k in sample})
    hits = {}
    for name, rx in INTERESTING:
        seen = []
        for m in rx.finditer(bytes(sample)):
            s = m.group(0).decode("latin-1", "replace")
            if s not in seen:
                seen.append(s)
            if len(seen) >= 25:
                break
        if seen:
            hits[name] = seen
    info["indicators"] = hits
    if info["kind"] == "pe":
        info["pe"] = pe_quick(p)
    return info


def pe_quick(p: Path) -> dict:
    try:
        import pefile  # type: ignore
    except ImportError:
        return {"note": "pefile مش متاح هنا؛ استخدم retool run pylibs أو rz-bin -I"}
    try:
        pe = pefile.PE(str(p), fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        secs = [{"name": s.Name.rstrip(b"\x00").decode("latin-1"), "vsize": s.Misc_VirtualSize,
                 "rsize": s.SizeOfRawData, "entropy": round(s.get_entropy(), 2)} for s in pe.sections]
        imps = {}
        for e in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            imps[e.dll.decode("latin-1")] = len(e.imports)
        sec_dir = pe.OPTIONAL_HEADER.DATA_DIRECTORY[4]
        clr_dir = pe.OPTIONAL_HEADER.DATA_DIRECTORY[14]
        return {"machine": hex(pe.FILE_HEADER.Machine), "timestamp": pe.FILE_HEADER.TimeDateStamp,
                "is_dll": pe.is_dll(), "dotnet": clr_dir.VirtualAddress != 0,
                "signed_blob": sec_dir.Size > 0, "sections": secs, "imports_per_dll": imps,
                "import_count": sum(imps.values())}
    except Exception as ex:  # noqa: BLE001
        return {"error": str(ex)}


# ---------------------------------------------------------------- plans
def L(layer: str, why: str, cmds: list[str]) -> dict:
    return {"layer": layer, "why": why, "cmds": cmds}


def plan(target: str, depth: int) -> list[dict]:
    c = classify(target)
    k, fam, t = c["kind"], c["family"], c["target"]
    q = f'"{t}"'
    steps: list[dict] = [L("L0 بصمة", "هوية الهدف قبل أي افتراض", [f'python omni.py probe {q} --json'])]
    if fam in ("binary", "mobile", "firmware", "archive", "document", "ai_model", "other", "forensic") or k == "wasm":
        steps.append(L("L0 تعرّف", "نوع/كومبايلر/باكر من مصدر مستقل عن الامتداد",
                       [f"{RETOOL} triage {q}", f"{RETOOL} run die -j {q}"]))
    if k == "pe":
        steps += [
            L("L1 بنية", "الاستيراد/التوقيع/الموارد = نية البرنامج الظاهرة",
              [f"rea inspect-artifact {q} --format md", f"rea inspect-pe-imports {q} --format md",
               f"rea inspect-pe-certificates {q} --format md", f"rea inspect-pe-resources {q} --format md",
               f"{RETOOL} run rz-bin -I -S -i {q}"]),
            L("L1 تفريع الباكر", "لو UPX: فك نسخة في output (ماتلمسش الأصل) / PyInstaller / .NET / Electron",
              [f"{RETOOL} run upx -t {q}", f"{RETOOL} run upx -d -o output\\unpacked.exe {q}",
               f"{RETOOL} run pyinstxtractor {q}", f"{RETOOL} run ilspy -p -o output\\cs {q}"]),
            L("L2 سلوك ستاتيكي", "قدرات + نصوص مخفية + توقيعات",
              [f"{RETOOL} triage {q} --deep --out output", f"{RETOOL} run capa {q}",
               f"{RETOOL} run floss --no static {q}", f"{RETOOL} run yara-x scan <rules.yar> {q}"]),
        ]
        if depth >= 3:
            steps.append(L("L3 كود", "ديكومبايل الدوال اللي الفرضيات بتشاور عليها بس",
                           [f"rea analyze {q} --format md", f"rea decompile {q} --function <addr|name> --format md",
                            f"{RETOOL} run rizin -q -c \"aaa;afl~main\" {q}"]))
            steps.append(L("L3 وقت التشغيل (بإذن صريح وفي بيئة معزولة)", "تأكيد السلوك الفعلي",
                           [f"{RETOOL} run frida-trace -i \"connect*\" -p <PID>", f"{RETOOL} run pe-sieve /pid <PID> /dir output",
                            f"{RETOOL} run mitmdump -w output\\flows.mitm"]))
    elif k in ("elf", "macho", "macho_or_class"):
        steps += [L("L1 بنية", "أقسام/رموز/مكتبات", [f"{RETOOL} run rz-bin -I -S -i -E {q}", f"rea inspect-artifact {q} --format md"]),
                  L("L2 سلوك", "قدرات ونصوص", [f"{RETOOL} run capa {q}", f"{RETOOL} run floss {q}"]),
                  L("L3 كود", "ديكومبايل موجّه", [f"rea analyze {q} --format md"])]
    elif k in ("apk", "dex"):
        steps += [L("L1 مانيفست", "صلاحيات/مكونات مصدّرة/شبكة", [f"rea inspect-android-package {q} --format md",
                                                                 f"{RETOOL} run androguard axml {q}"]),
                  L("L2 أسرار وروابط", "endpoints ومفاتيح", [f"{RETOOL} run apkleaks -f {q}"]),
                  L("L3 كود", "Java + smali", [f"{RETOOL} run jadx -d output\\jadx {q}",
                                               f"{RETOOL} run apktool d {q} -o output\\apktool"])]
    elif k in ("javascript", "asar", "browser_extension"):
        steps += [L("L1 فك تشويش", "رجّع الكود مقروء", [f"{RETOOL} run webcrack {q} -o output\\js"]),
                  L("L2 تطبيق", "IPC/شبكة/صلاحيات", [f"rea analyze-javascript-application {q} --format md"])]
    elif k == "wasm":
        steps += [L("L1 بنية", "دوال/استيراد/تصدير", [f"{RETOOL} run wasm-objdump -x {q}",
                                                     f"{RETOOL} run wasm2wat {q} -o output\\mod.wat"])]
    elif k in ("office_macro", "office_legacy", "office"):
        steps += [L("L1 ماكرو", "VBA وأنماط مشبوهة (AutoOpen/Shell/Download)", [f"{RETOOL} run olevba {q}"])]
    elif k == "pdf":
        steps += [L("L1 بنية", "JS/روابط/ملفات مدمجة", [f'python -I -c "import fitz,sys;d=fitz.open(sys.argv[1]);print(d.metadata, d.page_count, [l.get(\'uri\') for p in d for l in p.get_links()][:50], d.embfile_names())" {q}'])]
    elif k in ("pcap", "pcapng", "har"):
        steps += [L("L1 محادثات", "مين كلّم مين وقد إيه", [f"{RETOOL} run tshark -r {q} -q -z conv,ip",
                                                        f"{RETOOL} run tshark -r {q} -q -z http,tree",
                                                        f"{RETOOL} run tshark -r {q} -T fields -e dns.qry.name -Y dns"])]
    elif k == "sqlite":
        steps += [L("L1 سكيمة", "جداول وأعداد صفوف", [f'python -I -c "import sqlite3,sys;c=sqlite3.connect(\'file:\'+sys.argv[1]+\'?mode=ro\',uri=True);[print(r[0],c.execute(f\'select count(*) from [{{r[0]}}]\').fetchone()[0]) for r in c.execute(\'select name from sqlite_master where type=\\\'table\\\'\')]" {q}'])]
    elif fam == "ai_model":
        steps += [L("L1 ميتاداتا", "معمارية/كوانتايز/توكنيزر", [f"rea analyze {q} --format md"])]
    elif fam == "firmware":
        steps += [L("L1 خريطة", "أنظمة ملفات وأجزاء مدمجة", [f"rea analyze {q} --format md", f"{RETOOL} triage {q} --deep"])]
    elif fam == "archive":
        steps += [L("L1 محتوى", "اعرض من غير ما تفك", [f"7z l {q}"]),
                  L("L1 فك آمن", "في مجلد جديد فاضي وبعدين حلّل كل ملف بـ omni", [f"7z x {q} -ooutput\\extracted -y"])]
    elif fam == "media":
        steps += [L("L1 قياس", "مدة/أبعاد/كوديك/صوت", [f"ffprobe -v error -show_format -show_streams -of json {q}",
                                                     f"exiftool -a -G1 {q}"]),
                  L("L2 جودة", "LUFS/ذروة/مشاهد", [f'cd "{DRAGON_DIR}" && python -m dragon verify {q}',
                                                   f"scenedetect -i {q} list-scenes"])]
    elif fam in ("codebase", "folder"):
        steps += [L("L1 خريطة", "حجم/لغات/نقاط دخول", [f"rg --files {q} | head -200", "git log --oneline -20 (لو repo)"]),
                  L("L2 مخاطر", "أسرار متسابة/تبعيات/نقاط هجوم", [f"rg -n -i \"(api[_-]?key|secret|password|token)\\s*[:=]\" {q}",
                                                                 f"rg -n \"eval\\(|exec\\(|subprocess|child_process|innerHTML\" {q}"]),
                  L("L2 مسح ملفات تنفيذية جوه المجلد", "كل exe/dll/apk يتحلّل لوحده", [f"python omni.py probe <each binary>"])]
    elif k in ("url", "domain", "repo"):
        steps += [L("L1 سطح", "هيدرز/تقنيات/روابط (قراءة بس)", ["WebFetch على الصفحة", f"rea analyze-web-bundle {q} --format md"]),
                  L("L2 Bundles", "نزّل JS في مجلد جديد وفكّه", [f"{RETOOL} run webcrack <bundle.js> -o output\\js"])]
        if k == "repo":
            steps.append(L("L1 مستودع", "README/لغات/نشاط", [f"gh repo view {t.split('github.com/')[-1]}"]))
    elif k == "ip":
        steps += [L("L1 سياق", "مين صاحبه؟ (قراءة عامة فقط، مفيش مسح بورتات من غير إذن)", ["WebSearch/WHOIS عام"])]
    elif k == "process":
        pid = t.replace("pid:", "")
        steps += [L("L1 عملية", "مسار/أب/اتصالات", [f'powershell "Get-CimInstance Win32_Process -Filter \'ProcessId={pid}\' | fl *"',
                                                     f'powershell "Get-NetTCPConnection -OwningProcess {pid}"']),
                  L("L2 ذاكرة", "كود محقون", [f"{RETOOL} run pe-sieve /pid {pid} /dir output"])]
    steps.append(L("L∞ تركيب", "ACH + تحديث بايزي + تقرير بثلاث خانات",
                   [f'python omni.py report {q} --out output\\report.md']))
    if depth <= 0:
        steps = steps[:2]
    elif depth == 1:
        steps = [s for s in steps if s["layer"].startswith(("L0", "L1", "L∞"))]
    elif depth == 2:
        steps = [s for s in steps if not s["layer"].startswith("L3")]
    return [{"classified": c}] + steps


REPORT = """# تقرير تحليل: {name}

> النتيجة في سطر: _____
> الثقة الكلية: ___ (منخفضة/متوسطة/عالية) — ليه: _____

## 1. الهوية
| البند | القيمة | المصدر |
|---|---|---|
| النوع | {kind} ({family}) | omni classify |
| SHA-256 | {sha} | omni probe |
| الحجم | {size} | omni probe |
| الإنتروبي | {ent} | omni probe |
| تلميحات باكر | {pack} | omni probe |

## 2. الأسئلة (Key Intelligence Questions)
1. إيه ده؟  2. بيعمل إيه فعلًا؟  3. بيكلّم مين؟  4. إيه المخاطر؟  5. إيه اللي محتاج قرار؟

## 3. الفرضيات المتنافسة (ACH)
| الدليل | H1 | H2 | H3 | تشخيصي؟ |
|---|---|---|---|---|

## 4. النتائج حسب الأداة
### <اسم الأداة>
- الأمر: `...`
- طلع: ...
- معناه: ...

## 5. نموذج النظام
- المكونات والحدود (C4/Data-flow): ...
- نقاط الثقة (trust boundaries): ...
- STRIDE على كل حدّ: ...

## 6. ✅ اتأكد بدليل
- ... [المصدر: أمر/سطر/أوفست]

## 7. 🟡 استنتاج (مع احتمال)
- ... (~70%) لأن ...

## 8. ❓ لسه مجهول + إزاي نعرفه
- ... ← الخطوة اللي تحسمه: ...

## 9. التوصيات (مرتّبة بالأثر/المجهود)
1. ...
"""


def report(target: str, out: str | None) -> str:
    c = classify(target)
    pr = probe(target) if Path(c["target"]).is_file() else c
    txt = REPORT.format(name=Path(c["target"]).name or c["target"], kind=c["kind"], family=c["family"],
                        sha=pr.get("hashes", {}).get("sha256", "—"), size=pr.get("size", "—"),
                        ent=f'{pr.get("entropy_overall", "—")} {pr.get("entropy_verdict", "")}',
                        pack=", ".join(pr.get("packer_hints", [])) or "—")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(txt, encoding="utf-8")
    return txt


def hyp(hs: list[str]) -> str:
    head = "| الدليل | " + " | ".join(f"H{i+1}: {h}" for i, h in enumerate(hs)) + " | تشخيصي؟ |"
    sep = "|---" * (len(hs) + 2) + "|"
    rows = "\n".join("| ... | " + " | ".join("C/I/N" for _ in hs) + " | نعم/لا |" for _ in range(4))
    return (f"{head}\n{sep}\n{rows}\n\nC=متسق، I=متناقض، N=محايد. اختار الفرضية اللي عليها **أقل I**، "
            "مش أكتر C. الدليل اللي متسق مع الكل قيمته التشخيصية صفر.")


def bayes(prior: float, lrs: list[float]) -> str:
    odds = prior / (1 - prior)
    lines = [f"البداية: P={prior:.3f} (odds={odds:.3f})"]
    for lr in lrs:
        odds *= lr
        p = odds / (1 + odds)
        lines.append(f"× LR {lr:g} ← P={p:.3f}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("classify", "probe", "plan", "report"):
        s = sub.add_parser(name)
        s.add_argument("target")
        s.add_argument("--json", action="store_true")
        if name == "plan":
            s.add_argument("--depth", type=int, default=2)
        if name == "report":
            s.add_argument("--out")
    s = sub.add_parser("hyp"); s.add_argument("h", nargs="+")
    s = sub.add_parser("bayes"); s.add_argument("prior", type=float); s.add_argument("lr", type=float, nargs="+")
    a = ap.parse_args()
    if a.cmd == "classify":
        r = classify(a.target)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif a.cmd == "probe":
        r = probe(a.target)
        print(json.dumps(r, ensure_ascii=False, indent=2 if a.json else 1))
    elif a.cmd == "plan":
        r = plan(a.target, a.depth)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=2)); return
        c = r[0]["classified"]
        print(f"# خطة تحليل — {c['kind']} ({c['family']})\n")
        for s in r[1:]:
            print(f"## {s['layer']} — {s['why']}")
            for cmd in s["cmds"]:
                print(f"    {cmd}")
            print()
        missing = [x for x in ("rea", "ffprobe", "7z", "rg", "exiftool") if not shutil.which(x)]
        if missing:
            print("⚠ مش لاقي على PATH: " + ", ".join(missing))
    elif a.cmd == "report":
        print(report(a.target, a.out))
    elif a.cmd == "hyp":
        print(hyp(a.h))
    elif a.cmd == "bayes":
        print(bayes(a.prior, a.lr))


if __name__ == "__main__":
    main()
