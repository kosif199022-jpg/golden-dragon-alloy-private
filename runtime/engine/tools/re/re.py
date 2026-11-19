#!/usr/bin/env python3
"""re — Black Dragon reverse-engineering front door (v10.14).

    dragon.py tool re doctor                      # retool box + rea: what is installed here
    dragon.py tool re plan FILE [--report OUT.md] # identify the file from its bytes -> ordered tool chain + report skeleton
    dragon.py tool re audit PATH [--json]         # secrets + dangerous patterns in a folder/ZIP/skill package (before install)
    dragon.py tool re investigate FILE --out DIR  # runs the safe static steps (triage, die, audit) -> report.md + evidence.json
    dragon.py tool re triage FILE [--deep]        # retool triage (hashes, type/packer, PE sections, URLs, IPs)
    dragon.py tool re run ID [--yes] [args...]    # one retool tool; runtime tools (frida, pe-sieve, x64dbg...) need --yes

Rules: analysis and understanding of the user's own files only, never cracking, licence bypass or cloning.
Static by default: plan/audit read bytes and never execute the target. Tools that attach to a running
process, open a GUI, capture traffic or talk to a phone stay blocked until the user approves (--yes).
Every report separates evidence (tool output) from inference (our reading) and unknowns.
"""
# v10.16.1: this file is named re.py, so when run as a script its own folder is sys.path[0] and
# `import re` imported THIS file instead of the stdlib (tool re crashed). Drop our folder first.
import sys as _sys, os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:] = [p for p in _sys.path if _os.path.abspath(p or _os.getcwd()) != _HERE]
_sys.modules.pop('re', None) if getattr(_sys.modules.get('re'), '__file__', '') == _os.path.abspath(__file__) else None
import argparse, hashlib, json, os, re, shutil, struct, subprocess, sys, tempfile, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RULES = HERE / "rules" / "dragon_audit.yar"
RETOOL = Path(os.environ.get("DRAGON_RETOOL") or (Path.home() / "re-tools" / "retool.py"))
RUNTIME = {"frida", "frida-ps", "frida-trace", "pe-sieve", "x64dbg", "mitmdump", "adb", "die-gui", "ilspy-gui",
           "imhex", "tshark-live"}
TEXT_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".sh", ".ps1", ".bat", ".cmd", ".md", ".json", ".txt", ".yml",
            ".yaml", ".toml", ".ini", ".cfg", ".html", ".css", ".xml", ".env", ".jsonl", ".csv", ".yar"}

# ---------------------------------------------------------------- identification (bytes, not extensions)

def _read(p, n=None, off=0):
    with open(p, "rb") as f:
        f.seek(off)
        return f.read(n) if n else f.read()


def pe_info(p):
    b = _read(p, 4 * 1024 * 1024)
    info = {"dotnet": False, "upx": False, "pyinstaller": False, "installer": None, "bits": None}
    try:
        e = struct.unpack_from("<I", b, 0x3C)[0]
        if b[e:e + 4] != b"PE\0\0":
            return info
        nsec = struct.unpack_from("<H", b, e + 6)[0]
        opt_size = struct.unpack_from("<H", b, e + 20)[0]
        opt = e + 24
        magic = struct.unpack_from("<H", b, opt)[0]
        info["bits"] = 64 if magic == 0x20B else 32
        dd = opt + (112 if magic == 0x20B else 96)
        clr_rva = struct.unpack_from("<I", b, dd + 14 * 8)[0]
        info["dotnet"] = clr_rva != 0
        sec = opt + opt_size
        names = [b[sec + i * 40: sec + i * 40 + 8].rstrip(b"\0") for i in range(nsec)]
        info["sections"] = [n.decode("latin-1") for n in names]
        info["upx"] = any(n.startswith(b"UPX") for n in names)
    except struct.error:
        pass
    tail = _read(p, 8192, max(0, os.path.getsize(p) - 8192))
    info["pyinstaller"] = b"MEI\x0c\x0b\x0a\x0b\x0e" in tail or b"_MEIPASS" in b or b"pyi-runtime" in b
    for sig, name in ((b"Nullsoft", "NSIS"), (b"Inno Setup", "Inno Setup"), (b"electron.asar", "Electron")):
        if sig in b:
            info["installer"] = name
    return info


