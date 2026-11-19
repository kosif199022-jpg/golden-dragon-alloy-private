"""Stations 2+3 «يفهم المطلوب» and «يفكر بإبداع»: the thinking brain.

brief:    analysis facts (speech coverage, faces, motion, usable seconds, language) + the owner's words -> brief.json,
          with the evidence behind every inferred field.
concepts: three concepts that differ in ARC (and mostly rhythm), each with a hook from the strongest real sentences
          (hooks.score_hook) or a hooks_ar.json formula; one framework per Dragon Mind stage from mind_registry.json,
          its output filled from the job's own data; a weighted decision matrix with ±1-weight sensitivity; a
          pre-mortem; and the five-voice council prompt pack (council_prompt.md). No model API is called.
Deterministic; frameworks are "consulted" (scored) or "applied" (filled), never "executed".
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import common as C
from .hooks import score_hook as _score

STAGES = ["frame", "explore", "decide", "build", "verify", "learn"]
AR_RE = re.compile(r"[؀-ۿ]")
LATIN_RE = re.compile(r"[A-Za-z]")
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
DEFAULT_HOOK_ROLES = ("hook", "problem", "question", "cold-open", "tease")


def editor_mind() -> dict:
    return C.data("editor_mind.json")


def hook_roles() -> set:
    """Roles that may open a cut and count as the hook (shared by think, direct and review)."""
    return set((editor_mind().get("hook_roles") or {}).get("roles") or DEFAULT_HOOK_ROLES)


def ensure_hook_opening(arc: dict) -> dict:
    beats = list(arc.get("beats") or [])
    if beats and beats[0].get("role") in hook_roles():
        return arc
    return {**arc, "beats": [{"id": "hook", "role": "hook", "share": 0.08,
                              "purpose_ar": "أقوى جملة أو لقطة في أول 3 ثواني قبل ما القوس يبدأ"}] + beats}


def fold(text: str) -> str:
    t = (text or "").lower().translate(DIGITS)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه")):
        t = t.replace(a, b)
    return t


def hits(text: str, words: list) -> int:
    t = fold(text)
    return sum(1 for w in words if fold(w) in t)


PREFIX = r"(?:و|ف|ب|ل|ك|ال|بال|لل|وال|وب|ول)?"


def word_hits(text: str, words: list) -> int:
    """Whole-word matches (an Arabic one-letter prefix or ال is allowed): «فيديو» never matches «فيد»."""
    t = fold(text)
    n = 0
    for w in words:
        fw = re.escape(fold(w))
        if re.search(rf"(?<!\w){PREFIX}{fw}(?!\w)", t):
            n += 1
    return n


NEGATORS = ("مش", "ليس", "لا", "بدون", "من غير", "مافيش", "مفيش", "بلاش", "not", "no", "without")


def split_negated(text: str, n: int = 3) -> tuple:
    """(text with every word within n words after a negator removed, [the negated phrases])."""
    toks = (text or "").split()
    keep, neg, i = [], [], 0
    while i < len(toks):
        two = " ".join(toks[i:i + 2])
        step = 2 if fold(two) in {fold(x) for x in NEGATORS if " " in x} else (
            1 if fold(toks[i]) in {fold(x) for x in NEGATORS if " " not in x} else 0)
        if step:
            phrase = toks[i + step:i + step + n]
            if phrase:
                neg.append(" ".join(phrase).strip("،,."))
            i += step + len(phrase)
            continue
        keep.append(toks[i])
        i += 1
    return " ".join(keep), neg


def score_hook(text: str) -> dict:
    r = _score(text)
    return {"score": r["score"], "verdict": r["verdict"], "weakest": r["weakest"], "engine": "reel_tools.score_hook"}


def _q(s: str, n: int = 70) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# ------------------------------------------------------------------------------------------- analysis facts
def load_analysis(job: Path):
    try:
        return C.read(job, "analysis"), None
    except FileNotFoundError:
        return None, "مفيش analysis.json: البريف اتبنى من كلام صاحب الطلب بس"
    except (C.ContractError, json.JSONDecodeError) as e:
        return None, f"analysis.json مش مطابق للعقد ({e}): اتجاهلناه"


def sentences(analysis) -> list:
    """Transcript words -> sentences: break on end punctuation, a gap > 0.6 s, or 16 words; each hook-scored."""
    out = []
    for clip in (analysis or {}).get("clips", []):
        cur, words = [], clip.get("words") or []
        for i, w in enumerate(words):
            cur.append(w)
            nxt = words[i + 1] if i + 1 < len(words) else None
            if (re.search(r"[.!?؟،]$", str(w.get("w", ""))) or nxt is None
                    or float(nxt.get("start", 0)) - float(w.get("end", 0)) > 0.6 or len(cur) >= 16):
                text = " ".join(str(x.get("w", "")) for x in cur).strip()
                if text:
                    conf = [float(x.get("conf", 1.0)) for x in cur]
                    out.append({"clip": clip.get("id"), "start": round(float(cur[0].get("start", 0)), 3),
                                "end": round(float(cur[-1].get("end", 0)), 3), "text": text, "words": len(cur),
                                "conf": round(sum(conf) / len(conf), 3)})
                cur = []
    for s in out:
        h = score_hook(s["text"])
        s["hook_score"], s["hook_verdict"] = h["score"], h["verdict"]
    return out


def facts(analysis) -> dict:
    f = {"clips": 0, "duration": 0.0, "speech_s": 0.0, "speech_coverage": 0.0, "shots": 0, "faces_ratio": 0.0,
         "group_ratio": 0.0, "max_faces": 0, "motion_mean": 0.0, "quality_mean": 0.0, "usable_s": 0.0,
         "shaky": [], "best_shot": None, "best_motion_shot": None, "music_beats": 0, "words": 0,
         "word_lang": None, "low_conf": 0.0}
    if not analysis:
        return f
    shots, words = [], []
    for clip in analysis.get("clips", []):
        f["clips"] += 1
        f["duration"] += float(clip.get("duration") or 0)
        shots += clip.get("shots") or []
        words += clip.get("words") or []
    f["shots"], f["words"] = len(shots), len(words)
    f["speech_s"] = round(sum(max(0.0, float(w.get("end", 0)) - float(w.get("start", 0))) for w in words), 3)
    f["speech_coverage"] = round(f["speech_s"] / f["duration"], 3) if f["duration"] else 0.0
    if words:
        txt = " ".join(str(w.get("w", "")) for w in words)
        f["word_lang"] = "ar-eg" if len(AR_RE.findall(txt)) >= len(LATIN_RE.findall(txt)) else "en"
        f["low_conf"] = round(sum(1 for w in words if float(w.get("conf", 1)) < 0.6) / len(words), 3)
    if shots:
        q = lambda s: float((s.get("quality") or {}).get("score") or 0.5)  # noqa: E731
        shake = lambda s: float((s.get("quality") or {}).get("shake") or 0)  # noqa: E731
        n = len(shots)
        f["faces_ratio"] = round(sum(1 for s in shots if (s.get("faces") or 0) >= 1) / n, 3)
        f["group_ratio"] = round(sum(1 for s in shots if (s.get("faces") or 0) >= 2) / n, 3)
        f["max_faces"] = max(int(s.get("faces") or 0) for s in shots)
        f["motion_mean"] = round(sum(float(s.get("motion_energy") or 0) for s in shots) / n, 3)
        f["quality_mean"] = round(sum(q(s) for s in shots) / n, 3)
        f["usable_s"] = round(sum(float(s["end"]) - float(s["start"]) for s in shots if q(s) >= 0.45 and shake(s) < 0.6), 3)
        f["shaky"] = [s["id"] for s in shots if shake(s) >= 0.6][:8]
        f["best_shot"] = max(shots, key=lambda s: (q(s), s["id"]))["id"]
        f["best_motion_shot"] = max(shots, key=lambda s: (float(s.get("motion_energy") or 0) * q(s), s["id"]))["id"]
    else:
        f["usable_s"] = round(f["duration"], 3)
    f["music_beats"] = len((analysis.get("music") or {}).get("beats") or [])
    f["duration"] = round(f["duration"], 3)
    return f


# ------------------------------------------------------------------------------------------- brief inference
TRIGGER_WORDS = ["التنين الاسود", "التنين الأسود", "تنين", "مونتاج", "منتج", "اعمل", "اعملي", "عايز", "عاوز",
                 "ثانيه", "ثانية", "ثواني", "دقيقه", "دقيقة", "فيديو", "الفيديو", "ده", "دي", "black dragon", "montage"]
FILLER_WORDS = {"التنين", "الاسود", "عايزه", "عايزة", "عاوزه", "عاوزة", "عايزين", "بإحساس", "باحساس", "احساس", "يكون",
                "يبقى", "حاجه", "حاجة", "بس", "كده", "من", "غير", "بدون"}


def topic_of(task: str, em: dict) -> str:
    t = re.sub(r"[«»\"'،,.:؛!؟?()\-]", " ", task or "")
    t = re.sub(r"\d+", " ", t.translate(DIGITS))
    drop = {fold(w) for w in TRIGGER_WORDS + [w for ws in em["platform_words"].values() for w in ws]}
    joined = " ".join(w for w in t.split() if fold(w) not in drop and len(w) > 1)
    for ph in ("التنين الاسود", "التنين الأسود"):
        joined = joined.replace(ph, " ")
    feel = {fold(w) for ws in em["feeling_words"].values() for w in ws}
    drop2 = {fold(x) for x in FILLER_WORDS}
    words = [w for w in joined.split() if not (fold(w) in drop2 or fold(w) in feel or fold(w).lstrip("ب") in feel)]
    neg = re.search(r"(?:من غير|بدون|مش عايز|بلاش)", task or "")
    if neg:  # what the owner wants out is not the topic
        tail = {fold(x) for x in re.sub(r"[،,.]", " ", (task or "")[neg.end():]).split()[:4]}
        words = [w for w in words if fold(w) not in tail]
    if words and words[0].startswith("ل") and len(words[0]) >= 5 and not words[0].startswith(("لو", "لا", "لي")):
        words[0] = words[0][1:]      # «مونتاج لرحلتي» -> رحلتي
    return " ".join(words[:6]) or "الفيديو ده"


def best_by_hits(task: str, table: dict, key=lambda v: v) -> tuple:
    best, n = None, 0
    for k, v in table.items():
        h = hits(task, key(v))
        if h > n:
            best, n = k, h
    return best, n


def pick_content_type(task: str, f: dict, em: dict) -> tuple:
    task = split_negated(task)[0]          # «مش بأسلوب شرح» never types the job as talking-head
    best, n = best_by_hits(task, em["content_types"], lambda s: s["words"])
    if best:
        return best, f"من كلام الطلب ({n} كلمة دالة)"
    if not f["clips"]:
        return "montage", "افتراض: مفيش تحليل ولا كلمة دالة"
    sc, gr = f["speech_coverage"], f["group_ratio"]
    if sc >= 0.35:
        if gr >= 0.3 and f["clips"] >= 2:
            return "interview", f"كلام بيغطي {sc:.0%} ووشين أو أكتر في {gr:.0%} من اللقطات"
        return "talking-head", f"كلام بيغطي {sc:.0%} من المدة، ووش ظاهر في {f['faces_ratio']:.0%} من اللقطات"
    if sc < 0.15 and gr >= 0.4:
        return "event", f"كلام قليل ({sc:.0%}) وناس كتير في {gr:.0%} من اللقطات"
    if sc >= 0.15:
        return "talking-head", f"فيه كلام ({sc:.0%}) بس مش غالب: هنعامله كلام فوق لقطات"
    return "montage", f"مفيش كلام تقريبًا ({sc:.0%}): مونتاج لقطات"


def pick_seconds(task: str, arg, plat: dict, f: dict) -> tuple:
    if arg:
        sec, why = float(arg), ["من --seconds"]
    else:
        m = re.search(r"(\d+)\s*(ث|ثانيه|ثانية|ثواني|s\b|sec|second)", (task or "").translate(DIGITS))
        mm = re.search(r"(\d+)\s*(دقيقه|دقيقة|دقايق|min)", (task or "").translate(DIGITS))
        if m:
            sec, why = float(m.group(1)), ["من كلام الطلب"]
        elif mm:
            sec, why = float(mm.group(1)) * 60, ["من كلام الطلب"]
        else:
            sec, why = float(plat["default_seconds"]), [f"افتراض المنصة ({plat['default_seconds']} ث)"]
    lo, hi = plat["seconds"]
    if not arg and not (lo <= sec <= hi):
        sec = min(max(sec, lo), hi)
        why.append(f"اتظبط على مدى المنصة {lo}–{hi}")
    if arg:                 # the owner's number is never shrunk: the plan says how short the footage is instead
        if f["usable_s"] and sec > f["usable_s"]:
            why.append(f"تحذير: المادة الصالحة {f['usable_s']:.1f} ث بس، ناقص {sec - f['usable_s']:.1f} ث (آخر لقطة هتتمد)")
        return round(sec, 1), "؛ ".join(why)
    if f["usable_s"] and sec > f["usable_s"] * 0.9:
        sec = max(5.0, round(f["usable_s"] * 0.9))
        why.append(f"المادة الصالحة {f['usable_s']:.1f} ث بس، فالمدة نزلت لـ {sec:.0f}")
    return round(sec, 1), "؛ ".join(why)


def avoid_from_task(task: str) -> list:
    out = [m.group(1).strip() for m in
           re.finditer(r"(?:من غير|بدون|مش عايز|مش عاوز|ممنوع|بلاش|without|no)\s+([^،,.\n]{2,40})", task or "")]
    for ph in split_negated(task)[1]:
        if not any(fold(ph) in fold(o) or fold(o) in fold(ph) for o in out):
            out.append(ph)
    return out


# ------------------------------------------------------------------------------------------- frameworks
def _fillers(ctx: dict) -> dict:
    """Deterministic output of each framework the brain knows how to apply, from this job's own facts."""
    b, f, c = ctx["brief"], ctx["facts"], ctx.get("concept") or {}
    best, arc_ar, secs = ctx.get("best_sentence"), c.get("arc_name_ar", ""), b["target_seconds"]
    hook = (c.get("hook") or {}).get("text") or (best or {}).get("text") or ""
    beats = c.get("beats") or []
    return {
        "first principles": lambda: (
            f"حقايق: {f['clips']} كليب، {f['duration']:.0f} ث خام، {f['usable_s']:.0f} ث صالحة، كلام {f['speech_coverage']:.0%}"
            f"{', موسيقى بـ ' + str(f['music_beats']) + ' بيت' if f['music_beats'] else ''}. أعراف مش حقايق: "
            f"«لازم مقدمة»، «لازم كل اللقطات»، «لازم موسيقى ترند». نبني من الحقايق بس: {secs:.0f} ث من أحسن المادة."),
        "problem reframing": lambda: (
            f"الطلب مش «اعمل مونتاج»؛ السؤال الحقيقي: إزاي مشاهد {b['platform']} يفضل لحد الثانية {secs:.0f} "
            f"ويحس إنه {ctx['feeling_ar']}؟"),
        "inversion": lambda: (
            "إزاي نبوّظه؟ نبدأ بمقدمة، نسيب صمت، نكرر نفس الكادر، ترجمة غلط، نهاية مفيهاش حاجة. "
            "يبقى الخطة: هوك من أول فريم، قص الصمت، تنويع الأحجام، مراجعة الترجمة، ونهاية بتلف على الهوك."),
        "golden circle": lambda: (
            f"ليه: {ctx['one_truth']} ← إزاي: {b['content_type']} بإيقاع {c.get('rhythm') or ctx.get('default_rhythm', '…')} ← إيه: "
            f"{secs:.0f} ث {b['aspect']}."),
        "tfs framing": lambda: (
            f"نفس المادة تتقدم بإطارين: مكسب («شوف اللي هتكسبه») أو خسارة («اللي بيفوتك»). "
            f"الهوك الحالي «{_q(hook, 50)}» إطاره {'خسارة' if re.search('خسر|ضاع|غلط|متعملش|بيفوت', hook) else 'مكسب'}."),
        "tfs wysiati": lambda: (
            f"المشاهد مش شايف غير اللي على الشاشة: مش عارف مين ولا فين. لازم في أول {min(5, secs):.0f} ث "
            f"معلومة واحدة تعرّفه (كارت ≤ 6 كلمات)."),
        "jobs be done": lambda: (
            f"المشاهد «بيوظّف» الفيديو ده عشان {'يتعلم حاجة في دقيقة' if b['content_type'] in ('talking-head', 'interview') else 'يحس إحساس ' + ctx['feeling_ar'] + ' من غير مجهود'}؛ "
            f"أي لقطة مش بتخدم الشغلانة دي تتشال."),
        "beautiful question": lambda: (
            f"ماذا لو بدأنا من {'آخر جملة' if best else 'أقوى لقطة'} بدل الأولى؟ وإزاي نخلي الـ{secs:.0f} ث "
            f"سؤال واحد بيتجاوب في الآخر؟"),
        "provocation po": lambda: (
            f"Po: الفيديو يمشي بالعكس. اللي يطلع منه: نبدأ بلقطة من «{beats[-1]['id'] if beats else 'الذروة'}» ثانية واحدة "
            f"وبعدين نرجع نحكي إزاي وصلنا."),
        "scamper": lambda: (
            "S بدّل الترتيب الزمني · C ادمج لقطتين في سبليت · A استعير إيقاع تريلر · M كبّر لحظة واحدة سلو موشن · "
            "P استخدم الصمت كهوك · E اشيل المقدمة · R اعكس: النهاية الأول."),
        "tfs norms surprise causes": lambda: (
            f"المشاهد متوقع {ctx['ct_ar']} عادي؛ المفاجأة اللي تكسر التوقع: "
            f"«{_q(hook, 50) or 'أول فريم من نص الحدث'}» في أول 3 ث."),
        "lateral thinking": lambda: (
            "مدخل عشوائي: «مراية». الفكرة: لقطتين متقابلتين (قبل/بعد، هو/هي، فاضي/مليان) بنفس الكادر."),
        "morphological analysis": lambda: (
            f"المحاور: قوس × إيقاع × هوك. التوليفة دي: {c.get('arc_id', '…')} × {c.get('rhythm', '…')} × "
            f"{(c.get('hook') or {}).get('formula', '…')}."),
        "medici intersection": lambda: (
            f"نخلط {ctx['ct_ar']} مع لغة {'التريلر' if b['energy'] >= 0.6 else 'الفيلم الوثائقي'}: نفس المادة بقواعد مجال تاني."),
        "six thinking hats": lambda: (
            f"أبيض: {f['usable_s']:.0f} ث صالحة · أحمر: الإحساس {ctx['feeling_ar']} · أسود: الهوك ممكن ميوصلش · "
            f"أصفر: {'فيه كلام حقيقي نبني عليه' if best else 'المادة البصرية تكفي'} · أخضر: نهاية لوب · أزرق: نختار بالمصفوفة."),
        "pugh matrix": lambda: "المصفوفة تحت في decision.matrix: كل فكرة قصاد المعايير بالأوزان، والفايز اتختبر بتغيير ±1 في كل وزن.",
        "outside view": lambda: (
            f"المرجع: ريلز {b['platform']} الشغالة بين 15 و45 ث والهوك في أول 3 ث. هدفنا {secs:.0f} ث "
            f"{'جوه' if 15 <= secs <= 45 else 'برا'} المدى ده."),
        "tfs loss aversion": lambda: (
            "الخسارة أتقل من المكسب: الهوك يقول اللي هيضيع على المشاهد لو قفل الفيديو، مش بس اللي هيكسبه."),
        "tfs affect heuristic": lambda: (
            f"الحكم هيتبني على الإحساس قبل المعلومة: أول 3 ث لازم توصّل «{ctx['feeling_ar']}» بالصورة والصوت."),
        "one way two way doors": lambda: "اختيار الفكرة باب بيتفتح في الاتجاهين (نعيد الرندر)، النشر بس هو الباب اللي مبيرجعش: يقف عند صاحب الطلب.",
        "essentialism": lambda: f"نختار الأقل: {len(beats) or 5} بيتس بس، وكل لقطة مش بتزود معلومة جديدة تتشال.",
        "made stick success": lambda: (
            f"بسيط: فكرة واحدة «{_q(re.sub('[«»]', '', ctx['one_truth']).split(':')[0], 45)}» · غير متوقع: الهوك · ملموس: "
            f"{'رقم/اسم في الهوك' if re.search(r'[0-9٠-٩]', hook) else 'لقطة تتلمس بدل الكلام'} · "
            f"مصداقية: لقطة حقيقية من المادة · عاطفي: {ctx['feeling_ar']} · قصة: {arc_ar or 'القوس المختار'}."),
        "resonate sparkline": lambda: (
            "نبدّل بين «اللي موجود» و«اللي ممكن يكون» كل بيت: "
            + " ↔ ".join(x["id"] for x in beats[:5]) + "، والنهاية على «اللي ممكن يكون»."),
        "timed emotional arc platform tone": lambda: (
            "قوس الإحساس بالثواني: " + " · ".join(f"{x['id']} {x['start']:.0f}–{x['end']:.0f}ث" for x in beats)
            + f"؛ النبرة: {'مباشرة وعامية' if b['platform'] in ('reel', 'story') else 'أهدى وأعمق'}."),
        "storybrand": lambda: (
            f"البطل هو المشاهد مش صاحب الفيديو؛ المشكلة في أول بيت، المرشد يظهر في «{beats[1]['id'] if len(beats) > 1 else 'التمهيد'}»، "
            f"والخطة في «{beats[-2]['id'] if len(beats) > 1 else 'الحصاد'}»."),
        "hook model": lambda: (
            f"المحفز: أول فريم · الفعل: يكمّل 3 ث · المكافأة المتغيرة: {beats[2]['id'] if len(beats) > 2 else 'اللفة'} · "
            "الاستثمار: لوب في الآخر يرجعه للأول."),
        "theory mind reader model": lambda: (
            "المشاهد بيعمل سكرول وصوته مقفول غالبًا: الهوك لازم يتفهم من الصورة والكارت لوحدهم."),
        "look serves story inside budget": lambda: (
            f"اللوك يخدم «{arc_ar or 'القوس'}»: {ctx['grade_hint']}؛ مفيش لوك يتقرر قبل ما القصة تتقفل."),
        "via negativa": lambda: "نحسّن بالحذف: نشيل المقدمة، الصمت > 0.4 ث، التكرار، وأي لقطة جودتها أقل من 0.45.",
        "pre mortem": lambda: "شوف premortem تحت: خمس قصص فشل بأسباب مختلفة، كل واحدة ليها علامة بدري وإصلاح.",
        "red team": lambda: (
            f"أقوى 3 هجمات: (1) الهوك «{_q(hook, 40)}» ممكن يتقرا عام (2) "
            f"{'الإيقاع على البيت من غير موسيقى' if c.get('rhythm') == 'on-beat' and not f['music_beats'] else 'المدة ممكن تطوّل'} "
            "(3) النهاية ممكن تقع. الإصلاح: مراجعة يتفرج وينقد بتشيك على التلاتة."),
        "cognitive bias checklist": lambda: (
            "انحياز التأكيد: إحنا حبينا الفكرة دي، فهنقيسها بنفس المعايير زي التانيين · الهالة: لقطة حلوة متخليش الجملة الضعيفة تعدي."),
        "mental simulation chosen option": lambda: (
            "محاكاة: " + " ← ".join(f"{x['id']} ({x['end'] - x['start']:.0f}ث)" for x in beats)
            + "؛ لو أي بيت أقل من 1.5 ث أو أطول من 8 ث يبقى فيه مشكلة."),
        "tfs two selves": lambda: (
            f"المشاهد هيفتكر الذروة والنهاية بس: الذروة في «{max(beats, key=lambda x: x['end'] - x['start'])['id'] if beats else '…'}» "
            f"والنهاية في «{beats[-1]['id'] if beats else '…'}»، فدول أحسن لقطتين عندنا."),
        "after action review": lambda: "بعد الرندر: كان المفروض إيه؟ حصل إيه؟ ليه الفرق؟ هنعمل إيه المرة الجاية؟ (review.json).",
    }


