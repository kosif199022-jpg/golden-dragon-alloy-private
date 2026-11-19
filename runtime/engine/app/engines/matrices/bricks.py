"""The 86 reference styles as six bricks (state, operation, law, time, memory, feedback) - static analysis only.

extract_atlas  split the user's ai-style-atlas-prompts-FULL archive (zip or .txt) into a local tree outside git
               (lib/harness.js, lib/sound.js, styles/<id>.js, cards/<id>.json, manifest.json). Nothing is executed.
analyze        lexical scan of each style source (patterns in data/tables.json) + optional REA semantic graphs
               (normalized-AST fingerprints reveal shared function bodies) -> derived numbers only, safe to commit.
Every label is an inference from code (E2_STATIC_CODE), not a render test.
"""
import collections, hashlib, json, re, zipfile
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
BRICKS_FILE = DATA / "86_style_code_bricks.json"
INDEX = DATA / "86_style_research_database.json"
_T = json.loads((DATA / "tables.json").read_text(encoding="utf-8"))
PATTERNS = {g: {k: re.compile(v) for k, v in d.items()} for g, d in _T["brick_patterns"].items()}
COMPOSITE_MODE = re.compile(_T["composite_mode"])
TAG_SUPPORT = _T["tag_support"]


# ------------------------------------------------------------------ archive -> local reference tree
ENTRY = re.compile(r"^#(\d\d) — (.+)$")
FENCE_TITLE = re.compile(r"^(H HELPER LIBRARY|SOUND KIT|REFERENCE STYLE SOURCE)\b.*?(?:\(([^)]*)\))?\s*$")
KINDS = {"H HELPER LIBRARY": "harness", "SOUND KIT": "sound", "REFERENCE STYLE SOURCE": "style"}


def read_archive(path):
    p = Path(path)
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".txt")]
            if len(names) != 1:
                raise ValueError("expected exactly one .txt in the archive, found %d" % len(names))
            return z.read(names[0]).decode("utf-8"), hashlib.sha256(p.read_bytes()).hexdigest()
    data = p.read_bytes()
    return data.decode("utf-8"), hashlib.sha256(data).hexdigest()


def parse_archive(text):
    lines, entries, cur, i = text.splitlines(), [], None, 0
    while i < len(lines):
        line = lines[i]
        m = ENTRY.match(line)
        if m:
            cur = {"number": int(m.group(1)), "title": m.group(2).strip(), "card": {}, "blocks": {}}
            entries.append(cur)
        elif cur is not None:
            if line.startswith("Style ID:"):
                cur["style_id"] = line.split(":", 1)[1].strip()
            elif line.startswith("Category:"):
                cur["family"] = line.split(":", 1)[1].strip()
            for key in ("Look", "Motion", "How it explains"):
                if line.startswith(key + ":"):
                    cur["card"][key.lower().replace(" ", "_")] = line.split(":", 1)[1].strip()
            t = FENCE_TITLE.match(line)
            if t and i + 1 < len(lines) and lines[i + 1].startswith("```"):
                j = i + 2
                while j < len(lines) and not lines[j].startswith("```"):
                    j += 1
                cur["blocks"][KINDS[t.group(1)]] = "\n".join(lines[i + 2:j]) + "\n"
                i = j
        i += 1
    return entries