def identify(path):
    p = Path(path)
    if p.is_dir():
        kind = "skill-package" if (p / "SKILL.md").is_file() else "source-folder"
        if (p / "resources" / "app.asar").is_file():
            kind = "electron-app"
        return {"kind": kind, "path": str(p)}
    head = _read(p, 64)
    ext = p.suffix.lower()
    k, extra = "unknown", {}
    if head[:2] == b"MZ":
        extra = pe_info(p)
        k = ("pe-dotnet" if extra["dotnet"] else "pe-pyinstaller" if extra["pyinstaller"] else
             "pe-upx" if extra["upx"] else "pe-electron" if extra.get("installer") == "Electron" else "pe-native")
    elif head[:4] == b"\x7fELF":
        k = "elf"
    elif head[:4] in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
        k = "macho"
    elif head[:4] == b"PK\x03\x04":
        try:
            names = zipfile.ZipFile(p).namelist()
        except zipfile.BadZipFile:
            names = []
        s = set(names)
        if "AndroidManifest.xml" in s and any(n.endswith(".dex") for n in names):
            k = "apk"
        elif "[Content_Types].xml" in s:
            k = "office-macro" if any(n.endswith("vbaProject.bin") for n in names) else "office"
        elif any(n.endswith("SKILL.md") for n in names):
            k = "skill-zip"
        else:
            k = "zip"
        extra = {"entries": len(names)}
    elif head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        k = "office-ole"
    elif head[:4] == b"\0asm":
        k = "wasm"
    elif head[:4] in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\x0a\x0d\x0d\x0a"):
        k = "pcap"
    elif head[:16] == b"SQLite format 3\0":
        k = "sqlite"
    elif head[:4] == b"GGUF":
        k = "gguf"
    elif ext == ".asar":
        k = "asar"
    elif ext in (".js", ".mjs", ".cjs"):
        k = "javascript"
    elif ext == ".pyc":
        k = "pyc"
    elif ext in (".bin", ".hex", ".uf2", ".img", ".fw"):
        k = "firmware"
    return {"kind": k, "path": str(p), "size": p.stat().st_size,
            "sha256": hashlib.sha256(_read(p)).hexdigest() if p.stat().st_size < 512 * 1024 * 1024 else None, **extra}


# ---------------------------------------------------------------- chains (static first, runtime last and gated)
T = "triage"
# Order follows the owner's re-tools box and rea-ultra: identify -> unpack -> language-specific -> rea -> runtime (gated).
CHAINS = {
    "pe-native":      [(T, "--deep"), "die", "rz-bin", "rea:inspect-pe-imports", "rea:inspect-pe-certificates",
                       "rea:inspect-pe-load-config", "rea:inspect-pe-resources", "rea:inspect-byte-entropy", "floss", "capa",
                       "yara-x", "rea:analyze", "rea:decompile", "runtime:frida-trace", "runtime:pe-sieve"],
    "pe-upx":         [T, "die", ("upx", "-t"), ("upx", "-d -o UNPACKED_COPY.exe"), "note: then `re plan` the unpacked copy"],
    "pe-dotnet":      [T, "die", "ilspy", "rea:inspect-managed-artifact", "rea:inspect-managed-members", "capa"],
    "pe-pyinstaller": [T, "die", "pyinstxtractor", "note: pydisasm on the entry .pyc", "rea:inspect-python-pyc"],
    "pe-electron":    [T, "die", "note: 7z x into an empty folder", "rea:inspect-electron-fuses",
                       "rea:analyze-javascript-application", "webcrack"],
    "electron-app":   ["rea:inspect-electron-fuses", "rea:analyze-javascript-application", "webcrack", "runtime:frida"],
    "asar":           ["rea:analyze-javascript-application", "webcrack"],
    "javascript":     [T, "webcrack", "rea:analyze-web-bundle", "audit"],
    "elf":            [T, "die", "rz-bin", "floss", "capa", "rea:analyze", "rea:decompile"],
    "macho":          [T, "die", "rz-bin", "rea:inspect-macho", "rea:decompile"],
    "apk":            [T, "rea:inspect-android-package", "apktool", "jadx", "androguard", "apkleaks",
                       "rea:inspect-apk-signature", "rea:identify-flutter-build", "runtime:adb"],
    "wasm":           ["wasm-objdump", "wasm2wat", "rea:inspect-wasm-artifact"],
    "pcap":           [("tshark", "-q -z conv,ip -r"), "rea:inspect-pcap-capture"],
    "office-macro":   ["olevba", T, "yara-x"],
    "office-ole":     ["olevba", T, "yara-x"],
    "office":         ["olevba", T],
    "sqlite":         ["rea:inspect-sqlite-database"],
    "gguf":           [T, "rea:inspect-model-artifact"],
    "pyc":            ["pydisasm", "rea:inspect-python-pyc"],
    "firmware":       [T, "die", "rea:inspect-firmware-regions", "note: extract-firmware needs Binwalk/Unblob (Linux)",
                       "imhex"],
    "skill-zip":      ["audit", T, "rea:inspect-artifact", "note: read SKILL.md + scripts as untrusted text",
                       "note: run its tests only with the user's yes"],
    "skill-package":  ["audit", "note: read SKILL.md + scripts as untrusted text", "note: run its tests only with the user's yes"],
    "zip":            [T, "die", "audit"],
    "source-folder":  ["audit", "note: rg for subprocess/requests/socket/eval"],
    "unknown":        [T, "die", "yara-x", "imhex"],
}
WHY = {
    "triage": "هاشات ونوع وأقسام وروابط في ثواني", "die": "نوع الملف والكومبايلر والباكر", "capa": "قدرات البرنامج (شبكة، تشفير، حقن…) مع ATT&CK",
    "floss": "النصوص المخفية والمتشفرة", "rz-bin": "الأقسام والاستيراد والتصدير", "upx": "فك ضغط UPX على نسخة",
    "ilspy": "كود C# من ‎.NET", "pyinstxtractor": "فك PyInstaller لملفات ‎.pyc", "pydisasm": "بايت كود ‎.pyc",
    "jadx": "كود Java من APK", "apktool": "Manifest وموارد وsmali", "apkleaks": "روابط ومفاتيح متسابة في APK",
    "androguard": "تحليل APK من بايثون", "webcrack": "فك تشويش وتجميع JS", "wasm-objdump": "دوال WASM والاستيراد",
    "wasm2wat": "WASM لنص مقروء", "tshark": "قراية pcap", "olevba": "ماكرو Office", "yara-x": "قواعد أنماط",
    "audit": "مفاتيح متسابة وأوامر خطرة قبل التثبيت",
}


