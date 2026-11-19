#!/usr/bin/env python3
"""Black Dragon launcher: one command on claude.ai (cloud) and on the owner's PC.

    python3 scripts/dragon.py where              # which place am I in, which engine copy, which tools exist
    python3 scripts/dragon.py setup [--full]     # install what is missing for this place (pip; PC: also winget plan)
    python3 scripts/dragon.py <dragon command>   # find / show / verify / mux / patch-black / align / lyrics-sheet /
                                                 # cut / beats / words / mix / film / engines / run ...
    python3 scripts/dragon.py chrome <cmd> ...   # v10.6: drive the real Google Chrome (launch tabs snapshot click type text shot pdf …)
    python3 scripts/dragon.py kosif <cmd> ...    # v10.7: accelerated downloads (doctor probe fetch send list …)
    python3 scripts/dragon.py sahab <cmd> ...    # v10.6: «سحاب» cloud browser (start [--open] status url stop serve doctor)
    python3 scripts/dragon.py tool <name> ...    # bundled tools: arena, 3d, motion, cartoon, stickman, stock (free footage/photos),
                                                 # tiktok-post (TikTok photo post: images + music from the page JSON,
                                                 # which yt-dlp cannot fetch), styles (tools/styles/build_style.py)

Place detection (no flags needed):
  * PC     : a local black-dragon repo exists (DRAGON_HOME, Desktop\\التنين الأسود, ~/kosif-own/black-dragon).
             It is used directly, so local skills, old repos, Blender, yt-dlp and GPU models are all in reach.
             When that repo is an older dragon than this skill, a note on stderr says so (it lacks the new commands).
  * cloud  : no local repo (claude.ai sandbox, /mnt/user-data present). The engine bundled in app/ is copied
             to a writable folder (/tmp/dragon) and used there. Outputs go to /mnt/user-data/outputs.
A bundled copy (/tmp/dragon, or ~/.black-dragon/app on a PC without the repo) is copied again when the skill's app/
changes, so an updated skill never runs an old copy (a catalog rebuilt inside the copy is kept).
Override with DRAGON_MODE=pc|cloud or DRAGON_HOME=<folder>.
"""
import json, os, platform, shutil, stat, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
APP = SKILL / "app"
HOME = Path.home()
PC_CANDIDATES = [
    HOME / "OneDrive" / "Desktop" / "التنين الأسود",
    HOME / "OneDrive" / "Desktop" / "مهارات" / "التنين الأسود",   # the folder moved into «مهارات» on 2026-11-15
    HOME / "Desktop" / "التنين الأسود",
    HOME / "kosif-own" / "black-dragon",
]
OLD_REPOS = {"kosif-tool": next((p for p in (HOME / "kosif-tool", HOME / "kosif-own" / "kosif-tool") if p.exists()),
                                HOME / "kosif-own" / "kosif-tool"),  # v10.13: ~/kosif-tool is the current checkout
"kosif-atlas": HOME / "kosif-own" / "kosif-atlas",
             "100-superskills": HOME / "kosif-own" / "100-superskills", "fastify-motion-bro": HOME / "kosif-own" / "fastify-motion-bro"}
