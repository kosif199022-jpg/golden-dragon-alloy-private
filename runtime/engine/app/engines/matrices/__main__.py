"""python -m engines.matrices <command>   (same commands as kmx.py, plus generate / atlas-extract / bricks analyze)

  doctor                          what this machine can run, ledger chain, counts
  recipe validate R.json          six bricks, three parents/families, operators tagged in the 86-card index, no shared code
  experiment --recipe R --out D [--seeds 1,2] [--render] [--mp4] [--record [--replication] [--sources SRC-001,..]]
  scene --recipe R --out F.html   only the playable scene
  ledger [stats|list|verify]      rate --experiment EXP-0001 --score 4 --by NAME [--notes ..]
  ideate --count N [--seed S] [--record]           generate --catalog C [--seed S] [--count N] [--output F]
  hypotheses stats|show ID|mark ID --status S --evidence FILE
  sources list|verify|add --file F|--url U --title T --relevance R --rights X [--used-for "a;b"]
  bricks summary|show ID|analyze --src TREE [--rea a.json ..] [--out F]     atlas-extract --archive ZIP --out DIR
  laws list|run R [--frames N --n N --render DIR]|verify REPORT|atoms [--axis A]
  probe                           the original 1-D numeric glass probe
Global: --memory DIR puts ledger.jsonl + registry.json there (default engines/matrices/data/memory, env BD_MATRICES_MEMORY).
"""
import argparse, json, os, sys
from pathlib import Path


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m engines.matrices", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--memory", help="folder for ledger.jsonl and registry.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    add = lambda name, *args: sub.add_parser(name, *args)
    add("doctor"); add("probe")
    p = add("recipe"); p.add_argument("action", choices=["validate"]); p.add_argument("path")
    p = add("experiment"); p.add_argument("--recipe", required=True); p.add_argument("--out", required=True); p.add_argument("--seeds")
    for f in ("--render", "--mp4", "--record", "--replication"):
        p.add_argument(f, action="store_true")
    p.add_argument("--sources", help="comma-separated SRC ids that fed this experiment")
    p = add("scene"); p.add_argument("--recipe", required=True); p.add_argument("--out", required=True)
    p = add("ledger"); p.add_argument("action", choices=["stats", "list", "verify"], nargs="?", default="stats")
    p = add("rate"); p.add_argument("--experiment", required=True); p.add_argument("--score", type=float, required=True)
    p.add_argument("--by", required=True); p.add_argument("--notes")
    p = add("ideate"); p.add_argument("--count", type=int, default=10); p.add_argument("--seed", type=int, default=20261025); p.add_argument("--record", action="store_true")
    p = add("generate"); p.add_argument("--catalog"); p.add_argument("--seed", type=int, default=20261024); p.add_argument("--count", type=int, default=75); p.add_argument("--output")
    p = add("hypotheses"); p.add_argument("action", choices=["stats", "show", "mark"]); p.add_argument("id", nargs="?")
    p.add_argument("--status"); p.add_argument("--evidence"); p.add_argument("--note")
    p = add("sources"); p.add_argument("action", choices=["list", "add", "verify"])
    for f in ("--file", "--url", "--title", "--name", "--kind", "--rights", "--note"):
        p.add_argument(f)
    p.add_argument("--relevance", choices=["core", "method", "context", "not_relevant"]); p.add_argument("--used-for", dest="used_for"); p.add_argument("--pages", type=int)
    p = add("bricks"); p.add_argument("action", choices=["summary", "show", "analyze"]); p.add_argument("id", nargs="?")
    p.add_argument("--src"); p.add_argument("--rea", nargs="+"); p.add_argument("--out")
    p = add("atlas-extract"); p.add_argument("--archive", required=True); p.add_argument("--out", required=True)
    p = add("laws"); p.add_argument("action", choices=["list", "run", "verify", "atoms"]); p.add_argument("path", nargs="?")
    p.add_argument("--frames", type=int, default=32); p.add_argument("--n", type=int, default=120); p.add_argument("--render", metavar="DIR"); p.add_argument("--axis")
    a = ap.parse_args(argv)
    if a.memory:
        os.environ["BD_MATRICES_MEMORY"] = a.memory
    if a.cmd == "sources" and a.action == "add" and not (a.title and a.relevance and a.rights):
        ap.error("sources add needs --title, --relevance and --rights")
    if a.cmd == "hypotheses" and a.action == "mark" and not a.status:
        ap.error("hypotheses mark needs --status")
    try:
        return run(a)
    except ValueError as e:
        emit({"error": str(e)})
        return 2


