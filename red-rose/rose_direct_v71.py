"""V71 directing mind: turn the owner's request into a director's treatment before anything is rendered.

Ladder: 1 genre and intent → 2 hook inside the first 1.5 s → 3 beat structure for the genre in whole frames →
4 shot grammar per beat (shot size never repeats back to back, the camera always moves, light serves the beat,
cuts carry motion; hard cuts only on place/time jumps) → 5 style per beat for a cocktail (by the layers the beat
needs) → 6 a shot list in `continuity check` format, checked immediately → 7 the director's critic questions.
Principles distilled from reviewed sources (storyboard continuity, cartoon shot grammar, minimal-reel "sentence
type → scene type") and written as original rules. Output is a DRAFT plan: the owner approves, then the agent
fills real states/motions, renders a sample and verifies the actual frames.
"""
from __future__ import annotations
import json, math, re
import rose_styles_v70 as styles
from rose_continuity_v69 import check as continuity_check

GENRES = {
    "dua": (("دعاء", "ذكر", "أذكار", "اذكار", "استغفار", "dua", "azkar"),
            [("opening", .15), ("supplication", .6), ("closing", .25)]),
    "song": (("أغنية", "اغنية", "كلمات", "غنا", "song", "lyrics"),
             [("intro", .1), ("verse", .35), ("chorus", .25), ("verse2", .15), ("outro", .15)]),
    "documentary": (("وثائقي", "تاريخ", "قضية", "لغز", "جريمة", "documentary", "history", "mystery"),
                    [("cold-open", .1), ("context", .2), ("evidence", .4), ("turn", .15), ("verdict", .15)]),
    "ad": (("إعلان", "اعلان", "منتج", "براند", "تطبيق", "ad", "product", "launch", "brand"),
           [("hook", .12), ("problem", .18), ("reveal", .3), ("proof", .25), ("cta", .15)]),
    "talking-head": (("متكلم", "مقطع كلام", "بتكلم", "بودكاست", "talking", "podcast"),
                     [("hook", .1), ("point", .6), ("close", .3)]),
    "explainer": (("اشرح", "شرح", "إزاي", "ازاي", "ليه", "معلومة", "علوم", "explain", "how", "why"),
                  [("hook", .1), ("question", .12), ("mechanism", .48), ("example", .15), ("takeaway", .15)]),
    "story": (("قصة", "حكاية", "حدوتة", "كرتون", "story", "cartoon", "tale"),
              [("hook", .08), ("setup", .14), ("escalation", .44), ("pivot", .16), ("payoff", .18)]),
}
# beat role → (purpose, emotion, preferred shot sizes, camera, light, sound, layers needed)
ROLE = {
    "hook": ("أغرب صورة أو جملة في القصة، من غير مقدمة", "فضول", ["close-up", "dynamic"], "fast push-in", "day", "whoosh + hit", ["characters", "type"]),
    "setup": ("مين وفين وإمتى بتفصيلة واحدة ملموسة", "توجّه", ["establishing", "wide"], "slow crane down", "day", "ambience", ["places"]),
    "escalation": ("كل بيت أكبر من اللي قبله، والفعل بيوصل للي بعده", "توتر بيعلى", ["medium", "two-shot", "insert", "over-the-shoulder"], "tracking", "golden", "rising music", ["characters", "places"]),
    "pivot": ("«بس لما…»: الآلية الحقيقية بتشبيه من الحياة", "دهشة", ["close-up", "low-angle"], "push-in with 3° roll", "night-blue", "music stops, low hit", ["characters"]),
    "payoff": ("التويست في آخر كلمة، والحركة الفيزيائية تخلص عليها", "رضا/ضحكة", ["wide", "aerial"], "pull-back reveal", "golden", "sting", ["places", "characters"]),
    "question": ("السؤال اللي المشاهد عايز إجابته", "فضول", ["medium", "close-up"], "slow push-in", "day", "tick", ["type"]),
    "mechanism": ("الإجابة خطوة خطوة، كل خطوة صورة", "فهم", ["insert", "medium", "macro", "wide"], "orbit / track along the parts", "day", "soft clicks", ["places", "maps", "type"]),
    "example": ("مثال من الحياة يثبّت الفكرة", "تعرّف", ["medium", "two-shot"], "drift", "golden", "ambience", ["characters"]),
    "takeaway": ("جملة واحدة يفتكرها", "وضوح", ["close-up"], "slow push-in", "golden", "resolve chord", ["type"]),
    "cold-open": ("الدليل الأغرب قبل أي شرح", "غموض", ["insert", "close-up"], "rack focus", "night-blue", "drone", ["places", "type"]),
    "context": ("المكان والزمن على الخريطة", "توجّه", ["establishing", "aerial"], "map dive", "day", "ambience", ["maps", "places"]),
    "evidence": ("دليل ورا دليل، كل واحد بيتربط بخيط", "شك", ["insert", "medium", "macro"], "track across the board", "night-blue", "pin hits, typewriter", ["type", "places", "maps"]),
    "turn": ("المعلومة اللي بتقلب القصة", "صدمة", ["close-up", "dynamic"], "whip-pan", "night-blue", "silence then hit", ["type", "characters"]),
    "verdict": ("الخلاصة وسؤال مفتوح", "تأمل", ["wide"], "slow pull-back", "golden", "low resolve", ["places", "type"]),
    "problem": ("الوجع اللي الجمهور عارفه", "إحباط", ["medium", "close-up"], "handheld sway", "day", "low hum", ["characters", "type"]),
    "reveal": ("الحل يظهر في حركة واحدة متصلة", "انبهار", ["dynamic", "wide"], "one continuous transform", "golden", "rise + impact", ["type", "camera"]),
    "proof": ("رقم أو استخدام حقيقي", "ثقة", ["insert", "medium"], "parallax slide", "day", "clicks", ["type"]),
    "cta": ("الفعل المطلوب واسم البراند", "قرار", ["close-up"], "settle into lock", "golden", "logo sting", ["type"]),
    "point": ("كل جملة: الكلمة الأهم كبيرة، ورجوع للوش بعد كل فكرة", "اقتناع", ["close-up", "medium", "insert"], "punch-in / drift", "day", "subtle whoosh", ["type", "captions"]),
    "close": ("جملة الختام والوش", "ثقة", ["close-up"], "slow push-in", "golden", "soft end", ["type"]),
    "opening": ("سكون ومكان يهيّأ للدعاء", "خشوع", ["wide", "establishing"], "slow drift", "dawn", "ambience only", ["places"]),
    "supplication": ("كل سطر دعاء بمشهده، والكلمة بتنور مع الصوت", "رجاء", ["medium", "wide", "insert"], "slow push", "dawn", "voice only", ["captions", "places"]),
    "closing": ("آمين ومصدر الدعاء", "سكينة", ["wide"], "slow pull-back", "golden", "voice fades", ["captions"]),
    "intro": ("أول نغمة وصورة المزاج", "مزاج", ["wide"], "slow drift", "golden", "song", ["places"]),
    "verse": ("كل سطر مشهد وكلمة بتطلع مع الغنا", "حكي", ["medium", "two-shot"], "tracking", "golden", "song", ["characters", "captions"]),
    "chorus": ("أقوى صورة وأكبر حركة على القرار", "ذروة", ["dynamic", "close-up"], "orbit", "golden", "song", ["characters", "type"]),
    "verse2": ("تطور العلاقة/الحكاية", "حنين", ["medium", "over-the-shoulder"], "drift", "night-blue", "song", ["characters"]),
    "outro": ("صورة الختام اللي بتفضل", "حنين", ["wide"], "pull-back", "golden", "song fades", ["places"]),
}
SHOT_SECONDS = 2.5  # vary the camera every 2-3 s


