"""Golden Bird: separation from the White Bird / Black Dragon, the three new tools, and golden_tools behaviour."""
import ast
import hashlib
import json
import re
import zipfile
from pathlib import Path

import pytest

from conftest import APP, FORGE, read, tree

PY = ["app.py", "control.py", "mcp_control.py", "mcp_dragon.py", "brain.py", "voice.py", "golden_tools.py"]


# ---------------------------------------------------------------- generated + compiles
def test_generated_by_forge():
    stamp = json.loads(read(".gb_generated.json"))
    assert stamp["library_items"] > 50 and stamp["studio_programs"] >= 8
    for rel, h in stamp["files"].items():
        if rel.endswith((".woff2", ".woff", ".ttf", ".otf")) and not (APP / rel).exists():
            continue        # Red Dragon package: fonts are left out on purpose (font policy); any other missing file still fails
        assert hashlib.sha256((APP / rel).read_bytes()).hexdigest() == h, f"{rel} edited by hand"


@pytest.mark.parametrize("name", PY)
def test_compiles(name):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")          # an invalid escape (e.g. a lone backslash in CC_NOTE) fails here
        compile(read(name), name, "exec")


# ---------------------------------------------------------------- separation
def test_identity_and_mutex():
    t = read("app.py")
    assert 'APP = "الطائر الذهبي"' in t
    assert '"Local\\\\GoldenBirdDesktopApp"' in t
    assert '/ "GoldenBird" / "settings.json"' in t
    assert '".goldenbird-build" / "dist" / "GoldenBird"' in t
    assert "GOLDEN_BIRD_HOME" in t and "الطائر الذهبي" in t


def test_port_everywhere():
    for rel in ("control.py", "mcp_control.py", "mcp_dragon.py", "chrome_extension/background.js"):
        assert "47841" in read(rel), rel
    assert "const PORT = 47841;" in read("chrome_extension/background.js")


def test_no_white_bird_or_dragon_leftovers():
    strict = re.compile(r"47831|47821|Local\\+(?:White|Black)|/ \"(?:WhiteBird|BlackDragon)\" / \"settings\.json\"|\.whitebird-build|bd_build")
    pat = re.compile(r"WhiteBird|whitebird|White Bird|الطائر الأبيض|white-bird|🕊")
    allowed = {"app.py": 3, "golden_tools.py": 1, "README.md": 1, "ui/index.html": 2}   # lineage + first-run copy
    for p in APP.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".py", ".html", ".js", ".json", ".css", ".ps1", ".md", ".txt"):
            text = p.read_text(encoding="utf-8-sig", errors="replace")
            rel = p.relative_to(APP).as_posix()
            assert not strict.findall(text), f"{rel}: {strict.findall(text)[:3]}"
            assert len(pat.findall(text)) <= allowed.get(rel, 0), f"{rel}: {pat.findall(text)[:5]}"


def test_seed_prefers_white_bird_then_dragon():
    t = read("app.py")
    assert 'for n in ("WhiteBird", "BlackDragon")' in t
    assert 'if src.name in ("BlackDragon", "WhiteBird"):' in t


def test_build_script():
    b = read("build.ps1")
    assert "--name GoldenBird" in b and ".goldenbird-build" in b and "golden-bird.ico" in b
    assert '--add-data "$here\\golden;golden"' in b and "--hidden-import golden_tools" in b
    assert "run_tests.ps1" in b and "SkipTests" in b
    codes = ",".join(f"0x{ord(c):x}" for c in "الطائر الذهبي")
    assert codes in b


def test_ui_gold_layer():
    h = read("ui/index.html")
    assert "<title>الطائر الذهبي</title>" in h
    assert "الطائر الذهبي — gold layer" in h and "--on-accent" in h
    assert 'src="golden-bird.png"' in h and "gb-badge" in h
    assert (APP / "ui" / "golden-bird.png").is_file() and (APP / "ui" / "golden-bird.ico").is_file()
    assert h.count("<script") == h.count("</script>")


