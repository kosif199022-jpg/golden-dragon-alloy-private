"""Plain-assert tests for scripts/dmath.py.

Run:  python -I -X utf8 tests/test_dmath.py      (prints "N passed")
The math tests call the functions directly; the CLI tests run every subcommand
with --json (must parse) and --help (must exit 0) through subprocess.
"""

import importlib.util
import json
import math
import os
import random
import subprocess
import sys
import traceback

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(HERE, "..", "scripts", "dmath.py"))
_spec = importlib.util.spec_from_file_location("dmath", SCRIPT)
dm = importlib.util.module_from_spec(_spec)
sys.modules["dmath"] = dm
_spec.loader.exec_module(dm)

TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


# --- points, distances, angles ----------------------------------------------
@test
def triangle_3_4_5():
    assert dm.dist((0, 0), (3, 4))["distance"] == 5.0
    assert dm.dist((0, 0, 0), (3, 4, 0))["distance"] == 5.0
    assert close(dm.dist((1, 1, 1), (4, 5, 13))["distance"], 13.0)  # 3-4-12-13


@test
def right_angle_is_90():
    assert close(dm.angle((1, 0), (0, 0), (0, 1))["angle_deg"], 90.0, 1e-12)
    assert close(dm.angle((5, 0, 0), (0, 0, 0), (0, 0, 2))["angle_deg"], 90.0, 1e-12)
    assert close(dm.angle((1, 0), (0, 0), (0, -1))["signed_deg"], -90.0, 1e-12)


@test
def midpoint_and_lerp():
    assert dm.midpoint((0, 0, 0), (2, 4, 6))["midpoint"] == (1, 2, 3)
    assert dm.lerp((0, 0), (10, 20), 0.25)["point"] == (2.5, 5.0)
    assert dm.lerp((1, 1), (3, 3), 1.0)["point"] == (3, 3)


@test
def mixed_dimensions_rejected():
    try:
        dm.dist((0, 0), (1, 1, 1))
    except ValueError:
        return
    raise AssertionError("2D vs 3D should raise")


# --- IK -----------------------------------------------------------------------
@test
def ik2_straight_down():
    r = dm.ik2(0.45, 0.45, 0.0, -0.9)
    assert r["reachable"]
    assert close(r["root_deg"], 0.0, 1e-6) and close(r["mid_deg"], 0.0, 1e-6)
    assert r["fk_error"] < 1e-9


def _fk_from_degrees(l1, l2, root_deg, mid_deg):
    t1 = math.radians(root_deg)
    t2 = t1 + math.radians(mid_deg)
    return (l1 * math.sin(t1) + l2 * math.sin(t2), -l1 * math.cos(t1) - l2 * math.cos(t2))


@test
def ik2_fk_round_trip_50_random():
    rng = random.Random(1990)
    for _ in range(50):
        l1, l2 = rng.uniform(0.1, 1.5), rng.uniform(0.1, 1.5)
        lo, hi = abs(l1 - l2), l1 + l2
        d = lo + (hi - lo) * rng.uniform(0.001, 0.999)
        a = rng.uniform(-math.pi, math.pi)
        x, y = d * math.sin(a), -d * math.cos(a)
        r = dm.ik2(l1, l2, x, y, bend=rng.choice([1, -1]))
        assert r["reachable"] and r["fk_ok"], r
        ex, ey = _fk_from_degrees(l1, l2, r["root_deg"], r["mid_deg"])  # independent FK
        assert math.hypot(ex - x, ey - y) < 1e-9, (l1, l2, x, y, ex, ey)


@test
def ik2_bend_sign_picks_knee_side():
    # facing +X, bend -1 puts the knee in front (+X) of the hip-ankle line
    r = dm.ik2(0.45, 0.45, 0.1, -0.8, bend=-1)
    assert r["mid_deg"] < 0 and r["mid_joint"][0] > 0  # knee in front of the hip
    r2 = dm.ik2(0.45, 0.45, 0.1, -0.8, bend=1)
    assert r2["mid_deg"] > 0 and r2["mid_joint"][0] < r["mid_joint"][0]


@test
def ik2_unreachable_clamps():
    far = dm.ik2(1.0, 1.0, 3.0, 0.0)
    assert not far["reachable"]
    assert close(far["clamped_end"][0], 2.0) and close(far["clamped_end"][1], 0.0)
    assert close(far["root_deg"], 90.0) and close(far["mid_deg"], 0.0)
    assert close(far["reach_margin"], -1.0)
    near = dm.ik2(1.0, 0.5, 0.0, -0.2)
    assert not near["reachable"]
    assert close(near["clamped_end"][0], 0.0) and close(near["clamped_end"][1], -0.5)
    assert close(abs(near["mid_deg"]), 180.0)
    near2 = dm.ik2(0.5, 1.0, 0.0, -0.2)  # longer second bone: still lands toward target
    assert close(near2["clamped_end"][1], -0.5) and close(near2["clamped_end"][0], 0.0)


