"""Helpers of power_programs/voice_tts.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from ._lang_common import db
from ._lang_common import ffmpeg
from ._lang_common import norm_ar
from ._lang_common import peak_db
import re
from ._lang_common import read_wav
from ._lang_common import sha256
from ._lang_common import write_wav


def direct_ok(d):
    errs = []
    if len(d["note"].split()) > 60:
        errs.append("note > 60 words")
    if not 2 <= d["pace"] <= 4:
        errs.append("pace outside 2-4 wps")
    if not 1 <= d["energy"] <= 10:
        errs.append("energy outside 1-10")
    if d["pitch"] not in ("low", "mid", "high"):
        errs.append("pitch must be low|mid|high")
    return errs


def piper_length_scale(pace, base_pace=3.0):
    return round(base_pace / pace, 3)


def word_budget(seconds, wps=2.5, lang="en"):
    n = seconds * wps
    if lang == "ar":
        n *= 0.825          # 15-20 % fewer words: midpoint
    return int(n)


def scene_fill(seconds):
    if 3 <= seconds <= 4:
        lo, hi = 8, 12
    elif 5 <= seconds <= 6:
        lo, hi = 15, 22
    elif 7 <= seconds <= 8:
        lo, hi = 22, 30
    else:
        raise ValueError("no band")
    return lo, hi


def speed_plan(speed, content):
    if speed >= 1.5:
        raise ValueError("avoid >= 1.5")
    if not 0.7 <= speed <= 1.2:
        raise ValueError("speed outside 0.7-1.2")
    return {"content": content, "speed": speed, "piper_length_scale": round(1 / speed, 3), "method": "regenerate",
            "atempo": None}


PRON = {".com": " دوت كوم", "API": "إيه بي آي", "$1.9T": "قرابة تريليوني دولار", "٢٠٢٦": "ألفين وستة وعشرين"}


def say_show(text):
    say = text
    for k, v in PRON.items():
        say = say.replace(k, v)
    return say, text


WAW_WORDS = {"واحد", "واحده", "وقت", "وسط", "وصل", "وجه", "وزن", "وطن"}


def narration_plan(scenes, wps=2.5):
    out, issues = [], []
    for i, s in enumerate(scenes):
        conj = [w for w in s["vo"].split() if w.startswith("و") and len(w) > 3 and norm_ar(w).rstrip(".،") not in WAW_WORDS]
        if conj or " and " in s["vo"]:
            issues.append(f"scene {i}: needs 'and' -> split into two scenes")
        start = max(0.0, s["action_t"] - 0.4)
        out.append({"scene": i, "vo_start": round(start, 2), "lead": round(s["action_t"] - start, 2)})
    hook_s = len(scenes[0]["vo"].split()) / wps
    if hook_s > 2:
        issues.append("hook longer than 2 s")
    return out, issues


def to_ssml(line):
    s = re.sub(r"\[pause (\d+(?:\.\d+)?)s\]", lambda m: f"<break time='{int(float(m.group(1)) * 1000)}ms'/>", line)
    s = re.sub(r"\*([^*]+)\*", r"<emphasis>\1</emphasis>", s)
    s = re.sub(r"\(([a-z]+)\)\s*", "", s)
    return f"<speak><prosody rate='-5%'>{s}</prosody></speak>"


def piper_from_tags(line):
    pauses = [float(x) for x in re.findall(r"\[pause (\d+(?:\.\d+)?)s\]", line)]
    return {"sentence_silence": max(pauses) if pauses else 0.2, "length_scale": 1.05}


def parse_script(md):
    out = []
    for m in re.finditer(r"^## Line (\d+) — (.+?) \(Frame (\d+)\)\n(.*?)(?=^## |\Z)", md, re.S | re.M):
        body = m.group(4)
        spoken = " ".join(l.strip() for l in body.splitlines() if l.startswith("    "))
        guide = re.search(r"Time guide: (.+)", body)
        out.append({"line": int(m.group(1)), "label": m.group(2), "frame": int(m.group(3)), "spoken": spoken,
                    "time_guide": guide.group(1) if guide else None})
    return out


DIALECT = {"egyptian": ("مش", "ازاي", "دلوقتي", "ده", "دي"), "levantine": ("شو", "هلق", "منيح"), "gulf": ("شلون", "وايد")}


def block_dialects(text):
    toks = {norm_ar(t) for t in re.findall(r"[ء-ي]+", text)}
    return sorted(d for d, ms in DIALECT.items() if any(norm_ar(m) in toks for m in ms))


def direct_blocks(blocks, pron):
    out = []
    for b in blocks:
        ds = block_dialects(b["text"])
        spoken = b["text"]
        for w, s in pron.items():
            spoken = spoken.replace(w, s)
        errs = []
        if len(ds) > 1:
            errs.append("mixed dialects in one block")
        if not 1 <= b["energy"] <= 5:
            errs.append("energy must be 1-5")
        out.append({"spoken": spoken, "dialects": ds, "errors": errs})
    return out


def voice_route(brief):
    lang = brief.get("language") or "ar-EG"
    return {"language": lang, "engine": {"ar-SA": "Piper/Naayf", "ar-EG": "Gemini persona (VOICE-26)"}.get(lang, "ask"),
            "pron_map": f"pron_{lang}.json"}


EG_NUM = {11: "حداشر", 12: "اتناشر", 15: "خمستاشر", 100: "مية", 1000: "ألف"}


FILLERS = ("يا جماعة", "بصوا بقى", "تمام؟", "زي ما انتم شايفين")


def egyptianise(text):
    t = re.sub(r"\b(\d+)\b", lambda m: EG_NUM.get(int(m.group(1)), m.group(1)), text)
    t = t.replace("جنيه", "جنيه [geneh]")
    return t


def filler_ok(text):
    ss = [s for s in re.split(r"[.!؟?]\s*", text) if s.strip()]
    n = sum(text.count(f) for f in FILLERS)
    return n <= max(1, len(ss) // 3), n, len(ss)


VOICE = "Narrator: deep, warm, slightly raspy male, mid-40s, measured documentary pace"


def narrate(topic_words, i, n):
    line = " ".join(topic_words[i * 19:(i + 1) * 19][:19])
    return f"{VOICE}. Clip {i + 1}/{n}, 10 s. Says: \"{line}\". Sound: projector hum, paper snaps."


MUSCLE = {"Abs": ["Ribs down, crunch.", "Exhale at the top.", "Lower slowly now.", "No neck pulling.", "Squeeze and hold."],
          "Chest": ["Elbows at forty-five.", "Press up, exhale.", "Lower to chest level.", "Shoulders back, down.", "Full stretch, control."],
          "Back": ["Pull elbows to hips.", "Squeeze shoulder blades.", "Chest up, pull.", "Slow return, control.", "Lead with elbows."]}


def cue_for_rep(muscle, phase):
    lines = MUSCLE[muscle]
    return lines[phase % len(lines)]


def vo_spec_check(path):
    x, sr, bits = read_wav(path)
    x = x.mean(axis=1)
    room = x[: sr]                       # first 1 s is room tone
    return {"sr": sr, "bits": bits, "peak_db": round(peak_db(x), 2), "noise_floor_db": round(db(room), 1),
            "pass": sr == 48000 and bits == 24 and abs(peak_db(x) + 12) <= 1 and db(room) < -60}


def pacing(words_json, cues):
    gaps = []
    for a, b in zip(words_json, words_json[1:]):
        if b["start"] - a["end"] > 1.5:
            gaps.append({"from": a["end"], "to": b["start"], "motion": "camera drift"})
    sync = {c["word"]: round(abs(c["t"] - next(w["start"] for w in words_json if w["w"] == c["word"])) * 1000) for c in cues}
    return gaps, sync


INK, DONE = (0x8a, 0x7b, 0x70), (0x1f, 0x1b, 0x17)


def lerp(a, b, u):
    return tuple(round(x + (y - x) * u) for x, y in zip(a, b))


def word_colour(t, start, lead=0.06, dur=0.12):
    u = min(1.0, max(0.0, (t - (start - lead)) / dur))
    return lerp(INK, DONE, u)


def out_back(u, s=1.70158):
    u -= 1
    return u * u * ((s + 1) * u + s) + 1


def typed_at(t, wj):
    shown = [w["w"] for w in wj if w["start"] <= t]
    caret = int(t / 0.53) % 2 == 0
    return " ".join(shown), caret


def lecture_plan(sents, chapters):
    t, plan = 0.0, []
    for ch, idx in chapters:
        for i in idx:
            s = sents[i]
            lines = wrap_lines(s["text"], 28)
            plan.append({"t": round(t, 2), "draw_s": s["dur"], "element": f"el{i}", "subtitle": lines})
            t += s["dur"]
        plan.append({"t": round(t, 2), "eraser": ch})
        t += 0.6
    return plan


def wrap_lines(text, n):
    out, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + 1 > n and cur:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    out.append(cur)
    return out


def _proc(work, name, sig, sr, af, out_sr=None):
    src = write_wav(work / f"{name}_in.wav", sig, sr)
    dst = work / f"{name}_out.wav"
    extra = ["-ar", str(out_sr)] if out_sr else []
    ffmpeg("-i", src, "-af", af, *extra, "-c:a", "pcm_s16le", dst)
    y, ysr, _ = read_wav(dst)
    return y.mean(axis=1), ysr


def butter_lp(x, sr, fc):
    from scipy.signal import butter, sosfiltfilt
    return sosfiltfilt(butter(4, fc, "low", fs=sr, output="sos"), x)


def audiolab(stereo, sr, mode):
    if stereo.ndim != 2 or stereo.shape[1] != 2:
        raise ValueError("centre-cancel works on stereo only")
    L, R = stereo[:, 0], stereo[:, 1]
    mid, side = (L + R) / 2, (L - R) / 2
    if mode == "novoice":
        return side + butter_lp(mid, sr, 140)        # restore bass below 140 Hz after phase cancel
    if mode == "voice":
        return mid - butter_lp(mid, sr, 140)
    raise ValueError(mode)


VIEW_WORDS = {"home": ["الرئيسية", "home"], "projects": ["المشاريع", "projects"], "editor": ["المحرر", "editor"],
              "settings": ["الإعدادات", "settings"]}


def route_intent(transcript, ctx):
    t = transcript.lower()
    has = lambda *ws: any(w in t for w in ws)
    if has("افتح", "روح", "open", "go to"):
        for v, ws in VIEW_WORDS.items():
            if has(*ws):
                return {"action": "navigate", "view": v}
    if has("حالة", "status", "وصل فين"):
        return {"action": "status", "reply": f"render {ctx['render']}%"}
    return {"action": "guidance", "reply": "قول مثلًا: افتح المشاريع"}


def ease_out(u):
    return 1 - (1 - u) ** 3


def ring_scale(t, delay, dur=1.8, a=0.6, b=1.9):
    u = ((t - delay) % dur) / dur if t >= delay else 0.0
    return a + (b - a) * ease_out(u)


def fab(t, dur=1.6):
    u = (t % dur) / dur
    e = ease_out(u)
    return round(1 + 0.7 * e, 4), round(0.8 * (1 - e), 4)


def mic_constraints(purpose):
    c = {"echoCancellation": True, "noiseSuppression": True, "autoGainControl": True}
    if purpose == "vo-take":
        c["autoGainControl"] = False
    return {"audio": c}


REAL = {"amr diab", "fairuz", "morgan freeman", "عمرو دياب", "فيروز"}


def voice_request(req, clone=None):
    low = req.lower()
    hit = [n for n in REAL if n in low]
    if hit:
        return {"action": "describe timbre instead", "named": hit}
    if clone and not clone.get("consent_record"):
        return {"action": "refuse clone: no consent record"}
    return {"action": "ok"}


def preclean(t):
    return re.sub(r"\s+", " ", re.sub(r"[*_#>`]", "", t)).strip()


def tts_batch(lines, cache, voice="kareem", model="m1", settings="s1"):
    hits = miss = chars = 0
    for l in lines:
        t = preclean(l)
        k = sha256(f"{voice}:{model}:{settings}:{t}")
        if k in cache:
            hits += 1
        else:
            cache[k] = f"{k[:8]}.wav"
            miss += 1
            chars += len(t)
    return hits, miss, chars
