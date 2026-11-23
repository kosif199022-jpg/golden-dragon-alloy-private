"""Red Rose V29 delivery gate (W09): ``rose.py check``.

Read-only. It checks the SHAPE of a reply and whether the evidence and files it
leans on exist and say ok. It never checks whether the content is true, never
opens a database, never uses the network and never writes a file. Media is
measured with ffprobe/ffmpeg, which write nothing (output goes to pipes).

Python: ``check(request, draft_text, evidence_paths, files, words=None) -> dict``
CLI:    ``rose.py check --request TEXT --draft FILE [--evidence FILE ...]
         [--files PATH ...] [--words FILE] [--json] [--text] [--pretty]``
Exit:   0 pass, 1 fail, 2 usage.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import rose_io as rio

NOTE_AR = 'الفحص ده للشكل ووجود الدليل بس، مش للحقيقة'
CRITIC_QUESTIONS = [
    'إيه أضعف حاجة في الرد ده؟',
    'الدليل اللي الرد بيعتمد عليه اتقرا فعلًا ولا اتفرض؟',
    'إيه الملاحظة اللي لو ظهرت تهدّ الاستنتاج؟',
]
MAX_DRAFT_CHARS = 40000
SAMPLE_HEAD = 30000
SAMPLE_TAIL = 10000
VIDEO_EXT = {'.mp4', '.m4v', '.mov', '.mkv', '.webm'}
MP4_EXT = {'.mp4', '.m4v', '.mov'}
MEDIA_EXT = VIDEO_EXT | {'.wav', '.mp3', '.m4a', '.aac', '.png', '.jpg', '.jpeg', '.webp'}
BLACK_MEAN = 20          # mean luma (0..255) under which a sampled frame counts as black
PROBE_TIMEOUT = 300      # seconds per ffprobe/ffmpeg call
LUMA_W, LUMA_H = 64, 36

_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
_DIACRITICS = re.compile('[ً-ٰٟـ]')
_PATH_RE = re.compile(r'(?<![\w])(?:[A-Za-z]:[\\/]|\\\\[\w.$-]+\\|~[\\/])[^\s"\'<>|*?()\[\]{}،؛]+'
                      r'|(?<![\w:/.])/(?:[\w.$-]+/)+[\w.$-]*[^\s"\'<>|*?()\[\]{}،؛/]')  # POSIX: /home/user/work/out.mp4 (2+ parts; URLs excluded)
_AR_DONE = re.compile(
    r'(?<!\w)(?:خلص|خلصت|خلصنا|خلاص|جاهز|جاهزة|جاهزين|اتعمل|اتعملت|تم|تمت|تمّ|تمّت|'
    r'اتسلم|اتسلمت|مكتمل|مكتملة|اتنفذ|اتنفذت)(?!\w)')
_EN_DONE = re.compile(r'(?<![A-Za-z])(?:done|ready|finished|completed|delivered)(?![A-Za-z])', re.I)
_NEG = re.compile(r'(?:مش|مو|لسه|لسّه|مفيش|not|isn\'t|no)\s*$', re.I)
_ACTION = re.compile(
    r'(?<!\w)(?:نشر|انشر|نشرت|اتنشر|ارفع|رفع|رفعت|اترفع|امسح|مسح|مسحت|اتمسح|احذف|حذف|حذفت|اتحذف|'
    r'اشتر|اشتري|اشتريت|شراء|ثبت|ثبّت|تثبيت|اتثبت|ثبتت)|'
    r'\b(?:publish|published|upload|uploaded|delete|deleted|purchase|purchased|buy|bought|install|installed)\b',
    re.I)
_APPROVAL = re.compile(r'موافق|وافق|approv', re.I)
_CAPTION_KEYS = {'caption', 'captions', 'caption_text', 'burned_text', 'subtitle', 'subtitles',
                 'title', 'text', 'line', 'lines'}
_MENTION_WORDS = {
    'example_only': ['مثال', 'example', 'sample'],
    'approval_required': ['موافق', 'approval', 'approve'],
    'unavailable_here': ['متاح', 'unavailable'],
    'error': ['خطأ', 'خطا', 'فشل', 'error', 'failed'],
    'unreadable': ['اتقرا', 'unreadable'],
    'missing': ['مش موجود', 'missing'],
    'needs_input': ['محتاج', 'سؤال', 'needs_input', 'needs input', 'question'],
    'arabic_unshaped': ['تشكيل', 'unshaped', 'arabic', 'الحروف'],
}
_STOP = {'عايز', 'عاوز', 'اعمل', 'عمل', 'ايه', 'إيه', 'دي', 'ده', 'دا', 'في', 'على', 'من', 'الى', 'إلى',
         'the', 'and', 'for', 'with', 'this', 'that', 'make', 'the', 'واحد', 'حاجة', 'عشان', 'علشان',
         'اعملي', 'ممكن', 'تعمل', 'اعمله', 'بتاع', 'بتاعة', 'كده', 'يا'}


# --------------------------------------------------------------------------- text helpers

def _norm(text):
    text = _DIACRITICS.sub('', text or '').translate(_DIGITS)
    text = re.sub('[إأآٱ]', 'ا', text)
    return text.replace('ى', 'ي').replace('ة', 'ه').lower()


def _tokens(text):
    return re.sub(r'[^\w\s]', ' ', _norm(text)).split()


def _skel(word):
    """Arabic consonant skeleton: drop long-vowel letters and the article."""
    if re.search(r'[؀-ۿ]', word):
        if word.startswith('ال') and len(word) > 4:
            word = word[2:]
        return re.sub('[اوي ء]', '', word)
    return word


def _first_line_span(text):
    pos = 0
    for line in text.split('\n'):
        if line.strip():
            return pos, pos + len(line)
        pos += len(line) + 1
    return None


def _done_hits(text):
    hits = []
    for rx in (_AR_DONE, _EN_DONE):
        for m in rx.finditer(text):
            if _NEG.search(text[max(0, m.start() - 12):m.start()]):
                continue
            hits.append(m.group(0))
    hits += [mark for mark in ('✅', '✔', '✓') if mark in text]
    return hits


def _clean_path(raw):
    return raw.rstrip('.;:!؟,،')


def _expand(path):
    return Path(os.path.expanduser(path))


# --------------------------------------------------------------------------- evidence

def _all_strings(obj, out):
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _all_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _all_strings(v, out)
    return out


def _arabic_unshaped(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'warnings' and isinstance(v, list):
                if any(isinstance(w, str) and w.startswith('arabic_unshaped') for w in v):
                    return True
            if _arabic_unshaped(v):
                return True
    elif isinstance(obj, list):
        return any(_arabic_unshaped(v) for v in obj)
    return False


def _caption_strings(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _CAPTION_KEYS:
                if isinstance(v, str):
                    out.append(v)
                elif isinstance(v, (list, dict)):
                    _all_strings(v, out)
            elif isinstance(v, (list, dict)):
                _caption_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _caption_strings(v, out)
    return out


def _read_evidence(path):
    """-> (public record, envelope or None). Outcome is read from the envelope, never assumed."""
    rec = {'file': str(path), 'id': None, 'outcome': None}
    try:
        env = json.loads(rio.read_text_bytes(path))
    except (rio.ParamError, OSError) as exc:
        rec['outcome'] = 'missing'
        rec['detail'] = str(exc)[:200]
        return rec, None
    except json.JSONDecodeError as exc:
        rec['outcome'] = 'unreadable'
        rec['detail'] = f'not JSON: {exc.msg}'
        return rec, None
    if not isinstance(env, dict):
        rec['outcome'] = 'unreadable'
        rec['detail'] = 'envelope is not a JSON object'
        return rec, None
    rec['id'] = env.get('id') if isinstance(env.get('id'), str) else None
    outcome = env.get('outcome')
    if not isinstance(outcome, str):
        outcome = 'ok' if env.get('ok') is True else 'error'
    if outcome == 'ok' and (env.get('ok') is False or _arabic_unshaped(env)):
        outcome = 'error'
        rec['detail'] = 'ok outcome overridden: ok false or arabic_unshaped warning'
    rec['outcome'] = outcome
    return rec, env


# --------------------------------------------------------------------------- media

def _rate(text):
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError, TypeError):
        return None
    if value <= 0:
        return None
    return float(value)


def _num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _luma_means(path):
    cmd = ['ffmpeg', '-v', 'error', '-i', str(path), '-t', '0.5', '-vf',
           f'fps=10,scale={LUMA_W}:{LUMA_H}', '-pix_fmt', 'gray', '-f', 'rawvideo', '-']
    proc = subprocess.run(cmd, capture_output=True, timeout=PROBE_TIMEOUT)
    if proc.returncode != 0:
        raise RuntimeError('ffmpeg could not decode the first 0.5 s: ' + proc.stderr.decode('utf-8', 'replace')[:200])
    raw = proc.stdout
    size = LUMA_W * LUMA_H
    frames = [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)]
    return [sum(f) / len(f) for f in frames if f]


def _probe(path):
    entry = {'file': str(path), 'duration': None, 'frames': None, 'fps': None, 'width': None,
             'height': None, 'video_codec': None, 'audio_codec': None, 'first_frame_black': None,
             'error': None}
    cmd = ['ffprobe', '-v', 'error', '-count_frames', '-show_entries',
           'stream=codec_type,codec_name,width,height,avg_frame_rate,nb_read_frames,duration:format=duration',
           '-of', 'json', str(path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                              timeout=PROBE_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        entry['error'] = f'ffprobe unavailable or failed: {exc}'[:300]
        return entry
    if proc.returncode != 0:
        entry['error'] = 'ffprobe: ' + proc.stderr.strip()[:300]
        return entry
    try:
        data = json.loads(proc.stdout or '{}')
    except json.JSONDecodeError:
        entry['error'] = 'ffprobe output is not JSON'
        return entry
    streams = data.get('streams') or []
    fmt_duration = _num((data.get('format') or {}).get('duration'))
    videos = [s for s in streams if s.get('codec_type') == 'video']
    audios = [s for s in streams if s.get('codec_type') == 'audio']
    if audios:
        entry['audio_codec'] = audios[0].get('codec_name')
    if videos:
        v = videos[0]
        entry['video_codec'] = v.get('codec_name')
        entry['width'] = v.get('width')
        entry['height'] = v.get('height')
        entry['fps'] = _rate(v.get('avg_frame_rate', ''))
        try:
            entry['frames'] = int(v['nb_read_frames'])
        except (KeyError, TypeError, ValueError):
            entry['frames'] = None
        entry['duration'] = _num(v.get('duration')) or fmt_duration
    else:
        entry['duration'] = fmt_duration
    if videos and Path(path).suffix.lower() in VIDEO_EXT:
        try:
            means = _luma_means(path)
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            entry['error'] = str(exc)[:300]
            return entry
        if means:
            entry['first_frame_black'] = means[0] < BLACK_MEAN
            entry['_all_black_first_half'] = all(m < BLACK_MEAN for m in means)
    return entry


def _media_rules(entry, failures):
    name = Path(entry['file']).name
    ext = Path(entry['file']).suffix.lower()
    if ext in MP4_EXT and entry.get('audio_codec') not in (None, 'aac'):
        _fail(failures, 'R6', f'{name}: الصوت جوه MP4 لازم يكون AAC، والملف فيه {entry["audio_codec"]}',
              'ريّن الفيديو بصوت AAC (-c:a aac) وأعد القياس')
    if ext in VIDEO_EXT and entry.get('_all_black_first_half'):
        _fail(failures, 'R6', f'{name}: أول 0.5 ثانية سودا', 'اشيل الفريمات السودا من البداية أو قدّم اللقطة')
    if ext in MP4_EXT and entry.get('video_codec') and entry.get('width') and entry.get('height'):
        if entry['width'] % 2 or entry['height'] % 2:
            _fail(failures, 'R6', f'{name}: الأبعاد {entry["width"]}x{entry["height"]} مش زوجية',
                  'اعمل scale للأبعاد لأرقام زوجية')
    if ext in VIDEO_EXT and entry.get('frames') is not None and entry.get('duration') and entry.get('fps'):
        expected = math.floor(entry['duration'] * entry['fps'] + 0.5)
        if entry['frames'] != expected:
            _fail(failures, 'R6', f'{name}: الفريمات {entry["frames"]} مش مساوية round(المدة x fps) = {expected}',
                  'راجع الترميز أو الطول وأعد القياس')


def _number_mismatches(text, probed):
    t = (text or '').translate(_DIGITS)
    out = []
    dims = {(e['width'], e['height']) for e in probed if e.get('width') and e.get('height')}
    durs = [e['duration'] for e in probed if e.get('duration') is not None]
    frames = [e['frames'] for e in probed if e.get('frames') is not None]
    fpss = [e['fps'] for e in probed if e.get('fps')]
    if dims:
        for w, h in re.findall(r'(?<!\d)(\d{3,5})\s*[x×X*]\s*(\d{3,5})(?!\d)', t):
            if (int(w), int(h)) not in dims:
                out.append(f'{w}x{h}')
    if durs:
        for v in re.findall(r'(?<![\d.])(\d+(?:\.\d+)?)\s*(?:ثانية|ثواني|ثانيه|ثوانى|seconds|secs|sec|s)(?!\w)', t, re.I):
            if not any(abs(float(v) - d) <= 0.05 for d in durs):
                out.append(f'{v} ثانية')
    if frames:
        for v in re.findall(r'(?<![\d.])(\d+)\s*(?:فريم|فريمات|frames?)(?!\w)', t, re.I):
            if int(v) not in frames:
                out.append(f'{v} فريم')
    if fpss:
        for v in re.findall(r'(?<![\d.])(\d+(?:\.\d+)?)\s*(?:fps|فريم في الثانية)(?!\w)', t, re.I):
            if not any(abs(float(v) - f) <= 0.05 for f in fpss):
                out.append(f'{v} fps')
    return out


# --------------------------------------------------------------------------- words (R7)

def _load_words(words):
    """-> (list of normalized word tokens, error|None). Accepts a path or parsed JSON."""
    if words is None:
        return None, None
    data = words
    if isinstance(words, (str, Path)):
        try:
            data = json.loads(rio.read_text_bytes(words))
        except (rio.ParamError, OSError, json.JSONDecodeError) as exc:
            return None, f'ملف الكلمات مش مقروء: {exc}'[:300]
    if isinstance(data, dict):
        data = data.get('words', [])
    if not isinstance(data, list):
        return None, 'ملف الكلمات لازم يكون قايمة'
    flat = []
    for item in data:
        if isinstance(item, dict):
            flat.extend(_tokens(str(item.get('text', ''))))
        elif isinstance(item, str):
            flat.extend(_tokens(item))
    return flat, None


def _caption_mismatch(captions, word_tokens):
    """Each caption line must be a contiguous run of the supplied words. -> list of bad lines."""
    seq = ' ' + ' '.join(word_tokens) + ' '
    bad = []
    for cap in captions:
        for seg in re.split(r'\n|\|\|?', cap):
            toks = _tokens(seg)
            if toks and (' ' + ' '.join(toks) + ' ') not in seq:
                bad.append(seg.strip()[:80])
    return bad


# --------------------------------------------------------------------------- failures

def _fail(failures, rule, detail, fix_ar):
    failures.append({'rule': rule, 'detail': detail, 'fix_ar': fix_ar})


def _mentioned(text, rec):
    low = text.lower()
    tokens = [rec.get('id'), rec.get('outcome'), Path(rec['file']).name]
    if any(t and t in text for t in tokens):
        return True
    return any(w in low or w in text for w in _MENTION_WORDS.get(rec.get('outcome'), []))


# --------------------------------------------------------------------------- check

def check(request, draft_text, evidence_paths, files, words=None):
    """Run rules R1..R9 on a draft reply. Read-only; returns a plain dict (see module doc)."""
    failures, advisories = [], []
    request = request or ''
    text = draft_text or ''
    if len(text) > MAX_DRAFT_CHARS:
        text = text[:SAMPLE_HEAD] + '\n' + text[-SAMPLE_TAIL:]
        advisories.append(f'الرد أطول من {MAX_DRAFT_CHARS} حرف: اتفحص أول {SAMPLE_HEAD} وآخر {SAMPLE_TAIL} بس')

    # R1 empty draft
    if not text.strip():
        _fail(failures, 'R1', 'الرد فاضي', 'اكتب الرد قبل الفحص')

    # Evidence envelopes (R4, R5, R7)
    evidence, envelopes = [], []
    for path in evidence_paths or []:
        rec, env = _read_evidence(path)
        evidence.append(rec)
        envelopes.append(env)

    # Media and files (R6)
    media, measured = [], False
    for raw in files or []:
        p = _expand(raw)
        if not p.exists():
            _fail(failures, 'R6', f'الملف مش موجود: {raw}', 'اتأكد من المسار أو اعمل الملف الأول')
            media.append({'file': str(p), 'error': 'missing'})
            continue
        if p.is_dir():
            media.append({'file': str(p), 'error': None, 'kind': 'dir'})
            continue
        if p.stat().st_size == 0:
            _fail(failures, 'R6', f'الملف فاضي: {p.name}', 'الملف لازم يكون فيه محتوى')
            media.append({'file': str(p), 'error': 'empty'})
            continue
        if p.suffix.lower() in MEDIA_EXT:
            entry = _probe(p)
            if entry['error']:
                _fail(failures, 'R6', f'{p.name}: القياس فشل: {entry["error"]}', 'ابعت الملف تاني أو اتأكد إن ffprobe شغال')
            else:
                measured = True
                _media_rules(entry, failures)
            media.append(entry)
        else:
            measured = True
            media.append({'file': str(p), 'error': None, 'kind': 'file'})
    probed = [m for m in media if m.get('error') is None and 'kind' not in m and 'duration' in m]
    if text.strip() and probed:
        for bad in _number_mismatches(text, probed):
            _fail(failures, 'R6', f'الرقم اللي في الرد ({bad}) مش متطابق مع الملف المقاس',
                  'صحّح الرقم من القياس نفسه')

    if text.strip():
        # R2 path rules
        paths = list(_PATH_RE.finditer(text))
        if paths:
            span = _first_line_span(text)
            first = paths[0].start()
            if span is None or not (span[0] <= first <= span[1]):
                _fail(failures, 'R2', 'أول مسار في الرد مش في أول سطر',
                      'حط المسار الرئيسي في أول سطر من الرد')
        seen = set()
        for m in paths:
            clean = _clean_path(m.group(0))
            if clean in seen:
                continue
            seen.add(clean)
            if not _expand(clean).exists():
                _fail(failures, 'R2', f'المسار اللي في الرد مش موجود على الجهاز: {clean}',
                      'اتأكد من المسار أو شيل الجملة اللي فيها المسار')

        # R3 long reply needs the done section
        nonempty = [l for l in text.splitlines() if l.strip()]
        if len(nonempty) > 8 and 'اللي اتعمل' not in text:
            _fail(failures, 'R3', f'الرد فيه {len(nonempty)} سطر ومفيهوش «اللي اتعمل»',
                  'ضيف قسم «اللي اتعمل» في نقط قصيرة في آخر الرد')

        # R8 publish-type actions need an approval mention
        if _ACTION.search(text) and not _APPROVAL.search(text):
            _fail(failures, 'R8', 'الرد فيه فعل نشر أو رفع أو مسح أو شراء أو تثبيت من غير ذكر موافقة',
                  'اكتب إن الموافقة اتاخدت بالظبط، أو شيل الفعل ده من الرد')

    # R4 / R5 evidence against done-claims
    hits = _done_hits(text)
    if hits:
        ok_evidence = any(rec['outcome'] == 'ok' for rec in evidence)
        if not ok_evidence and not measured:
            _fail(failures, 'R4', f'الرد بيقول «{hits[0]}» من غير دليل ok ولا ملف مقاس',
                  'شغّل الأمر وخلّي الناتج ok، أو قول إن الشغل لسه مش متقاس')
    for rec in evidence:
        if rec['outcome'] == 'ok':
            continue
        if hits:
            _fail(failures, 'R5', f'الرد بيقول خلص ومعاه دليل حالته {rec["outcome"]}: {Path(rec["file"]).name}',
                  'اشيل قول خلص، واكتب الحالة الحقيقية للدليل')
        elif text.strip() and not _mentioned(text, rec):
            _fail(failures, 'R5', f'الرد ماذكرش الدليل اللي حالته {rec["outcome"]}: {Path(rec["file"]).name}',
                  'اذكر حالة الدليل ده صراحة في الرد')

    # R7 burned text must come from the supplied words
    captions = []
    for env in envelopes:
        if env is not None:
            _caption_strings(env, captions)
    if captions:
        word_tokens, werr = _load_words(words) if words is not None else (None, None)
        if werr:
            _fail(failures, 'R7', werr, 'اعمل ملف الكلمات من التسجيل الحقيقي وأعد الفحص')
        elif word_tokens is None:
            advisories.append('الدليل فيه نص على الفيديو، بس ماتحددش --words فمارتفحصش')
        else:
            for bad in _caption_mismatch(captions, word_tokens):
                _fail(failures, 'R7', f'نص على الفيديو مش من ملف الكلمات: «{bad}»',
                      'استخدم الكلمات من ملف الكلمات بالحرف، أو شيل النص')

    # R9 advisory: request items should show up in the reply
    if request.strip() and text.strip():
        items = []
        for tok in _tokens(request):
            if len(tok) >= 3 and tok not in _STOP and tok not in items:
                items.append(tok)
        draft_skels = {_skel(t) for t in _tokens(text)}
        missing = [t for t in items[:12] if _skel(t) and _skel(t) not in draft_skels]
        for t in missing[:5]:
            advisories.append(f'كلمة من الطلب مش ظاهرة في الرد (قرب معناها، مش مؤكد): {t}')

    return {
        'passed': not failures,
        'failures': failures,
        'advisories': advisories,
        'evidence': [{k: v for k, v in rec.items() if k in ('file', 'id', 'outcome', 'detail')} for rec in evidence],
        'media': [{k: v for k, v in m.items() if not k.startswith('_')} for m in media],
        'critic_questions': list(CRITIC_QUESTIONS),
        'note_ar': NOTE_AR,
    }


# --------------------------------------------------------------------------- CLI

def _write_text(text):
    out = sys.stdout
    buf = getattr(out, 'buffer', None)
    data = (text + '\n')
    if buf is not None:
        buf.write(data.encode('utf-8'))
        buf.flush()
    else:
        out.write(data)


def _summary_text(result):
    lines = ['نتيجة الفحص: ' + ('✅ عدّى' if result['passed'] else '❌ فشل')]
    for f in result['failures']:
        lines.append(f'- {f["rule"]}: {f["detail"]} ← {f["fix_ar"]}')
    for a in result['advisories']:
        lines.append(f'- تنبيه: {a}')
    lines.append(result['note_ar'])
    return '\n'.join(lines)


def handler(args):
    if not (args.request or '').strip():
        return rio.fail('--request is empty', hint='اكتب الطلب كله بكلامك', code=rio.EXIT_USAGE)
    warnings = []
    try:
        draft = rio.read_text_bytes(args.draft, warnings)
    except rio.ParamError as exc:
        return rio.fail(str(exc), hint=exc.hint or 'give an existing draft file', code=rio.EXIT_USAGE)
    result = check(args.request, draft, args.evidence or [], args.files or [], words=args.words)
    result['advisories'] = list(warnings) + result['advisories']
    doc = {'ok': result['passed'], 'outcome': 'ok' if result['passed'] else 'error', **result}
    if args.text:
        _write_text(_summary_text(doc))
    else:
        rio.emit(doc, pretty=args.pretty)
    return rio.EXIT_OK if result['passed'] else rio.EXIT_ERROR


def register(subparsers):
    p = subparsers.add_parser(
        'check', help='delivery gate: check a draft reply against its evidence and measured files (read-only)',
        description='Read-only delivery gate. Exit 0 pass, 1 fail, 2 usage. It checks shape and evidence only, not truth.')
    p.add_argument('--request', required=True, help='the user request, as said')
    p.add_argument('--draft', required=True, metavar='FILE', help='the reply to check (any text encoding)')
    p.add_argument('--evidence', nargs='+', action='extend', default=[], metavar='FILE',
                   help='evidence envelope JSON files (rose.py run --out)')
    p.add_argument('--files', nargs='+', action='extend', default=[], metavar='PATH',
                   help='files the reply delivers (media is measured)')
    p.add_argument('--words', default=None, metavar='FILE', help='timed words JSON for caption checks')
    p.add_argument('--json', action='store_true', help='JSON output (default)')
    p.add_argument('--text', action='store_true', help='short Arabic summary instead of JSON')
    p.add_argument('--pretty', action='store_true', help='indent the JSON')
    rio.json_usage_errors(p)
    p.set_defaults(ext_func=handler)
    return p


def main(argv=None):
    parser = argparse.ArgumentParser(prog='rose_check')
    sub = parser.add_subparsers(dest='cmd')
    register(sub)
    args = parser.parse_args(['check'] + list(argv or []) if argv is not None else None)
    return args.ext_func(args)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
