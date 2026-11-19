#!/usr/bin/env python3
"""library — the owner's skill packs and prompt libraries inside Black Dragon (v10.17).

    dragon.py tool library list                      # the 12 bundled packs: what each is for, and what it overlaps
    dragon.py tool library show faceless-shorts      # path + first lines of the pack's SKILL.md
    dragon.py tool library find "ريل مينيمال عربي"    # rank packs and prompts for a request (Arabic or English)
    dragon.py tool library prompts                   # the prompt files and their 105 indexed entries
    dragon.py tool library prompt h09                # print one prompt (h01.. = Hady Raie library, a01..a86 = Style Atlas)
    dragon.py tool library grep "Seedance"           # line search across every prompt file
    dragon.py tool library doctor                    # every indexed file is on disk, counts match

Everything here is read-only: it prints text and paths. The packs under skills/library/ are bundled verbatim
(SOURCE.json has the archive SHA-256). Their scripts are source to read before running; installers, repository
downloads and paid generation (Higgsfield, Kling) still need the owner's explicit yes (see `tool hf check`).
"""
import argparse, json, re, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
INDEX = SKILL / "app" / "data" / "library.json"
_AR = str.maketrans("أإآٱةىؤئ", "ااااهيوي")
_STOP = {"في", "من", "على", "عن", "the", "and", "for", "with", "to", "of", "or", "in", "عايز", "اعمل", "اعملي", "هات"}
# request words -> index words (Egyptian Arabic to the English the pack descriptions use)
SYN = {"ريل": "reel reels", "ريلز": "reel reels", "شورتس": "shorts", "شورت": "shorts", "موشن": "motion", "جرافيك": "graphics",
       "ستيكمان": "stickman stick", "موقع": "site website", "منتج": "product", "اعلان": "ad promo launch", "كلينج": "kling",
       "مينيمال": "minimal", "وش": "faceless face", "وجه": "faceless face", "شرح": "explainer", "اكسبلينر": "explainer",
       "كرتون": "cartoon", "ستوري": "storyboard story", "بورد": "storyboard", "صوره": "image", "صور": "image",
       "ثامنيل": "thumbnail", "شخصيه": "character", "افتر": "after effects", "افكت": "after effects", "برومبت": "prompt",
       "برومنت": "prompt", "ستايل": "style", "فيلم": "film", "مونتاج": "edit montage", "متحدث": "talking head",
       "توكينج": "talking head", "سيدانس": "seedance", "فيو": "veo flow", "لعبه": "toy", "ساس": "saas", "تطبيق": "app saas"}


def norm(s):
    s = re.sub(r"[ً-ْـ]", "", str(s).lower()).translate(_AR)
    return re.sub(r"[^\w\s]", " ", s)


def words(q):
    out = []
    for w in norm(q).split():
        if len(w) < 2 or w in _STOP:
            continue
        out.append(w)
        base = w[2:] if w.startswith("ال") and len(w) > 4 else w
        if base != w:
            out.append(base)
        out += SYN.get(base, "").split()
    return list(dict.fromkeys(out))


def load():
    if not INDEX.is_file():
        raise SystemExit(f"library index missing: {INDEX}")
    return json.loads(INDEX.read_text(encoding="utf-8"))


def score(ws, strong, weak):
    s, w = set(norm(strong).split()), set(norm(weak).split())
    return sum(3 * (x in s) + (x in w) for x in ws)


def pfile(lib, fid):
    return next(f for f in lib["prompt_files"] if f["id"] == fid)


def cmd_list(a):
    lib = load()
    rows = [dict(p, present=(SKILL / p["entry"]).is_file(), path=str(SKILL / p["entry"])) for p in lib["packs"]]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1)); return 0
    for r in rows:
        print(f"{'✓' if r['present'] else '✗'} {r['id']} [{r['area']}] · {r['files']} ملف\n   {r['ar']}\n   {r['overlap']}\n   read: {r['path']}")
    print(f"\n{len(rows)} حزمة · `tool library show <id>` · البرومبتات: `tool library prompts`")
    return 0 if all(r["present"] for r in rows) else 1


def cmd_show(a):
    lib = load()
    p = next((x for x in lib["packs"] if x["id"] == a.id or x["name"] == a.id), None)
    if p is None:
        print("packs: " + ", ".join(x["id"] for x in lib["packs"]), file=sys.stderr); return 2
    entry = SKILL / p["entry"]
    print(f"# {p['id']} — {p['ar']}\n# entry: {entry}\n# source: {p['source_archive']} sha256={p['source_archive_sha256'][:16]}…"
          f" ({p['files']} files)\n# {p['overlap']}")
    for extra in p["skill_files"][1:]:
        print(f"# also: {SKILL / extra}")
    print()
    print("\n".join(entry.read_text(encoding="utf-8", errors="replace").splitlines()[:a.lines]))
    return 0


def cmd_find(a):
    lib, ws = load(), words(a.query)
    hits = []
    for p in lib["packs"]:
        sc = score(ws, p["id"].replace("-", " ") + " " + p["name"] + " " + p["area"], p["ar"] + " " + p["en"])
        if sc:
            hits.append((sc, "pack", p["id"], p["ar"], f"tool library show {p['id']}"))
    for s in lib["prompts"]:
        sc = score(ws, s["title"] + " " + s.get("slug", ""), s["section"])
        if sc:
            hits.append((sc, "prompt", s["id"], f"{s['title']} — {s['section']}", f"tool library prompt {s['id']}"))
    hits.sort(key=lambda h: (-h[0], h[1], h[2]))
    out = [{"score": h[0], "kind": h[1], "id": h[2], "what": h[3], "cmd": "python scripts/dragon.py " + h[4]} for h in hits[:a.limit]]
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1)); return 0
    if not out:
        print(f"library: مفيش نتيجة لـ «{a.query}». جرّب `tool library list` أو `tool library grep`."); return 1
    for o in out:
        print(f"{o['score']:3} {o['kind']:6} {o['id']}\n     {o['what']}\n     {o['cmd']}")
    return 0