PROGRAMS = ["ffmpeg", "ffprobe", "node", "blender", "yt-dlp", "magick", "tesseract", "auto-editor", "nvidia-smi", "git", "upscayl-bin", "rembg", "deep-filter", "inkscape", "melt", "aria2c"]
TOOLS = {  # name -> script inside the skill
    "arena": "tools/arena/bracket.py",
    "montage-arena": "skills/montage-arena/scripts/arena.py",  # v1990.2: independent adversarial edit decision arena
    "windows-lint": "skills/windows-commands/scripts/wincmd_lint.py",  # v1990.2: static Windows command audit, never executes input
    "3d": "tools/studio/build_studio.py",
    "blender-pro": "tools/blender-pro/bridge.py",
    "creativity": "tools/absolute_creativity/bridge.py",
    "rea-ultra": "tools/rea_ultra/bridge.py",
    "visual-forge": "tools/visual_forge/bridge.py",
    "physics": "tools/physics_math/bridge.py",
    "motion": "tools/studio/motion_styles.py",
    "stickman": "tools/stickman/stickman_kit.py",
    "cinema-craft": "tools/cinema_craft/cinema_craft.py",  # v10.17.3: reviewed spec audit/style and non-destructive frame-tested trim
    "reel-dna": "tools/reel_dna/reel_dna.py",  # v10.17.2: extract Katana report timing; plan and render with owned media only
    "looks": "tools/looks/looks.py",  # v1990.5: the couple, outfits, expressions, scenes, styles, layouts and models we settled on (with pictures)
    "lyric": "tools/lyric_couple/mk.py",  # v1990.5: build a lyric film page from spec.json (render with tools/lyric_couple/render.sh)
    "mono": "tools/mono_story/build.py",  # v1990.7: animated shots / stills + subtitle looks (ink, comic, khawater) + doodle card (ST07, ST08)
    "library": "tools/library/library.py",     # v10.17: the owner's 12 skill packs + prompt libraries: list | show | find | prompts | prompt | grep | doc (restored in v1990.9)
    "codekit": "tools/codekit/codekit.py",  # v1990.8: the 12 code-video tools (status / map / install / demo / vendor-gsap)
    "video12": "tools/video12/video12.py",  # owner's kit for the same 12 tools: list / plan / doctor / install (dry-run unless --yes) / run
    "palette": "tools/nature_palette/scripts/nature_palette.py",  # v1990.8: nature-palette skill (extract / reel / learn)
    "chroma": "tools/chroma_motion/scripts/chroma_identity.py",  # v1990.8: chroma-motion skill: photo -> brand identity board, tokens, motion video
    "hf-blender": "tools/hf_blender/hf_blender.py",  # v1990.4: sandbox Blender pilot, offline plan/package/check; no cloud execution
    "hf": "tools/hf_sandbox/hf.py",  # v10.12 recipe + QC; v1990: free / trend / blender / higgsedit / apps / codefilm
    "pack": "tools/packs/packs.py",  # v1990: reviewed-by-hash registry of uploaded skill packs, static scan, safe unpack outside the skill
    "framecheck": "tools/framecheck/framecheck.py",  # v1990: pops, blend cuts, first frames after every cut, freezes, numbered sheets
    "critic": "tools/critic/critic.py",  # v1990: blind-critic packet, eight-axis scorecard, version ledger
    "tags": "tools/caption/tags.py",  # v10.11: caption + hashtags as a copyable code block
    "stock": "tools/stock/stock.py",  # free footage + photos with licence sidecars (free_footage.py, free_photos.py)
    "hunter": "tools/media_hunter/mh.py",  # Media Hunter: live stock client + offline multi-type links
    "fetch": "tools/fetch/fetch.py",
    "tiktok-post": "tools/fetch/tiktok_post.py",  # photo posts: yt-dlp does not support them
    "styles": "tools/styles/build_style.py",
    "care": "tools/care/care.py",             # local phone compatibility check, job status and resources
    "layout": "tools/care/layout.py",         # Arabic keyboard layout correction
    "hunter615": "tools/media_hunter_615/mh.py",  # actual 615-site offline index; live source search requires network
    "fusion": "tools/repo_fusion/scripts/repo_fusion.py",  # offline capability source references
    "repo": "tools/repo_link/repo_link.py",  # repo metadata and approval-gated actions
    "musicmap": "tools/repo_fusion/scripts/fusion/native_musicmap.py",
    "opuscar": "tools/repo_fusion/scripts/fusion/native_opuscar.py",
    "shotcraft": "tools/repo_fusion/scripts/fusion/native_shotcraft.py",
    "pixelfx": "tools/repo_fusion/scripts/fusion/native_pixelfx.py",
    "reads": "tools/repo_fusion/scripts/fusion/native_cab.py",
    "blender-audit": "tools/repo_fusion/scripts/fusion/native_blender_audit.py",
    "three-frames": "tools/repo_fusion/scripts/fusion/native_three.py",
    "physics-bake": "tools/repo_fusion/scripts/fusion/native_rapier_bake.py",
    "promptlib": "tools/repo_fusion/scripts/fusion/native_promptlib.py",
    "sp": "tools/superpowers/sp.py",        # v10.13: live KOSIF Superpowers hub (find/doctor/tool/qc/run)
    "atlas": "tools/atlas/atlas.py",
    "github-atlas": "tools/github_atlas/atlas.py",  # v1990.1: 1000 GitHub repositories; offline discovery only        # v10.13: curated Atlas skills bundled in skills/atlas-picks
    "re": "tools/re/re.py",                 # v10.14: reverse-engineering front door (plan/audit/investigate/run)
    "brain": "tools/brain/brain.py",        # v10.14: one briefing from every source + thinking protocol + lessons
    "genius": "tools/genius/bridge.py",      # v10.17: Dragon Genius — delivery gate + transcript QA (doctor/gate/qa)
    "omni": "tools/omni/bridge.py",          # v10.17: Omni Analyst — triage any target (doctor/classify/probe/plan/report/hyp/bayes)
    "reftiming": "tools/onscreen/ref_timing.py",  # v10.16.1: on-screen lyric timing measured from a reference video
    "onscreen": "tools/onscreen/onscreen.py",  # v10.15: no description on screen (his words / confirmed lyrics / credit only)
    "fonts": "tools/fonts/fonts.py",        # v10.15: OFL fonts not in the ZIP: doctor | fetch [--from DIR] [--download] --yes
    "paint": "tools/paint/bridge.py",          # v10.16: Paint Studio (Win11 Paint as code): doctor | ops | new | draw | export | preview | ai ...
    "grab": "tools/grab/bridge.py",            # v10.16: video-grabber: plan | doctor | ghost | proxies | URL... (proxy rotation, stream sniffer)
    "toon": "tools/toon/toon.py",              # v10.16: cartoon/anime look: doctor | styles | image | video [--seconds 3] | setup (dry run)
    "links": "tools/links/links.py",           # v10.16: registry of the links used with Black Dragon: stats | find | list | route | add (offline)
    "psd": "tools/psd_studio/psd.py",                  # v10.8.1: layered PSD without Photoshop: inspect | export | build | cutout | doctor
    "lyric-ass": "tools/lyric_remake/lyric_ass.py",     # v10.8.1: timed Arabic lyric/caption spec -> .ass (bidi-safe colour words)
    "song-map": "tools/cinema_extras/song_map.py",      # cinema: energy map + beats per song (pick a section, cut on the beat)
    "sheets": "tools/cinema_extras/sheets.py",          # cinema: timestamped contact sheets (BDC_REFS / BDC_WORK env)
    "skill-atlas": "tools/cinema_extras/skill_atlas.py",
    "machine": "tools/machine/machine.py",  # v1990.3: start door, laptop-or-cloud question, machine map, RE paths, whole-PC control, desktop-app link  # cinema: rebuild references/SKILL_ATLAS.md [--out PATH]
    "package": "tools/package/package.py",      # v10.18 (merged in v1990.10): stamp + checksum + zip the skill: [--set-version X] [--out DIR] [--no-zip] [--check]
    "powers": "tools/powers/powers.py",          # v1990.10: every power and connection (MCP, engines, cloud, agents, RE, PC control, skills): route | map | show | doctor | first
}
ENGINE_ALIASES = {"chrome": "chrome", "sahab": "cloud_browser", "cloud-browser": "cloud_browser", "kosif": "kosif"}  # v10.6/10.7: `<alias> …` = `run <engine> …`
CARE_ALIASES = {"play-check": "play", "status": "status", "last": "last", "resources": "resources"}
TRACKABLE = {"film", "run", "words", "mux", "patch-black", "align", "beats", "mix", "cut", "v10", "lyrics-sheet"}
MEDIA_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".flac",
             ".png", ".jpg", ".jpeg", ".webp", ".gif", ".srt", ".vtt", ".ass", ".json", ".xlsx"}
