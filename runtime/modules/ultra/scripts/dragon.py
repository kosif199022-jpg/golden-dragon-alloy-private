"""Black Dragon Ultra — one front door for every KOSIF module.

python dragon.py where                      # repo root and module count
python dragon.py modules [--json]           # every module with its purpose
python dragon.py route "task" [--top 4]     # which modules fit this task, and how to start each
python dragon.py needs MODULE               # tools one module really imports or calls (static scan)
python dragon.py doctor [--tier T] [--json] # unified tool protocol: what is installed, what is missing
python dragon.py install TIER               # system | core | node | heavy | agents
python dragon.py find "task"                # Superpowers hub: tools + catalog powers for the task
python dragon.py think "task"               # Dragon Mind: 26 faculties, six-stage thinking
python dragon.py plan "task" [--build-index]# Black Dragon: merged method plan from 7,400+ sources
python dragon.py cycle "task"               # route + find + think + plan -> out/dragon/<slug>/DRAGON.md
python dragon.py exec MODULE SCRIPT [args]  # run a module script from the repo root (right python/node, PATH, KOSIF_ROOT)
python dragon.py verify FILE... [--out ev.json]  # measure real outputs: duration, size, resolution, loudness
python dragon.py learn "task" --modules M.. --result passed|failed [--note] [--evidence]  # memory that boosts routing
"""
from __future__ import annotations

import argparse, ast, datetime, glob, importlib.util, json, os, re, shutil, subprocess, sys, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
PY = sys.executable
ME = SKILL.name


# ---------------- repo location ----------------
def repo_root() -> Path:
    if os.environ.get("KOSIF_ROOT"):
        return Path(os.environ["KOSIF_ROOT"]).resolve()
    cfg = SKILL / "dragon.json"
    if cfg.exists():
        p = Path(json.loads(cfg.read_text(encoding="utf-8"))["repo_root"])
        if (p / ".claude" / "skills").is_dir():
            return p.resolve()
    for p in [SKILL, *SKILL.parents]:
        if (p / ".claude" / "skills" / "kosif-superpowers").is_dir():
            return p.resolve()
    sys.exit("KOSIF repo not found. Set KOSIF_ROOT or write dragon.json {\"repo_root\": \"...\"} next to SKILL.md")


ROOT = repo_root()
MODS = ROOT / ".claude" / "skills"
ENV = {**os.environ, "KOSIF_ROOT": str(ROOT), "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
TOOLS = json.loads((SKILL / "tools.json").read_text(encoding="utf-8"))


# ---------------- text matching (Arabic-aware) ----------------
AR_DIAC = re.compile(r"[\u064B-\u065F\u0670\u0640]")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s.lower())
    s = AR_DIAC.sub("", s)
    s = re.sub("[أإآٱ]", "ا", s).replace("ة", "ه").replace("ى", "ي")
    return s


STOP = set("""the a an and or of to in on at by for from with then than into onto is are be been it its this that these those
my your our their me you we they i as so do does make use using get want need please can could would should will also just
\u0641\u064A \u0645\u0646 \u0639\u0644\u0649 \u0645\u0639 \u0639\u0646 \u0627\u0644\u0649 \u0627\u0644\u064A \u0627\u0644\u0627 \u0647\u0630\u0627 \u0647\u0630\u0647 \u0630\u0644\u0643 \u062B\u0645 \u0627\u0648 \u0627\u0646 \u0627\u0646\u0627 \u0644\u064A \u0644\u0643 \u0639\u0627\u064A\u0632 \u0627\u0631\u064A\u062F \u0627\u0628\u063A\u064A \u0645\u0645\u0643\u0646 \u0643\u0644 \u0628\u0639\u0636""".split())


def tokens(s: str) -> set[str]:
    out = set()
    for t in re.findall(r"[\w\u0600-\u06FF]+", norm(s)):
        if len(t) < 2 or t in STOP: continue
        out.add(t)
        for pre in ("وال", "بال", "لل", "ال", "و"):
            if t.startswith(pre) and len(t) - len(pre) >= 3:
                out.add(t[len(pre):]); break
    return out


