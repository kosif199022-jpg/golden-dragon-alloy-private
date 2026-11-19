"""Infinite Matrices (المصفوفات اللانهائية): invent visual systems from causal bricks and prove the cause.

Three parents from the 86-style index (structure / dynamics / finish) + six bricks (state, operation, law, time, memory,
feedback) make a recipe; `experiment` runs A/B/C counterfactuals with replication over seeds and a dose sweep, writes a
seekable scene, optionally renders stills/MP4, and can record the result in the hash-chained research ledger.

    from engines import matrices as mx
    mx.experiment("engines/matrices/data/recipes/glass-remembers-light.json", "out/glass", render=True)
    mx.ideate(10); mx.laws.experiment(mx.laws.load_plan(path)); mx.memory.stats()

The causal claim holds inside the numerical model only (same stimulus, same seed, one factor changed).
Modules: engine (glass memory sim, probe, generator), laws (four typed laws), memory (ledger + sources),
bricks (atlas extract + static analysis), scene (HTML scene, capture, MP4). Data in data/, page + JS in assets/.
"""
import json, shutil, sys
from pathlib import Path
from . import engine, laws, memory, bricks
from .engine import BRICKS, load_recipe, validate_recipe, recipe_hash, generate, probe

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
REPO = HERE.parents[1]
CATALOG = DATA / "86_style_research_database.json"
RECIPES = DATA / "recipes"


def catalog():
    return json.loads(CATALOG.read_text(encoding="utf-8"))["styles"]


def doctor():
    from .scene import node_playwright, RENDER, ASSETS
    chain = memory.verify_ledger()
    rep = {"python": sys.version.split()[0], "node": bool(shutil.which("node")), "node_playwright": node_playwright(),
           "ffmpeg": bool(shutil.which("ffmpeg")), "render_cjs": RENDER.exists(),
           "atlas_assets": all((ASSETS / f).exists() for f in ("atlas_harness.js", "atlas_sound.js", "scene.html", "capture.cjs")),
           "catalog_86": len(catalog()) == 86, "hypotheses_283": memory.hypothesis_status()[1],
           "code_bricks": bricks.BRICKS_FILE.exists(), "ledger": chain, "sources": len(memory.read_registry()["sources"]), "network": False}
    rep["can_render"] = rep["node_playwright"]
    rep["can_mp4"] = rep["node_playwright"] and rep["ffmpeg"] and rep["render_cjs"]
    return rep


def validate(rec):
    """Recipe problems against the 86-card index and REA code lineage (parents that share function bodies)."""
    return validate_recipe(rec, catalog()) + ["parents share code lineage (REA): " + c
                                              for c in bricks.lineage_conflicts([p.get("style_id") for p in rec.get("parents", [])])]


def report_md(r, rec):
    m = r["main"]
    pct = lambda v: "%.1f%%" % (100 * v)
    out = ["# %s — %s" % (rec["id"], rec["title_en"]), "", "**%s** · %s" % (rec["title_ar"], r["verdict"]), "", r["claim_scope"], "", "## Six bricks", ""]
    out += ["- **%s:** %s" % (b, rec["bricks"][b]) for b in BRICKS]
    out += ["", "## Parents (one role each, three families)", ""]
    out += ["- %s → `%s` (%s), operator `%s`: %s" % (p["role"], p["style_id"], p["family"], p["operator"], p["why"]) for p in rec["parents"]]
    out += ["", "## Conditions (same stimulus, same seed, one factor changed)", "",
            "| condition | change | motes on trace after beam off | memory after off | same memory as A |", "|---|---|---|---|---|"]
    out += ["| %s | `%s` | %s | %.2f | %s |" % (k, json.dumps(c.get("set") or {}), pct(m[k]["capture_mean_after_off"]), m[k]["memory_after_off"],
                                             m[k].get("same_memory_as_A", "—")) for k, c in rec["conditions"].items()]
    out += ["", "Chance level (share of the pane that is on the trace): %s." % pct(m["_chance_level"]), "",
            "## Replication over %d seeds" % len(r["replication"]), "", "| A minus | mean | sd | min | positive | sign test p |", "|---|---|---|---|---|---|"]
    out += ["| %s | %+.3f | %.3f | %+.3f | %s | %s |" % (k, e["mean_capture_gain_A_minus"], e["sd"], e["min"], e["positive_in"], e["sign_test_p_one_sided"])
            for k, e in r["effect"].items()]
    out += ["", "## Dose-response (coupling gain × factor)", "", "| factor | capture A |", "|---|---|"]
    out += ["| %.2f | %s |" % (row["gain_factor"], pct(row["capture_A"])) for row in r["dose_response"]["rows"]]
    out += ["", "Spearman ρ = %.3f." % r["dose_response"]["spearman_rho"], "", "## Checks", ""]
    out += ["- %s %s" % ("✅" if v else "❌", k) for k, v in r["checks"].items()]
    rd = r.get("render")
    if rd:
        out += ["", "## Render evidence", "", "- deterministic (same t → same pixels): %s" % rd.get("same_t_same_pixels"),
                "- page errors: %d" % len(rd.get("page_errors") or [])]
        for t, d in sorted((rd.get("pixel_diff") or {}).items(), key=lambda kv: float(kv[0])):
            out.append("- t=%ss: A vs B changed pixels %s, A vs C %s" % (t, pct(d.get("A_full|B_no_coupling", {}).get("changed_pixel_share", 0)),
                                                                          pct(d.get("A_full|C_no_memory", {}).get("changed_pixel_share", 0))))
        if rd.get("mp4"):
            out.append("- video: %s" % rd["mp4"])
    out += ["", "## Limits", "", "- The causal claim holds inside this numerical model; it says nothing about real glass optics.",
            "- Particles read memory but do not write it (one-directional chain, v1).",
            "- Visual quality and meaning still need a human rating (`kmx.py rate`).",
            "- Not a claim of global novelty; parents come from a third-party reference atlas analysed locally.", ""]
    return "\n".join(out)