PIP_CORE = ["librosa", "soundfile", "pyloudnorm", "opencv-python-headless", "arabic_reshaper", "python-bidi",
            "scenedetect", "auto-editor", "yt-dlp", "pytest"]
PIP_FULL = ["faster-whisper"]          # word timings
PIP_GPU = ["whisperx", "demucs"]       # only where a GPU (or patience) exists
WINGET = {"ffmpeg": "Gyan.FFmpeg", "node": "OpenJS.NodeJS.LTS", "blender": "BlenderFoundation.Blender",
          "yt-dlp": "yt-dlp.yt-dlp", "magick": "ImageMagick.ImageMagick", "tesseract": "UB-Mannheim.TesseractOCR"}


USAGE = {
    "where": "usage: dragon.py where\n  prints JSON: mode (cloud|pc), dragon_home, engine_version vs bundled_version, programs, "
             "old repos, outputs folder. Changes nothing.",
    "setup": "usage: dragon.py setup [--full] [--gpu] [--yes]\n  DRY RUN unless --yes is explicitly given; never installs system packages automatically.",
}


def is_cloud_box():
    return Path("/mnt/user-data").exists() or os.environ.get("CLAUDE_CODE_REMOTE") == "true"


def detect():
    forced = os.environ.get("DRAGON_MODE")
    home = os.environ.get("DRAGON_HOME")
    if home and (Path(home) / "dragon" / "cli.py").exists():
        return (forced or ("cloud" if is_cloud_box() else "pc")), Path(home)
    if forced != "cloud":
        for c in PC_CANDIDATES:
            if (c / "dragon" / "cli.py").exists():
                return "pc", c
    if forced == "pc" or (not is_cloud_box() and platform.system() in ("Windows", "Darwin")):
        return "pc", HOME / ".black-dragon" / "app"      # PC without the repo: use the bundled copy
    return "cloud", Path("/tmp/dragon")


