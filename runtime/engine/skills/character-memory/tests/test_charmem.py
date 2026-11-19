"""Tests for Dragon Character Memory & Auto Rotoscope, run on the experiment folder made by `charmem_cli.py demo OUT`.

    python -I -X utf8 tests/test_charmem.py [OUT]          (default OUT: env CHARMEM_OUT)
Every threshold is fixed here in advance; a test prints the measured number next to it, and the run writes
OUT/tests_report.json. Exit code 1 if any test fails.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
RD = HERE.parents[3]                                    # red-dragon/ (engine/skills/character-memory/tests -> 4 up)
sys.path.insert(0, str(SCRIPTS))
from charmem import animate, memory  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CHARMEM_OUT", "."))
RESULTS = []


def check(name, ok, measured, threshold):
    RESULTS.append({"test": name, "pass": bool(ok), "measured": measured, "threshold": threshold})
    print(f"{'PASS' if ok else 'FAIL'}  {name:<52} {measured}   (needs {threshold})")


def jl(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def t1_frames():
    tm = jl(OUT / "02_work" / "timing.json")
    t = np.array([f["t"] for f in tm["frames"]])
    d = np.diff(t)
    files = list((OUT / "02_work" / "frames").glob("*.png"))
    check("T1a frame count = duration x fps (8 s x 30)", len(t) == 240 and len(files) == 240, f"{len(t)} timed, {len(files)} files", "240 and 240")
    check("T1b timing from the stream: steps of 1/fps", bool(np.all(d > 0)) and float(np.abs(d - 1 / tm["fps"]).max()) < 0.001,
          f"max |dt-1/30| = {float(np.abs(d - 1 / tm['fps']).max()) * 1000:.3f} ms, monotonic {bool(np.all(d > 0))}", "< 1 ms, monotonic")


def t2_redraw():
    s = jl(OUT / "03_redraw" / "redraw_metrics.json")["summary"]
    check("T2a redraw mask IoU (mean / worst frame)", s["mask_iou"]["mean"] >= 0.995 and s["mask_iou"]["min"] >= 0.99,
          f"{s['mask_iou']['mean']} / {s['mask_iou']['min']}", ">= 0.995 / >= 0.99")
    check("T2b colour-label agreement", s["label_agree"]["mean"] >= 0.96, s["label_agree"]["mean"], ">= 0.96")
    check("T2c PSNR in the character box (mean / worst)", s["psnr_db"]["mean"] >= 27 and s["psnr_db"]["min"] >= 26,
          f"{s['psnr_db']['mean']} / {s['psnr_db']['min']} dB", ">= 27 / >= 26 dB")
    check("T2d SSIM in the character box", s["ssim"]["mean"] >= 0.94, s["ssim"]["mean"], ">= 0.94")
    n = len(list((OUT / "03_redraw" / "svg").glob("*.svgz")))
    check("T2e one SVG per frame", n == 240, n, "240")


def t3_tracking():
    r = jl(OUT / "02_work" / "tracking_vs_truth.json")
    J = r["joints"]
    meas = {k: v for k, v in J.items() if v["interpolated_frames"] == 0}
    med = float(np.median([v["median_px"] for v in meas.values()]))
    check("T3a joints median error vs truth (visible joints)", med <= 7.0, f"{med:.2f} px of a {r['head_unit_px']:.0f}-px head", "<= 7 px")
    worst = max(meas.items(), key=lambda kv: kv[1]["median_px"])
    check("T3b worst visible joint (median)", worst[1]["median_px"] <= 15.0, f"{worst[0]} {worst[1]['median_px']} px", "<= 15 px")
    o = r["occlusion"][0]
    check("T3c hidden hand found (precision / recall)", o["precision"] >= 0.9 and o["recall"] >= 0.9, f"{o['precision']} / {o['recall']} on {o['hidden_truth']} frames", ">= 0.9 / >= 0.9")
    hid = J.get("hand.R", {})
    check("T3d hidden hand position (inferred, information-limited)", hid.get("p95_px", 999) <= 150, f"p95 {hid.get('p95_px')} px", "<= 150 px (documented limit)")


def t4_jitter():
    J = jl(OUT / "02_work" / "tracking_vs_truth.json")["joints"]
    blob = {k: v["jitter_rms_px"] for k, v in J.items() if k.split(".")[0] in ("hand", "foot", "head") and v["interpolated_frames"] == 0}
    derived = {k: v["jitter_rms_px"] for k, v in J.items() if k.split(".")[0] in ("shoulder", "elbow", "knee", "ankle", "neck") and v["interpolated_frames"] == 0}
    check("T4a jitter of blob-centre joints (worst)", max(blob.values()) <= 1.5, f"{max(blob, key=blob.get)} {max(blob.values())} px/frame²", "<= 1.5")
    check("T4b jitter of derived joints (worst)", max(derived.values()) <= 4.0, f"{max(derived, key=derived.get)} {max(derived.values())} px/frame²", "<= 4.0")


def t5_expressions():
    mem = jl(OUT / "character_memory.json")
    gt = jl(OUT / "01_reference" / "gt.json")
    pred = {i: e["name"] for e in mem["face"]["expressions"] for i in e.get("frames", [])}
    acc = sum(1 for g in gt["frames"] if pred.get(g["i"]) == g["expression"]) / len(gt["frames"])
    check("T5a expressions recognised vs truth", acc >= 0.95, f"{acc:.3f}", ">= 0.95")
    obs = {e["name"] for e in mem["face"]["expressions"] if e["observed"]}
    gen = [e for e in mem["face"]["expressions"] if e.get("generated")]
    check("T5b observed and generated kept apart", obs == {"neutral", "smile", "surprise", "laugh", "confused", "blink"} and all(e.get("derived_from") for e in gen),
          f"observed {sorted(obs)}; generated {[e['name'] for e in gen]}", "6 observed + generated with derived_from")


def t6_memory():
    p = OUT / "character_memory.json"
    mem = memory.load(p)
    with tempfile.TemporaryDirectory() as td:
        q = Path(td) / "copy.json"
        q.write_text(json.dumps(mem, ensure_ascii=False), encoding="utf-8")
        back = memory.load(q)
    check("T6a save -> load round trip", back == mem, "identical" if back == mem else "differs", "identical")
    need = ["identity", "skeleton", "parts", "layers", "face", "poses", "motions", "timeline", "provenance", "quality"]
    check("T6b sections present", all(k in mem for k in need), [k for k in need if k not in mem] or "all", ", ".join(need))
    bad = [x.get("name") for sec in (mem["parts"], mem["face"]["expressions"], mem["motions"], mem["skeleton"]["bones"])
           for x in sec if not (0.0 <= float(x.get("confidence", -1)) <= 1.0)]
    check("T6c every item has a confidence in [0,1]", not bad, bad or "all", "all")
    nosrc = [x["name"] for x in mem["face"]["expressions"] + mem["motions"] if x.get("observed") and not x.get("frames")]
    check("T6d every observed item cites its frames", not nosrc, nosrc or "all", "all")


def t7_transfer():
    info = jl(OUT / "04_new_scene" / "scene_script.json")
    import cv2
    cap = cv2.VideoCapture(str(OUT / "04_new_scene" / "new_scene.mp4"))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    check("T7a new scene rendered from memory (uses_video = false)", info["uses_video"] is False and n == info["frames"], f"{n} frames, uses_video={info['uses_video']}", "frames = script, false")
    vid = OUT / "01_reference" / "reference.mp4"
    hid = vid.with_suffix(".mp4.hidden_for_test")
    vid.rename(hid)
    try:
        with tempfile.TemporaryDirectory() as td:
            t0 = time.time()
            r = animate.render(OUT / "character_memory.json", "تضحك", td)
            ok = Path(td, "new_scene.mp4").stat().st_size > 10000
    finally:
        hid.rename(vid)
    check("T7b a command renders with the source video hidden", ok and r["actions"] == ["laugh"], f"{r['actions']} in {time.time() - t0:.1f} s", "renders")
    for cmd, want in (("خلّي الشخصية تمشي", ["walk"]), ("تضحك", ["laugh"]), ("تجلس", ["sit"]), ("انتقل بها إلى الجانب الآخر من المشهد", ["cross"]),
                      ("تمشي للناحية التانية وبعدين تضحك وبعدين تقعد", ["cross", "laugh", "sit"])):
        got = animate.parse(cmd)
        check(f"T7c command «{cmd[:32]}»", got == want, got, want)


def t8_identity():
    a = jl(OUT / "character_memory.json")
    b = jl(OUT / "05_reanalysis" / "character_memory_from_new_scene.json")
    from skimage.color import rgb2lab
    pa = {p["role"]: p["rgb"] for p in a["identity"]["palette"] if p["role"] != "unassigned"}
    pb = {p["role"]: p["rgb"] for p in b["identity"]["palette"] if p["role"] != "unassigned"}
    de = {r: float(np.linalg.norm(rgb2lab(np.array([[pa[r]]], np.uint8))[0, 0] - rgb2lab(np.array([[pb[r]]], np.uint8))[0, 0])) for r in pa if r in pb}
    check("T8a same colours re-learned from the new scene (worst ΔE)", len(de) >= 9 and max(de.values()) <= 8, f"{len(de)} roles, worst {max(de, key=de.get)} ΔE {max(de.values()):.2f}", ">= 9 roles, <= 8")
    la = {x["name"]: x["length_hu"] for x in a["skeleton"]["bones"] if x["length_hu"]}
    lb = {x["name"]: x["length_hu"] for x in b["skeleton"]["bones"] if x["length_hu"]}
    rel = {k: abs(lb[k] / la[k] - 1) for k in la if k in lb and not k.startswith(("hand", "foot"))}
    check("T8b same proportions re-learned (worst bone)", max(rel.values()) <= 0.12, f"{max(rel, key=rel.get)} {max(rel.values()) * 100:.1f}%", "<= 12%")
    ha = np.array(next(p for p in a["parts"] if p["name"] == "head")["shape"]["radii_hu"])
    hb = np.array(next(p for p in b["parts"] if p["name"] == "head")["shape"]["radii_hu"])
    corr = float(np.corrcoef(ha, hb)[0, 1])
    check("T8c same head shape re-learned (radial correlation)", corr >= 0.9, f"{corr:.3f}", ">= 0.9")


def t9_edit():
    mem = memory.load(OUT / "character_memory.json")
    ed = json.loads(json.dumps(mem))
    e = next(x for x in ed["face"]["expressions"] if x["name"] == "laugh")
    e["params"]["mouth_w"] = round(e["params"]["mouth_w"] * 1.3, 4)
    from PIL import Image
    imgs, heads = [], []
    for m in (mem, ed):
        ch = animate.Character(m, 210)
        lm = next(x for x in m["motions"] if x["name"] == "laugh")
        c = {k: lm["channels"][k][0] for k in memory.POSE_KEYS}
        c["px"], c["py"] = 540.0, 1100.0
        L, J = ch.layers(c, "laugh")
        im = Image.new("RGB", (2160, 3840), (240, 240, 240))
        ch.draw(im, L, s=2)
        imgs.append(np.asarray(im.resize((1080, 1920))).astype(int))
        heads.append(J["head"])
    d = np.abs(imgs[0] - imgs[1]).max(2) > 8
    ys, xs = np.nonzero(d)
    hc = heads[0]
    inside = bool(len(xs)) and float(np.max(np.hypot(xs - hc[0], ys - hc[1]))) <= 0.6 * 210
    check("T9a a wider laugh changes only the face", inside, f"{len(xs)} px changed, farthest {float(np.max(np.hypot(xs - hc[0], ys - hc[1]))) if len(xs) else 0:.0f} px from the head centre", "all within 0.6 head")
    same = ed["identity"] == mem["identity"] and ed["skeleton"] == mem["skeleton"] and ed["parts"] == mem["parts"]
    check("T9b identity, skeleton and parts untouched by the edit", same, same, "true")


def t10_red_dragon():
    rd = RD / "scripts" / "rd.py"
    env = dict(os.environ, RED_DRAGON_HOME=tempfile.mkdtemp(prefix="rd-test-"))
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(rd), "selftest"], capture_output=True, text=True, env=env, timeout=600)
    ok = r.returncode == 0 and '"ok": true' in r.stdout
    check("T10a red-dragon selftest", ok, (re.search(r'"playbooks": \d+', r.stdout) or [r.stdout[-120:]])[0], "ok")
    spec = importlib.util.spec_from_file_location("rd_t", rd)
    m = importlib.util.module_from_spec(spec)
    os.environ["RED_DRAGON_HOME"] = env["RED_DRAGON_HOME"]
    argv, sys.argv = sys.argv, [sys.argv[0]]
    spec.loader.exec_module(m)
    sys.argv = argv
    names = ["VERSION", "playbooks", "lessons", "understand", "brief", "library", "lib_find", "lib_install", "LIBRARY", "repos_top", "repos_find"]
    missing = [n for n in names if not hasattr(m, n)]
    check("T10b names the desktop app calls", not missing, missing or "all 11", "all 11")
    ev = RD / "mind" / "route_eval" / "route_eval.py"
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(ev), str(RD / "scripts"), "--split", "test"], capture_output=True, text=True, timeout=600)
    nums = [int(x) for x in re.findall(r"(\d+)%", r.stdout)]
    check("T10c routing on the held-out requests (exact/ok/top3)", len(nums) == 3 and nums[0] >= 52 and nums[1] >= 58 and nums[2] >= 66, nums, ">= 52 / 58 / 66 %")
    pb = {p["id"] for p in m.playbooks()}
    check("T10d new route present", "character-memory" in pb, "character-memory" in pb, "true")


if __name__ == "__main__":
    for t in (t1_frames, t2_redraw, t3_tracking, t4_jitter, t5_expressions, t6_memory, t7_transfer, t8_identity, t9_edit, t10_red_dragon):
        try:
            t()
        except Exception as e:  # noqa: BLE001
            check(t.__name__ + " (crashed)", False, f"{type(e).__name__}: {e}", "no crash")
    n_ok = sum(r["pass"] for r in RESULTS)
    print(f"\n{n_ok}/{len(RESULTS)} passed")
    (OUT / "tests_report.json").write_text(json.dumps({"passed": n_ok, "total": len(RESULTS), "results": RESULTS}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    raise SystemExit(0 if n_ok == len(RESULTS) else 1)
