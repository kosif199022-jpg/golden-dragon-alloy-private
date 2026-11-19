#!/usr/bin/env python3
"""fonts — get the free (SIL OFL 1.1) fonts the engines read, without bundling them in the ZIP.

    python scripts/dragon.py tool fonts doctor [--json]                    # present / missing per folder (exit 1 if missing)
    python scripts/dragon.py tool fonts fetch                              # PLAN only: what would be copied from local folders
    python scripts/dragon.py tool fonts fetch --yes                        # copy matching OFL fonts from local folders
    python scripts/dragon.py tool fonts fetch --download --yes             # + download what is still missing from google/fonts
    python scripts/dragon.py tool fonts fetch --from D:\\fonts --yes        # extra local folder(s) to search first
    python scripts/dragon.py tool fonts list                               # the manifest (file, family, folder, licence, url)

Why: font binaries are not shipped (references/FONTS_REQUIRED.md). Every font here is OFL 1.1; the tool only ever
places files named in MANIFEST below, into the folders the engines already read, so no engine code changes.
Rules: never overwrites an existing font file; each placed font opens with PIL ImageFont (and its family name matches)
or it is rejected; its licence text goes next to it when the folder has none for that family; SHA-256, source
(path or URL) and licence go into fonts.lock.json in that folder. Downloads only from github.com/google/fonts (ofl/).
Exit: 0 ok · 1 required fonts still missing · 2 usage / input error.
"""
import argparse, datetime, hashlib, json, os, shutil, sys, tempfile, urllib.parse, urllib.request
from pathlib import Path

PKG = Path(__file__).resolve().parents[2]
HOME = Path.home()
LOCK = "fonts.lock.json"
LOCK_SCHEMA = "black-dragon.fonts.lock.v1"
GF_RAW = "https://github.com/google/fonts/raw/main/"
FONT_EXT = (".ttf", ".otf", ".woff2", ".woff")
PRUNE = {"node_modules", ".git", "__pycache__", ".pytest_cache", ".venv", "venv", "site-packages"}

CINEMA, TALK, WEB = "app/engines/cinema/assets/fonts", "app/engines/talking_head/data/fonts", "app/engines/web_film/assets/fonts"
STYLES, CARTOON, MATRICES = "tools/styles/fonts", "tools/cartoon/fonts", "app/engines/matrices/assets"

# (folder relative to PKG, file, family as the font names itself, google/fonts path or None, who reads it)
# All SIL OFL 1.1. gf=None: no upstream file with this exact name/instance (static cut of a variable family, or the
# owner's own OFL derivative) -> local copy only.
MANIFEST = [
    (CINEMA, "ArefRuqaa-Bold.ttf", "Aref Ruqaa", "ofl/arefruqaa/ArefRuqaa-Bold.ttf", "cinema engine.js, image_studio ruqaa"),
    (CINEMA, "Cairo-900.ttf", "Cairo", None, "cinema, image_studio cairo"),
    (CINEMA, "Cairo-700.ttf", "Cairo", None, "cinema, image_studio cairo-bold"),
    (CINEMA, "Cairo-400.ttf", "Cairo", None, "image_studio cairo-regular"),
    (CINEMA, "Amiri-Bold.ttf", "Amiri", "ofl/amiri/Amiri-Bold.ttf", "cinema, image_studio amiri"),
    (CINEMA, "ElMessiri-700.ttf", "El Messiri", None, "cinema, image_studio messiri"),
    (CINEMA, "Tajawal-Black.ttf", "Tajawal", "ofl/tajawal/Tajawal-Black.ttf", "cinema, image_studio tajawal"),
    (CINEMA, "ReemKufi-700.ttf", "Reem Kufi", None, "cinema, image_studio kufi"),
    (CINEMA, "InstrumentSerif-Italic.ttf", "Instrument Serif", "ofl/instrumentserif/InstrumentSerif-Italic.ttf",
     "cinema, image_studio serif"),
    (TALK, "Anton-Regular.ttf", "Anton", "ofl/anton/Anton-Regular.ttf", "talking_head render/style.json, image_studio anton"),
    (WEB, "Cairo.ttf", "Cairo", "ofl/cairo/Cairo[slnt,wght].ttf", "web_film world_example.json"),
    (STYLES, "ArefRuqaa-Bold.ttf", "Aref Ruqaa", "ofl/arefruqaa/ArefRuqaa-Bold.ttf", "styles build_style.py Ruqaa"),
    (STYLES, "Tajawal-Bold.ttf", "Tajawal", "ofl/tajawal/Tajawal-Bold.ttf", "styles Tajawal"),
    (STYLES, "Lalezar-Regular.ttf", "Lalezar", "ofl/lalezar/Lalezar-Regular.ttf", "styles Lalezar"),
    (STYLES, "ElMessiri-700.ttf", "El Messiri", None, "styles Messiri"),
    (STYLES, "Amiri-Bold.ttf", "Amiri", "ofl/amiri/Amiri-Bold.ttf", "styles Amiri"),
    (STYLES, "ScheherazadeNew-Bold.ttf", "Scheherazade New", "ofl/scheherazadenew/ScheherazadeNew-Bold.ttf",
     "styles Scheherazade (Quran verses)"),
    (CARTOON, "Lalezar-Regular.ttf", "Lalezar", "ofl/lalezar/Lalezar-Regular.ttf", "cartoon engine/index.html"),
    (MATRICES, "KOSIFJumuah-Bold.woff2", "KOSIF Jumuah", None, "matrices scene.py (owner's own OFL derivative of Amiri)"),
]
LICENCE = "OFL-1.1"

