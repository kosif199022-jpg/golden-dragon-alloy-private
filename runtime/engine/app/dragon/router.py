"""Route a request (Arabic, Egyptian or English) to the best skills, tools, powers and superpowers."""
import json
from functools import lru_cache
from pathlib import Path
from .arabic import normalize, tokens
from .catalog import connect

KIND_ORDER = ("tool", "skill", "superpower", "power")


@lru_cache(maxsize=1)
def _synonyms():
    """Arabic app/craft words -> English terms, so «بلندر» finds Blender skills (data/synonyms.json)."""
    p = Path(__file__).resolve().parent.parent / "data" / "synonyms.json"
    raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return {normalize(k): v for k, v in raw.items() if not k.startswith("_")}


def find(query: str, kinds=KIND_ORDER, limit: int = 6, con=None):
    """Return {kind: [rows]} ranked by BM25 (name matches weigh 4x the body)."""
    toks = tokens(query)
    toks += [e for t in toks for e in _synonyms().get(t, []) if e not in toks]
    if not toks:
        return {k: [] for k in kinds}
    # OR of prefix terms so Arabic inflections still match (e.g. مونتاج* hits مونتاجات)
    match = " OR ".join(f'"{t}"*' for t in toks)
    con = con or connect()
    out = {}
    for k in kinds:
        rows = con.execute(
            "SELECT i.*, bm25(items_fts, 0.0, 4.0, 1.0) AS score FROM items_fts JOIN items i ON i.id = items_fts.id "
            "WHERE items_fts MATCH ? AND i.kind = ? ORDER BY score LIMIT ?", (match, k, limit)).fetchall()
        out[k] = [dict(r) for r in rows]
    return out


def show(item_id: str, con=None):
    con = con or connect()
    r = con.execute("SELECT * FROM items WHERE id = ? OR name = ? LIMIT 1", (item_id, item_id)).fetchone()
    return dict(r) if r else None