STAMP = ".bundle_stamp"                                     # written into every copy this launcher makes of app/
BUNDLED_HOMES = (Path("/tmp/dragon"), HOME / ".black-dragon" / "app")
SKIP = ("__pycache__", ".pytest_cache")


def bundle_stamp(app=None):
    """Code/content fingerprint. No mtime-only false negatives, no binary/font scans."""
    import hashlib
    app = Path(app or APP)
    h = hashlib.sha256()
    for p in sorted(app.rglob("*")):
        rel = p.relative_to(app)
        if not p.is_file() or set(SKIP) & set(rel.parts):
            continue
        if p.suffix.lower() in (".py", ".js", ".cjs", ".html", ".css", ".md", ".json", ".txt"):
            h.update(rel.as_posix().encode("utf-8"))
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()[:16]



def _real(p):
    """The folder's real path, case-folded on Windows: what a stamp records so it only counts in that folder."""
    return os.path.normcase(os.path.realpath(str(p)))


def _catalog_sig(app=None):
    """Content-sensitive catalog identity: same size/mtime must not hide a new tool entry."""
    import hashlib
    c = Path(app or APP) / "data" / "catalog.sqlite"
    try:
        digest = hashlib.sha256()
        with c.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()[:24]
    except OSError:
        return ""


def _read_stamp(home):
    """(content hash, copy path, catalog identity): supports v1.2 single-line stamp and v1.3 legacy multiline."""
    try:
        lines = (Path(home) / STAMP).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if not lines:
        return None
    if len(lines) > 1:
        return (lines + ["", "", ""])[:3]
    try:
        metadata = (Path(home) / (STAMP + ".meta")).read_text(encoding="utf-8").splitlines()
    except OSError:
        metadata = []
    return [lines[0]] + (metadata + ["", ""])[:2]


def _ours(home):
    """A copy this launcher made: /tmp/dragon or ~/.black-dragon/app, or a folder whose stamp names that very folder.
    A stamp copied along into the owner's repo (it names another folder, or is the one-line v1.2-beta form) does not
    count: the owner's files are never overwritten."""
    if home in BUNDLED_HOMES:
        return True
    st = _read_stamp(home)
    return bool(st and st[1] and st[1] == _real(home))


def _owner_writable(root):
    """Add the owner's write bit to every folder and file under root. A read-only skill folder (claude.ai mounts it so)
    gives 0555 folders through copytree's copystat: the stamp and every later refresh would fail. No-op on Windows."""
    for dp, _dns, fns in os.walk(root):
        for p in [dp] + [os.path.join(dp, f) for f in fns]:
            try:
                m = os.stat(p).st_mode
                if not m & stat.S_IWUSR:
                    os.chmod(p, m | stat.S_IWUSR)
            except OSError:
                pass


def _copier(keep_catalog):
    def copy(src, dst):
        """copy2, except a catalog rebuilt inside the copy is kept while the bundled catalog is unchanged since then."""
        d = Path(dst)
        if keep_catalog and d.name == "catalog.sqlite" and d.exists() and d.stat().st_mtime > Path(src).stat().st_mtime:
            return dst
        if d.exists() and not os.access(d, os.W_OK):  # read-only file copied from a read-only skill folder
            os.chmod(d, stat.S_IREAD | stat.S_IWRITE)
        return shutil.copy2(src, dst)
    return copy