FILLED = set(_fillers({"brief": {"target_seconds": 30}, "facts": {}, "concept": None}))


def apply_frameworks(stage: str, want: dict, task: str, n: int, ctx: dict, avoid=()) -> tuple:
    """Score every registry framework of one stage that the brain can fill; apply the top n."""
    pool = [e for e in C.data("mind_registry.json")["frameworks"] if e["stage"] == stage]
    rows = []
    for e in pool:
        if e["key"] not in FILLED:
            continue
        s = sum(w * e["video"]["tags"].get(t, 0) for t, w in want.items())
        s += 0.08 * min(3, hits(task, e.get("triggers") or []))
        s += 0.05 * len({r["source"] for r in e["sources"]})        # agreed on by several books = sturdier
        s -= 0.35 if e["key"] in avoid else 0
        rows.append((round(s, 4), e["key"], e))
    rows.sort(key=lambda r: (-r[0], r[1]))
    fill = _fillers(ctx)
    return [{"id": e["id"], "key": e["key"], "name_ar": e["name_ar"], "stage": stage,
             "source": "+".join(sorted({r["source"] for r in e["sources"]})),
             "sources": [f"{r['file']}#{r['id']}" for r in e["sources"]], "output": fill[e["key"]]()}
            for _, _, e in rows[:n]], len(pool)