# extra trigger words per module (Arabic + English), on top of each SKILL.md's own text
TRIGGERS = {
    "video-montage": "مونتاج قص دمج فيديو ترجمه موسيقي ريلز تيك توك تصدير ffmpeg montage edit cut trim subtitles",
    "image-studio": "صوره صور فلتر قص خلفيه ازاله شعار بوست فوتوشوب raw psd ترميم الوان photo image crop background",
    "kosif-web-film": "فيديو موشن انترو برومو اعلان كينتك فيلم صفحه ويب motion intro promo explainer",
    "kosif-voice-studio": "صوت تعليق صوتي استنساخ تفريغ ترجمه srt tts voice dubbing transcription",
    "kosif-reel-hooks": "ريل هوك سكريبت فكره فيديو قصير اكتب reel hook script",
    "kosif-kling-director": "كلينج فيلم قصير برومبت ستوري بورد kling storyboard prompt",
    "kosif-shadow-theatre": "ظل ظلال مسرح سلويت silhouette shadow",
    "kosif-infinite-matrices": "اسلوب بصري جديد ابتكار مصفوفه نظام حركه style invent recipe",
    "kosif-site-snapshot": "نسخ موقع اوفلاين الوان خطوط موقعي clone snapshot website design",
    "living-site": "موقع حي ثلاثي الابعاد spline موقع ويب landing website 3d",
    "editorial-film-edit": "ارشيف تحريري حبيبات فيلم نص حركي editorial archival grain",
    "kosif-instagram-discovery": "انستجرام مرجع ريلز بحث instagram reference",
    "kosif-instagram-video-research": "انستجرام بحث مراجع منشئ instagram research creator",
    "kosif-upload-link": "رفع ملفات رابط الرفع كبير upload big file",
    "kosif-superpowers": "قدرات قدراتك تقدر تعمل ايه خريطه ذهنيه رسم ثلاثي بيانات مستندات excel pdf powers capability",
    "kosif-dragon-mind": "فكر عقل التنين فكك القدرات خطط think decompose",
    "kosif-black-dragon": "التنين الاسود دمج مصادر خطه fusion plan",
    "kosif-skills-atlas": "برمجه devops mcp وكيل منتج كتابه بحث code agent product research",
    "kosif-superskills-library": "كتابه نسخ اعلاني كود بيانات اكسل تصميم بزنس copywriting excel business",
    "obra-superpowers": "خطه تنفيذ اختبار اختبارات تصحيح خطا باج مراجعه كود عصف tdd debug debugging bug test tests brainstorm review refactor subagents plan plans write execute implement",
    "reverse-engineer-anything": "هندسه عكسيه تحليل برنامج تطبيق ثنائي rea reverse engineer binary decompile",
}


def read_module(d: Path) -> dict | None:
    f = d / "SKILL.md"
    if not f.exists(): return None
    text = f.read_text(encoding="utf-8", errors="ignore")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    fm = m.group(1) if m else ""
    name = (re.search(r"^name:\s*(.+)$", fm, re.M) or [None, d.name])[1].strip().strip('"')
    dm = re.search(r"^description:\s*(.*)$((?:\n[ \t]+.*)*)", fm, re.M)
    desc = ""
    if dm:
        first, rest = dm.group(1).strip(), dm.group(2)
        desc = " ".join(x.strip() for x in rest.splitlines() if x.strip()) if first in (">-", ">", "|", "|-", "") else first + " " + " ".join(x.strip() for x in rest.splitlines() if x.strip())
        desc = desc.strip().strip('"').strip("'")
    body = text[m.end():] if m else text
    cmds = []
    for line in body.splitlines():
        l = line.strip().strip("`")
        if re.match(r"^(python3?|node|npx|bash|ffmpeg)\s", l) and len(cmds) < 3:
            cmds.append(l[:200])
    heads = " ".join(re.findall(r"^#+\s*(.+)$", body, re.M))
    return {"dir": d.name, "name": name, "description": desc, "skill_md": str(f), "commands": cmds,
            "bag_hi": tokens(name + " " + desc + " " + TRIGGERS.get(d.name, "")),
            "bag_lo": tokens(heads + " " + body[:6000])}


