"""Script -> sentences, and voiceover -> per-word / per-sentence timing.
Primary: sherpa-onnx Parakeet word timestamps aligned to the script text.
Fallback (no model): energy-based speech detection + syllable-proportional placement snapped to pauses."""
import json, os, re, subprocess, difflib
import numpy as np

SPLIT = re.compile(r"(?<=[.!?…؟])[\"”’)»]*\s+")
ABBR = re.compile(r"\b(Mr|Mrs|Ms|Dr|St|vs|Jr|Sr|U\.S|e\.g|i\.e|No|Inc|Co|Mt)\.$", re.I)


def sentences(text):
    text = text.replace('\r', '')
    out = []
    for para in re.split(r"\n", text):
        para = para.strip()
        if not para or para.startswith('#'): continue
        parts = [s.strip() for s in SPLIT.split(para) if s.strip()]
        merged = []
        for p in parts:
            if merged and ABBR.search(merged[-1]): merged[-1] += " " + p
            else: merged.append(p)
        out += merged
    return out


AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
AR_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي", "گ": "ك", "ڤ": "ف", "پ": "ب", "چ": "ج"})


def norm(w):
    """Comparable form of a word: lower-case Latin, digits, and Arabic letters with diacritics/tatweel removed
    and common spelling variants folded (أ/إ/آ->ا, ى->ي, ة->ه ...), so cues match however the SRT spells them."""
    w = w.lower().replace("’", "'").translate(AR_DIGITS)
    w = re.sub(r"[ً-ٰٟـ]", "", w).translate(AR_FOLD)
    w = re.sub(r"[^a-z0-9'ء-ي]+", "", w)
    return w.strip("'")


def strip_al(w):
    """Arabic word without a leading و/ف/ب/ل/ك and ال (for loose cue matching)."""
    w = norm(w)
    for p in ("وال", "فال", "بال", "كال", "لل", "ال"):
        if w.startswith(p) and len(w) - len(p) >= 2: return w[len(p):]
    return w


def words_of(s): return [w for w in (norm(x) for x in s.split()) if w]


def syllables(w):
    w = norm(w)
    if not w: return 1
    if w.isdigit(): return max(1, len(w) * 2)
    if re.search(r"[\u0621-\u064A]", w): return max(1, round(len(w) / 2))  # Arabic: ~2 letters per syllable
    n = len(re.findall(r"[aeiouy]+", w))
    if w.endswith('e') and n > 1 and not w.endswith('le'): n -= 1
    return max(1, n)


