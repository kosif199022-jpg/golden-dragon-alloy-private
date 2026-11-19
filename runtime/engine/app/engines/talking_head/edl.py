"""The EDL (edit decision list): house-style validation and the fully resolved render plan."""
import json, os, re
from pathlib import Path

from .project import info, load

STYLE = json.loads((Path(__file__).with_name("data") / "style.json").read_text(encoding="utf-8"))
JOINED = re.compile(STYLE["joined_script"])
STILL = (".jpg", ".jpeg", ".png")


def _abs(P, rel):
    return rel if os.path.isabs(rel) else os.path.join(P, rel)


def _clips(I):
    return list(I.get("clips") or []) + ([I["bgclip"]] if I.get("bgclip") else [])


# ------------------------------------------------------------------------------------------------ validate
def validate(edl_path):
    """(errors, warnings, summary). Errors stop the render; warnings are house-style breaks to fix or accept."""
    edl = load(edl_path)
    P = edl.get("project_dir") or os.path.dirname(os.path.abspath(edl_path))
    W, H = edl.get("W", 1080), edl.get("H", 1920)
    R = STYLE["rules"]
    accent = edl.get("accent", STYLE["colors"]["accent"]).upper()
    palette = {accent, *STYLE["palette"]}
    err, warn, dur = [], [], None
    cuts_p = os.path.join(P, (edl.get("presenter") or {}).get("cuts", "analysis/cuts.json"))
    if os.path.exists(cuts_p):
        dur = sum(c["src_t1"] - c["src_t0"] for c in load(cuts_p))
    else:
        err.append("cut list not found: " + cuts_p)
    exists = lambda rel: os.path.exists(_abs(P, rel))
    ins = sorted(edl.get("inserts", []), key=lambda i: i["t0"])
    ids = set()
    for k, I in enumerate(ins):
        tag = "insert %s" % I.get("id")
        if I.get("id") in ids:
            err.append(tag + ": duplicate id")
        ids.add(I.get("id"))
        if I.get("kind") not in STYLE["kinds"]:
            err.append(tag + ": unknown kind %s" % I.get("kind"))
            continue
        err += [tag + ': needs "%s"' % r for r in STYLE["kinds"][I["kind"]] if not I.get(r)]
        if I["t1"] <= I["t0"]:
            err.append(tag + ": t1 must be after t0")
        if I["t1"] - I["t0"] < R["short_insert"]:
            warn.append(tag + ": only %.2f s - inserts under ~0.6 s read as a glitch" % (I["t1"] - I["t0"]))
        if dur and I["t1"] > dur + 0.02:
            err.append(tag + ": ends after the program (%.2f s)" % dur)
        if k and I["t0"] < ins[k - 1]["t1"] - 0.02:
            err.append(tag + ": overlaps %s" % ins[k - 1]["id"])
        if I.get("layout", "full") not in ("full", "split"):
            err.append(tag + ": layout must be full or split")
        if I.get("trans", "whip") not in STYLE["transitions"]:
            err.append(tag + ": unknown transition %s" % I.get("trans"))
        if I["kind"] == "vsplit" and len(I.get("clips") or []) < 2:
            err.append(tag + ": vsplit needs two clips")
        for c in _clips(I):
            if not c.get("src") or not exists(c["src"]):
                err.append(tag + ": clip missing %s" % c.get("src"))
            err += [tag + ": %s missing %s" % (mk, c[mk]) for mk in ("cutout_matte", "color_figures_matte") if c.get(mk) and not exists(c[mk])]
            if c.get("src", "").lower().endswith(STILL):
                warn.append(tag + ": still image %s - prefer moving footage (a photo needs a push or parallax at least)" % c["src"])
        keys = [s[0] for s in I.get("slots", [])] + (list(I.get("logos", [])) if I["kind"] == "converge" else []) + \
            [c.get("logo") for c in I.get("cards", []) if c.get("logo")]
        err += [tag + ': logo key "%s" not in "logos"' % key for key in keys if key not in (edl.get("logos") or {})]
    prev = 0.0
    for I in ins:
        if I["t0"] - prev > R["alone"]:
            warn.append("presenter alone %.1f-%.1f s (%.1f s) - the style wants a visual change every ~2-4 s" % (prev, I["t0"], I["t0"] - prev))
        prev = I["t1"]
    if dur and dur - prev > R["alone"]:
        warn.append("presenter alone at the end %.1f-%.1f s" % (prev, dur))

    texts = edl.get("text", [])
    fonts_ok = set(STYLE["fonts"]) | set(edl.get("fonts") or {})
    for T in texts:
        tag = 'text "%s" @%.2f' % (T.get("text", "")[:24], T.get("t0", -1))
        if T.get("font") not in fonts_ok:
            err.append(tag + ': font must be %s (or a key added under "fonts")' % ", ".join(sorted(fonts_ok)))
            continue
        if JOINED.search(T.get("text", "")) and T.get("anim") == "build":
            warn.append(tag + ': Arabic text cannot build letter by letter (the joins break) - rendered as "words"')
        if T.get("anim", "pop") not in STYLE["anims"]:
            err.append(tag + ": unknown anim %s" % T.get("anim"))
        err += [tag + ": needs %s" % r for r in ("text", "t0", "t1", "size") if r not in T]
        if "y" not in T and not T.get("behind"):
            err.append(tag + ": needs y")
        if T.get("t1", 0) <= T.get("t0", 0):
            err.append(tag + ": t1 must be after t0")
        lines = T.get("text", "").split("\n")
        if len([ln for ln in lines if ln.strip()]) > R["max_lines"]:
            warn.append(tag + ": more than two lines - split it into separate text items")
        longest = max(lines, key=len)
        caps = T["font"] != "anton" and longest.isupper()
        est = STYLE["char_w"].get(T["font"], STYLE["char_w"]["serif"]) * (STYLE["caps_w"] if caps else 1) * T.get("size", 0) * len(longest)
        if est > R["max_w"] * W:
            warn.append(tag + ": ~%d px wide (> %d) - %s" % (est, R["max_w"] * W, "the renderer will shrink it to fit" if T.get("fit", True)
                                                             else '"fit": false keeps it - check it is inside the frame'))
        if T.get("y", 0) >= R["bottom_zone"] * H:
            warn.append(tag + ": text in the bottom fifth - the house style keeps all text between y 700 and 1350")
        if T.get("color", "#FFFFFF").upper() not in palette:
            warn.append(tag + ": colour %s is off-palette (accent, white)" % T.get("color").upper())
        if T["font"] == "anton" and T.get("text", "") != T.get("text", "").upper():
            warn.append(tag + ": big Anton words are set in capitals")
    subs = sorted([T for T in texts if T.get("anim") == "words"], key=lambda T: T["t0"])
    for a, b in zip(subs, subs[1:]):
        if a["t1"] > b["t0"] + 0.01 and abs(a.get("y", 0) - b.get("y", 0)) < 120:
            warn.append('subtitles overlap: "%s" and "%s" (only one line at a time)' % (a["text"][:20], b["text"][:20]))
    summary = "%d inserts, %d text items, program %.2f s: %d error(s), %d warning(s)" % (len(ins), len(texts), dur or 0, len(err), len(warn))
    return err, warn, summary