_copy_keep_catalog = _copier(True)  # v1.2 name, kept for callers


def ensure_home(mode, home):
    """The engine folder to run. A repo the owner keeps is used as it is. A bundled copy (made by this launcher) is
    made again when the skill's app/ changed since the copy: an old copy would hide the new commands and fixes."""
    has_engine = (home / "dragon" / "cli.py").exists()
    if has_engine and not _ours(home):
        return home
    stamp, old = bundle_stamp(), _read_stamp(home)
    if has_engine and old and old[0] == stamp:
        return home
    keep = bool(old) and old[2] == _catalog_sig()      # bundled catalog changed: take the new one
    try:
        home.mkdir(parents=True, exist_ok=True)
        _owner_writable(home)                           # repairs a copy left at 0555 by an earlier run
        shutil.copytree(APP, home, dirs_exist_ok=True, copy_function=_copier(keep),
                        ignore=shutil.ignore_patterns(*SKIP))
        _owner_writable(home)
        (home / STAMP).write_text(stamp, encoding="utf-8")
        (home / (STAMP + ".meta")).write_text(f"{_real(home)}\n{_catalog_sig()}\n", encoding="utf-8")
    except OSError as e:
        if not has_engine:
            raise
        print(f"note: could not refresh the engine copy in {home} ({type(e).__name__}: {str(e)[:200]}); "
              f"to get a fresh copy run `chmod -R u+w` on that folder, delete it, and run the command again "
              f"(or set DRAGON_HOME={APP})", file=sys.stderr)
    return home


def engine_version(home):
    """dragon.__version__ of an engine folder, read from the file (no import), or None."""
    import re
    try:
        m = re.search(r'__version__\s*=\s*"([^"]+)"', (Path(home) / "dragon" / "__init__.py").read_text(encoding="utf-8"))
    except OSError:
        return None
    return m.group(1) if m else None


def older_repo_note(home):
    """One line when the owner's repo (used instead of the bundled copy) is an older dragon than this skill, else ''."""
    import re
    if _ours(home):
        return ""
    have, new = engine_version(home), engine_version(APP)
    key = lambda v: tuple(int(x) for x in re.findall(r"\d+", v or "0")[:3])
    if not new or key(have) >= key(new):
        return ""
    return (f"note: {home} has dragon {have or 'without a version'}; this skill bundles {new} (new commands such as mux, "
            f"patch-black, align, lyrics-sheet and the stricter verify). Set DRAGON_HOME={APP} to use the skill's engine "
            f"(copying it over your repo is an install: only with your yes and a backup first).")


GATE_CMDS = {"verify", "mux", "patch-black", "align", "lyrics-sheet", "film", "run", "v10", "probe-tools", "ecosystem", "plan"}


def gate_home(cmd, mode, home):
    """v1.3: an older owner repo never runs a delivery-gate command (its verify passed MP3-in-MP4 and black films, and
    it lacks mux/patch-black/align): those run on the skill's own engine, with one stderr line saying so."""
    if cmd not in GATE_CMDS or not older_repo_note(home):
        return home
    bundled = HOME / ".black-dragon" / "app" if mode == "pc" else Path("/tmp/dragon")
    try:
        new = ensure_home(mode, bundled)
    except OSError:
        new = APP
    print(f"note: {home} has an older dragon ({engine_version(home) or 'no version'}); `{cmd}` runs on the skill's "
          f"engine {engine_version(APP)} instead ({new}). To make it permanent: set DRAGON_HOME={APP}", file=sys.stderr)
    return new


def surface():
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        return "claude-code-cloud"
    if Path("/mnt/user-data").exists():
        return "claude.ai"
    return "pc" if platform.system() in ("Windows", "Darwin") else "local"


def outputs_line():
    """Where the finished file goes on this surface: claude.ai -> /mnt/user-data/outputs; a Claude Code cloud session
    -> ./out, delivered with SendUserFile and a private link (even when /mnt/user-data exists there)."""
    if surface() == "claude-code-cloud":
        return f"{Path.cwd() / 'out'} → deliver with SendUserFile + private link"
    if Path("/mnt/user-data").exists():
        return "/mnt/user-data/outputs"
    return str(Path.cwd())