@test
def ik2_root_offset():
    r = dm.ik2(0.5, 0.5, 2.0, 0.0, root=(2.0, 1.0))
    assert r["reachable"] and close(r["root_deg"], 0.0, 1e-6) and r["fk_error"] < 1e-9


# --- camera -----------------------------------------------------------------
@test
def cam_target_projects_to_centre():
    for res in ((1080, 1920), (1920, 1080), (1000, 1000)):
        r = dm.cam_project(50, res, (0.3, 1.6, 5), (0, 1, 0), [(0, 1, 0)])
        p = r["points"][0]
        assert close(p["px"], res[0] / 2, 1e-9) and close(p["py"], res[1] / 2, 1e-9), p
        assert p["in_frame"]


@test
def cam_top_edge_and_behind():
    t = math.tan(math.radians(25))
    r = dm.cam_project(50, (1080, 1920), (0, 0, 5), (0, 0, 0),
                       [(0, 5 * t, 0), (0, -5 * t, 0), (0, 0, 10)])
    top, bottom, behind = r["points"]
    assert close(top["py"], 0.0, 1e-9) and close(bottom["py"], 1920.0, 1e-9)
    assert behind["px"] is None and not behind["in_frame"]


@test
def cam_vertical_fov_and_9x16_horizontal():
    v, h = dm.fov_pair(50, 1080, 1920)
    assert v == 50 and close(h, math.degrees(2 * math.atan(math.tan(math.radians(25)) * 0.5625)))
    assert h < v  # 9:16 horizontal FOV is narrower
    v2, h2 = dm.fov_pair(50, 1920, 1080)
    assert h2 > v2


@test
def cam_size_vs_frame_fit():
    for fov, res, s, fill in ((50, (1080, 1920), 1.78, 0.8), (35, (1920, 1080), 0.4, 0.5), (75, (1000, 1000), 3, 1.2)):
        d = dm.frame_fit(fov, res, s, fill)["distance"]
        px = dm.cam_size(fov, res, d, s)["px_height"]
        assert close(px, fill * res[1], 1e-6), (px, fill * res[1])
        # cross-check with the projection of the object's top and bottom
        pr = dm.cam_project(fov, res, (0, 0, d), (0, 0, 0), [(0, s / 2, 0), (0, -s / 2, 0)])
        assert close(pr["points"][1]["py"] - pr["points"][0]["py"], px, 1e-6)


@test
def frame_fit_width_limit():
    r = dm.frame_fit(50, (1080, 1920), 1.78, 0.8, width=1.6)
    assert r["limited_by"] == "width" and r["distance"] > r["distance_for_height"]


# --- angular, sun, puppet ------------------------------------------------------
@test
def sun_angular_size():
    deg = dm.angular_size(1.3927e9, 1.496e11)["deg"]
    assert abs(deg - 0.533) <= 0.01, deg
    back = dm.angular_solve(deg, dist_=1.496e11)["size"]
    assert close(back / 1.3927e9, 1.0, 1e-12)


@test
def sun_shadow_45_equals_height():
    r = dm.sun_shadow(2.0, 45.0, az=90.0)
    assert close(r["length"], 2.0, 1e-12)
    assert close(r["shadow_az_deg"], 270.0) and close(r["dir_en"][0], -1.0)  # sun east -> shadow west
    for bad in (0.0, -5.0):
        try:
            dm.sun_shadow(2.0, bad)
        except ValueError:
            continue
        raise AssertionError(f"elev {bad} must be refused")


@test
def puppet_shadow_limits_and_monotonic():
    r0 = dm.puppet_shadow(3.0, 0.0, 0.4, light_size=0.05)
    assert r0["magnification"] == 1.0 and r0["penumbra"] == 0.0 and close(r0["shadow_size"], 0.4)
    r0b = dm.puppet_shadow(3.0, 1e-12, 0.4, light_size=0.05)
    assert close(r0b["magnification"], 1.0, 1e-9) and r0b["penumbra"] < 1e-9
    prev = r0
    for d in (0.5, 1.0, 2.0, 2.9):  # farther from the screen: bigger AND blurrier
        r = dm.puppet_shadow(3.0, d, 0.4, light_size=0.05)
        assert r["shadow_size"] > prev["shadow_size"] and r["penumbra"] > prev["penumbra"]
        prev = r
    w = dm.puppet_shadow(3.0, 1.0, 0.4, want=1.2)["puppet_dist_for_want"]
    assert close(dm.puppet_shadow(3.0, w, 0.4)["shadow_size"], 1.2)


# --- body, gait -----------------------------------------------------------------
@test
def body_thigh_178():
    r = dm.body(1.78)
    assert abs(r["m"]["thigh"] - 0.436) <= 0.001, r["m"]["thigh"]
    assert close(r["head_unit_m"], 1.78 / 7.5)
    assert close(r["m"]["head"], 1.78 * (1 - 0.870), 1e-9)  # derived row = 1 - chin
    assert close(r["m"]["trunk"], r["m"]["shoulder"] - r["m"]["hip"], 1e-9)
    assert dm.body(1.78, px_per_m=100)["rows"][0]["px"] > 0