def step_cmd(step, path):
    py = f'"{sys.executable}"'
    rt = f'"{RETOOL}"'
    q = f'"{path}"'
    if isinstance(step, tuple):
        tool, args = step
    else:
        tool, args = step, ""
    if tool == T:
        return {"tool": "triage", "cmd": f"{py} {rt} triage {q} {args}".strip(), "gate": False, "why": WHY["triage"]}
    if tool == "audit":
        return {"tool": "audit", "cmd": f'python scripts/dragon.py tool re audit {q}', "gate": False, "why": WHY["audit"]}
    if tool.startswith("note:"):
        return {"tool": "note", "cmd": None, "gate": False, "why": tool[5:].strip()}
    if tool.startswith("rea:"):
        c = tool[4:]
        heavy = c in ("decompile", "analyze")
        return {"tool": "rea", "cmd": f"rea {c} {q}", "gate": False,
                "why": "REA: " + c.replace("-", " ") + (" (Ghidra، timeout حوالي 30 دقيقة، بس لو محتاجين الكود نفسه)" if heavy else "")}
    if tool.startswith("runtime:"):
        t = tool.split(":", 1)[1]
        return {"tool": t, "cmd": f"{py} {rt} run {t} ...", "gate": True,
                "why": "وقت التشغيل: محتاج موافقة المستخدم وبرنامج شغال"}
    if tool == "yara-x":
        return {"tool": "yara-x", "cmd": f'{py} {rt} run yara-x scan "{RULES}" {q}', "gate": False, "why": WHY["yara-x"]}
    if tool in WHY or tool in ("imhex",):
        return {"tool": tool, "cmd": f"{py} {rt} run {tool} {args} {q}".replace("  ", " ").strip(),
                "gate": tool in RUNTIME, "why": WHY.get(tool, "محرر هيكس بواجهة (بيتفتح للمستخدم)")}
    raise ValueError(f"unknown chain step: {tool}")


def plan(path):
    ident = identify(path)
    steps = [step_cmd(s, path) for s in CHAINS.get(ident["kind"], CHAINS["unknown"])]
    return {"kind": "black-dragon/re-plan", "target": ident, "steps": steps,
            "not_applicable_note": "Tools outside this chain do not fit this file type: say so in one line per tool.",
            "report_sections": ["Evidence (tool output, quoted)", "Inference (our reading)", "Unknown (not checked / blocked)"],
            "policy": "Static first. Runtime tools only with the user's yes. No cracking, licence bypass or cloning."}


