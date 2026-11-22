"""Red Rose V30: explicit, reviewed storyboard -> original illustrated H264 MP4.

Bridges V29's evidence-based, frame-accurate storyboard to the existing native
V20 clay/schematic-map renderer. No Remotion, Maven, Figma or old Dragon runtime
is imported or executed. Any visual downgrade MUST be opted into explicitly.
Writes only through the capability runtime approval gate, stages media privately,
verifies full MP4 decode, then atomically hard-links a NEW output (never replaces).
"""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fusion_studio_v20 import plan as fusion_plan, render_video
from intelligence_director_v29 import storyboard_plan
from verify_media import verify_video

OPS = ("compile", "render")
EFFECTS = {"compile": "read", "render": "write"}
_MAPPABLE = {"clay": "clay", "map": "map"}
_FALLBACK = {"toon", "reel", "faceless", "saas", "editorial"}
_ALLOWED = {"story", "map_routes", "allow_illustrative_fallback"}


def _validate_dict(d, allowed, required=()):
    if type(d) is not dict:
        raise ValueError("operation params must be an object")
    bad = set(d) - set(allowed)
    if bad:
        raise ValueError("unknown parameters: " + ",".join(sorted(bad)))
    missing = set(required) - set(d)
    if missing:
        raise ValueError("missing parameters: " + ",".join(sorted(missing)))


def compile_storyboard(params):
    """Review a bounded storyboard; refuse unsupported visual fidelity."""
    _validate_dict(params, _ALLOWED, ("story",))
    if type(params["story"]) is not dict:
        raise ValueError("story must be a JSON object")
    fallback = params.get("allow_illustrative_fallback", False)
    if type(fallback) is not bool:
        raise ValueError("allow_illustrative_fallback must be boolean")
    routes = params.get("map_routes", {})
    if type(routes) is not dict:
        raise ValueError("map_routes must be an object keyed by shot number")
    story = storyboard_plan(params["story"])
    if story["aspect"] not in ("9:16", "1:1"):
        raise ValueError("native illustrated renderer only supports 9:16 and 1:1; no 16:9 crop")
    if story["total_frames"] > 360:
        raise ValueError("native illustration render budget is <=360 frames")
    preset = "iphone-vertical" if story["aspect"] == "9:16" else "social-square"
    scenes, downgrades, used_routes = [], [], set()
    for beat in story["shots"]:
        visual = beat["visual"]
        idx = str(beat["index"])
        title = beat["caption_text"]
        if len(title) > 100:
            raise ValueError("illustrated caption limit is 100 characters for shot " + idx)
        if visual in _MAPPABLE:
            kind = visual
        elif visual in _FALLBACK and fallback:
            kind = "clay"
            downgrades.append({"shot":beat["index"], "requested":visual,
                               "rendered_as":"original_clay_illustration"})
        else:
            raise ValueError("render cannot reproduce visual style '" + str(visual) +
                             "'; 3D and full Remotion are not available. Opt into illustrative fallback for supported flat styles.")
        scene = {"kind":kind, "title":title,
                 "duration":beat["duration_frames"]/story["fps"]}
        if kind == "map":
            if idx not in routes:
                raise ValueError("schematic map route required for shot " + idx)
            coords = routes[idx]
            _validate_dict(coords, ("from", "to"), ("from", "to"))
            scene.update({"from":coords["from"],"to":coords["to"]})
            used_routes.add(idx)
        scenes.append(scene)
    unused = set(routes) - used_routes
    if unused:
        raise ValueError("unused or invalid map routes: " + ",".join(sorted(map(str,unused))))
    # Existing plan validates map coordinates, per-shot time budgets and frames.
    native = fusion_plan(scenes, story["fps"], preset)
    if native["frames"] != story["total_frames"]:
        raise ValueError("storyboard/natural render frame count mismatch")
    return {
        "status": "compiled_not_rendered", "storyboard": story,
        "native_project": native, "downgrades": downgrades,
        "human_approval_required_to_render": True,
        "render_limits": "Original illustrated clay / schematic map video only; silent H264 MP4; no neural models, editable Figma, 3D or content understanding."
    }


def run(op, params):
    """IO_ADAPTERS dispatcher injects approve_write ONLY for effect=write."""
    if op not in OPS:
        raise ValueError("unknown storyboard pipeline op")
    if op == "compile":
        return compile_storyboard(params)
    _validate_dict(params, _ALLOWED|{"approve_write","output"}, ("story","output"))
    if params.get("approve_write") is not True:
        raise PermissionError("explicit approved render required")
    path_text = params["output"]
    if type(path_text) is not str or not path_text or len(path_text) > 1024:
        raise ValueError("new .mp4 output path required")
    original = Path(path_text).expanduser()
    # Never follow an output symlink, including a dangling one.
    if original.is_symlink():
        raise ValueError("refusing symlink output")
    target = original.absolute()
    if target.suffix.lower() != ".mp4" or target.exists() or not target.parent.is_dir():
        raise ValueError("output must be a new MP4 in an existing directory")
    compiled = compile_storyboard({k:v for k,v in params.items() if k in _ALLOWED})
    native = compiled["native_project"]
    # Staging and verification take place before final destination creation.
    # TemporaryDirectory exists within same directory, so hard-link is atomic.
    with TemporaryDirectory(dir=target.parent, prefix=".rose-v30-") as temp:
        staged = Path(temp)/"staged.mp4"
        render_video(native, staged, approve_write=True)
        qa = verify_video(staged, expected_fps=native["fps"],
                          expected_frames=native["frames"], width=native["width"],
                          height=native["height"], expected_audio=False)
        # os.link fails with FileExistsError if another writer creates target,
        # eliminating an accidental overwrite window.
        os.link(staged, target)
    return {"status":"rendered_and_verified","output":str(target),
            "qa":qa,"scene_count":len(native["scenes"]),
            "frames":native["frames"],"fps":native["fps"],
            "downgrades":compiled["downgrades"],
            "edits":"Save original story JSON separately to replan; MP4 is not an editable NLE project.",
            "warning":"Native illustrated silent clip only; user review required before publishing."}
