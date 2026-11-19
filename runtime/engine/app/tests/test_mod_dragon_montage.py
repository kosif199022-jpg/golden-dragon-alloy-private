"""Parity gate for engines/dragon_montage: the OLD kosif-dragon-montage scripts and the NEW package run on the same
synthetic clips (ffmpeg testsrc/sine) and their outputs are compared with numbers.

OLD is read-only (KOSIF_DRAGON_MONTAGE_OLD, default C:/Users/cinde/kosif-tool/.claude/skills/kosif-dragon-montage);
it runs with -B so no bytecode lands in it, and every job folder lives in tmp_path. On ffmpeg >= 7 the old render's
`-filter_complex_script` (removed in ffmpeg 9) is rewritten to `-/filter_complex` by a tiny in-process shim; nothing
else of the old code is touched.
"""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OLD = Path(os.environ.get("KOSIF_DRAGON_MONTAGE_OLD", r"C:\Users\cinde\kosif-tool\.claude\skills\kosif-dragon-montage"))
OLD_SCRIPTS = OLD / "scripts"

try:
    from engines.media import exe
    exe("ffmpeg"), exe("ffprobe")
    HAVE_FFMPEG = True
except FileNotFoundError:
    HAVE_FFMPEG = False
HAVE = {m: importlib.util.find_spec(m) is not None for m in ("cv2", "numpy", "librosa", "scenedetect", "PIL")}
needs_old = pytest.mark.skipif(not OLD_SCRIPTS.is_dir(), reason="old kosif-dragon-montage not on this machine")
needs_media = pytest.mark.skipif(not (HAVE_FFMPEG and HAVE["cv2"] and HAVE["numpy"]), reason="ffmpeg + opencv needed")
needs_librosa = pytest.mark.skipif(not HAVE["librosa"], reason="librosa needed for the music beat grid")
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
TASK = "اعمل ريل قصير حماسي"
WORDS = [("السر", 0.3, 0.7), ("اللي", 0.75, 1.0), ("محدش", 1.05, 1.5), ("قالهولك", 1.55, 2.1), ("عن", 2.6, 2.8),
         ("المونتاج", 2.85, 3.4), ("لازم", 3.9, 4.2), ("تعرفه", 4.25, 4.8), ("النهارده", 4.85, 5.4), ("تابعني", 6.2, 6.7),
         ("عشان", 6.75, 7.0), ("تعرف", 7.05, 7.5)]


# ------------------------------------------------------------------------------------------------ runners
def run_old(script: str, *args, timeout=900) -> subprocess.CompletedProcess:
    res = subprocess.run([sys.executable, "-B", str(OLD_SCRIPTS / script), *map(str, args)], capture_output=True,
                         text=True, encoding="utf-8", errors="replace", env=ENV, timeout=timeout)
    assert res.returncode == 0, f"OLD {script} {args}: {res.stderr[-2000:]}{res.stdout[-800:]}"
    return res


SHIM = """import sys
sys.path.insert(0, sys.argv[1])
import dm_common as C
_run = C.run
def run(job, station, tool, argv, **kw):
    return _run(job, station, tool, [{opt!r} if a == '-filter_complex_script' else a for a in argv], **kw)
C.run = run
import dm_render
sys.exit(dm_render.main(sys.argv[2:]))
"""


def run_old_render(job: Path, *extra):
    from engines.dragon_montage.render import graph_file_option
    res = subprocess.run([sys.executable, "-B", "-c", SHIM.format(opt=graph_file_option()), str(OLD_SCRIPTS), "render", "--job",
                          str(job), *extra], capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, timeout=1800)
    assert res.returncode == 0 and '"rendered"' in res.stdout, f"OLD render: {res.stderr[-2000:]}{res.stdout[-1500:]}"


