"""Unified catalog: every SKILL.md, runnable tool, power and superpower from all sources in one SQLite FTS5 file.

Sources are data (data/sources.json), not code. Re-run `python -m dragon build` after adding a repo or skill.
"""
import json, os, re, sqlite3, time
from pathlib import Path
from .arabic import tokens

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "catalog.sqlite"
HOME = Path.home()

DEFAULT_SOURCES = {
    "skill_roots": [
        {"source": "kosif-tool", "path": "~/kosif-own/kosif-tool/.claude/skills", "depth": 3},
        {"source": "100-superskills", "path": "~/kosif-own/100-superskills", "depth": 4},
        {"source": "kosif-atlas", "path": "~/kosif-own/kosif-atlas", "depth": 6},
        {"source": "fastify-motion-bro", "path": "~/kosif-own/fastify-motion-bro", "depth": 4},
        {"source": "installed", "path": "~/.claude/skills", "depth": 2},
        {"source": "dragon-repos", "path": "~/dragon-repos", "depth": 6},
    ],
    "tools_json": "~/kosif-own/kosif-tool/.claude/skills/kosif-superpowers/data/tools.json",
    "micro_index": "~/kosif-own/kosif-tool/.claude/skills/kosif-superpowers/data/micro_index.json",
}
SKIP_DIRS = {".git", "node_modules", "__pycache__", "vendor", "dist", "build"}
FRONT = re.compile(r"^---\s*\n(.*?)\n---", re.S)


def _p(s):
    return Path(os.path.expanduser(s))


def _fresh_kosif_tool(src):
    """v10.13: point ~/kosif-own/kosif-tool entries at the freshest kosif-tool checkout (e.g. ~/kosif-tool).
    No-op when only one checkout exists or the configured one is already the freshest."""
    try:
        from .superpowers import pick, repo_of
        best = pick()
    except Exception:
        return src
    if best is None:
        return src
    old = "~/kosif-own/kosif-tool"
    new = repo_of(best)
    if os.path.normcase(str(new)) == os.path.normcase(str(_p(old))):
        return src
    fix = lambda s: (new.as_posix() + s[len(old):]) if isinstance(s, str) and s.startswith(old) else s
    out = dict(src)
    out["skill_roots"] = [dict(r, path=fix(r.get("path"))) for r in src.get("skill_roots", [])]
    for k in ("tools_json", "micro_index"):
        if k in out:
            out[k] = fix(out[k])
    return out


def load_sources():
    f = DATA / "sources.json"
    if f.exists():
        return _fresh_kosif_tool(json.loads(f.read_text(encoding="utf-8-sig")))  # tolerate a BOM from Windows editors
    DATA.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(DEFAULT_SOURCES, ensure_ascii=False, indent=1), encoding="utf-8")
    return _fresh_kosif_tool(DEFAULT_SOURCES)


def parse_frontmatter(text):
    """name + description from a SKILL.md header (handles folded `>-` and quoted values)."""
    m = FRONT.match(text)
    if not m:
        return None, ""
    body = m.group(1)
    name = re.search(r"^name:\s*(.+)$", body, re.M)
    desc = re.search(r"^description:\s*(?:>-?|\|-?)?\s*(.*?)(?=^\w[\w-]*:\s|\Z)", body, re.M | re.S)
    clean = lambda s: re.sub(r"\s+", " ", s).strip().strip('"').strip("'")
    return (clean(name.group(1)) if name else None), (clean(desc.group(1)) if desc else "")


def walk_skills(root: Path, depth: int):
    """Yield SKILL.md paths without descending into heavy folders (fast on 70k-file mirrors)."""
    stack = [(root, 0)]
    while stack:
        d, lvl = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            if e.is_file() and e.name == "SKILL.md":
                yield Path(e.path)
            elif e.is_dir() and lvl < depth and e.name not in SKIP_DIRS and not e.name.startswith("."):
                stack.append((Path(e.path), lvl + 1))
            elif e.is_dir() and e.name == ".claude" and lvl < depth:
                stack.append((Path(e.path), lvl + 1))


SCHEMA = """
CREATE TABLE items(id TEXT PRIMARY KEY, kind TEXT, source TEXT, name TEXT, title_ar TEXT, title_en TEXT,
                   summary TEXT, path TEXT, status TEXT, command TEXT, requires TEXT, extra TEXT);
CREATE VIRTUAL TABLE items_fts USING fts5(id UNINDEXED, name, body, tokenize='unicode61 remove_diacritics 2');
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
"""


