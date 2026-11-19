"""v1990: offline tests for the measured-free Higgsfield kit. Never calls Higgsfield, never spends."""
import ast
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "tools" / "hf_sandbox"
HF = [sys.executable, str(BIN / "hf.py")]


def run(*a):
    return subprocess.run(HF + list(a), capture_output=True, text=True, encoding="utf-8")


def module(name):
    spec = importlib.util.spec_from_file_location("t1990_" + name, BIN / (name + ".py"))
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(BIN))
    spec.loader.exec_module(m)
    return m


def test_free_catalog_shape_and_evidence():
    d = json.loads((BIN / "free.json").read_text(encoding="utf-8"))
    ids = [i["id"] for i in d["items"]]
    assert len(ids) == len(set(ids)) == 28
    assert d["balance_before"] == d["balance_after"]
    for i in d["items"]:
        assert i["status"] in d["status_legend"]
        assert i["evidence"].strip(), i["id"]          # no claim without evidence
    measured = {i["id"] for i in d["items"] if i["status"] == "measured"}
    assert {"jutsu", "higgsedit", "katana-analysis", "matchcut", "tiktok-trend"} <= measured
    by = {i["id"]: i["status"] for i in d["items"]}
    assert by["xl"] == "unknown" and by["video-analysis"] == "unknown"   # never promoted without a measurement
    assert by["grade-hf"] == "paid" and by["generation"] == "paid"
    assert len(d["matchcut_app"]["actions"]) == 28


def test_free_cli():
    r = run("free", "--json", "--status", "measured")
    assert r.returncode == 0 and all(i["status"] == "measured" for i in json.loads(r.stdout))
    assert json.loads(run("free", "jutsu").stdout)["id"] == "jutsu"
    assert run("free", "nope").returncode == 2
    assert run("free", "--status", "bogus").returncode == 2
    assert "347.88" in run("free").stdout


def test_trend_refs():
    d = json.loads((BIN / "trend_refs.json").read_text(encoding="utf-8"))
    assert len(d["what_if_styles"]) == 56 and len(d["katana_presets"]) == 100
    assert len({s["slug"] for s in d["what_if_styles"]}) == 56
    for s in d["what_if_styles"]:
        assert re.fullmatch(r"https://static-public-media\.higgsfield\.ai/what-if-styles/published/[0-9a-f]{64}", s["reference_video"])
    assert any(x["tool"] == "tiktok_music_trending" for x in d["live_sources"])


def test_trend_cli_and_injection_guard():
    r = run("trend", "find", "toy")
    assert r.returncode == 0 and "toy-planet" in r.stdout
    assert run("trend", "find", "zzzzqq").returncode == 1
    r = run("trend", "commands", "ink-gold")
    assert r.returncode == 0 and "analysis only" in r.stdout and "trend_dna.sh ink-gold 'https://" in r.stdout
    assert "generate_" not in r.stdout                       # the teardown never generates
    assert run("trend", "commands", "https://x.test/a'b; rm -rf ~").returncode == 2
    assert run("trend", "commands", "not-a-slug").returncode == 2
    assert run("trend", "live").returncode == 0


def test_templates_are_valid_and_carry_the_measured_fixes():
    scene = (BIN / "templates" / "jutsu_scene.py").read_text(encoding="utf-8")
    ast.parse(scene)
    assert "if s.world is None" in scene                      # the bug the first live run hit
    assert "BLENDER_EEVEE_NEXT'" not in scene and "type='AREA'" not in scene
    assert scene.index('media_type = "IMAGE"') < scene.index('file_format = "PNG"')
    assert "urllib" not in scene and "requests" not in scene   # the runtime has no network
    js = (BIN / "templates" / "higgsedit_ar.js").read_text(encoding="utf-8")
    assert "fontFamily: AR" in js and 'direction: "rtl"' in js
    sh = (BIN / "templates" / "trend_dna.sh").read_text(encoding="utf-8")
    assert subprocess.run(["bash", "-n", str(BIN / "templates" / "trend_dna.sh")]).returncode == 0
    assert "generate" not in sh and "rm -rf" not in sh


