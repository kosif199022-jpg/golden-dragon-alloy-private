"""Package distilled Golden Dragon knowledge into one self-contained SQLite file.

Preserves active instructions and quarantined entries with their original JSON.
Never executes source instructions and never deletes source skills.
"""
import argparse
import json
import sqlite3
from pathlib import Path

def build(source, destination):
    brain = json.loads(Path(source).read_text(encoding="utf-8-sig"))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError("Refusing to overwrite an existing brain bundle")
    con = sqlite3.connect(destination)
    try:
        con.execute("CREATE TABLE knowledge (id INTEGER PRIMARY KEY, status TEXT NOT NULL, text TEXT NOT NULL, payload TEXT NOT NULL)")
        con.execute("CREATE INDEX knowledge_status ON knowledge(status)")
        try:
            con.execute("CREATE VIRTUAL TABLE knowledge_fts USING fts5(text, content='knowledge', content_rowid='id')")
            fts = True
        except sqlite3.OperationalError:
            fts = False
        counts = {}
        for status, key in [("active", "instructions"), ("quality_review", "quality_quarantine"), ("conflict_review", "requires_review")]:
            items = brain.get(key, [])
            counts[status] = len(items)
            for entry in items:
                obj = entry.get("instruction", entry) if isinstance(entry, dict) else entry
                value = obj.get("text", "") if isinstance(obj, dict) else ""
                con.execute("INSERT INTO knowledge(status,text,payload) VALUES (?,?,?)",
                            (status, value, json.dumps(entry, ensure_ascii=False)))
        if fts:
            con.execute("INSERT INTO knowledge_fts(knowledge_fts) VALUES ('rebuild')")
        con.execute("CREATE TABLE manifest (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        con.execute("INSERT INTO manifest VALUES (?,?)", ("counts", json.dumps(counts)))
        con.execute("INSERT INTO manifest VALUES (?,?)", ("fts5", json.dumps(fts)))
        con.commit()
        return {"counts": counts, "total": sum(counts.values()), "fts5": fts, "path": str(destination)}
    except BaseException:
        con.close()
        destination.unlink(missing_ok=True)
        raise
    finally:
        con.close()

def query(database, phrase, limit=5, include_review=False):
    con = sqlite3.connect(database)
    try:
        has_fts = json.loads(con.execute("SELECT value FROM manifest WHERE key='fts5'").fetchone()[0])
        if has_fts:
            terms = [w.replace('"', '') for w in phrase.split() if w.strip('"')]
            if not terms:
                return []
            match = " OR ".join('"' + term + '"' for term in terms)
            sql = ("SELECT k.status,k.text,k.payload FROM knowledge_fts f JOIN knowledge k ON k.id=f.rowid "
                   "WHERE knowledge_fts MATCH ? " + ("" if include_review else "AND k.status='active' ") +
                   "ORDER BY bm25(knowledge_fts) LIMIT ?")
            rows = con.execute(sql, (match, limit)).fetchall()
        else:
            sql = "SELECT status,text,payload FROM knowledge WHERE instr(lower(text),lower(?))>0 "
            if not include_review:
                sql += "AND status='active' "
            rows = con.execute(sql + "LIMIT ?", (phrase, limit)).fetchall()
        return [{"status": status, "text": text, "record": json.loads(payload)} for status, text, payload in rows]
    finally:
        con.close()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action", required=True)
    b = sub.add_parser("build")
    b.add_argument("brain")
    b.add_argument("output")
    q = sub.add_parser("query")
    q.add_argument("database")
    q.add_argument("phrase")
    q.add_argument("--limit", type=int, default=5)
    q.add_argument("--include-review", action="store_true")
    a = p.parse_args()
    result = build(a.brain, a.output) if a.action == "build" else query(a.database, a.phrase, max(1, min(a.limit, 100)), a.include_review)
    print(json.dumps(result, ensure_ascii=True))