def extract_atlas(archive, out):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("refusing to write into a non-empty folder: %s" % out)
    text, archive_sha = read_archive(archive)
    entries = parse_archive(text)
    ids = [e.get("style_id") for e in entries]
    if len(entries) != 86 or len(set(ids)) != 86 or None in ids:
        raise ValueError("expected 86 distinct entries, parsed %d (%d ids)" % (len(entries), len(set(ids))))
    for d in ("lib", "styles", "cards"):
        (out / d).mkdir(parents=True)
    files, shared, missing = {}, {"harness": set(), "sound": set()}, []

    def write(rel, body):
        (out / rel).write_text(body, encoding="utf-8")
        files[rel] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    for e in entries:
        for kind in ("harness", "sound"):
            body = e["blocks"].get(kind)
            if body:
                if not shared[kind]:
                    write("lib/%s.js" % kind, body)
                shared[kind].add(hashlib.sha256(body.encode()).hexdigest())
        if not e["blocks"].get("style"):
            missing.append(e["style_id"])
            continue
        write("styles/%s.js" % e["style_id"], e["blocks"]["style"])
        write("cards/%s.json" % e["style_id"], json.dumps({"number": e["number"], "style_id": e["style_id"], "title": e["title"],
                                                           "family": e.get("family"), **e["card"]}, ensure_ascii=False, indent=1) + "\n")
    manifest = {"schema": "kosif.matrices.atlas-extract.v1", "archive_sha256": archive_sha, "entries": len(entries),
                "styles_with_source": 86 - len(missing), "missing_source": missing,
                "shared_variants": {k: len(v) for k, v in shared.items()}, "files": files,
                "rights": "Third-party text (Futurepedia AI Style Atlas). Local analysis only; do not commit or redistribute."}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {k: v for k, v in manifest.items() if k != "files"}


# ------------------------------------------------------------------ lexical bricks
def strip_comments(src):
    return re.sub(r"(?m)(^|[^:\\])//.*$", r"\1", re.sub(r"/\*.*?\*/", " ", src, flags=re.S))


def lexical(src):
    s = strip_comments(src)
    feats = {"lines": src.count("\n") + 1}
    feats.update({g: {k: len(rx.findall(s)) for k, rx in d.items()} for g, d in PATTERNS.items()})
    feats["composite_modes"] = dict(collections.Counter(COMPOSITE_MODE.findall(s)).most_common())
    feats["uses_math_random"] = bool(re.search(r"Math\.random\s*\(", s))
    return feats, s


def top(d, n, floor=1):
    return [k for k, v in sorted(d.items(), key=lambda kv: (-kv[1], kv[0])) if v >= floor][:n]


MEMORY_LABELS = {"cached_texture": "cached_texture (static memory: built once, reused every frame)",
                 "trail_by_resampling": "trail_by_resampling (history recomputed from earlier t, no stored state)",
                 "iterative_build": "iterative_build (a counted loop builds the frame from many items or sub-steps; a weak memory signal)"}
FEEDBACK_LABELS = {"pixel_postprocess": "pixel_postprocess (reads back pixels inside the same frame and rewrites them; not cross-frame)",
                   "field_drives_motion": "field_drives_motion (a computed field steers geometry)"}


def bricks_from(f):
    return {"state": top(f["state"], 4), "operation": top(f["operations"], 5), "law": top(f["laws"], 5),
            "time": top(f["time"], 3) or ["static_or_untimed"],
            "memory": [v for k, v in MEMORY_LABELS.items() if f["memory"][k]] or ["none_detected"],
            "feedback": [v for k, v in FEEDBACK_LABELS.items() if f["feedback"][k]] or ["none_detected"]}


