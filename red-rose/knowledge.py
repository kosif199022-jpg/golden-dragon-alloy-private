# Red Rose knowledge ingestion extension
# Independent module: never invokes legacy skills.
from pathlib import Path
from datetime import datetime, timezone
import hashlib

def ingest(db, directory):
    root = Path(directory).resolve()
    imported = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".py", ".json", ".yaml", ".yml"}:
            continue
        if any(x in {".git", "node_modules", ".venv"} for x in path.parts):
            continue
        if path.stat().st_size > 2_000_000:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        db.execute("CREATE TABLE IF NOT EXISTS knowledge (id INTEGER PRIMARY KEY, source TEXT, sha256 TEXT UNIQUE, content TEXT, imported TEXT)")
        cur = db.execute("INSERT OR IGNORE INTO knowledge(source,sha256,content,imported) VALUES (?,?,?,?)",
            (str(path.relative_to(root)),sha,content,datetime.now(timezone.utc).isoformat()))
        imported += cur.rowcount
    db.commit()
    return imported
