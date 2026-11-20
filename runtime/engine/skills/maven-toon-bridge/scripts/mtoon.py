#!/usr/bin/env python3
"""Golden Dragon v3.5.5: maven-toon-bridge -- drive the owner's PRIVATE copy of Maven Toon (by @maven.iqq) and add the
Golden Dragon layer on top of it: an Egyptian script check, the owner's mandatory credit, and the export gate.

    rd.py mtoon install maven-toon-skill.zip     unpack the owner's zip OUTSIDE the repo (default ~/dragon-tools/maven-toon)
    rd.py mtoon where | doctor                   where the copy is, and its own `toon.py doctor`
    rd.py mtoon run <toon.py args...>            pass-through: plan, stills, render, join, check, words, silent, library ...
    rd.py mtoon script-eg PROJECT --seconds 15   Egyptian script check (hook, turn, payoff, length, one register)
    rd.py mtoon credit PROJECT                   final.mp4 -> final_credit.mp4 (© Mahmoud Elkosif + end card, libass, exact)
    rd.py mtoon gate VIDEO                       owner's export standard: 1080x1920, 30 fps, H.264, audio, faststart
    rd.py mtoon selftest                         offline checks (no Maven copy needed)

v3.5.6: the owner (who states he is Maven, the tool's author) granted full integration on 2026-11-20, so Maven Toon now
lives in the repo at engine/skills/maven-toon (fonts excluded by the repo rule: `rd.py mtoon fonts` fetches the two OFL
fonts from google/fonts). `install` still updates from a newer zip, into the repo copy (--dest) or ~/dragon-tools.

    rd.py mtoon fonts                            fetch Lalezar + Poppins ExtraBold (OFL) into the skill's engine/fonts
    rd.py mtoon render PROJECT [--budget 200]     render with every CPU core (Maven's default is 2), repeat until DONE
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

SCHEMA = "golden-dragon.mtoon.v1"
HERE = Path(__file__).resolve()
REPO = HERE.parents[4]                                    # .../black-dragon-skill
HOME = Path(os.environ.get("MTOON_HOME", Path.home() / "dragon-tools" / "maven-toon"))
VENDORED = REPO / "engine" / "skills" / "maven-toon"
FONTS = {"Lalezar-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/lalezar/Lalezar-Regular.ttf",
         "Poppins-ExtraBold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-ExtraBold.ttf"}
MAX_UNPACKED = 200 * 1024 * 1024                          # the real zip unpacks to ~3 MB; anything near this is wrong

CREDIT = "© Mahmoud Elkosif"
END_1 = "مونتاج وإخراج Mahmoud Elkosif"
END_2 = "تابعني على فيسبوك"

# ---------------------------------------------------------------- helpers

def out(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, indent=1))
    return code


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def skill_dir() -> Path | None:
    if os.environ.get("MTOON_HOME"):                       # an explicit copy wins (e.g. a newer zip being tried)
        cands = (HOME, *HOME.glob("*"), VENDORED)
    else:
        cands = (VENDORED, HOME, *HOME.glob("*"))
    for c in cands:
        if (c / "toon.py").is_file() and (c / "SKILL.md").is_file():
            return c
    return None


def python_for(sd: Path) -> str:
    """MTOON_PY, else the copy's own venv if the owner made one there, else this interpreter."""
    if os.environ.get("MTOON_PY"):
        return os.environ["MTOON_PY"]
    for v in (sd / ".venv" / "Scripts" / "python.exe", sd / ".venv" / "bin" / "python"):
        if v.is_file():
            return str(v)
    return sys.executable


# ---------------------------------------------------------------- install (safe unzip, outside the repo)

def safe_members(zf: zipfile.ZipFile):
    total, bad, names = 0, [], []
    for i in zf.infolist():
        n = i.filename.replace("\\", "/")
        mode = (i.external_attr >> 16) & 0o170000
        if n.startswith("/") or re.match(r"^[A-Za-z]:", n) or ".." in Path(n).parts:
            bad.append(f"path escapes the folder: {n}")
        elif mode == 0o120000:
            bad.append(f"symlink refused: {n}")
        total += i.file_size
        names.append(n)
    if total > MAX_UNPACKED:
        bad.append(f"unpacked size {total} > {MAX_UNPACKED}")
    return bad, names, total