def all_modules() -> list[dict]:
    out = []
    for d in sorted(MODS.iterdir()):
        if d.is_dir() and d.name != ME:
            m = read_module(d)
            if m: out.append(m)
    return out


# ---------------- commands ----------------
def cmd_where(a):
    mods = all_modules()
    print(f"repo   {ROOT}\nmodules {len(mods)}\nskill  {SKILL}")


def cmd_modules(a):
    mods = all_modules()
    if a.json:
        print(json.dumps([{k: v for k, v in m.items() if not k.startswith("bag")} for m in mods], ensure_ascii=False, indent=1)); return
    for m in mods:
        print(f"- {m['dir']:<32} {m['description'][:150]}")


BRAINS = {"kosif-black-dragon", "kosif-dragon-mind", "kosif-superpowers"}  # used by `cycle` anyway
LEDGER = ROOT / "out" / "dragon" / "ledger.jsonl"


def ledger_boost(task: str) -> dict[str, float]:
    """Modules that succeeded on similar past tasks get a bonus (Jaccard similarity of task words)."""
    boost: dict[str, float] = {}
    if not LEDGER.exists(): return boost
    t = tokens(task)
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try: rec = json.loads(line)
        except json.JSONDecodeError: continue
        past = tokens(rec.get("task", "")); sim = len(t & past) / max(1, len(t | past))
        if sim < .2: continue
        sign = 1 if rec.get("result") == "passed" else -0.5
        for m in rec.get("modules", []): boost[m] = boost.get(m, 0) + sign * sim * 6
    return boost


def score(task: str, m: dict) -> float:
    t = tokens(task)
    hi = len(t & m["bag_hi"]); lo = len(t & m["bag_lo"])
    s = hi * 3 + lo * 0.5
    if m["dir"] in BRAINS and not (t & tokens(TRIGGERS.get(m["dir"], ""))): s *= .3
    return s


def route(task: str, top: int = 4) -> list[dict]:
    boost = ledger_boost(task)
    ranked = sorted(((score(task, m) + boost.get(m["dir"], 0), m) for m in all_modules()), key=lambda x: -x[0])
    return [dict(m, score=round(s, 1), learned=round(boost.get(m["dir"], 0), 1)) for s, m in ranked[:top] if s > 0]


def cmd_route(a):
    hits = route(a.task, a.top)
    if not hits:
        print("No module matched. Start with: python dragon.py find \"<task>\" (Superpowers hub)"); return
    for h in hits:
        print(f"\n## {h['dir']}  (score {h['score']})\n{h['description'][:220]}\nread: {h['skill_md']}")
        for c in h["commands"]: print(f"  $ {c}")


# ---- needs (static scan of one module) ----
def module_needs(name: str) -> dict:
    d = MODS / name
    if not d.is_dir(): sys.exit(f"no module '{name}'. See: python dragon.py modules")
    stdlib = set(sys.stdlib_module_names); local = {p.stem for p in d.rglob("*.py")}
    imports: set[str] = set(); exes: set[str] = set()
    for p in d.rglob("*"):
        if not p.is_file() or any(x in p.parts for x in ("node_modules", "vendor", "__pycache__")): continue
        if p.suffix == ".py":
            try: tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError: continue
            for n in ast.walk(tree):
                ms = [x.name for x in n.names] if isinstance(n, ast.Import) else [n.module] if isinstance(n, ast.ImportFrom) and n.module and n.level == 0 else []
                for mname in ms:
                    top = mname.split(".")[0]
                    if top not in stdlib and top not in local and not top.startswith("_"): imports.add(top)
        if p.suffix in (".py", ".js", ".mjs", ".sh", ".ps1"):
            txt = p.read_text(encoding="utf-8", errors="ignore")
            for exe in ("ffmpeg", "ffprobe", "node", "npx", "magick", "tesseract", "git", "blender", "exiftool"):
                # only real calls: in a quoted command string or a subprocess/which call, not prose
                if re.search(rf"""(["'\[]\s*{exe}(\.exe)?\s*["',\s]|which\(\s*["']{exe}["']|^\s*{exe}\s+-)""", txt, re.M): exes.add(exe)
    known = {imp: pip for tier in TOOLS["tiers"].values() for imp, pip in tier.get("python", [])}
    return {"module": name,
            "python": [{"import": i, "pip": known.get(i, i), "ok": importlib.util.find_spec(i) is not None} for i in sorted(imports)],
            "programs": [{"cmd": e, "ok": bool(find_exe(e))} for e in sorted(exes)]}