def build(db_path: Path = DB, sources=None, log=print, own=None):
    own = (sources is None) if own is None else own   # fixtures stay pure; the real build adds the dragon's own tools
    sources = sources or load_sources()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    counts, t0 = {}, time.time()

    def add(row, search_text):
        try:
            con.execute("INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", row)
        except sqlite3.IntegrityError:
            return False
        con.execute("INSERT INTO items_fts VALUES(?,?,?)", (row[0], " ".join(tokens(row[3] or "", False)),
                                                           " ".join(tokens(search_text, False))))
        counts[row[1] + ":" + row[2]] = counts.get(row[1] + ":" + row[2], 0) + 1
        return True

    # 1) skills from every root
    for r in sources["skill_roots"]:
        root = _p(r["path"])
        if not root.exists():
            log(f"  skip missing root {root}")
            continue
        for sk in walk_skills(root, r.get("depth", 4)):
            try:
                with open(sk, encoding="utf-8", errors="ignore") as fh:
                    head = fh.read(6000)
            except OSError:
                continue
            name, desc = parse_frontmatter(head)
            name = name or sk.parent.name
            rel = sk.parent.relative_to(root).as_posix()
            add((f"skill:{r['source']}:{rel}", "skill", r["source"], name, "", "", desc[:2000], str(sk), "", "", "", ""),
                f"{name} {sk.parent.name} {desc}")
    # 2) runnable tools (with their commands)
    tj = _p(sources["tools_json"])
    if tj.exists():
        base = tj.parent.parent
        for t in json.loads(tj.read_text(encoding="utf-8"))["tools"]:
            cmds = t.get("commands") or t.get("examples") or []
            cmd = cmds[0] if isinstance(cmds, list) and cmds else (cmds if isinstance(cmds, str) else "")
            if isinstance(cmd, dict):
                cmd = cmd.get("example") or cmd.get("cmd") or cmd.get("command") or json.dumps(cmd, ensure_ascii=False)
            text = " ".join(str(x) for x in [t.get("id"), t.get("title_en"), t.get("title_ar"), t.get("summary_en"),
                                             t.get("summary_ar"), " ".join(t.get("use_when", [])), t.get("area")])
            add((f"tool:{t['id']}", "tool", "superpowers", t["id"], t.get("title_ar", ""), t.get("title_en", ""),
                 t.get("summary_ar") or t.get("summary_en", ""), str(base / t.get("path", "")), t.get("status", ""),
                 str(cmd), json.dumps(t.get("requires", []), ensure_ascii=False), t.get("area", "")), text)
    # 3) powers + superpowers
    mj = _p(sources["micro_index"])
    if mj.exists():
        m = json.loads(mj.read_text(encoding="utf-8"))
        for p in m.get("powers", []):
            text = " ".join(str(x) for x in [p["id"], p.get("name_en"), p.get("name_ar"), p.get("what"),
                                             " ".join(p.get("tags", [])), p.get("family"), p.get("group")])
            add((f"power:{p['id']}", "power", "superpowers", p["id"], p.get("name_ar", ""), p.get("name_en", ""),
                 p.get("what", ""), p.get("family", ""), p.get("status", ""), "",
                 json.dumps(p.get("requires", []), ensure_ascii=False), p.get("group", "")), text)
        for s in m.get("superpowers", []):
            text = " ".join(str(x) for x in [s["id"], s.get("name_en"), s.get("name_ar"), " ".join(s.get("focus", [])),
                                             s.get("family"), s.get("domain")])
            add((f"superpower:{s['id']}", "superpower", "superpowers", s["id"], s.get("name_ar", ""), s.get("name_en", ""),
                 f"{s.get('size', 0)} members, best={s.get('best', '')}", s.get("family", ""), s.get("best", ""), "",
                 "", json.dumps(s.get("members", [])[:40])), text)
    # 4) the dragon's own engines, bundled tools and local programs (data/own_tools.json)
    if own:
        counts.update(register_own(con))
    con.execute("INSERT INTO meta VALUES('built', ?)", (time.strftime("%Y-%m-%d %H:%M:%S"),))
    con.execute("INSERT INTO meta VALUES('counts', ?)", (json.dumps(counts),))
    con.commit()
    con.close()
    if db_path.exists():
        db_path.unlink()
    tmp.rename(db_path)
    log(f"catalog: {sum(counts.values())} items in {time.time() - t0:.1f}s -> {db_path}")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        log(f"  {k:32} {v}")
    return counts


def register_own(con=None, path=None):
    """Upsert data/own_tools.json as kind=tool, source=black-dragon (idempotent; works without the other repos)."""
    path = Path(path or Path(__file__).resolve().parent.parent / "data" / "own_tools.json")
    own = json.loads(path.read_text(encoding="utf-8"))["tools"]
    close = con is None
    con = con or sqlite3.connect(DB)
    for t in own:
        iid = f"tool:black-dragon:{t['id']}"
        con.execute("DELETE FROM items WHERE id = ?", (iid,))
        con.execute("DELETE FROM items_fts WHERE id = ?", (iid,))
        con.execute("INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (iid, "tool", "black-dragon", t["id"], t["ar"], t["en"], t["what"], "", "registered", t["cmd"], "", "own"))
        con.execute("INSERT INTO items_fts VALUES(?,?,?)", (iid, " ".join(tokens(t["id"].replace("-", " ") + " " + t["en"], False)),
                    " ".join(tokens(" ".join([t["ar"], t["en"], t["what"]]), False))))
    row = con.execute("SELECT value FROM meta WHERE key='counts'").fetchone()
    if row:
        c = json.loads(row[0]); c["tool:black-dragon"] = len(own)
        con.execute("UPDATE meta SET value=? WHERE key='counts'", (json.dumps(c),))
    if close:
        con.commit(); con.close()
    return {"tool:black-dragon": len(own)}


def connect(db_path: Path = DB):
    if not db_path.exists():
        raise SystemExit("catalog not built yet: python -m dragon build")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con
