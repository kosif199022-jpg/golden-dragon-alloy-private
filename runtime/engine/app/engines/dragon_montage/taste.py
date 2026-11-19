"""Station 4 «يختار الذوق»: brief (+ chosen concept, + look_override.json from mimic) -> look.json.

  pick   --job DIR [--style ID] [--invent] [--seed N]   rank every style of data/taste_index.json by fit, say why
  query  --feeling tense [--platform reel] [--content talking-head] [--energy 0.7] [--top 5]
  filter grade|transition|camera ID [--W --H --fps --seconds]   the executable ffmpeg filter
--invent fuses a new look from the top styles of different sources (the kmx ideate engine is not part of this repo).
"""
from __future__ import annotations

import argparse
import json
import re
import zlib
from pathlib import Path

from . import common as C

STATION = "taste"
FEEL_AR = {"tense": "متوتر", "warm": "دافي", "epic": "ملحمي", "playful": "مرح", "calm": "هادي",
           "inspiring": "ملهم", "sad": "حزين", "funny": "كوميدي"}
FEEL_NEAR = {"tense": ["epic", "sad"], "warm": ["calm", "inspiring"], "epic": ["inspiring", "tense"],
             "playful": ["funny", "inspiring"], "calm": ["warm", "sad"], "inspiring": ["epic", "warm"],
             "sad": ["calm", "warm"], "funny": ["playful"]}
FEEL_ENERGY = {"tense": 0.7, "warm": 0.45, "epic": 0.7, "playful": 0.7, "calm": 0.25, "inspiring": 0.6,
               "sad": 0.3, "funny": 0.75}
SRC_AR = {"catalog": "كتالوج الستايلات (311)", "library500": "مكتبة الـ500 ستايل", "atlas86": "أطلس الـ86",
          "kmx": "المصفوفات اللانهائية (kmx)", "mimic": "محاكاة فيديو مرجعي"}
TOKEN = re.compile(r"[\w\-]+", re.UNICODE)
VOCAB = {"grade": ("grades.json", "grades"), "transition": ("transitions.json", "transitions"),
         "camera": ("camera.json", "cameras"), "caption": ("caption_styles.json", "styles")}


def vocab(kind: str) -> dict:
    file, key = VOCAB[kind]
    return {x["id"]: x for x in C.data(file)[key]}


def resolve(kind: str, ident) -> str | None:
    """id, alias, underscore name or (transitions) bare xfade name -> canonical id, else None."""
    if not ident:
        return None
    v, s = vocab(kind), str(ident).strip()
    if s in v:
        return s
    low = s.lower().replace("_", "-")
    for i, x in v.items():
        names = [i] + list(x.get("aliases") or []) + ([x["xfade"]] if x.get("xfade") else [])
        if s in names or low in [str(n).lower().replace("_", "-") for n in names]:
            return i
    return f"xfade-{low}" if kind == "transition" and f"xfade-{low}" in v else None


def grade_filter(gid: str) -> str:
    return vocab("grade")[resolve("grade", gid) or gid]["ffmpeg"]


def transition_filter(tid: str, offset: float, seconds: float | None = None) -> str | None:
    t = vocab("transition")[resolve("transition", tid) or tid]
    if not t.get("xfade"):
        return None
    sec = float(seconds if seconds is not None else t["seconds"])
    return f"xfade=transition={t['xfade']}:duration={sec:.3f}:offset={max(0.0, offset):.3f}"


def camera_filter(cid: str, W: int, H: int, fps: float, seconds: float, **params) -> str:
    c = vocab("camera")[resolve("camera", cid) or cid]
    p = {**c.get("defaults", {}), **{k: v for k, v in params.items() if k in c.get("defaults", {})}}
    return c["ffmpeg"].format(W=int(W), H=int(H), W2=int(W) * 2, H2=int(H) * 2, fps=fps,
                              frames=max(1, round(seconds * fps)), **p)


# ---------------------------------------------------------------- ranking
def words(text: str) -> set:
    return {w.lower() for w in TOKEN.findall(text or "") if len(w) > 2}