def cmd_needs(a):
    n = module_needs(a.module)
    if a.json: print(json.dumps(n, ensure_ascii=False, indent=1)); return
    print(f"# {n['module']}")
    for x in n["python"]: print(f"  {'OK' if x['ok'] else '--'}  py  {x['import']:<22} pip install {x['pip']}")
    for x in n["programs"]: print(f"  {'OK' if x['ok'] else '--'}  exe {x['cmd']}")


# ---- doctor / install ----
def find_exe(cmd: str) -> str | None:
    p = shutil.which(cmd)
    if p: return p
    roots = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", ""),
             os.path.expandvars(r"%LOCALAPPDATA%\Programs"), os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")]
    for r in filter(None, roots):
        for pat in (f"*/{cmd}.exe", f"*/bin/{cmd}.exe", f"*/*/bin/{cmd}.exe"):
            hits = glob.glob(os.path.join(r, pat))
            if hits: return sorted(hits)[-1]
    return None


def npm_list() -> list[str]:
    f = ROOT / TOOLS["tiers"]["node"]["npm_file"]
    return [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")] if f.exists() else []


def npm_ok(spec: str) -> bool:
    name = spec.rsplit("@", 1)[0] if spec.count("@") > (1 if spec.startswith("@") else 0) else spec
    return (ROOT / "node_modules" / name / "package.json").exists()


def browser_ok(name: str) -> bool:
    base = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright")
    return any(base.glob(f"{name}-*"))


def doctor(tiers: list[str]) -> dict:
    rep = {}
    for t in tiers:
        spec = TOOLS["tiers"][t]; rows = []
        for e in spec.get("exe", []):
            p = find_exe(e["cmd"]); rows.append({"name": e["cmd"], "ok": bool(p), "detail": p or f"winget install -e --id {e['winget']}"})
        for imp, pip in spec.get("python", []):
            ok = importlib.util.find_spec(imp.split(".")[0]) is not None
            rows.append({"name": imp, "ok": ok, "detail": "installed" if ok else f"pip install {pip}"})
        for b in spec.get("browsers", []):
            ok = browser_ok(b); rows.append({"name": f"playwright:{b}", "ok": ok, "detail": "installed" if ok else f"python -m playwright install {b}"})
        if t == "node":
            for s in npm_list():
                ok = npm_ok(s); rows.append({"name": s, "ok": ok, "detail": "installed" if ok else "npm install --no-save"})
        rep[t] = rows
    return rep


def cmd_doctor(a):
    tiers = [a.tier] if a.tier else list(TOOLS["tiers"])
    rep = doctor(tiers)
    if a.json: print(json.dumps(rep, ensure_ascii=False, indent=1)); return
    for t, rows in rep.items():
        ok = sum(r["ok"] for r in rows)
        print(f"\n== {t}: {ok}/{len(rows)} ready — {TOOLS['tiers'][t]['why']}")
        for r in rows:
            if not r["ok"] or a.verbose: print(f"  {'OK' if r['ok'] else '--'}  {r['name']:<28} {r['detail']}")
    core_ok = all(r["ok"] for t in ("system", "core") if t in rep for r in rep[t])
    print("\nREADY" if core_ok else "\nNOT READY: python dragon.py install system && python dragon.py install core")


def cmd_install(a):
    t = a.tier; spec = TOOLS["tiers"].get(t)
    if not spec: sys.exit(f"tiers: {', '.join(TOOLS['tiers'])}")
    if t == "agents" and not a.yes:
        sys.exit("agents tier = paid/keyed SDKs. Ask the user, then rerun with --yes.")
    for e in spec.get("exe", []):
        if not find_exe(e["cmd"]):
            print(f"[winget] {e['winget']}")
            # --source winget: avoids the msstore source, whose network errors make winget stop and ask
            subprocess.run(["winget", "install", "-e", "--id", e["winget"], "--source", "winget",
                            "--accept-source-agreements", "--accept-package-agreements"])
    missing = [pip for imp, pip in spec.get("python", []) if importlib.util.find_spec(imp.split(".")[0]) is None]
    if missing:
        extra = ["--index-url", spec["torch_index"], "--extra-index-url", "https://pypi.org/simple"] if t == "heavy" and "torch" in missing else []
        print(f"[pip] {len(missing)} packages")
        r = subprocess.run([PY, "-m", "pip", "install", "--disable-pip-version-check", *extra, *missing])
        if r.returncode:  # retry one by one so a single bad wheel does not block the rest
            for pkg in missing:
                subprocess.run([PY, "-m", "pip", "install", "--disable-pip-version-check", *extra, pkg])
    for b in spec.get("browsers", []):
        if not browser_ok(b): subprocess.run([PY, "-m", "playwright", "install", b])
    if t == "node":
        todo = [s for s in npm_list() if not npm_ok(s)]
        if todo:
            npm = find_exe("npm") or "npm"
            print(f"[npm] {len(todo)} packages into {ROOT / 'node_modules'}")
            subprocess.run([npm, "install", "--no-save", "--no-audit", "--no-fund", *todo], cwd=ROOT, shell=os.name == "nt")
    cmd_doctor(argparse.Namespace(tier=t, json=False, verbose=False))


# ---- delegations to existing engines (run from repo root so their paths keep working) ----
def tool_env() -> dict:
    """ENV plus the folders of tools installed this session but not yet on PATH (winget, Program Files)."""
    env = dict(ENV); extra = []
    for e in TOOLS["tiers"]["system"]["exe"]:
        if not shutil.which(e["cmd"]):
            p = find_exe(e["cmd"])
            if p: extra.append(str(Path(p).parent))
    if extra: env["PATH"] = os.pathsep.join(dict.fromkeys(extra)) + os.pathsep + env.get("PATH", "")
    return env


def run_mod(rel: str, *args: str, capture=False):
    script = MODS / rel
    if not script.exists(): sys.exit(f"missing {script}")
    return subprocess.run([PY, str(script), *args], cwd=ROOT, env=tool_env(), text=True, encoding="utf-8",
                          capture_output=capture)


def slug(task: str) -> str:
    s = re.sub(r"[^\w\u0600-\u06FF]+", "-", task).strip("-")[:40] or "task"
    return f"{datetime.date.today():%Y%m%d}-{s}"


INDEX = Path("out/black-dragon-fusion-01")


def cmd_find(a):
    run_mod("kosif-superpowers/scripts/hub.py", "find", a.task)


def cmd_think(a, out: Path | None = None):
    out = out or ROOT / "out" / "dragon" / slug(a.task) / "mind"
    out.mkdir(parents=True, exist_ok=True)
    return run_mod("kosif-dragon-mind/scripts/dragon_mind.py", "think", a.task, "--out", str(out))


def ensure_index(build: bool):
    if (ROOT / INDEX / "sources.jsonl").exists(): return True
    if not build:
        print(f"Black Dragon index missing ({INDEX}). Build once (~5 min): python dragon.py plan \"...\" --build-index"); return False
    print("building Black Dragon index (~5 min, 7,400+ sources)…")
    return run_mod("kosif-black-dragon/scripts/black_dragon.py", "index", "--out", str(INDEX)).returncode == 0


def cmd_plan(a, save: Path | None = None):
    if not ensure_index(a.build_index): return None
    save = save or ROOT / "out" / "dragon" / slug(a.task) / "plan.md"
    save.parent.mkdir(parents=True, exist_ok=True)
    run_mod("kosif-black-dragon/scripts/black_dragon.py", "plan", a.task, "--index", str(INDEX / "sources.jsonl"), "--save", str(save))
    return save


def cmd_cycle(a):
    job = ROOT / "out" / "dragon" / slug(a.task); job.mkdir(parents=True, exist_ok=True)
    hits = route(a.task, 4)
    lines = [f"# التنين الأسود الفائق — {a.task}", "", f"*{datetime.datetime.now():%Y-%m-%d %H:%M} · plan, not execution — run the steps, then verify real outputs.*", "",
             "## 1. الوحدات المختارة (route)"]
    for h in hits:
        n = module_needs(h["dir"]); miss = [x["pip"] for x in n["python"] if not x["ok"]] + [x["cmd"] for x in n["programs"] if not x["ok"]]
        lines += [f"- **{h['dir']}** (score {h['score']}): {h['description'][:160]}", f"  - read `{h['skill_md']}`",
                  *[f"  - `{c}`" for c in h["commands"][:2]],
                  f"  - tools: {'all present' if not miss else 'missing → ' + ', '.join(miss[:8])}"]
    lines += ["", "## 2. القدرات من السوبر باور (find)", "```"]
    f = run_mod("kosif-superpowers/scripts/hub.py", "find", a.task, capture=True)
    lines += [(f.stdout or f.stderr or "").strip()[:4000], "```", "", "## 3. عقل التنين (think)"]
    t = cmd_think(a, job / "mind")
    lines.append(f"- trace: `{job / 'mind'}` (exit {t.returncode})" if t else "- skipped")
    lines += ["", "## 4. خطة التنين الأسود (plan)"]
    p = cmd_plan(a, job / "plan.md")
    if p and p.exists(): lines.append(p.read_text(encoding="utf-8"))
    else: lines.append("- index missing: rerun with --build-index")
    lines += ["", "## 5. التحقق", "- Run only the commands the plan needs. Report real files, sizes and durations. Never mark done without an output you checked."]
    (job / "DRAGON.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nDRAGON.md -> {job / 'DRAGON.md'}")


# ---- exec: run any module script from the repo root with the right interpreter, PATH and KOSIF_ROOT ----
def cmd_exec(a):
    d = MODS / a.module
    if not d.is_dir(): sys.exit(f"no module '{a.module}'. See: python dragon.py modules")
    script = (d / a.script).resolve()
    if not script.is_relative_to(d.resolve()) or not script.is_file(): sys.exit(f"no script {a.script} inside {a.module}")
    args = [x for x in a.args if x != "--"]
    if script.suffix in (".js", ".mjs"):
        cmd = [find_exe("node") or "node", str(script), *args]
    else:
        cmd = [PY, str(script), *args]
    sys.exit(subprocess.run(cmd, cwd=ROOT, env=tool_env()).returncode)


# ---- verify: measure real outputs, write an evidence file ----
def probe_file(p: Path) -> dict:
    r: dict = {"path": str(p), "exists": p.exists()}
    if not p.exists(): return r
    r["bytes"] = p.stat().st_size
    ext = p.suffix.lower()
    if ext in (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"):
        fp = find_exe("ffprobe")
        if fp:
            out = subprocess.run([fp, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
                                  "-of", "json", str(p)], capture_output=True, text=True, encoding="utf-8")
            try:
                j = json.loads(out.stdout); r["duration_s"] = round(float(j["format"]["duration"]), 3)
                r["streams"] = j.get("streams", [])
            except Exception as e: r["error"] = f"ffprobe: {e}"
            ff = find_exe("ffmpeg")
            if ff and any(s.get("codec_type") == "audio" for s in r.get("streams", [])):
                o = subprocess.run([ff, "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
                                   capture_output=True, text=True, encoding="utf-8", errors="ignore")
                m = re.search(r"I:\s*(-?[\d.]+) LUFS", o.stderr)
                if m: r["loudness_lufs"] = float(m.group(1))
        else: r["error"] = "ffprobe missing"
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"):
        try:
            from PIL import Image
            with Image.open(p) as im: r.update(width=im.width, height=im.height, mode=im.mode, format=im.format)
        except Exception as e: r["error"] = f"image: {e}"
    elif ext in (".html", ".md", ".txt", ".json", ".srt", ".vtt"):
        txt = p.read_text(encoding="utf-8", errors="ignore"); r.update(chars=len(txt), lines=txt.count("\n") + 1)
        if ext == ".json":
            try: json.loads(txt); r["json_valid"] = True
            except json.JSONDecodeError as e: r["json_valid"] = False; r["error"] = str(e)
    r["ok"] = r["exists"] and r.get("bytes", 0) > 0 and "error" not in r
    return r


def cmd_verify(a):
    rows = [probe_file(Path(x)) for x in a.files]
    for r in rows:
        bits = [f"{k}={r[k]}" for k in ("duration_s", "width", "height", "loudness_lufs", "chars", "json_valid") if k in r]
        vid = next((s for s in r.get("streams", []) if s.get("codec_type") == "video"), None)
        if vid: bits.append(f"{vid.get('width')}x{vid.get('height')} {vid.get('codec_name')}")
        print(f"{'OK ' if r.get('ok') else 'FAIL'} {r['path']}  {r.get('bytes', 0) // 1024} KB  " + "  ".join(bits) + (f"  ERROR {r['error']}" if "error" in r else ""))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"verified_at": datetime.datetime.now().isoformat(timespec="seconds"), "files": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"evidence -> {a.out}")
    sys.exit(0 if all(r.get("ok") for r in rows) else 1)


# ---- learn: procedural memory that improves routing ----
def cmd_learn(a):
    known = {m["dir"] for m in all_modules()}
    bad = [m for m in a.modules if m not in known]
    if bad: sys.exit(f"unknown modules: {', '.join(bad)}")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": datetime.datetime.now().isoformat(timespec="seconds"), "task": a.task, "modules": a.modules,
           "result": a.result, "note": a.note, "evidence": a.evidence}
    with LEDGER.open("a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    n = sum(1 for _ in LEDGER.open(encoding="utf-8"))
    print(f"learned ({a.result}): {', '.join(a.modules)}  · ledger has {n} records -> {LEDGER}")


def main():
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("where")
    p = sub.add_parser("modules"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("route"); p.add_argument("task"); p.add_argument("--top", type=int, default=4)
    p = sub.add_parser("needs"); p.add_argument("module"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("doctor"); p.add_argument("--tier"); p.add_argument("--json", action="store_true"); p.add_argument("-v", "--verbose", action="store_true")
    p = sub.add_parser("install"); p.add_argument("tier"); p.add_argument("--yes", action="store_true")
    for n in ("find", "think"):
        p = sub.add_parser(n); p.add_argument("task")
    p = sub.add_parser("plan"); p.add_argument("task"); p.add_argument("--build-index", action="store_true")
    p = sub.add_parser("cycle"); p.add_argument("task"); p.add_argument("--build-index", action="store_true")
    p = sub.add_parser("exec"); p.add_argument("module"); p.add_argument("script"); p.add_argument("args", nargs=argparse.REMAINDER)
    p = sub.add_parser("verify"); p.add_argument("files", nargs="+"); p.add_argument("--out")
    p = sub.add_parser("learn"); p.add_argument("task"); p.add_argument("--modules", nargs="+", required=True)
    p.add_argument("--result", choices=["passed", "failed"], required=True); p.add_argument("--note", default=""); p.add_argument("--evidence", default="")
    a = ap.parse_args()
    {"where": cmd_where, "modules": cmd_modules, "route": cmd_route, "needs": cmd_needs, "doctor": cmd_doctor,
     "install": cmd_install, "find": cmd_find, "think": cmd_think, "plan": cmd_plan, "cycle": cmd_cycle,
     "exec": cmd_exec, "verify": cmd_verify, "learn": cmd_learn}[a.cmd](a)


if __name__ == "__main__":
    main()