def test_cost_gate_classification():
    hf = module("hf")
    assert hf.classify("scene_builder_3d_run_python")[1] == "free"
    assert hf.classify("mcp__Higgsfield__scene_builder_3d_show_scene")[1] == "free"
    assert hf.classify("scene_builder_3d_generate_video")[1] == "paid"
    assert hf.classify("scene_builder_3d_generate_angles")[1] == "paid"
    assert hf.classify("apps_invoke")[1] == "paid"             # one measured action is not a blanket yes
    assert hf.classify("virality_predictor")[1] == "paid"
    assert hf.classify("media_import_url")[1] == "unknown"
    assert run("check", "scene_builder_3d_generate_video").returncode == 3


def test_text_commands_and_references():
    for c in ("blender", "higgsedit", "apps", "codefilm"):
        r = run(c)
        assert r.returncode == 0 and r.stdout.strip(), c
    assert "World" in run("blender", "rules").stdout
    assert run("blender", "bogus").returncode == 2
    assert (ROOT / "references" / "HIGGSFIELD_FREE_V1990.md").exists()


def test_version_and_registry():
    v = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "app" / "dragon" / "__init__.py").read_text(encoding="utf-8")).group(1)
    assert v == "1990" or v.startswith("1990.")  # v1990.x series
    ids = [t["id"] for t in json.loads((ROOT / "app" / "data" / "own_tools.json").read_text(encoding="utf-8"))["tools"]]
    assert len(ids) == len(set(ids)) >= 75  # the registry only grows (83 in v1990.9, 85 in v1990.10)
    assert {"hf-free", "hf-trend", "hf-blender", "framecheck", "blind-critic", "pack-registry"} <= set(ids)
    assert not (ROOT / "SOURCE_V1990_COMPANIONS.json").exists()      # unlicensed kits are cards (tool pack), not copies


def test_reel_dna_reads_real_katana_output(tmp_path):
    """Fixture = real numbers from a 2026-11-11 Katana run (ink-gold, 60 s, 24 fps). v10.17.2 could not read these files."""
    fx = ROOT / "app" / "tests" / "fixtures" / "katana_ink_gold"
    out = tmp_path / "dna.json"
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "reel_dna" / "reel_dna.py"), "extract",
                        "--analysis", str(fx / "analysis.json"), "--energy", str(fx / "energy.json"),
                        "--beats", str(fx / "beats.json"), "--words", str(fx / "words.json"),
                        "--cutsync", str(fx / "cutsync.json"), "--out", str(out)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["fps"] == 24.0 and d["total_frames"] == 1440 and d["source_schema"] == "rr.analysis/1"
    assert len(d["shots"]) == 38 and len(d["cuts"]) == 37
    assert sum(s["duration_frames"] for s in d["shots"]) == 1440          # frame-exact, no gap from inclusive f1
    assert d["shots"][0]["end_frame"] == 52 and d["shots"][-1]["start_frame"] == 1409
    kinds = [e["type"] for e in d["energy_events"]]
    assert (kinds.count("flash"), kinds.count("shake"), kinds.count("pan"), kinds.count("punch")) == (18, 9, 21, 16)
    assert len(d["beat_frames"]) == 142 and d["cut_sync"]["on_onset_share"] == 0.838
    assert d["energy_rates"]["cuts_ps"] == 0.63 and "path" not in d["energy_rates"]
    assert d["words"][0]["confidence"] == 0.695 and d["warnings"] == []


def test_reel_dna_katana_rejects_bad_cut(tmp_path):
    bad = tmp_path / "a.json"
    bad.write_text(json.dumps({"schema": "rr.analysis/1", "ref": {"fps": "24/1", "nb_frames": 48},
                               "cuts": [{"f0": 0}, {"f0": 99}]}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "reel_dna" / "reel_dna.py"), "extract",
                        "--analysis", str(bad), "--out", str(tmp_path / "o.json")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode != 0 and not (tmp_path / "o.json").exists()