# ------------------------------------------------------------------------------------------- brief
AUDIENCE = {"reel": "ناس بتعمل سكرول على الموبايل، صوتها مقفول غالبًا، بتقرر في 3 ثواني",
            "story": "متابعين بيعدّوا الستوري بسرعة، 15 ثانية بالكتير",
            "youtube": "مشاهد قاعد قدام الشاشة ومستعد يدي وقت لو اتشد",
            "square": "فيد إنستجرام/فيسبوك، صوت مقفول", "landscape": "مشاهد على شاشة عرضية"}


def build_brief(job, task: str, platform=None, seconds=None) -> dict:
    em = editor_mind()
    analysis, note = load_analysis(Path(job))
    f, sents = facts(analysis), sentences(analysis)
    if platform:
        plat_id, plat_why = platform, "من --platform"
    else:
        plat_id = next((p for p, ws in em["platform_words"].items() if word_hits(task, ws)), None)
        plat_id, plat_why = (plat_id, "من كلام الطلب") if plat_id else ("reel", "افتراض: ريل")
    if plat_id not in em["platforms"]:
        plat_id, plat_why = "reel", f"منصة مش معروفة ({platform}): رجعنا لريل"
    plat = em["platforms"][plat_id]
    ct, ct_why = pick_content_type(task, f, em)
    feel = best_by_hits(task, em["feeling_words"])[0]
    feel, feel_why = (feel, "من كلام الطلب") if feel else (em["content_types"][ct]["default_feeling"],
                                                           f"افتراض نوع المحتوى ({ct})")
    fe = em["feelings"][feel]
    sec, sec_why = pick_seconds(task, seconds, plat, f)
    energy = round(0.7 * fe["energy"] + 0.3 * f["motion_mean"], 2) if f["shots"] else fe["energy"]
    lang = f["word_lang"] or ("ar-eg" if AR_RE.search(task or "") or not task else "en")
    topic = topic_of(task, em)
    best = max(sents, key=lambda s: (s["hook_score"], -s["start"]), default=None)
    one_truth = (f"«{_q(best['text'], 90)}»: دي الجملة اللي الفيديو كله يخدمها" if best
                 else f"{topic} في {sec:.0f} ثانية بإحساس {fe['name_ar']}")
    spec = em["content_types"][ct]
    must = list(spec["keep_ar"])
    if best:
        must.insert(0, f"الجملة «{_q(best['text'], 80)}» ({best['clip']} {best['start']:.2f}–{best['end']:.2f})")
    if f["best_shot"]:
        must.append(f"أحسن لقطة جودة: {f['best_shot']}")
    avoid = avoid_from_task(task) + list(spec["avoid_ar"]) + (["لقطات مهزوزة: " + "، ".join(f["shaky"])] if f["shaky"] else [])
    brief = C.new("brief", task=task, one_truth=one_truth, audience=AUDIENCE[plat_id], platform=plat_id,
                  aspect=plat["aspect"], target_seconds=sec, feeling=feel, energy=energy, language=lang,
                  content_type=ct, must_keep=must, avoid=avoid, frameworks=[])
    brief["requirements"] = [task] if task else []          # PROTOCOL «الطلبات بالحرف»: the request word for word
    brief["owner_seconds"] = float(seconds) if seconds else None
    brief["footage_seconds"] = round(f["usable_s"], 1) if f["usable_s"] else None
    ctx = {"brief": brief, "facts": f, "best_sentence": best, "one_truth": one_truth, "feeling_ar": fe["name_ar"],
           "ct_ar": spec["name_ar"], "grade_hint": fe["grade_hint"], "concept": None, "default_rhythm": fe["rhythm"]}
    brief["frameworks"], considered = apply_frameworks("frame", {"story": 1.0, "hook": 0.7, "critique": 0.4}, task, 3, ctx)
    brief["topic"] = topic
    brief["evidence"] = {"platform": plat_why, "content_type": ct_why, "feeling": feel_why, "target_seconds": sec_why,
                         "language": "من التفريغ" if f["word_lang"] else "من لغة الطلب",
                         "analysis": note or f"analysis.json: {f['clips']} كليب، {f['shots']} لقطة، {f['words']} كلمة"}
    brief["facts"] = f
    brief["hook_candidates"] = [{k: s[k] for k in ("clip", "start", "end", "text", "hook_score", "hook_verdict", "conf")}
                                for s in sorted(sents, key=lambda s: (-s["hook_score"], s["start"]))[:5]]
    brief["consulted"] = {"frame_stage_frameworks_read": considered, "applied": len(brief["frameworks"]),
                          "editor_mind": "data/editor_mind.json"}
    return brief


