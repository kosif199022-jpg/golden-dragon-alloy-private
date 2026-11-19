"""Parity: engines.matrices (new) vs kosif-infinite-matrices/scripts/kmx.py (old), same seeds and inputs.

The old skill is copied into a tmp sandbox (it writes its ledger next to its scripts), so the original repo is never
touched; the new module writes its ledger to tmp via --memory. Compared: JSON outputs, ledger records (minus timestamps
and the hash chain that depends on them), report/scene files, SVG frames, stills and video (SSIM).
"""
import copy, json, os, re, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
KOSIF = Path(os.environ.get("KOSIF_ROOT") or Path.home() / "kosif-tool")
OLD = KOSIF / ".claude" / "skills" / "kosif-infinite-matrices"
NEW_DATA = ROOT / "engines" / "matrices" / "data"
pytestmark = pytest.mark.skipif(not (OLD / "scripts" / "kmx.py").exists(), reason="original kosif-infinite-matrices skill missing")
HAS_BROWSER = shutil.which("node") and shutil.which("ffmpeg") and (KOSIF / "node_modules" / "playwright").exists()
VOLATILE = {"at", "prev_sha256"}


@pytest.fixture(scope="module")
def box(tmp_path_factory):
    t = tmp_path_factory.mktemp("matrices")
    sk = t / "old" / ".claude" / "skills" / "kosif-infinite-matrices"
    for d in ("scripts", "data", "recipes", "sources", "memory"):
        shutil.copytree(OLD / d, sk / d, ignore=shutil.ignore_patterns("__pycache__"))
    for rel in ("tools/render_html.cjs", ".claude/skills/kosif-superpowers/assets/atlas_harness.js",
                ".claude/skills/kosif-superpowers/assets/atlas_sound.js", "fonts/kosif-jumuah/KOSIFJumuah-Bold.woff2"):
        (t / "old" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(KOSIF / rel, t / "old" / rel)
    mem = t / "newmem"
    mem.mkdir()
    shutil.copy2(NEW_DATA / "memory" / "ledger.jsonl", mem / "ledger.jsonl")
    shutil.copy2(NEW_DATA / "memory" / "registry.json", mem / "registry.json")
    rec = json.loads((NEW_DATA / "recipes" / "glass-remembers-light.json").read_text(encoding="utf-8"))
    small = copy.deepcopy(rec)  # small and fast, same physics
    small.update(grid={"w": 24, "h": 14}, particles=40, duration=3.0, fps=15)
    small["stimulus"].update(on=[0.0, 1.5], center=[12.0, 7.0], radius=[8.0, 4.0], period=1.5)
    small["structure"]["tiles"] = 8
    small["metrics"]["settle_after_off"] = 0.5
    small["acceptance"].update(seeds=[1, 2], dose_gains=[0.0, 0.5, 1.0])
    small["id"], small["slug"] = "KMX-R-T001", "glass-small"
    (t / "small.json").write_text(json.dumps(small, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, NODE_PATH=str(KOSIF / "node_modules"), PYTHONIOENCODING="utf-8")
    return {"t": t, "skill": sk, "mem": mem, "small": t / "small.json", "env": env}


def old(box, *args, ok=(0,)):
    r = subprocess.run([sys.executable, str(box["skill"] / "scripts" / "kmx.py"), *map(str, args)], cwd=box["t"] / "old",
                       capture_output=True, text=True, encoding="utf-8", env=box["env"])
    assert r.returncode in ok, r.stderr[-2000:]
    return json.loads(r.stdout) if r.stdout.strip().startswith(("{", "[")) else r.stdout


def new(box, *args, ok=(0,)):
    r = subprocess.run([sys.executable, "-m", "engines.matrices", "--memory", str(box["mem"]), *map(str, args)], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", env=box["env"])
    assert r.returncode in ok, r.stderr[-2000:]
    return json.loads(r.stdout) if r.stdout.strip().startswith(("{", "[")) else r.stdout


def ledger(path, skip=0):
    return [{k: v for k, v in json.loads(l).items() if k not in VOLATILE}
            for l in Path(path).read_text(encoding="utf-8").splitlines()[skip:] if l.strip()]


def ssim(a, b, size="320:180"):
    from engines.media import ffmpeg
    r = ffmpeg("-v", "info", "-i", a, "-i", b, "-lavfi", f"[0:v]scale={size},format=yuv420p[x];[1:v]scale={size},format=yuv420p[y];[x][y]ssim",
               "-f", "null", "-", capture=True)
    return float(re.findall(r"All:([\d.]+)", r.stderr)[-1])


def test_numeric_commands_match(box):
    assert new(box, "probe") == old(box, "probe")
    rec = NEW_DATA / "recipes" / "glass-remembers-light.json"
    assert new(box, "recipe", "validate", rec) == old(box, "recipe", "validate", rec)
    for args in (["hypotheses", "stats"], ["hypotheses", "show", "KMX-SEED-007"], ["bricks", "summary"], ["bricks", "show", "flow-field"],
                 ["laws", "atoms"], ["laws", "atoms", "--axis", "motion"]):
        assert new(box, *args) == old(box, *args), args
    n, o = new(box, "laws", "list"), old(box, "laws", "list")
    assert n["laws"] == o["laws"] and [Path(p).name for p in n["recipes"]] == [Path(p).name for p in o["recipes"]]


def test_generate_matches_matrices_py(box):
    cat = OLD / "data" / "86_style_research_database.json"
    r = subprocess.run([sys.executable, str(box["skill"] / "scripts" / "matrices.py"), "--catalog", str(cat), "--seed", "7", "--count", "40"],
                       capture_output=True, text=True, encoding="utf-8")
    assert json.loads(r.stdout) == new(box, "generate", "--catalog", cat, "--seed", "7", "--count", "40")


@pytest.mark.parametrize("law", ["elastic-memory", "material-memory", "self-imprinting", "trajectory-memory"])
def test_laws_match_and_svg_frames_identical(box, law):
    o_rec, n_rec = box["skill"] / "recipes" / "laws" / f"{law}.json", NEW_DATA / "recipes" / "laws" / f"{law}.json"
    assert new(box, "laws", "run", n_rec, "--frames", 16, "--n", 32) == old(box, "laws", "run", o_rec, "--frames", 16, "--n", 32)
    od, nd = box["t"] / "lo" / law, box["t"] / "ln" / law
    o = old(box, "laws", "run", o_rec, "--frames", 12, "--n", 24, "--render", od)
    n = new(box, "laws", "run", n_rec, "--frames", 12, "--n", 24, "--render", nd)
    assert {k: v for k, v in o.items() if k != "report"} == {k: v for k, v in n.items() if k != "report"}
    assert json.loads((od / "report.json").read_text(encoding="utf-8")) == json.loads((nd / "report.json").read_text(encoding="utf-8"))
    for f in sorted(od.rglob("*.svg")):  # same SVG text (the old writer used platform newlines)
        assert f.read_text(encoding="utf-8") == (nd / f.relative_to(od)).read_text(encoding="utf-8"), f
    assert new(box, "laws", "verify", nd / "report.json") == {"verified": True}


def test_ideas_and_ledger_records_match(box):
    o_ledger, base = box["skill"] / "memory" / "ledger.jsonl", len(ledger(box["mem"] / "ledger.jsonl"))
    assert new(box, "ideate", "--count", 12, "--seed", 3, "--record") == old(box, "ideate", "--count", 12, "--seed", 3, "--record")
    assert new(box, "ideate", "--count", 5, "--seed", 3) == old(box, "ideate", "--count", 5, "--seed", 3)  # recorded ideas are skipped
    ev = box["t"] / "evidence.txt"
    ev.write_text("evidence", encoding="utf-8")
    strip = lambda e: {k: v for k, v in e.items() if k not in VOLATILE | {"evidence"}}
    assert strip(new(box, "hypotheses", "mark", "KMX-SEED-002", "--status", "PROPOSED_RECIPE", "--evidence", ev)) == \
        strip(old(box, "hypotheses", "mark", "KMX-SEED-002", "--status", "PROPOSED_RECIPE", "--evidence", ev))
    assert [strip(e) for e in ledger(box["mem"] / "ledger.jsonl", base)] == [strip(e) for e in ledger(o_ledger, base)]
    assert new(box, "ledger", "verify")["ok"] and old(box, "ledger", "verify")["ok"]
    src = dict(title="T", relevance="method", rights="own", used_for="a;b")
    args = [x for k, v in src.items() for x in ("--" + k.replace("_", "-"), v)] + ["--file", ev]
    assert new(box, "sources", "add", *args) == old(box, "sources", "add", *args)


def test_experiment_report_and_record_match(box):
    o_out, n_out = box["t"] / "eo", box["t"] / "en"
    o = old(box, "experiment", "--recipe", box["small"], "--out", o_out, "--record", "--sources", "SRC-001", ok=(0, 3))
    n = new(box, "experiment", "--recipe", box["small"], "--out", n_out, "--record", "--sources", "SRC-001", ok=(0, 3))
    drop = lambda s: {k: v for k, v in s.items() if k not in ("scene", "out")}
    assert drop(n) == drop(o) and n["scene"]["bytes"] > 0
    for f in ("report.json", "report.md"):
        assert (n_out / f).read_bytes() == (o_out / f).read_bytes(), f
    body = lambda p: re.sub(r"<!-- Generated by .*?-->", "", p.read_text(encoding="utf-8"))
    assert body(n_out / "scene.html") == body(o_out / "scene.html")
    oe, ne = ledger(box["skill"] / "memory" / "ledger.jsonl")[-1], ledger(box["mem"] / "ledger.jsonl")[-1]
    oa, na = oe.pop("artifacts"), ne.pop("artifacts")
    assert ne == oe
    assert {k: v for k, v in na["sha256"].items() if k != "scene.html"} == {k: v for k, v in oa["sha256"].items() if k != "scene.html"}
    assert new(box, "rate", "--experiment", ne["id"], "--score", 4, "--by", "tester")["score"] == 4.0
    old(box, "rate", "--experiment", oe["id"], "--score", 4, "--by", "tester")
    assert ledger(box["mem"] / "ledger.jsonl")[-1] == ledger(box["skill"] / "memory" / "ledger.jsonl")[-1]
    s1, s2 = new(box, "ledger", "stats"), old(box, "ledger", "stats")
    assert s1["operator_scores"] == s2["operator_scores"] and s1["by_type"] == s2["by_type"]


@pytest.mark.skipif(not HAS_BROWSER, reason="node + ffmpeg + playwright needed")
def test_render_stills_and_video_ssim(box):
    o_out, n_out = box["t"] / "ro", box["t"] / "rn"
    o = old(box, "experiment", "--recipe", box["small"], "--out", o_out, "--render", "--mp4", ok=(0, 3))
    n = new(box, "experiment", "--recipe", box["small"], "--out", n_out, "--render", "--mp4", ok=(0, 3))
    assert n["status"] == o["status"]
    ro = json.loads((o_out / "report.json").read_text(encoding="utf-8"))["render"]
    rn = json.loads((n_out / "report.json").read_text(encoding="utf-8"))["render"]
    assert rn["stills"] == ro["stills"] and rn["page_errors"] == ro["page_errors"] == []
    assert rn["same_t_same_pixels"] and rn["visible_difference_after_off"] == ro["visible_difference_after_off"]
    for t, d in ro["pixel_diff"].items():
        for pair, v in d.items():
            assert abs(rn["pixel_diff"][t][pair]["changed_pixel_share"] - v["changed_pixel_share"]) < 0.01, (t, pair)
    scores = {s: ssim(o_out / s, n_out / s) for s in ro["stills"]}
    assert min(scores.values()) >= 0.98, scores
    assert rn["mp4"] and ro["mp4"]
    v = ssim(o_out / ro["mp4"], n_out / rn["mp4"])
    assert v >= 0.98, v
    from engines.media import probe
    assert {s["codec_type"] for s in probe(n_out / rn["mp4"])["streams"]} == {"video", "audio"}
    print("PARITY stills SSIM", scores, "video SSIM", v)


def test_atlas_extract_and_bricks_analyze_match(box):
    """A synthetic 86-entry archive (the real one is third-party and stays local) through extract + static analysis."""
    styles = json.loads((NEW_DATA / "86_style_research_database.json").read_text(encoding="utf-8"))["styles"]
    bodies = ["const g = H.layer(w, h); for (let i = 0; i < n; i++) { ctx.moveTo(x, y); ctx.lineTo(Math.sin(t * 2), y); }",
              "ctx.globalCompositeOperation = 'lighter'; const nz = H.makeNoise(3); ctx.fillText('x', 0, 0); // grad\n ctx.getImageData(0,0,1,1);",
              "if (t < 2.5) { ctx.arc(0,0,Math.hypot(1,2),0,7); ctx.fill(); } particles.forEach(p => H.ease(t - i * 0.1));"]
    lines = []
    for i, s in enumerate(styles):
        lines += [f"#{s['number']:02d} — {s['style_id'].title()}", f"Style ID: {s['style_id']}", f"Category: {s['card_family']}",
                  "Look: dark", "Motion: slow", "How it explains: by example"]
        if i < 2:
            lines += ["H HELPER LIBRARY (shared)", "```js", f"const H = {{v: {i}}};", "```", "SOUND KIT", "```js", "const SOUND = {};", "```"]
        lines += ["REFERENCE STYLE SOURCE (code)", "```js", f"/* {s['style_id']} */", bodies[i % 3], "```", ""]
    arc = box["t"] / "atlas.txt"
    arc.write_text("\n".join(lines), encoding="utf-8")
    od, nd = box["t"] / "atlas_old", box["t"] / "atlas_new"
    r = subprocess.run([sys.executable, str(box["skill"] / "scripts" / "kmx_atlas_extract.py"), "--archive", str(arc), "--out", str(od)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == new(box, "atlas-extract", "--archive", arc, "--out", nd)
    for f in sorted(od.rglob("*")):
        if f.is_file():
            assert f.read_text(encoding="utf-8") == (nd / f.relative_to(od)).read_text(encoding="utf-8"), f
    r = subprocess.run([sys.executable, str(box["skill"] / "scripts" / "kmx_bricks.py"), "analyze", "--src", str(od), "--out", str(box["t"] / "bo.json")],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    new(box, "bricks", "analyze", "--src", nd, "--out", box["t"] / "bn.json")
    assert json.loads((box["t"] / "bn.json").read_text(encoding="utf-8")) == json.loads((box["t"] / "bo.json").read_text(encoding="utf-8"))


@pytest.mark.skipif(not os.environ.get("BD_FULL"), reason="full-size run takes ~1 min; set BD_FULL=1")
def test_full_recipe_reproduces_committed_exp0001():
    from engines import matrices as mx
    want = json.loads((OLD / "experiments" / "EXP-0001-glass-remembers-light" / "report.json").read_text(encoding="utf-8"))
    got = mx.engine.experiment(mx.load_recipe(NEW_DATA / "recipes" / "glass-remembers-light.json"))[0]
    assert got == {k: want[k] for k in got}