# Local places that hold the same OFL files (searched in this order; exact hint paths first, then a pruned walk).
DEFAULT_ROOTS = [
    HOME / "kosif-own" / "black-dragon",                       # the original engine copy (byte-identical fonts)
    HOME / "OneDrive" / "Desktop" / "التنين الأسود",
    HOME / "OneDrive" / "Desktop" / "مهارات" / "التنين الأسود",   # the folder moved into «مهارات» on 2026-11-15
    HOME / ".claude" / "skills" / "black-dragon-cinema",
    HOME / ".claude" / "skills" / "canvas-design" / "canvas-fonts",
    HOME / "kosif-tool",
    HOME / "kosif-own",
    HOME / ".claude" / "skill-backups",
    HOME / "skill-backups",
]
if os.environ.get("LOCALAPPDATA"):
    DEFAULT_ROOTS.append(Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts")
DEFAULT_ROOTS.append(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts")
HINTS = {  # file -> relative dirs under HOME checked before any walk
    "KOSIFJumuah-Bold.woff2": ["kosif-own/black-dragon/engines/matrices/assets", "kosif-tool/fonts/kosif-jumuah",
                               "kosif-own/kosif-tool/fonts/kosif-jumuah"],
    "Anton-Regular.ttf": ["kosif-own/black-dragon/engines/talking_head/data/fonts", "kosif-tool/.claude/skills/talking-head-reels/assets/fonts"],
    "Cairo.ttf": ["kosif-own/black-dragon/engines/web_film/assets/fonts"],
    "ScheherazadeNew-Bold.ttf": ["kosif-tool/styles/dua/kit/fonts", "kosif-own/kosif-tool/styles/dua/kit/fonts"],
    "Lalezar-Regular.ttf": ["kosif-tool/.claude/skills/cartoon-audio-short/kit/fonts", "kosif-tool/.claude/skills/kosif-superpowers/proofs/_shared/fonts"],
    "Tajawal-Bold.ttf": ["kosif-tool/.claude/skills/kosif-superpowers/proofs/_shared/fonts"],
    "InstrumentSerif-Italic.ttf": ["kosif-own/black-dragon/engines/cinema/assets/fonts", ".claude/skills/canvas-design/canvas-fonts"],
}
_CINEMA_HINT = ["kosif-own/black-dragon/engines/cinema/assets/fonts",
                "kosif-tool/.claude/skills/kosif-superpowers/vendor/100-superskills/skills/kosif-mimic/assets/fonts",
                "kosif-tool/.claude/skills/kosif-superpowers/proofs/_shared/fonts"]
for _f in ("ArefRuqaa-Bold.ttf", "Cairo-900.ttf", "Cairo-700.ttf", "Cairo-400.ttf", "Amiri-Bold.ttf", "ElMessiri-700.ttf",
           "Tajawal-Black.ttf", "ReemKufi-700.ttf", "Tajawal-Bold.ttf", "Lalezar-Regular.ttf"):
    HINTS[_f] = HINTS.get(_f, []) + _CINEMA_HINT


def entries(root=PKG):
    return [{"folder": f, "file": n, "family": fam, "gf": gf, "used_by": use, "licence": LICENCE,
             "path": Path(root) / f / n,
             "url": (GF_RAW + urllib.parse.quote(gf)) if gf else None} for f, n, fam, gf, use in MANIFEST]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(path, family):
    """Opens with PIL ImageFont and names itself `family`. Returns (ok, reason)."""
    try:
        from PIL import ImageFont
        f = ImageFont.truetype(str(path), 40)
        name = " ".join(x for x in f.getname() if x)
    except Exception as e:  # pragma: no cover - depends on FreeType build
        if str(path).lower().endswith(".woff2") and Path(path).read_bytes()[:4] == b"wOF2":
            return True, "woff2 header ok (PIL could not open: %s)" % e
        return False, "PIL cannot open: %s" % e
    key = lambda s: s.lower().replace(" ", "")
    if key(family) not in key(name):
        return False, "family %r does not match %r" % (name, family)
    return True, name


def _lock_path(folder):
    return Path(folder) / LOCK


def read_lock(folder):
    p = _lock_path(folder)
    if p.is_file():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("schema") == LOCK_SCHEMA:
                return d
        except Exception:
            pass
    return {"schema": LOCK_SCHEMA, "fonts": {}}


def write_lock(folder, name, rec):
    d = read_lock(folder)
    d["fonts"][name] = rec
    d["fonts"] = dict(sorted(d["fonts"].items()))
    _lock_path(folder).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _tag(family):
    return family.replace(" ", "").lower()


def _is_ofl_for(p, family):
    n = p.name.lower()
    if p.suffix.lower() not in (".txt", ".md") or ("ofl" not in n and "licen" not in n):
        return False
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "OPEN FONT LICENSE" in t.upper() and (family.lower() in t.lower() or _tag(family) in n.replace("-", "").replace("_", ""))


def licence_present(folder, family):
    """True when some OFL text in `folder` names `family` (in its text or its file name)."""
    return any(_is_ofl_for(p, family) for p in Path(folder).glob("*"))


LICENCE_HINTS = {  # family -> local licence texts (relative to HOME) when the chosen source folder has none
    "KOSIF Jumuah": ["kosif-tool/fonts/kosif-jumuah/OFL.txt", "kosif-own/kosif-tool/fonts/kosif-jumuah/OFL.txt"],
    "Instrument Serif": ["kosif-own/kosif-atlas/skills/97-frontend-design-director/206-frontend-design-director/examples/assets/InstrumentSerif-OFL.txt"],
}


def licence_beside(src, family, use_hints=True):
    """An OFL text naming this family: next to the source font, else a known local copy."""
    d = Path(src).parent
    cands = sorted(d.glob("*.txt"), key=lambda p: (_tag(family) not in p.name.lower().replace("-", ""), p.name))
    hint_files = [HOME / h for h in LICENCE_HINTS.get(family, [])] if use_hints else []
    for p in cands + [h for h in hint_files if h.is_file()]:
        if _is_ofl_for(p, family):
            return p
    return None


def licence_name(folder, family):
    base = "OFL-%s.txt" % family.replace(" ", "")
    return base if not (Path(folder) / base).exists() else None


def doctor(root=PKG, as_json=False, out=None):
    out = out or sys.stdout
    rows = []
    for e in entries(root):
        ok = e["path"].is_file()
        rows.append({"folder": e["folder"], "file": e["file"], "family": e["family"], "present": ok,
                     "licence": e["licence"], "licence_text": licence_present(e["path"].parent, e["family"]),
                     "downloadable": bool(e["url"]), "used_by": e["used_by"]})
    missing = [r for r in rows if not r["present"]]
    if as_json:
        print(json.dumps({"root": str(root), "fonts": rows, "missing": len(missing)}, ensure_ascii=False, indent=1), file=out)
    else:
        for r in rows:
            print("%-7s %-32s %-28s %s%s" % ("OK" if r["present"] else "MISSING", r["file"], r["folder"], r["family"],
                                            "" if r["licence_text"] else "  (no licence text yet)"), file=out)
        print("%d/%d present%s" % (len(rows) - len(missing), len(rows),
                                   "" if not missing else " - run: python scripts/dragon.py tool fonts fetch --yes"), file=out)
    return 1 if missing else 0


def index_roots(roots, wanted):
    """filename(lower) -> [paths], pruned walk, stops looking for a name once found."""
    found = {}
    for r in roots:
        r = Path(r)
        if not r.is_dir():
            continue
        for dp, dns, fns in os.walk(r):
            dns[:] = [d for d in dns if d not in PRUNE]
            for fn in fns:
                k = fn.lower()
                if k in wanted:
                    found.setdefault(k, []).append(Path(dp) / fn)
    return found


def find_local(todo, roots, use_hints=True, log=print):
    """For each manifest entry: first verified local candidate (hints, then --from / default roots)."""
    pick, rejected = {}, []

    def take(e, cands):
        for c in cands:
            if not c.is_file() or c.resolve() == e["path"].resolve():
                continue
            ok, why = verify(c, e["family"])
            if ok:
                pick[id(e)] = c
                return True
            rejected.append((str(c), why))
        return False

    rest = []
    for e in todo:
        hints = [HOME / h / e["file"] for h in HINTS.get(e["file"], [])] if use_hints else []
        if not take(e, hints):
            rest.append(e)
    if rest:
        log("searching %d folder(s) for %d file name(s) ..." % (len(roots), len({e['file'] for e in rest})))
        idx = index_roots(roots, {e["file"].lower() for e in rest})
        for e in rest:
            take(e, idx.get(e["file"].lower(), []))
    return pick, rejected


def download(url, dest_dir):
    if not url.startswith(GF_RAW):
        raise ValueError("refusing non google/fonts URL: " + url)
    p = Path(dest_dir) / Path(urllib.parse.unquote(url)).name
    req = urllib.request.Request(url, headers={"User-Agent": "black-dragon-fonts/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(p, "wb") as fh:
        shutil.copyfileobj(r, fh)
    return p


def place(e, src, source, kind, lic_src=None, lic_url=None, log=print):
    """Copy src -> e['path'] (never overwrite), licence beside it, lock record."""
    dst = e["path"]
    if dst.exists():
        log("keep    %s (exists, not overwritten)" % dst)
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)
    lic_file = None
    if licence_present(dst.parent, e["family"]):
        lic_file = "(already in folder)"
    else:
        name = licence_name(dst.parent, e["family"])
        if name and lic_src:
            shutil.copyfile(lic_src, dst.parent / name)
            lic_file = name
        elif name and lic_url:
            try:
                tmpd = tempfile.mkdtemp()
                shutil.copyfile(download(lic_url, tmpd), dst.parent / name)
                shutil.rmtree(tmpd, ignore_errors=True)
                lic_file = name
            except Exception as ex:
                log("warn    licence text not downloaded for %s: %s" % (e["family"], ex))
    rec = {"family": e["family"], "licence": e["licence"], "sha256": sha256(dst), "bytes": dst.stat().st_size,
           "source": source, "source_kind": kind, "licence_file": lic_file, "used_by": e["used_by"],
           "placed_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    write_lock(dst.parent, dst.name, rec)
    log("placed  %s  <- %s%s" % (dst, source, "" if lic_file else "  (no licence text found)"))
    return rec


def repair_licences(ents, use_defaults=True, log=print):
    """Fonts present but without a licence text beside them: copy one (never overwriting)."""
    for e in ents:
        folder = e["path"].parent
        if e["path"].exists() and not licence_present(folder, e["family"]):
            src = licence_beside(e["path"], e["family"], use_hints=use_defaults)
            name = licence_name(folder, e["family"])
            if src and name:
                shutil.copyfile(src, folder / name)
                lk = read_lock(folder)
                if e["file"] in lk["fonts"]:
                    write_lock(folder, e["file"], dict(lk["fonts"][e["file"]], licence_file=name))
                log("licence %s <- %s" % (folder / name, src))


def fetch(root=PKG, extra=(), use_defaults=True, do_download=False, yes=False, log=print):
    ents = entries(root)
    todo = [e for e in ents if not e["path"].exists()]
    if not todo:
        if yes:
            repair_licences(ents, use_defaults, log)
        log("all %d fonts present; nothing to fetch" % len(ents))
        return 0, []
    pick, rejected = {}, []
    if extra:  # --from folders win over the default places
        pick, rejected = find_local(todo, [Path(x) for x in extra], use_hints=False, log=log)
    if use_defaults:
        p2, r2 = find_local([e for e in todo if id(e) not in pick], DEFAULT_ROOTS, use_hints=True, log=log)
        pick.update(p2); rejected += r2
    for c, why in rejected[:20]:
        log("reject  %s: %s" % (c, why))
    plan = []
    for e in todo:
        if id(e) in pick:
            plan.append(("copy", e, pick[id(e)]))
        elif e["url"] and do_download:
            plan.append(("download", e, e["url"]))
        else:
            plan.append(("missing", e, e["url"] or "local only (no upstream file with this name)"))
    placed = []
    if not yes:
        for act, e, src in plan:
            log("plan    %-8s %s/%s  <- %s" % (act, e["folder"], e["file"], src))
        log("dry run: nothing written. Add --yes to do it%s." % ("" if do_download else " (and --download for the rest)"))
        return (1 if any(a == "missing" for a, _, _ in plan) else 0), plan
    for act, e, src in plan:
        if e["path"].exists():  # an earlier entry of this run may not create it, but stay safe
            continue
        if act == "copy":
            rec = place(e, src, str(src), "local", lic_src=licence_beside(src, e["family"]),
                        lic_url=(GF_RAW + urllib.parse.quote(str(Path(e["gf"]).parent.as_posix()) + "/OFL.txt")) if (e["gf"] and do_download) else None,
                        log=log)
        elif act == "download":
            tmpd = tempfile.mkdtemp(prefix="bd-fonts-")
            try:
                got = download(src, tmpd)
                ok, why = verify(got, e["family"])
                if not ok:
                    log("reject  %s: %s" % (src, why))
                    continue
                rec = place(e, got, src, "download",
                            lic_url=GF_RAW + urllib.parse.quote(Path(e["gf"]).parent.as_posix() + "/OFL.txt"), log=log)
            except Exception as ex:
                log("fail    %s: %s" % (src, ex))
                continue
            finally:
                shutil.rmtree(tmpd, ignore_errors=True)
        else:
            log("missing %s/%s (%s)" % (e["folder"], e["file"], src))
            continue
        if rec:
            placed.append(str(e["path"]))
    repair_licences(ents, use_defaults, log)
    still = [e for e in ents if not e["path"].exists()]
    log("%d placed, %d still missing" % (len(placed), len(still)))
    return (1 if still else 0), placed


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dragon.py tool fonts", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(PKG), help="package root (default: this skill)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor"); d.add_argument("--json", action="store_true")
    sub.add_parser("list")
    f = sub.add_parser("fetch")
    f.add_argument("--from", dest="src", action="append", default=[], help="extra local folder to search (repeatable)")
    f.add_argument("--no-default-sources", action="store_true", help="search only --from folders")
    f.add_argument("--download", action="store_true", help="download what is still missing from github.com/google/fonts")
    f.add_argument("--yes", action="store_true", help="actually copy/download (default: print the plan)")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if not root.is_dir():
        print("no such root: %s" % root, file=sys.stderr)
        return 2
    if a.cmd == "doctor":
        return doctor(root, a.json)
    if a.cmd == "list":
        print(json.dumps([{k: (str(v) if isinstance(v, Path) else v) for k, v in e.items()} for e in entries(root)],
                         ensure_ascii=False, indent=1))
        return 0
    for s in a.src:
        if not Path(s).is_dir():
            print("--from: no such folder: %s" % s, file=sys.stderr)
            return 2
    rc, _ = fetch(root, a.src, not a.no_default_sources, a.download, a.yes)
    return rc


if __name__ == "__main__":
    sys.exit(main())