def experiment(recipe, out, seeds=None, render=False, mp4=False, record=False, replication=False, sources=(), ledger=None):
    """Recipe -> report.json/.md + scene.html (+ stills, pixel diff, MP4) [+ ledger record]. Returns a summary dict."""
    from . import scene
    rec = load_recipe(recipe)
    errs = validate(rec)
    if errs:
        return {"valid": False, "errors": errs}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report, runs, ref = engine.experiment(rec, seeds=seeds)
    report.update(roles={p["role"]: p["operator"] for p in rec["parents"]}, parents=[p["style_id"] for p in rec["parents"]], status="NUMERIC_TESTED")
    sc = scene.write_scene(out / "scene.html", rec, runs, engine.measure(runs, rec, ref), report["verdict"])
    if render:
        if not scene.node_playwright():
            return {"error": "render needs node + Playwright + Chromium (see doctor)"}
        rd = report["render"] = scene.render_experiment(rec, out, mp4)
        if not rd["page_errors"] and rd["same_t_same_pixels"] and rd["visible_difference_after_off"]:
            report["status"] = "RENDER_TESTED"
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "report.md").write_text(report_md(report, rec), encoding="utf-8")
    summary = {"verdict": report["verdict"], "status": report["status"], "checks": report["checks"], "effect": report["effect"], "scene": sc, "out": str(out)}
    if record:
        arts = {str(p.relative_to(out)): memory.sha256_file(p) for p in sorted(out.rglob("*"))
                if p.is_file() and p.suffix in (".json", ".md", ".png", ".jpg", ".html", ".mp4")}
        res = out.resolve()
        rel = str(res.relative_to(REPO)) if res.is_relative_to(REPO) else str(out)
        ev = memory.record_experiment(report, {"dir": rel, "sha256": arts}, path=ledger, replication=replication, sources=[s for s in sources if s])
        summary["ledger"] = {"id": ev["id"], "type": ev["type"], "seq": ev["seq"]}
    return summary


def ideate(count=10, seed=20261025, record=False, ledger=None):
    """New parent/role triples never seen in the 283 seeds or the ledger, ranked by operator feedback, without shared code lineage."""
    scores, known, shares = memory.operator_scores(ledger), memory.known_signatures(ledger), bricks.lineage()
    weight = lambda h: 1.0 + sum(scores.get(r + ":" + op, {}).get("posterior_mean", 0.5) - 0.5 for r, op in h["roles"].items())
    pool = sorted(generate(catalog(), min(4000, count * 40), seed), key=lambda h: (-weight(h), h["id"]))
    out, skipped = [], 0
    for h in pool:
        sig = memory.signature(h["parents"], h["roles"])
        if sig in known:
            continue
        if bricks.lineage_conflicts(h["parents"], shares):
            skipped += 1  # parents reuse the same code (REA fingerprint): not an independent combination
            continue
        known.add(sig)
        out.append({"id": h["id"], "parents": h["parents"], "parent_families": h["parent_families"], "roles": h["roles"], "status": "PROPOSED",
                    "weight": round(weight(h), 4), "next_step": "write a recipe (six bricks + conditions) and run kmx.py experiment",
                    "origin": "ideate seed=%d" % seed})
        if len(out) == count:
            break
    recorded = [memory.record_idea(i, path=ledger)["seq"] for i in out] if record else []
    return {"count": len(out), "recorded": recorded, "skipped_shared_code_lineage": skipped, "ideas": out,
            "note": "Ideas are proposals; nothing was rendered or tested. Weights use ledger feedback only."}