# ------------------------------------------------------------------------------------------- concepts
CONCEPT_WANT = {"classic-5": {"story": 1.0, "emotion": 0.6}, "viral-editorial": {"hook": 1.0, "contrast": 0.9},
                "problem-agitate-solve": {"hook": 0.8, "emotion": 0.7, "contrast": 0.4},
                "journey": {"story": 1.0, "emotion": 0.9, "rhythm": 0.4}, "countdown": {"hook": 0.8, "rhythm": 0.8},
                "before-after": {"contrast": 1.0, "rhythm": 0.5}}
RHYTHM_WANT = {"on-beat": {"rhythm": 0.6}, "speech-led": {"hook": 0.3, "story": 0.3}, "slow-burn": {"emotion": 0.5}}
STAGE_TILT = {"verify": {"critique": 1.0}, "learn": {"emotion": 0.4, "critique": 0.6}, "decide": {"critique": 0.4}}
TOPIC_SLOTS = ("موضوع", "مهمة", "الحاجة", "حاجة", "جملة", "الطريقة الجديدة", "الجديدة")


def choose_combos(ct: str, f: dict, feel_rhythm: str, em: dict) -> list:
    speech, out, used = f["words"] > 0, [], set()
    for arc, rhythm in (tuple(x) for x in em["content_types"][ct]["pool"]):
        if arc in used:
            continue
        if rhythm == "speech-led" and not speech:
            rhythm = "slow-burn" if all(r != "slow-burn" for _, r in out) else "on-beat"
        out.append((arc, rhythm))
        used.add(arc)
        if len(out) == 3:
            break
    for arc in em["arcs"]:          # top up when a content type lists fewer than three arcs
        if len(out) == 3:
            break
        if arc not in used:
            out.append((arc, feel_rhythm))
            used.add(arc)
    rhythms = {r for _, r in out}
    if len(rhythms) < 2:            # the three must not share one rhythm
        out[-1] = (out[-1][0], next(r for r in ("slow-burn", "on-beat", "speech-led")
                                    if r not in rhythms and (r != "speech-led" or speech)))
    if feel_rhythm not in {r for _, r in out} and (feel_rhythm != "speech-led" or speech):
        out[-1] = (out[-1][0], feel_rhythm)
        if len({r for _, r in out}) < 2:
            out[-2] = (out[-2][0], next(r for r in ("on-beat", "slow-burn") if r != feel_rhythm))
    return out


