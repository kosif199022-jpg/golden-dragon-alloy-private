#!/usr/bin/env python3
"""atlas — curated KOSIF Atlas skills inside Black Dragon (v10.13).

    dragon.py tool atlas list                    # the bundled picks and when to read each
    dragon.py tool atlas show <name>             # path + first lines of a pick's SKILL.md
    dragon.py tool atlas find "captions arabic"  # search the local Atlas index (~/kosif-own/kosif-atlas/index.json)
                                                 # safe filter: READ_ONLY_OK, no risk flags, permissive licence

Why: Atlas mirrors ~15,000 third-party skills, mostly off-topic for video (Workspace, Azure, Zoom...).
254 media-related, read-only, MIT/Apache/BSD skills were reviewed; 5 that add something new were copied
verbatim into skills/atlas-picks/ with their SOURCE.md (repo + commit) and licence. They are reference text:
nothing here runs their code, and `find` only reads the index.
"""
import argparse, json, os, re, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
PICKS_DIR = SKILL / "skills" / "atlas-picks"
PICKS = {
    "joined-audio-transcript-drift": ("audio",
        "لزق مقاطع صوت كتير (دعاء، تلاوة، قطع TTS، فصول) والتوقيت بيتزحلق: كل وصلة بتزوّد ~50 ms. اقراها قبل concat."),
    "legibility-contrast-and-spacing": ("typography",
        "كتابة فوق فوتيج: تباين 4.5:1 كحد أدنى (7:1 أحسن للريلز)، scrim، تتبّع ومسافة سطور. قبل أي كابشن أو تايتل."),
    "social-video-hooks": ("reels",
        "أول ثانية في الريل + جدول بيتس (وقت/كلام/صورة/معلومة جديدة) + فحص يشتغل بصوت ومن غير صوت."),
    "awwwards-motion": ("motion",
        "أفلام الويب والكانفاس: ثوابت سبرينج (300/30/1)، شيدرات GLSL، بارتيكلز، post-processing."),
    "ffmpeg": ("video",
        "مرجع ffmpeg: إنكود بكارت الشاشة (NVENC)، filter_complex، فحص VFR وPTS/DTS من ffprobe."),
}
ATLAS_ROOTS = [Path(os.environ["DRAGON_ATLAS_ROOT"])] if os.environ.get("DRAGON_ATLAS_ROOT") else []
ATLAS_ROOTS += [Path.home() / "kosif-own" / "kosif-atlas", Path.home() / "kosif-atlas"]
SAFE_LICENSES = {"MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "ISC", "0BSD", "Unlicense", "CC0-1.0",
                 "MIT-0", "MIT AND Apache-2.0", "MIT OR Apache-2.0"}


def cmd_list(a):
    rows = [{"name": n, "area": ar, "when": w, "path": str(PICKS_DIR / n / "SKILL.md"),
             "present": (PICKS_DIR / n / "SKILL.md").is_file()} for n, (ar, w) in PICKS.items()]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1)); return 0
    for r in rows:
        print(f"{'✓' if r['present'] else '✗'} {r['name']} [{r['area']}]\n   {r['when']}\n   read: {r['path']}")
    return 0 if all(r["present"] for r in rows) else 1


def cmd_show(a):
    p = PICKS_DIR / a.name / "SKILL.md"
    if a.name not in PICKS or not p.is_file():
        print("picks: " + ", ".join(PICKS), file=sys.stderr); return 2
    print(f"# {p}\n# source: {PICKS_DIR / a.name / 'SOURCE.md'}\n")
    print("\n".join(p.read_text(encoding="utf-8").splitlines()[:a.lines]))
    return 0


def atlas_index():
    for r in ATLAS_ROOTS:
        f = r / "index.json"
        if f.is_file():
            return r, json.loads(f.read_text(encoding="utf-8-sig")).get("skills", [])
    return None, []


def cmd_find(a):
    root, skills = atlas_index()
    if root is None:
        print("Atlas index not found locally (set DRAGON_ATLAS_ROOT). Searched: "
              + ", ".join(map(str, ATLAS_ROOTS)), file=sys.stderr)
        return 4
    words = [w for w in re.findall(r"\w+", a.query.lower()) if len(w) > 1]
    hits = []
    for s in skills:
        safe = s.get("verdict") == "READ_ONLY_OK" and not s.get("risk_flags") and s.get("license") in SAFE_LICENSES
        if not safe and not a.all:
            continue
        name, desc = s.get("skill", "").lower(), s.get("description", "").lower()
        score = sum(3 * (w in name) + (w in desc) for w in words)
        if score:
            hits.append((score, s))
    hits.sort(key=lambda x: (-x[0], x[1].get("id", 0)))
    out = [{"id": s["id"], "skill": s["skill"], "license": s.get("license"), "verdict": s.get("verdict"),
            "risk_flags": s.get("risk_flags"), "path": str(root / s["path"] / "SKILL.md"),
            "bundled": s["skill"] in PICKS, "description": s.get("description", "")[:200]} for _, s in hits[:a.limit]]
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1)); return 0
    print(f"Atlas · {a.query} · {len(hits)} matches ({'all' if a.all else 'safe only'}) · {root}")
    for o in out:
        tag = " · bundled" if o["bundled"] else ""
        print(f"  {o['id']} {o['skill']} [{o['license']} · {o['verdict']}{tag}]\n     {o['description']}\n     read: {o['path']}")
    print("Third-party text: read as reference, never run its scripts without review and the user's yes.")
    return 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="dragon.py tool atlas", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list"); l.add_argument("--json", action="store_true")
    s = sub.add_parser("show"); s.add_argument("name"); s.add_argument("--lines", type=int, default=60)
    f = sub.add_parser("find"); f.add_argument("query"); f.add_argument("--limit", type=int, default=10)
    f.add_argument("--all", action="store_true", help="include REVIEW_BEFORE_INSTALL / flagged / other licences")
    f.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    return {"list": cmd_list, "show": cmd_show, "find": cmd_find}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
