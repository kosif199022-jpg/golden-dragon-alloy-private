"""Helpers of runners/fam_skills_part1.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from .core import fx
import json
import math
import re
import subprocess


def jw(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def tw(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


def rel_lum(hexc):
    hexc = hexc.lstrip("#")
    rgb = [int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted([rel_lum(a), rel_lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


SECRET_RE = re.compile(r"(sk_live_[0-9a-zA-Z]{8,}|AKIA[0-9A-Z]{16}|ghp_[0-9A-Za-z]{20,}|(?i:api[_-]?key|secret|password|token)"
                       r"\s*[=:]\s*['\"][^'\"\s$]{8,}['\"])")


def secrets_in(text):
    return SECRET_RE.findall(text)


def md_sections(text):
    return [m.group(1).strip() for m in re.finditer(r"^#{1,3}\s+(.+)$", text, re.M)]


def words(text):
    return re.findall(r"[\w\u064B-\u065F\u0670]+", text)


def _entry_balanced(e):
    return sum(Decimal(l[1]) for l in e["lines"]) == sum(Decimal(l[2]) for l in e["lines"])


def _ad_lint(ad):
    issues = []
    b = [s["start"] for s in ad["segments"]] + [ad["segments"][-1]["end"]]
    if b != [0, 3, 10, 22, 30]:
        issues.append("structure %s" % b)
    vo = " ".join(s["vo"] for s in ad["segments"])
    if len(words(vo)) > 70:
        issues.append("vo %d words" % len(words(vo)))
    if sum(1 for s in ad["segments"] if s.get("cta")) != 1:
        issues.append("cta count")
    if {h["type"] for h in ad["hooks"]} != {"question", "visual", "result"}:
        issues.append("hooks")
    for s in ad["segments"]:
        if not set(words(s["on_screen"])) <= set(words(s["vo"])):
            issues.append("on-screen text not in VO at %s" % s["start"])
        if len(words(s["vo"])) / (s["end"] - s["start"]) > 3.0:
            issues.append("pace at %s" % s["start"])
    for c in ad.get("claims", []):
        if not c.get("proof"):
            issues.append("claim without proof")
    return issues


_BANNED = re.compile(r"(?i)\b(ghibli|pixar|disney|greg rutkowski|miyazaki|wes anderson|in the style of)\b")


_STYLES = {
    "flat-anime": {"lock": "clean cel shading, bold uniform outlines, two-tone shadows, saturated flat colour fields",
                   "light": "soft overcast key from upper left", "lens": "orthographic-feel 50mm, deep focus",
                   "neg": "photoreal skin, bokeh, film grain, lens flare"},
    "archival-photo": {"lock": "silver gelatin print, fine grain, gentle halation, lifted blacks",
                       "light": "single window key from camera left, 4300K", "lens": "35mm f/2.8, natural perspective",
                       "neg": "neon, HDR halo, plastic skin, cartoon outlines"}}


def _style_prompt(style, subject):
    s = _STYLES[style]
    return "%s. STYLE LOCK: %s. LIGHT: %s. LENS: %s. NEGATIVE: %s" % (subject, s["lock"], s["light"], s["lens"], s["neg"])


def _style_lint(p, style):
    iss = []
    if _BANNED.search(p):
        iss.append("artist/studio name")
    if "NEGATIVE:" not in p or not p.split("NEGATIVE:")[1].strip():
        iss.append("no negatives")
    if "anime" in style and re.search(r"f/1\.[0-9]", p):
        iss.append("shallow aperture on anime")
    return iss


_AR = "\u0600-\u06FF"


def _ar_typo_issues(t):
    iss = []
    iss += ["latin comma"] * len(re.findall(r"(?<=[%s]) ?,|,(?= ?[%s])" % (_AR, _AR), t))
    iss += ["latin question mark"] * len(re.findall(r"(?<=[%s])\s*\?" % _AR, t))
    iss += ["space before punctuation"] * len(re.findall(r" +[،؛؟.!:]", t))
    if re.search(r"[0-9]", t) and re.search(r"[\u0660-\u0669]", t):
        iss.append("mixed digit systems")
    return iss


def _ar_typo_fix(t):
    t = re.sub(r"(?<=[%s]) ?, ?" % _AR, "، ", t)
    t = re.sub(r"(?<=[%s])\s*\?" % _AR, "؟", t)
    t = re.sub(r" +([،؛؟.!:])", r"\1", t)
    t = t.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    return re.sub(r"  +", " ", t)


def _ebur(path):
    d = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=60).stderr
    tail = d[d.rfind("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+) LUFS", tail).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", tail).group(1))
    return i, tp


def _ngrams(t, n=15):
    w = re.findall(r"\w+", t.lower())
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def _distil(chap, text):
    fws = re.findall(r"The ([A-Z][\w ]+?) Framework: ([^.]+)\.", text)
    principles = re.findall(r"Principle: ([^.]+)\.", text)
    anti = re.findall(r"Anti-pattern: ([^.]+)\.", text)
    out = []
    for name, how in fws:
        steps = [s.strip() for s in re.split(r",| then | and ", how) if s.strip()]
        out.append({"framework": name, "chapter": chap, "steps": [" ".join(s.split()[:8]) for s in steps]})
    return out, [" ".join(p.split()[:10]) for p in principles], [" ".join(a.split()[:9]) for a in anti]


_PRD_SECTIONS = ["Problem", "Users and persona", "Goals and metrics", "Requirements", "Out of scope", "Risks", "Launch plan", "Open questions"]


def _prd_lint(t):
    iss = [s for s in _PRD_SECTIONS if not re.search(r"^## %s$" % re.escape(s), t, re.M)]
    reqs = re.findall(r"^- (US-\d+ .+)$", t, re.M)
    iss += ["no AC: " + r[:20] for r in reqs if "Given" not in r or "Then" not in r]
    for line in t.splitlines():
        if re.search(r"\d{2,}", line) and not re.search(r"\[(source: [^\]]+|estimate)\]", line) and not line.startswith(("- US-", "#")):
            iss.append("unsourced number: " + line[:30])
    return iss


_LAYERS = ["subject", "action", "setting", "lighting", "camera", "mood", "style"]


_SHOT_H = {"CU": (0.25, 0.6), "MS": (0.7, 1.4), "WS": (2.5, 12)}


def _framed_h(focal, dist, sensor_h=24.0):
    return sensor_h * dist / focal


def _scene_lint(scene):
    iss = [l for l in _LAYERS if not scene["layers"].get(l)]
    dirs = {s["key_dir"] for s in scene["shots"]}
    if len(dirs) > 1:
        iss.append("light direction changes %s" % sorted(dirs))
    props = {tuple(sorted(s["props"])) for s in scene["shots"]}
    if len(props) > 1:
        iss.append("props change")
    for s in scene["shots"]:
        h = _framed_h(s["lens_mm"], s["distance_m"])
        lo, hi = _SHOT_H[s["size"]]
        if not lo <= h <= hi:
            iss.append("%s: %dmm at %.1fm frames %.2fm, not %s" % (s["id"], s["lens_mm"], s["distance_m"], h, s["size"]))
    return iss


def _pack(cands, window, reply_reserve, budget):
    keep, evicted = [], []
    avail = window - reply_reserve
    by = {k: [c for c in cands if c["kind"] == k] for k in ["static", "decision", "retrieval", "history", "example", "other"]}
    for k in ["static", "decision"]:
        keep += by[k]
    for k, order in [("retrieval", lambda c: -c["rel"]), ("history", lambda c: -c["t"]), ("example", lambda c: c["tok"])]:
        used = 0
        for c in sorted(by[k], key=order):
            if used + c["tok"] <= budget[k]:
                keep.append(c)
                used += c["tok"]
            else:
                evicted.append(c)
    evicted += by["other"]
    while sum(c["tok"] for c in keep) > avail:            # eviction rule: oldest history, then least relevant, then examples
        pool = sorted([c for c in keep if c["kind"] == "history"], key=lambda c: c["t"]) or \
            sorted([c for c in keep if c["kind"] == "retrieval"], key=lambda c: c["rel"]) or [c for c in keep if c["kind"] == "example"]
        keep.remove(pool[0])
        evicted.append(pool[0])
    order = {"static": 0, "retrieval": 1, "example": 2, "history": 3, "decision": 4}
    return sorted(keep, key=lambda c: (order[c["kind"]], -c.get("rel", 0), c.get("t", 0))), evicted


_STAGES = ["orientation", "foundations", "tools", "application", "synthesis"]


def _topo(mods):
    done, order = set(), []
    pending = list(mods)
    while pending:
        nxt = next(m for m in pending if set(m["pre"]) <= done)
        order.append(nxt)
        done.add(nxt["id"])
        pending.remove(nxt)
    return order


def _curr_issues(order):
    iss, seen = [], set()
    for m in order:
        if not set(m["pre"]) <= seen:
            iss.append("%s before its prerequisites" % m["id"])
        seen.add(m["id"])
    st = [_STAGES.index(m["stage"]) for m in order]
    if st != sorted(st):
        iss.append("stage order reversed")
    return iss


def _gpt_issues(instr, knowledge, api, starters, tests):
    iss = []
    if len(instr) > 8000:
        iss.append("instructions over 8000 chars")
    if secrets_in(instr) or any(secrets_in(t) for t in knowledge.values()):
        iss.append("secret in instructions/knowledge")
    if len(knowledge) >= 20 or any(not re.search(r"^# ", t, re.M) for t in knowledge.values()):
        iss.append("knowledge files")
    if any(not s["url"].startswith("https://") for s in api.get("servers", [])):
        iss.append("non-https action")
    if "bearer" not in json.dumps(api.get("components", {}).get("securitySchemes", {})).lower():
        iss.append("no bearer auth")
    if any(not op.get("description") for p in api["paths"].values() for op in p.values()):
        iss.append("operation without description")
    if len(starters) != 4:
        iss.append("starters")
    if len(tests) != 10 or sum(t["adversarial"] for t in tests) < 2:
        iss.append("test plan")
    return iss


def _schema_issues(db):
    iss = []
    for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        cols = db.execute("PRAGMA table_info(%s)" % t).fetchall()
        for c in cols:
            if re.search(r"total|price|amount", c[1]) and re.search(r"FLOAT|REAL|DOUBLE", c[2].upper()):
                iss.append("%s.%s money as %s" % (t, c[1], c[2]))
        names = {c[1] for c in cols}
        if not {"created_at", "updated_at"} <= names:
            iss.append("%s missing timestamps" % t)
        idx_cols = set()
        for ix in db.execute("PRAGMA index_list(%s)" % t).fetchall():
            first = db.execute("PRAGMA index_info(%s)" % ix[1]).fetchall()
            if first:
                idx_cols.add(first[0][2])
        for fk in db.execute("PRAGMA foreign_key_list(%s)" % t).fetchall():
            if fk[3] not in idx_cols:
                iss.append("%s.%s FK without index" % (t, fk[3]))
    return iss


def _mmd_lint(t):
    iss = []
    edges = re.findall(r"^\s*\S+.*?(-->|---)(\|[^|]+\|)?", t, re.M)
    iss += ["unlabelled edge"] * sum(1 for _, lab in edges if not lab)
    nodes = set(re.findall(r"\b([A-Z]\w*)[\[\(]", t))
    if len(nodes) > 12:
        iss.append("over 12 nodes")
    head = t.splitlines()[0].split()
    if len(head) < 2 or head[1] not in ("LR", "TB", "TD"):
        iss.append("no single direction")
    for fill, col in re.findall(r"fill:(#[0-9A-Fa-f]{6}).*?color:(#[0-9A-Fa-f]{3,6})", t):
        col = col if len(col) == 7 else "#" + "".join(c * 2 for c in col[1:])
        if contrast(fill, col) < 4.5:
            iss.append("low contrast role %s" % fill)
    return iss


def _docker_issues(dockerfile, ignore, ci):
    iss = []
    froms = re.findall(r"^FROM (\S+)", dockerfile, re.M)
    if len(froms) < 2:
        iss.append("single stage")
    if not all(re.search(r"slim|alpine|distroless", f) for f in froms):
        iss.append("large base image")
    users = re.findall(r"^USER (\S+)", dockerfile, re.M)
    if not users or users[-1] in ("root", "0"):
        iss.append("runs as root")
    if re.search(r"^(ENV|ARG) .*(SECRET|TOKEN|PASSWORD)", dockerfile, re.M | re.I):
        iss.append("secret baked into image")
    if not {".env", ".git"} <= set(ignore.split()):
        iss.append(".dockerignore misses .env/.git")
    if ci is not None:
        jobs = ci["jobs"]
        chain = [j for j in ["lint", "test", "build", "publish"] if j in jobs]
        if chain != ["lint", "test", "build", "publish"] or any(jobs[b].get("needs") != a for a, b in zip(chain, chain[1:])):
            iss.append("job order")
        if "refs/tags" not in jobs.get("publish", {}).get("if", "") or "environment" not in jobs.get("publish", {}):
            iss.append("publish not gated on tag + environment")
        if ci.get("permissions") != {"contents": "read"}:
            iss.append("token permissions not minimal")
        if secrets_in(yaml_dump(ci)):
            iss.append("literal secret in workflow")
    return iss


def yaml_dump(o):
    import yaml
    return yaml.safe_dump(o)


_LIMITS = {"amazon": 200, "noon": 150, "salla": 120}


_BANNED_CLAIMS = re.compile(r"(يعالج|يشفي|آمن 100|مضمون 100|cures?|100% safe|guaranteed)")


def _listing_issues(lst, product):
    iss = []
    if len(lst["title"]) > _LIMITS[lst["platform"]]:
        iss.append("title over limit")
    if not all(k in lst["title"] for k in [product["category"], product["key_feature"], product["spec"]]):
        iss.append("title formula")
    if len(lst["benefits"]) != 3 or len(lst["faq"]) != 5:
        iss.append("benefits/faq count")
    if lst["specs"] != product["specs"]:
        iss.append("specs differ from product data")
    if _BANNED_CLAIMS.search(json.dumps(lst, ensure_ascii=False)):
        iss.append("unproven health/safety claim")
    return iss


_SOURCES = {"wb-2025": {"title": "World Bank WDI 2025 (fixture copy)", "primary": True,
                        "text": "Egypt population 2024: 116.5 million. Saudi Arabia population 2024: 33.9 million."},
            "blog-x": {"title": "travel blog", "primary": False, "text": "Egypt has about 120 million people."},
            "who-2024": {"title": "WHO fact sheet 2024 (fixture copy)", "primary": True, "text": "Global life expectancy 2021: 71.4 years."}}


def _classify(claim):
    num = float(re.search(r"([\d.]+)", claim["value"]).group(1))
    best = None
    for sid, s in _SOURCES.items():
        if not s["primary"]:
            continue
        m = re.search(re.escape(claim["subject"]) + r"[^:]*: ([\d.]+)", s["text"])
        if m:
            best = (sid, float(m.group(1)), m.group(0))
    if not best:
        return "unverifiable", None, None
    return ("supported" if abs(best[1] - num) / best[1] <= 0.02 else "contradicted"), best[0], best[2]


def _expert(method, data):
    if method == "empirical":
        s = {k: v["uptime"] - 99 + v["speed"] for k, v in data.items()}
    elif method == "theoretical":
        s = {k: 2 * v["arabic_support"] - v["lockin"] for k, v in data.items()}
    elif method == "practical":
        s = {k: -v["cost"] / 10 + v["speed"] for k, v in data.items()}
    else:                                   # contrarian: minimise worst-case regret (downtime hours x lock-in)
        s = {k: -(100 - v["uptime"]) * 87.6 * (0.5 + v["lockin"]) / 50 for k, v in data.items()}
    best = max(s, key=s.get)
    weak = min(s, key=s.get)
    return {"method": method, "scores": s, "choice": best, "weakness": "ignores criteria outside %s; worst option %s" % (method, weak),
            "input_sha": __import__("hashlib").sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:12]}


def _verdict(ops, data, rng, runs=2000):
    w = {"empirical": 0.3, "theoretical": 0.25, "practical": 0.25, "contrarian": 0.2}
    def tally(d):
        tot = {k: 0.0 for k in d}
        for o in ops:
            sc = _expert(o["method"], d)["scores"]
            lo, hi = min(sc.values()), max(sc.values())
            for k in d:
                tot[k] += w[o["method"]] * (sc[k] - lo) / ((hi - lo) or 1)
        return max(tot, key=tot.get), tot
    win, tot = tally(data)
    keep = 0
    for _ in range(runs):                   # red team: perturb every input +-20% and see if the winner survives
        d = {k: {c: v * (1 + rng.uniform(-0.2, 0.2)) if c != "uptime" else min(100, v * (1 + rng.uniform(-0.002, 0.002)))
                 for c, v in o.items()} for k, o in data.items()}
        keep += tally(d)[0] == win
    return win, tot, keep / runs


def _img_metrics(path):
    import numpy as np
    import cv2
    im = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)  # v10.15: imread fails on Arabic paths
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(float)
    sharp = float(cv2.Laplacian(g, cv2.CV_64F).var())
    clip = float(((g >= 250) | (g <= 5)).mean())
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    mask = hsv[..., 1] > 120
    ys, xs = np.nonzero(mask)
    cx, cy = (xs.mean() / g.shape[1], ys.mean() / g.shape[0]) if len(xs) else (0.5, 0.5)
    thirds = min(math.hypot(cx - a, cy - b) for a in (1 / 3, 2 / 3) for b in (1 / 3, 2 / 3))
    dom = im[mask].mean(0)[::-1] if len(xs) else im.reshape(-1, 3).mean(0)[::-1]
    return {"sharpness": sharp, "clipped": clip, "mean_luma": float(g.mean()), "subject_xy": [cx, cy], "thirds_dist": thirds,
            "dominant_rgb": [int(x) for x in dom]}


def _img_score(m):
    return {"sharpness": min(20, m["sharpness"] / 25), "exposure": 20 * max(0, 1 - m["clipped"] * 5) * max(0, 1 - abs(m["mean_luma"] - 118) / 118),
            "composition": 20 * max(0, 1 - m["thirds_dist"] / 0.25), "colour": 20.0 if max(m["dominant_rgb"]) - min(m["dominant_rgb"]) > 60 else 8.0}


def _editorial_chain(grain_temporal=True):
    # light neutral B&W -> highlight bloom (bright pass, blur, screen) -> film grain new every frame -> soft vignette
    flags = "t+u" if grain_temporal else "u"
    return ("format=yuv420p,hue=s=0,curves=all='0/0.04 0.5/0.52 1/0.96',split[a][b];"
            "[b]lutyuv=y='if(gt(val,190),val,16)',gblur=sigma=8[bl];[a][bl]blend=all_mode=screen:all_opacity=0.35,"
            "noise=c0s=14:c0f=%s,vignette=angle=PI/6,format=yuv420p" % flags)


def _grain_corr(path):
    import numpy as np
    from scipy.ndimage import uniform_filter
    f = fx.frames(path, size=(320, 180))[..., 0]
    hp = np.array([x - uniform_filter(x, 5) for x in f])
    cs = [np.corrcoef(hp[i].ravel(), hp[i + 1].ravel())[0, 1] for i in range(len(hp) - 1)]
    return float(np.mean(cs)), float(hp.std())
