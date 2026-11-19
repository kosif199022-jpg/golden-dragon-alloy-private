"""Tests for Dragon Character Memory. They run the real pipeline on the demo character (once per session) and measure it.
The demo's ground truth is read HERE only, to score the tracker; the tool itself never opens it.
Reuse an existing run with  DCM_DEMO_DIR=path  (it must contain REPORT.json)."""
import json, os, shutil, subprocess, sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import dcm  # noqa: E402

wrap = lambda a: (a + 180) % 360 - 180


@pytest.fixture(scope="session")
def demo(tmp_path_factory):
    d = os.environ.get("DCM_DEMO_DIR")
    if d and (Path(d) / "REPORT.json").is_file():
        return Path(d)
    out = tmp_path_factory.mktemp("dcm_demo")
    dcm.cmd_demo(out)
    return out


@pytest.fixture(scope="session")
def data(demo):
    j = lambda p: json.loads((demo / p).read_text(encoding="utf-8"))
    return {"dir": demo, "frames": j("work/frames.json"), "tracks": j("work/tracks.json"), "redraw": j("work/redraw_report.json"), "rebuild": j("work/rebuild_report.json"),
            "mem": j("character_memory.json"), "gt": j("reference/ground_truth.json")["frames"], "scene": j("new_scene/new_scene_report.json"),
            "identity": j("identity_work/identity_report.json")}


# ---- 1. frames and timing
def test_every_frame_extracted_with_its_original_time(data):
    f = data["frames"]
    assert f["count"] == 144 and len(f["frames"]) == 144
    t = np.array([x["t"] for x in f["frames"]])
    assert np.all(np.diff(t) > 0)
    assert np.abs(t - np.arange(144) / 24).max() < 1e-3


# ---- 2. redraw quality
def test_redraw_is_close_to_the_reference(data):
    r = data["redraw"]
    assert r["psnr_db"]["mean"] >= 36 and r["psnr_db"]["min"] >= 33
    assert r["ssim"]["min"] >= 0.99
    assert r["fg_iou"]["min"] >= 0.98


def test_redraw_is_real_vector_data(data):
    svg = (data["dir"] / "work" / "redraw_svg" / "f00060.svg").read_text(encoding="utf-8")
    assert svg.count("<path") >= 8 and 'fill-rule="evenodd"' in svg


# ---- 3. no jitter that the source did not have
def test_redraw_adds_no_jitter(data):
    assert data["redraw"]["centroid_err_px"]["max"] <= 0.5


def test_still_parts_stay_still(data):
    x = np.array([f["parts"]["torso"]["c"][0] for f in data["tracks"]["frames"][:12]])      # the character only breathes here
    assert x.std() <= 0.8


# ---- 4. the tracker against ground truth
def test_tracker_matches_ground_truth(data):
    tr, gt = data["mem"]["pose_track"], data["gt"]
    err = lambda k, g, ang=True: np.array([wrap(a[k] - b[g]) if ang else a[k] - b[g] for a, b in zip(tr, gt)])
    assert np.abs(err("x", "x", False)).mean() <= 2.0 and np.abs(err("y", "y", False)).mean() <= 2.0
    assert np.abs(err("torso", "torso")).mean() <= 1.5
    for k, g in (("arm_L", "armL"), ("arm_R", "armR"), ("leg_L", "legL"), ("leg_R", "legR")):
        seen = np.array([k not in a["interpolated"] for a in tr])
        assert np.abs(err(k, g)[seen]).mean() <= 4.0, k


def test_expressions_are_read_correctly(data):
    fr = data["tracks"]["frames"]; gt = data["gt"]
    blink = [f["frame"] for f in fr if f["expr"]["eyes"] == "closed"]
    truth = [g["frame"] for g in gt if g["eye"] < 0.3]
    assert set(blink) <= set(range(min(truth) - 1, max(truth) + 2)) and len(set(blink) & set(truth)) >= 0.7 * len(truth)
    mouth_ok = [f["expr"]["mouth"] == g["mouth"] for f, g in zip(fr, gt) if f["expr"]["mouth"] is not None]
    assert np.mean(mouth_ok) >= 0.93
    assert any(f["expr"]["eyes"] == "wide" for f in fr[132:])


def test_hidden_eye_is_reported_as_hidden_not_as_closed(data):
    occ = [f for f in data["tracks"]["frames"] if f["expr"]["eyes_occluded"]]
    assert occ, "the wave passes in front of the face: some frames must report an occluded eye"
    assert all(36 <= f["frame"] <= 84 for f in occ)


# ---- 5. memory: content, honesty, round trip
def test_memory_has_the_required_sections(data):
    m = data["mem"]
    for k in ("identity", "parts", "layers", "expressions", "poses", "clips", "timeline", "pose_track", "confidence", "synthesized", "source"):
        assert k in m, k
    assert set(m["parts"]) >= {"torso", "head", "hair", "arm_L", "arm_R", "leg_L", "leg_R"}
    for k, p in m["parts"].items():
        assert "template_frame" in p and "confidence" in p and len(p["template"]) >= 4, k
    assert set(m["expressions"]["eyes"]) >= {"open", "closed"} and set(m["expressions"]["mouth"]) >= {"closed", "smile", "open"}
    assert all(e["observed"] and "source_frame" in e for grp in m["expressions"].values() for e in grp.values())
    assert {"walk_cycle", "wave"} <= set(m["clips"]) and all(c["observed"] for c in m["clips"].values())
    acts = {a["action"] for a in m["timeline"]}
    assert {"walk", "wave", "blink", "idle"} <= acts
    assert "sit" not in json.dumps(m["poses"]) and "laugh" not in json.dumps(m["expressions"]), "nothing unseen may be stored as observed"