def report_skeleton(p):
    t = p["target"]
    lines = [f"# تقرير تحليل: {Path(t['path']).name}", "",
             f"- النوع (من البايتات): **{t['kind']}**" + (f" · SHA-256 `{t['sha256']}`" if t.get("sha256") else ""), ""]
    for s in p["steps"]:
        lines += [f"## {s['tool']}", f"_{s['why']}_", f"`{s['cmd']}`" if s["cmd"] else "", "- الدليل: ", ""]
    lines += ["## اللي اتأكد بدليل", "- ", "## استنتاج", "- ", "## لسه مجهول", "- ", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- audit (portable regex mirror of the YARA rules)
PATTERNS = [
    ("bd_secret_api_key", "high", re.compile(rb"sk-(?:proj-|live-|ant-)?[A-Za-z0-9_]{32,}|gh[pousr]_[A-Za-z0-9]{36}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{35}|xox[abpr]-[0-9A-Za-z\-]{10,}")),
    ("bd_private_key", "high", re.compile(rb"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----")),
    ("bd_obfuscated_exec", "high", re.compile(rb"exec\(\s*(?:base64|zlib|marshal|codecs)|eval\(\s*(?:base64|atob|unescape)|powershell -enc|-EncodedCommand|FromBase64String", re.I)),
    ("bd_remote_pipe_shell", "high", re.compile(rb"(?:curl|wget) [^\n|]{1,200}\|\s*(?:ba)?sh|(?:iwr|Invoke-WebRequest|irm|Invoke-RestMethod) [^\n|]{1,200}\|\s*iex", re.I)),
    ("bd_credential_read", "high", re.compile(rb"\.ssh/id_rsa|\.aws/credentials|Login Data|\\Google\\Chrome\\User Data")),
    ("bd_destructive_ops", "info", re.compile(rb"shutil\.rmtree|Remove-Item -Recurse|rm -rf")),
    ("bd_shell_true", "info", re.compile(rb"shell=True")),
]
TEST_HINT = re.compile(r"(^|[\\/])(tests?|fixtures?|examples?)([\\/]|$)|test_", re.I)
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".sh", ".ps1", ".bat", ".cmd", ".vbs", ".psm1"}
ACK = HERE / "rules" / "reviewed_hits.json"   # hits a human already read and explained (file suffix + rule + reason)


def context_of(rel):
    if TEST_HINT.search(rel):
        return "test/fixture"
    return "code" if Path(rel).suffix.lower() in CODE_EXT or not Path(rel).suffix else "doc/data"


def load_ack(path=ACK):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def acked(hit, acks):
    f = hit["file"].replace("\\", "/")
    return next((a["reason"] for a in acks if f.endswith(a["file"]) and a["rule"] == hit["rule"]), None)


def _mask(s):
    s = s.decode("latin-1")
    return s if len(s) <= 14 else s[:10] + "…[masked]"


def scan_tree(root):
    hits = []
    for p in sorted(Path(root).rglob("*")):
        if not p.is_file() or {".git", "node_modules", "__pycache__"} & set(p.parts):
            continue
        if p.suffix.lower() not in TEXT_EXT and p.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        rel = str(p.relative_to(root))
        for rule, sev, rx in PATTERNS:
            m = rx.search(data)
            if m:
                hits.append({"rule": rule, "severity": sev, "file": rel, "sample": _mask(m.group(0)),
                             "line": data[:m.start()].count(b"\n") + 1, "context": context_of(rel)})
    return hits