def cmd_install(a):
    z = Path(a.zip).expanduser()
    if not z.is_file():
        return out({"ok": False, "error": f"zip not found: {z}"}, 2)
    dest = Path(a.dest).expanduser() if a.dest else HOME
    if inside(dest, REPO) and dest.resolve() != VENDORED.resolve():
        return out({"ok": False, "error": f"inside the repo only the vendored folder is allowed: {VENDORED}"}, 2)
    with zipfile.ZipFile(z) as zf:
        bad, names, total = safe_members(zf)
        if bad:
            return out({"ok": False, "error": "unsafe zip", "problems": bad[:10]}, 2)
        if not any(n.endswith("toon.py") for n in names) or not any(n.endswith("SKILL.md") for n in names):
            return out({"ok": False, "error": "this zip has no toon.py + SKILL.md: not a Maven Toon package"}, 2)
        if dest.exists() and any(dest.iterdir()):
            if not a.replace:
                return out({"ok": False, "error": f"{dest} is not empty; pass --replace (the old copy is zipped next to it first)"}, 2)
            bak = shutil.make_archive(str(dest) + ".bak", "zip", dest)
            shutil.rmtree(dest)
        else:
            bak = None
        dest.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="mtoon-") as tmp:      # unpack into an empty new folder first
            zf.extractall(tmp)
            roots = [p for p in Path(tmp).rglob("toon.py") if (p.parent / "SKILL.md").is_file()]
            src = roots[0].parent
            for p in src.iterdir():
                shutil.move(str(p), str(dest / p.name))
    sd = skill_dir()
    ver = ""
    rd = (sd / "README.md") if sd else None
    if rd and rd.is_file():
        m = re.search(r"\*\*Version ([0-9.]+)\*\*", rd.read_text(encoding="utf-8", errors="replace"))
        ver = m.group(1) if m else ""
    rec = {"schema": SCHEMA, "zip": z.name, "zip_sha256": sha256(z), "files": len(names), "bytes": total,
           "version": ver, "installed_at": str(dest), "backup": bak,
           "rights": "Maven parts: rights/MAVEN-RIGHTS.txt; repo integration granted by the owner (Maven) 2026-11-20"}
    (dest / ".golden-dragon-install.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    rec["ok"] = True
    rec["next"] = "rd.py mtoon doctor  (then: pip install -r requirements.txt, only after the owner says yes)"
    return out(rec)


# ---------------------------------------------------------------- where / doctor / run

def cmd_where(a):
    sd = skill_dir()
    rec = {}
    if sd and (HOME / ".golden-dragon-install.json").is_file():
        rec = json.loads((HOME / ".golden-dragon-install.json").read_text(encoding="utf-8"))
    return out({"ok": bool(sd), "home": str(HOME), "skill": str(sd) if sd else None, "install": rec,
                "hint": None if sd else "rd.py mtoon install <maven-toon zip>"}, 0 if sd else 1)


def cmd_run(args):
    sd = skill_dir()
    if not sd:
        return out({"ok": False, "error": "no Maven Toon copy installed", "fix": "rd.py mtoon install <zip>"}, 1)
    for x in args:                                          # Maven's own rule: projects live OUTSIDE the skill folder
        p = Path(x).expanduser()
        if p.exists() and p.is_dir() and inside(p, sd) and p.resolve() != sd.resolve() and "examples" not in p.parts:
            return out({"ok": False, "error": f"project {p} is inside the skill folder; copy it outside first"}, 2)
    return subprocess.call([python_for(sd), "toon.py", *args], cwd=str(sd))


def cmd_fonts(a):
    sd = skill_dir()
    if not sd:
        return out({"ok": False, "error": "no Maven Toon copy"}, 1)
    fd = sd / "engine" / "fonts"
    fd.mkdir(parents=True, exist_ok=True)
    import urllib.request
    got = {}
    for name, url in FONTS.items():
        f = fd / name
        if f.is_file() and f.stat().st_size > 10000 and not a.force:
            got[name] = "present"
            continue
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "golden-dragon-fonts"}), timeout=60) as r:
            data = r.read()
        if not data.startswith((b"\x00\x01\x00\x00", b"OTTO", b"true")):
            return out({"ok": False, "error": f"{name}: not a font file"}, 1)
        f.write_bytes(data)
        got[name] = f"downloaded {len(data)} B sha256 {hashlib.sha256(data).hexdigest()[:16]}"
    return out({"ok": True, "dir": str(fd), "fonts": got, "licence": "SIL OFL 1.1 (OFL-*.txt next to them)"})


