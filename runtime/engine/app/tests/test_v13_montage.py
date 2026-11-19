"""v1.3 dogfood fixes in the montage engine (dragon_montage) and its neighbours.

Each test pins one triaged finding from the harvested sessions: «فيديو» planned at 1:1, Kling proposals asking for
an AI likeness of Mayar, an explicit --seconds cut down, «مش بأسلوب شرح» typed as talking-head, no verbatim
requirements, --style hadi / calm failing, blind top-3 stock downloads, the reference grade replacing his colours,
the reference's cut list reduced to a mean, AAC 192k / CRF 18 / no BT.709 in the final, Kling at 21:9.
No network, no owner media; only JSON files in tmp_path."""
import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engines.dragon_montage import common as C  # noqa: E402
import importlib  # noqa: E402
Dr = importlib.import_module("engines.dragon_montage.direct")   # the package exports a function named direct
from engines.dragon_montage import edl as E  # noqa: E402
from engines.dragon_montage import generate as G  # noqa: E402
from engines.dragon_montage import stock as St  # noqa: E402
from engines.dragon_montage import taste as T  # noqa: E402
from engines.dragon_montage import think as Th  # noqa: E402

FACTS0 = {"clips": 0, "speech_coverage": 0.0, "group_ratio": 0.0, "faces_ratio": 0.0, "usable_s": 0.0}


# ---------------------------------------------------------------- think: platform, negation, seconds, requirements

@pytest.mark.parametrize("task", ["اعمل فيديو لميار على أغنية وطنية", "3 فيديوهات سينمائية لميار",
                                  "فيديوهات الرياض في الشتا", "فديو حماسي"])
def test_video_word_is_never_the_square_platform(task):
    em = Th.editor_mind()
    assert "فيد" not in em["platform_words"]["square"]
    hit = next((p for p, ws in em["platform_words"].items() if Th.word_hits(task, ws)), None)
    assert hit is None                                     # -> the reel default (9:16)


def test_square_only_when_asked():
    em = Th.editor_mind()
    assert Th.word_hits("اعمله مربع للفيسبوك", em["platform_words"]["square"]) == 1
    assert Th.word_hits("square post", em["platform_words"]["square"]) == 1
    assert Th.word_hits("ريل لميار", em["platform_words"]["reel"]) >= 1


def test_negated_keyword_does_not_type_the_job_and_goes_to_avoid():
    em = Th.editor_mind()
    task = "3 فيديوهات سينمائية مش بأسلوب شرح لميار"
    ct, why = Th.pick_content_type(task, FACTS0, em)
    assert ct != "talking-head", why
    kept, neg = Th.split_negated(task)
    assert "شرح" not in kept and any("شرح" in n for n in neg)
    assert any("شرح" in a for a in Th.avoid_from_task(task))
    assert Th.pick_content_type("فيديو شرح للطلاب", FACTS0, em)[0] == "talking-head"   # not negated: still works


def test_explicit_seconds_are_never_shrunk():
    plat = {"default_seconds": 30, "seconds": [5, 90]}
    f = {**FACTS0, "usable_s": 6.0}
    sec, why = Th.pick_seconds("", 21, plat, f)
    assert sec == 21 and "ناقص" in why                    # the owner's number, plus a warning
    sec2, _ = Th.pick_seconds("", None, plat, f)
    assert sec2 < 21                                        # without --seconds the old fit to the footage stays


def test_brief_keeps_the_request_word_for_word(tmp_path):
    task = "موشن لميار على أغنية وطنية، مش بأسلوب شرح"
    br = Th.build_brief(tmp_path, task, None, 40)
    assert br["requirements"] == [task] and br["owner_seconds"] == 40.0 and br["target_seconds"] == 40.0
    assert br["platform"] == "reel" and br["aspect"] == "9:16"