def beats_for(arc: dict, target: float, hook_first: float) -> list:
    """Seconds per beat from the arc shares; an opening hook is capped at the hook window, the rest stretch."""
    durs = [target * b["share"] for b in arc["beats"]]
    if arc["beats"][0]["role"] == "hook" and durs[0] > hook_first and len(durs) > 1:
        extra, durs[0] = durs[0] - hook_first, hook_first
        rest = sum(durs[1:])
        durs = [durs[0]] + [d + extra * d / rest for d in durs[1:]]
    out, t = [], 0.0
    for b, d in zip(arc["beats"], durs):
        out.append({"id": b["id"], "role": b["role"], "start": round(t, 2), "end": round(t + d, 2), "purpose": b["purpose_ar"]})
        t += d
    if out:
        out[-1]["end"] = round(target, 2)
    return out


def formula_hook(fid: int, topic: str, hooks: dict) -> tuple:
    """Fill a hooks_ar formula: the topic only goes into a "subject" slot; other slots stay {{slot}} for the owner."""
    h = next((x for x in hooks.get("hooks", []) if x["id"] == fid), None)
    if not h:
        return f"{topic}: اتفرج للآخر.", f"hooks_ar#{fid}", False
    text, placed = h["template"], False
    for slot in re.findall(r"\{([^}]+)\}", h["template"]):
        if not placed and any(w in slot for w in TOPIC_SLOTS):
            text, placed = text.replace("{" + slot + "}", topic, 1), True
        else:
            text = text.replace("{" + slot + "}", "{{" + slot + "}}", 1)
    return text, f"hooks_ar#{fid} {h['name']}", "{{" in text


