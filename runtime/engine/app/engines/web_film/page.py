"""Web Film: a motion film as one seek-driven HTML page — plan it, scaffold the page, check structure and contracts."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

PKG = Path(__file__).resolve().parent
ASSETS, DATA = PKG / "assets", PKG / "data"
PRESETS = json.loads((DATA / "presets.json").read_text(encoding="utf-8"))
RATIOS = {k: tuple(v) for k, v in PRESETS["ratios"].items()}
KINDS, TRANSITIONS = tuple(PRESETS["kinds"]), tuple(PRESETS["transitions"])
PALETTE = PRESETS["palette"]


def fill(template: str, **vals: str) -> str:
    """One pass over {{KEY}} slots, so a value that happens to contain {{X}} is never expanded again."""
    return re.sub(r"\{\{(\w+)\}\}", lambda m: vals[m.group(1)], template)


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def default_plan(prompt: str, duration: float = 15.0, ratio: str = "9:16", requirements=None) -> dict:
    """A starting plan: five shots with uneven lengths (short hook, long middle, held end) that tile the duration."""
    if ratio not in RATIOS:
        raise SystemExit(f"--ratio must be one of {', '.join(RATIOS)}")
    reqs = [r for r in (requirements or []) if r.strip()]
    d = PRESETS["default_shots"]
    shots, t = [], 0.0
    for i, (w, kind, tr) in enumerate(zip(d["weights"], KINDS, d["transitions"])):
        end = round(duration if i == len(d["weights"]) - 1 else t + duration * w, 3)
        shots.append({"start": round(t, 3), "end": end, "kind": kind, "text": "", "transition_in": tr,
                      "motion": "", "covers": [], "memorable": kind == d["memorable_kind"]})
        t = end
    if reqs:
        shots[0]["covers"] = list(range(len(reqs)))
    w, h = RATIOS[ratio]
    return {"schema": "kosif.web_film.plan.v1", "prompt": prompt, "requirements": reqs, "concept": "",
            "visual_language": {"palette": list(PALETTE), "type": PRESETS["font"], "motif": "", "motion_rule": ""},
            "duration": duration, "fps": 30, "width": w, "height": h, "seed": 7, "shots": shots}


def check_plan(plan: dict) -> list[str]:
    dur, shots = plan.get("duration"), plan.get("shots") or []
    if not _num(dur) or dur <= 0:
        return ["duration must be a positive number"]
    errs = []
    if len(shots) < 3:
        errs.append(f"need at least 3 shots, found {len(shots)}")
    for key in ("width", "height"):
        if not isinstance(plan.get(key), int) or plan[key] <= 0:
            errs.append(f"{key} must be a positive whole number of pixels")
    if not isinstance(plan.get("seed", 7), int):
        errs.append("seed must be a whole number")
    if not (plan.get("concept") or "").strip():
        errs.append("concept is empty: write the one idea the film serves")
    t = 0.0
    for i, s in enumerate(shots):
        a, b = s.get("start"), s.get("end")
        if not _num(a) or not _num(b) or b <= a:
            errs.append(f"shot {i}: start/end invalid")
            continue
        if abs(a - t) > 1e-3:
            errs.append(f"shot {i} starts at {a}, expected {round(t, 3)} (gap or overlap)")
        if s.get("transition_in") not in TRANSITIONS:
            errs.append(f"shot {i}: transition_in must be one of {', '.join(TRANSITIONS)}")
        t = b
    if shots and abs(t - dur) > 1e-3:
        errs.append(f"shots end at {round(t, 3)}, film duration is {dur}")
    lengths = [round(s["end"] - s["start"], 2) for s in shots if _num(s.get("end")) and _num(s.get("start"))]
    if len(lengths) >= 3 and len(set(lengths)) == 1:
        errs.append("every shot has the same length: vary the pacing")
    for i in range(1, len(shots)):
        tr = shots[i].get("transition_in")
        if tr == shots[i - 1].get("transition_in") and tr != "cut":
            errs.append(f"shots {i - 1} and {i} use the same transition ({tr})")
    if shots and not any(s.get("memorable") for s in shots):
        errs.append("no shot is marked memorable")
    covered = {c for s in shots for c in (s.get("covers") or []) if isinstance(c, int)}
    errs += [f"requirement {k} has no shot covering it: {r!r}"
             for k, r in enumerate(plan.get("requirements") or []) if k not in covered]
    return errs


_NET = re.compile(r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//|url\(\s*["']?\s*(?:https?:)?//|fetch\(\s*["']https?://""", re.I)
_PAGE_RULES = [  # (pattern, message): each match is a broken contract of a seekable, offline page
    (_NET, "page loads something from the network: keep fonts and images local"),
    (re.compile(r"\bDate\.now\(|new Date\(|performance\.now\("), "page reads the wall clock: every frame must be a function of t"),
    (re.compile(r"Math\.random\b"), "unseeded Math.random(): use the seeded rng(seed)"),
    (re.compile(r"\bset(?:Interval|Timeout)\("), "setInterval/setTimeout drive motion: compute from t instead"),
]