def find_program(name, home=None):
    """Use the same extended program lookup as doctor, including Windows paths."""
    p = shutil.which(name)
    if p or name == "nvidia-smi":
        return p
    sys.path.insert(0, str(home or APP))
    try:
        from dragon.doctor import find_program as fp
        return fp(name)
    except (ImportError, OSError, ValueError):
        return None
    finally:
        sys.path.pop(0)



def where():
    mode, home = detect()
    info = {
        "mode": mode, "os": platform.system(), "dragon_home": str(home),
        "uses_bundled_engine": _ours(home),   # a launcher copy (/tmp/dragon, ~/.black-dragon/app), not live code
        "engine_kind": ("bundled copy" if _ours(home) else "skill app (live code)" if _real(home) == _real(APP)
                        else "owner repo"),
        "programs": {p: bool(find_program(p, home if (home / "dragon").exists() else None)) for p in PROGRAMS},
        "old_repos": {k: v.exists() for k, v in OLD_REPOS.items()},
        "outputs": outputs_line(),
        "surface": surface(),
        "engine_version": engine_version(home), "bundled_version": engine_version(APP),
    }
    note = older_repo_note(home)
    if note:
        info["note"] = note
    elif info["engine_version"] is None and _ours(home):
        info["note"] = (f"no engine copy in {home} yet (normal on a fresh machine): the first other command, "
                        f"e.g. `doctor`, makes it")
    info["gpu"] = info["programs"]["nvidia-smi"]
    info["route"] = (
        "PC: full power. Use local repos (kosif-tool video_protocol, dragon-montage stations), Blender, yt-dlp, GPU models when present."
        if mode == "pc" else
        "Cloud: bundled engine only. No Blender/GPU; YouTube/TikTok downloads are often blocked, ask the user to upload the file."
    )
    return info


def _note(home):
    note = older_repo_note(home)
    if note:
        print(note, file=sys.stderr)


def run(args, home=None):
    env = dict(os.environ)
    ff = SKILL / "tools" / "stock" / "free_footage.py"     # the montage stock station's client (ROADMAP T5)
    if ff.is_file() and not os.environ.get("DRAGON_FREE_FOOTAGE"):
        env["DRAGON_FREE_FOOTAGE"] = str(ff)
    if home:
        env["PYTHONPATH"] = str(home) + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("DRAGON_SKILL", str(SKILL))   # v10.15: an engine copy finds the skill's tools/ (probe-tools)
    return subprocess.call([sys.executable] + args, env=env)


