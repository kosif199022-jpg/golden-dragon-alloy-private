#!/usr/bin/env python3
"""sp — Black Dragon <-> KOSIF Superpowers live bridge (v10.13).

    dragon.py tool sp where                      # every local checkout, which one is used and why
    dragon.py tool sp find "ريل تكريم بأغنية"    # hub.py find: ranked tools (ready?) + exact command, powers, guides
    dragon.py tool sp doctor [--area edit]       # which of the 212 tools run on this machine now
    dragon.py tool sp tool verify-video          # one tool card: commands, inputs, safety, consent
    dragon.py tool sp qc FILM.mp4 --duration 15  # second delivery gate: Superpowers verify-video (9:16, 30 fps, AAC, LUFS)
    dragon.py tool sp run <id> [--yes] [args]    # hub.py run; consent tools stay blocked (exit 3) without --yes

Why: v10.0-v10.12 only *printed* command templates and looked for the older ~/kosif-own checkout.
This tool calls the freshest checkout's hub.py as a child process (read-only for where/find/doctor/tool).
`qc` runs only verify-video, which reads the film with ffprobe/ffmpeg and writes one JSON report.
`run` passes --yes through only when the user typed it: approval stays with the user, never with this tool.
"""
import argparse, json, os, subprocess, sys
from importlib import util
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
_spec = util.spec_from_file_location("bd_superpowers", SKILL / "app" / "dragon" / "superpowers.py")
SP = util.module_from_spec(_spec); _spec.loader.exec_module(SP)
TIMEOUT = int(os.environ.get("DRAGON_SP_TIMEOUT", "180"))


def root_or_exit():
    r = SP.pick()
    if r is None:
        print("Superpowers مش موجود على الجهاز ده. دوّرت في:\n  " + "\n  ".join(map(str, SP.candidates()))
              + "\nحط المسار في DRAGON_SUPERPOWERS_ROOT لو هو في مكان تاني.", file=sys.stderr)
        sys.exit(4)
    return r


def hub(args, capture=True, timeout=TIMEOUT):
    root = root_or_exit()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    cmd = [sys.executable, str(root / "scripts" / "hub.py")] + list(args)
    try:
        p = subprocess.run(cmd, capture_output=capture, text=True, encoding="utf-8", errors="replace",
                           env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"hub.py {' '.join(args[:2])}: timeout after {timeout}s (DRAGON_SP_TIMEOUT)", file=sys.stderr)
        sys.exit(5)
    return p


def hub_json(args):
    p = hub(list(args) + ["--json"])
    if p.returncode not in (0,):
        sys.stderr.write(p.stderr[-2000:])
        sys.exit(p.returncode or 1)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        sys.stderr.write("hub.py did not return JSON:\n" + p.stdout[:800])
        sys.exit(6)


def abs_command(card, root):
    """First command with an absolute script path and this Python (works from any cwd, spaces included)."""
    fc = (card.get("first_command") or "").strip()
    run_from = Path(card.get("run_from") or root)
    parts = fc.split(maxsplit=2)
    if len(parts) >= 2 and parts[0] in ("python", "python3") and parts[1].endswith(".py"):
        script = run_from / parts[1]
        rest = parts[2] if len(parts) > 2 else ""
        return f'"{sys.executable}" "{script}" {rest}'.strip()
    return fc


def cmd_where(a):
    rows = SP.survey()
    best = SP.pick()
    for r in rows:
        r["used"] = best is not None and Path(r["path"]) == best
    out = {"used": str(best) if best else None, "rule": "DRAGON_SUPERPOWERS_ROOT if set, else the freshest checkout",
           "checkouts": rows}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1)); return 0
    for r in rows:
        mark = "← المستخدم" if r["used"] else ""
        print(f"{'✓' if r['present'] else '✗'} {r['path']} {mark}")
    return 0 if best else 4


def cmd_find(a):
    root = root_or_exit()
    res = hub_json(["find", a.query, "--limit", str(a.limit)])
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1)); return 0
    plan = res.get("execution_plan") or {}
    print(f"سوبر باور · {a.query}   ({root})")
    print("\n▶ أدوات")
    for i, t in enumerate(res.get("tools", []), 1):
        st = (t.get("readiness") or {}).get("state", "?")
        gate = " · محتاجة موافقة" if (t.get("consent") or t.get("safety") in ("network", "runs-external-programs")) else ""
        print(f"  {i}. {t['id']} [{st}{gate}] {t.get('title_ar') or t.get('title_en','')}")
        print(f"     $ {abs_command(t, root)}")
    if plan.get("blocked"):
        print("\n✗ ناقصها حاجة: " + ", ".join(f"{b['id']} ({', '.join(b.get('missing', []))})" for b in plan["blocked"]))
    pw = res.get("powers", [])[:5]
    if pw:
        print("\n▶ قدرات")
        for p in pw:
            print(f"  {p['id']} [{p.get('status','')}] {p.get('name_ar') or p.get('name_en','')}")
    gd = res.get("guides", [])[:3]
    if gd:
        print("\n▶ أدلة: " + " · ".join(str(root / g["path"]) for g in gd))
    return 0