def run_new(*args, timeout=900, env=None) -> subprocess.CompletedProcess:
    res = subprocess.run([sys.executable, "-m", "engines.dragon_montage", *map(str, args)], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace", env={**ENV, **(env or {})}, timeout=timeout)
    assert res.returncode == 0, f"NEW {args}: {res.stderr[-2000:]}{res.stdout[-800:]}"
    return res


def jload(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def diff(a, b, tol=1e-6, path="$") -> list:
    """Every place where two JSON values differ (floats within tol)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = [f"{path}: keys {sorted(set(a) ^ set(b))}"] if set(a) != set(b) else []
        return out + [d for k in set(a) & set(b) for d in diff(a[k], b[k], tol, f"{path}.{k}")]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: len {len(a)} != {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, tol, f"{path}[{i}]")]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return [] if abs(a - b) <= tol else [f"{path}: {a} != {b}"]
    return [] if a == b else [f"{path}: {str(a)[:120]!r} != {str(b)[:120]!r}"]


def drop(obj, *keys):
    obj = copy.deepcopy(obj)
    for k in keys:
        target, parts = obj, k.split(".")
        for p in parts[:-1]:
            target = target.get(p, {}) if isinstance(target, dict) else {}
        if isinstance(target, dict):
            target.pop(parts[-1], None)
    return obj


def copy_job(src: Path, dst: Path, files=("analysis.json", "brief.json", "concepts.json", "look.json", "edl.json")) -> Path:
    dst.mkdir(parents=True, exist_ok=True)
    for f in files:
        if (src / f).exists():
            shutil.copy2(src / f, dst / f)
    return dst


# ------------------------------------------------------------------------------------------------ fixtures
@pytest.fixture(scope="module")
def media(tmp_path_factory):
    if not HAVE_FFMPEG:
        pytest.skip("ffmpeg needed")
    from engines.dragon_montage import make_test_clip
    from engines.media import ffmpeg
    d = tmp_path_factory.mktemp("مونتاج")            # an Arabic path on purpose
    a = make_test_clip(d / "a clip.mp4", 8.0, tone=440)
    b = make_test_clip(d / "b.mp4", 6.0, tone=660, color="rgbtestsrc")
    m = d / "beat.wav"                                # decaying pings every 0.5 s = 120 BPM
    ffmpeg("-f", "lavfi", "-i", "aevalsrc='0.8*sin(2*PI*880*t)*exp(-30*mod(t,0.5))':s=44100:d=12", m)
    return {"dir": d, "a": a, "b": b, "music": m}


@pytest.fixture(scope="module")
def analyses(media, tmp_path_factory):
    """OLD and NEW analyze on the same clips + music."""
    if not (OLD_SCRIPTS.is_dir() and HAVE["cv2"] and HAVE["librosa"]):
        pytest.skip("old scripts, opencv and librosa needed")
    root = tmp_path_factory.mktemp("analyze")
    args = ["--clip", media["a"], "--clip", media["b"], "--music", media["music"], "--no-transcribe"]
    run_old("dm_analyze.py", "--job", root / "old", *args)
    run_new("station", "analyze", "--job", root / "new", *args)
    return jload(root / "old" / "analysis.json"), jload(root / "new" / "analysis.json"), root


def scenario(analysis: dict, kind: str) -> dict:
    """montage: the measured analysis with its music bed; speech: no music, timed Arabic words on c01."""
    a = copy.deepcopy(analysis)
    if kind == "speech":
        a["music"] = {"path": None, "bpm": None, "beats": [], "downbeats": []}
        a["clips"][0]["words"] = [{"w": w, "start": s, "end": e, "conf": 0.9} for w, s, e in WORDS]
    return a


@pytest.fixture(scope="module", params=["montage", "speech"])
def chains(request, analyses, tmp_path_factory):
    """OLD and NEW stations 2-5b from one identical analysis.json."""
    old_an, _, _ = analyses
    root = tmp_path_factory.mktemp(f"chain_{request.param}")
    jobs = {}
    for side in ("old", "new"):
        job = root / side
        job.mkdir()
        (job / "analysis.json").write_text(json.dumps(scenario(old_an, request.param), ensure_ascii=False), encoding="utf-8")
        jobs[side] = job
    task = TASK if request.param == "montage" else "اعمل ريل كلام عن سر المونتاج"
    o, n = jobs["old"], jobs["new"]
    run_old("dm_think.py", "brief", "--job", o, "--task", task, "--platform", "reel", "--seconds", 8)
    run_new("station", "brief", "--job", n, "--task", task, "--platform", "reel", "--seconds", 8)
    for script, station, sub in (("dm_think.py", "concepts", ["concepts"]), ("dm_taste.py", "taste", ["pick"]),
                                 ("dm_direct.py", "direct", ["direct"]), ("dm_generate.py", "generate", ["gaps"]),
                                 ("dm_storyboard.py", "storyboard", ["storyboard"])):
        run_old(script, *sub, "--job", o)
        run_new("station", station, "--job", n)
    return {"kind": request.param, "old": o, "new": n, "root": root}


# ------------------------------------------------------------------------------------------------ pure parity
@needs_old
def test_hook_score_matches_reel_tools():
    from engines.dragon_montage.hooks import score_hook
    path = OLD.parent / "kosif-reel-hooks" / "scripts" / "reel_tools.py"
    if not path.exists():
        pytest.skip("reel_tools.py not present")
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("old_reel_tools", path)
    rt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rt)
    hooks = [h["template"] for h in jload(ROOT / "engines" / "dragon_montage" / "data" / "hooks_ar.json")["hooks"]]
    lines = hooks + [w for w, _, _ in WORDS] + ["خسرت ٤٠٠٠ جنيه في عقد ناقصه سطر واحد.", "اهلا يا جماعه النهارده هنتكلم",
                                                "Stop wasting 3 hours on edits", "في الفيديو ده هوريكم السر", "متعملش كده تاني",
                                                "انت بتضيع وقتك #مونتاج", "I lost $400 in one day", "ليه محدش قالك ده قبل كده؟"]
    for text in lines:
        o, n = rt.score_hook(text), score_hook(text)
        assert (o["score"], o["verdict"], o["weakest"]) == (n["score"], n["verdict"], n["weakest"]), text
        assert {k: v["score"] for k, v in o["checks"].items()} == {k: v["score"] for k, v in n["checks"].items()}, text


@needs_old
def test_doctor_verdicts_match():
    res = subprocess.run([sys.executable, "-B", str(OLD_SCRIPTS / "dm_doctor.py"), "doctor", "--json"], capture_output=True,
                         text=True, encoding="utf-8", env=ENV)
    o = json.loads(res.stdout)
    n = json.loads(subprocess.run([sys.executable, "-m", "engines.dragon_montage", "doctor", "--json"], cwd=ROOT,
                                  capture_output=True, text=True, encoding="utf-8", env=ENV).stdout)
    assert [t["id"] for t in o["tools"]] == [t["id"] for t in n["tools"]]
    # a tool the old check found inside the old repo itself (its node_modules, side venvs) belongs to that repo
    local = {t["id"] for t in o["tools"] if str(t.get("where") or "").lower().startswith(str(OLD.parents[2]).lower())}
    po = {t["id"]: t["present"] for t in o["tools"] if t["id"] not in local}
    pn = {t["id"]: t["present"] for t in n["tools"] if t["id"] not in local}
    assert po == pn, diff(po, pn)
    assert o["missing_required"] == n["missing_required"] and o["ready"] == n["ready"]
    lv = lambda r: {k: (v["level"], sorted(set(v["missing_recommended"]) - local)) for k, v in r["stations"].items()}  # noqa: E731
    assert lv(o) == lv(n)
    plan = subprocess.run([sys.executable, "-m", "engines.dragon_montage", "doctor", "install-plan", "--os", "windows", "--all"],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=ENV).stdout
    assert "winget install -e --id Gyan.FFmpeg" in plan


# ------------------------------------------------------------------------------------------------ station parity
@needs_old
@needs_media
@needs_librosa
def test_analyze_parity(analyses):
    o, n, _ = analyses
    assert len(o["clips"]) == len(n["clips"]) == 2
    assert sorted(o["tools_used"]) == sorted(n["tools_used"]) and sorted(o["missing"]) == sorted(n["missing"])
    assert not diff(drop(o, "tools_used", "missing"), drop(n, "tools_used", "missing"), tol=1e-3)
    shots = [s for c in n["clips"] for s in c["shots"]]
    assert len(shots) >= 4 and all(s["quality"]["score"] is not None and s["thumb"] for s in shots)
    assert n["music"]["bpm"] and abs(n["music"]["bpm"] - 120) < 3 and len(n["music"]["beats"]) >= 18


@needs_old
@needs_media
def test_brief_concepts_look_parity(chains):
    o, n = chains["old"], chains["new"]
    for kind in ("brief", "concepts", "look"):
        d = diff(jload(o / f"{kind}.json"), jload(n / f"{kind}.json"))
        assert not d, f"{chains['kind']} {kind}: {d[:8]}"
    council = (n / "council_prompt.md").read_text(encoding="utf-8")
    assert council.count("```") >= 10 and "STANDARD" in council


@needs_old
@needs_media
def test_edl_parity(chains):
    o, n = jload(chains["old"] / "edl.json"), jload(chains["new"] / "edl.json")
    d = diff(o, n)
    assert not d, f"{chains['kind']} edl: {d[:8]}"
    assert n["events"] and all(e["reason"].strip() for e in n["events"])
    if chains["kind"] == "speech":
        assert n["events"][0]["kind"] == "speech" and n["captions"]["enabled"]


@needs_old
@needs_media
def test_generate_and_storyboard_parity(chains):
    o, n = jload(chains["old"] / "generate.json"), jload(chains["new"] / "generate.json")
    strip = lambda g: [{k: v for k, v in p.items() if k != "lint"} for p in g["proposals"]]  # noqa: E731
    assert not diff(o["gaps"], n["gaps"]) and not diff(o["context"], n["context"])
    assert not diff(strip(o), strip(n))
    po, pn = jload(chains["old"] / "preview" / "plan.json"), jload(chains["new"] / "preview" / "plan.json")
    assert not diff(po, pn)
    assert (chains["new"] / "preview" / "storyboard.jpg").stat().st_size > 5000


@needs_old
@needs_media
def test_edl_converters_parity(chains):
    o, n = chains["old"], chains["new"]
    for to in ("timeline", "pve", "words"):
        run_old("dm_edl.py", "convert", "--job", o, "--to", to)
        run_new("tool", "edl", "convert", "--job", n, "--to", to)
        assert not diff(jload(o / f"edl.{to}.json"), jload(n / f"edl.{to}.json")), to
    tl = n / "edl.timeline.json"
    from engines.dragon_montage import edl as E
    back = E.from_timeline(jload(tl), jload(n / "analysis.json"))
    assert [(e["src_in"], e["src_out"]) for e in back["events"]] == [(e["src_in"], e["src_out"]) for e in jload(n / "edl.json")["events"]]


@pytest.fixture(scope="module")
def renders(chains, tmp_path_factory):
    """OLD and NEW render of the same job files (OLD's), then OLD and NEW review of the OLD render."""
    root = tmp_path_factory.mktemp(f"render_{chains['kind']}")
    o, n = copy_job(chains["old"], root / "old"), copy_job(chains["old"], root / "new")
    run_old_render(o, "--fast", "--no-export")
    # same caption font files as the old render (it ships Cairo-400 that the new repo's font folder lacks)
    fonts = OLD.parents[0] / "kosif-superpowers" / "vendor" / "100-superskills" / "skills" / "kosif-mimic" / "assets" / "fonts"
    run_new("station", "render", "--job", n, "--fast", "--no-export", timeout=1800,
            env={"DRAGON_FONT_DIRS": str(fonts)} if fonts.is_dir() else None)
    ro, rn = copy_job(o, root / "review_old"), copy_job(o, root / "review_new")
    for r in (ro, rn):
        shutil.copytree(o / "render", r / "render")
        shutil.copy2(o / "render.json", r / "render.json")
    run_old("dm_review.py", "review", "--job", ro, "--round", 1)
    run_new("station", "review", "--job", rn, "--round", 1)
    return {"kind": chains["kind"], "old": o, "new": n, "review_old": ro, "review_new": rn}


@needs_old
@needs_media
def test_render_parity(renders):
    from engines.dragon_montage import qc
    from engines.media import probe
    o, n = jload(renders["old"] / "render.json"), jload(renders["new"] / "render.json")
    keys = ("final", "width", "height", "fps", "duration", "edl_duration", "events", "events_out", "muted", "music",
            "caption_cues", "captions_ass", "caption_safe_area", "grade")
    d = diff({k: o.get(k) for k in keys}, {k: n.get(k) for k in keys})
    assert not d, d[:8]
    lo, ln = o["loudness"]["measured_before"]["limiter"], n["loudness"]["measured_before"]["limiter"]
    assert abs(lo["output_true_peak"] - ln["output_true_peak"]) <= 0.3
    fo, fn = renders["old"] / o["final"], renders["new"] / n["final"]
    do, dn = (float(probe(f)["format"]["duration"]) for f in (fo, fn))
    assert abs(do - dn) <= 0.05, (do, dn)
    sim = qc.similarity(fo, fn, vmaf="libvmaf" in subprocess.run([exe("ffmpeg"), "-hide_banner", "-filters"],
                                                                 capture_output=True, text=True).stdout)
    renders["similarity"] = sim
    print(f"\n[{renders['kind']}] duration old {do:.3f} new {dn:.3f}  similarity {sim}")
    assert sim["ssim"] >= 0.98, sim
    if sim.get("vmaf") is not None:
        assert sim["vmaf"] >= 95, sim
    assert n["verify"]["pass"] in (True, False) and n["verify"]["width"] == n["width"]


@needs_old
@needs_media
def test_review_and_apply_review_parity(renders):
    ro, rn = jload(renders["review_old"] / "review.json"), jload(renders["review_new"] / "review.json")
    assert [(c["id"], c["pass"]) for c in ro["checks"]] == [(c["id"], c["pass"]) for c in rn["checks"]]
    fx = lambda r: [(f["event"], f["action"], f["check"], f.get("src_in"), f.get("src_out"), f.get("seconds")) for f in r["fixes"]]  # noqa: E731
    assert fx(ro) == fx(rn)
    assert (ro["verdict"], ro["score"], ro["frames"]) == (rn["verdict"], rn["score"], rn["frames"])
    assert not diff(ro["measured"], rn["measured"], tol=0.05)
    if rn["fixes"]:
        run_old("dm_direct.py", "direct", "--job", renders["review_old"], "--apply-review")
        run_new("station", "direct", "--job", renders["review_new"], "--apply-review")
        eo, en = jload(renders["review_old"] / "edl.json"), jload(renders["review_new"] / "edl.json")
        d = diff(eo, en)
        assert not d, d[:8]


# ------------------------------------------------------------------------------------------------ new-only behaviour
@needs_media
def test_edit_pipeline_end_to_end(media, tmp_path):
    job = tmp_path / "تنين job"
    out = json.loads(run_new("edit", TASK, "--clip", media["a"], "--clip", media["b"], "--job", job, "--platform", "reel",
                             "--seconds", 8, "--no-transcribe", "--preview", "--rounds", 2, timeout=1800).stdout.strip().splitlines()[-1])
    assert Path(out["final"]).is_file()
    from engines.dragon_montage import read
    for kind in ("analysis", "brief", "concepts", "look", "edl", "render", "review"):
        read(job, kind)
    assert "الأرقام بأمانة" in (job / "report.md").read_text(encoding="utf-8")
    assert "rounds" in jload(job / "job.json")
    assert any(json.loads(x)["owner_media"] for x in (job / "receipts.jsonl").read_text(encoding="utf-8").splitlines())


@needs_media
def test_mimic_writes_rhythm_and_look(media, tmp_path):
    run_new("station", "mimic", "--job", tmp_path, "--reference", media["a"])
    rh, lk = jload(tmp_path / "reference_rhythm.json"), jload(tmp_path / "look_override.json")
    assert rh["stats"]["shot_count"] == 2 and abs(rh["stats"]["mean_shot_s"] - 4.0) < 0.2
    from engines.dragon_montage import validate
    validate("look", lk)
    assert lk["transitions"] == [{"id": "cut"}]


def test_stock_uses_a_configured_client_without_network(tmp_path):
    fake = tmp_path / "fake_ff.py"
    fake.write_text("import json, pathlib, sys\nd = pathlib.Path('out/free-footage'); d.mkdir(parents=True, exist_ok=True)\n"
                    "(d / 'last_search.json').write_text(json.dumps({'results': [\n"
                    " {'id': 'a:1', 'licence': {'verified': False}, 'width': 1920, 'height': 1080},\n"
                    " {'id': 'b:2', 'licence': {'verified': True, 'commercial': True}, 'width': 1280, 'height': 720}]}))\n",
                    encoding="utf-8")
    env = {**ENV, "DRAGON_FREE_FOOTAGE": str(fake)}
    res = subprocess.run([sys.executable, "-m", "engines.dragon_montage", "station", "stock-search", "--job", tmp_path / "job",
                          "--query", "coffee"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["top"] == ["b:2", "a:1"]          # verified commercial licence first
    res = subprocess.run([sys.executable, "-m", "engines.dragon_montage", "station", "stock-search", "--job", tmp_path / "job2",
                          "--query", "x"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                         env={k: v for k, v in ENV.items() if k != "DRAGON_FREE_FOOTAGE"})
    assert res.returncode != 0 and "DRAGON_FREE_FOOTAGE" in res.stderr


def test_cli_lists_the_old_subcommands():
    res = subprocess.run([sys.executable, "-m", "engines.dragon_montage", "--help"], cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", env=ENV)
    for sub in ("edit", "plan", "go", "doctor", "station"):
        assert sub in res.stdout
    for name in ("analyze", "brief", "concepts", "taste", "direct", "render", "review", "generate", "mimic", "stock-search",
                 "stock-fetch", "storyboard"):
        assert name in res.stdout