# Guardian: persistent LOCAL receipts, not asynchronous service or all-jobs monitor.
def _state_dir():
    p = Path(os.environ.get("DRAGON_STATE") or (HOME / ".black-dragon"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _jobs_append(record):
    try:
        with (_state_dir() / "jobs.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"warning: job log unavailable: {exc}", file=sys.stderr)


def _job_start(argv):
    import time, uuid
    j = {"id": uuid.uuid4().hex, "pid": os.getpid(), "argv": list(argv),
         "cwd": str(Path.cwd()), "start": time.time()}
    _jobs_append(j)
    return j


def _job_outputs(job):
    """Only paths supplied by this command, plus recently written files in cwd/out; no global filesystem scan."""
    start, cwd, seen = job["start"] - 1, Path(job["cwd"]), []
    for arg in job["argv"][1:]:
        if not arg or arg.startswith("-"):
            continue
        p = Path(arg)
        p = p if p.is_absolute() else cwd / p
        try:
            if p.is_file() and p.stat().st_mtime >= start and p.suffix.lower() in MEDIA_EXT:
                seen.append(str(p.resolve()))
        except (OSError, ValueError):
            continue
    outdir = cwd / "out"
    if outdir.is_dir():
        try:
            for p in outdir.rglob("*"):
                if len(seen) >= 50:
                    break
                if p.is_file() and p.suffix.lower() in MEDIA_EXT and p.stat().st_mtime >= start:
                    resolved = str(p.resolve())
                    if resolved not in seen:
                        seen.append(resolved)
        except OSError:
            pass
    return seen[:50]


def _job_end(job, code):
    import time
    files = _job_outputs(job)
    _jobs_append({"id": job["id"], "end": time.time(), "exit": int(code), "outputs": files})
    if files:
        print("Files created by this command (also via `last`):", file=sys.stderr)
        for path in files[:6]:
            print("  " + path, file=sys.stderr)


def _memory_note():
    """Warn without installing software, killing tasks, or claiming OS-wide tracking."""
    try:
        from importlib import util
        spec = util.spec_from_file_location("bd_guardian_care", SKILL / "tools/care/care.py")
        mod = util.module_from_spec(spec); spec.loader.exec_module(mod)
        r = mod.resources()
        os.environ.setdefault("DRAGON_MAX_WORKERS", str(r["workers"]))
        if r["level"] != "ok":
            print(f"RAM available {r['ram_free_gb']} GB: {r['advice']}", file=sys.stderr)
    except Exception as exc:
        print(f"resource preflight unavailable: {type(exc).__name__}", file=sys.stderr)

def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return 0
    cmd = argv[0]
    if cmd in ENGINE_ALIASES:                    # v10.6: `chrome …` / `sahab …` / `kosif …` = `run <engine> …`
        argv = ["run", ENGINE_ALIASES[cmd]] + argv[1:]
        cmd = "run"
    asks_help = any(x in ("-h", "--help") for x in argv[1:2])
    if cmd == "start":                           # v1990.3: first command when the package reaches Claude (asks: laptop or cloud?)
        return run([str(SKILL / TOOLS["machine"]), "start"] + argv[1:])
    if cmd in ("where", "setup") and asks_help:
        print(USAGE[cmd]); return 0
    if cmd == "where":
        print(json.dumps(where(), ensure_ascii=False, indent=1)); return 0
    if cmd == "setup":
        allowed = {"--full", "--gpu", "--yes", "--dry-run", "--help", "-h"}
        invalid = set(argv[1:]) - allowed
        if invalid:
            print("invalid setup arguments: " + ", ".join(sorted(invalid)), file=sys.stderr); return 2
        if "--help" in argv or "-h" in argv:
            print("setup: dry-run by default. Add --full for speech tools or --gpu for heavy models. "
                  "Only `setup --yes` installs dependencies; system packages are suggested, not installed.")
            return 0
        mode, home = detect()
        pkgs = PIP_CORE + (PIP_FULL if "--full" in argv else []) + (PIP_GPU if "--gpu" in argv else [])
        print("setup plan: Python packages:", ", ".join(pkgs))
        info = where()
        if mode == "pc" and platform.system() == "Windows":
            for p in PROGRAMS:
                if not info["programs"][p] and p in WINGET:
                    print(f"  OPTIONAL system install: winget install -e --id {WINGET[p]}")
        if "--yes" not in argv or "--dry-run" in argv:
            print("dry-run only: no installation. Run `setup --yes` after explicit user approval.")
            return 0
        home = ensure_home(mode, home)
        _note(home)
        status = subprocess.call([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check"] + pkgs)
        if status != 0:
            print(f"pip install failed (exit {status})", file=sys.stderr)
            return status
        run(["-m", "dragon", "doctor"], home=home)
        print(f"mode={mode}  DRAGON_HOME={home}")
        return 0
    if cmd == "tool":
        if len(argv) < 2 or argv[1] not in TOOLS and argv[1] != "cartoon":
            print("tools:", ", ".join(list(TOOLS) + ["cartoon"]), " (tool <name> --help for each)")
            return 0 if argv[1:2] and argv[1] in ("-h", "--help") else 2
        if argv[1] == "cartoon":
            print(f"cartoon kit: {SKILL / 'tools' / 'cartoon'}  ->  bash tools/setup.sh <project dir>  (see references/skills/cartoon-short.md)")
            return 0
        if any(x in ("-h", "--help") for x in argv[2:]) or argv[1] in ("layout", "fusion", "repo"):
            return run([str(SKILL / TOOLS[argv[1]])] + argv[2:])
        job = _job_start(argv)
        code = run([str(SKILL / TOOLS[argv[1]])] + argv[2:])
        _job_end(job, code)
        return code
    if cmd in CARE_ALIASES:
        return run([str(SKILL / TOOLS["care"]), CARE_ALIASES[cmd]] + argv[1:])
    mode, home = detect(); home = ensure_home(mode, home)
    gated = gate_home(cmd, mode, home)
    if gated == home:
        _note(home)
    job = None
    if cmd in TRACKABLE and not asks_help:
        _memory_note()
        job = _job_start(argv)
    code = run(["-m", "dragon"] + argv, home=gated)
    if job:
        _job_end(job, code)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