def cmd_render(args):
    """Maven renders on 2 workers by default; the dragon uses every core it has (leave one free on the laptop)."""
    if "--workers" not in args:
        n = os.cpu_count() or 2
        args = [*args, "--workers", str(max(1, n - 1) if n > 4 else n)]
    return cmd_run(["render", *args])


# ---------------------------------------------------------------- Egyptian script check (Golden Dragon's own rules)

EG_RATE = 2.1                       # spoken Arabic words per second (estimate; measure on the real voice with words.json)
BAD_OPEN = ("النهارده هحكي", "النهاردة هحكي", "في الفيديو ده", "فى الفيديو ده", "استنى للآخر", "استنوا للآخر",
            "أهلا", "اهلا", "السلام عليكم", "مرحبا", "هل تعلم", "تعرفوا ايه", "تعرفوا إيه")
TURN = ("تعرف ليه", "تعرفي ليه", "عارف ليه", "والسبب", "والسر", "أصل", "اصل ", "بص يا", "بصّ", "الحكاية إن", "الحكاية ان")
ESCAL = ("بس", "فـ", "وبعدين", "وفجأة", "وفي يوم", "وفى يوم", "ولما")
IRAQI = ("هسه", "شلون", "ماكو", "اكو ", "كلش", "هواية", "لعد", "چ", "گ", "باچر")
FUSHA = ("لكنّ", "لذلك", "إنّ", "حيث إن", "في تلك الليلة")


def words_of(line: str):
    return [w for w in re.split(r"\s+", re.sub(r"[^\w؀-ۿ\s]", " ", line)) if w]


def check_script(text: str, seconds: float, register: str = "eg"):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    res, fails = [], 0

    def r(ok, what, why=""):
        nonlocal fails
        fails += 0 if ok else 1
        res.append({"ok": bool(ok), "check": what, "why": why})

    if not lines:
        r(False, "script has lines", "empty")
        return {"ok": False, "checks": res}
    n = [len(words_of(l)) for l in lines]
    total = sum(n)
    target = seconds * EG_RATE
    r(abs(total - target) <= max(3, 0.12 * target), f"length {total} words for {seconds:g} s (target ~{target:.0f})",
      "cut or add a beat; on a recorded voice the words are fixed")
    r(n[0] <= 7, f"hook ≤ 7 words ({n[0]})")
    r(not lines[0].rstrip().endswith(("؟", "?")), "hook is a flat statement, not a question")
    r(not any(lines[0].startswith(b) for b in BAD_OPEN), "no greeting / 'in this video' / 'wait till the end' opener")
    k = len(lines)
    turns = TURN + (("تدري ليش", "والسرّ") if register == "any" else ())
    lo, hi = int(k * 0.45), max(int(k * 0.92), int(k * 0.45) + 1)
    r(any(any(t in l for t in turns) for l in lines[lo:hi]),
      "a turn line («تعرف ليه؟» / «والسبب؟» / «أصل…») in the second half")
    r(sum(1 for l in lines[1:] if any(l.startswith(e) or f" {e} " in f" {l} " for e in ESCAL)) >= 1,
      "escalation joined by بس / وبعدين / وفجأة / ولما")
    r(n[-1] <= 9, f"payoff ≤ 9 words ({n[-1]})")
    r(max(n) <= 14, f"one picture per sentence: longest line {max(n)} words ≤ 14")
    if register == "eg":
        mixed = [m for m in IRAQI + FUSHA if m in text]
        r(not mixed, "one register (Egyptian) from first word to last", ", ".join(mixed))
    return {"ok": fails == 0, "words": total, "lines": k, "seconds": seconds, "register": register, "checks": res}


def cmd_script_eg(a):
    p = Path(a.project)
    f = p / "script.txt" if p.is_dir() else p
    if not f.is_file():
        return out({"ok": False, "error": f"no script.txt at {f}"}, 2)
    rep = check_script(f.read_text(encoding="utf-8"), a.seconds, a.register)
    for c in rep["checks"]:
        print(("✓ " if c["ok"] else "✗ ") + c["check"] + (f"  ← {c['why']}" if not c["ok"] and c["why"] else ""), file=sys.stderr)
    return out(rep, 0 if rep["ok"] else 1)


# ---------------------------------------------------------------- ffprobe / credit / gate

def probe(v: Path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(v)],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[-300:])
    return json.loads(r.stdout)


