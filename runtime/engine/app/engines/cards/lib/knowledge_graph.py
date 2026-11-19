"""Helpers of power_programs/knowledge_graph.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from collections import Counter
from PIL import Image
from PIL import ImageDraw
from pathlib import Path
import ast
from collections import defaultdict
from collections import deque
import numpy as np
import re
from ._lang_common import words


def freshness_report(answer_meta, head, changed_files, query_files):
    stale = answer_meta["commit"] != head
    unindexed = sorted(set(query_files) & set(changed_files)) if stale else []
    rep = {"repo": answer_meta["repo"], "graph_source": "hosted", "indexed_at": answer_meta["indexed_at"],
           "indexed_commit": answer_meta["commit"], "head": head, "stale": stale,
           "nodes": answer_meta["nodes"], "edges": answer_meta["edges"]}
    if unindexed:
        rep["fallback"] = {"files": unindexed, "source": "local CLI or grep", "status": "GRAPHIFY_NOT_EXECUTED",
                           "next_step": "graphify extract --code-only on the working tree"}
    return rep


def import_graph(root: Path):
    edges = []
    for f in sorted(root.glob("*.py")):
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                edges.append((f.stem, node.module.split(".")[0]))
            elif isinstance(node, ast.Import):
                edges += [(f.stem, a.name.split(".")[0]) for a in node.names]
    local = {f.stem for f in root.glob("*.py")}
    return [(a, b) for a, b in edges if b in local]


def skill_index(root: Path):
    rows = []
    for sk in sorted(root.glob("*/SKILL.md")):
        text = sk.read_text()
        fm = re.match(r"---\n(.*?)\n---", text, re.S).group(1)
        meta = dict(l.split(": ", 1) for l in fm.splitlines() if ": " in l)
        rows.append({"name": meta["name"], "description": meta["description"], "lines": len(text.splitlines())})
    return rows


TRANSLATE = {"فيديو": "video", "ترجمة": "caption", "قص": "cut", "صوت": "audio"}


def expand(question, labels, cap=12):
    vocab = Counter(t for l in labels for t in re.split(r"[_\W]+", l.lower()) if len(t) > 2)
    out = []
    for w in words(question):
        cands = [w, TRANSLATE.get(w)]
        for c in cands:
            if c and c in vocab and c not in out:
                out.append(c)
    return out[:cap]


def traversal_for(q):
    q = q.lower()
    if "break" in q or "affected" in q:
        return "affected"
    if re.search(r"how does .* reach|how .* gets? to", q):
        return "DFS"
    if "related" in q:
        return "path"
    return "BFS"


STEPS = (0.95, 0.85, 0.75, 0.65, 0.55)


def label(edge):
    if edge.get("stated"):
        return ("EXTRACTED", None)
    c = edge["confidence"]
    if c < 0.55:
        return ("AMBIGUOUS", None)
    return ("INFERRED", min(STEPS, key=lambda s: (abs(s - c), -s)))


def force_layout(nodes, edges, seed=7, iters=200):
    rng = np.random.default_rng(seed)
    pos = rng.uniform(-1, 1, (len(nodes), 2))
    idx = {n: i for i, n in enumerate(nodes)}
    for _ in range(iters):
        d = pos[:, None, :] - pos[None, :, :]
        dist = np.linalg.norm(d, axis=2) + 1e-3
        rep = (d / dist[..., None] ** 3).sum(axis=1) * 0.01
        att = np.zeros_like(pos)
        for a, b in edges:
            i, j = idx[a], idx[b]
            v = pos[j] - pos[i]
            att[i] += v * 0.05
            att[j] -= v * 0.05
        pos += rep + att
        pos -= pos.mean(axis=0)
    return pos


def bfs_order(edges, start):
    adj = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    seen, q, order = {start}, deque([start]), []
    while q:
        n = q.popleft()
        for m in sorted(adj[n]):
            if m not in seen:
                seen.add(m)
                order.append((n, m))
                q.append(m)
    return order


def draw_frame(pos, nodes, order, t, size=96):
    im = Image.new("RGB", (size, size), (10, 10, 14))
    dr = ImageDraw.Draw(im)
    span = np.abs(pos).max() or 1
    xy = {n: tuple(((pos[i] / span) * 0.4 + 0.5) * size) for i, n in enumerate(nodes)}
    k = int(round(t * len(order)))
    for a, b in order[:k]:
        dr.line([xy[a], xy[b]], fill=(255, 200, 0), width=1)
    return im, k


REL = re.compile(r"(\b[A-Z][a-z]+\b) (founded|leads|acquired|partners with|funds) (\b[A-Z][a-z]+\b)")


def extract(chunks):
    ents, rels = {}, []
    for cid, text in chunks.items():
        for a, r, b in REL.findall(text):
            for e in (a, b):
                ents.setdefault(e.lower(), {"name": e, "chunks": set()})["chunks"].add(cid)
            rels.append((a.lower(), r, b.lower(), cid))
    return ents, rels


def modularity_communities(nodes, edges):
    """Greedy agglomerative modularity (Clauset-Newman-Moore style, small graphs)."""
    m = len(edges)
    deg = Counter()
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    comm = {n: {n} for n in nodes}

    def q(cs):
        tot = 0.0
        for c in cs:
            lc = sum(1 for a, b in edges if a in c and b in c)
            dc = sum(deg[n] for n in c)
            tot += lc / m - (dc / (2 * m)) ** 2
        return tot
    cur = list(comm.values())
    best = q(cur)
    while True:
        cand = None
        for i in range(len(cur)):
            for j in range(i + 1, len(cur)):
                if not any((a in cur[i] and b in cur[j]) or (a in cur[j] and b in cur[i]) for a, b in edges):
                    continue
                trial = [c for k, c in enumerate(cur) if k not in (i, j)] + [cur[i] | cur[j]]
                v = q(trial)
                if cand is None or v > cand[0]:
                    cand = (v, trial)
        if not cand or cand[0] <= best:
            return cur, best
        best, cur = cand
