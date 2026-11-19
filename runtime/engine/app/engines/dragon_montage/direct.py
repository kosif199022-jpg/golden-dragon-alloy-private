"""Station 5 «يكتب المونتاج» — the director: analysis + brief + concepts + look -> edl.json.

Deterministic:
  a) candidates: speech clips -> phrases cut on word gaps (fillers and pauses > 0.4 s break a phrase);
     other clips -> one window per shot, length from the feeling/energy pace (or reference_rhythm.json).
  b) every candidate is scored for each arc role + quality + faces + novelty.
  c) the chosen concept's arc is filled to brief.target_seconds with per-role budgets.
  d) with music beats, b-roll cuts snap to the nearest downbeat/beat (±0.15 s, else re-fit); speech cuts only
     move inside word gaps.
  e) transitions, camera and captions come from look.json; every event has a concrete en | ar reason.
apply_review: review.json fixes -> the next edl.json (old kept as edl.rN.json), then a re-fill toward the target.
"""
from __future__ import annotations

import argparse
import bisect
import copy
import json
import re
from pathlib import Path

from . import common as C
from . import edl as E
from .think import hook_roles

r3 = E.r3
STATION = "direct"
FILLERS = {"امم", "اممم", "ام", "مم", "اه", "آه", "ااه", "آآ", "اا", "ا", "يعني", "إيه", "ايه", "بقى", "طيب",
           "um", "uh", "umm", "uhm", "er", "erm", "ah", "eh", "like", "hmm"}
EMPHASIS = {"جدا", "جداً", "اوي", "أوي", "خالص", "مستحيل", "ابدا", "أبدا", "أبداً", "لازم", "اهم", "أهم", "السر",
            "الحقيقة", "اخطر", "أخطر", "اول", "أول", "افضل", "أفضل", "never", "always", "secret", "truth", "best",
            "first", "only", "must", "wow"}
CTA = {"تابع", "تابعني", "تابعونا", "اشترك", "اشتركوا", "لايك", "شير", "اللينك", "الرابط", "احجز", "احجزوا", "كلمني",
       "كلمنا", "جرب", "جربوا", "يلا", "متنساش", "follow", "subscribe", "link", "book", "try", "join", "comment"}
QUESTION = {"ليه", "ازاي", "إزاي", "امتى", "إمتى", "فين", "مين", "تخيل", "تخيّل", "هل", "why", "how", "what", "imagine"}
SENT_END = re.compile(r"[.!?؟…]$")
TOKEN = re.compile(r"[\w؀-ۿ]+")
PACING = {"tense": (0.6, 1.6), "playful": (0.6, 1.5), "funny": (0.7, 1.8), "epic": (1.2, 2.8),
          "inspiring": (1.4, 3.0), "warm": (1.8, 3.5), "calm": (2.5, 5.0), "sad": (2.5, 5.0)}
ROLE_WEIGHT = {"hook": 0.10, "setup": 0.22, "context": 0.22, "problem": 0.18, "turn": 0.22, "build": 0.22,
               "journey": 0.25, "climax": 0.20, "reveal": 0.18, "proof": 0.18, "payoff": 0.22, "cta": 0.10, "outro": 0.08}
ROLE_AR = {"hook": "خطّاف", "setup": "تمهيد", "context": "سياق", "problem": "مشكلة", "turn": "تحوّل", "build": "تصاعد",
           "journey": "رحلة", "climax": "ذروة", "reveal": "كشف", "proof": "دليل", "payoff": "حصاد", "cta": "دعوة",
           "outro": "خاتمة"}
SPEECH_SHARE = {"speech-led": 0.75, "slow-burn": 0.5, "on-beat": 0.35}
SPEECH_CONTENT = {"talking-head", "interview", "podcast", "debate", "explainer"}
SNAP_TOL = 0.15
REFILL_TOL = 0.08          # apply_review re-fills until the cut is within 8% under brief.target_seconds
FIX_ORDER = {"drop": 0, "swap": 1, "trim": 2, "retime": 3, "extend": 4, "regrade": 5, "add": 6}
MIN_KEEP = {"speech": 0.8, "broll": 0.3}
DEFAULT_ARC = ["hook", "setup", "turn", "payoff", "cta"]


def norm(tok: str) -> str:
    t = re.sub(r"[ً-ْـ]", "", tok.strip().casefold())          # harakat + tatweel
    return re.sub(r"(.)\1{2,}", r"\1\1", t).strip(".,!?؟،…:;\"'()")


def is_filler(w: dict) -> bool:
    t = norm(E.word_text(w))
    return t in FILLERS or bool(re.fullmatch(r"(ا|آ|م|ه|e|u|m|h)+", t or "x"))


def tokens(s) -> set:
    return {norm(x) for x in TOKEN.findall(str(s)) if len(x) > 1}


def repeats(toks: set, used: list) -> bool:
    return any(len(toks & u) / max(1, len(toks | u)) >= 0.6 for u in used)


def qscore(shot) -> float:
    """Shot quality; null (no OpenCV) counts as a neutral 0.5."""
    v = ((shot or {}).get("quality") or {}).get("score")
    try:
        return float(v) if v is not None else 0.5
    except (TypeError, ValueError):
        return 0.5