def font_dir(explicit: str | None):
    if explicit:
        return Path(explicit)
    sd = skill_dir()
    if sd and (sd / "engine" / "fonts" / "Lalezar-Regular.ttf").is_file():
        return sd / "engine" / "fonts"
    return None


def ass_time(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def write_ass(path: Path, dur: float, w=1080, h=1920, font="Lalezar"):
    end0 = max(0.0, dur - 3.0)
    ev = [f"Dialogue: 0,{ass_time(0)},{ass_time(dur)},Credit,,0,0,0,,{CREDIT}",
          f"Dialogue: 1,{ass_time(end0)},{ass_time(dur)},End,,0,0,0,,{{\\fad(250,0)}}{END_1}\\N{END_2}"]
    path.write_text(
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 2\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {w}\nPlayResY: {h}\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
        "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Credit,{font},34,&H50FFFFFF,&H000000FF,&H64000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,40,40,70,1\n"
        f"Style: End,{font},62,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,4,2,2,60,60,170,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + "\n".join(ev) + "\n",
        encoding="utf-8")


def cmd_credit(a):
    p = Path(a.project)
    src = p / "final.mp4" if p.is_dir() else p
    dst = Path(a.out) if a.out else src.with_name(src.stem + "_credit.mp4")
    if not src.is_file():
        return out({"ok": False, "error": f"no video at {src} (run: rd.py mtoon run join PROJECT)"}, 2)
    if dst.exists() and not a.force:
        return out({"ok": False, "error": f"{dst} exists (never overwritten; --force to replace)"}, 2)
    fd = font_dir(a.fonts)
    if not fd:
        return out({"ok": False, "error": "Lalezar not found: install the Maven copy or pass --fonts DIR"}, 2)
    info = probe(src)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    dur = float(info["format"]["duration"])
    nfr = v.get("nb_frames")
    with tempfile.TemporaryDirectory(prefix="mtoon-credit-") as tmp:
        ass = Path(tmp) / "credit.ass"
        write_ass(ass, dur, int(v["width"]), int(v["height"]))
        esc = lambda s: str(s).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
               "-vf", f"ass='{esc(ass)}':fontsdir='{esc(fd)}'",
               "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-profile:v", "high", "-preset", a.preset, "-crf", "17",
               "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
               "-c:a", "copy", "-movflags", "+faststart"]
        if nfr:
            cmd += ["-frames:v", str(nfr)]
        r = subprocess.run(cmd + [str(dst)], capture_output=True, text=True)
    if r.returncode:
        return out({"ok": False, "error": r.stderr.strip()[-400:]}, 1)
    g = gate(dst, expect_dur=dur)
    return out({"ok": g["ok"], "out": str(dst), "credit": CREDIT, "end_card_from": round(max(0, dur - 3), 2), "gate": g},
               0 if g["ok"] else 1)


def gate(vid: Path, expect_dur: float | None = None, need_audio=True):
    info = probe(vid)
    vs = [s for s in info["streams"] if s["codec_type"] == "video"]
    au = [s for s in info["streams"] if s["codec_type"] == "audio"]
    v = vs[0] if vs else {}
    num, den = (v.get("r_frame_rate", "0/1").split("/") + ["1"])[:2]
    fps = float(num) / float(den or 1)
    dur = float(info["format"].get("duration", 0))
    with open(vid, "rb") as f:
        head = f.read(1 << 16)
    moov, mdat = head.find(b"moov"), head.find(b"mdat")
    checks = [
        ("1080x1920", v.get("width") == 1080 and v.get("height") == 1920, f"{v.get('width')}x{v.get('height')}"),
        ("30 fps", abs(fps - 30) < 0.01, f"{fps:.3f}"),
        ("H.264", v.get("codec_name") == "h264", v.get("codec_name")),
        ("yuv420p", v.get("pix_fmt") == "yuv420p", v.get("pix_fmt")),
        ("audio stream", bool(au) or not need_audio, au[0]["codec_name"] if au else "none"),
        ("faststart (moov before mdat)", moov != -1 and (mdat == -1 or moov < mdat), f"moov@{moov} mdat@{mdat}"),
    ]
    if expect_dur is not None:
        checks.append(("same duration as source", abs(dur - expect_dur) <= 0.05, f"{dur:.3f} vs {expect_dur:.3f}"))
    return {"ok": all(c[1] for c in checks), "file": str(vid), "duration": round(dur, 3),
            "checks": [{"check": c[0], "ok": bool(c[1]), "got": c[2]} for c in checks]}