def yara_x(root):
    """Second opinion with the real YARA-X engine when the retool box is present (rule names only)."""
    if not RETOOL.is_file():
        return None
    try:
        r = subprocess.run([sys.executable, str(RETOOL), "run", "yara-x", "scan", "-r", str(RULES), str(root)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    except (OSError, subprocess.TimeoutExpired):
        return None
    rows = [l.split(" ", 1) for l in r.stdout.splitlines() if l.startswith("bd_")]
    return [{"rule": a, "file": os.path.relpath(b.strip(), root)} for a, b in rows if b]


def safe_extract(zpath, dest):
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():
            target = (Path(dest) / n).resolve()
            if not str(target).startswith(str(Path(dest).resolve())):
                raise ValueError(f"zip path escapes the folder: {n}")
        z.extractall(dest)


def audit(path, ack_file=ACK):
    acks = load_ack(ack_file)
    p = Path(path)
    tmp = None
    if p.is_file() and zipfile.is_zipfile(p):
        tmp = tempfile.mkdtemp(prefix="bd_audit_")
        safe_extract(p, tmp)
        root = Path(tmp)
    elif p.is_dir():
        root = p
    else:
        root = Path(tempfile.mkdtemp(prefix="bd_audit_")); tmp = str(root)
        shutil.copy2(p, root / p.name)
    try:
        hits = scan_tree(root)
        yx = yara_x(root)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    for h in hits:
        h["reviewed"] = acked(h, acks)
    high = [h for h in hits if h["severity"] == "high" and h["context"] == "code" and not h["reviewed"]]
    hi = lambda ctx: sum(h["severity"] == "high" and h["context"] == ctx for h in hits)
    return {"kind": "black-dragon/re-audit", "target": str(p), "files_hit": len({h["file"] for h in hits}),
            "high_in_code": len(high), "high_reviewed": sum(bool(h["reviewed"]) and h["severity"] == "high" for h in hits),
            "high_in_tests": hi("test/fixture"), "high_in_docs": hi("doc/data"),
            "info": sum(h["severity"] == "info" for h in hits), "verdict": "REVIEW" if high else "CLEAN_STATIC",
            "hits": hits, "yara_x": yx,
            "note": "Static pattern scan: a hit is evidence that the text exists, not that it runs. CLEAN_STATIC is not a guarantee."}


# ---------------------------------------------------------------- investigate: run the safe static steps, fill the evidence
AUTO = {"triage", "die", "audit"}   # fast, read-only; everything else is listed as pending


def _capture(args, timeout=300):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run([sys.executable, str(RETOOL)] + args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 99, "", f"{type(e).__name__}: {e}"


def investigate(path, out_dir):
    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} مش فاضي")
    out.mkdir(parents=True, exist_ok=True)
    p = plan(path)
    ev = {"target": p["target"], "ran": [], "pending": [], "not_applicable": []}
    for s in p["steps"]:
        if s["tool"] == "note":
            continue
        if s["tool"] not in AUTO or s["gate"]:
            ev["pending"].append({"tool": s["tool"], "why": s["why"], "cmd": s["cmd"], "gated": s["gate"]})
            continue
        if s["tool"] == "audit":
            ev["ran"].append({"tool": "audit", "result": audit(path)})
            continue
        if not RETOOL.is_file():
            ev["pending"].append({"tool": s["tool"], "why": "retool مش موجود", "cmd": s["cmd"], "gated": False})
            continue
        args = (["triage", str(path), "--json"] + (["--deep"] if "--deep" in (s["cmd"] or "") else [])
                if s["tool"] == "triage" else ["run", "die", "-j", str(path)])
        code, so, se = _capture(args, timeout=900)
        try:
            data = json.loads(so)
        except ValueError:
            data = so[-6000:]
        ev["ran"].append({"tool": s["tool"], "exit": code, "result": data, "stderr": se[-1500:]})
    used = {s["tool"] for s in p["steps"]}
    ev["not_applicable"] = sorted(set(WHY) - used - {"triage", "audit"})
    (out / "evidence.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "report.md").write_text(render_report(ev), encoding="utf-8")
    return ev


def _short(v, n=900):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= n else s[:n] + " …"


def render_report(ev):
    t = ev["target"]
    L = [f"# تقرير تحليل: {Path(t['path']).name}", "",
         f"- النوع من البايتات: **{t['kind']}**" + (f" · SHA-256 `{t['sha256']}`" if t.get("sha256") else ""), ""]
    for r in ev["ran"]:
        L += [f"## {r['tool']} (اتشغّل)", "```", _short(r["result"]), "```", ""]
    for r in ev["pending"]:
        L += [f"## {r['tool']} ({'محتاج موافقة' if r['gated'] else 'لسه'})", f"_{r['why']}_",
              f"`{r['cmd']}`" if r["cmd"] else "", ""]
    if ev["not_applicable"]:
        L += ["## أدوات مش مناسبة للنوع ده", "- " + "، ".join(ev["not_applicable"]), ""]
    L += ["## اللي اتأكد بدليل", "- (من الأقسام اللي اتشغّلت فوق بس)", "## استنتاج", "- ", "## لسه مجهول",
          "- " + "، ".join(r["tool"] for r in ev["pending"]) if ev["pending"] else "- ", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- CLI

def retool(args, capture=False):
    if not RETOOL.is_file():
        print(f"retool مش موجود: {RETOOL} (حدده بـ DRAGON_RETOOL)", file=sys.stderr)
        return 4
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.call([sys.executable, str(RETOOL)] + args, env=env)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="dragon.py tool re", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    pl = sub.add_parser("plan"); pl.add_argument("path"); pl.add_argument("--json", action="store_true")
    pl.add_argument("--report", help="write an Arabic report skeleton (evidence/inference/unknown) here")
    au = sub.add_parser("audit"); au.add_argument("path"); au.add_argument("--json", action="store_true")
    iv = sub.add_parser("investigate", help="run the safe static steps and write report.md + evidence.json")
    iv.add_argument("path"); iv.add_argument("--out", required=True)
    tr = sub.add_parser("triage"); tr.add_argument("path"); tr.add_argument("--deep", action="store_true")
    tr.add_argument("--out")
    rn = sub.add_parser("run"); rn.add_argument("--yes", action="store_true"); rn.add_argument("id")
    a, extra = ap.parse_known_args(argv)
    if a.cmd != "run" and extra:
        ap.error("unrecognized arguments: " + " ".join(extra))

    if a.cmd == "doctor":
        print(f"retool: {'✓ ' + str(RETOOL) if RETOOL.is_file() else '✗ مش موجود'}")
        print(f"rea: {'✓ ' + shutil.which('rea') if shutil.which('rea') else '✗ مش على الـ PATH'}")
        print(f"rules: {RULES}")
        return retool(["list"]) if RETOOL.is_file() else 4
    if a.cmd == "plan":
        p = plan(a.path)
        if a.report:
            out = Path(a.report)
            if out.exists():
                print(f"موجود: {out} (اختار اسم تاني)", file=sys.stderr); return 2
            out.write_text(report_skeleton(p), encoding="utf-8")
            p["report_written"] = str(out)
        if a.json:
            print(json.dumps(p, ensure_ascii=False, indent=1)); return 0
        t = p["target"]
        print(f"النوع: {t['kind']}" + (f" · {t['size']:,} بايت" if t.get("size") else ""))
        for i, s in enumerate(p["steps"], 1):
            print(f"  {i}. {s['tool']}{' 🔒 موافقة' if s['gate'] else ''} — {s['why']}")
            if s["cmd"]:
                print(f"     $ {s['cmd']}")
        print(p["policy"])
        return 0
    if a.cmd == "audit":
        r = audit(a.path)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["verdict"] != "REVIEW" else 1
        print(f"الحكم: {r['verdict']} · خطر في كود بيشتغل {r['high_in_code']} · اتراجع قبل كده {r['high_reviewed']} · "
              f"في اختبارات/أمثلة {r['high_in_tests']} · في نصوص وصف/بيانات {r['high_in_docs']} · معلومات {r['info']}")
        for h in sorted(r["hits"], key=lambda h: (h["severity"] != "high", h["context"] != "code", bool(h["reviewed"]), h["file"])):
            if h["severity"] == "high":
                tag = f" ✓ {h['reviewed']}" if h["reviewed"] else ""
                print(f"  [{h['context']}] {h['rule']} {h['file']}:{h['line']}  {h['sample']}{tag}")
        if r["yara_x"] is not None:
            print(f"YARA-X: {len(r['yara_x'])} تطابق (رأي تاني من المحرك الحقيقي)")
        print(r["note"])
        return 0 if r["verdict"] != "REVIEW" else 1
    if a.cmd == "investigate":
        try:
            ev = investigate(a.path, a.out)
        except FileExistsError as e:
            print(e, file=sys.stderr); return 2
        print(f"اتشغّل: {', '.join(r['tool'] for r in ev['ran']) or '—'} · لسه: {len(ev['pending'])} خطوة")
        print(f"التقرير: {Path(a.out) / 'report.md'}")
        return 0
    if a.cmd == "triage":
        return retool(["triage", a.path] + (["--deep"] if a.deep else []) + (["--out", a.out] if a.out else []))
    if a.cmd == "run":
        if a.id in RUNTIME and not a.yes:
            print(f"{a.id} بيشتغل على برنامج شغال أو بيفتح واجهة أو بيلتقط ترافيك. اسأل المستخدم، وبعد موافقته زوّد --yes.",
                  file=sys.stderr)
            return 3
        return retool(["run", a.id] + extra)


if __name__ == "__main__":
    sys.exit(main())