def make_hook(arc_id: str, idx: int, sents: list, used: set, topic: str, em: dict, hooks: dict, f: dict) -> dict:
    formulas = em["hook_rules"]["arc_formulas"].get(arc_id, [3])
    window = em["hook_rules"]["window_s"]
    ranked = [s for s in sorted(sents, key=lambda s: (-s["hook_score"], s["start"])) if s["text"] not in used]
    pool = [s for s in ranked if s["end"] - s["start"] <= window * 2.2] or ranked
    if pool:   # later concepts look further down the list so the three hooks differ in substance
        pick = pool[min(idx, len(pool) - 1)] if arc_id != "journey" else max(pool, key=lambda s: (s["start"], s["text"]))
        used.add(pick["text"])
        sc = score_hook(pick["text"])
        return {"text": pick["text"], "formula": f"transcript:{pick['clip']}@{pick['start']:.2f}-{pick['end']:.2f}",
                "closest_formula": f"hooks_ar#{formulas[0]}", "score": round(sc["score"] / 100, 2),
                "verdict": sc["verdict"], "weakest": sc["weakest"],
                "first_seconds": round(min(window, max(1.0, pick["end"] - pick["start"])), 2),
                "src": {"clip": pick["clip"], "start": pick["start"], "end": pick["end"]},
                "on_screen": " ".join(pick["text"].split()[:6]), "engine": sc["engine"],
                "visual": f"وش المتكلم أو {f['best_motion_shot']}" if f["best_motion_shot"] else "وش المتكلم"}
    text, formula, needs = formula_hook(formulas[min(idx, len(formulas) - 1)] if formulas else 3, topic, hooks)
    sc = score_hook(text.replace("{{", "").replace("}}", ""))
    return {"text": text, "formula": formula, "score": round(sc["score"] / 100, 2), "verdict": sc["verdict"],
            "weakest": sc["weakest"], "first_seconds": window, "src": None, "on_screen": " ".join(topic.split()[:6]),
            "needs_owner_fill": needs, "engine": sc["engine"],
            "visual": f"أعلى لقطة حركة × جودة: {f['best_motion_shot']}" if f["best_motion_shot"] else "أول لقطة فيها حركة",
            "note": "مفيش تفريغ كلام: الهوك كارت على الشاشة فوق أقوى لقطة. أي {{خانة}} يملاها صاحب الطلب، ممنوع نخترع أرقام."}


def risks_for(rhythm: str, f: dict, brief: dict, arc: dict, hook: dict) -> list:
    r = []
    if rhythm == "on-beat" and not f["music_beats"]:
        r.append("مفيش موسيقى متحللة بالـ beats: هنقطع على الحركة أو نختار تراك ونحلله قبل الرندر")
    if rhythm == "speech-led" and f["low_conf"] > 0.15:
        r.append(f"{f['low_conf']:.0%} من الكلمات ثقة التفريغ فيها واطية: الترجمة محتاجة مراجعة")
    if rhythm == "slow-burn" and brief["target_seconds"] < 20:
        r.append("نار هادية في أقل من 20 ث ممكن تبان بطيئة بدل ما تبان عميقة")
    if brief["target_seconds"] < arc["min_seconds"]:
        r.append(f"القوس ده محتاج {arc['min_seconds']} ث على الأقل والهدف {brief['target_seconds']:.0f}")
    if hook.get("needs_owner_fill"):
        r.append("الهوك فيه خانة محتاجة رقم أو معلومة من صاحب الطلب")
    if hook.get("verdict") == "WEAK":
        r.append(f"الهوك ضعيف في «{hook.get('weakest')}» حسب reel_tools")
    if f["shaky"]:
        r.append(f"{len(f['shaky'])} لقطة مهزوزة لازم تتشال أو تتثبت")
    return r or ["مفيش خطر واضح من البيانات؛ الخطر الباقي إن الهوك ميشدش في الواقع"]