def load_audio(path, sr=16000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def speech_mask(x, sr=16000, hop=0.01):
    n = int(sr * hop); m = len(x) // n
    e = np.sqrt(np.mean(x[:m * n].reshape(m, n) ** 2, axis=1) + 1e-12); db = 20 * np.log10(e)
    ref = np.percentile(db, 95); thr = max(ref - 32, np.percentile(db, 10) + 6)
    on = db > thr
    k = int(0.12 / hop)  # close short gaps < 120 ms
    idx = np.where(on)[0]
    if len(idx):
        gaps = np.diff(idx)
        for a, g in zip(idx[:-1], gaps):
            if 1 < g <= k: on[a:a + g] = True
    return on, hop


def find_model():
    cands = [os.environ.get("RM_ASR", ""), os.path.expanduser("~/models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"),
             os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8")]
    for c in cands:
        if c and os.path.exists(os.path.join(c, "encoder.int8.onnx")): return c
    return None


def asr_words(x, sr, model):
    import sherpa_onnx
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(encoder=f"{model}/encoder.int8.onnx", decoder=f"{model}/decoder.int8.onnx",
                                                        joiner=f"{model}/joiner.int8.onnx", tokens=f"{model}/tokens.txt",
                                                        num_threads=max(1, min(8, os.cpu_count() or 2)), model_type="nemo_transducer")
    on, hop = speech_mask(x, sr)
    # chunk at silences, ~20 s per chunk
    cuts = [0]; L = len(x) / sr; t = 0.0
    while t + 24 < L:
        lo, hi = int((t + 16) / hop), int(min(t + 24, L) / hop)
        seg = on[lo:hi]; off = np.where(~seg)[0]
        c_ = (lo + off[len(off) // 2]) * hop if len(off) else (t + 20)
        cuts.append(c_); t = c_
    cuts.append(L); words = []
    for a, b in zip(cuts, cuts[1:]):
        st = rec.create_stream(); st.accept_waveform(sr, x[int(a * sr):int(b * sr)]); rec.decode_stream(st); r = st.result
        cur = None
        for tok, ts in zip(r.tokens, r.timestamps):
            new = tok.startswith(" ") or tok.startswith("▁") or cur is None
            piece = tok.replace("▁", " ").strip()
            if not piece: continue
            if new:
                cur = [piece, a + ts]; words.append(cur)
            else:
                cur[0] += piece
    return [(norm(w), t) for w, t in words if norm(w)]


def align(script_sents, audio_path):
    x = load_audio(audio_path); sr = 16000; L = len(x) / sr
    on, hop = speech_mask(x, sr)
    sw = []  # (sentence idx, word)
    for i, s in enumerate(script_sents):
        for w in s.split():
            if norm(w): sw.append((i, w))
    model = find_model(); method = "asr"; times = [None] * len(sw)
    if model:
        aw = asr_words(x, sr, model)
        sm = difflib.SequenceMatcher(a=[norm(w) for _, w in sw], b=[w for w, _ in aw], autojunk=False)
        for blk in sm.get_matching_blocks():
            for k in range(blk.size): times[blk.a + k] = aw[blk.b + k][1]
        matched = sum(t is not None for t in times) / max(1, len(times))
        if matched < 0.35: method = "fallback"; times = [None] * len(sw)
    else:
        method = "fallback"; matched = 0.0
    if method == "fallback":
        # place words on speech time proportionally to syllables
        st = np.where(on)[0] * hop; syl = np.cumsum([0] + [syllables(w) for _, w in sw]); tot = syl[-1]
        for k in range(len(sw)):
            j = int(min(len(st) - 1, syl[k] / tot * len(st))); times[k] = float(st[j]) if len(st) else k * .35
    # interpolate gaps
    known = [k for k, t in enumerate(times) if t is not None]
    if not known: raise SystemExit("alignment failed: no words found")
    for k in range(len(times)):
        if times[k] is None:
            prev = max([j for j in known if j < k], default=None); nxt = min([j for j in known if j > k], default=None)
            if prev is None: times[k] = max(0.0, times[nxt] - .3 * (nxt - k))
            elif nxt is None: times[k] = times[prev] + .3 * (k - prev)
            else: times[k] = times[prev] + (times[nxt] - times[prev]) * (k - prev) / (nxt - prev)
    for k in range(1, len(times)): times[k] = max(times[k], times[k - 1])
    # sentence spans; end = end of speech run after the last word
    out = []
    for i, s in enumerate(script_sents):
        ks = [k for k, (si, _) in enumerate(sw) if si == i]
        if not ks: continue
        t0 = times[ks[0]]; tl = times[ks[-1]]
        j = int(tl / hop) + 5
        while j < len(on) and on[j]: j += 1
        t1 = min(L, j * hop + .05)
        nxt = times[ks[-1] + 1] if ks[-1] + 1 < len(times) else L
        t1 = max(tl + .15, min(t1, nxt - .02))
        out.append(dict(i=i, text=s, start=round(max(0, t0 - .06), 3), end=round(t1, 3),
                        words=[dict(w=sw[k][1], n=norm(sw[k][1]), t=round(times[k], 3)) for k in ks]))
    if method == "fallback":  # snap sentence starts to speech onsets near the estimate
        for s in out:
            j = int(s["start"] / hop)
            for d in range(0, 60):
                for jj in (j - d, j + d):
                    if 0 < jj < len(on) and on[jj] and not on[jj - 1]:
                        s["start"] = round(jj * hop - .04, 3); break
                else: continue
                break
    return dict(duration=round(L, 3), method=method, matched=round(matched, 3), sentences=out)


# ---------------------------------------------------------------- SRT -> timing (the main path for Arabic voiceovers)
TS = re.compile(r"(\d+):(\d{1,2}):(\d{1,2})[,.](\d{1,3})\s*-->\s*(\d+):(\d{1,2}):(\d{1,2})[,.](\d{1,3})")
SPLIT_AT = re.compile(r"[.!?…،؛؟,;:]$")


def parse_srt(path):
    """-> [(start, end, text)] in file order. Handles BOM, CRLF, missing index lines, <i>/{\\an8} tags, multi-line cues."""
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"): txt = raw.decode("utf-16")
    else:
        try: txt = raw.decode("utf-8-sig")
        except UnicodeDecodeError: txt = raw.decode("cp1256", errors="replace")  # old Windows Arabic subtitles
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    cues = []; cur = None; lines = txt.split("\n")
    for j, ln in enumerate(lines):
        if ln.strip().isdigit() and j + 1 < len(lines) and TS.search(lines[j + 1]): continue  # cue index line
        m = TS.search(ln)
        if m:
            g = [int(x) for x in m.groups()]
            a = g[0] * 3600 + g[1] * 60 + g[2] + int(str(m.group(4)).ljust(3, "0")) / 1000
            b = g[4] * 3600 + g[5] * 60 + g[6] + int(str(m.group(8)).ljust(3, "0")) / 1000
            cur = [a, b, []]; cues.append(cur); continue
        s = ln.strip()
        if cur is None or not s: continue
        cur[2].append(s)
    out = []
    for a, b, ls in cues:
        t = " ".join(ls); t = re.sub(r"<[^>]+>|\{[^}]*\}", "", t); t = re.sub(r"\s+", " ", t).strip()
        if t: out.append((a, max(b, a + .05), t))
    out.sort(key=lambda c: c[0])
    if not out: raise SystemExit(f"no subtitles found in {path}")
    return out


def _weight(w):
    """Spoken-length weight of a word: letters without diacritics (numbers count more, they're read as words)."""
    n = norm(w)
    if not n: return 0.5
    if n.isdigit(): return 3.0 * len(n)
    return max(1.0, len(n))


def _place_words(words, a, b, on, hop):
    """Spread words over the voiced part of [a, b], proportional to length."""
    i0, i1 = int(a / hop), max(int(a / hop) + 1, int(b / hop))
    act = np.where(on[i0:i1])[0] if i0 < len(on) else np.array([], int)
    wts = np.array([_weight(w) for w in words]); cum = np.concatenate([[0], np.cumsum(wts)])[:-1] / wts.sum()
    if len(act) < 5: return [a + (b - a) * f for f in cum]
    return [(i0 + act[min(len(act) - 1, int(f * len(act)))]) * hop for f in cum]


def _best_offset(cues, on, hop, L):
    """Find a global SRT shift (-2..+2 s) that best lines subtitle time up with detected speech."""
    n = len(on); sub = np.zeros(n, bool)
    for a, b, _ in cues: sub[int(a / hop):min(n, int(b / hop))] = True
    def score(sh):
        k = int(round(sh / hop)); s = np.roll(sub, k)
        if k > 0: s[:k] = False
        elif k < 0: s[k:] = False
        return (s & on).sum() / max(1, s.sum())
    base = score(0.0); best = max(np.arange(-2.0, 2.01, .05), key=score)
    return float(best), base, score(best)


def from_srt(srt_path, audio_path, max_len=8.0, offset=None):
    """SRT + voiceover -> timing dict (same format as align()). Each subtitle cue becomes one numbered unit
    ("sentence"); cues longer than max_len seconds are split at punctuation (or mid-cue) into smaller units."""
    x = load_audio(audio_path); sr = 16000; L = len(x) / sr
    on, hop = speech_mask(x, sr); cues = parse_srt(srt_path); notes = []
    if offset is None:
        sh, s0, s1 = _best_offset(cues, on, hop, L)
        if abs(sh) >= .15 and s1 - s0 > .06: offset = sh; notes.append(f"SRT looked shifted: applied offset {sh:+.2f}s (speech overlap {s0:.0%} -> {s1:.0%})")
        else: offset = 0.0
        cover = max(s0, s1)
    else:
        cover = None
    if offset: cues = [(a + offset, b + offset, t) for a, b, t in cues]
    if cues[-1][1] > L + 1.5: notes.append(f"WARNING: subtitles run to {cues[-1][1]:.1f}s but the audio is {L:.1f}s: is this the SRT of this exact file?")
    # word-by-word SRT (most cues are 1-2 words): merge into phrase units but keep each word's exact time
    exact = {}
    if np.median([len(t.split()) for _, _, t in cues]) <= 2 and len(cues) > 8:
        merged = []; cur = None
        for a, b, t in cues:
            gap = a - cur[1] if cur else 0
            if cur and (gap > .4 or SPLIT_AT.search(cur[2][-1]) or (b - cur[0] > 6 and len(cur[2]) >= 3)):
                merged.append(cur); cur = None
            if cur is None: cur = [a, b, [], []]
            ws_ = t.split(); cur[1] = b; cur[2] += ws_; cur[3] += [a + (b - a) * k / len(ws_) for k in range(len(ws_))]
        if cur: merged.append(cur)
        cues = [(a, b, " ".join(ws_)) for a, b, ws_, _ in merged]
        for (a, b, ws_, tws) in merged: exact[(round(a, 3), " ".join(ws_))] = tws
        notes.append(f"word-by-word SRT: merged into {len(cues)} phrase units, exact word times kept")
    units = []; prev_end = 0.0
    for a, b, t in cues:
        key = (round(a, 3), t)
        a = max(a, prev_end, 0.0); b = min(max(b, a + .2), L)
        if a >= L - .05: notes.append(f"WARNING: cue past the end of the audio dropped: {t[:40]}"); continue
        ws = t.split(); tw = [max(a, x) for x in exact[key]] if key in exact else _place_words(ws, a, b, on, hop)
        # split long cues into pieces of <= max_len s, preferring punctuation
        pieces = [(0, len(ws))]
        while True:
            lo, hi = max(pieces, key=lambda p: (tw[p[1]] if p[1] < len(ws) else b) - tw[p[0]])
            dur = (tw[hi] if hi < len(ws) else b) - tw[lo]
            if dur <= max_len or hi - lo < 4: break
            mid = tw[lo] + dur / 2; cands = [k for k in range(lo + 2, hi - 1)]
            punct = [k for k in cands if SPLIT_AT.search(ws[k - 1])]
            k = min(punct or cands, key=lambda k: abs(tw[k] - mid) * (1 if k in punct else 1.6))
            i_ = pieces.index((lo, hi)); pieces[i_:i_ + 1] = [(lo, k), (k, hi)]
        for lo, hi in pieces:
            st = tw[lo]; en = tw[hi] - .02 if hi < len(ws) else b
            units.append(dict(text=" ".join(ws[lo:hi]), start=round(st, 3), end=round(max(en, st + .15), 3),
                              words=[dict(w=ws[k], n=norm(ws[k]), t=round(tw[k], 3)) for k in range(lo, hi)]))
        prev_end = b
    for i, u in enumerate(units): u["i"] = i
    out = [dict(i=u["i"], text=u["text"], start=u["start"], end=u["end"], words=u["words"]) for u in units]
    return dict(duration=round(L, 3), method="srt", matched=1.0, offset=round(offset, 3), speech_cover=None if cover is None else round(float(cover), 3),
                cues=len(cues), sentences=out), notes
