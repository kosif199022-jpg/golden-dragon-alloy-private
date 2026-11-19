"""Research memory: a hash-chained append-only ledger + a sha256 source registry.

ledger.jsonl  each line stores the sha256 of the previous line. Events: experiment, replication, idea, rating, hypothesis_status.
registry.json every file or link that fed the work, by sha256 (same bytes under another name become an alias).
Default home: engines/matrices/data/memory/ (override with the env var BD_MATRICES_MEMORY=<dir>).
Rules: one recipe hash = one experiment (re-runs are replications); idea signatures never repeat (283 seeds + ledger);
a rating names an existing experiment and a reviewer; leaving UNTESTED_UNRENDERED needs an evidence file (its sha256 is kept).
"""
import datetime, hashlib, json, math, os
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
SEEDS = DATA / "283_hypothesis_seeds.json"
EVENT_TYPES = ("experiment", "replication", "idea", "rating", "hypothesis_status")
HYP_STATUSES = ("UNTESTED_UNRENDERED", "PROPOSED_RECIPE", "NUMERIC_TESTED", "RENDER_TESTED", "REJECTED", "PRODUCTION_READY")
RELEVANCE = ("core", "method", "context", "not_relevant")


def home():
    return Path(os.environ.get("BD_MATRICES_MEMORY") or DATA / "memory")


def _ledger(path):
    return Path(path) if path else home() / "ledger.jsonl"


def _registry(path):
    return Path(path) if path else home() / "registry.json"


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# ------------------------------------------------------------------ ledger
def _lines(path):
    p = _ledger(path)
    return [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def read_ledger(path=None):
    return [json.loads(l) for l in _lines(path)]


def verify_ledger(path=None):
    if not _ledger(path).exists():
        return {"ok": True, "events": 0, "problems": []}
    prev, problems, lines = None, [], _lines(path)
    for i, line in enumerate(lines, 1):
        ev = json.loads(line)
        if ev.get("seq") != i:
            problems.append("line %d: seq %s" % (i, ev.get("seq")))
        if ev.get("prev_sha256") != prev:
            problems.append("line %d: broken hash chain" % i)
        if ev.get("type") not in EVENT_TYPES:
            problems.append("line %d: unknown type %s" % (i, ev.get("type")))
        prev = hashlib.sha256(line.encode("utf-8")).hexdigest()
    return {"ok": not problems, "events": len(lines), "head_sha256": prev, "problems": problems}


def append(event, path=None):
    p = _ledger(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if event.get("type") not in EVENT_TYPES:
        raise ValueError("type must be one of %s" % (EVENT_TYPES,))
    chk = verify_ledger(p)
    if not chk["ok"]:
        raise RuntimeError("ledger chain is broken, refusing to append: %s" % chk["problems"][:3])
    ev = dict(event, seq=chk["events"] + 1, prev_sha256=chk.get("head_sha256"))
    ev.setdefault("at", now_iso())
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.write(canonical(ev) + "\n")
    return ev


def next_id(prefix, events):
    return "%s%04d" % (prefix, 1 + sum(1 for e in events if e.get("id", "").startswith(prefix)))


def record_experiment(report, artifacts, path=None, replication=False, sources=None):
    events = read_ledger(path)
    same = [e for e in events if e["type"] == "experiment" and e.get("recipe_hash") == report["recipe_hash"]]
    if same and not replication:
        raise ValueError("recipe %s (hash %s) already recorded as %s; pass replication=True to log a re-run"
                         % (report["recipe_id"], report["recipe_hash"], same[0]["id"]))
    return append({"type": "replication" if same else "experiment", "id": next_id("EXP-", events), "recipe_id": report["recipe_id"],
                   "recipe_hash": report["recipe_hash"], "replicates": same[0]["id"] if same else None, "verdict": report["verdict"],
                   "status": report.get("status"), "checks": report["checks"], "effect": report["effect"],
                   "dose_spearman": report["dose_response"]["spearman_rho"], "roles": report.get("roles"), "parents": report.get("parents"),
                   "render": report.get("render"), "artifacts": artifacts, "sources": sources or []}, path)


def signature(parent_ids, roles):
    return "|".join(sorted(parent_ids)) + "#" + ",".join("%s=%s" % (k, roles[k]) for k in sorted(roles))


def _seeds(seeds):
    return json.loads(Path(seeds).read_text(encoding="utf-8"))["hypotheses"]


def known_signatures(path=None, seeds=SEEDS):
    sigs = {signature([p["style_id"] for p in h["parents"]], h["roles"]) for h in _seeds(seeds)}
    return sigs | {e["signature"] for e in read_ledger(path) if e["type"] == "idea"}


def record_idea(idea, path=None, seeds=SEEDS):
    sig = signature(idea["parents"], idea["roles"])
    if sig in known_signatures(path, seeds):
        raise ValueError("duplicate idea signature: " + sig)
    return append({"type": "idea", "id": idea["id"], "signature": sig, "parents": idea["parents"], "roles": idea["roles"],
                   "status": "PROPOSED", "origin": idea.get("origin", "ideate")}, path)


def record_rating(experiment_id, score, by, notes="", path=None):
    exp = next((e for e in read_ledger(path) if e.get("id") == experiment_id and e["type"] in ("experiment", "replication")), None)
    if exp is None:
        raise ValueError("no experiment %s in the ledger" % experiment_id)
    if not (0 <= float(score) <= 5):
        raise ValueError("score must be 0..5")
    if not by or not by.strip():
        raise ValueError("a rating needs the reviewer's name (--by)")
    return append({"type": "rating", "experiment": experiment_id, "recipe_id": exp["recipe_id"], "score": float(score),
                   "by": by.strip(), "notes": notes, "kind": "HUMAN_RATING"}, path)


def mark_hypothesis(hyp_id, status, evidence=None, note="", path=None, seeds=SEEDS):
    if hyp_id not in {h["id"] for h in _seeds(seeds)}:
        raise ValueError("unknown hypothesis id " + hyp_id)
    if status not in HYP_STATUSES:
        raise ValueError("status must be one of %s" % (HYP_STATUSES,))
    ev = {"type": "hypothesis_status", "hypothesis": hyp_id, "status": status, "note": note}
    if status != "UNTESTED_UNRENDERED":
        if not evidence or not Path(evidence).exists():
            raise ValueError("leaving UNTESTED needs an existing --evidence file")
        ev.update(evidence=str(evidence), evidence_sha256=sha256_file(evidence))
    return append(ev, path)


def hypothesis_status(path=None, seeds=SEEDS):
    status = {h["id"]: h.get("status", "UNTESTED_UNRENDERED") for h in _seeds(seeds)}
    status.update({e["hypothesis"]: e["status"] for e in read_ledger(path) if e["type"] == "hypothesis_status"})
    counts = {}
    for s in status.values():
        counts[s] = counts.get(s, 0) + 1
    return status, counts


def operator_scores(path=None):
    """Beta(1+wins, 1+losses) per (role, operator) from verdicts and human ratings (score >= 4 wins). Ideas add nothing."""
    events = read_ledger(path)
    runs = [e for e in events if e["type"] in ("experiment", "replication")]
    exp = {e["id"]: e for e in runs}
    recipe_roles = {e["recipe_id"]: e["roles"] for e in runs if e.get("roles")}
    tally = {}
    for e in events:
        if e["type"] in ("experiment", "replication"):
            roles, ok = e.get("roles"), e.get("verdict") == "CONFIRMED_IN_MODEL"
        elif e["type"] == "rating":
            roles, ok = recipe_roles.get(e["recipe_id"]) or (exp.get(e["experiment"]) or {}).get("roles"), e["score"] >= 4
        else:
            continue
        for role, op in (roles or {}).items():
            tally.setdefault(role + ":" + op, [0, 0])[0 if ok else 1] += 1
    out = {}
    for k in sorted(tally):
        w, l = tally[k]
        a, b = 1 + w, 1 + l
        out[k] = {"wins": w, "losses": l, "posterior_mean": round(a / (a + b), 4),
                  "sd": round(math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1))), 4)}
    return out