def test_memory_joints_and_proportions_are_right(data):
    m = data["mem"]
    truth = {"arm_L": (-28, -29), "arm_R": (28, -29)}
    for k, (x, y) in truth.items():
        j = m["parts"][k]["joint_in_parent"]
        assert abs(j[0] - x) <= 4 and abs(j[1] - y) <= 4, (k, j)
    pr = m["identity"]["proportions"]
    assert abs(pr["head_height"] - 68 / 78) <= 0.06, pr           # hair top to chin: 35 + 33 px on a 78 px torso
    assert abs(pr["head_width"] - 64 / 78) <= 0.06, pr
    assert abs(pr["arm_length"] - 77 / 78) <= 0.06 and abs(pr["torso_width"] - 56 / 78) <= 0.05, pr


def test_memory_round_trip(data, tmp_path):
    p = tmp_path / "m.json"
    dcm.jdump(data["mem"], p)
    assert dcm.jload(p) == data["mem"]
    rig = dcm.Rig(dcm.jload(p))
    assert len(rig.shapes(data["mem"]["pose_track"][0])) >= 10


# ---- 6. the memory really holds the character
def test_reference_can_be_rebuilt_from_memory(data):
    r = data["rebuild"]
    assert r["fg_iou"]["mean"] >= 0.85 and r["fg_iou"]["min"] >= 0.72
    assert r["ssim"]["mean"] >= 0.96


# ---- 7. new scene from the memory alone
def test_new_scene_needs_only_the_memory(data, tmp_path):
    shutil.copy2(data["dir"] / "character_memory.json", tmp_path / "m.json")       # nothing else is copied: no frames, no video
    rep = dcm.cmd_animate(tmp_path / "m.json", tmp_path / "scene", "idle 0.3; walk_to 0.6; wave 1; laugh 0.8; sit 1; blink", scale=0.8)
    assert rep["reads_reference_video"] is False and (tmp_path / "scene" / "new_scene.mp4").stat().st_size > 5000
    src = {a["action"]: a["source"] for a in rep["actions"]}
    assert src["walk_to"].startswith("observed") and src["wave"] == "observed" and src["blink"] == "observed"
    assert src["laugh"] == "synthesized" and src["sit"] == "synthesized"
    n = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0",
                            str(tmp_path / "scene" / "new_scene.mp4")], capture_output=True, text=True).stdout.strip())
    assert n == rep["frames"]


def test_character_in_the_new_scene_is_the_same_character(data):
    i = data["identity"]
    assert not i["roles_not_found"]
    assert max(i["palette_max_channel_diff"].values()) <= 14
    assert max(i["proportion_error_pct"].values()) <= 6.0
    assert i["same_character"] is True


def test_scene_moves_across_and_stays_on_the_ground(data):
    st = data["scene"]["states"]
    assert st[-1]["x"] - st[0]["x"] > 0.4 * data["scene"]["size"][0]
    stand = [s["y"] for s in st[:10]]
    assert max(stand) - min(stand) < 4


# ---- 8. changing an expression or a move does not change the body
def test_expression_change_leaves_the_body_untouched(data):
    m = data["mem"]; rig = dcm.Rig(m); s0 = dict(m["pose_track"][0])
    def body(s):
        cv = np.zeros((360 * dcm.SS, 640 * dcm.SS, 3), np.uint8); rig.draw(cv, s)
        pal = m["identity"]["palette"]
        return {k: np.all(cv == np.array(pal[k], np.uint8), axis=2) for k in ("torso", "arm", "leg")}      # hair is left out: the eyes overlap its fringe by a pixel
    a = body({**s0, "eyes": "open", "mouth": "closed"}); b = body({**s0, "eyes": "closed", "mouth": "open", "mouth_scale": (1.2, 1.0)})
    for k in a:
        assert np.array_equal(a[k], b[k]), k


def test_pose_change_keeps_every_part_the_same_size(data):
    m = data["mem"]; rig = dcm.Rig(m); s0 = dict(m["pose_track"][0])
    area = lambda poly: 0.5 * abs(np.dot(poly[:, 0], np.roll(poly[:, 1], 1)) - np.dot(poly[:, 1], np.roll(poly[:, 0], 1)))
    a = [area(p) for _, _, p in rig.shapes(s0)]
    b = [area(p) for _, _, p in rig.shapes({**s0, "arm_R": -120, "leg_L": 30, "torso": 8, "head": -10, "x": s0["x"] + 90})]
    assert np.allclose(a, b, rtol=1e-6)


# ---- 9. the Red Dragon it plugs into still works
def test_red_dragon_selftest_still_passes():
    rd = Path(os.environ.get("RED_DRAGON_DIR") or Path.home() / ".claude" / "skills" / "red-dragon") / "scripts" / "rd.py"
    if not rd.is_file():
        pytest.skip("red-dragon is not installed here")
    r = subprocess.run([sys.executable, "-X", "utf8", str(rd), "selftest"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=300)
    assert r.returncode == 0 and json.loads(r.stdout[r.stdout.index("{"):])["ok"] is True, r.stdout[-400:]
