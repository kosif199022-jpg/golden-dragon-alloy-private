"""V70 motion-graphics style catalogue: menu, show and cocktail planning (read-only).

When the owner asks for motion graphics for any clip, run `styles menu` first and offer every installed style
(native Red Rose engines + the owner's style-pack library), let him pick one or a cocktail, then plan with
`styles cocktail`. Each style renders through its own engine, documented in its own SKILL.md/README: read it
before running. This module never renders, installs or downloads anything; a style is "rendered_ok" only
when agent/style_tests_v70.json holds measured evidence for it.
"""
from __future__ import annotations
import hashlib, json, os, re, subprocess
from pathlib import Path

SKILL = Path(__file__).resolve().parent
REGISTRY = SKILL / "agent" / "style_registry_v70.json"
TESTS = SKILL / "agent" / "style_tests_v70.json"
LIB = Path.home() / ".red-rose" / "libraries" / "style-packs"
ROLES = ("characters", "places", "camera", "type", "captions", "maps", "music", "sfx")
ASPECTS = {"9:16": 9 / 16, "16:9": 16 / 9, "1:1": 1.0}


def registry(path=REGISTRY):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [s["id"] for s in data["styles"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate style id in registry")
    return data["styles"]


def tests(path=TESTS):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")).get("results", {}) if p.is_file() else {}


def _tree_sha(root: Path) -> str:
    h = hashlib.sha256()
    for d, ds, fs in sorted(os.walk(root)):
        ds.sort()
        for f in sorted(fs):
            p = Path(d, f)
            h.update(p.relative_to(root).as_posix().encode())
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def location(style, lib=LIB, skill=SKILL):
    src = style["source"]
    kind, _, ref = src.partition(":")
    if kind == "native":
        root = skill / ref
        return root, root.is_dir(), None
    if kind == "pack":
        root = Path(lib) / ref
        return root, root.is_dir(), ref
    raise ValueError(f"bad source {src}")


def install_state(style, lib=LIB, verify=False):
    root, present, pack = location(style, lib)
    if not present:
        return "missing"
    if pack is None or not verify:
        return "installed"
    mpath = Path(lib) / "MANIFEST.json"
    if not mpath.is_file():
        return "installed_unverified"
    man = json.loads(mpath.read_text(encoding="utf-8"))
    want = man.get(pack, {}).get("tree_sha256")
    return "installed_verified" if want and _tree_sha(root) == want else "changed_since_install"


def probe_clip(clip):
    """Read-only ffprobe of a clip: duration and aspect. Returns None when ffprobe is unavailable."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=width,height:format=duration", "-of", "json", str(clip)],
                             capture_output=True, text=True, timeout=60, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    j = json.loads(out)
    st = (j.get("streams") or [{}])[0]
    w, h = st.get("width"), st.get("height")
    dur = float(j.get("format", {}).get("duration", 0) or 0)
    ratio = w / h if w and h else None
    aspect = min(ASPECTS, key=lambda k: abs(ASPECTS[k] - ratio)) if ratio else None
    return {"width": w, "height": h, "seconds": round(dur, 3), "aspect": aspect}


def _fits(style, aspect):
    return aspect is None or "any" in style["aspect"] or aspect in style["aspect"]


def menu(clip=None, need=(), lib=LIB, reg=None, tested=None):
    reg = reg if reg is not None else registry()
    tested = tested if tested is not None else tests()
    info = probe_clip(clip) if clip else None
    aspect = info["aspect"] if info else None
    need = [n for n in need if n]
    bad = [n for n in need if n not in ROLES]
    if bad:
        raise ValueError(f"unknown roles {bad}; use {ROLES}")
    groups = {}
    for s in reg:
        if need and not all(n in s["layers"] for n in need):
            continue
        t = tested.get(s["id"], {})
        groups.setdefault(s["family"], []).append({
            "id": s["id"], "name_ar": s["name_ar"], "best_for": s["best_for"], "layers": s["layers"],
            "input": s["input"], "aspect": s["aspect"], "fits_clip": _fits(s, aspect), "runtime": s["runtime"],
            "install": install_state(s, lib), "render_test": t.get("status", "not_tested_here"),
            "substyles": s.get("substyles", []), "dua_gate": s.get("dua_gate", False),
            "paid_generation": s.get("paid_generation", False), "credit": s["credit"]})
    count = sum(len(v) for v in groups.values())
    return {"clip": info, "styles": count, "families": groups,
            "how_to_choose": "pick one id, or a cocktail: a+b (segments) or characters=a,places=b,type=c (layers)",
            "execution_allowed": False}


def show(style_id, lib=LIB, reg=None, tested=None):
    reg = reg if reg is not None else registry()
    s = next((x for x in reg if x["id"] == style_id), None)
    if not s:
        raise ValueError(f"unknown style '{style_id}'")
    root, present, pack = location(s, lib)
    rights = sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                    if p.is_file() and re.search(r"(?i)licen|rights", p.name)) if present else []
    t = (tested if tested is not None else tests()).get(style_id, {})
    return {**s, "root": str(root), "doc_path": str(root / s["doc"]) if pack else str(SKILL / s["doc"]),
            "install": install_state(s, lib, verify=bool(pack)), "rights_files": rights[:12],
            "render_test": t or {"status": "not_tested_here"},
            "next": "read doc_path fully before running this engine; run its own doctor/check if it has one"}


def parse_cocktail(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 400:
        raise ValueError("empty cocktail")
    if "=" in text:
        roles = {}
        for part in re.split(r"[,،]", text):
            role, _, sid = part.partition("=")
            role, sid = role.strip(), sid.strip()
            if role not in ROLES or not sid:
                raise ValueError(f"bad role part '{part.strip()}'")
            roles[role] = sid
        return "layers", roles
    ids = [x.strip() for x in text.split("+") if x.strip()]
    if len(ids) < 1:
        raise ValueError("empty cocktail")
    return "segments", ids


def cocktail(text, seconds, fps=30, aspect="9:16", reg=None, lib=LIB, tested=None):
    if type(fps) is not int or not 1 <= fps <= 120:
        raise ValueError("fps")
    if not isinstance(seconds, (int, float)) or not 1 <= seconds <= 600:
        raise ValueError("seconds 1-600")
    if aspect not in ASPECTS:
        raise ValueError(f"aspect must be one of {list(ASPECTS)}")
    reg = reg if reg is not None else registry()
    tested = tested if tested is not None else tests()
    by = {s["id"]: s for s in reg}
    mode, sel = parse_cocktail(text)
    ids = list(sel.values()) if mode == "layers" else sel
    unknown = [i for i in ids if i not in by]
    if unknown:
        raise ValueError(f"unknown styles {unknown}")
    blockers, warnings = [], []
    for i in dict.fromkeys(ids):
        s = by[i]
        if not _fits(s, aspect):
            blockers.append(f"{i} does not support {aspect} (has {s['aspect']})")
        if install_state(s, lib) == "missing":
            blockers.append(f"{i} is not installed")
        if s.get("paid_generation"):
            blockers.append(f"{i} needs a paid generator: explicit owner approval and price first")
        if s.get("dua_gate"):
            warnings.append(f"{i}: mandatory dua footage/font gate (references/DUA_REELS_PLAYBOOK.md) applies")
        if tested.get(i, {}).get("status") != "rendered_ok":
            warnings.append(f"{i}: engine not yet render-tested on this PC; run a short sample first")
    total = int(round(seconds * fps))
    plan = {"mode": mode, "aspect": aspect, "fps": fps, "frames": total, "seconds": round(total / fps, 3)}
    if mode == "segments":
        n = len(ids)
        cuts = [round(total * k / n) for k in range(n + 1)]
        plan["segments"] = [{"n": k + 1, "style": ids[k], "start_frame": cuts[k], "end_frame": cuts[k + 1],
                             "engine_doc": show(ids[k], lib, reg, tested)["doc_path"],
                             "output": f"seg_{k + 1:02d}_{ids[k]}.mp4"} for k in range(n)]
        plan["join"] = ("render every segment at the same size/fps, then join with montage-code (whole-frame "
                        "transitions) and verify with media-contract verify")
    else:
        for role, sid in sel.items():
            if role not in by[sid]["layers"]:
                blockers.append(f"{sid} does not provide the '{role}' layer (has {by[sid]['layers']})")
        scene = {r: by[sel[r]] for r in ("characters", "places", "camera") if r in sel}
        engines = {s["source"] for s in scene.values()}
        if len(engines) > 1:
            blockers.append("characters/places/camera come from different engines: they cannot share one scene. "
                            "Use one engine for the scene, or a segments cocktail (a+b)")
        base = next(iter(scene.values()))["id"] if scene else ids[0]
        overlays = [{"role": r, "style": sid} for r, sid in sel.items()
                    if r not in ("characters", "places", "camera") and by[sid]["source"] != by[base]["source"]]
        if overlays:
            warnings.append("overlay layers need the overlay engine to render with transparency (alpha); "
                            "not verified for any pack yet: test a 3-second sample first")
        plan["base_scene"] = {"style": base, "engine_doc": show(base, lib, reg, tested)["doc_path"]}
        plan["overlays"] = overlays
        plan["join"] = "render base scene, render overlays with alpha, composite with ffmpeg overlay, verify"
    plan["after_planning"] = ["write the shot list and run `rose.py continuity check`",
                              "render a 3-second sample per engine and look at the frames",
                              "full render, then media-contract verify and a visual review"]
    return {"status": "blocked" if blockers else "plan_ready", "blockers": blockers, "warnings": warnings,
            "plan": plan, "rendered": False, "execution_allowed": False}


def handle(a):
    try:
        if a.action == "menu":
            r = menu(a.target or None, (a.need or "").split(",") if a.need else ())
        elif a.action == "show":
            r = show(a.target)
        else:
            r = cocktail(a.target, a.seconds, a.fps, a.aspect)
        print(json.dumps(r, ensure_ascii=False, indent=1 if a.pretty else None))
        return 0
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)[:300]}, ensure_ascii=False))
        return 1


def register(sub):
    p = sub.add_parser("styles", help="V70 motion-graphics style menu, details and cocktail plan (read-only)")
    p.add_argument("action", choices=["menu", "show", "cocktail"])
    p.add_argument("target", nargs="?", default="", help="menu: optional clip; show: style id; cocktail: a+b or role=id,...")
    p.add_argument("--need", help="menu filter, comma roles e.g. characters,places")
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--aspect", default="9:16")
    p.add_argument("--pretty", action="store_true")
    p.set_defaults(ext_func=handle)