def stats(path=None):
    events = read_ledger(path)
    by = {}
    for e in events:
        by[e["type"]] = by.get(e["type"], 0) + 1
    return {"events": len(events), "by_type": by, "chain": verify_ledger(path), "hypotheses_283": hypothesis_status(path)[1],
            "experiments": [{k: e.get(k) for k in ("id", "type", "recipe_id", "verdict", "status", "at")}
                            for e in events if e["type"] in ("experiment", "replication")],
            "operator_scores": operator_scores(path)}


# ------------------------------------------------------------------ source registry
def read_registry(path=None):
    p = _registry(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"schema": "kosif.matrices.sources.v1", "sources": []}


def write_registry(reg, path=None):
    p = _registry(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    reg["sources"].sort(key=lambda s: s["id"])
    p.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def add_source(title, relevance, rights, used_for, file=None, url=None, name=None, kind=None, note="", pages=None, path=None, added=None):
    if relevance not in RELEVANCE:
        raise ValueError("relevance must be one of %s" % (RELEVANCE,))
    if not file and not url:
        raise ValueError("a source needs --file or --url")
    reg = read_registry(path)
    digest = sha256_file(file) if file else None
    display = name or (Path(file).name if file else url)
    for s in reg["sources"]:
        if (digest and s.get("sha256") == digest) or (url and not digest and s.get("url") == url):
            if display not in s["names"]:
                s["names"].append(display)
                write_registry(reg, path)
            return s, False
    n = 1 + max([int(s["id"].split("-")[1]) for s in reg["sources"]] or [0])
    s = {"id": "SRC-%03d" % n, "title": title, "names": [display], "kind": kind or (Path(file).suffix.lstrip(".") if file else "url"),
         "sha256": digest, "bytes": Path(file).stat().st_size if file else None, "pages": pages, "url": url, "rights": rights,
         "relevance": relevance, "used_for": used_for, "note": note, "added": added or now_iso()[:10],
         "content_in_repo": "none (metadata and derived measurements only)"}
    reg["sources"].append(s)
    write_registry(reg, path)
    return s, True


def verify_source(file, path=None):
    digest = sha256_file(file)
    return next((s for s in read_registry(path)["sources"] if s.get("sha256") == digest), None)