def test_coverage_flags_a_hook_that_is_the_request(tmp_path):
    from engines.dragon_montage.pipeline import coverage
    task = "ريل لميار"
    C.write(tmp_path, "brief", C.new("brief", task=task, platform="reel", aspect="9:16", target_seconds=30,
                                     feeling="inspiring", content_type="montage", requirements=[task]))
    C.write(tmp_path, "concepts", C.new("concepts", concepts=[{"id": "A", "hook": {"text": "ريل لميار"}}],
                                        decision={"chosen": "A"}))
    cv = coverage(tmp_path)
    assert cv["verdict"] == "WEAK" and any("WEAK hook" in p for p in cv["problems"])
    C.write(tmp_path, "concepts", C.new("concepts", concepts=[{"id": "A", "hook": {"text": "بنت عندها 11 سنة"}}],
                                        decision={"chosen": "A"}))
    assert coverage(tmp_path)["verdict"] == "ok"


# ---------------------------------------------------------------- generate: no AI likeness of a real person

def _gen_job(tmp_path, task, faces):
    C.write(tmp_path, "brief", C.new("brief", task=task, platform="reel", aspect="9:16", target_seconds=30,
                                     feeling="warm", content_type="montage"))
    shot = {"id": "c01-s001", "start": 0.0, "end": 4.0, "faces": faces, "thumb": "thumbs/c01.jpg",
            "quality": {"score": 0.8}}
    C.write(tmp_path, "analysis", C.new("analysis", clips=[{"id": "c01", "duration": 4.0, "shots": [shot]}],
                                        music={"path": None}, tools_used=[], missing=[]))


@pytest.mark.parametrize("task,faces", [("ريل عادي عن البحر", 1), ("موشن لميار وأغنية وطنية", 0)])
def test_generate_never_asks_for_a_real_person(tmp_path, task, faces):
    _gen_job(tmp_path, task, faces)
    doc = G.gaps(tmp_path)
    vids = [p for p in doc["proposals"] if p["kind"] == "video"]
    assert vids, doc["gaps"]
    for p in vids:
        assert "Exactly 0 people" in p["prompt"] and "Exactly 1 person" not in p["prompt"]
        assert p["reference_still"] is None and p["people"] == 0 and p["forbidden_subject"]
        assert p["mcp_call"]["args"]["mode"] == "text-to-video"
    assert doc["context"]["forbidden_subject"] == ("minor" if "ميار" in task else "real-person")
    assert "عمره ما يطلّع شبه بالـ AI لشخص حقيقي" in (tmp_path / "GENERATE_AR.md").read_text(encoding="utf-8")


def test_generate_keeps_people_free_footage_unchanged(tmp_path):
    _gen_job(tmp_path, "ريل عن البحر", 0)
    p = next(p for p in G.gaps(tmp_path)["proposals"] if p["kind"] == "video")
    assert p["reference_still"] == "thumbs/c01.jpg" and "forbidden_subject" not in p


# ---------------------------------------------------------------- direct: reach the owner's length, reference cuts

def _edl(lens, kinds=None):
    evs, t = [], 0.0
    for i, L in enumerate(lens):
        evs.append({"id": f"e{i}", "clip": "c01", "src_in": 0.0, "src_out": L, "rec_in": t, "reason": "x",
                    "kind": (kinds or ["broll"] * len(lens))[i], "transition_in": {"id": "cut"}})
        t += L
    return {"events": evs}


def test_reach_target_runs_on_then_slows_the_last_shot():
    edl = _edl([3.0, 3.0])
    plans = [{"shot_end": 3.0}, {"shot_end": 4.0}]
    r = Dr.reach_target(edl, plans, 9.0)
    assert r["extended_s"] == pytest.approx(1.0) and r["speed"] is not None
    assert edl["duration"] == pytest.approx(9.0, abs=0.02) and r["short_by"] <= 0.02
    sp = _edl([3.0, 3.0], ["broll", "speech"])
    Dr.reach_target(sp, [{"shot_end": 3.0}, {"shot_end": 3.0}], 9.0)
    assert sp["events"][-1]["speed"] >= 0.9                # a voice is never slowed more than 10%


