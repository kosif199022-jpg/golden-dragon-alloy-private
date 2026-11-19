"""Offline, metadata-only tests; never starts Higgsfield or workflows."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "tools" / "hf_sandbox"

def module(name):
    spec = importlib.util.spec_from_file_location("test_"+name, BIN / (name+".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def test_catalog_unique_and_alias():
    w=module("workflows")
    d=w.load()
    assert len(d["workflows"]) == 14
    assert len({r["name"] for r in d["workflows"]}) == 14
    assert next(x for x in d["workflows"] if x["name"] == "microdrama-ads")["alias_of"] == "drama-ads"
    assert sum(r["readiness"] == "dependency_ready" for r in d["workflows"]) == 8

def test_routes_do_not_claim_execution():
    w=module("workflows")
    assert "shorts-studio" in w.route("ريلز موشن", w.load()["workflows"])
    assert "video-montage" in w.route("ترجمة كابشن كلمة", w.load()["workflows"])
    assert "microdrama-ads" not in w.route("دراما", w.load()["workflows"])

def test_cli_metadata_and_cost_gate():
    r=subprocess.run([sys.executable,str(BIN / "hf.py"),"workflows","--json"],capture_output=True,text=True)
    assert r.returncode == 0
    assert len(json.loads(r.stdout)) == 14
    r=subprocess.run([sys.executable,str(BIN / "hf.py"),"workflow","katana"],capture_output=True,text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["readiness"] == "needs_setup"
    r=subprocess.run([sys.executable,str(BIN / "hf.py"),"route","ريلز كابشن عربي","--json"],capture_output=True,text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["verified_execution"] is False
    hf=module("hf")
    assert hf.classify("media_import_url")[1] == "unknown"
    assert hf.classify("sandbox_exec")[1] == "free"
    assert hf.classify("generate_video")[1] == "paid"
