"""V69 supplementary source intake: owner-approved archives -> append-only local FTS5 index.

Reads text documents only (md/txt/markdown, one nested level of .zip/.skill). Never extracts to disk,
never executes anything, skips binaries/executables, keeps secret-like and instruction-hijack chunks out of
search. Retrieved text is untrusted reference data, not instructions. Does not touch the V66/V67 indexes.
"""
from __future__ import annotations
from pathlib import Path, PurePosixPath
from contextlib import closing
import hashlib, io, json, re, sqlite3, time, zipfile

HOME = Path.home() / ".red-rose"
DB = HOME / "intake-v69" / "intake.sqlite3"
TEXT_EXT = {".md", ".markdown", ".txt"}
NESTED_EXT = {".zip", ".skill"}
MAX_DOC = 2 * 1024 ** 2
MAX_NESTED = 25 * 1024 ** 2
MAX_ENTRIES = 20000
CHUNK = 1200
SECRET = re.compile(r"(?i)(?:api[_ -]?key|access[_ -]?token|password|secret|cookie|authorization)\s*[:=]\s*\S{6,}"
                    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|sk-(?:proj-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}")
HIJACK = re.compile(r"(?i)ignore (?:all |any )?(?:previous|prior) instructions|disregard (?:the )?system prompt|you are now (?:in )?developer mode|jailbreak")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
LABEL = re.compile(r"[a-z0-9][a-z0-9._-]{2,80}")


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p) -> str:
    with Path(p).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _connect(path, create=False):
    path = Path(path)
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=10)
        db.execute("CREATE TABLE IF NOT EXISTS archives(label TEXT PRIMARY KEY, sha256 TEXT UNIQUE, path TEXT, origin TEXT,"
                   " added_at TEXT, receipt TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS docs(sha256 TEXT, label TEXT, entry TEXT, bytes INTEGER, PRIMARY KEY(label, entry))")
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(doc UNINDEXED, label UNINDEXED, entry, section, body,"
                   " line UNINDEXED, tokenize='unicode61 remove_diacritics 2')")
        return db
    return sqlite3.connect(path.resolve(strict=True).as_uri() + "?mode=ro", uri=True, timeout=10)


def _safe_entry(name: str) -> bool:
    p = PurePosixPath(name.replace("\\", "/"))
    return not p.is_absolute() and ".." not in p.parts and not name.endswith("/")


def iter_text_docs(zf: zipfile.ZipFile, prefix="", depth=0, counter=None):
    """Yield (entry_path, bytes) for text docs; descend one level into nested zip/.skill in memory."""
    counter = counter if counter is not None else [0]
    for info in zf.infolist():
        counter[0] += 1
        if counter[0] > MAX_ENTRIES:
            raise ValueError("too many entries")
        if info.is_dir() or info.flag_bits & 1 or not _safe_entry(info.filename):
            continue
        name = info.filename.replace("\\", "/")
        ext = PurePosixPath(name).suffix.lower()
        if ext in TEXT_EXT and info.file_size <= MAX_DOC:
            yield prefix + name, zf.read(info)
        elif ext in NESTED_EXT and depth == 0 and info.file_size <= MAX_NESTED:
            try:
                with zipfile.ZipFile(io.BytesIO(zf.read(info))) as inner:
                    yield from iter_text_docs(inner, prefix + name + "!/", depth + 1, counter)
            except zipfile.BadZipFile:
                continue


def chunks_of(text: str):
    """Split markdown/plain text by headings into bounded chunks: (section, first_line, body)."""
    section, start, buf, size = "", 1, [], 0
    for i, line in enumerate(text.splitlines(), 1):
        m = HEADING.match(line)
        if m or size + len(line) > CHUNK:
            if buf:
                yield section, start, "\n".join(buf)
            buf, size, start = [], 0, i
            if m:
                section = m.group(1)[:160]
                continue
        if line.strip():
            buf.append(line.strip()[:CHUNK])
            size += len(line)
    if buf:
        yield section, start, "\n".join(buf)


def add(archive, label, origin="", approved=False, path=DB):
    if not approved:
        raise PermissionError("explicit write approval required")
    if not isinstance(label, str) or not LABEL.fullmatch(label):
        raise ValueError("label must be lowercase a-z0-9._- (3-81 chars)")
    archive = Path(archive).resolve(strict=True)
    digest = sha_file(archive)
    stats = {"docs": 0, "duplicate_docs": 0, "chunks": 0, "skipped_secret": 0, "skipped_hijack": 0, "undecodable": 0}
    with closing(_connect(path, create=True)) as db:
        if db.execute("SELECT 1 FROM archives WHERE label=? OR sha256=?", (label, digest)).fetchone():
            raise FileExistsError("archive or label already indexed; intake is append-only")
        seen = {r[0] for r in db.execute("SELECT sha256 FROM docs")}
        try:
            with zipfile.ZipFile(archive) as zf:
                for entry, raw in iter_text_docs(zf):
                    d = sha_bytes(raw)
                    db.execute("INSERT INTO docs VALUES(?,?,?,?)", (d, label, entry, len(raw)))
                    if d in seen:
                        stats["duplicate_docs"] += 1
                        continue
                    seen.add(d)
                    try:
                        text = raw.decode("utf-8-sig")
                    except UnicodeDecodeError:
                        stats["undecodable"] += 1
                        continue
                    stats["docs"] += 1
                    for section, line, body in chunks_of(text):
                        if SECRET.search(body):
                            stats["skipped_secret"] += 1
                            continue
                        if HIJACK.search(body):
                            stats["skipped_hijack"] += 1
                            continue
                        db.execute("INSERT INTO chunks VALUES(?,?,?,?,?,?)", (d, label, entry, section, body, line))
                        stats["chunks"] += 1
            if sha_file(archive) != digest:
                raise ValueError("archive changed during intake")
            receipt = {"label": label, "archive_sha256": digest, "origin": origin[:300], **stats,
                       "method": "text-only FTS5 BM25 lexical index; not semantic review", "semantic_reviewed": False,
                       "external_scripts_executed": False, "native_capabilities_added": 0}
            db.execute("INSERT INTO archives VALUES(?,?,?,?,?,?)",
                       (label, digest, str(archive), origin[:300], time.strftime("%Y-%m-%dT%H:%M:%S%z"), json.dumps(receipt)))
            db.commit()
        except Exception:
            db.rollback()
            raise
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("index integrity error")
    return receipt