def score(row: dict, feeling: str, energy: float, platform, content, hint: set, avoid: set) -> tuple:
    parts, moods = {}, row["moods"]
    if feeling in moods:
        parts["feeling"] = [3.0, 2.0, 1.2][moods.index(feeling)]
    elif any(n in moods for n in FEEL_NEAR.get(feeling, [])):
        parts["feeling"] = 0.6
    parts["energy"] = round(2.0 * (1 - abs(row["energy"] - energy)), 3)
    if platform:
        parts["platform"] = 1.0 if platform in row["platforms"] else 0.6 if "any" in row["platforms"] else 0.0
    if content and content in row["content_types"]:
        parts["content"] = 2.0 if row["content_types"][0] == content else 1.4
    if feeling in vocab("grade")[row["grade_id"]]["feelings"]:
        parts["grade"] = 0.8                      # the style's own grade already carries the feeling
    bag = set(row.get("keywords") or []) | words(" ".join(map(str, [row.get("name"), row.get("slug"), row.get("family"), row["id"]])))
    if hint & bag:
        parts["hint"] = round(min(3.0, 1.2 * len(hint & bag)), 2)
        parts["hint_words"] = sorted(hint & bag)[:6]
    if avoid & bag:
        parts["avoid"] = -1.5 * len(avoid & bag)
    return round(sum(v for v in parts.values() if isinstance(v, (int, float))), 3), parts


def rank(feeling: str, energy=None, platform=None, content=None, hint: str = "", avoid=None, top=None) -> list:
    e = FEEL_ENERGY.get(feeling, 0.5) if energy is None else float(energy)
    hw, aw = words(hint), words(" ".join(avoid or []))
    out = []
    for r in C.data("taste_index.json")["styles"]:
        s, parts = score(r, feeling, e, platform, content, hw, aw)
        out.append({**r, "score": s, "parts": parts})
    out.sort(key=lambda r: (-r["score"], r["source"], r["id"]))
    return out[:top] if top else out


# ---------------------------------------------------------------- look assembly
def _transitions(ids: list) -> list:
    v, out = vocab("transition"), []
    for i in ["cut"] + list(ids):
        i = resolve("transition", i)
        if i and not any(t["id"] == i for t in out):
            out.append({"id": i, **({"seconds": v[i]["seconds"]} if v[i].get("xfade") else {})})
    return out[:4]


def _camera(ids: list) -> list:
    v, out = vocab("camera"), []
    for i in ids:
        i = resolve("camera", i)
        if i and not any(c["id"] == i for c in out):
            out.append({"id": i, **v[i].get("defaults", {})})
    return out[:3]


def _bpm(e: float) -> list:
    return [60, 85] if e < 0.35 else [85, 110] if e < 0.6 else [105, 128] if e < 0.8 else [120, 150]


def _captions(style: str, brief: dict) -> dict:
    if brief.get("content_type") in ("talking-head", "interview") and style == "none":
        style = "karaoke"
    cs = vocab("caption")[style]
    return {"style": style, "font": (cs.get("ass") or {}).get("Fontname") or "Cairo",
            "position": cs.get("position") or "lower", "fallback_fonts": C.data("caption_styles.json")["font_fallback"]}


def _why(row: dict, brief: dict, energy: float, concept, alts: list, extra: str = "") -> str:
    f, g = brief.get("feeling"), vocab("grade")[row["grade_id"]]
    bits = [f"اخترت «{row.get('name_ar') or row.get('name')}» ({row['id']}) من {SRC_AR.get(row['source'], row['source'])}",
            f"لأن إحساسه {FEEL_AR.get(f, f)} زي ما البريف عايز بالظبط" if f in row["moods"] else
            f"إحساسه ({'، '.join(FEEL_AR.get(m, m) for m in row['moods'])}) قريب من {FEEL_AR.get(f, f)}",
            f"وطاقته {row['energy']:.2f} قريبة من المطلوب {energy:.2f}"]
    if brief.get("content_type") in row["content_types"]:
        bits.append(f"وبيمشي مع نوع المحتوى ({brief['content_type']})")
    hw = row.get("parts", {}).get("hint_words")
    if hw and concept:
        bits.append(f"وفيه كلمات من فكرة المفهوم {concept.get('id')}: {', '.join(hw)}")
    s = "، ".join(bits) + "." + (f" اللون: «{g['name_ar']}» ({g['id']}) — {row.get('grade_why', '')}. "
                                 f"الانتقالات: {' / '.join(row['transition_ids'])}. الكاميرا: {' / '.join(row['camera_ids'])}. "
                                 f"الترجمة: {row['caption_style']}.")
    if alts:
        s += " البدايل اللي كانت قريبة: " + "، ".join(f"{a['id']} ({a['score']:.1f})" for a in alts[:3]) + "."
    return s + (" " + extra if extra else "")


SAME_COLOURS = re.compile(r"نفس (?:ال)?(?:الوان|ألوان|لون|الالوان|الألوان|جريد|جريدينج)|same colou?rs?|same grade|match the grade", re.I)


