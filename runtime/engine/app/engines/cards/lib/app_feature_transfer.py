"""Helpers of power_programs/app_feature_transfer.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from PIL import ImageChops
from PIL import ImageDraw
from pathlib import Path
import fnmatch
import hashlib
import json
import math
import numpy as np
import os
import re
import subprocess
import yaml


def save_json(work, name, obj):
    (work / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def ff(*args, ok=True):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], capture_output=True, text=True)
    if ok and r.returncode:
        raise RuntimeError(r.stderr[-600:])
    return r


def probe(p):
    return json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(p)],
                                     capture_output=True, text=True, check=True).stdout)


def dur(p):
    return float(probe(p)["format"]["duration"])


def choose_ui(event: str, online: bool, local_ok: bool):
    if event == "did-fail-load" or not online:
        return "local:offline.html" if local_ok else "error"
    return "remote"


FLIP = [("margin-left", "margin-right"), ("padding-left", "padding-right"), ("border-left", "border-right"), ("left", "right"),
        ("text-align: left", "text-align: right")]


def to_rtl(css: str) -> str:
    out = css
    for a, b in FLIP:
        out = re.sub(rf"(?<![\w-]){re.escape(a)}(?![\w-])", "\0TMP\0", out)
        out = re.sub(rf"(?<![\w-]){re.escape(b)}(?![\w-])", a, out)
        out = out.replace("\0TMP\0", b)
    out = re.sub(r"translateX\((-?)(\d+)px\)", lambda m: f"translateX({'' if m.group(1) else '-'}{m.group(2)}px)", out)
    return out


def bundle_for(lang):
    return "app.rtl.css" if lang.split("-")[0] in ("ar", "he", "fa", "ur") else "app.ltr.css"


EXTS = "avi gif heic jpeg jpg key mkv mov mp4 mpeg numbers pages png svg webm webp".split()


def associations():
    import mimetypes
    mimetypes.add_type("image/heic", ".heic")
    mimetypes.add_type("video/x-matroska", ".mkv")
    mimetypes.add_type("image/webp", ".webp")
    for e, m in (("key", "application/x-iwork-keynote-sffkey"), ("numbers", "application/x-iwork-numbers-sffnumbers"), ("pages", "application/x-iwork-pages-sffpages")):
        mimetypes.add_type(m, "." + e)
    return [{"ext": e, "mimeType": mimetypes.guess_type("f." + e)[0]} for e in EXTS]


def files_from_argv(argv):
    return [a for a in argv[1:] if not a.startswith("-") and Path(a).suffix.lstrip(".").lower() in EXTS]


SENTINEL = b"dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX"


FUSES = ["RunAsNode", "EnableCookieEncryption", "EnableNodeOptionsEnvironmentVariable", "EnableNodeCliInspectArguments",
         "EnableEmbeddedAsarIntegrityValidation", "OnlyLoadAppFromAsar"]


WANT = {"RunAsNode": "0", "EnableCookieEncryption": "1", "EnableNodeOptionsEnvironmentVariable": "0", "EnableNodeCliInspectArguments": "0",
        "EnableEmbeddedAsarIntegrityValidation": "1", "OnlyLoadAppFromAsar": "1"}


def write_fuses(states: dict) -> bytes:
    wire = bytes([1, len(FUSES)]) + "".join(states[f] for f in FUSES).encode()
    return os.urandom(64) + SENTINEL + wire + os.urandom(64)


def read_fuses(blob: bytes) -> dict:
    i = blob.index(SENTINEL) + len(SENTINEL)
    ver, n = blob[i], blob[i + 1]
    vals = blob[i + 2:i + 2 + n].decode()
    return {"version": ver, **{FUSES[k]: vals[k] for k in range(n)}}


def fuse_audit(blob):
    f = read_fuses(blob)
    return [k for k, v in WANT.items() if f[k] != v]


def update_decision(latest_yml: str, current: str, payload: bytes, recording: bool):
    import base64
    meta = yaml.safe_load(latest_yml)
    newer = tuple(map(int, meta["version"].split("."))) > tuple(map(int, current.split(".")))
    ok_hash = base64.b64encode(hashlib.sha512(payload).digest()).decode() == meta["sha512"]
    if not newer:
        return "up-to-date"
    if not ok_hash:
        return "reject: sha512 mismatch"
    return "defer: recording" if recording else "offer to user"


PII = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"), (re.compile(r"(?:/Users|/home|C:\\\\Users)[/\\\\][^/\\\\\s]+"), "<home>"),
       (re.compile(r"\b(?:\+?966|0)5\d{8}\b"), "[phone]")]


def scrub(event: dict) -> dict:
    txt = json.dumps(event, ensure_ascii=False)
    for rx, rep in PII:
        txt = rx.sub(rep, txt)
    return json.loads(txt)


def send_report(event, consent):
    return scrub(event) if consent else None


def parse_deeplink(url, scheme="myapp"):
    from urllib.parse import urlsplit, parse_qs
    u = urlsplit(url)
    if u.scheme != scheme:
        return None
    return {"action": u.netloc, "path": u.path.strip("/"), "query": {k: v[0] for k, v in parse_qs(u.query).items()}}


def second_instance(argv, scheme="myapp"):
    links = [a for a in argv if a.startswith(scheme + "://")]
    return parse_deeplink(links[0], scheme) if links else {"action": "focus"}


def bootstrap(payload: bytes, expected_sha: str, cert_der: bytes, pins: set):
    pin = "sha256//" + __import__("base64").b64encode(hashlib.sha256(cert_der).digest()).decode()
    if pin not in pins:
        return "abort: certificate pin mismatch"
    if sha256(payload) != expected_sha:
        return "abort: payload hash mismatch"
    return "run"


def v7_to_v8(d): return {**{k: v for k, v in d.items() if k != "expo"}, "exposure": d["expo"], "version": 8}


def v8_to_v9(d): return {**d, "exposure": {"ev": d["exposure"]}, "version": 9}


def v9_to_v10(d): return {**d, "tags": d.get("tags", []), "version": 10}


MIGRATIONS = {7: v7_to_v8, 8: v8_to_v9, 9: v9_to_v10}


def migrate(doc, latest=10):
    while doc["version"] < latest:
        if doc["version"] not in MIGRATIONS:
            raise ValueError(f"no migration from v{doc['version']}")
        doc = MIGRATIONS[doc["version"]](doc)
    return doc


def radial_mask(H, W, cx, cy, r, feather):
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.hypot(xx - cx, yy - cy)
    return np.clip((r + feather - d) / feather, 0, 1)


def local_adjust(img, mask, adjust):
    m = mask[..., None]
    return img * (1 - m) + adjust(img) * m


def build_asset(params: dict, seed: int):
    rng = np.random.default_rng(seed)
    n, r, jitter = params["segments"], params["radius"], params["jitter"]
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    rad = r * (1 + jitter * rng.uniform(-1, 1, n))
    return np.stack([rad * np.cos(ang), rad * np.sin(ang)], 1)


def cached_build(cache: Path, params, seed):
    key = sha256(json.dumps({"p": params, "s": seed}, sort_keys=True).encode())[:16]
    p = cache / f"{key}.json"
    if p.exists():
        return json.loads(p.read_text()), True
    g = build_asset(params, seed).round(6).tolist()
    p.write_text(json.dumps(g))
    return g, False


def export_animation(keys, fps=30):
    """One keyframed property (x over time) -> Lottie layer JSON, SVG SMIL and glTF animation sampler."""
    import base64
    import struct
    op = round(keys[-1][0] * fps)
    lottie = {"v": "5.7.0", "fr": fps, "ip": 0, "op": op, "w": 200, "h": 100,
              "layers": [{"ty": 4, "ks": {"p": {"a": 1, "k": [{"t": round(t * fps), "s": [x, 50, 0]} for t, x in keys]}}}]}
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100"><circle r="8" cy="50"><animate attributeName="cx" '
           f'dur="{keys[-1][0]}s" values="{";".join(str(x) for _, x in keys)}" keyTimes="{";".join(str(round(t / keys[-1][0], 4)) for t, _ in keys)}" repeatCount="indefinite"/></circle></svg>')
    times = struct.pack(f"<{len(keys)}f", *[t for t, _ in keys])
    vals = struct.pack(f"<{3 * len(keys)}f", *[v for _, x in keys for v in (x / 100, 0.5, 0)])
    buf = times + vals
    gltf = {"asset": {"version": "2.0"}, "nodes": [{"name": "dot"}], "scenes": [{"nodes": [0]}],
            "buffers": [{"byteLength": len(buf), "uri": "data:application/octet-stream;base64," + base64.b64encode(buf).decode()}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(times)}, {"buffer": 0, "byteOffset": len(times), "byteLength": len(vals)}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": len(keys), "type": "SCALAR", "min": [keys[0][0]], "max": [keys[-1][0]]},
                          {"bufferView": 1, "componentType": 5126, "count": len(keys), "type": "VEC3"}],
            "animations": [{"samplers": [{"input": 0, "output": 1, "interpolation": "LINEAR"}], "channels": [{"sampler": 0, "target": {"node": 0, "path": "translation"}}]}]}
    return lottie, svg, gltf


def fidelity_check(contract, ref, built):
    allowed = set(contract["deviations"])
    diffs = sorted(k for k in ref if ref[k] != built.get(k))
    return {"undeclared": [d for d in diffs if d not in allowed], "declared": [d for d in diffs if d in allowed]}


def computed(styles, tokens):
    return {k: tokens.get(v[4:-1], v) if isinstance(v, str) and v.startswith("var(") else v for k, v in styles.items()}


def accept_tokenisation(before, after, tokens):
    return computed(before, tokens) == computed(after, tokens)


def render_ui(elements, W=144, H=90):
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    for e in elements:
        d.rectangle(e["box"], fill=e["fill"])
    return im


def first_diff_element(ref, built, elements):
    diff = ImageChops.difference(ref, built)
    bbox = diff.getbbox()
    if not bbox:
        return None, None
    for e in sorted(elements, key=lambda e: (e["box"][1], e["box"][0])):
        x0, y0, x1, y1 = e["box"]
        if not (x1 < bbox[0] or x0 > bbox[2] or y1 < bbox[1] or y0 > bbox[3]):
            return e["id"], bbox
    return "unknown", bbox


def design_foundation(repo: Path):
    css = "\n".join(p.read_text() for p in sorted(repo.rglob("*.css")))
    def block(sel):
        m = re.search(re.escape(sel) + r"\s*{([^}]*)}", css)
        return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", m.group(1))) if m else {}
    fonts = re.findall(r"@font-face\s*{[^}]*font-family:\s*['\"]?([^;'\"]+)", css)
    strategy = "class" if ".dark" in css else "media" if "prefers-color-scheme" in css else "none"
    return {"root": block(":root"), "dark": block(".dark"), "fonts": fonts, "theme_strategy": strategy}


def theme_css(theme):
    errs = []
    if set(theme["light"]) != set(theme["dark"]):
        errs.append("modes have different keys")
    if not theme.get("intent"):
        errs.append("missing designer intent")
    if theme.get("default") not in ("light", "dark"):
        errs.append("default mode")
    for f in theme.get("fonts", []):
        if f.get("licence") not in ("OFL", "Apache-2.0", "MIT"):
            errs.append(f"font licence {f['family']}")
    css = ":root{" + ";".join(f"--{k}:{v}" for k, v in theme["light"].items()) + "}\n.dark{" + ";".join(f"--{k}:{v}" for k, v in theme["dark"].items()) + "}"
    return css, errs


def frame_rules(jsx: str):
    errs = []
    if re.search(r"onClick=\{\s*\(\)\s*=>\s*\{\s*\}\s*\}", jsx):
        errs.append("empty onClick")
    if re.search(r"<(?:div|main)[^>]*className=\"root\"[^>]*style=\{\{[^}]*width:\s*['\"]?\d+px", jsx):
        errs.append("fixed root width")
    if re.search(r"device-frame|iphone-frame", jsx):
        errs.append("device frame drawn")
    return errs


CONTRACT_KEYS = ["props", "callbacks", "state", "requests", "routes", "validation", "loading", "empty", "error", "keyboard", "aria"]


def behaviour_gaps(old, new):
    gaps = []
    for k in CONTRACT_KEYS:
        missing = sorted(set(old.get(k, [])) - set(new.get(k, [])))
        if missing:
            gaps.append((k, missing))
    return gaps


def preflight(env):
    report = {"auth": {s: bool(env.get(f"{s.upper()}_TOKEN")) for s in ("github", "media")}, "project": env.get("PROJECT"), "version": env.get("TOOL_VERSION")}
    if not report["version"]:
        nxt = "install"
    elif not all(report["auth"].values()):
        nxt = "sign in: " + ",".join(k for k, v in report["auth"].items() if not v)
    elif not report["project"]:
        nxt = "ask which project"
    else:
        nxt = "continue"
    report["next"] = nxt
    return report


def manifest(root, patterns):
    return {str(p.relative_to(root)): sha256(p.read_bytes()) for p in sorted(root.rglob("*")) if p.is_file() and any(fnmatch.fnmatch(str(p.relative_to(root)), pt) for pt in patterns)}


def handoff(root, base, allow):
    now = {str(p.relative_to(root)): sha256(p.read_bytes()) for p in sorted(root.rglob("*")) if p.is_file()}
    changed = sorted(k for k in now if k in base and now[k] != base[k])
    deleted = sorted(k for k in base if k not in now)
    added = sorted(k for k in now if k not in base)
    outside = [k for k in changed + added if not any(fnmatch.fnmatch(k, a) for a in allow)]
    state = "no change" if not (changed or deleted or added) else ("rejected" if outside else "changed")
    return {"state": state, "changed": changed, "deleted": deleted, "added": added, "outside_allowlist": outside}


def pinned_export(ref: Path, pin: str):
    now = sha256(ref.read_bytes())
    return {"ok": now == pin, "pinned": pin[:12], "current": now[:12]}


def worker_briefs(refs_path: Path, scenes):
    refs = json.loads(refs_path.read_text())
    lock = {k: refs["lock"][k] for k in ("palette", "fonts")}
    return [{"scene": s, "refs": str(refs_path), "lock": lock, "roles": sorted({r["role"] for r in refs["files"]})} for s in scenes]


def fan_out(scene: dict, axes: dict, work: Path):
    base = work / "scene"
    base.mkdir()
    (base / "scene.json").write_text(json.dumps(scene, sort_keys=True))
    out = []
    for axis, value in axes.items():
        d = work / f"scene--{axis}"
        d.mkdir()
        v = dict(scene, **{axis: value})
        (d / "scene.json").write_text(json.dumps(v, sort_keys=True))
        out.append(d)
    return base, out


def render_cards(template, records):
    return [template.format(**r) for r in records]


def sketch_slots(img):
    import cv2
    a = np.asarray(img.convert("L"))
    cs, hier = cv2.findContours((a < 128).astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    H, W = a.shape
    boxes = []
    for i, c in enumerate(cs):
        if hier[0][i][3] != -1:
            continue
        x, y, w, h = cv2.boundingRect(c)
        if w * h > 200:
            boxes.append((round(x / W, 2), round(y / H, 2), round(w / W, 2), round(h / H, 2)))
    return sorted(boxes, key=lambda b: (b[1], b[0]))


def xfade_plan(durs, T, fps=30):
    offs, acc = [], durs[0]
    for i in range(1, len(durs)):
        t = min(T, durs[i - 1] / 2, durs[i] / 2)
        t = round(t * fps) / fps
        offs.append((round((acc - t) * fps) / fps, t))
        acc = acc + durs[i] - t
    return offs, acc


def atempo_chain(S):
    parts = []
    while S < 0.5:
        parts.append(0.5)
        S /= 0.5
    while S > 100:
        parts.append(100.0)
        S /= 100
    parts.append(round(S, 6))
    return parts


def media_plan(p):
    info = probe(p)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    rot = 0
    for sd in v.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(sd["rotation"])
    w, h = (v["height"], v["width"]) if abs(rot) % 180 == 90 else (v["width"], v["height"])
    d = float(info["format"]["duration"])
    container = info["format"]["format_name"]
    web = v["codec_name"] in ("h264", "hevc", "vp9", "av1") and v["pix_fmt"] == "yuv420p" and any(c in container for c in ("mp4", "mov", "webm"))
    return {"display": (w, h), "poster_at": min(0.1 * d, 1.0), "proxy": not web, "duration": d}


def peaks(pcm: np.ndarray, per=80):
    n = len(pcm) // per
    v = np.abs(pcm[: n * per].reshape(n, per)).max(axis=1).astype(float)
    return (np.sqrt(v / v.max()) * 255).round().astype(int)


def bitrate(w, h, fps, quality="normal", codec="h264"):
    bpp = {"normal": 0.07, "high": 0.12, "max": 0.2}[quality]
    return round(bpp * w * h * fps * (0.65 if codec == "hevc" else 1))


def encode_with_fallback(src, out, kbps):
    tried = []
    for enc in ("h264_videotoolbox", "h264_nvenc", "libx264"):
        r = ff("-i", src, "-c:v", enc, "-b:v", f"{kbps}k", "-movflags", "+faststart", out, ok=False)
        tried.append((enc, r.returncode))
        if r.returncode == 0:
            return enc, tried
        if not re.search(r"(Unknown encoder|Error while opening encoder|Cannot load|No device|not found|Could not open)", r.stderr, re.I):
            return None, tried
    return None, tried


def guard(req, root: Path, app="kosif", hosts=("127.0.0.1:7777", "localhost:7777")):
    if req.get("bind") not in ("127.0.0.1", None):
        return 500, "bind"
    if req["headers"].get("Host") not in hosts:
        return 403, "host"
    if req["method"] != "GET" and req["headers"].get(f"X-{app}") != "1":
        return 403, "csrf"
    if "id" in req and not re.fullmatch(r"[a-z0-9-]{1,40}", req["id"]):
        return 400, "id"
    target = os.path.normpath(os.path.join(str(root), req.get("path", "").lstrip("/")))
    if not (target + os.sep).startswith(str(root) + os.sep) and target != str(root):
        return 403, "path"
    return 200, "ok"
