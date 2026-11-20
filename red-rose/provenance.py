"""Independent source catalog: metadata only, no private source contents."""
from datetime import datetime, timezone

def register(db, repository, path, revision, license_id="unverified"):
    if not repository or not path or not revision:
        raise ValueError("repository, path and revision required")
    db.execute("""CREATE TABLE IF NOT EXISTS source_catalog (
        repository TEXT NOT NULL, path TEXT NOT NULL, revision TEXT NOT NULL,
        license_id TEXT NOT NULL, recorded_at TEXT NOT NULL,
        PRIMARY KEY(repository,path,revision))""")
    db.execute("INSERT OR REPLACE INTO source_catalog VALUES (?,?,?,?,?)",
        (repository,path,revision,license_id,datetime.now(timezone.utc).isoformat()))
    db.commit()

def list_sources(db):
    db.execute("""CREATE TABLE IF NOT EXISTS source_catalog (
        repository TEXT NOT NULL, path TEXT NOT NULL, revision TEXT NOT NULL,
        license_id TEXT NOT NULL, recorded_at TEXT NOT NULL,
        PRIMARY KEY(repository,path,revision))""")
    return [dict(zip(("repository","path","revision","license_id","recorded_at"), row))
            for row in db.execute("SELECT * FROM source_catalog ORDER BY repository,path")]
