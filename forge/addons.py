"""Addons: skills added to the alloy after the blend, without touching runtime/ (which stays byte-identical).

    python -I -X utf8 forge/addons.py            # (re)index addons/ into kb/alloy.db + ledger + MANIFEST.json
    python -I -X utf8 forge/addons.py --check    # read-only: every addon file is in the ledger with the same sha-256

addons/addons.json lists each addon (id, source, licence, private_only, Arabic/English triggers).
Every file becomes a ledger row  addon:<id>/<rel> -> addons/<id>/<rel>.  SKILL.md files become skill units,
other .md files reference units, and code in scripts/tools/engine/kit/src folders script units, all with
origin "addon:<id>". The exact text given to the full-text index is kept in table addon_fts, so a re-run
removes the old rows exactly (the index is contentless). Never executes anything from addons/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "forge"))
import alloy  # noqa: E402

norm = alloy.norm
SKIP_DIRS = {"__pycache__", "node_modules", ".git", "out", "frames"}
CODE_EXT = {".py", ".mjs", ".js", ".cjs", ".ts", ".sh", ".ps1"}
CODE_DIRS = {"scripts", "tools", "engine", "kit", "src"}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not m:
        return {}, text
    fm = {}
    for k, v in re.findall(r"^([A-Za-z_-]+):\s*(.*)$", m.group(1), re.M):
        fm[k] = v.strip().strip('"').strip("'")
    return fm, text[m.end():]


def first_heading(text: str) -> str:
    m = re.search(r"(?m)^#{1,3}\s+(.+)$", text)
    return m.group(1).strip() if m else ""


def first_paragraph(text: str, limit: int = 400) -> str:
    for block in re.split(r"\n\s*\n", text):
        b = block.strip()
        if b and not b.startswith(("#", "```", "|", "---", "<")):
            return re.sub(r"\s+", " ", b)[:limit]
    return ""


def code_summary(text: str) -> str:
    m = re.match(r'\s*(?:#![^\n]*\n)?\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', text, re.S)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()[:300]
    lines = []
    for ln in text.splitlines()[:25]:
        s = ln.strip()
        if s.startswith("#!"):
            continue
        if s.startswith(("#", "//", "*", "/*")):
            s = s.lstrip("#/* ").strip()
            if s:
                lines.append(s)
        elif s and lines:
            break
    return " ".join(lines)[:300]


def files_of(d: Path) -> list[Path]:
    out = []
    for dp, dn, fn in os.walk(d):
        dn[:] = sorted(x for x in dn if x not in SKIP_DIRS)
        for n in sorted(fn):
            if n.endswith((".pyc", ".pyo")) or n == ".DS_Store":
                continue
            out.append(Path(dp) / n)
    return out


def load_registry() -> list[dict]:
    reg = json.loads((ROOT / "addons" / "addons.json").read_text(encoding="utf-8"))
    return reg["addons"]


def check(verbose: bool = True) -> tuple[bool, str]:
    """Every file under addons/<id>/ is in the ledger with the same sha-256, and every addon has its skill unit."""
    con = sqlite3.connect(f"file:{(ROOT / 'kb' / 'alloy.db').as_posix()}?mode=ro", uri=True)
    led = {p: (s, pl) for p, s, pl in con.execute("SELECT path, sha256, place FROM ledger WHERE path LIKE 'addon:%'")}
    bad, n = [], 0
    reg = load_registry()
    for a in reg:
        d = ROOT / "addons" / a["id"]
        if not d.is_dir():
            bad.append(f"missing folder addons/{a['id']}")
            continue
        for f in files_of(d):
            n += 1
            rel = f.relative_to(d).as_posix()
            key = f"addon:{a['id']}/{rel}"
            got = led.pop(key, None)
            if not got or got[0] != sha(f.read_bytes()):
                bad.append(key)
        if not con.execute("SELECT 1 FROM units WHERE origin = ? AND kind = 'skill' LIMIT 1", (f"addon:{a['id']}",)).fetchone():
            bad.append(f"no skill unit for {a['id']}")
    bad += [f"stale ledger row {k}" for k in list(led)[:5]]
    detail = f"{len(reg)} addons, {n} files" + (f", problems: {bad[:5]}" if bad else "")
    return not bad, detail


def build() -> dict:
    kb = ROOT / "kb" / "alloy.db"
    con = sqlite3.connect(str(kb))
    con.execute("CREATE TABLE IF NOT EXISTS addon_fts(rowid INTEGER PRIMARY KEY, title TEXT, summary TEXT, body TEXT)")
    # 1) remove the previous addon rows exactly
    old = con.execute("SELECT rowid, title, summary, body FROM addon_fts").fetchall()
    for rid, t, s, b in old:
        con.execute("INSERT INTO fts(fts, rowid, title, summary, body) VALUES('delete', ?, ?, ?, ?)", (rid, t, s, b))
        con.execute("DELETE FROM units WHERE rowid = ?", (rid,))
    con.execute("DELETE FROM addon_fts")
    con.execute("DELETE FROM ledger WHERE path LIKE 'addon:%'")
    existing = {r[0] for r in con.execute("SELECT id FROM units")}

    def add_unit(uid: str, kind: str, title: str, summary: str, body: str, path: str, how: str, lic: str,
                 origin: str, meta: dict, extra: str = "") -> str:
        if uid in existing:
            uid = f"{uid}@addons"
        n = 2
        base = uid
        while uid in existing:
            uid = f"{base}{n}"
            n += 1
        existing.add(uid)
        cur = con.execute("INSERT INTO units VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                          (uid, kind, title, summary, zlib.compress(body.encode("utf-8"), 9) if body else None, path,
                           json.dumps([{"path": path, "sha": sha(body.encode('utf-8'))[:16]}], ensure_ascii=False),
                           how, lic, "active", origin, json.dumps(meta, ensure_ascii=False)))
        heads = " ".join(re.findall(r"(?m)^#{1,4}\s+(.+)$", body))[:4000]
        vals = (norm(f"{title} {uid.split(':', 1)[-1].replace('-', ' ')}"), norm(f"{summary} {extra}"), norm(f"{body[:8000]} {heads} {extra}"))
        con.execute("INSERT INTO fts(rowid, title, summary, body) VALUES (?,?,?,?)", (cur.lastrowid, *vals))
        con.execute("INSERT INTO addon_fts VALUES (?,?,?,?)", (cur.lastrowid, *vals))
        return uid

    stats = {"addons": 0, "files": 0, "skills": 0, "references": 0, "scripts": 0}
    for a in load_registry():
        aid = a["id"]
        d = ROOT / "addons" / aid
        origin = f"addon:{aid}"
        lic = a.get("license", "")
        meta = {"added": a.get("added"), "source": a.get("source"), "private_only": a.get("private_only", False)}
        stats["addons"] += 1
        for f in files_of(d):
            rel = f.relative_to(d).as_posix()
            place = f"addons/{aid}/{rel}"
            b = f.read_bytes()
            uid = None
            if f.suffix.lower() == ".md":
                text = b.decode("utf-8", "replace")
                fm, body = frontmatter(text)
                if f.name == "SKILL.md":
                    name = (fm.get("name") or f.parent.name).strip().lower()
                    is_root = f.parent == d
                    uid = add_unit(f"skill:{name}", "skill", fm.get("name") or name, fm.get("description") or first_paragraph(body),
                                   text, place, f"اقرا {place}", lic, origin,
                                   meta | {"addon_root": is_root}, a.get("triggers", "") if is_root else "")
                    stats["skills"] += 1
                else:
                    uid = add_unit(f"doc:{place}", "reference", first_heading(body) or f.name, first_paragraph(body),
                                   text, place, f"اقرا {place}", lic, origin, meta)
                    stats["references"] += 1
            elif f.suffix.lower() in CODE_EXT and (set(Path(rel).parts[:-1]) & CODE_DIRS or "/" not in rel) \
                    and "vendor" not in Path(rel).parts and not f.name.endswith(".min.js") and len(b) < 400_000:
                text = b.decode("utf-8", "replace")
                uid = add_unit(f"script:{place}", "script", f"{aid}: {rel}", code_summary(text) or rel,
                               text[:20000], place, f"اقرا {place} الأول (كود مهارة مضافة)، وبعدين شغّله من مجلده",
                               lic, origin, meta)
                stats["scripts"] += 1
            con.execute("INSERT INTO ledger VALUES (?,?,?,?,?,?)",
                        (f"addon:{aid}/{rel}", sha(b), len(b), place, uid or "", f"addon {aid}"))
            stats["files"] += 1
    for k, v in {"alloy_version": alloy.VERSION, "addons": json.dumps(stats), "addons_built": time.strftime("%Y-%m-%d %H:%M")}.items():
        con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, str(v)))
    con.commit()
    con.execute("INSERT INTO fts(fts) VALUES ('optimize')")
    con.commit()
    con.execute("VACUUM")
    con.close()
    # 2) MANIFEST.json (same writer as the blend; runtime fields unchanged)
    import blend  # noqa: E402
    man = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
    blend.write_manifest(ROOT, {"source": man.get("source"), "runtime_files": man.get("runtime_files"),
                                "runtime_digest": man.get("runtime_digest")})
    man = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))  # a git checkout: keep .git/ out
    man["files"] = {k: v for k, v in man["files"].items() if not k.startswith(".git/") and k != ".git"}
    with open(ROOT / "MANIFEST.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="index addons/ into the alloy")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        ok, detail = check()
        print(("✓ " if ok else "✗ ") + detail)
        return 0 if ok else 1
    print("addons ->", build())
    ok, detail = check()
    print(("✓ " if ok else "✗ ") + detail)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