def test_light_mode_keeps_light_surfaces():
    """Regression (2026-11-14): warm dark surfaces in an unconditional :root overrode the light media query -> dark on dark."""
    css = (FORGE / "overlay" / "golden-bird.css").read_text(encoding="utf-8")
    plain = [b for b in re.findall(r"(?m)^:root\{[^}]*\}", css)]
    assert plain and not any("--bg" in b or "--card" in b for b in plain)
    assert "@media not (prefers-color-scheme: light){:root:not([data-theme=light])" in css


# ---------------------------------------------------------------- the three tools
def _tools():
    t = tree()
    for node in t.body:
        if isinstance(node, ast.Assign) and any(getattr(x, "id", "") == "TOOLS" for x in node.targets):
            return {c.args[0].value: c for c in node.value.elts if isinstance(c, ast.Call) and c.args}
    raise AssertionError("TOOLS not found")


def test_tools_registered_with_right_approval():
    tools = _tools()
    for name in ("studio", "studio_run", "motion_lib", "speech_sync"):
        assert name in tools
    def approval(call):
        return any(k.arg == "approval" and k.value.value is True for k in call.keywords)
    assert approval(tools["studio_run"])
    assert not approval(tools["studio"]) and not approval(tools["motion_lib"]) and not approval(tools["speech_sync"])


def test_dispatch_and_prompt():
    t = read("app.py")
    assert 'if name in ("studio", "studio_run", "motion_lib", "speech_sync"):' in t and "def golden_dispatch(" in t
    assert 'if name == "speech_sync":' in t and "الوقت مربوط بالكلام" in t
    assert '{APP_SOURCE}\\\\golden_tools.py" sync SCRIPT.txt' in t      # two backslashes in source = one in the f-string
    assert t.startswith('"""الطائر الذهبي — Windows desktop app, generated from the Black Dragon app by forge/make_white_bird.py + '
                        'forge/make_golden_bird.py.')
    assert "## قدرات الطائر الذهبي" in t and "بروتوكول الذهب" in t
    assert 'golden_tools.py" studio list' in t and 'golden_tools.py" lib find' in t    # subscription mode mapping


# ---------------------------------------------------------------- golden_tools: catalogs
def test_catalogs_valid(gt):
    lib = gt.library()
    ids = [i["id"] for i in lib["items"]]
    assert len(ids) == len(set(ids)) and len(ids) > 50
    for it in lib["items"]:
        assert it.get("name") and it.get("license") is not None
        if it.get("offline_entry"):
            assert Path(it["offline_entry"]).exists(), it["id"]
        assert (it.get("readiness") == "ready-offline") == bool(it.get("offline_entry")), it["id"]   # ✓ only when kit can copy
    for p in gt.studio_items():
        assert re.fullmatch(r"[0-9a-f]{64}", p["archive_sha256"]), p["id"]
        assert p["exe"]


@pytest.mark.parametrize("q,expect", [("انيميشن تايم لاين", "gsap"), ("جزيئات", "tsparticles"), ("ثري دي", "three"),
                                      ("لوتي", "lottie"), ("شيدر", "shader")])
def test_arabic_search(gt, q, expect):
    hits = [i["id"] for i in gt.lib_find(q, 8)]
    assert any(expect in h for h in hits), (q, hits)


def test_kit_copies_ready_builds_and_licence(gt, tmp_path):
    ready = next(i for i in gt.lib_items() if i["id"] == "gsap")
    out, ok = gt.lib_kit(tmp_path, ["gsap"])
    assert ok, out
    assert (tmp_path / "vendor" / "gsap" / Path(ready["offline_entry"]).name).is_file()
    assert '<script src="vendor/gsap/gsap.min.js"></script>' in out
    assert "GSAP" in (tmp_path / "vendor" / "LICENSES.md").read_text(encoding="utf-8")