def genre_of(text):
    t = text.casefold()
    best, hits = "story", 0
    for g, (words, _) in GENRES.items():
        n = sum(1 for w in words if w in t)
        if n > hits:
            best, hits = g, n
    return best, hits > 0


def _alloc(weights, total):
    raw = [w * total for w in weights]
    out = [math.floor(x) for x in raw]
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - out[i], reverse=True)[: total - sum(out)]:
        out[i] += 1
    return out


def direct(request, seconds, fps=30, aspect="9:16", cocktail=None, genre=None, reg=None, lib=styles.LIB):
    if not isinstance(request, str) or not request.strip() or len(request) > 2000:
        raise ValueError("request text required")
    if not isinstance(seconds, (int, float)) or not 3 <= seconds <= 600:
        raise ValueError("seconds 3-600")
    if type(fps) is not int or not 12 <= fps <= 120:
        raise ValueError("fps 12-120")
    if genre is not None and genre not in GENRES:
        raise ValueError(f"genre must be one of {list(GENRES)}")
    detected, sure = genre_of(request)
    g = genre or detected
    reg = reg if reg is not None else styles.registry()
    by = {s["id"]: s for s in reg}
    picks = [x.strip() for x in cocktail.split("+")] if cocktail else []
    bad = [p for p in picks if p not in by]
    if bad:
        raise ValueError(f"unknown styles {bad}")
    total = int(round(seconds * fps))
    beats = GENRES[g][1]
    frames = _alloc([w for _, w in beats], total)
    hook_limit = int(1.5 * fps)
    shots, beat_rows, cursor, prev_size, uses = [], [], 0, None, {p: 0 for p in picks}
    for (role, _), n in zip(beats, frames):
        purpose, emotion, sizes, cam, light, sound, needs = ROLE[role]
        style = None
        if picks:  # best layer fit for this beat; ties go to the least used style so the cocktail mixes
            style = max(picks, key=lambda p: (len(set(needs) & set(by[p]["layers"])), -uses[p], -picks.index(p)))
            uses[style] += 1
        k = max(1, round(n / fps / SHOT_SECONDS))
        cuts = [cursor + round(n * i / k) for i in range(k + 1)]
        beat_rows.append({"role": role, "purpose": purpose, "emotion": emotion, "start_frame": cursor,
                          "end_frame": cursor + n, "seconds": round(n / fps, 2), "light": light, "sound": sound,
                          "style": style, "shots": k})
        for i in range(k):
            size = next((s for s in sizes[i % len(sizes):] + sizes if s != prev_size), sizes[0])
            if size == prev_size:  # every option repeats: pick a neutral alternative
                size = "medium" if prev_size != "medium" else "wide"
            prev_size = size
            first = not shots
            shot = {"id": f"{role}-{i + 1}", "start_frame": cuts[i], "end_frame": cuts[i + 1], "shot_type": size,
                    "camera_move": cam if i == 0 else f"{cam} (continues)",
                    "subject_motion": f"DRAFT: continuous motion for «{purpose}»",
                    "cut_in": "motion", "state": {}, "beat": role, "style": style, "light": light}
            if first:
                shot["director_note"] = f"hook must read within {hook_limit} frames ({hook_limit / fps:.1f} s), without sound"
            shots.append(shot)
        cursor += n
    report = continuity_check({"fps": fps, "duration_frames": total, "shots": shots})
    cocktail_plan = styles.cocktail("+".join(dict.fromkeys(b["style"] for b in beat_rows if b["style"])), seconds,
                                    fps, aspect, reg=reg, lib=lib) if picks else None
    return {
        "status": "draft_for_owner_review", "genre": g, "genre_detected": sure, "intent": request.strip()[:300],
        "fps": fps, "frames": total, "seconds": round(total / fps, 3), "aspect": aspect,
        "hook": {"within_frames": hook_limit, "rule": "frame 0 already shows the hook image; no logo, no title card first"},
        "beats": beat_rows, "shot_list": shots, "continuity": {k: report[k] for k in ("status", "errors", "warnings", "issues")},
        "cocktail": cocktail_plan,
        "unused_styles": [p for p in picks if not uses[p]],
        "director_questions": [
            "لو اتشاف من غير صوت: الهوك مفهوم في أول 1.5 ثانية؟",
            "كل بيت فيه حركة حقيقية طول مدته، ولا فيه لقطة واقفة زي السلايد شو؟",
            "حجم اللقطة اتغير بين كل لقطتين؟ والكاميرا بتتحرك كل 2-3 ثواني؟",
            "كل فعل بدأ في لقطة بيوصل لنتيجة في اللي بعدها؟ والحاجات (لبس/مكان/أدوات) ثابتة إلا بسبب؟",
            "التويست أو الذروة بيخلص على آخر كلمة؟ والصوت بيخدم البيت (سكوت قبل الضربة)؟",
            "كل جملة في الكلام اتصورت حرفيًا ولا بنوصف اللي المشاهد شايفه أصلًا؟"],
        "next": ["owner approves or edits this treatment", "fill real state/subject_motion per shot, rerun `continuity check`",
                 "`styles show` each style, read its doc, render a 3-second sample", "full render → media-contract verify → visual review"],
        "rendered": False, "execution_allowed": False}


def handle(a):
    try:
        print(json.dumps(direct(a.request, a.seconds, a.fps, a.aspect, a.styles, a.genre), ensure_ascii=False,
                         indent=1 if a.pretty else None))
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)[:300]}, ensure_ascii=False))
        return 1


def register(sub):
    p = sub.add_parser("direct", help="V71 directing mind: treatment, beats, shot grammar, cocktail per beat (draft)")
    p.add_argument("request")
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--aspect", default="9:16")
    p.add_argument("--styles", help="cocktail ids joined by +")
    p.add_argument("--genre", choices=list(GENRES))
    p.add_argument("--pretty", action="store_true")
    p.set_defaults(ext_func=handle)
