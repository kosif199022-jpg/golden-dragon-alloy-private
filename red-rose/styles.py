"""Reusable named style recipes (metadata, not generated images)."""
import json
from datetime import datetime, timezone


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS styles (
        name TEXT PRIMARY KEY, recipe TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    db.commit()


def save(db, name, recipe):
    initialize(db)
    name = name.strip()
    if not name or len(name) > 120:
        raise ValueError('Style name must be 1..120 characters')
    if not isinstance(recipe, dict) or not recipe:
        raise ValueError('Style recipe must be a nonempty JSON object')
    db.execute('INSERT INTO styles(name,recipe,updated_at) VALUES(?,?,?) '
               'ON CONFLICT(name) DO UPDATE SET recipe=excluded.recipe,updated_at=excluded.updated_at',
               (name, json.dumps(recipe, ensure_ascii=False, sort_keys=True),
                datetime.now(timezone.utc).isoformat()))
    db.commit()
    return {'saved': True, 'name': name}


def load(db, name):
    initialize(db)
    row = db.execute('SELECT recipe FROM styles WHERE name=?', (name,)).fetchone()
    return {'name': name, 'recipe': json.loads(row[0])} if row else None


def list_styles(db):
    initialize(db)
    return [r[0] for r in db.execute('SELECT name FROM styles ORDER BY name')]