def _apply_override(job: Path, look: dict, brief: dict | None = None) -> dict:
    """mimic's look_override.json (a measured reference) wins for transitions / camera. v1.3: its grade only when the
    owner asked for the reference's colours («نفس الألوان»): --reference copies pace, not his footage's colour."""
    try:
        ov = json.loads((job / "look_override.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return look
    applied = []
    gid = resolve("grade", (ov.get("grade") or {}).get("id"))
    task = " ".join(str((brief or {}).get(k) or "") for k in ("task", "topic"))
    if gid and not SAME_COLOURS.search(task):
        look["why"] += (f" لون المرجع ({gid}) ماتطبقش: لون الفوتيج بتاعك فضل زي ما هو"
                        f" (قول «نفس الألوان» لو عايز لون المرجع).")
        look["reference_grade"] = {"id": gid, "applied": False}
        gid = None
    if gid:
        look["grade"] = {**look["grade"], **{k: v for k, v in ov["grade"].items() if k != "id"}, "id": gid,
                         "engine": vocab("grade")[gid]["engine"]}
        applied.append("grade")
    for key, kind in (("transitions", "transition"), ("camera", "camera")):
        items = []
        for t in ov.get(key) or []:
            tid = resolve(kind, t.get("id") if isinstance(t, dict) else t)
            if tid:
                items.append({**(t if isinstance(t, dict) else {}), "id": tid})
        if items:
            look[key] = items
            applied.append(key)
    if applied:
        look["override"] = {"from": "look_override.json", "source": ov.get("style_source", "mimic"), "keys": applied}
        look["why"] += f" وبعدين طبّقت قياسات الفيديو المرجعي (look_override.json) على: {', '.join(applied)}."
    return look


def invent(ranked: list) -> tuple:
    """Fuse a new look from the top style of each source (local fusion; returns (pseudo-row, record))."""
    parents, seen = [], set()
    for r in ranked:
        if r["source"] not in seen:
            parents.append(r)
            seen.add(r["source"])
        if len(parents) == 3:
            break
    rec = {"idea": None, "parents": [p["id"] for p in parents], "fallback": True,
           "note": "kmx.py ideate unavailable or no parents matched the atlas; fused the top styles per source"}
    lead = max(parents, key=lambda p: p["score"])
    moods, pool_t, pool_c = [], [], []
    for p in parents:
        moods += [m for m in p["moods"] if m not in moods]
    for p in sorted(parents, key=lambda p: -p["score"]):
        pool_t += [t for t in p["transition_ids"] if t not in pool_t]
        pool_c += [c for c in p["camera_ids"] if c not in pool_c]
    names = " × ".join(p.get("name") or p["id"] for p in parents)
    row = {"id": "KMX-local-%08x" % zlib.crc32("|".join(p["id"] for p in parents).encode()), "source": "kmx",
           "name": names, "name_ar": "دمج جديد: " + names, "moods": moods[:3],
           "energy": round(sum(p["energy"] for p in parents) / len(parents), 2),
           "content_types": lead["content_types"], "grade_id": lead["grade_id"],
           "grade_why": f"لون الأب الأقوى {lead['id']} ({lead.get('grade_why', '')})",
           "transition_ids": pool_t[:4], "camera_ids": pool_c[:3], "caption_style": lead["caption_style"],
           "score": round(sum(p["score"] for p in parents) / len(parents), 3), "parts": lead.get("parts", {})}
    return row, rec


# v1.3: words the owner (or a session) really types for --style. They map to a mood rule, not one fixed id.
STYLE_ALIASES = {"calm": "calm", "هادي": "calm", "هادئ": "calm", "هادى": "calm", "هدوء": "calm", "soft": "calm",
                 "clean": "minimal", "nil": "minimal", "minimal": "minimal", "بسيط": "minimal", "نضيف": "minimal",
                 "editorial": "editorial", "cinematic": "calm", "سينمائي": "calm"}
LOUD_LOOK = re.compile(r"anime|cyber|pixel|glitch|whiteboard|neon|hype|vhs|8-?bit|comic|cartoon|impasto|painterly|"
                       r"psychedelic|sticker|chart|graffiti|meme|thermal|infrared|x-?ray", re.I)
CALM_TRANSITIONS = {"cut", "match-cut", "xfade-fade", "xfade-dissolve", "xfade-fadeblack", "xfade-fadewhite"}
FOOTAGE_FAMILIES = {"cinematic-genres", "photos", "optics-light", "Light & Imaging", "motion-time", "kinetic-type"}


def _text_of(r: dict) -> str:
    return " ".join(str(x) for x in (r.get("id"), r.get("name"), r.get("slug"), r.get("family"), r.get("source_style_id"),
                                     " ".join(r.get("keywords") or [])))


def is_loud(r: dict) -> bool:
    """A look the skill warns against for the owner's footage films (anime-hype, cyberpunk, pixelize, whiteboard …)."""
    return bool(LOUD_LOOK.search(_text_of(r))) or any(t in ("xfade-pixelize", "xfade-hlslice") for t in r["transition_ids"])


def alias_rows(alias: str, ranked: list) -> list:
    """Rows for a mood alias, best first. calm: low energy, only cuts/dissolves/fades, no loud look; minimal/editorial:
    rows whose name says so, then the calm rows."""
    kind = STYLE_ALIASES.get(str(alias).strip().lower(), STYLE_ALIASES.get(str(alias).strip()))
    if not kind:
        return []
    quiet = [r for r in ranked if not is_loud(r) and set(r["transition_ids"]) <= CALM_TRANSITIONS | {"xfade-wipeleft", "xfade-coverup"}]
    calm = sorted((r for r in quiet if float(r.get("energy") or 0.5) <= 0.45),
                  key=lambda r: (r.get("family") not in FOOTAGE_FAMILIES, float(r.get("energy") or 0.5), -float(r.get("score") or 0)))
    if kind == "calm":
        return calm or quiet
    word = re.compile(r"editorial" if kind == "editorial" else r"minimal|clean|swiss|editorial", re.I)
    named = [r for r in quiet if word.search(_text_of(r))]
    return named + [r for r in calm if r not in named]


def _quiet(row: dict) -> dict:
    """The same row with only calm transitions (cut first) for a calm alias."""
    keep = [t for t in row["transition_ids"] if t in CALM_TRANSITIONS] or ["cut"]
    return {**row, "transition_ids": keep}


def pick(job, style: str | None = None, do_invent: bool = False, seed: int | None = None) -> dict:
    job = Path(job)
    brief = C.read(job, "brief")
    concept = None
    if (job / "concepts.json").exists():
        try:
            cj = C.read(job, "concepts")
            chosen = (cj.get("decision") or {}).get("chosen")
            concept = next((c for c in cj["concepts"] if c.get("id") == chosen), None) or (cj["concepts"] or [None])[0]
        except (C.ContractError, KeyError, ValueError):
            concept = None
    feeling = brief.get("feeling") or "inspiring"
    e = brief.get("energy")
    e = FEEL_ENERGY.get(brief.get("feeling"), 0.5) if e is None else float(e)
    e += {"on-beat": 0.1, "slow-burn": -0.15, "speech-led": -0.03}.get((concept or {}).get("rhythm"), 0.0)
    energy = round(max(0.0, min(1.0, e)), 2)
    hint = " ".join(filter(None, [(concept or {}).get("style_hint"), (concept or {}).get("title"), brief.get("one_truth")]))
    ranked = rank(feeling, energy, brief.get("platform"), brief.get("content_type"), hint, brief.get("avoid"))
    extra, kmx_rec = "", None
    if style:
        row = next((r for r in ranked if style in (r["id"], r.get("slug"), r.get("source_style_id"))), None)
        if row is None and alias_rows(style, ranked):
            row = _quiet(alias_rows(style, ranked)[0])
            extra = f"(--style {style} = مزاج «{STYLE_ALIASES.get(style.lower(), STYLE_ALIASES.get(style))}»: أهدى ستايل مناسب، قطع وذوبان بس.)"
        elif row is None:
            raise SystemExit(f"taste: style {style!r} not in taste_index (catalog/library500/atlas86 ids or slugs) and not "
                             f"an alias ({', '.join(sorted(STYLE_ALIASES))}); list calm ids with `taste list --calm`")
        else:
            extra = "(الستايل ده انت اللي حددته بـ --style.)"
    elif do_invent:
        row, kmx_rec = invent(ranked)
        extra = "kmx مش متاح فدمجت أحسن ستايل من كل مصدر."
    else:
        asked = " ".join(str(brief.get(k) or "") for k in ("task", "topic"))
        loud_ok = bool(LOUD_LOOK.search(asked)) or any(w in asked for w in ("انمي", "أنمي", "سايبر", "بيكسل", "جليتش"))
        row = ranked[0] if loud_ok else next((r for r in ranked if not is_loud(r)), ranked[0])
    alts = [r for r in ranked if r["id"] != row["id"]][:5]
    g = vocab("grade")[row["grade_id"]]
    look = C.new("look", style_id=row["id"], style_source=row["source"], style_name=row.get("name"),
                 style_ref=row.get("ref"), grade={"id": g["id"], "engine": g["engine"], "lut": None},
                 transitions=_transitions(row["transition_ids"]), camera=_camera(row["camera_ids"]),
                 captions=_captions(row["caption_style"], brief),
                 music={"mood": feeling, "bpm_range": _bpm(energy)},
                 why=_why(row, brief, energy, concept, alts, extra),
                 fit={"score": row.get("score"), "parts": row.get("parts"), "target_energy": energy,
                      "feeling": feeling, "concept": (concept or {}).get("id")},
                 alternatives=[{"id": a["id"], "source": a["source"], "name": a.get("name"), "score": a["score"]} for a in alts],
                 matrix_atoms=sorted({a for t in row["transition_ids"] for a in vocab("transition")[t].get("matrix_atoms", [])}
                                     | {a for c in row["camera_ids"] for a in vocab("camera")[c].get("matrix_atoms", [])}))
    if kmx_rec:
        look["kmx"] = kmx_rec
    look = _apply_override(job, look, brief)
    C.write(job, "look", look)
    return look


def main(argv=None) -> int:
    C.utf8_stdio()
    ap = argparse.ArgumentParser(prog="dragon_montage taste", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    p.add_argument("--job", required=True)
    p.add_argument("--style")
    p.add_argument("--invent", action="store_true")
    p.add_argument("--seed", type=int)
    q = sub.add_parser("query")
    q.add_argument("--feeling", required=True, choices=list(FEEL_AR))
    q.add_argument("--platform")
    q.add_argument("--content")
    q.add_argument("--energy", type=float)
    q.add_argument("--hint", default="")
    q.add_argument("--top", type=int, default=5)
    q.add_argument("--json", action="store_true")
    ls = sub.add_parser("list", help="ids for a mood alias: --calm, --alias minimal|editorial|هادي")
    ls.add_argument("--calm", action="store_true")
    ls.add_argument("--alias")
    ls.add_argument("--top", type=int, default=10)
    f = sub.add_parser("filter")
    f.add_argument("kind", choices=["grade", "transition", "camera"])
    f.add_argument("id")
    f.add_argument("--W", type=int, default=1080)
    f.add_argument("--H", type=int, default=1920)
    f.add_argument("--fps", type=float, default=30)
    f.add_argument("--seconds", type=float, default=2.0)
    a = ap.parse_args(argv)
    if a.cmd == "pick":
        look = pick(a.job, a.style, a.invent, a.seed)
        print(json.dumps({k: look[k] for k in ("style_id", "style_source", "grade", "transitions", "camera", "captions")},
                         ensure_ascii=False))
        print(look["why"])
    elif a.cmd == "query":
        rows = rank(a.feeling, a.energy, a.platform, a.content, a.hint, top=a.top)
        if a.json:
            print(json.dumps(rows, ensure_ascii=False, indent=1))
        for r in [] if a.json else rows:
            print(f"{r['score']:5.2f}  {r['id']:28} {r['source']:10} {str(r.get('name'))[:34]:34} moods={','.join(r['moods'])} "
                  f"e={r['energy']} grade={r['grade_id']} tr={','.join(r['transition_ids'])} cam={','.join(r['camera_ids'])}")
    elif a.cmd == "list":
        alias = a.alias or ("calm" if a.calm else None)
        if not alias:
            raise SystemExit("taste list: pass --calm or --alias NAME (" + ", ".join(sorted(STYLE_ALIASES)) + ")")
        rows = alias_rows(alias, rank("calm", 0.25, "reel", "montage", ""))
        if not rows:
            raise SystemExit(f"taste list: {alias!r} is not an alias")
        for r in rows[:a.top]:
            print(f"{r['id']:28} e={r['energy']} {str(r.get('family'))[:18]:18} {str(r.get('name'))[:40]}  "
                  f"tr={','.join(t for t in r['transition_ids'] if t in CALM_TRANSITIONS) or 'cut'}")
    elif a.kind == "grade":
        print(grade_filter(a.id))
    elif a.kind == "transition":
        print(transition_filter(a.id, max(0.0, a.seconds - 0.5)) or "cut")
    else:
        print(camera_filter(a.id, a.W, a.H, a.fps, a.seconds))
    return 0