def check_html(text: str, plan: dict) -> list[str]:
    errs = []
    if not re.search(r"window\.__kosif\s*=", text):
        errs.append("page does not define window.__kosif (the renderer's seek API)")
    if not re.search(r"\bseek\s*[:(]", text):
        errs.append("window.__kosif has no seek(t)")
    m = re.search(r"""(?<![-\w])["']?duration["']?\s*:\s*([0-9.]+)""", text)
    if m and abs(float(m.group(1)) - float(plan.get("duration", 0))) > 1e-3:
        errs.append(f"page duration {m.group(1)} differs from plan {plan.get('duration')}")
    errs += [msg for rx, msg in _PAGE_RULES if rx.search(text)]
    scenes = len(re.findall(r'data-shot="\d+"', text))
    if scenes and scenes != len(plan.get("shots") or []):
        errs.append(f"page has {scenes} scenes, plan has {len(plan['shots'])} shots")
    return errs


def check(plan: dict, page_text: str | None = None) -> dict:
    errs = [f"plan: {e}" for e in check_plan(plan)]
    if page_text is not None:
        errs += [f"html: {e}" for e in check_html(page_text, plan)]
    return {"ok": not errs, "errors": errs}


def scaffold(plan: dict) -> str:
    """A working page from the plan: one <section data-shot> per shot, driven by assets/scaffold.js."""
    vl = plan.get("visual_language") or {}
    bg, fg, accent = ((vl.get("palette") or PALETTE) + PALETTE)[:3]
    rtl = bool(re.search(r"[؀-ۿ]", json.dumps(plan, ensure_ascii=False)))
    scenes = []
    for i, s in enumerate(plan["shots"]):
        words = "".join(f'<span class="w">{html.escape(w)}</span> ' for w in (s.get("text") or "").strip().split())
        extra = {"shape": '<div class="shape"></div>', "reveal": '<div class="field"></div>'}.get(s.get("kind"), "")
        scenes.append(f'<section class="scene k-{html.escape(s.get("kind", ""))}" data-shot="{i}">{extra}<h1>{words}</h1></section>')
    # "<" escaped so text such as "</script>" in a shot cannot end the script block.
    data = json.dumps({"duration": plan["duration"], "seed": plan.get("seed", 7), "shots": plan["shots"]},
                      ensure_ascii=False).replace("<", "\\u003c")
    engine = (ASSETS / "scaffold.js").read_text(encoding="utf-8").replace("__PLAN__", data)
    return fill((ASSETS / "scaffold.html").read_text(encoding="utf-8"),
                LANG="ar" if rtl else "en", DIR="rtl" if rtl else "ltr",
                TITLE=html.escape(plan.get("concept") or plan.get("prompt") or "KOSIF web film"),
                W=str(plan["width"]), H=str(plan["height"]), BG=bg, FG=fg, ACCENT=accent,
                FONT=vl.get("type") or PRESETS["font"], TYPE_PX=str(int(plan["width"] * 0.09)),
                SCENES="\n".join(scenes), ENGINE=engine)


def write_scaffold(plan_path, out) -> Path:
    out = Path(out)
    if out.suffix.lower() not in (".html", ".htm"):      # --out DIR: the page goes inside it, not into a file named DIR
        out = out / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(scaffold(json.loads(Path(plan_path).read_text(encoding="utf-8"))), encoding="utf-8")
    return out