def test_kit_refuses_paths_outside_roots(gt, tmp_path, monkeypatch):
    evil = tmp_path / "secret.txt"
    evil.write_text("x", encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    (data / "library.json").write_text(json.dumps({"roots": [str(tmp_path / "libs")], "items": [
        {"id": "evil", "name": "evil", "license": "MIT", "offline_entry": str(evil)}]}), encoding="utf-8")
    monkeypatch.setattr(gt, "DATA", data)
    out, ok = gt.lib_kit(tmp_path / "proj", ["evil"])
    assert not ok and "برّه" in out
    assert not (tmp_path / "proj" / "vendor" / "evil").exists()


def test_kit_reports_unknown_and_unready(gt, tmp_path):
    out, ok = gt.lib_kit(tmp_path, ["no-such-lib"])
    assert not ok and "مفيش عنصر" in out


def test_kit_copies_es_module_imports(gt, tmp_path, monkeypatch):
    """three.module.js imports ./three.core.js: kit brings every relative import along (keeping sub-folders), and an import
    that points above the module's own folder is reported as a failure, never copied and never a ✓."""
    libs = tmp_path / "libs"
    (libs / "m" / "util").mkdir(parents=True)
    (libs / "n").mkdir()
    (libs / "m" / "lib.module.js").write_text("import {a} from './core.js';\n", encoding="utf-8")
    (libs / "m" / "core.js").write_text('export * from "./util/x.js";\nexport const a = 1;\n', encoding="utf-8")
    (libs / "m" / "util" / "x.js").write_text("export const x = 2;\n", encoding="utf-8")
    (libs / "n" / "n.module.js").write_text("import '../m/core.js';\n", encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()

    def item(i, f):
        return {"id": i, "name": i, "license": "MIT", "commercial_ok": "yes", "offline_kind": "esm", "offline_entry": str(f)}
    (data / "library.json").write_text(json.dumps({"roots": [str(libs)], "items": [
        item("m", libs / "m" / "lib.module.js"), item("n", libs / "n" / "n.module.js")]}), encoding="utf-8")
    monkeypatch.setattr(gt, "DATA", data)
    out, ok = gt.lib_kit(tmp_path / "proj", ["m"])
    v = tmp_path / "proj" / "vendor" / "m"
    assert ok and (v / "core.js").is_file() and (v / "util" / "x.js").is_file(), out
    assert "file://" in out                                   # the CORS note for ES modules
    out, ok = gt.lib_kit(tmp_path / "proj", ["n"])
    assert not ok and "../m/core.js" in out and "✗ n" in out
    assert not (tmp_path / "proj" / "vendor" / "n" / "core.js").exists()


# ---------------------------------------------------------------- golden_tools: studio install (never runs anything)
def _fake_studio(gt, tmp_path, monkeypatch, good_hash=True):
    arc = tmp_path / "prog.zip"
    with zipfile.ZipFile(arc, "w") as z:
        z.writestr("prog-1.0/bin/tool.exe", "not a real program")
    h = hashlib.sha256(arc.read_bytes()).hexdigest()
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    (data / "studio.json").write_text(json.dumps({"programs": [
        {"id": "tool", "name": "Tool", "version": "1.0", "archive": str(arc), "archive_sha256": h if good_hash else "0" * 64,
         "exe": "prog-1.0/bin/tool.exe"}]}), encoding="utf-8")
    monkeypatch.setattr(gt, "DATA", data)
    monkeypatch.setattr(gt, "STUDIO_HOME", tmp_path / "studio")


def test_studio_install_checks_hash_and_unpacks(gt, tmp_path, monkeypatch):
    if not gt.seven_zip():
        pytest.skip("7-Zip not installed")
    _fake_studio(gt, tmp_path, monkeypatch)
    assert gt.studio_state(gt.studio_items()[0]) == "متاح للفك"
    out, ok = gt.studio_install("tool")
    assert ok, out
    cmd, _ = gt.studio_cmd("tool", ["--x", "y"])
    assert cmd[0].endswith("tool.exe") and cmd[1:] == ["--x", "y"]
    assert gt.studio_state(gt.studio_items()[0]) == "جاهز"


def test_studio_install_refuses_wrong_hash(gt, tmp_path, monkeypatch):
    if not gt.seven_zip():
        pytest.skip("7-Zip not installed")
    _fake_studio(gt, tmp_path, monkeypatch, good_hash=False)
    out, ok = gt.studio_install("tool")
    assert not ok and "البصمة" in out
    assert not (tmp_path / "studio" / "tool").exists()


def test_studio_cmd_needs_install(gt, tmp_path, monkeypatch):
    _fake_studio(gt, tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError):
        gt.studio_cmd("tool", [])


def test_cli(gt, capsys):
    assert gt.main(["lib", "find", "gsap"]) == 0
    assert "gsap" in capsys.readouterr().out
    assert gt.main(["studio", "list"]) == 0
    assert "rhubarb" in capsys.readouterr().out
    assert gt.main(["lib", "show", "no-such"]) == 1
    assert gt.main(["nope"]) == 2


def test_forge_is_the_source_of_golden_tools():
    assert (FORGE / "modules" / "golden_tools.py").read_bytes() == (APP / "golden_tools.py").read_bytes()


# ---------------------------------------------------------------- speech sync (time follows speech)
SCRIPT = "@{intro}اللَّهمَّ إنّا نسألك@{/intro} رحمةً من عندك ||\n@{boom!}تَهدي بها قلوبَنا\n@{end}وتجمع بها شملَنا@{/end}\n"
SPOKEN = [("اللهم", 0.20, 0.62), ("انا", 0.66, 0.90), ("نسالك", 0.95, 1.50), ("رحمه", 1.62, 2.05), ("عندك", 2.40, 2.90),
          ("يا", 3.00, 3.10), ("تهدي", 3.30, 3.70), ("بها", 3.72, 3.95), ("قلو", 4.00, 4.25), ("بنا", 4.25, 4.60),
          ("وتجمع", 5.00, 5.50), ("بها", 5.52, 5.75), ("شملنا", 5.80, 6.40)]


def _words(tmp_path, fmt="whisperx"):
    rows = [{"word": w, "start": s, "end": e} for w, s, e in SPOKEN]
    data = {"segments": [{"words": rows}]} if fmt == "whisperx" else rows
    p = tmp_path / "words.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.mark.parametrize("fmt", ["whisperx", "list"])
def test_speech_sync_arabic(gt, tmp_path, fmt):
    res, srt = gt.speech_sync(SCRIPT, _words(tmp_path, fmt), fps=30)
    w = {x["w"]: x for x in res["words"]}
    assert res["stats"]["matched"] == 11 and res["stats"]["script_words"] == 12      # only «من» is missing in the recording
    assert w["اللَّهمَّ"]["start"] == 0.20 and w["رحمةً"]["end"] == 2.05             # hamza / tashkeel / ة normalised
    assert not w["من"]["matched"] and 2.05 <= w["من"]["start"] < w["من"]["end"] <= 2.40   # spread into the gap
    assert (w["قلوبَنا"]["start"], w["قلوبَنا"]["end"]) == (4.00, 4.60)             # «قلو بنا» merged (1:2)
    assert res["ranges"]["intro"]["start"] == 0.20 and res["ranges"]["intro"]["end"] == 1.50
    assert res["ranges"]["end"]["start_f"] == 150 and res["moments"]["boom"]["t"] == 3.30
    assert [c["text"] for c in res["captions"]] == ["اللَّهمَّ إنّا نسألك رحمةً من عندك", "تَهدي بها قلوبَنا", "وتجمع بها شملَنا"]
    assert srt.startswith("1\n00:00:00,200 --> 00:00:02,900\n")


def test_speech_sync_rejects_bad_marks(gt, tmp_path):
    with pytest.raises(ValueError):
        gt.speech_sync("@{a}كلام من غير قفلة", _words(tmp_path))
    with pytest.raises(ValueError):
        gt.speech_sync("كلام @{/b}", _words(tmp_path))


def test_speech_sync_cli_writes_files(gt, tmp_path):
    s = tmp_path / "script.txt"
    s.write_text(SCRIPT, encoding="utf-8")
    assert gt.main(["sync", str(s), str(_words(tmp_path)), str(tmp_path / "out"), "--fps", "25"]) == 0
    d = json.loads((tmp_path / "out" / "sync.json").read_text(encoding="utf-8"))
    assert d["fps"] == 25 and d["moments"]["boom"]["f"] == round(3.30 * 25)
    assert (tmp_path / "out" / "captions.srt").read_text(encoding="utf-8").count("-->") == 3


def test_studio_cmd_blocks_batch_metacharacters(gt, tmp_path, monkeypatch):
    """A .cmd program (gaffer.cmd) gets its arguments re-parsed by cmd.exe (BatBadBut): & | ^ < > % " are refused."""
    if not gt.seven_zip():
        pytest.skip("7-Zip not installed")
    arc = tmp_path / "g.zip"
    with zipfile.ZipFile(arc, "w") as z:
        z.writestr("g/bin/gaffer.cmd", "@echo off")
    data = tmp_path / "data"
    data.mkdir()
    (data / "studio.json").write_text(json.dumps({"programs": [{"id": "g", "name": "G", "archive": str(arc),
        "archive_sha256": hashlib.sha256(arc.read_bytes()).hexdigest(), "exe": "g/bin/gaffer.cmd"}]}), encoding="utf-8")
    monkeypatch.setattr(gt, "DATA", data)
    monkeypatch.setattr(gt, "STUDIO_HOME", tmp_path / "studio")
    assert gt.studio_install("g")[1]
    assert gt.studio_cmd("g", ["mcp", "shot01.gfr"])[0][1:] == ["mcp", "shot01.gfr"]
    for bad in ("a&calc", "x|y", "%PATH%", 'q"w'):
        with pytest.raises(ValueError):
            gt.studio_cmd("g", ["mcp", bad])


def test_studio_records_carry_verified_cautions(gt):
    progs = {p["id"]: p for p in gt.studio_items()}
    assert "UTF-8" in progs["handbrakecli"]["cautions"] and "[Y/N]" in progs["tconverter"]["cautions"]
    assert "phonetic" in progs["rhubarb"]["cautions"]
    assert "friction" not in progs and "glaxnimate" not in progs          # GUI-only / nested archive: library, not studio
    assert all("->" not in p["exe"] and "(" not in p["exe"] for p in progs.values())


# ---------------------------------------------------------------- golden mind (2026-11-14: smarter, bilingual)
def test_golden_mind_prompt_and_effort():
    t = read("app.py")
    assert "## عقل الطائر الذهبي (تفكير فائق بالعربي والإنجليزي)" in t
    assert "Task / Deliverable / Constraints / Done-when" in t and "think start" in t
    assert t.count('_settings.get("effort", "xhigh")') == 6 and '_settings.get("effort", "high")' not in t
    assert t.count('EFFORTS.index("max"):') == 2 and t.count('effort = "max"') == 2
    assert "def _gb_mind_upgrade():" in t and "    _wb_seed()\n    _gb_mind_upgrade()\n    api = Api()" in t
    assert "arabic-captions-khatt" in t and "taste-distillation" in t


def test_golden_mind_upgrade_runs_once(tmp_path):
    """Run the generated _gb_mind_upgrade() against temp settings: medium -> xhigh once, then the owner's choice stays."""
    import ast
    src = read("app.py")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "_gb_mind_upgrade")
    s = tmp_path / "settings.json"
    ns = {"json": json, "SETTINGS": s, "_wb_life": lambda m: None}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "app.py", "exec"), ns)
    s.write_text(json.dumps({"effort": "medium", "model": "x"}), encoding="utf-8")
    ns["_gb_mind_upgrade"]()
    d = json.loads(s.read_text(encoding="utf-8"))
    assert d["effort"] == "xhigh" and d["gb_mind_v1"] is True and d["model"] == "x"
    d["effort"] = "low"
    s.write_text(json.dumps(d), encoding="utf-8")
    ns["_gb_mind_upgrade"]()
    assert json.loads(s.read_text(encoding="utf-8"))["effort"] == "low"        # the owner's later choice is kept


@pytest.mark.parametrize("q,expect", [("والجزيئات", "tsparticles"), ("للانتقالات", "hyperframes-house-motion"), ("particles confetti", "canvas-confetti")])
def test_bilingual_search(gt, q, expect):
    hits = [i["id"] for i in gt.lib_find(q, 10)]
    assert any(expect in h for h in hits), (q, hits)
