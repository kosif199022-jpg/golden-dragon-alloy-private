"""Helpers of power_programs/ai_generation.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from pathlib import Path
import cv2
import hashlib
import json
import math
import numpy as np
import re
from ._lang_common import words


HYPE = ("8k", "4k", "masterpiece", "ultra-detailed", "award-winning", "trending", "best quality", "beautiful",
        "hyperrealistic", "octane render")


def strip_hype(text):
    parts = [p.strip() for p in text.split(",")]
    return ", ".join(p for p in parts if p and p.lower() not in HYPE)


def golden(spec):
    order = ("style", "composition", "camera", "lighting", "subject", "wardrobe", "environment", "atmosphere")
    line = ", ".join(spec[k] for k in order) + f", mood: {spec['mood']} --ar {spec['aspect']}"
    layers = ("location", "subject", "wardrobe", "lighting", "camera", "atmosphere", "technical")
    missing = [l for l in layers if not spec.get("layers", {}).get(l)]
    return line, missing


def iron_lint(prompt, locks, used_locks):
    issues = []
    if re.match(r"\s*a photo of", prompt, re.I):
        issues.append("opens with 'a photo of'")
    hype = [h for h in HYPE if re.search(rf"\b{re.escape(h)}\b", prompt, re.I)]
    if hype:
        issues.append("hype: " + ",".join(hype))
    for name, text in locks.items():
        if text not in used_locks.get(name, ""):
            issues.append(f"lock '{name}' paraphrased")
    return issues


POSITIVE = {"no blur": "tack-sharp focus", "no people": "empty, deserted", "no text": "clean, text-free surfaces"}


def frame_negatives(neg, platform):
    if platform in ("sdxl", "kling"):
        return {"prompt_add": [], "negative": neg}
    if platform == "wan":
        return {"prompt_add": [], "negative": neg[:3]}
    add = [POSITIVE[n] for n in neg if n in POSITIVE]
    return {"prompt_add": add, "negative": []}


def still_check(prompt, api_aspect):
    n = len(prompt.split())
    desc = [d for d in prompt.split(",") if d.strip()]
    ar = re.search(r"(\d+:\d+)", prompt)
    return {"words_ok": 40 <= n <= 80, "descriptors_ok": 5 <= len(desc) <= 8,
            "ratio_twice": bool(ar) and ar.group(1) == api_aspect, "n": n, "d": len(desc)}


def narrative(subject, style, context, other):
    total = 100
    alloc = {"subject": 30, "style": 25, "context": 15, "other": 30}
    def take(t, n):
        w = t.split()
        return " ".join((w * (n // max(len(w), 1) + 1))[:n])
    paras = [take(subject, alloc["subject"]) + ".", take(style, alloc["style"]) + ". " + take(context, alloc["context"]) + ".",
             take(other, alloc["other"]) + ". ultra-realistic, high resolution"]
    return "\n\n".join(paras), alloc, total


def mj_translate(p):
    params = {}
    m = re.search(r"--ar (\d+:\d+)", p)
    if m:
        params["aspect_ratio"] = m.group(1)
    t = re.sub(r"--ar \S+|--v \S+|--style raw|--s \d+|--stylize \d+", "", p)
    if re.search(r"--chaos (\d+)", t):
        t = re.sub(r"--chaos \d+", "", t) + ", unexpected, surreal composition"
    t = re.sub(r"\((\w+):1\.\d\)", r"prominently featuring \1", t)
    t = strip_hype(re.sub(r"\s+", " ", t).strip(" ,"))
    return t, params


CAM_WORDS = ("static", "pan", "tilt", "dolly", "tracking", "crane", "handheld", "orbit", "push-in", "dolly zoom", "rack focus")


def video_formula(p):
    n = len(p.split())
    issues = []
    if not 50 <= n <= 100:
        issues.append(f"{n} words (50-100)")
    if not any(c in p.lower() for c in CAM_WORDS):
        issues.append("camera move or 'static' missing")
    if re.search(r"\bcut to\b|\bscene changes\b", p, re.I):
        issues.append("scene change inside clip")
    if re.search(r"text (says|reading)|caption reading|on-screen text", p, re.I):
        issues.append("on-screen text requested")
    return issues


SUFFIX = "No music score. No subtitles or on-screen text."


def segment_call(prompt, ref_has_signage=False):
    p = prompt.rstrip(". ") + ". " + SUFFIX
    if ref_has_signage:
        p += " Only the text that exists in @Image1 itself."
    return {"prompt": p, "generate_audio": False}


def montage_plan(total_s, lo=4, hi=15, target=8):
    n = max(1, math.ceil(total_s / target))
    while total_s / n > hi:
        n += 1
    while n > 1 and total_s / n < lo:
        n -= 1
    base = total_s / n
    return [round(base, 2)] * n


SDXL = {"1:1": (1024, 1024), "16:9": (1344, 768), "9:16": (768, 1344), "4:5": (896, 1152), "3:2": (1216, 832), "2.39:1": (1536, 640)}


def forge(spec):
    warn = [f"missing {k}: prompts will be weaker" for k in ("lens", "style") if not spec.get(k)]
    core = ", ".join(spec[k] for k in ("subject", "action", "environment") if spec.get(k))
    w, h = SDXL[spec["aspect"]]
    return {"prompts": {"sdxl": {"prompt": core, "width": w, "height": h, "cfg": 6, "steps": 35}},
            "variations": {"subtle": core + ", softer light", "dramatic": core + ", hard rim light, deep shadows",
                           "technical": core + ", 50 mm, f/2.8, 1/250 s"}, "warnings": warn}


def snap(d, allowed):
    return min(allowed, key=lambda a: (abs(a - d), -a))


def platform_shot(p, dur, prompt, refs=0):
    if p == "veo":
        return {"dur": snap(dur, (4, 6, 8))}
    if p == "sora":
        if len(prompt) > 4000:
            raise ValueError("sora prompt > 4000 chars")
        return {"dur": snap(dur, (4, 8, 12))}
    if p == "runway":
        if refs > 3:
            raise ValueError("runway <= 3 refs")
        return {"dur": min(10, max(2, dur))}
    if p == "kling":
        return {"dur": min(10, max(5, dur))}


REQ12 = ("subject", "environment", "shot", "lighting", "style", "aspect")


SDXL12 = {"16:9": (1344, 768), "9:16": (768, 1344), "4:5": (896, 1120)}


def builders(spec):
    miss = [k for k in REQ12 if not spec.get(k)]
    if miss:
        raise ValueError(f"missing {miss}")
    core = ", ".join(spec[k] for k in REQ12[:-1])
    neg = ", ".join(spec.get("negative", []))
    w, h = SDXL12[spec["aspect"]]
    return {"midjourney": f"{core} --ar {spec['aspect']} --s 200 --v 7 --no {neg}",
            "flux": f"{core}. Avoid: {neg}.",
            "sdxl": {"prompt": f"({spec['subject']}:1.3), {core}", "steps": 30, "cfg": 6.0, "width": w, "height": h},
            "chatgpt": f"Create one single image. Aspect ratio {spec['aspect']}. Do not include {neg}. {core}.",
            "ideogram": f"\"{spec.get('text', '')}\" {core} --ar {spec['aspect']}",
            "nanobanana": f"Generate a single photorealistic-quality image of {core}. Exclude: {neg}."}


MAXS = {"veo": 8, "sora": 20, "kling": 10, "runway": 10, "luma": 9, "pika": 10, "hailuo": 10}


REAL_PEOPLE = {"elon musk", "taylor swift", "mohamed salah"}


def shot_forge(doc, platforms):
    out, lint = [], []
    aspect, fps = doc.get("aspect", "16:9"), doc.get("fps", 24)
    for i, s in enumerate(doc["shots"]):
        if any(n in s["prompt"].lower() for n in REAL_PEOPLE):
            lint.append((i, "BLOCK"))
        if not doc.get("lock"):
            lint.append((i, "REVISE"))
        if sum(1 for c in CAM_WORDS if re.search(rf"\b{c}\b", s["prompt"].lower())) > 1:
            lint.append((i, "FLAG camera"))
        out.append({p: {"dur": min(s["dur"], MAXS[p]), "aspect": aspect, "fps": fps} for p in platforms})
    return out, lint


def aiprompts(shot):
    layers = {k: shot[k] for k in ("location", "subject", "wardrobe", "lighting", "camera", "atmosphere", "technical")}
    text = ", ".join(layers.values())
    warn = []
    if not re.search(r"\d{4}K", shot["lighting"]) or not re.search(r"left|right|behind|above|front", shot["lighting"]):
        warn.append("lighting lacks direction or Kelvin")
    return {"layers": layers, "prompts": {"runway": text[:1000], "kling": {"prompt": text[:2500], "negative_prompt": "blur, watermark"},
                                          "veo": text, "sora": text}, "warnings": warn,
            "rubric": {k: 20 for k in ("clarity", "camera", "light", "continuity", "platform fit")}}


def omniprompt(brief, overrides=None, duration=10):
    if not brief.get("style") or not brief.get("scenes"):
        raise SystemExit("brief not filled")
    ov = overrides or {}
    for r in ov.get("remove", []):
        if any(r in s["elements"] for s in brief["scenes"]):
            raise ValueError(f"refuse: scenes are built on {r}")
    palette = [ov.get("palette", {}).get(c, c) for c in brief["palette"]]
    scale = 0.83 if duration == 12 else 10 / brief["duration"]
    times = [round(s["t"] * (scale if duration == 12 else 10 / brief["duration"]), 2) for s in brief["scenes"]]
    w, h = brief["size"]
    if min(w, h) < 1080:
        f = 1080 / min(w, h)
        w, h = round(w * f), round(h * f)
    block = {"STYLE": brief["style"], "SPECS": f"{w}x{h}, {duration} s, palette {palette}", "TIMELINE": times,
             "ADD": ov.get("add", []), "BRAND MARK": brief.get("brand", ""), "TYPOGRAPHY LOCK": brief.get("font", ""),
             "SOUND": brief.get("sound", ""), "FINAL FRAME": brief.get("final", ""), "EXCLUDE": ov.get("remove", [])}
    return block, (w, h)


FIELDS16 = ("subject", "environment", "action", "camera", "lighting", "color_grade", "materials", "atmosphere_vfx",
            "composition_story", "negative_constraints", "aspect_ratio")


def compile_prompt(scene):
    miss = [f for f in FIELDS16 if not scene.get(f)]
    if miss:
        raise ValueError(f"missing {miss}")
    if not re.fullmatch(r"\d+:\d+", scene["aspect_ratio"]):
        raise ValueError("aspect_ratio must be W:H")
    digest = hashlib.sha256(json.dumps(scene, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    prompt = ", ".join(scene[f] for f in FIELDS16[:9])
    return {"prompt": prompt, "negative_prompt": scene["negative_constraints"], "scene_digest": digest, "scene_spec": scene}


def apply_locks(spec):
    L = spec.get("locks", {})
    subj = spec["subject"] + (", " + L["character"] if L.get("character") else "")
    style = spec["style"] + (", " + L["style"] if L.get("style") else "")
    p = f"{subj}, {spec['action']}, {style}" + (", " + L["location"] if L.get("location") else "")
    return p, ([] if L else ["REVISE: no lock"])


def ease_overshoot(u, over=0.07):
    base = 1 - (1 - u) ** 3
    return base + over * math.sin(math.pi * u) * (u > 0.5)


def seeds(shots, lock):
    lock = strip_hype(lock)
    out, t = [], 0.0
    for s in shots:
        at = round(t + 0.3 * s["dur"], 2)
        out.append({"shot": s["id"], "seed_at": at, "veo2_prompt": f"{lock}, {s['desc']}", "sora_prompt": f"{s['desc']}. {lock}",
                    "kling_prompt": f"{s['desc']}, {lock}", "runway_gen3_prompt": f"{s['desc']}; {lock}"})
        t += s["dur"]
    return {"style_lock": lock, "shots": out}


def proplan(task, locks):
    need = ("speaker", "font", "palette", "motion_direction")
    miss = [k for k in need if not locks.get(k)]
    if miss:
        raise ValueError(f"lock {miss}")
    stage = {"stage": "model_prompt_with_continuity", "locks": locks}
    prompts = [f"{s}. Speaker {locks['speaker']}; font {locks['font']}; palette {locks['palette']}; motion {locks['motion_direction']}." for s in task]
    return stage, prompts


SLOTS24 = ("role", "context", "task", "inputs", "constraints", "output_format", "edge_cases", "quality_bar")


def llm_lint(p, untrusted=()):
    tags = re.findall(r"<(\w+)>", p)
    present = [s for s in SLOTS24 if s in tags]
    order_ok = present == [s for s in SLOTS24 if s in present] and [t for t in tags if t in SLOTS24] == present
    undelimited = [u for u in untrusted if u in p and not re.search(rf"<untrusted>[^<]*{re.escape(u)}", p)]
    if undelimited:
        return 3, "untrusted input not delimited"
    if len(present) < 8 or not order_ok:
        return 1, f"missing or out of order: {[s for s in SLOTS24 if s not in present]}"
    return 0, "ok"


def egypt_pack():
    shots = [("orbit dive", 24, 3), ("Giza solar mirrors", 35, 4), ("Nile train", 28, 4), ("Cairo lotus tower", 24, 4), ("Alexandria Pharos", 35, 3)]
    neg = ["text artifacts", "logos", "watermarks", "real people", "distorted pyramids", "dystopia", "smog", "flags"]
    out = []
    for name, lens, d in shots:
        base = f"{name}, {lens}mm, gold / warm white / cyan on near-black, 9:16, 30 fps, {d} s"
        out.append({"kling": {"prompt": base, "negative_prompt": ", ".join(neg)}, "runway": {"prompt": base},
                    "veo": {"prompt": base, "notes": "last frame -> next first frame"}})
    return shots, out


LOOKS = {"Film Noir": "B&W, venetian blinds, smoke, 1940s", "Cyberpunk Neon": "neon, holograms, rain reflections, teal + magenta",
         "Claymation": "stop-motion, fingerprints", "Ukiyo-e": "woodblock, flat planes"}


LIVING = {"wes anderson", "greg rutkowski", "hayao miyazaki"}


def pick_look(name, style_layer_extra=""):
    if any(a in style_layer_extra.lower() for a in LIVING):
        raise ValueError("describe traits, never a living artist's name")
    return {"style": LOOKS[name], "lock": LOOKS[name]}


PRE = "isometric low-poly floating island, matte clay, tilt-shift, soft contact shadow, background [BG_HEX], palette [PALETTE]"


TAIL = "no text, no letters, no logos"


def preamble_prompt(subject, bg, pal):
    return PRE.replace("[BG_HEX]", bg).replace("[PALETTE]", pal) + f", {subject}, {TAIL}"


def freeze_lock(lock_text, prompts_by_subject, names=LIVING):
    if any(n in lock_text.lower() for n in names) or re.search(r"\bstudio ghibli|pixar\b", lock_text, re.I):
        return False, "traits only, no names"
    held = [s for s, p in prompts_by_subject.items() if lock_text in p]
    return len(held) >= 2, held


DOMAIN = {"portrait": {"lens": "85mm", "f": "f/1.4-f/5.6", "light": "Rembrandt", "aspect": "4:5"},
          "food": {"lens": "50mm", "light": "overhead window light", "aspect": "4:5"},
          "landscape": {"lens": "16mm", "light": "golden hour haze", "aspect": "16:9", "layers": "foreground/mid/background"},
          "product": {"lens": "100mm macro", "light": "softbox + strip rims", "aspect": "1:1"},
          "cinema": {"body": "ARRI Alexa 65", "stock": "Kodak Vision3 500T"}}


def modifiers(domain, subject):
    d = DOMAIN[domain]
    return f"{subject}, " + ", ".join(v for k, v in d.items() if k != "aspect") + (f" --ar {d['aspect']}" if "aspect" in d else "")


def teal_orange(img, amount=0.3):
    a = img.astype(np.float64) / 255
    lum = a.mean(axis=2, keepdims=True)
    teal, orange = np.array([0.0, 0.5, 0.5]), np.array([1.0, 0.55, 0.2])
    w = np.clip((lum - 0.2) / 0.6, 0, 1)
    tint = (1 - w) * teal + w * orange
    out = a * (1 - amount) + amount * tint * (0.5 + lum)
    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


CFG = {"photoreal": (0.4, 0.5), "cinematic": (0.5, 0.6), "neon cyberpunk": (0.5, 0.6), "anime": (0.6, 0.7), "vintage 8 mm": (0.6, 0.7),
       "watercolor": (0.7, 0.8), "pixel art": (0.8, 0.9)}


def kling_cfg(style, requested=None):
    lo, hi = CFG[style]
    if requested is None:
        return round((lo + hi) / 2, 2)
    return min(hi, max(lo, requested))


def measure_image(img, k=3):
    a = np.asarray(img).reshape(-1, 3).astype(np.float32)
    _, labels, centers = cv2.kmeans(a, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5), 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.ravel(), minlength=k)
    order = np.argsort(-counts)
    hexes = ["#%02x%02x%02x" % tuple(int(round(c)) for c in centers[i]) for i in order]
    w, h = img.size
    return {"palette": hexes, "share": (counts[order] / counts.sum()).round(2).tolist(), "aspect": f"{w}:{h}",
            "brightness": round(float(a.mean()) / 255, 3)}


BAD_TAGS = ("script", "foreignObject", "image", "iframe", "a", "style", "animate", "set")


def sanitize_svg(svg):
    for t in BAD_TAGS:
        svg = re.sub(rf"<{t}\b[^>]*/>|<{t}\b.*?</{t}>", "", svg, flags=re.S | re.I)
    svg = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", svg)
    svg = re.sub(r"\s(xlink:)?href\s*=\s*(\"[^\"]*\"|'[^']*')", "", svg)
    svg = re.sub(r"url\((?!#)[^)]*\)", "none", svg)
    svg = re.sub(r"javascript:", "", svg, flags=re.I)
    return svg


def extract_code(text):
    m = re.findall(r"```[\w+-]*\n(.*?)```", text, re.S)
    if m:
        return m[0].rstrip("\n")
    stripped = re.sub(r"^```\w*\s*$", "", text, flags=re.M).strip()
    return stripped


def bridge(prompt, backend, cli_checked_at=None, now=0):
    if backend == "none":
        return {"route": "manual package"}
    via = "stdin" if len(prompt) >= 28000 else "argv"
    fresh = cli_checked_at is not None and now - cli_checked_at < 600
    return {"route": "cli" if backend in ("auto", "cli") and fresh else "api", "via": via, "timeout": 240, "max_tokens": 8000}


def image_route(need, client_work=False):
    tree = {"text in image": ["Ideogram", "Gemini", "GPT Image"], "set consistency": ["Flux multi-reference", "Nano Banana Pro", "Recraft"],
            "edit existing": ["Gemini", "Flux Kontext", "ChatGPT Images"], "vector": ["Recraft", "draw it yourself"],
            "volume": ["Flux Schnell", "Gemini Flash", "self-hosted SD"]}
    opts = tree[need]
    if client_work:
        opts = [o for o in opts if o != "FLUX.1-dev"]
    return opts[0], opts


RECIPE = {"sdxl": {"sampler": "dpmpp_2m", "scheduler": "karras", "steps": 25, "cfg": (7, 8)},
          "flux": {"sampler": "euler", "scheduler": "sgm_uniform", "steps": 20, "cfg": (1, 3.5)},
          "krea": {"sampler": "euler", "scheduler": "simple", "steps": 20, "cfg": (1, 1)}}


def karras(n, smin=0.0292, smax=14.6146, rho=7.0):
    r = np.linspace(0, 1, n)
    return (smax ** (1 / rho) + r * (smin ** (1 / rho) - smax ** (1 / rho))) ** rho


def recipe_ok(model, cfg, denoise, mode):
    lo, hi = RECIPE[model]["cfg"]
    dn = (denoise == 1.0) if mode == "txt2img" else 0.3 <= denoise <= 0.7
    return lo <= cfg <= hi and dn


def band_check(kind, v):
    return {"lora_style": 0.6 <= v <= 0.9, "lora_concept": 0.4 <= v <= 0.6, "controlnet": 0.3 <= v <= 1.0, "inpaint_denoise": 0.6 <= v <= 0.85}[kind]


def inpaint_composite(orig, regen, mask):
    m = (mask > 127)[..., None]
    return np.where(m, regen, orig)


def video_route(need, stage):
    final = {"quality+audio": "Veo 3", "volume": "Kling professional", "character": "Seedance R2V", "self-hosted": "Wan 2.x"}
    draft = {"quality+audio": "Gemini Flash 512 still + Kling standard", "volume": "Kling standard", "character": "Seedance 480p",
             "self-hosted": "Wan 2.x 480p"}
    return (draft if stage == "draft" else final)[need]


def motion_prompt(image_desc, action, move, pace, dur):
    p = f"{action}, camera {move}, {pace}, {dur} s"
    redesc = sorted(set(w for w in words(image_desc) if len(w) > 4) & set(words(p)))
    return p, redesc


def prompt_only_cards(shots, approved_cost=False):
    cards = [{"shot": s, "prompt": f"{s}, 9:16", "label": "prompt only — none has been rendered"} for s in shots]
    return {"cards": cards, "may_render": approved_cost, "credentials": "HF_CREDENTIALS=<placeholder>"}


def song_brief(lyrics):
    blocks = [b.strip() for b in lyrics.split("\n\n") if b.strip()]
    from collections import Counter
    c = Counter(blocks)
    chorus = max(c, key=c.get)
    hook = chorus.splitlines()[0]
    return {"chorus": chorus, "hook": hook, "reel_cut": [hook, chorus], "master": "user returns the track; treat as untouched master"}


LANES = {"image": r"(image|photo|poster|graphic|illustration|صورة|بوستر|رسم|جرافيك|تصوير)",
         "video": r"(video|animation|avatar|motion|reel|فيديو|تحريك|أفاتار|موشن)"}


PRIORITY = {"Figma": 100, "Adobe Express": 98, "Adobe": 90, "Canva": 88, "Runway": 88, "Higgsfield": 86, "OpenArt": 84, "HeyGen": 82}


def route_lanes(task, registered, connected):
    lanes = [l for l, rx in LANES.items() if re.search(rx, task, re.I)]
    usable = sorted((a for a in registered if a in connected), key=lambda a: -PRIORITY[a])
    return lanes, usable


def corpus_search(root: Path, query, hits=8, per_file=3, length=200):
    length = max(200, min(30000, length))
    out = []
    q = query.lower()
    for f in sorted(root.glob("*.txt")):
        t = f.read_text(encoding="utf-8")
        n = 0
        for m in re.finditer(re.escape(q), t.lower()):
            if n >= per_file or len(out) >= hits:
                break
            out.append({"file": f.name, "offset": m.start(), "text": t[m.start():m.start() + length]})
            n += 1
    return out


def tile_state(t, i, n=4, rtl=True, dur=1.0, stagger=0.3):
    order = (n - 1 - i) if rtl else i
    u = min(1, max(0, (t - order * stagger) / dur))
    e = 1 - (1 - u) ** 2                     # power2.out
    return round(40 * (1 - e), 2), round(0.4 + 0.6 * e, 3)


def _noise(x, y, seed=0):
    xi, yi = np.floor(x).astype(int), np.floor(y).astype(int)
    xf, yf = x - xi, y - yi

    def h(a, b):
        v = np.sin(a * 127.1 + b * 311.7 + seed * 74.7) * 43758.5453
        return v - np.floor(v)
    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    return (h(xi, yi) * (1 - u) + h(xi + 1, yi) * u) * (1 - v) + (h(xi, yi + 1) * (1 - u) + h(xi + 1, yi + 1) * u) * v


def fbm(x, y):
    s, a = 0.0, 0.5
    for i in range(4):
        s = s + a * _noise(x * 2 ** i, y * 2 ** i, i)
        a *= 0.5
    return s / 0.9375


RAMP = np.array([[200, 180, 255], [120, 230, 240], [255, 190, 210], [240, 200, 110], [170, 240, 200]], float)


def iridescent(t, W=64, H=36):
    y, x = np.mgrid[0:H, 0:W] / 12.0
    q = fbm(x, y)
    r = fbm(x + 4 * q + 0.15 * t, y + 4 * q)
    v = fbm(x + 4 * r, y + 4 * r)
    idx = np.clip(v, 0, 0.999) * 4
    i0 = idx.astype(int)
    f = (idx - i0)[..., None]
    col = RAMP[i0] * (1 - f) + RAMP[np.minimum(i0 + 1, 4)] * f
    rim = (1 - np.abs(v - 0.5) * 2) ** 3
    return np.clip(col + rim[..., None] * 60, 0, 255).astype(np.uint8)


def ken_burns(img, u, s0=1.0, s1=1.06, pan=0.015):
    e = 0.5 - 0.5 * math.cos(math.pi * u)
    s = s0 + (s1 - s0) * e
    W, H = img.size
    w, h = W / s, H / s
    cx = W / 2 + pan * W * e
    box = (cx - w / 2, H / 2 - h / 2, cx + w / 2, H / 2 + h / 2)
    return img.resize((W, H), Image.BICUBIC, box=box), s, cx


def triage(assets):
    rows = []
    for a in assets:
        if a["type"] in ("typography", "logo", "chart"):
            src = "compose"
        elif a.get("existing"):
            src = "use-existing"
        elif a.get("can_photograph"):
            src = "photograph"
        else:
            src = "generate"
        rows.append((a["name"], a["type"], src))
    eliminated = sum(1 for r in rows if r[2] != "generate")
    return rows, eliminated


def plate_prompt_ok(prompt, refs):
    baked = bool(re.search(r"\"[^\"]+\"|«[^»]+»|text that says|with the words", prompt))
    return (not baked) and "text-free" in prompt and 3 <= len(refs) <= 10


def outlier_action(images, thresh=40):
    means = np.array([np.asarray(i).reshape(-1, 3).mean(axis=0) for i in images])
    med = np.median(means, axis=0)
    out = [k for k, m in enumerate(means) if np.linalg.norm(m - med) > thresh]
    if not out:
        return out, "consistent"
    return out, "regenerate the outlier" if len(out) == 1 else "fix the base and regenerate all" if len(out) >= 3 else "regenerate outliers"


def budget_log(calls, unit_prices, cap):
    spent, log = 0.0, []
    for c in calls:
        cost = unit_prices[c["kind"]]
        if spent + cost > cap:
            return 1, log + [f"REFUSED {c['kind']}: over cap {cap}"]
        spent += cost
        log.append(f"{c['kind']} {cost} -> {spent}")
    return 0, log


def yield_flag(kept, generated, rounds):
    flags = []
    if generated and kept / generated < 0.3:
        flags.append("weak prompt (<30 % yield)")
    if rounds > 3:
        flags.append("switch to composition (>3 rounds)")
    return flags


NONCOMM = {"FLUX.1-dev", "SD3-medium-noncommercial"}


def licence_audit(brief, manifest):
    bad = [m["file"] for m in manifest if brief["use"] == "commercial" and m["model"] in NONCOMM]
    needs_indemnity = brief.get("resold", False)
    return bad, needs_indemnity


def disclosure(manifest, endcard):
    needs = any(m["generated"] and m["kind"] in ("human", "voice") for m in manifest)
    ok = (not needs) or bool(re.search(r"AI|generated|مولّد|ذكاء اصطناعي", endcard))
    return needs, ok


def cut_plan(ref_lengths, take_s, seed=3, min_s=0.8):
    rng = np.random.default_rng(seed)
    cuts, t = [], 0.0
    while True:
        L = float(rng.choice(ref_lengths))
        if t + L > take_s:
            break
        cuts.append((round(t, 2), round(t + L, 2)))
        t += L
    return cuts, sum(b - a for a, b in cuts) / take_s


ALLOWED_LIC = {"pexels", "pixabay", "own", "cc0", "cc-by"}


def pipeline_check(stage):
    errs = []
    for s in stage["script"]:
        n = len(stage["terms"].get(s, []))
        if not 2 <= n <= 3:
            errs.append(f"terms for '{s}': {n}")
    errs += [f"clip {c['url']} licence {c['licence']}" for c in stage["clips"] if c["licence"] not in ALLOWED_LIC]
    if not stage["approved"].get("script") or not stage["approved"].get("clips"):
        errs.append("user approval missing before render")
    if stage.get("voice") == "cloned" and not stage.get("consent"):
        errs.append("cloned voice without consent")
    return errs