@test
def gait_defaults():
    r = dm.gait(1.75)
    assert close(r["step_length"], 0.413 * 1.75) and close(r["stride_length"], 2 * r["step_length"])
    assert 100 <= r["cadence_spm"] <= 120 and r["speed"] == 1.3
    assert close(r["step_period_s"] * r["cadence_spm"], 60.0)


# --- timing and curves --------------------------------------------------------------
@test
def minjerk_endpoints_and_midpoint():
    r = dm.ease(1.0, 24, 0.0, 1.0, "minjerk")
    v = [f["value"] for f in r["frames"]]
    assert v[0] == 0.0 and v[-1] == 1.0 and close(v[12], 0.5, 1e-12)
    for c in dm.EASES:
        assert dm.ease_value(c, 0.0) == 0.0 and dm.ease_value(c, 1.0) == 1.0, c
        assert close(dm.ease_value(c, 0.5), 0.5, 1e-12) or c in ("in", "out"), c
    e = dm.ease(0.5, 24, 0.1, 0.3, "smoothstep")
    assert e["frames"][-1]["value"] == 0.3  # exact end value, no float drift


@test
def semicircle_arc():
    r = dm.arc(2.0, 180.0)
    assert close(r["arc_length"], 2 * math.pi) and close(r["chord"], 4.0) and close(r["sagitta"], 2.0)


@test
def bezier_straight_line():
    assert close(dm.bezier((0, 0), (1, 0), (2, 0), (3, 0))["length"], 3.0, 1e-9)
    r = dm.bezier((0, 0, 0), (1, 1, 1), (2, 2, 2), (3, 3, 3))
    assert close(r["length"], 3 * math.sqrt(3), 1e-9)
    assert r["point_at_half"] == (1.5, 1.5, 1.5)


@test
def bezier_curve_bounds():
    r = dm.bezier((0, 0), (1, 2), (3, 2), (4, 0))
    assert r["chord"] < r["length"] < r["control_polygon"] and r["error_estimate"] < 1e-5
    assert r["point_at_half"] == (2.0, 1.5)


# --- CLI ------------------------------------------------------------------------------
CLI_CASES = [
    ["body", "1.78", "--px-per-m", "400", "--heads"],
    ["dist", "0,0,0", "3,4,0"],
    ["angle", "1,0", "0,0", "0,1"],
    ["midpoint", "-1,-2", "3,4"],
    ["lerp", "0,0", "10,0", "-0.5"],
    ["ik2", "0.436", "0.438", "0.25", "-0.80", "--bend", "-1"],
    ["cam", "--fov", "50", "--res", "1080x1920", "--pos", "-1,1.6,5", "--target", "0,1,0",
     "--point", "0,1,0", "--point", "-0.5,0,0"],
    ["cam-size", "--fov", "50", "--res", "1080x1920", "--dist", "4", "--size", "1.78"],
    ["frame-fit", "--fov", "50", "--res", "1080x1920", "--height", "1.78", "--fill", "0.8"],
    ["angular", "--size", "1.3927e9", "--dist", "1.496e11"],
    ["sun-shadow", "--height", "1.75", "--elev", "30", "--az", "135"],
    ["puppet-shadow", "--light-dist", "3", "--puppet-dist", "1", "--size", "0.4", "--light-size", "0.05"],
    ["gait", "--height", "1.75"],
    ["ease", "--dur", "1", "--fps", "24", "--from", "0", "--to", "1", "--curve", "minjerk"],
    ["arc", "--radius", "1", "--deg", "180"],
    ["bezier", "0,0", "1,2", "3,2", "4,0"],
]


def _run(args):
    return subprocess.run([sys.executable, "-I", "-X", "utf8", SCRIPT] + args,
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


@test
def cli_json_every_subcommand():
    seen = set()
    for case in CLI_CASES:
        p = _run(case + ["--json"])
        assert p.returncode == 0, (case, p.stderr)
        data = json.loads(p.stdout)
        assert data["ok"] is True and data["cmd"] == case[0], case
        seen.add(case[0])
    subs = set(dm.build_parser()._subparsers._group_actions[0].choices)
    assert seen == subs, subs - seen


@test
def cli_help_every_subcommand():
    subs = list(dm.build_parser()._subparsers._group_actions[0].choices)
    assert len(subs) == 16
    for s in subs:
        p = _run([s, "--help"])
        assert p.returncode == 0 and "usage:" in p.stdout, (s, p.stderr)
    assert _run(["--help"]).returncode == 0


@test
def cli_refusal_is_json():
    p = _run(["sun-shadow", "--height", "2", "--elev", "0", "--json"])
    assert p.returncode == 2
    data = json.loads(p.stdout)
    assert data["ok"] is False and "elevation" in data["error"]


def main():
    passed, failed = 0, []
    for fn in TESTS:
        try:
            fn()
            passed += 1
        except Exception:
            failed.append(fn.__name__)
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    if failed:
        print(f"{passed} passed, {len(failed)} failed: {', '.join(failed)}")
        sys.exit(1)
    print(f"{passed} passed")


if __name__ == "__main__":
    main()