def premortem(f: dict, chosen: dict) -> list:
    """Five failure stories with different causes, each with an early sign and a fix."""
    return [
        {"cause": "hook", "story": f"الناس قفلت في أول 3 ث لأن «{_q(chosen['hook']['text'], 40)}» متقريش كوعد",
         "early_sign": "retention بيقع تحت 60% في الثانية 3", "fix": "كارت ≤ 6 كلمات من أول فريم + حركة في أول لقطة"},
        {"cause": "rhythm", "story": f"الإيقاع ({chosen['rhythm']}) زهّق في النص: بيت أطول من 6 ث من غير تغيير",
         "early_sign": "review: dead-air أو لقطة أطول من max_hold", "fix": "punch-in أو B-roll كل 2–4 ث"},
        {"cause": "material", "story": f"المادة الصالحة ({f['usable_s']:.0f} ث) مكفتش وفيه لقطات اتكررت",
         "early_sign": "نفس الشوت مرتين في الـ EDL", "fix": "قصّر المدة أو اقترح لقطات تتصور/تتولد (dm_generate)"},
        {"cause": "words", "story": "الترجمة فيها كلمة غلط أو متأخرة فالمعنى باظ",
         "early_sign": f"{f['low_conf']:.0%} كلمات ثقتها واطية", "fix": "مراجعة الترجمة على الكلمات قبل الحرق"},
        {"cause": "ending", "story": "النهاية وقعت: مفيش لوب ولا دعوة فالفيديو ماتعادش",
         "early_sign": "آخر جملة مفيهاش ولا كلمة من الهوك", "fix": "آخر بيت يكرر كلمة من الهوك أو يرجع لأول لقطة"},
    ]


def decide(criteria: dict, scores: dict) -> dict:
    """Weighted matrix; the winner is re-checked under a ±1 change of every weight."""
    def total(w):
        return {o: sum(w[c] * float(s.get(c, 0)) for c in w) for o, s in scores.items()}
    base = total(criteria)
    winner = max(base, key=base.get)
    flips = []
    for c in criteria:
        for d in (-1, 1):
            t = total({**criteria, c: criteria[c] + d})
            if max(t, key=t.get) != winner:
                flips.append({"criterion": c, "delta": d, "new_winner": max(t, key=t.get)})
    ranked = sorted(base.values(), reverse=True)
    return {"totals": base, "winner": winner, "margin": ranked[0] - ranked[1] if len(ranked) > 1 else None,
            "robust": not flips, "flips": flips}


ADVISORS = [("المعارض", "The Contrarian", "Assume the idea hides a fatal flaw and hunt for it."),
            ("مفكر المبادئ الأولى", "The First-Principles Thinker", "Ask what is really being solved; strip the assumptions."),
            ("الموسِّع", "The Expansionist", "Look for the upside nobody priced in."),
            ("الغريب", "The Outsider", "Know nothing about the field; react only to what is on the page."),
            ("المنفِّذ", "The Executor", "Can it be done, and what is the first step tomorrow morning?")]


def council_pack(job: Path, brief: dict, concepts: list, decision: dict) -> dict:
    """The five-voice council prompt pack (STANDARD depth for an L2 choice between three options)."""
    opts = "; ".join(f"{c['id']}: {c['title']} — {c['logline']}" for c in concepts)
    question = (f"«{brief['task']}» — between {opts} — which concept should the Black Dragon cut, what does it miss, "
                "and what would change the choice?")
    framed = "\n".join([
        f"Question / السؤال:\n{question}\n",
        "Hard constraints / قيود:\n- لا نخترع أرقام أو نتايج مش موجودة في المادة\n"
        f"- المدة {brief['target_seconds']:.0f} ثانية {brief['aspect']}\n- النشر بيقف عند صاحب الطلب\n",
        "Context worth reading / سياق مفيد:\n- brief.json\n- concepts.json\n- analysis.json\n",
        f"Known, with evidence / معلوم بدليل:\n- {brief['evidence']['analysis']}\n"
        f"- decision matrix: winner {decision['chosen']}, margin {decision['sensitivity'].get('margin')}, "
        f"robust={decision['sensitivity'].get('robust')}\n",
        "Unknown / مجهول:\n- رد فعل الجمهور الحقيقي (retention) مجهول لحد النشر\n",
        "What is at stake / ما على المحك:\na wrong concept wastes a render round and the owner's trust\n"])
    parts = ["# مجلس الخمسة — حزمة البرومنتات (Dragon Montage, station 3)", "",
             "Depth / العمق: **STANDARD** — L2 -> STANDARD", "",
             "Claude يشغّل الأصوات الخمسة وبعدين يكتب الحكم ويحدّث `concepts.json → decision.council.verdict`. "
             "السكربت ده ما بينادي أي موديل.", ""]
    for ar, name, style in ADVISORS:
        parts += [f"## {ar} / {name}", "", "```", f"You sit on a five-member council as {name} ({ar}).\n\n"
                  f"How you think: {style}\n\n---\n{framed}---\nAnswer from your angle only, 150-300 words, "
                  "in the user's language.", "```", ""]
    parts += ["## الرئيس / Chairman", "",
              "اكتب الحكم بالأقسام: أين اتفق المجلس · أين اختلف المجلس · النقاط العمياء · التوصية (حرف الفكرة) · أول خطوة.", ""]
    (job / "council_prompt.md").write_text("\n".join(parts), encoding="utf-8")
    return {"used": "llm_council", "status": "prompt_pack_ready", "prompt": "council_prompt.md", "depth": "STANDARD",
            "verdict": f"لسه: المجلس متشغّلش. الاختيار الحالي {decision['chosen']} من المصفوفة؛ Claude يشغّل council_prompt.md ويحدّث الحكم."}