def cmd_doctor(a):
    res = hub_json(["doctor"] + (["--area", a.area] if a.area else []))
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1)); return 0
    s = res.get("summary", {})
    print(f"سوبر باور: {s.get('ready')} جاهزة من {s.get('tools')} · ناقصها حاجة {s.get('missing')}")
    for t in res.get("tools", []):
        if t.get("state") != "ready":
            print(f"  ✗ {t['id']}: {', '.join(t.get('missing', []))}")
    for req, n in s.get("biggest_unlocks", [])[:3]:
        print(f"  تثبيت {req} يفتح {n} أداة (بموافقتك بس)")
    return 0


def cmd_tool(a):
    card = hub_json(["tool", a.id])
    if a.json:
        print(json.dumps(card, ensure_ascii=False, indent=1)); return 0
    root = root_or_exit()
    print(f"{card['id']} · {card.get('title_ar') or card.get('title_en')} [{(card.get('readiness') or {}).get('state')}]")
    print(card.get("summary_ar") or card.get("summary_en") or "")
    print(f"safety: {card.get('safety')} · consent: {card.get('consent') or '—'}")
    for c in card.get("commands", [])[:8]:
        print(f"  {c.get('name')}: {c.get('example')}  — {c.get('does','')}")
    print(f"$ {abs_command(card, root)}")
    return 0


def cmd_qc(a):
    """verify-video only: reads the film (ffprobe/ffmpeg), writes one JSON report next to it."""
    film = Path(a.file).resolve()
    if not film.is_file():
        print(f"مش لاقي الملف: {film}", file=sys.stderr); return 2
    report = Path(a.out).resolve() if a.out else film.with_name(film.stem + ".sp_qc.json")
    if report.exists() and not a.force:
        print(f"التقرير موجود: {report} (استخدم --force أو --out)", file=sys.stderr); return 2
    args = ["run", "--yes", "verify-video", str(film), "--aspect", a.aspect, "--fps", str(a.fps), "--json", str(report)]
    if a.duration:
        args += ["--duration", str(a.duration)]
    if a.lufs is not None:
        args += ["--lufs", str(a.lufs)]
    if a.no_audio:
        args += ["--no-audio"]
    p = hub(args, capture=False, timeout=max(TIMEOUT, 600))
    verdict = "PASS" if p.returncode == 0 else "FAIL"
    print(f"sp qc: {verdict} (exit {p.returncode}) · report: {report}")
    return p.returncode


def cmd_run(a, extra):
    args = ["run"] + (["--yes"] if a.yes else []) + [a.id] + extra
    p = hub(args, capture=False, timeout=None)
    if p.returncode == 3:
        print("الأداة دي محتاجة موافقة (شبكة، أو برامج خارجية، أو حقوق). اسأل المستخدم الأول، وبعد موافقته شغّلها بـ --yes.",
              file=sys.stderr)
    return p.returncode


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="dragon.py tool sp", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("where"); w.add_argument("--json", action="store_true")
    f = sub.add_parser("find"); f.add_argument("query"); f.add_argument("--limit", type=int, default=5)
    f.add_argument("--json", action="store_true")
    d = sub.add_parser("doctor"); d.add_argument("--area"); d.add_argument("--json", action="store_true")
    t = sub.add_parser("tool"); t.add_argument("id"); t.add_argument("--json", action="store_true")
    q = sub.add_parser("qc", help="Superpowers verify-video as a second delivery gate")
    q.add_argument("file"); q.add_argument("--aspect", default="9:16"); q.add_argument("--fps", type=float, default=30)
    q.add_argument("--duration", type=float); q.add_argument("--out"); q.add_argument("--force", action="store_true")
    q.add_argument("--lufs", type=float, help="target loudness (verify-video default -14)")
    q.add_argument("--no-audio", action="store_true", help="the film is silent on purpose")
    r = sub.add_parser("run", help="hub.py run; --yes only after the user approved")
    r.add_argument("--yes", action="store_true"); r.add_argument("id")
    a, extra = ap.parse_known_args(argv)
    if a.cmd != "run" and extra:
        ap.error("unrecognized arguments: " + " ".join(extra))
    return {"where": cmd_where, "find": cmd_find, "doctor": cmd_doctor, "tool": cmd_tool,
            "qc": cmd_qc}.get(a.cmd, lambda x: cmd_run(x, extra))(a)


if __name__ == "__main__":
    sys.exit(main())