def cmd_prompts(a):
    lib = load()
    if a.json:
        print(json.dumps({"files": lib["prompt_files"], "prompts": lib["prompts"]}, ensure_ascii=False, indent=1)); return 0
    for f in lib["prompt_files"]:
        ok = (SKILL / f["file"]).is_file()
        print(f"{'✓' if ok else '✗'} [{f['id']}] {f['title']}\n   {SKILL / f['file']} · {f['lines']} سطر")
        mine = [s for s in lib["prompts"] if s["file"] == f["id"]]
        if f["id"] == "atlas" and not a.all:
            print(f"   {len(mine)} ستايل (a01..a{len(mine):02d}) — `tool library prompts --all` أو `find`")
            continue
        sec = None
        for s in mine:
            if s["section"] != sec:
                sec = s["section"]; print(f"   — {sec}")
            print(f"     {s['id']}  {s['title']}")
    return 0


def cmd_prompt(a):
    lib = load()
    s = next((x for x in lib["prompts"] if x["id"] == a.id or x.get("slug") == a.id), None)
    if s is None:
        print("unknown prompt id; run `tool library prompts --all`", file=sys.stderr); return 2
    f = pfile(lib, s["file"])
    lines = (SKILL / f["file"]).read_text(encoding="utf-8", errors="replace").splitlines()
    if "start" in s:
        start, end = s["start"], s["end"]
    else:  # Style Atlas entry: from its own heading line (after the index) to the next entry
        head = re.compile(r"^#(\d{2}) — ")   # entry header in the file: "#03 — Shadow Puppet Theatre"
        heads = [(i, m.group(1)) for i, ln in enumerate(lines, 1) for m in [head.match(ln)] if m]
        k = next((j for j, (_, n) in enumerate(heads) if n == s["id"][1:]), None)
        if k is None:
            print(f"entry {s['id']} not located; use: tool library grep \"{s['title']}\"", file=sys.stderr); return 3
        start = heads[k][0]
        end = heads[k + 1][0] - 2 if k + 1 < len(heads) else len(lines)   # stop before the next entry's ==== rule
    body = lines[start - 1:end]
    cut = a.lines and len(body) > a.lines
    print(f"# {s['id']} · {s['title']} · {f['file']}:{start}-{end}\n")
    print("\n".join(ln if len(ln) <= a.width else ln[:a.width] + " …" for ln in (body[:a.lines] if cut else body)))
    if cut:
        print(f"\n… {len(body) - a.lines} سطر كمان (--lines 0 للكل)")
    return 0


def cmd_grep(a):
    lib = load()
    pat = re.compile(re.escape(a.pattern), re.I)
    n = 0
    for f in lib["prompt_files"]:
        p = SKILL / f["file"]
        if not p.is_file():
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            for i, ln in enumerate(fh, 1):
                if pat.search(ln):
                    print(f"{f['file']}:{i}: {ln.strip()[:160]}")
                    n += 1
                    if n >= a.limit:
                        print(f"… (--limit {a.limit})"); return 0
    return 0 if n else 1


def cmd_doctor(a):
    lib, bad = load(), []
    for p in lib["packs"]:
        root = SKILL / "skills" / "library" / p["id"]
        have = sum(1 for f in root.rglob("*") if f.is_file() and f.name != "SOURCE.json" and "__pycache__" not in f.parts)
        if not (SKILL / p["entry"]).is_file():
            bad.append(f"{p['id']}: entry missing")
        elif have < p["files"]:
            bad.append(f"{p['id']}: {have}/{p['files']} files")
        if not (root / "SOURCE.json").is_file():
            bad.append(f"{p['id']}: SOURCE.json missing")
    for f in lib["prompt_files"]:
        if not (SKILL / f["file"]).is_file():
            bad.append(f"{f['file']}: missing")
    rep = {"ok": not bad, "packs": len(lib["packs"]), "prompt_files": len(lib["prompt_files"]),
           "prompts": len(lib["prompts"]), "problems": bad}
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if not bad else 1


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="dragon.py tool library", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("list"); x.add_argument("--json", action="store_true")
    x = sub.add_parser("show"); x.add_argument("id"); x.add_argument("--lines", type=int, default=60)
    x = sub.add_parser("find"); x.add_argument("query"); x.add_argument("--limit", type=int, default=8)
    x.add_argument("--json", action="store_true")
    x = sub.add_parser("prompts"); x.add_argument("--all", action="store_true"); x.add_argument("--json", action="store_true")
    x = sub.add_parser("prompt"); x.add_argument("id"); x.add_argument("--lines", type=int, default=80)
    x.add_argument("--width", type=int, default=2000)
    x = sub.add_parser("grep"); x.add_argument("pattern"); x.add_argument("--limit", type=int, default=40)
    sub.add_parser("doctor")
    a = ap.parse_args(argv)
    return {"list": cmd_list, "show": cmd_show, "find": cmd_find, "prompts": cmd_prompts, "prompt": cmd_prompt,
            "grep": cmd_grep, "doctor": cmd_doctor}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