# ---------------------------------------------------------------------------- inputs
def load_inputs(job: Path) -> dict:
    opt = lambda kind, default: C.read(job, kind) if (job / f"{kind}.json").exists() else default  # noqa: E731
    try:
        ref = json.loads((job / "reference_rhythm.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ref = None
    return {"analysis": C.read(job, "analysis"),
            "brief": opt("brief", C.new("brief", task="", platform="reel", aspect="9:16", target_seconds=45,
                                        feeling="inspiring", energy=0.5, content_type="montage", must_keep=[], avoid=[])),
            "concepts": opt("concepts", C.new("concepts", concepts=[{"id": "A", "arc": DEFAULT_ARC, "rhythm": "on-beat", "hook": {}}],
                                              decision={"chosen": "A"})),
            "look": opt("look", C.new("look", style_id="clean", grade={"id": "none"}, transitions=[{"id": "cut"}],
                                      camera=[], captions={"style": "clean", "font": "Cairo", "position": "lower"})),
            "reference": ref}


def chosen_concept(concepts: dict) -> dict:
    cid = (concepts.get("decision") or {}).get("chosen")
    return next((c for c in concepts.get("concepts", []) if c.get("id") == cid),
                (concepts.get("concepts") or [{"id": "A", "arc": DEFAULT_ARC}])[0])


def pacing_range(brief: dict, concept: dict, reference) -> tuple:
    if reference and (reference.get("pacing") or {}).get("mean_shot_s"):
        m = float(reference["pacing"]["mean_shot_s"])
        return max(0.4, m * 0.6), max(0.8, m * 1.5), f"reference rhythm mean {m:.2f}s"
    lo, hi = PACING.get(brief.get("feeling", ""), (1.2, 3.0))
    e = float(brief.get("energy", 0.5) if brief.get("energy") is not None else 0.5)
    f = (1.3 - 0.6 * max(0.0, min(1.0, e))) * (1.25 if concept.get("rhythm") == "slow-burn" else 1)
    return round(lo * f, 3), round(hi * f, 3), f"{brief.get('feeling', 'default')} @ energy {e:.2f}"


def speech_share(cands: list, concept: dict) -> float:
    sp, br = any(c["kind"] == "speech" for c in cands), any(c["kind"] == "broll" for c in cands)
    return SPEECH_SHARE.get(concept.get("rhythm", ""), 0.5) if sp and br else (1.0 if sp else 0.0)


# ---------------------------------------------------------------------------- (a) candidates
def shot_at(clip: dict, t: float):
    return next((s for s in clip.get("shots") or [] if s["start"] - 1e-6 <= t < s["end"] + 1e-6), None)


def mean_rms(clip: dict, a: float, b: float) -> float:
    en = clip.get("energy") or []
    if not en:
        return 0.0
    ts = [e["t"] for e in en]
    i, j = bisect.bisect_left(ts, a), bisect.bisect_right(ts, b)
    vals = [en[k]["rms"] for k in range(i, j)] or [en[min(i, len(en) - 1)]["rms"]]
    return sum(vals) / len(vals)


def phrases(clip: dict, max_len: float = 8.0, pause: float = 0.4) -> list:
    """Words -> phrases: break on fillers, pauses > pause, silences, sentence ends and max_len."""
    words = sorted(clip.get("words") or [], key=lambda w: (float(w["start"]), float(w["end"])))
    sil = [(float(s["start"]), float(s["end"])) for s in clip.get("silences") or [] if s["end"] - s["start"] > pause]
    out, cur = [], []
    for w in words:
        if is_filler(w):
            out, cur = out + ([cur] if cur else []), []
            continue
        if cur:
            ga, gb = float(cur[-1]["end"]), float(w["start"])
            if gb - ga > pause or any(a < gb and b > ga for a, b in sil) or float(w["end"]) - float(cur[0]["start"]) > max_len:
                out, cur = out + [cur], []
        cur.append(w)
        if SENT_END.search(E.word_text(w)):
            out, cur = out + [cur], []
    return [p for p in out + [cur] if p]


def speech_candidate(clip: dict, ws: list, all_words: list, idx_of: dict, hook_toks: set, must: set, avoid: set) -> dict:
    """A phrase -> candidate with cut points inside the gaps around it (never inside a word)."""
    i0, i1 = idx_of[id(ws[0])], idx_of[id(ws[-1])]
    prev_end = float(all_words[i0 - 1]["end"]) if i0 > 0 else 0.0
    next_start = float(all_words[i1 + 1]["start"]) if i1 + 1 < len(all_words) else float(clip["duration"])
    s, e = float(ws[0]["start"]), float(ws[-1]["end"])
    src_in = max(prev_end + 0.02, s - 0.08, 0.0)
    src_out = min(next_start - 0.02, e + 0.12, float(clip["duration"]))
    text = " ".join(E.word_text(w) for w in ws)
    toks = tokens(text)
    shot = shot_at(clip, (s + e) / 2) or {}
    emph = [E.word_text(w) for w in ws if norm(E.word_text(w)) in EMPHASIS or w.get("emphasis")
            or re.search(r"\d|!", E.word_text(w))]
    return {"kind": "speech", "clip": clip["id"], "shot": shot.get("id"), "src_in": r3(src_in), "src_out": r3(src_out),
            "dur": src_out - src_in, "text": text, "n_words": len(ws), "wps": len(ws) / max(0.3, e - s),
            "conf": sum(float(w.get("conf", 0.8)) for w in ws) / len(ws), "quality": qscore(shot),
            "faces": int(shot.get("faces", 0) or 0), "motion": float(shot.get("motion_energy", 0) or 0),
            "rms": mean_rms(clip, s, e), "emphasis": emph, "question": bool(toks & QUESTION) or "؟" in text or "?" in text,
            "cta": bool(toks & CTA), "hook_overlap": len(toks & hook_toks) / max(1, len(hook_toks)) if hook_toks else 0.0,
            "must": bool(toks & must), "avoid": bool(toks & avoid), "pos": s / max(1.0, float(clip["duration"])),
            "word_gaps": [(float(ws[k]["end"]), float(ws[k + 1]["start"])) for k in range(len(ws) - 1)],
            "words": [(float(w["start"]), float(w["end"])) for w in ws], "pad_lo": prev_end + 0.02, "pad_hi": next_start - 0.02}


def broll_candidates(clip: dict, lo: float, hi: float, avoid_shots: set) -> list:
    out = []
    for s in clip.get("shots") or []:
        length = float(s["end"]) - float(s["start"])
        if s["id"] in avoid_shots or length < max(0.4, lo * 0.6):
            continue
        L = min(hi, length * 0.85) if length > lo else length
        start = float(s["start"]) + (length - L) * 0.35         # skip the settle-in, keep the steady middle
        q = s.get("quality") or {}
        out.append({"kind": "broll", "clip": clip["id"], "shot": s["id"], "src_in": r3(start), "src_out": r3(start + L),
                    "dur": L, "shot_start": float(s["start"]), "shot_end": float(s["end"]), "text": "",
                    "quality": qscore(s), "faces": int(s.get("faces", 0) or 0), "motion": float(s.get("motion_energy", 0) or 0),
                    "shake": float(q.get("shake") or 0), "saturation": float((s.get("color") or {}).get("saturation", 0.4) or 0.4),
                    "pos": float(s["start"]) / max(1.0, float(clip.get("duration") or s["end"])),
                    "estimated": bool(q.get("estimated")),
                    "emphasis": [], "must": False, "avoid": False, "cta": False, "question": False})
    return out


def build_candidates(analysis: dict, brief: dict, concept: dict, lo: float, hi: float) -> list:
    hook_toks = tokens((concept.get("hook") or {}).get("text", ""))
    must = set().union(*[tokens(x) for x in brief.get("must_keep") or []])
    avoid = set().union(*[tokens(x) for x in brief.get("avoid") or []])
    cands = []
    for order, clip in enumerate(analysis.get("clips", [])):
        words = sorted(clip.get("words") or [], key=lambda w: (float(w["start"]), float(w["end"])))
        quiet = set()
        if len(words) >= 5:
            idx_of = {id(w): i for i, w in enumerate(words)}
            clip = {**clip, "words": words}
            for ws in phrases(clip):
                if sum(not is_filler(w) for w in ws) >= 2:
                    c = speech_candidate(clip, ws, words, idx_of, hook_toks, must, avoid)
                    if c["dur"] >= 0.6:
                        cands.append(c)
            # wordless shots inside a talking clip can still serve as b-roll
            quiet = {s["id"] for s in clip.get("shots") or []
                     if any(float(w["start"]) < s["end"] and float(w["end"]) > s["start"] for w in words)}
        cands += broll_candidates(clip, lo, hi, quiet)
        for c in cands:
            c.setdefault("order", order)
    for i, c in enumerate(cands):
        c["cid"] = f"k{i:04d}"
    return cands


# ---------------------------------------------------------------------------- (b) scoring
def score(c: dict, role: str, hook_budget: float) -> tuple:
    """Role fitness (0..~2) plus a concrete (en, ar) reason fragment."""
    q, faces, mot, sp = c["quality"], c["faces"], c["motion"], c["kind"] == "speech"
    base = 0.35 * q + (0.12 if faces else 0.0) - 0.25 * c.get("shake", 0) - (0.08 if c.get("estimated") else 0)
    if c["must"]:
        base += 0.8
    if c["avoid"]:
        base -= 1.0
    if role == "hook":
        if sp:
            short = 1.0 if c["dur"] <= hook_budget * 1.2 else max(0.0, 1 - (c["dur"] - hook_budget) / 4)
            punch = min(1.0, c["wps"] / 3.5) * 0.3 + (0.35 if c["emphasis"] else 0) + (0.3 if c["question"] else 0) \
                + 0.6 * c.get("hook_overlap", 0) + 0.4 * min(1.0, c["rms"] / 0.3)
            return (base + 0.7 * short + punch,
                    f"strongest short line ({c['dur']:.1f}s, {c['wps']:.1f} w/s{', emphasis ' + c['emphasis'][0] if c['emphasis'] else ''}{', question' if c['question'] else ''})",
                    f"أقوى جملة قصيرة ({c['dur']:.1f}ث){' فيها سؤال' if c['question'] else ''}{' وتأكيد «' + c['emphasis'][0] + '»' if c['emphasis'] else ''}")
        return (base + 0.9 * mot + (0.35 if faces else 0) + 0.2 * c.get("saturation", 0.4),
                f"most energetic shot (motion {mot:.2f}{', face' if faces else ''})",
                f"أكثر لقطة فيها حركة ({mot:.2f}){' ووش واضح' if faces else ''}")
    if role in ("setup", "context", "problem"):
        return (base + 0.6 * (1 - c["pos"]) + (0.45 if sp else 0) + (0.2 * c.get("conf", 0) if sp else 0),
                "early, clear statement that sets the scene" if sp else "establishing shot from early in the footage",
                "جملة واضحة من الأول بتعرّف الحكاية" if sp else "لقطة تأسيسية من أول التصوير")
    if role in ("turn", "build", "journey", "proof"):
        return (base + 0.55 * mot + 0.25 * (1 - abs(c["pos"] - 0.5) * 2) + (0.2 if c["question"] else 0),
                f"mid-story movement (motion {mot:.2f})" if not sp else "mid-story line that moves the story on",
                f"حركة في نص الحكاية ({mot:.2f})" if not sp else "جملة من النص بتحرّك الحكاية")
    if role in ("payoff", "climax", "reveal"):
        return (base + 0.45 * c["pos"] + (0.35 if c["emphasis"] else 0) + 0.35 * mot + 0.25 * q,
                f"late, high-quality {'line with emphasis' if c['emphasis'] else 'moment'} (q {q:.2f})",
                f"لحظة قوية متأخرة بجودة {q:.2f}{' وفيها تأكيد' if c['emphasis'] else ''}")
    if role in ("cta", "outro"):
        return (base + (1.2 if c["cta"] else 0) + 0.5 * c["pos"] + (0.3 if sp else 0) + (0.2 if faces else 0) - 0.3 * mot,
                "call to action spoken to camera" if c["cta"] else ("closing line" if sp else "calm closing shot"),
                "دعوة صريحة للمشاهد" if c["cta"] else ("جملة ختام" if sp else "لقطة ختام هادية"))
    return base + 0.3 * mot, "fits the arc", "مناسبة للقوس"


# ---------------------------------------------------------------------------- (c) fill the arc
def budgets(arc: list, target: float, hook_first: float) -> dict:
    w = {r: ROLE_WEIGHT.get(r, 0.2) for r in arc}
    b = {r: target * w[r] / sum(w.values()) for r in arc}
    if "hook" in b:
        want = max(1.5, min(float(hook_first or 3.0), target * 0.15))
        diff, b["hook"] = b["hook"] - want, want
        others = [r for r in arc if r != "hook"]
        for r in others:
            b[r] += diff / max(1, len(others))
    return b


def ranges_overlap(c: dict, used: list) -> bool:
    return any(u["clip"] == c["clip"] and c["src_in"] < u["src_out"] - 1e-6 and c["src_out"] > u["src_in"] + 1e-6
               for u in used)


def trim_speech(c: dict, max_dur: float):
    """Shorten a phrase at a word gap so it fits max_dur (>= 2 words kept, never inside a word)."""
    for k in range(len(c["words"]) - 1, 1, -1):
        end, nxt = c["words"][k - 1][1], c["words"][k][0]
        out = min(end + 0.12, (end + nxt) / 2)
        if out - c["src_in"] <= max_dur:
            return dict(c, src_out=r3(out), dur=out - c["src_in"], words=c["words"][:k], word_gaps=c["word_gaps"][:k - 1],
                        pad_hi=c["words"][k][0] - 0.02, n_words=k, trimmed=True)
    return None


def fit_broll(c: dict, want: float, lo: float, hi: float) -> dict:
    span = c["shot_end"] - c["shot_start"]
    L = max(min(want, hi, span), min(lo, span))
    src_in = r3(c["shot_start"] + (span - L) * 0.35)
    return dict(c, src_in=src_in, src_out=r3(src_in + L), dur=L)


def _key(s: float, cc: dict) -> tuple:
    return round(s, 6), -cc["order"], -cc["src_in"]


def direct_plan(inp: dict) -> tuple:
    analysis, brief = inp["analysis"], inp["brief"]
    concept = chosen_concept(inp["concepts"])
    arc = list(concept.get("arc") or DEFAULT_ARC)
    target = float(brief.get("target_seconds") or 45)
    lo, hi, pace_why = pacing_range(brief, concept, inp["reference"])
    cands = build_candidates(analysis, brief, concept, lo, hi)
    share = speech_share(cands, concept)
    bud = budgets(arc, target, float((concept.get("hook") or {}).get("first_seconds") or 3))
    hr = hook_roles()
    opener = arc[0] if arc and arc[0] in hr else None
    talk_first = any(c["kind"] == "speech" for c in cands) and (
        brief.get("content_type") in SPEECH_CONTENT or concept.get("rhythm") == "speech-led")
    used, used_shots_broll, shot_uses, used_texts, plan = [], set(), {}, [], []
    totals, carry = {"speech": 0.0, "broll": 0.0}, 0.0
    for ri, role in enumerate(arc):
        budget, filled, picks = bud[role] + carry, 0.0, []
        for _ in range(40):
            opening = ri == 0 and opener is not None and not picks     # the first 3 s: judged as a hook
            remaining = budget - filled
            if remaining < max(0.4, lo * 0.5):
                break
            best = None
            for c in cands:
                if ranges_overlap(c, used) or (c["kind"] == "broll" and c["shot"] in used_shots_broll):
                    continue
                if opening and talk_first and c["kind"] != "speech":
                    continue
                if c["kind"] == "speech":
                    cc, slack = c, (1.6 if role == "hook" or opening else 1.25)
                    if c["dur"] > remaining * slack + 0.5:
                        cc = trim_speech(c, remaining * slack + 0.3)
                        if cc is None:
                            continue
                else:
                    if remaining < lo * 0.6:
                        continue
                    cc = fit_broll(c, remaining if remaining < hi else hi, lo, hi)
                s, en, ar = score(cc, "hook" if opening else role, bud.get("hook", 3.0))
                if role != "hook" and not opening and 0 < share < 1:
                    done = totals["speech"] + totals["broll"]
                    want_speech = (totals["speech"] / done if done else share) < share
                    s += 0.4 if (cc["kind"] == "speech") == want_speech else -0.15
                if cc.get("shot") and cc["kind"] == "speech":
                    s -= 0.05 * shot_uses.get(cc["shot"], 0)          # novelty: same talking shot again
                if cc.get("trimmed"):
                    s -= 0.15
                if cc["kind"] == "speech":
                    if repeats(tokens(cc["text"]), used_texts):
                        s -= 1.5                                         # never say the same line twice
                    if cc["cta"] and role not in ("cta", "outro"):
                        s -= 0.6                                         # keep the ask for the end
                if best is None or _key(s, cc) > best[0]:
                    best = (_key(s, cc), cc, en, ar, s)
            if best is None:
                break
            _, cc, en, ar, s = best
            cc = dict(cc, role=role, why_en=en, why_ar=ar, score=round(s, 3), **({"hook": True} if opening else {}))
            used.append(cc)
            picks.append(cc)
            if cc["kind"] == "broll":
                used_shots_broll.add(cc["shot"])
            if cc.get("shot"):
                shot_uses[cc["shot"]] = shot_uses.get(cc["shot"], 0) + 1
            totals[cc["kind"]] += cc["dur"]
            if cc["kind"] == "speech":
                used_texts.append(tokens(cc["text"]))
            filled += cc["dur"]
            if role == "hook":
                break
        carry = budget - filled
        plan += picks[:1] + order_role(picks[1:], role) if picks and picks[0].get("hook") else order_role(picks, role)
    meta = {"concept": concept.get("id"), "arc": arc, "target_seconds": target, "pacing": [lo, hi], "pacing_why": pace_why,
            "speech_share_target": share, "budgets": {k: round(v, 2) for k, v in bud.items()},
            "candidates": len(cands), "candidates_speech": sum(c["kind"] == "speech" for c in cands),
            "candidates_broll": sum(c["kind"] == "broll" for c in cands), "opener": opener, "hook_roles": sorted(hr)}
    return plan, meta, cands


def order_role(picks: list, role: str) -> list:
    """Inside a role: speech stays chronological, b-roll is interleaved between lines."""
    if role == "hook" or len(picks) <= 1:
        return picks
    by = lambda kind: sorted([p for p in picks if p["kind"] == kind], key=lambda p: (p["order"], p["src_in"]))  # noqa: E731
    a, b = (by("speech"), by("broll")) if picks[0]["kind"] == "speech" else (by("broll"), by("speech"))
    out = []
    while a or b:
        out += ([a.pop(0)] if a else []) + ([b.pop(0)] if b else [])
    return out


# ---------------------------------------------------------------------------- (d) beats
def nearest(grid: list, t: float):
    if not grid:
        return None
    i = bisect.bisect_left(grid, t)
    return min((grid[j] for j in (i - 1, i) if 0 <= j < len(grid)), key=lambda g: (abs(g - t), g))


def snap_to_beats(events: list, plans: list, analysis: dict, lo: float, hi: float) -> int:
    m = analysis.get("music") or {}
    beats, downs = sorted(float(x) for x in m.get("beats") or []), sorted(float(x) for x in m.get("downbeats") or [])
    if not beats:
        return 0
    snapped, edl = 0, {"events": events}
    for i, (ev, p) in enumerate(zip(events, plans)):
        E.reflow(edl)
        if i == len(events) - 1:
            break
        cut = ev["rec_in"] + E.event_seconds(ev) - E.overlap(events[i + 1])
        sp = float(ev.get("speed", 1.0))
        if p["kind"] == "broll":
            lo_out = ev["src_in"] + max(0.4, lo * 0.7) * sp
            hi_out = min(p["shot_end"], ev["src_in"] + hi * 1.3 * sp)
            fits = lambda g: lo_out <= ev["src_out"] + (g - cut) * sp <= hi_out  # noqa: E731
            choice = next(((g, label) for g, label in ((nearest(downs, cut), "downbeat"), (nearest(beats, cut), "beat"))
                           if g is not None and abs(g - cut) <= SNAP_TOL and fits(g)), None)
            if choice is None:      # elastic b-roll: re-fit to the beat grid
                choice = next(((g, "beat (re-fit)") for g in sorted({x for x in beats if abs(x - cut) <= 0.75},
                                                                     key=lambda x: (abs(x - cut), x)) if fits(g)), None)
            if choice:
                g, label = choice
                ev["src_out"] = r3(ev["src_out"] + (g - cut) * sp)
                ev["beat"] = {"at": r3(g), "type": label, "moved": r3(g - cut)}
                snapped += 1
        else:   # speech: may only move inside the gap after the last kept word
            g_lo, g_hi = p["words"][-1][1] + 0.03, p["pad_hi"]
            for g in (nearest(downs, cut), nearest(beats, cut)):
                if g is None or abs(g - cut) > SNAP_TOL:
                    continue
                new_out = ev["src_out"] + (g - cut) * sp
                if g_lo <= new_out <= g_hi:
                    ev["src_out"] = r3(new_out)
                    ev["beat"] = {"at": r3(g), "type": "beat (inside word gap)", "moved": r3(g - cut)}
                    snapped += 1
                    break
    E.reflow(edl)
    return snapped


# ---------------------------------------------------------------------------- (e) look + assemble
def apply_look(events: list, plans: list, look: dict) -> None:
    xf = next(({"id": t.get("id", n), "xfade": n, "seconds": float(t.get("seconds", t.get("duration", 0.25)))}
               for t in look.get("transitions") or [] for n in [E.xfade_name(t)] if n), None)
    cam = next((dict(c) for c in look.get("camera") or [] if c.get("id") and c["id"] not in ("static", "none")), None)
    prev = None
    for i, (ev, p) in enumerate(zip(events, plans)):
        if xf and prev is not None and prev["role"] != p["role"] and prev["kind"] == "broll" and p["kind"] == "broll":
            ev["transition_in"] = dict(xf)
            ev["reason"] += (f"; {xf['xfade']} {xf['seconds']}s into the {p['role']} section (look) | "
                             f"انتقال {xf['xfade']} لبداية قسم {ROLE_AR.get(p['role'], p['role'])} حسب الذوق")
        else:
            ev["transition_in"] = {"id": "cut"}
        jump = prev is not None and p["kind"] == "speech" and prev["kind"] == "speech" and p.get("shot") == prev.get("shot")
        punched = i > 0 and events[i - 1].get("camera", {}).get("id") not in (None, "static")
        if cam and p["kind"] == "speech" and (p["emphasis"] or jump) and not (jump and punched):
            ev["camera"] = dict(cam)
            ev["reason"] += (f"; {cam['id']} on «{p['emphasis'][0]}» | {cam['id']} على كلمة «{p['emphasis'][0]}»" if p["emphasis"]
                             else f"; {cam['id']} hides the jump cut | {cam['id']} عشان يخفي القفزة")
        elif cam and p["kind"] == "broll" and p["role"] in ("hook", "climax", "payoff") and cam["id"] != "punch-in":
            ev["camera"] = dict(cam)
        else:
            ev["camera"] = {"id": "static"}
        prev = p


def to_events(plan: list) -> list:
    evs = []
    for i, p in enumerate(plan, 1):
        detail = f"«{' '.join(p['text'].split()[:8])}»" if p["kind"] == "speech" else f"shot {p['shot']}"
        reason = (f"{p['role']}: {p['why_en']}, quality {p['quality']:.2f}{', face' if p['faces'] else ''} — {detail}"
                  f" | {ROLE_AR.get(p['role'], p['role'])}: {p['why_ar']}، جودة {p['quality']:.2f}")
        if p.get("trimmed"):
            reason += " (trimmed at a word gap | اتقصّت عند فاصل بين كلمتين)"
        ev = {"id": f"e{i:03d}", "clip": p["clip"], "src_in": p["src_in"], "src_out": p["src_out"], "rec_in": 0.0,
              "speed": 1.0, "transition_in": {"id": "cut"}, "camera": {"id": "static"}, "reason": reason,
              "role": p["role"], "kind": p["kind"], "shot": p.get("shot"), "score": p["score"]}
        if p["kind"] == "speech":
            ev["text"] = p["text"]
        if p.get("hook"):
            ev["hook"] = True
        evs.append(ev)
    return evs


def fit_duration(events: list, plans: list, target: float, lo: float, hi: float) -> None:
    """Final ±5% guard: stretch or shrink elastic b-roll windows inside their shots."""
    edl = E.reflow({"events": events})
    for _ in range(3):
        diff = target - edl["duration"]
        elastic = [(e, p) for e, p in zip(events, plans) if p["kind"] == "broll"]
        if abs(diff) <= target * 0.05 or not elastic:
            return
        for e, p in elastic:
            new_out = min(p["shot_end"], max(e["src_in"] + max(0.4, lo * 0.7), e["src_out"] + diff / len(elastic)))
            e["src_out"] = r3(min(new_out, e["src_in"] + hi * 1.3))
        E.reflow(edl)


def reference_exact(edl: dict, plans: list, reference) -> dict:
    """--reference-exact: the cuts land at the reference's own cut times (reference_rhythm.transitions[].at), shot by
    shot, instead of its mean shot length. A shot too short for its slot keeps its length (reported)."""
    ats = sorted(float(t["at"]) for t in (reference or {}).get("transitions") or [] if t.get("at") is not None)
    end = float(((reference or {}).get("reference") or {}).get("duration") or 0)
    edges = [0.0] + [a for a in ats if a > 0] + ([end] if end and (not ats or end > ats[-1]) else [])
    slots = [round(b - a, 3) for a, b in zip(edges, edges[1:]) if b - a > 0.1]
    short = []
    for i, (ev, slot) in enumerate(zip(edl["events"], slots)):
        p = plans[i] if i < len(plans) else {}
        sp = float(ev.get("speed", 1.0) or 1.0)
        limit = float(p.get("shot_end") or ev["src_out"])
        want = float(ev["src_in"]) + slot * sp
        if want > limit + 1e-6:
            short.append(ev["id"])
        ev["src_out"] = r3(min(want, limit))
        ev["transition_in"] = {"id": "cut"}            # the reference's cut times hold only with straight cuts
    E.reflow(edl)
    return {"slots": slots, "applied": min(len(slots), len(edl["events"])), "short_shots": short,
            "cuts_at": [r3(e["rec_in"]) for e in edl["events"][1:]]}


def reach_target(edl: dict, plans: list, target: float, max_slow: float = 0.5, clip_ends: dict | None = None) -> dict:
    """The owner gave --seconds: the cut must reach it. First the last event runs on inside its shot (or clip), then it
    slows down (speed >= max_slow). Overlaps of the xfades are counted by E.reflow. Returns what was done."""
    E.reflow(edl)
    gap = round(target - edl["duration"], 3)
    done = {"target": target, "before": edl["duration"], "gap": gap, "extended_s": 0.0, "speed": None}
    if gap <= 0.02 or not edl["events"]:
        return done
    ev = edl["events"][-1]
    p = plans[-1] if plans and len(plans) == len(edl["events"]) else {}
    limit = float(p.get("shot_end") or (clip_ends or {}).get(ev.get("clip")) or ev["src_out"])
    sp = float(ev.get("speed", 1.0) or 1.0)
    room = max(0.0, limit - float(ev["src_out"]))
    ext = min(room, gap * sp)
    if ext > 0:
        ev["src_out"] = r3(float(ev["src_out"]) + ext)
        done["extended_s"] = r3(ext)
    E.reflow(edl)
    gap = target - edl["duration"]
    if ev.get("kind") == "speech":
        max_slow = max(max_slow, 0.9)       # a voice slowed more than 10% sounds wrong
    if gap > 0.02:
        src = float(ev["src_out"]) - float(ev["src_in"])
        new = max(max_slow, src / (src / sp + gap))
        ev["speed"] = round(new, 4)
        done["speed"] = ev["speed"]
        E.reflow(edl)
    done["after"] = edl["duration"]
    done["short_by"] = round(max(0.0, target - edl["duration"]), 3)
    return done


def direct(job) -> dict:
    job = Path(job)
    inp = load_inputs(job)
    analysis, brief, look = inp["analysis"], inp["brief"], inp["look"]
    plan, meta, _ = direct_plan(inp)
    if not plan:
        raise SystemExit("no usable footage: analysis has no shots and no words")
    lo, hi = meta["pacing"]
    events = to_events(plan)
    fit_duration(events, plan, meta["target_seconds"], lo, hi)
    apply_look(events, plan, look)
    meta["snapped_cuts"] = snap_to_beats(events, plan, analysis, lo, hi)
    w, h = C.ASPECTS.get(brief.get("aspect", "9:16"), (1080, 1920))
    caps, music = look.get("captions") or {}, analysis.get("music") or {}
    has_speech = any(e["kind"] == "speech" for e in events)
    for e in events:
        if e["kind"] == "broll" and music.get("path"):
            e["mute"] = True            # natural sound off under the music bed
    style = caps.get("style", "clean")
    edl = C.new("edl", width=w, height=h, fps=30, events=events,
                audio={"music": {"path": music.get("path"), "gain_db": -18 if has_speech else -8, "duck_under_speech_db": -10},
                       "voice_from": "events", "target_lufs": -14},
                captions={"enabled": style != "none" and has_speech, "style": style, "font": caps.get("font", "Cairo"),
                          "position": caps.get("position", "lower"), "words_from": "analysis"},
                grade=dict(look.get("grade") or {"id": "none"}), duration=0.0)
    E.reflow(edl)
    if inp.get("reference") and inp["reference"].get("exact"):
        meta["reference_exact"] = reference_exact(edl, plan, inp["reference"])
    elif brief.get("owner_seconds"):
        ends = {c["id"]: float(c.get("duration") or 0) or None for c in analysis.get("clips", [])}
        meta["reach_target"] = reach_target(edl, plan, float(brief["owner_seconds"]), clip_ends=ends)
    edl["revision"] = 0
    edl["meta"] = {**meta, "station": STATION, "look": look.get("style_id"), "events": len(events),
                   "deviation_pct": round(100 * (edl["duration"] - meta["target_seconds"]) / meta["target_seconds"], 1)}
    problems = E.check(edl)
    if problems:
        raise SystemExit("edl check failed: " + "; ".join(problems))
    C.write(job, "edl", edl)
    return edl


# ---------------------------------------------------------------------------- apply_review
def _word_safe(clip: dict, t: float, *, side: str) -> float:
    """Move t out of any word: to the gap before (side='out') or after (side='in')."""
    for w in clip.get("words") or []:
        s, e = float(w["start"]), float(w["end"])
        if s < t < e:
            return r3(s - 0.02) if side == "out" else r3(e + 0.02)
    return r3(t)


def _shot_bounds(clip: dict, ev: dict) -> tuple:
    sh = next((s for s in clip.get("shots") or [] if s.get("id") == ev.get("shot")), None) or \
        shot_at(clip, (float(ev["src_in"]) + float(ev["src_out"])) / 2)
    return (float(sh["start"]), float(sh["end"])) if sh else (0.0, float(clip.get("duration") or ev["src_out"]))


def _neighbour_limits(ev: dict, events: list) -> tuple:
    """Source range this event may grow into without overlapping another event from the same clip."""
    lo, hi = 0.0, float("inf")
    for o in events:
        if o is ev or o["clip"] != ev["clip"]:
            continue
        if o["src_out"] <= ev["src_in"] + 1e-6:
            lo = max(lo, float(o["src_out"]))
        elif o["src_in"] >= ev["src_out"] - 1e-6:
            hi = min(hi, float(o["src_in"]))
    return lo, hi


def extend_event(ev: dict, clip: dict, events: list, secs: float) -> float:
    """Grow an event by ~secs: b-roll inside its shot (tail, then head), speech to the next word gap."""
    n_lo, n_hi = _neighbour_limits(ev, events)
    dur = float(clip.get("duration") or ev["src_out"])
    a0, b0 = float(ev["src_in"]), float(ev["src_out"])
    if ev.get("kind") == "speech":
        nxt = [w for w in sorted(clip.get("words") or [], key=lambda w: float(w["start"])) if float(w["start"]) >= b0 - 0.02]
        b = b0
        for i, w in enumerate(nxt):
            if is_filler(w) or float(w["end"]) > min(n_hi - 0.02, dur):
                break
            follow = float(nxt[i + 1]["start"]) if i + 1 < len(nxt) else dur
            b = min(float(w["end"]) + 0.12, (float(w["end"]) + follow) / 2, n_hi - 0.02, dur)
            if b - b0 >= secs:
                break
        ev["src_out"] = r3(max(b, b0))
    else:
        s_lo, s_hi = _shot_bounds(clip, ev)
        b = min(b0 + secs, s_hi, n_hi, dur)
        ev["src_in"], ev["src_out"] = r3(max(a0 - max(0.0, secs - (b - b0)), s_lo, n_lo, 0.0)), r3(b)
    return (float(ev["src_out"]) - float(ev["src_in"])) - (b0 - a0)


def _global_fix(edl: dict, fx: dict, detail: str) -> str:
    tgt = fx.get("target", "grade")
    if tgt == "audio":
        edl["audio"]["target_lufs"] = float(fx.get("lufs", edl["audio"].get("target_lufs", -14)))
        tp = float(edl["audio"].get("limiter_tp", -1.0))   # each failed round lowers the ceiling a little more
        edl["audio"]["limiter_tp"] = max(-3.0, round(tp - 0.5, 2)) if fx.get("check") == "audio-clipping" else tp
    elif tgt == "captions":
        cap = edl.setdefault("captions", {})
        if fx.get("min_bottom") is not None or fx.get("check") == "safe-area":
            cap["min_bottom_frac"] = max(float(cap.get("min_bottom_frac") or 0), float(fx.get("min_bottom") or 0.24))
        if fx.get("check") == "caption-coverage":
            cap["enabled"] = True
        cap["note"] = detail
    elif tgt == "encode":
        edl.setdefault("render_hints", {})["encode"] = detail
    else:
        edl["grade"] = {**edl.get("grade", {}), **({"id": fx["grade"]} if fx.get("grade") else {}), "note": detail}
    return f"global {tgt}"


def _event_fix(fx: dict, ev: dict, edl: dict, clip: dict, inp: dict, dropped: list):
    """Apply one event fix; returns (note, None) or (None, why-skipped)."""
    act, speech = fx.get("action"), ev.get("kind") == "speech"
    if act == "trim":
        if "src_in" in fx or "src_out" in fx:
            a, b = float(fx.get("src_in", ev["src_in"])), float(fx.get("src_out", ev["src_out"]))
        elif fx.get("seconds") is not None:
            secs = float(fx["seconds"])
            a, b = (ev["src_in"] + secs, ev["src_out"]) if fx.get("side") in ("head", "in", "start") else (ev["src_in"], ev["src_out"] - secs)
        else:   # never guess a number out of the prose `detail`
            return None, "trim without structured src_in/src_out/seconds"
        a, b = max(a, float(ev["src_in"])), min(b, float(ev["src_out"]))   # trims narrow, never widen
        if speech:
            a, b = _word_safe(clip, a, side="in"), _word_safe(clip, b, side="out")
        keep = MIN_KEEP["speech" if speech else "broll"]
        if b - a < keep:
            return None, f"trim would leave < {keep} s"
        ev["src_in"], ev["src_out"] = r3(a), r3(b)
        return f"trimmed to {a:.2f}-{b:.2f}", None
    if act == "extend":
        if fx.get("seconds") is None:
            return None, "extend without structured seconds"
        got = extend_event(ev, clip, edl["events"], max(0.1, float(fx["seconds"])))
        return (f"extended +{got:.2f}s to {ev['src_in']:.2f}-{ev['src_out']:.2f}", None) if got >= 0.05 else \
            (None, "no room to extend inside the shot/next word")
    if act == "retime":
        if fx.get("speed") is not None:
            ev["speed"] = max(0.5, min(2.0, float(fx["speed"])))
            return f"speed {ev['speed']}", None
        if "rec_at" not in fx:
            return None, "retime without an explicit speed or rec_at"
        E.reflow(edl)    # move this event's out-cut to output time rec_at by changing its src_out
        b = ev["src_out"] + (float(fx["rec_at"]) - (ev["rec_in"] + E.event_seconds(ev))) * float(ev.get("speed", 1.0))
        if speech:
            b = _word_safe(clip, b, side="out")
        b = min(b, float(clip.get("duration", b)))
        if b - ev["src_in"] < 0.3:
            return None, "retime would leave < 0.3 s"
        ev["src_out"] = r3(b)
        return f"cut moved to {float(fx['rec_at']):.2f}s", None
    if act == "regrade":
        ev["grade"] = {"id": fx.get("grade") or str(fx.get("detail", "")) or "neutral"}
        return f"grade {ev['grade']['id']}", None
    if act == "swap":
        new = hook_swap(ev, edl, inp, fx.get("kind"), dropped) if fx.get("role") == "hook" or fx.get("check") == "hook-in-3s" \
            else swap_source(ev, edl, inp, fx.get("with_shot") or fx.get("with"), dropped)
        if new is None:
            return None, "no unused replacement"
        ev.update(new)
        if new.get("hook"):
            edl["events"].remove(ev)
            edl["events"].insert(0, ev)
        return f"swapped to {ev['shot']} {ev['src_in']:.2f}-{ev['src_out']:.2f}", None
    return None, f"unknown action {act}"


def apply_review(job) -> dict:
    job = Path(job)
    inp = load_inputs(job)
    review, edl = C.read(job, "review"), C.read(job, "edl")
    rev = int(edl.get("revision", 0))
    C.save(job / f"edl.r{rev}.json", edl)
    edl = copy.deepcopy(edl)
    meta = edl.setdefault("meta", {})
    dropped = meta.setdefault("dropped_ranges", [])       # never re-add what a review threw out
    clips, by_id = E.clip_index(inp["analysis"]), {e["id"]: e for e in edl["events"]}
    applied, skipped = [], []
    rnd = review.get("round", rev + 1)
    fixes = sorted(review.get("fixes") or [], key=lambda f: FIX_ORDER.get(f.get("action"), 9))
    drop_ids = {f.get("event") for f in fixes if f.get("action") == "drop"}
    for fx in fixes:
        act, eid, detail = fx.get("action"), fx.get("event"), str(fx.get("detail", ""))
        if eid in (None, "*"):
            if act == "regrade":
                applied.append({**fx, "result": _global_fix(edl, fx, detail)})
            elif act == "add":
                applied.append({**fx, "result": "re-fill toward target (below)"})
            else:
                skipped.append({**fx, "why": "global fix without an event only supports regrade/add"})
            continue
        ev = by_id.get(eid)
        if ev is None:
            skipped.append({**fx, "why": "unknown or already dropped event"})
            continue
        if act != "drop" and eid in drop_ids:
            skipped.append({**fx, "why": "event is dropped in this round"})
            continue
        if act == "drop":
            edl["events"].remove(ev)
            by_id.pop(eid)
            dropped.append({"clip": ev["clip"], "src_in": ev["src_in"], "src_out": ev["src_out"], "check": fx.get("check"),
                            "round": rnd})
            applied.append({**fx, "result": "dropped"})
            continue
        note, why = _event_fix(fx, ev, edl, clips.get(ev["clip"], {}), inp, dropped)
        if why:
            skipped.append({**fx, "why": why})
            continue
        ev["reason"] += f"; review r{rnd}: {act} ({fx.get('check', detail)[:60]}) {note} | مراجعة {rnd}: {act}"
        applied.append({**fx, "result": note})
    E.reflow(edl)
    target = float(inp["brief"].get("target_seconds") or meta.get("target_seconds") or edl["duration"])
    for ev in refill(edl, inp, target, dropped):
        applied.append({"event": ev["id"], "action": "add", "check": "duration", "by": "direct",
                        "detail": f"re-fill toward {target:.0f}s",
                        "result": f"added {ev['kind']} {ev['clip']} {ev['src_in']:.2f}-{ev['src_out']:.2f} as {ev['role']}"})
    edl["revision"] = rev + 1
    meta["deviation_pct"] = round(100 * (edl["duration"] - target) / max(0.1, target), 1)
    meta["events"] = len(edl["events"])
    edl.setdefault("history", []).append({"revision": rev + 1, "from": f"edl.r{rev}.json", "review_round": rnd,
                                          "applied": applied, "skipped": skipped, "duration": edl["duration"]})
    problems = E.check(edl)
    if problems:
        raise SystemExit("edl check failed after review: " + "; ".join(problems))
    C.write(job, "edl", edl)
    return edl


def _candidates(inp: dict) -> tuple:
    brief, concept = inp["brief"], chosen_concept(inp["concepts"])
    lo, hi, _ = pacing_range(brief, concept, inp["reference"])
    return build_candidates(inp["analysis"], brief, concept, lo, hi), lo, hi, concept


def hook_swap(ev: dict, edl: dict, inp: dict, kind, dropped: list):
    """Replace the opening event with the best hook candidate; talking content -> a spoken line, never b-roll."""
    cands, lo, hi, _ = _candidates(inp)
    others = [e for e in edl["events"] if e is not ev]
    want = kind or ("speech" if any(c["kind"] == "speech" for c in cands) else "broll")
    used_texts = [tokens(e.get("text", "")) for e in others if e.get("kind") == "speech"]
    used_shots = {e.get("shot") for e in others if e.get("kind") == "broll"}
    best = None
    for c in cands:
        if c["kind"] != want or ranges_overlap(c, others) or ranges_overlap(c, dropped) or \
                (c["kind"] == "broll" and c["shot"] in used_shots):
            continue
        cc = c
        if c["kind"] == "speech":
            if c["dur"] > 6.0:
                cc = trim_speech(c, 5.5)
                if cc is None:
                    continue
            if repeats(tokens(cc["text"]), used_texts):
                continue
        else:
            cc = fit_broll(c, min(3.0, hi), lo, hi)
        s, en, ar = score(cc, "hook", 3.0)
        s -= 0.6 if cc.get("cta") else 0
        if best is None or _key(s, cc) > best[0]:
            best = (_key(s, cc), cc, en, ar)
    if best is None:
        return None
    _, c, en, ar = best
    role = ev.get("role") if ev.get("role") in hook_roles() else "hook"
    out = {"clip": c["clip"], "shot": c["shot"], "src_in": c["src_in"], "src_out": c["src_out"], "kind": c["kind"],
           "role": role, "hook": True, "speed": 1.0,
           "reason": f"{role}: {en} (hook swap) | {ROLE_AR.get(role, role)}: {ar} (استبدال للهوك)"}
    if c["kind"] == "speech":
        out["text"] = c["text"]
    else:
        ev.pop("text", None)
    return out


def refill(edl: dict, inp: dict, target: float, dropped: list) -> list:
    """Add the best unused candidates back until the cut is near the target (middle arc roles, the concept's
    speech/b-roll mix, nothing a review dropped, the hook stays first)."""
    cands, lo, hi, concept = _candidates(inp)
    arc = list(concept.get("arc") or DEFAULT_ARC)
    share, hr = speech_share(cands, concept), hook_roles()
    roles = [r for r in arc if r not in hr and r not in ("cta", "outro")] or [r for r in arc if r not in hr] or arc
    rank = {r: i for i, r in enumerate(arc)}
    added = []
    E.reflow(edl)
    next_id = max([int(e["id"][1:]) for e in edl["events"] if re.fullmatch(r"e\d+", e["id"])] + [0]) + 1
    for _ in range(40):
        gap = target - edl["duration"]
        if gap <= target * REFILL_TOL or gap < 0.5:
            break
        evs = edl["events"]
        used_texts = [tokens(e.get("text", "")) for e in evs if e.get("kind") == "speech"]
        used_shots = {e.get("shot") for e in evs if e.get("kind") == "broll"}
        sp_s = sum(E.event_seconds(e) for e in evs if e.get("kind") == "speech")
        want_speech = (sp_s / (sum(E.event_seconds(e) for e in evs) or 1.0)) < share
        best = None
        for c in cands:
            if ranges_overlap(c, evs) or ranges_overlap(c, dropped):
                continue
            if c["kind"] == "speech":
                cc = c
                if c["dur"] > gap * 1.25 + 0.5:
                    cc = trim_speech(c, gap * 1.25 + 0.3)
                    if cc is None:
                        continue
                if repeats(tokens(cc["text"]), used_texts):
                    continue
            else:
                if c["shot"] in used_shots or gap < lo * 0.6:
                    continue
                cc = fit_broll(c, min(gap, hi), lo, hi)
            role, s, en, ar = max(((r, *score(cc, r, 3.0)) for r in roles), key=lambda x: x[1])
            if 0 < share < 1:
                s += 0.4 if (cc["kind"] == "speech") == want_speech else -0.15
            if cc.get("trimmed"):
                s -= 0.15
            if cc.get("cta"):
                s -= 0.6
            if best is None or _key(s, cc) > best[0]:
                best = (_key(s, cc), cc, role, en, ar, s)
        if best is None:
            break
        _, cc, role, en, ar, s = best
        ev = to_events([dict(cc, role=role, why_en=en, why_ar=ar, score=round(s, 3))])[0]
        ev["id"], next_id = f"e{next_id:03d}", next_id + 1
        ev["reason"] += " (re-filled after review | اتضافت بعد المراجعة عشان المدة)"
        pos = 1          # the end of its arc section; index 0 (the hook) never moves
        for i, e in enumerate(evs):
            if i and rank.get(e.get("role"), 0) <= rank.get(role, 0):
                pos = i + 1
        evs.insert(max(1, min(pos, len(evs))), ev)
        E.reflow(edl)
        added.append(ev)
    return added


def swap_source(ev: dict, edl: dict, inp: dict, with_shot, dropped=None):
    cands, lo, hi, _ = _candidates(inp)
    others = [e for e in edl["events"] if e is not ev]
    used_shots = {e.get("shot") for e in others if e.get("kind") == "broll"} | {ev.get("shot")}
    want, pool = E.event_seconds(ev), []
    for c in cands:
        if ranges_overlap(c, others) or ranges_overlap(c, dropped or []) or c["kind"] != ev.get("kind", c["kind"]):
            continue
        if (with_shot and c.get("shot") != with_shot) or (not with_shot and c.get("shot") in used_shots):
            continue
        cc = fit_broll(c, want, lo, hi) if c["kind"] == "broll" else c
        s, en, ar = score(cc, ev.get("role", "turn"), 3.0)
        pool.append((-s, cc["cid"], cc, en, ar))
    if not pool:
        return None
    _, _, c, en, ar = min(pool, key=lambda x: (x[0], x[1]))
    return {"clip": c["clip"], "shot": c["shot"], "src_in": c["src_in"], "src_out": c["src_out"],
            "reason": f"{ev.get('role', 'turn')}: {en} (swap) | {ROLE_AR.get(ev.get('role'), '')}: {ar} (استبدال)"}


def main(argv=None) -> int:
    C.utf8_stdio()
    ap = argparse.ArgumentParser(prog="dragon_montage direct", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("direct")
    d.add_argument("--job", required=True)
    d.add_argument("--apply-review", action="store_true")
    sub.add_parser("apply-review").add_argument("--job", required=True)
    a = ap.parse_args(argv)
    job = Path(a.job)
    if a.cmd == "apply-review" or a.apply_review:
        edl = apply_review(job)
        h = edl["history"][-1]
        print(json.dumps({"edl": str(job / "edl.json"), "revision": edl["revision"], "events": len(edl["events"]),
                          "duration": edl["duration"], "applied": len(h["applied"]), "skipped": len(h["skipped"])}))
        return 0
    edl = direct(job)
    print(json.dumps({"edl": str(job / "edl.json"), "events": len(edl["events"]), "duration": edl["duration"],
                      "target": edl["meta"]["target_seconds"], "snapped_cuts": edl["meta"]["snapped_cuts"],
                      "concept": edl["meta"]["concept"]}, ensure_ascii=False))
    return 0