def cmd_gate(a):
    g = gate(Path(a.video), need_audio=not a.no_audio)
    return out(g, 0 if g["ok"] else 1)


# ---------------------------------------------------------------- selftest (offline, no Maven copy needed)

def cmd_selftest(_a):
    bad = []
    if not (VENDORED / "toon.py").is_file() or not (VENDORED / "rights" / "MAVEN-RIGHTS.txt").is_file():
        bad.append("vendored maven-toon missing (toon.py or rights)")
    if list((VENDORED / "engine" / "fonts").glob("*.ttf")) and not (REPO / ".gitignore").read_text(encoding="utf-8").count("maven-toon/engine/fonts"):
        bad.append("fonts present but not gitignored")
    good = "\n".join(["القهوجي مابياخدش فلوس على أول كوباية.",
                      "في قهوة صغيرة في شبرا، عم حسن بيصب الشاي من الفجر.",
                      "وبعدين ييجي الزبون التاني ويدفع عادي.",
                      "بس الكل كان بيضحك عليه.",
                      "وفجأة القهوة بقت مليانة كل يوم.",
                      "تعرف ليه؟ اللي يشرب أول كوباية ببلاش بيرجع.",
                      "وكوباية واحدة جابت شارع كامل."])
    rep = check_script(good, 23)
    if not rep["ok"]:
        bad.append("good Egyptian script failed: " + "; ".join(c["check"] for c in rep["checks"] if not c["ok"]))
    worse = check_script("هل تعلم ليه الشاي بيتشرب سخن جدا كل يوم؟\nهسه نشوف.", 15)
    if worse["ok"] or sum(not c["ok"] for c in worse["checks"]) < 4:
        bad.append("bad script was not caught")
    with tempfile.TemporaryDirectory(prefix="mtoon-st-") as tmp:
        t = Path(tmp)
        zp = t / "evil.zip"                          # unsafe zips are refused
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr("../escape.txt", "x")
            zf.writestr("maven-toon/toon.py", "")
        with zipfile.ZipFile(zp) as zf:
            if not safe_members(zf)[0]:
                bad.append("path traversal not refused")
        if not inside(REPO / "x" / "y", REPO) or inside(t, REPO):
            bad.append("inside() wrong")
        write_ass(t / "c.ass", 10.0)
        s = (t / "c.ass").read_text(encoding="utf-8")
        if CREDIT not in s or END_1 not in s or "0:00:07.00" not in s:
            bad.append("credit ASS wrong")
        if shutil.which("ffmpeg") and shutil.which("ffprobe"):   # export gate on a tiny synthetic clip
            v = t / "v.mp4"
            r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                                "color=c=0x223344:s=1080x1920:r=30:d=1", "-f", "lavfi", "-i", "sine=f=440:d=1",
                                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(v)],
                               capture_output=True, text=True)
            if r.returncode:
                bad.append("ffmpeg synthetic clip failed")
            elif not gate(v)["ok"]:
                bad.append("gate refused a valid clip: " + json.dumps(gate(v)["checks"], ensure_ascii=False))
    print(json.dumps({"ok": not bad, "problems": bad}, ensure_ascii=False))
    return 1 if bad else 0


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "run":
        return cmd_run(argv[1:])
    if argv and argv[0] == "render":
        return cmd_render(argv[1:])
    ap = argparse.ArgumentParser(prog="rd.py mtoon", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("install"); s.add_argument("zip"); s.add_argument("--dest"); s.add_argument("--replace", action="store_true")
    sub.add_parser("where")
    sub.add_parser("doctor")
    sub.add_parser("run")
    sub.add_parser("render")
    s = sub.add_parser("fonts"); s.add_argument("--force", action="store_true")
    s = sub.add_parser("script-eg"); s.add_argument("project"); s.add_argument("--seconds", type=float, default=15)
    s.add_argument("--register", choices=["eg", "any"], default="eg")
    s = sub.add_parser("credit"); s.add_argument("project"); s.add_argument("--out"); s.add_argument("--fonts")
    s.add_argument("--force", action="store_true"); s.add_argument("--preset", default="slow")
    s = sub.add_parser("gate"); s.add_argument("video"); s.add_argument("--no-audio", action="store_true")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "doctor":
        return cmd_run(["doctor"])
    return {"install": cmd_install, "fonts": cmd_fonts, "where": cmd_where, "script-eg": cmd_script_eg, "credit": cmd_credit,
            "gate": cmd_gate, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
