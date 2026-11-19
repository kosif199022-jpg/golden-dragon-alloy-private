"""alloy selftest — the gate before anyone says «خلص».

    python -X utf8 alloy.py selftest [--quick] [-v]

--quick skips the 217 MB runtime digest and the engine room's own rd.py selftest.
Every runtime test runs with RED_DRAGON_HOME pointed at a throw-away folder, so the owner's real
learning memory (~/.red-dragon) is never written by a test.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

PROBES = [  # sanity probes (not the evaluation): request -> road that must be in the top 3
    ("اعمل ريل من الفيديوهات دي على الأغنية", "road:reel-montage"),
    ("حلل البرنامج ده هندسة عكسية exe", "road:re-file"),
    ("فين الملف اللي عملته؟ خلصت؟", "road:status"),
    ("اعمل محاكي 3D للماكينة دي وازاي بتشتغل", "road:machine-sim"),
    ("طابق كشف البنك مع الحوالات", "road:reconcile"),
    ("حوّل الفيديو ده لكرتون انمي", "road:toon"),
]


def lp(p: Path) -> str:
    s = str(p.resolve())
    return "\\\\?\\" + s if os.name == "nt" else s


def run(root: Path, quick: bool = False, verbose: bool = False) -> int:
    sys.path.insert(0, str(root))
    import alloy  # noqa: E402

    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, bool(ok), detail))

    # 1) SKILL.md against the Agent Skills spec
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"\A---\s*\n(.*?)\n---", text, re.S)
    fm = dict(re.findall(r"^(name|description):\s*(.+)$", m.group(1), re.M)) if m else {}
    desc = fm.get("description", "").strip().strip('"')
    check("SKILL.md: name = folder name", fm.get("name", "").strip() == root.name, fm.get("name", ""))
    check("SKILL.md: description 1–1024 chars", 0 < len(desc) <= 1024, f"{len(desc)} chars")
    n_lines = text.count("\n") + 1
    check("SKILL.md: under 500 lines", n_lines < 500, f"{n_lines} lines")
    refs = sorted(set(re.findall(r"`((?:references|runtime|kb|forge|ledger|branches)/[^`\s*<>]+)`", text)))
    in_kb = []
    if not (root / "runtime").exists():  # portable packing: runtime/ files must be readable from the knowledge base
        kcon = sqlite3.connect(f"file:{(root / 'kb' / 'alloy.db').as_posix()}?mode=ro", uri=True)
        for r in [r for r in refs if r.startswith("runtime/")]:
            if kcon.execute("SELECT 1 FROM units WHERE path = ? LIMIT 1", (r,)).fetchone():
                in_kb.append(r)
    missing = [r for r in refs if r not in in_kb and not os.path.exists(lp(root / r.rstrip("/")))]
    check("SKILL.md: every path it names exists", not missing,
          f"{len(refs)} paths" + (f" ({len(in_kb)} read from kb: alloy show <path>)" if in_kb else "")
          + (f", missing: {missing}" if missing else ""))

    # 2) manifest of the skill's own files
    man = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    portable = not (root / "runtime").exists()   # the cloud packing: no engine room, no branches/ (their text is in kb)
    listed = {rel: meta for rel, meta in man["files"].items()
              if not (portable and rel.startswith("branches/"))}
    bad = [rel for rel, meta in listed.items()
           if not os.path.exists(lp(root / rel)) or hashlib.sha256(open(lp(root / rel), "rb").read()).hexdigest() != meta["sha256"]]
    check("MANIFEST.json: sha-256 of every skill file", not bad,
          f"{len(listed)} files" + (" (portable: branches/ in kb only)" if portable else "") + (f", changed: {bad[:5]}" if bad else ""))

    # 3) knowledge base
    con = sqlite3.connect(f"file:{(root / 'kb' / 'alloy.db').as_posix()}?mode=ro", uri=True)
    qc = con.execute("PRAGMA quick_check").fetchone()[0]
    check("kb: sqlite quick_check", qc == "ok", qc)
    kinds = dict(con.execute("SELECT kind, count(*) FROM units GROUP BY kind").fetchall())
    need = {"road": 43, "rule": 100, "lesson": 200, "thinking": 44, "skill": 600, "reference": 1000, "script": 500,
            "catalog-skill": 10000}
    low = {k: kinds.get(k, 0) for k, n in need.items() if kinds.get(k, 0) < n}
    check("kb: every core kind is there", not low, ", ".join(f"{k}={kinds.get(k, 0)}" for k in need) + (f" LOW {low}" if low else ""))
    n_fts = con.execute("SELECT count(*) FROM fts").fetchone()[0] if False else con.execute("SELECT count(*) FROM units").fetchone()[0]

    # 4) ledger: every original file accounted for, every place exists
    led = con.execute("SELECT path, place FROM ledger").fetchall()
    rt = [r for r in led if r[1].startswith("runtime/")]
    check("ledger: every main file listed", len([r for r in led if not r[0].startswith("branch:")]) == man["runtime_files"],
          f"{len(led)} entries, main files {man['runtime_files']}")
    have_rt = (root / "runtime").exists()
    if have_rt:
        gone = [p for _, p in rt if not os.path.exists(lp(root / p))]
        check("ledger: every runtime/ place exists", not gone, f"{len(rt)} checked" + (f", missing {gone[:3]}" if gone else ""))
    br = [r for r in led if r[1].startswith("branches/")]
    if not portable:
        gone_b = [p for _, p in br if not os.path.exists(lp(root / p))]
        check("ledger: every branches/ place exists", not gone_b, f"{len(br)} checked" + (f", missing {gone_b[:3]}" if gone_b else ""))

    # 5) runtime digest (byte-identical engine room)
    if have_rt and not quick:
        lines = []
        for path, place in sorted(r for r in led if r[1].startswith("runtime/")):
            h = hashlib.sha256(open(lp(root / place), "rb").read()).hexdigest()
            lines.append(f"{path}\t{h}\n")
        dig = hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()
        check("runtime: byte-identical to the source (digest)", dig == man["runtime_digest"], dig[:16])

    # 6) routing sanity probes
    misses = []
    for q, want in PROBES:
        got = [r["id"] for r in alloy.search(q, ["road"], 3)]
        if want not in got:
            misses.append(f"{q} → {got}")
    check("find: sanity probes reach the right road (top 3)", not misses, f"{len(PROBES) - len(misses)}/{len(PROBES)}"
          + (f" misses: {misses}" if misses else ""))

    # 7) code compiles (without writing __pycache__)
    errs = []
    for f in [root / "alloy.py", *sorted((root / "forge").glob("*.py"))]:
        try:
            compile(f.read_text(encoding="utf-8"), str(f), "exec")
        except SyntaxError as e:
            errs.append(f"{f.name}: {e}")
    check("code: alloy.py + forge/*.py compile", not errs, "; ".join(errs))

    # 8) the one door reaches the mind (rd.py) — throw-away memory
    if have_rt:
        env = dict(os.environ, RED_DRAGON_HOME=tempfile.mkdtemp(prefix="alloy-mem-"), PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, "-X", "utf8", str(root / "alloy.py"), "understand", "lkjh,"],
                           capture_output=True, env=env, timeout=120)
        check("door: alloy understand → runtime rd.py", p.returncode == 0, f"rc={p.returncode}")
        if not quick:
            p = subprocess.run([sys.executable, "-I", "-X", "utf8", str(root / "runtime" / "scripts" / "rd.py"), "selftest",
                                "--quick"], capture_output=True, env=env, timeout=900, cwd=str(root / "runtime"))
            tail = p.stdout.decode("utf-8", "replace").strip().splitlines()[-3:]
            check("runtime: rd.py selftest --quick (engine room works where it sits)", p.returncode == 0,
                  f"rc={p.returncode} · " + " | ".join(tail)[:300])

    # report
    width = max(len(n) for n, _, _ in results)
    ok_all = all(ok for _, ok, _ in results)
    for n, ok, d in results:
        print(f"{'✓' if ok else '✗'} {n:<{width}}  {d if (verbose or not ok) else d[:90]}")
    print(f"\n{'ok' if ok_all else 'FAIL'}: {sum(ok for _, ok, _ in results)}/{len(results)}"
          f"{' (quick)' if quick else ''} · units {n_fts}")
    return 0 if ok_all else 1