def status(path=DB):
    if not Path(path).is_file():
        return {"index_ready": False, "archives": []}
    with closing(_connect(path)) as db:
        arch = [json.loads(r[0]) for r in db.execute("SELECT receipt FROM archives ORDER BY added_at")]
        n = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
    return {"index_ready": True, "archives": arch, "chunks": n}


def _terms(q):
    if not isinstance(q, str) or not q.strip() or len(q) > 500:
        raise ValueError("invalid query")
    return list(dict.fromkeys(re.findall(r"[^\W_]{2,40}", q.casefold())))[:12]


def search(query, limit=8, path=DB, label=None):
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError("limit")
    tok = _terms(query)
    if not Path(path).is_file() or not tok:
        return {"index_ready": Path(path).is_file(), "matches": []}
    rows, seen = [], set()
    with closing(_connect(path)) as db:
        for op in (" AND ", " OR "):
            match = op.join('"' + t + '"' for t in tok)
            sql = ("SELECT doc,label,entry,section,line,snippet(chunks,4,'[',']',' … ',24),bm25(chunks,0,0,3,4,1,0)"
                   " FROM chunks WHERE chunks MATCH ?" + (" AND label=?" if label else "") +
                   " ORDER BY bm25(chunks,0,0,3,4,1,0) LIMIT ?")
            args = (match, label, limit * 3) if label else (match, limit * 3)
            for r in db.execute(sql, args):
                key = (r[0], r[4])
                if key in seen or sum(1 for x in rows if x[0] == r[0]) >= 2:  # at most 2 chunks per document
                    continue
                seen.add(key)
                rows.append(r)
                if len(rows) >= limit:
                    break
            if len(rows) >= limit or len(tok) == 1:
                break
    return {"index_ready": True, "execution_allowed": False, "ranking": "lexical; relevance not guaranteed",
            "matches": [{"rank": i + 1, "sha256": d, "label": lb, "entry": e, "section": s, "line": ln,
                         "snippet": sn[:300], "status": "unreviewed_reference", "instruction_authority": False}
                        for i, (d, lb, e, s, ln, sn, _) in enumerate(rows)]}


def inspect(doc_sha, line=1, window=40, path=DB):
    if not isinstance(doc_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", doc_sha):
        raise ValueError("invalid digest")
    if type(line) is not int or line < 1 or type(window) is not int or not 1 <= window <= 200:
        raise ValueError("invalid window")
    with closing(_connect(path)) as db:
        row = db.execute("SELECT d.label,d.entry,a.path,a.sha256 FROM docs d JOIN archives a ON a.label=d.label"
                         " WHERE d.sha256=? LIMIT 1", (doc_sha,)).fetchone()
    if not row:
        raise ValueError("unknown document")
    label, entry, apath, asha = row
    if sha_file(apath) != asha:
        raise ValueError("source archive changed since intake; re-review before use")
    outer, _, inner = entry.partition("!/")
    with zipfile.ZipFile(apath) as zf:
        raw = zf.read(_find(zf, outer))
        if inner:
            with zipfile.ZipFile(io.BytesIO(raw)) as nz:
                raw = nz.read(_find(nz, inner))
    if sha_bytes(raw) != doc_sha:
        raise ValueError("document digest mismatch")
    lines = raw.decode("utf-8-sig", errors="replace").splitlines()
    lo = max(0, line - 1)
    return {"label": label, "entry": entry, "sha256": doc_sha, "verified": True, "from_line": lo + 1,
            "text": "\n".join(lines[lo:lo + window]), "total_lines": len(lines),
            "status": "unreviewed_reference", "instruction_authority": False}


def _find(zf, name):
    for info in zf.infolist():
        if info.filename.replace("\\", "/") == name:
            return info
    raise ValueError("entry missing from archive")


def handle(a):
    try:
        if a.action == "status":
            r = status()
        elif a.action == "add":
            r = add(a.source, a.label, a.origin or "", a.approve_write)
        elif a.action == "search":
            r = search(a.source, a.limit, label=a.label)
        else:
            r = inspect(a.source, a.line, a.window)
        print(json.dumps(r, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error, zipfile.BadZipFile, PermissionError) as e:
        print(json.dumps({"error": str(e)[:300]}))
        return 1


def register(sub):
    p = sub.add_parser("intake", help="V69 owner-approved supplementary source index (text only, append-only)")
    p.add_argument("action", choices=["status", "add", "search", "inspect"])
    p.add_argument("source", nargs="?", default="")
    p.add_argument("--label")
    p.add_argument("--origin")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--line", type=int, default=1)
    p.add_argument("--window", type=int, default=40)
    p.add_argument("--approve-write", action="store_true")
    p.set_defaults(ext_func=handle)