# ------------------------------------------------------------------------------------------------ plan
def build_plan(edl_path):
    """Everything the renderer needs, computed once: media sizes, presenter pieces (pauses removed, framing per piece),
    punch-in keys around inserts, insert timing (adjacency, transition entries, split blocks), text timing rules."""
    edl = load(edl_path)
    P = edl.get("project_dir") or os.path.dirname(os.path.abspath(edl_path))
    cfg = load(os.path.join(P, "project.json")) if os.path.exists(os.path.join(P, "project.json")) else {}
    W, H = edl.get("W", 1080), edl.get("H", 1920)
    fps = float(edl.get("fps") or cfg.get("fps") or 25)
    col = {k: edl.get(k, v) for k, v in STYLE["colors"].items()}

    pr = dict(cuts="analysis/cuts.json", faces=cfg.get("faces", "analysis/faces.jsonl"),
              matte_body=cfg.get("matte_body", "matte/presenter_body.mov"), matte_head=cfg.get("matte_head", "matte/presenter_head.mov"),
              src=cfg.get("presenter"))
    pr.update({k: v for k, v in (edl.get("presenter") or {}).items()})
    if not pr.get("src") or not os.path.exists(_abs(P, pr["src"])):
        raise FileNotFoundError("presenter video not found: %s" % pr.get("src"))
    psrc = _abs(P, pr["src"])
    pm = info(psrc)
    sw, sh = pm["w"], pm["h"]
    cuts = load(_abs(P, pr["cuts"]))
    if cuts and "src_f0" in cuts[0] and "src_t0" not in cuts[0]:            # frame-based cut lists
        cuts = [dict(src_t0=c["src_f0"] / fps, src_t1=c["src_f1"] / fps, prog_t0=c["prog_f0"] / fps) for c in cuts]
    dur = round(sum(c["src_t1"] - c["src_t0"] for c in cuts), 4)

    fpath = _abs(P, pr["faces"])
    if os.path.exists(fpath):
        fl = [json.loads(l) for l in open(fpath, encoding="utf-8") if l.strip()]
        xs, ys = sorted(f["x"] for f in fl if "x" in f), sorted(f["y"] for f in fl if "y" in f)
        GX, GY = xs[len(xs) // 2] * sw, ys[len(ys) // 2] * sh
    else:
        GX, GY = sw / 2, sh * 0.35
    fill, fill_half = max(W / sw, H / sh), max(W / sw, (H / 2) / sh)
    fr = json.loads(json.dumps(STYLE["framing"]))
    for k, v in (pr.get("framing") or {}).items():
        fr.setdefault(k, {}).update(v)
    zoom = edl.get("zoom") or [[c["prog_t0"], c["prog_t0"] + c["src_t1"] - c["src_t0"], "wide" if i % 2 == 0 else "tight"]
                               for i, c in enumerate(cuts)]

    def zoom_at(t):
        return next((z for a, b, z in zoom if a - 1e-6 <= t < b - 1e-6), "wide")

    def pieces(w, h, fixed=None):
        out = []
        for c in cuts:
            p0, p1 = c["prog_t0"], c["prog_t0"] + c["src_t1"] - c["src_t0"]
            bounds = {round(p0 * fps), round(p1 * fps)}
            if not fixed:
                bounds |= {round(a * fps) for a, b, z in zoom if p0 + 1e-3 < a < p1 - 1e-3}
            bounds = sorted(bounds)
            for a, b in zip(bounds, bounds[1:]):
                a, b = a / fps, b / fps
                f = fixed or fr[zoom_at(a + 0.5 / fps)]
                s = (fill_half if fixed else fill) * f["scale"]
                y0 = f["face_y"] * h
                out.append(dict(t0=a, t1=b, off=c["src_t0"] - c["prog_t0"], s0=s, s1=s * 1.03, y0=y0,
                                ax=min(max(GX, w / 2 / s), sw - w / 2 / s), ay=min(max(GY, y0 / s), sh - (h - y0) / s)))
        return out

    mattes = {}
    for k in ("matte_body", "matte_head"):
        mp = _abs(P, pr[k])
        if os.path.exists(mp):
            mi = info(mp)
            mattes[k] = dict(src=mp, w=mi["w"], h=mi["h"], fps=mi["fps"] or fps, div=sw / float(mi["w"]))

    inserts = sorted(edl.get("inserts", []), key=lambda i: i["t0"])
    for I in inserts:
        if I["kind"] not in STYLE["kinds"]:
            raise ValueError("insert %s: unknown kind %s" % (I["id"], I["kind"]))
        I.setdefault("layout", "full")
        I.setdefault("trans", "whip")
        I.setdefault("flash", None)
        for c in _clips(I):
            src = _abs(P, c["src"])
            if not os.path.exists(src):
                raise FileNotFoundError("insert %s: clip not found: %s" % (I["id"], c["src"]))
            m = info(src)
            c.update(abs=src, w=m["w"], h=m["h"], srcdur=m["dur"], fps=m["fps"] or fps, still=src.lower().endswith(STILL))
            for mk in ("cutout_matte", "color_figures_matte"):
                if c.get(mk):
                    mp = _abs(P, c[mk])
                    if not os.path.exists(mp):
                        raise FileNotFoundError("insert %s: matte not found: %s" % (I["id"], c[mk]))
                    mi = info(mp)
                    c.update({mk + "_abs": mp, mk + "_w": mi["w"], mk + "_h": mi["h"], mk + "_fps": mi["fps"] or fps})
    logos = {}
    for k, rel in (edl.get("logos") or {}).items():
        if os.path.exists(_abs(P, rel)):
            li = info(_abs(P, rel))
            logos[k] = dict(src=_abs(P, rel), w=li["w"], h=li["h"])

    # insert timing: in/out points, adjacency, split blocks, transition entries, presenter punch-in keys
    n = len(inserts)
    for i, I in enumerate(inserts):
        I["vis"] = round((I["t1"] - I["t0"]) * fps) / fps
        I["dur"] = I["vis"] + 0.5
        prevI, nextI = (inserts[i - 1] if i else None), (inserts[i + 1] if i < n - 1 else None)
        I["prevAdj"] = bool(prevI and abs(prevI["t1"] - I["t0"]) < 0.02)
        I["nextAdj"] = bool(nextI and abs(nextI["t0"] - I["t1"]) < 0.02)
        I["in"], I["out"] = I["t0"], I["t1"]
        if I["layout"] == "split":
            I["groupStart"] = not (I["prevAdj"] and prevI["layout"] == "split")
            I["out"] = I["t1"] + (0.45 if I["nextAdj"] else 0)
            if not I["groupStart"] and I.get("flash") == "invert":
                I["flash"] = None
    split_blocks = []
    for i, I in enumerate(inserts):
        if I["layout"] == "split" and I["groupStart"]:
            ge, gi = I["t1"], i + 1
            while gi < n and inserts[gi]["layout"] == "split" and abs(inserts[gi]["t0"] - ge) < 0.02:
                ge, gi = inserts[gi]["t1"], gi + 1
            geAdj = gi < n and abs(inserts[gi]["t0"] - ge) < 0.02
            split_blocks.append(dict(t0=I["t0"], t1=ge + (0.45 if geAdj else 0), divider=[I["t0"] + 0.32, ge]))
            if I["prevAdj"] and i:
                inserts[i - 1]["out"] = max(inserts[i - 1]["out"], I["t0"] + 0.4)
    for i, I in enumerate(inserts):             # a split after a split: the previous one stays a moment underneath
        if I["layout"] == "split" and not I["groupStart"] and i:
            inserts[i - 1]["out"] = max(inserts[i - 1]["out"], I["t0"] + 0.35)
    full = [I for I in inserts if I["layout"] != "split"]
    base_keys = []
    for q, I in enumerate(full):
        I["entry"] = entry = STYLE["transitions"].get(I["trans"], 0.0)
        prev = full[q - 1] if q else None
        adjacent = bool(prev and abs(prev["out"] - I["in"]) < 0.02)
        if entry > 0 and adjacent:
            prev["out"] = I["in"] + entry + 0.02
        if not adjacent:
            base_keys += [(I["in"] - 0.18, 100.0), (I["in"], 122.0)]
        nxt = full[q + 1] if q < len(full) - 1 else None
        if (not nxt or nxt["in"] - I["out"] > 0.3) and not I.get("norelease"):
            base_keys += [(I["out"], 116.0), (I["out"] + 0.22, 100.0)]
    base_keys.sort()

    # text rules
    texts = [dict(t) for t in edl.get("text", [])]
    pw_path = os.path.join(P, "analysis", "program_words.json")
    pwords = load(pw_path) if os.path.exists(pw_path) else []
    da = STYLE["default_anim"]
    for T in texts:
        T.setdefault("color", "#FFFFFF")
        T.setdefault("anim", da.get(T["font"], da["*"]))
        if JOINED.search(T.get("text", "")):            # Arabic letters stay joined: reveal word by word, no tracking
            T["_rtl"] = True
            T.setdefault("tracking", 0)
            if T["anim"] == "build":
                T["anim"] = "words"
        T.setdefault("x", W / 2)
        if T["anim"] == "words" and not T.get("wt"):
            nw = len(T["text"].split())
            ws = [w["s"] for w in pwords if T["t0"] - 0.05 <= w["s"] < T["t1"] - 0.05]
            T["wt"] = [max(T["t0"], round(x, 3)) for x in ws] if len(ws) == nw else \
                [round(T["t0"] + (T["t1"] - 0.12 - T["t0"]) * i / max(nw, 1), 3) for i in range(nw)]
        if T.get("behind") and "y" not in T:
            T["y"] = round(fr[zoom_at(T["t0"] + 0.01)]["face_y"] * H - 0.09 * H)
        T["text"] = T["text"].replace("\r\n", "\n").replace("\r", "\n")
        T.setdefault("max_w", round(STYLE["rules"]["max_w"] * W))
    iv = sorted((i["t0"], i["t1"]) for i in inserts)

    def block_end(t):
        hit = next((b for a, b in iv if a - 1e-3 <= t < b), None)
        return hit if hit is not None else min([a for a, b in iv if a > t] or [dur])
    big = [T for T in texts if T["font"] == "anton"]
    for T in big:                                   # big words hold to the end of their shot
        if not T.get("keep_t1"):
            be = block_end(T["t0"] + 0.01)
            nxt = [U["t0"] for U in big if U is not T and T["t0"] < U["t0"] < be and abs(U["y"] - T["y"]) < 160 and abs(U["x"] - T["x"]) < 600]
            T["t1"] = round(max(T["t1"], min([be] + nxt)), 3)
    bottom = sorted([T for T in texts if T["y"] >= STYLE["rules"]["bottom_zone"] * H], key=lambda T: T["t0"])
    for a_, b_ in zip(bottom, bottom[1:]):           # one line at the bottom at a time
        a_["t1"] = min(a_["t1"], b_["t0"])
    for T in texts:
        T["glow"] = T.get("glow", T["color"].upper() == col["accent"].upper() and T["font"] == "anton")
    texts = [T for T in texts if T["t1"] > T["t0"] + 0.01]

    look = dict(STYLE["look"], **(edl.get("look") or {}))
    if look.get("halftone"):
        hp = _abs(P, look["halftone"])
        look["halftone"] = hp if os.path.exists(hp) else None
    audio = _abs(P, edl.get("audio") or cfg.get("audio") or "audio/program_master.wav")
    if not os.path.exists(audio):
        raise FileNotFoundError("program audio not found: %s" % audio)
    return dict(W=W, H=H, fps=fps, dur=dur, name=edl.get("name") or cfg.get("name") or "Reel", P=P,
                presenter=dict(src=psrc, w=sw, h=sh, fps=pm["fps"] or fps), mattes=mattes, audio=audio, logos=logos,
                pieces=pieces(W, H), pieces_half=pieces(W, H // 2, fixed=fr["half"]), inserts=inserts, split_blocks=split_blocks,
                base_keys=base_keys, text=texts, look=look, accent=col["accent"], bw_black=col["bw_black"], bw_white=col["bw_white"],
                ui_bg=col["ui_bg"], fonts=dict(STYLE["fonts"], **(edl.get("fonts") or {})))