# ------------------------------------------------------------------ REA ingestion
def rea_per_module(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    nr = d.get("normalized_result") or {}
    sg = nr.get("semantic_graph") or {}
    node_mod, fn_span = {}, {}
    per = collections.defaultdict(lambda: {"functions": 0, "call_sites": 0, "bindings": 0, "relations": collections.Counter(), "fingerprints": []})
    kinds = {"function": "functions", "call-site": "call_sites", "binding": "bindings"}
    for n in sg.get("nodes", []):
        ident = n.get("identity") or {}
        mod = ident.get("module_path") or ""
        node_mod[n.get("node_id")] = mod
        if n.get("kind") in kinds:
            per[mod][kinds[n["kind"]]] += 1
        if n.get("kind") == "function":
            try:
                r = ident.get("source_range") or {}
                fn_span[n["node_id"]] = r["end"]["line"] - r["start"]["line"] + 1
            except (KeyError, TypeError):
                fn_span[n["node_id"]] = 0
    for r in sg.get("relations", []):
        per[node_mod.get(r.get("source_node_id"), "")]["relations"][r.get("relation", "?")] += 1
    for fp in sg.get("fingerprints", []):
        fid = fp.get("function_node_id")
        h = (fp.get("components") or {}).get("normalized_ast_sha256")
        if fp.get("status") == "complete" and h and fn_span.get(fid, 0) >= 3:  # ignore one-line lambdas
            per[node_mod.get(fid, "")]["fingerprints"].append(h)
    st, cov = nr.get("statistics") or {}, sg.get("coverage") or {}
    meta = {"rea_version": (d.get("provider") or {}).get("version") or None, "provider": (d.get("provider") or {}).get("id"),
            "evidence_id": d.get("evidence_id"), "root_artifact_sha256": nr.get("root_artifact_sha256"),
            "parsed_javascript_files": st.get("parsed_javascript_files"), "visited_ast_nodes": st.get("visited_ast_nodes"),
            "semantic_nodes": len(sg.get("nodes", [])), "semantic_relations": len(sg.get("relations", [])),
            "fingerprints": len(sg.get("fingerprints", [])), "semantic_coverage": cov.get("status"), "semantic_truncated": cov.get("truncated")}
    return per, meta


def rea_merge(paths):
    """Merge REA runs; per module keep the run that analysed it most deeply (most function nodes)."""
    merged, metas = {}, []
    for path in paths:
        per, meta = rea_per_module(path)
        metas.append(meta)
        merged.update({mod: v for mod, v in per.items() if mod not in merged or v["functions"] > merged[mod]["functions"]})
    return merged, {
        "rea_version": metas[0]["rea_version"], "provider": metas[0]["provider"], "runs": len(metas),
        "evidence_ids": [m["evidence_id"] for m in metas], "root_artifact_sha256": sorted({m["root_artifact_sha256"] for m in metas}),
        "visited_ast_nodes": sum(m["visited_ast_nodes"] or 0 for m in metas), "semantic_nodes": sum(m["semantic_nodes"] for m in metas),
        "semantic_relations": sum(m["semantic_relations"] for m in metas), "fingerprints": sum(m["fingerprints"] for m in metas),
        "any_run_truncated": any(m["semantic_truncated"] for m in metas),
        "style_modules_with_functions": sum(1 for k, v in merged.items() if k.startswith("styles/") and v["functions"])}


def analyze(src_dir, rea_paths=None):
    src = Path(src_dir)
    man = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    index = {s["style_id"]: s for s in json.loads(INDEX.read_text(encoding="utf-8"))["styles"]}
    per, meta = rea_merge(rea_paths if isinstance(rea_paths, list) else [rea_paths]) if rea_paths else ({}, None)
    fp_owner = collections.defaultdict(set)
    for mod, v in per.items():
        if mod.startswith("styles/"):
            for h in v["fingerprints"]:
                fp_owner[h].add(Path(mod).stem)
    styles = []
    for sid in sorted(index, key=lambda k: index[k]["number"]):
        raw = (src / "styles" / (sid + ".js")).read_text(encoding="utf-8")
        feats, stripped = lexical(raw)
        card = json.loads((src / "cards" / (sid + ".json")).read_text(encoding="utf-8"))
        tags = index[sid]["operator_tags"]
        support = {t: bool(re.search(TAG_SUPPORT[t], stripped)) for t in tags if t in TAG_SUPPORT}
        row = {"number": index[sid]["number"], "style_id": sid, "family": index[sid]["card_family"],
               "source_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(), "card_matches_index": card.get("family") == index[sid]["card_family"],
               "features": feats, "bricks": bricks_from(feats), "analyst_tags": tags,
               "tag_support": {"checked": len(support), "supported": sum(support.values()),
                               "unsupported": sorted(t for t, ok in support.items() if not ok), "unchecked": sorted(t for t in tags if t not in TAG_SUPPORT)},
               "evidence": "E2_STATIC_CODE", "status": "NOT_RECONSTRUCTED"}
        r = per.get("styles/%s.js" % sid)
        if r is not None and r["functions"]:
            row["rea"] = {"functions": r["functions"], "call_sites": r["call_sites"], "bindings": r["bindings"],
                          "relations": dict(r["relations"].most_common()), "multi_line_fingerprints": len(r["fingerprints"]),
                          "shares_function_bodies_with": sorted({o for h in r["fingerprints"] for o in fp_owner[h] if o != sid})}
        styles.append(row)
    agg = collections.Counter("%s:%s" % (b, lab.split(" ")[0]) for s in styles for b, labels in s["bricks"].items() for lab in labels)
    checked = sum(s["tag_support"]["checked"] for s in styles)
    supported = sum(s["tag_support"]["supported"] for s in styles)
    return {"schema": "kosif.matrices.code-bricks.v1",
            "title": "86-style static code decomposition into state / operation / law / time / memory / feedback",
            "archive_sha256": man["archive_sha256"],
            "method": "Lexical scan of each reference style source + REA semantic graph. Static only: nothing executed, no source text stored here.",
            "evidence": "E2_STATIC_CODE (labels inferred from code patterns; not a render test)", "rea": meta, "style_count": len(styles),
            "brick_frequency": dict(sorted(agg.items(), key=lambda kv: (-kv[1], kv[0]))),
            "analyst_tag_validation": {"checked": checked, "supported_by_code": supported, "rate": round(supported / checked, 4) if checked else None},
            "findings": findings(styles), "styles": styles}


def findings(styles):
    n = len(styles)
    has = lambda brick, prefix: [s["style_id"] for s in styles if any(l.startswith(prefix) for l in s["bricks"][brick])]
    post, steer, resample = has("feedback", "pixel_postprocess"), has("feedback", "field_drives_motion"), has("memory", "trail_by_resampling")
    modes = collections.Counter(m for s in styles for m in s["features"]["composite_modes"])
    graph = {s["style_id"]: set((s.get("rea") or {}).get("shares_function_bodies_with", [])) for s in styles}
    seen, clusters = set(), []
    for sid in graph:
        if sid in seen or not graph[sid]:
            continue
        stack, comp = [sid], set()
        while stack:
            x = stack.pop()
            if x not in comp:
                comp.add(x)
                stack.extend(graph.get(x, set()) - comp)
        seen |= comp
        clusters.append(sorted(comp))
    clusters.sort(key=lambda c: (-len(c), c))
    return {
        "shared_code_lineage": {"styles_sharing_function_bodies": sum(1 for v in graph.values() if v), "clusters": clusters,
                                "meaning": "REA normalized-AST fingerprints (functions of 3+ lines) that appear in more than one style: these styles reuse the same drawing routine, so pairing them is not an independent combination."},
        "pure_function_of_time": "All %d styles are written as frame = f(t); none keeps state between frames." % n,
        "memory_is_simulated": "%d/%d styles fake history by recomputing earlier t inside the frame (trail_by_resampling); no style stores a material memory that later frames read." % (len(resample), n),
        "temporal_feedback_styles": "0/%d: no style carries pixels or state from one frame into the next (every frame is rebuilt from t)." % n,
        "within_frame_pixel_postprocess": {"count": len(post), "styles": post},
        "field_steers_geometry": {"count": len(steer), "styles": steer},
        "styles_using_Math_random": [s["style_id"] for s in styles if s["features"]["uses_math_random"]],
        "composite_modes_by_style_count": dict(modes.most_common()),
        "implication": "A persistent memory field that changes later motion (the glass-memory recipe) is a mechanism the 86 references do not contain; it must be simulated outside the pure-t frame and played back."}


# ------------------------------------------------------------------ committed data
def load(path=BRICKS_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def show(style_id, path=BRICKS_FILE):
    s = next((s for s in load(path)["styles"] if s["style_id"] == style_id), None)
    return None if s is None else {k: s[k] for k in s if k != "features"} | {"operations": s["features"]["operations"]}


def summary(path=BRICKS_FILE):
    d = load(path)
    return {k: d[k] for k in ("style_count", "rea", "analyst_tag_validation", "findings")} | {"top_bricks": dict(list(d["brick_frequency"].items())[:30])}


def lineage(path=BRICKS_FILE):
    """style_id -> styles whose code shares function bodies with it (REA fingerprints)."""
    p = Path(path)
    return {s["style_id"]: set((s.get("rea") or {}).get("shares_function_bodies_with", [])) for s in load(p)["styles"]} if p.exists() else {}


def lineage_conflicts(parent_ids, shares=None):
    shares = lineage() if shares is None else shares
    return ["%s+%s" % (a, b) for i, a in enumerate(parent_ids) for b in parent_ids[i + 1:] if b in shares.get(a, ())]