def build_concepts(job) -> dict:
    job = Path(job)
    em, hooks = editor_mind(), C.data("hooks_ar.json")
    brief = C.read(job, "brief")
    analysis, _ = load_analysis(job)
    f, sents = facts(analysis), sentences(analysis)
    best = max(sents, key=lambda s: (s["hook_score"], -s["start"]), default=None)
    fe = em["feelings"][brief["feeling"]]
    ct = brief["content_type"] if brief["content_type"] in em["content_types"] else "montage"
    target = float(brief["target_seconds"])
    topic = brief.get("topic") or topic_of(brief["task"], em)
    used_hooks, used_fw, concepts, consulted = set(), set(), [], 0
    for i, (arc_id, rhythm) in enumerate(choose_combos(ct, f, fe["rhythm"], em)):
        arc, rh = ensure_hook_opening(em["arcs"][arc_id]), em["rhythms"][rhythm]
        hook = make_hook(arc_id, i, sents, used_hooks, topic, em, hooks, f)
        beats = beats_for(arc, target, float(hook["first_seconds"]))
        c = {"id": "ABC"[i], "title": f"{arc['name_ar'].split(':')[0]} × {rh['name_ar']}",
             "logline": (f"{topic}: {' ← '.join(b['purpose'].split('،')[0] for b in beats[:3])}… "
                         f"في {target:.0f} ث، {rh['name_ar']}"),
             "arc": [b["role"] for b in beats], "arc_id": arc_id, "arc_name_ar": arc["name_ar"], "beats": beats,
             "hook": hook, "rhythm": rhythm,
             "style_hint": (f"{fe['name_ar']}: {fe['grade_hint']}؛ قطع {rh['avg_cut_s'][0]}–{rh['avg_cut_s'][1]} ث؛ "
                            f"انتقالات {'/'.join(rh['transitions'])}؛ ترجمة {em['content_types'][ct]['captions']}"),
             "cut_rule": rh["cut_rule"]}
        c["risks"] = risks_for(rhythm, f, brief, arc, hook)
        ctx = {"brief": brief, "facts": f, "best_sentence": best, "one_truth": brief.get("one_truth", ""),
               "feeling_ar": fe["name_ar"], "ct_ar": em["content_types"][ct]["name_ar"], "grade_hint": fe["grade_hint"],
               "concept": c}
        fws = []
        for st in STAGES:
            want = dict(CONCEPT_WANT.get(arc_id, {"story": 1.0}))
            for extra in (RHYTHM_WANT[rhythm], STAGE_TILT.get(st, {})):
                for k, v in extra.items():
                    want[k] = want.get(k, 0) + v
            got, n = apply_frameworks(st, want, brief["task"], 1, ctx, avoid=used_fw)
            consulted += n
            used_fw |= {g["key"] for g in got}
            fws += got
        c["frameworks"] = fws
        concepts.append(c)

    weights = {"hook": 3, "clarity": 2, "novelty": 2, "fit": 3, "feasibility": 2}
    scores = {}
    for i, c in enumerate(concepts):
        arc = em["arcs"][c["arc_id"]]
        clarity = (5 - max(0, len(c["beats"]) - 4) - (1 if target < arc["min_seconds"] else 0)
                   - (1 if target / max(1, len(c["beats"])) < 2.5 else 0))
        fit = 5 - i + (1 if c["rhythm"] == fe["rhythm"] else 0) - (1 if ct not in arc["best_for"] else 0)
        feas = (5 - (3 if c["rhythm"] == "speech-led" and not f["words"] else 0)
                - (2 if c["rhythm"] == "on-beat" and not f["music_beats"] and f["motion_mean"] < 0.3 else 0)
                - (1 if c["rhythm"] == "slow-burn" and f["usable_s"] and f["usable_s"] < target * 1.5 else 0)
                - (1 if c["hook"].get("needs_owner_fill") else 0))
        hook_pts = 1 + round(c["hook"]["score"] * 4) - (1 if c["hook"].get("needs_owner_fill") else 0)
        clip5 = lambda v: max(1, min(5, v))  # noqa: E731
        scores[c["id"]] = {"hook": clip5(hook_pts), "clarity": clip5(clarity), "novelty": [3, 4, 5][i],
                           "fit": clip5(fit), "feasibility": clip5(feas)}
    res = decide(weights, scores)
    chosen = res["winner"]
    ch = next(c for c in concepts if c["id"] == chosen)
    ranked = sorted(res["totals"].items(), key=lambda kv: (-kv[1], kv[0]))
    flip_txt = ("الاختيار ثابت لو غيّرنا أي وزن ±1" if res["robust"] else "الاختيار بيتقلب لو: " +
                "، ".join(f"{x['criterion']} {x['delta']:+d} ← {x['new_winner']}" for x in res["flips"][:3]))
    tie = res["totals"][chosen] == ranked[1][1]
    why = (f"{chosen} «{ch['title']}» {'اتعادل' if tie else 'كسب'} بـ {res['totals'][chosen]:g} نقطة قصاد {ranked[1][0]} ({ranked[1][1]:g})"
           f"{'، والتعادل اتكسر لصالح الأقرب لنوع المحتوى' if tie else ''}. "
           f"الهوك: «{_q(ch['hook']['text'], 60)}» ({ch['hook']['score']:.2f}). {flip_txt}"
           f"{'؛ القرار هش، فالمجلس لازم يتشغّل قبل الرندر' if not res['robust'] else ''}.")
    decision = {"chosen": chosen, "matrix": [{"id": k, "scores": s, "total": res["totals"][k]} for k, s in scores.items()],
                "why": why, "sensitivity": {"engine": "kosif-superpowers/scripts/think.py decide", "weights": weights,
                                            "robust": res["robust"], "margin": res["margin"], "flips": res["flips"]}}
    decision["council"] = council_pack(job, brief, concepts, decision)
    pm = premortem(f, ch)
    out = C.new("concepts", concepts=concepts, decision=decision,
                premortem=[f"{p['story']} — علامة بدري: {p['early_sign']} — الإصلاح: {p['fix']}" for p in pm])
    out["premortem_detail"] = pm
    out["consulted"] = {"registry_frameworks_scored": consulted, "frameworks_applied": sum(len(c["frameworks"]) for c in concepts),
                        "registry_size": len(C.data("mind_registry.json")["frameworks"]), "hook_sentences_scored": len(sents),
                        "hook_formulas": len(hooks.get("hooks", [])),
                        "note": "consulted = اتقرا واتقاس؛ applied = اتطبق على بيانات الشغلانة دي. ولا واحد منهم «اتنفذ» على الفيديو."}
    return out


def brief(job, task, platform=None, seconds=None) -> dict:
    job = C.job_dir(job)
    br = build_brief(job, task, platform, seconds)
    C.write(job, "brief", br)
    return br


def concepts(job) -> dict:
    job = C.job_dir(job)
    cc = build_concepts(job)
    C.write(job, "concepts", cc)
    return cc


def main(argv=None) -> int:
    C.utf8_stdio()
    ap = argparse.ArgumentParser(prog="dragon_montage think", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("brief")
    b.add_argument("--job", required=True)
    b.add_argument("--task", required=True)
    b.add_argument("--platform")
    b.add_argument("--seconds", type=float)
    sub.add_parser("concepts").add_argument("--job", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "brief":
        br = brief(a.job, a.task, a.platform, a.seconds)
        print(f"brief: {br['content_type']} · {br['platform']} {br['aspect']} · {br['target_seconds']:g}s · "
              f"{br['feeling']} · frameworks {[x['id'] for x in br['frameworks']]}")
    else:
        cc = concepts(a.job)
        for x in cc["concepts"]:
            print(f"{x['id']}: {x['arc_id']} × {x['rhythm']} · hook {x['hook']['score']:.2f} «{_q(x['hook']['text'], 50)}»")
        print(f"chosen {cc['decision']['chosen']} · robust={cc['decision']['sensitivity']['robust']}")
    return 0