def run(a):
    from . import engine, memory as M, laws as L, bricks as B, catalog, doctor, validate, experiment, ideate, recipe_hash, RECIPES, DATA
    c = a.cmd
    if c == "doctor":
        r = doctor(); emit(r); return 0 if r["ledger"]["ok"] and r["catalog_86"] else 1
    if c == "probe":
        emit(engine.probe()); return 0
    if c == "recipe":
        rec = json.loads(Path(a.path).read_text(encoding="utf-8"))
        errs = validate(rec)
        emit({"recipe": rec.get("id"), "valid": not errs, "errors": errs, "recipe_hash": None if errs else recipe_hash(rec)}); return 0 if not errs else 1
    if c == "experiment":
        s = experiment(a.recipe, a.out, seeds=[int(x) for x in a.seeds.split(",")] if a.seeds else None, render=a.render, mp4=a.mp4,
                       record=a.record, replication=a.replication, sources=(a.sources or "").split(","))
        emit(s)
        return 1 if "valid" in s else 2 if "error" in s else 0 if s["verdict"] == "CONFIRMED_IN_MODEL" else 3
    if c == "scene":
        from .scene import write_scene
        rec = engine.load_recipe(a.recipe)
        runs, _, m = engine.run_conditions(rec)
        emit(write_scene(a.out, rec, runs, m)); return 0
    if c == "ledger":
        if a.action == "verify":
            r = M.verify_ledger(); emit(r); return 0 if r["ok"] else 1
        emit([{k: e.get(k) for k in ("seq", "type", "id", "recipe_id", "hypothesis", "experiment", "status", "verdict", "score", "at")}
              for e in M.read_ledger()] if a.action == "list" else M.stats()); return 0
    if c == "rate":
        emit(M.record_rating(a.experiment, a.score, a.by, a.notes or "")); return 0
    if c == "ideate":
        emit(ideate(a.count, a.seed, a.record)); return 0
    if c == "generate":
        if not 1 <= a.count <= 100000:
            raise ValueError("count range 1..100000")
        res = {"seed": a.seed, "source_count": 86, "warning": "Ideas only; not visual renders or globally verified unique styles",
               "hypotheses": engine.generate(engine.load_catalog(a.catalog or DATA / "86_style_research_database.json"), a.count, a.seed)}
        text = json.dumps(res, ensure_ascii=False, indent=2)
        Path(a.output).write_text(text, encoding="utf-8") if a.output else print(text)
        return 0
    if c == "hypotheses":
        status, counts = M.hypothesis_status()
        if a.action == "stats":
            emit({"total": len(status), "by_status": counts}); return 0
        if not a.id:
            emit({"error": "give a hypothesis id"}); return 2
        if a.action == "show":
            h = next((x for x in json.loads(M.SEEDS.read_text(encoding="utf-8"))["hypotheses"] if x["id"] == a.id), None)
            emit(dict(h, current_status=status[a.id]) if h else {"error": "unknown id"}); return 0 if h else 2
        emit(M.mark_hypothesis(a.id, a.status, a.evidence, a.note or "")); return 0
    if c == "sources":
        if a.action == "list":
            emit(M.read_registry()); return 0
        if a.action == "verify":
            s = M.verify_source(a.file); emit({"registered": bool(s), "source": s}); return 0 if s else 1
        s, new = M.add_source(a.title, a.relevance, a.rights, [u for u in (a.used_for or "").split(";") if u], file=a.file, url=a.url,
                              name=a.name, kind=a.kind, note=a.note or "", pages=a.pages)
        emit({"new": new, "source": s}); return 0
    if c == "bricks":
        if a.action == "analyze":
            out = B.analyze(a.src, a.rea)
            dest = Path(a.out or B.BRICKS_FILE)
            dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            emit({"out": str(dest), "styles": out["style_count"], "rea": bool(out["rea"]), "tag_validation": out["analyst_tag_validation"]}); return 0
        if a.action == "show":
            s = B.show(a.id)
            emit(s if s else {"error": "unknown style id"}); return 0 if s else 2
        emit(B.summary()); return 0
    if c == "atlas-extract":
        r = B.extract_atlas(a.archive, a.out); emit(r); return 0 if not r["missing_source"] else 1
    # laws
    if a.action == "list":
        emit({"laws": L.LAWS, "recipes": sorted(str(x.relative_to(DATA)) for x in L.RECIPES.glob("*.json"))}); return 0
    if a.action == "atoms":
        rows = L.atoms()
        emit([r for r in rows if r["axis"] == a.axis] if a.axis else {"count": len(rows), "axes": sorted({r["axis"] for r in rows})}); return 0
    if a.action == "verify":
        ok = L.verify_render(a.path); emit({"verified": ok}); return 0 if ok else 1
    plan = L.load_plan(a.path)
    out = L.render(plan, a.render, a.frames, a.n) if a.render else L.experiment(plan, a.frames, a.n)
    if a.render:
        out = {k: v for k, v in out.items() if k != "files_sha256"} | {"report": str(Path(a.render) / "report.json")}
    emit(out); return 0


if __name__ == "__main__":
    sys.exit(main())