def test_reference_exact_cuts_at_the_reference_times():
    edl = _edl([3.5, 3.5, 3.5])
    ref = {"transitions": [{"at": 8.0}, {"at": 12.0}], "reference": {"duration": 15.0}}
    plans = [{"shot_end": 20.0}] * 3
    r = Dr.reference_exact(edl, plans, ref)
    assert r["slots"] == [8.0, 4.0, 3.0] and r["cuts_at"] == [8.0, 12.0]


# ---------------------------------------------------------------- stock: place names, no blind top-N

def test_stock_match_all_for_a_place_and_no_blind_fetch(tmp_path):
    assert St.match_mode("Riyadh skyline winter") == "all" and St.match_mode("coffee pouring") == "any"
    C.save(tmp_path / "stock.json", {"results": [{"id": "mixkit:1"}], "downloaded": []})
    assert St.fetch(tmp_path) == []                        # default: nothing taken without ids
    with pytest.raises(SystemExit, match="--ids"):
        St.main(["fetch", "--job", str(tmp_path)])


# ---------------------------------------------------------------- taste: mood aliases, reference grade

@pytest.mark.parametrize("alias", ["calm", "هادي", "clean", "nil", "minimal", "editorial"])
def test_style_aliases_give_quiet_rows(alias):
    rows = T.alias_rows(alias, T.rank("calm", 0.25, "reel", "montage", ""))
    assert rows, alias
    for r in rows[:10]:
        assert not T.is_loud(r)
        assert not {"xfade-pixelize", "xfade-hlslice"} & set(r["transition_ids"])


def test_pick_with_a_calm_alias_and_the_default_avoid_loud_looks(tmp_path):
    C.write(tmp_path, "brief", C.new("brief", task="موشن لميار", platform="reel", aspect="9:16", target_seconds=30,
                                     feeling="epic", content_type="montage", energy=0.8))
    look = T.pick(tmp_path, "هادي")
    assert {t["id"] for t in look["transitions"]} <= T.CALM_TRANSITIONS
    assert "مزاج" in look["why"]
    row = next(r for r in T.rank("epic", 0.8, "reel", "montage", "") if r["id"] == T.pick(tmp_path)["style_id"])
    assert not T.is_loud(row)
    with pytest.raises(SystemExit, match="taste list --calm"):
        T.pick(tmp_path, "no-such-style")


def test_reference_grade_only_when_asked(tmp_path):
    ov = C.new("look", style_id="mimic-reference", grade={"id": "teal-orange"}, transitions=[{"id": "cut"}], captions={})
    C.save(tmp_path / "look_override.json", ov)
    base = {"grade": {"id": "none", "engine": "ffmpeg"}, "why": "", "transitions": [], "camera": []}
    if not T.resolve("grade", "teal-orange"):
        pytest.skip("grade id not in this vocabulary")
    kept = T._apply_override(tmp_path, json.loads(json.dumps(base)), {"task": "مونتاج على أغنيتي"})
    assert kept["grade"]["id"] == "none" and kept["reference_grade"]["applied"] is False
    took = T._apply_override(tmp_path, json.loads(json.dumps(base)), {"task": "نفس الألوان بالظبط"})
    assert took["grade"]["id"] != "none"


# ---------------------------------------------------------------- export standard, Kling ratio

def test_final_render_meets_the_owner_standard():
    src = (ROOT / "engines" / "dragon_montage" / "render.py").read_text(encoding="utf-8")
    assert '"-b:a", "320k"' in src and '"192k"' not in src
    assert '"slow"' in src and '"17"' in src and "colorprim=bt709" in src


def test_kling_director_defaults_to_9_16():
    from engines import kling_director as K
    assert inspect.signature(K.build).parameters["ratio"].default == "9:16"
    main = (ROOT / "engines" / "kling_director" / "__main__.py").read_text(encoding="utf-8")
    assert 'default="9:16"' in main and 'default="21:9"' not in main


def test_mux_reports_padding(tmp_path):
    from engines import deliver
    assert "padded_s" in inspect.getsource(deliver.mux)
