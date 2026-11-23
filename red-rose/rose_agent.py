"""Red Rose V29 W07: understand (decode a message) and brief (route, ask-or-assume, depth-scaled plan).

Stateless and read-only: no database, no file writes, no network. Context only through ``prev``.
Data: agent/*.json and agent/*.txt (authored fresh for this item). rose_ext loads ``register``.

Public API:
    understand(text) -> {text, original, changed, fixes, kind, kind_reason, attachments}
    route(text, prev=None) -> {type, id, matched, alternative, candidates, confidence}
    brief(text, prev=None, files=None, depth='auto') -> brief dict (see references/INTERFACE.md)
    render_brief(b) -> text for the agent (approvals always on the first line)
CLI: rose.py understand "TEXT" [--json] ; rose.py brief "REQUEST" [--prev ..] [--files ..] [--depth ..] [--json|--text]
"""
from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import rose_io as rio

HERE = Path(__file__).resolve().parent
AGENT = HERE / 'agent'
ROUTING_EVALS = HERE / 'evals' / 'routing'

BUDGET = {'L0': 200, 'L1': 900, 'L2': 1800, 'L3': 2600}
K1, B = 1.2, 0.75
SAFETY_KEYS = frozenset({'audio_rights_confirmed'})   # never assumed on the owner's behalf
MEDIA_EXT = ('.mp4', '.mov', '.m4v', '.mkv', '.avi', '.webm', '.wav', '.mp3', '.m4a', '.aac',
             '.png', '.jpg', '.jpeg', '.webp')
OUTWARD = ('publish', 'paid', 'network', 'install')
UNREADY = ('unavailable_here', 'pc_only', 'known_broken')

_DIAC = re.compile('[ً-ٰٟـ]')
_FOLD = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ة': 'ه', 'ؤ': 'و', 'ئ': 'ي'})
_ARABIC_RUN = re.compile(r'[؀-ۿ]+')
_WORD = re.compile(r'[؀-ۿa-z0-9]+')
_PREFIXES = ('وال', 'بال', 'كال', 'فال', 'لل', 'ال', 'و', 'ب', 'ل', 'ف', 'ك')
_AR_DIACRITICS = 'ً-ْٰ'
_LATIN_CORE = re.compile(r"[A-Za-z\[\];',./`" + _AR_DIACRITICS + "]+")
_LATIN_LETTER = re.compile(r"[A-Za-z\[\];',./`]")
_LEAD = re.compile(r"^[^A-Za-z\[\];',./`]*")
_AR_LETTER = re.compile('[ء-ي]')   # native Arabic letters (diacritics excluded)
# Bigrams that dominate English words. A Latin token that is mostly made of them reads as English.
_EN_BIGRAMS = frozenset(
    'th he in er an re on at en nd ti es or te of ed is it al ar st to nt ng se ha as ou io le ve '
    'co me de hi ri ro ic ne ea ra ce li ch ll be ma si om ur el ta ly ca lo fo no pr ac'.split())
FALLBACK_MIN_SCORE = None   # router: score a lone candidate needs to be answered (None = abstain, as before)
EN_LIKE = 0.4     # share of English bigrams at or above which a Latin token is English
AR_LIKE = 0.15    # share at or below which a Latin token (3+ letters) is layout-typed Arabic evidence
_URL = re.compile(r'(://|^www\.)', re.I)
_DOMAIN = re.compile(r'^[\w-]+\.(com|net|org|io|dev|co|me|ly|be|ai)(/\S*)?$', re.I)
_FILE_EXT = re.compile(r'[A-Za-z][^\s]*\.[A-Za-z0-9]{1,5}$')
_NEVER_CHARS = frozenset('\\:@=?#%+&*<>|~"_')   # '/' is a layout key (ظ); paths are caught by _never_decode
_ATTACH = re.compile(r'\[مرفق:\s*([^\]]*)\]')
_CLAUDE_CODE = re.compile(r'^\s*🔗\s*من Claude Code\s*[:：]?\s*')
_SECONDS = re.compile(r'([0-9٠-٩]+)\s*(?:ثانيه|ثانية|ثواني|ثوانى|seconds?|sec)', re.I)
_BY_NAME = re.compile(r'(?:باسم|بعنوان)\s+(.+)$')

_CACHE: dict = {}


# ----------------------------------------------------------------------------- data

def _json(name):
    key = ('json', name)
    if key not in _CACHE:
        _CACHE[key] = json.loads((AGENT / name).read_text(encoding='utf-8-sig'))
    return _CACHE[key]


def _lexicon(name, lower=False):
    key = ('lex', name)
    if key not in _CACHE:
        words = set()
        for line in (AGENT / name).read_text(encoding='utf-8-sig').splitlines():
            item = line.split('#', 1)[0].strip()
            if item:
                words.add(fold(item).lower() if lower else fold(item))
        _CACHE[key] = words
    return _CACHE[key]


def _layout():
    return _json('layout_map.json')


def _commands():
    return {c.lower() for c in _layout()['commands']}


def _en_words():
    return _lexicon('lexicon_en.txt', lower=True) | _commands()


def _dictation():
    key = ('dict',)
    if key not in _CACHE:
        _CACHE[key] = {fold(k): v for k, v in _json('dictation.json')['stems'].items()}
    return _CACHE[key]


# ----------------------------------------------------------------------------- text helpers

def fold(text):
    """Arabic folding: diacritics and tatweel out; alef variants, ya, ta marbuta, waw/ya hamza unified."""
    s = unicodedata.normalize('NFKC', str(text or ''))
    return _DIAC.sub('', s).translate(_FOLD)


def _stems(word):
    """[word] plus the word without its first known prefix (remainder at least 3 letters)."""
    out = [word]
    for prefix in _PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 3:
            out.append(word[len(prefix):])
            break
    return out


def _term(word):
    """Route term: prefix-stripped stem, with known dictation slips corrected (same rule as understand)."""
    stem = _stems(word)[-1]
    fixed = _dictation().get(stem)
    return _term_plain(fold(fixed)) if fixed else stem


def _term_plain(word):
    return _stems(word)[-1] if len(word) > 3 else word


def _terms(text):
    """Normalised route terms of a text (folded, prefix-stripped, single letters dropped)."""
    out = []
    for w in _WORD.findall(fold(text).lower()):
        if len(w) < 2 and not w.isdigit():
            continue
        out.append(_term(w))
    return out


def _stopwords():
    key = ('stop',)
    if key not in _CACHE:
        raw = _json('synonyms.json')['stopwords']
        _CACHE[key] = {t for w in raw for t in _terms(w)}
    return _CACHE[key]


def _syn_map():
    key = ('syn',)
    if key not in _CACHE:
        table = {}
        for k, values in _json('synonyms.json')['terms'].items():
            table.setdefault(_term(fold(k).lower()), []).extend(_term(fold(v).lower()) for v in values)
        try:
            import rose_catalog
            for k, values in (rose_catalog.load().get('synonyms') or {}).items():
                table.setdefault(_term(fold(k).lower()), []).extend(
                    _term(fold(v).lower()) for v in values)
        except Exception:  # catalogue missing: the owner synonyms still apply
            pass
        _CACHE[key] = table
    return _CACHE[key]


# ----------------------------------------------------------------------------- understand

def _never_decode(chunk):
    if any(ch.isdigit() for ch in chunk):
        return True
    if _URL.search(chunk) or chunk.startswith('-') or chunk.count('/') >= 2:
        return True
    if any(ch in _NEVER_CHARS for ch in chunk):
        return True
    return bool(_FILE_EXT.search(chunk))


def _mappable(core):
    """(c) every character of the token maps through the Arabic-101 table (diacritics pass through)."""
    not_decoded = set(_layout().get('shift_not_decoded', []))
    if any(ch in not_decoded for ch in core):
        return False
    return bool(_LATIN_LETTER.search(core))


def _decode_core(core):
    layout = _layout()
    mapping, shift = layout['map'], layout.get('shift', {})
    caps_lock = core.isupper() and sum(c.isalpha() for c in core) >= 2   # all caps: Caps Lock slip, lowercase keys
    out = []
    for ch in core:
        if ch.isupper() and ch in shift and not caps_lock:
            out.append(shift[ch])
        elif ch.lower() in mapping:
            out.append(mapping[ch.lower()])
        else:
            out.append(ch)   # Arabic diacritic typed inside the token
    return ''.join(out)


def _decoded_ok(decoded):
    """A decoded token is a known Arabic word (folded; prefix-aware for longer words)."""
    lex = _lexicon('lexicon_ar.txt')
    folded = fold(decoded)
    if len(folded) <= 4:
        return folded in lex
    return any(s in lex for s in _stems(folded))


def _en_likeness(core):
    """Share of adjacent letter pairs that are common English bigrams; None under two letters."""
    letters = ''.join(c for c in core.lower() if 'a' <= c <= 'z')
    pairs = [letters[k:k + 2] for k in range(len(letters) - 1)]
    if not pairs:
        return None, letters
    return sum(p in _EN_BIGRAMS for p in pairs) / len(pairs), letters


def _kind_phrases(section):
    return [' '.join(_WORD.findall(fold(p).lower())) for p in _json('kinds.json')[section]]


def _has_work_hint(text):
    hints = {fold(h).lower() for h in _json('kinds.json')['work_hints']}
    return any(s in hints for w in _WORD.findall(fold(text).lower()) for s in _stems(w))


def _kind(text):
    t = text.strip()
    if not t:
        return 'task', 'empty message'
    if len(t.split()) == 1 and (_URL.search(t) or _DOMAIN.match(t)):
        return 'link', 'the whole message is a link'
    words = _WORD.findall(fold(t).lower())
    joined = ' '.join(words)
    padded = f' {joined} '
    hints = {fold(h).lower() for h in _json('kinds.json')['work_hints']}
    has_hint = any(s in hints for w in words for s in _stems(w))
    for phrase in _kind_phrases('continue'):
        if joined == phrase:
            return 'continue', f'continue word: {phrase}'
    for phrase in _kind_phrases('status'):
        if phrase and f' {phrase} ' in padded:
            return 'status', f'status phrase: {phrase}'
    for phrase in _kind_phrases('complaint'):
        if phrase and f' {phrase} ' in padded:
            return 'complaint', f'complaint phrase: {phrase}'
    if not has_hint:
        for phrase in _kind_phrases('greet'):
            if phrase and padded.startswith(f' {phrase} ') and len(words) <= 10:
                return 'greet', f'greet phrase at the start: {phrase}'
        for phrase in _kind_phrases('thanks'):
            if phrase and padded.startswith(f' {phrase} ') and len(words) <= 6:
                return 'thanks', f'thanks phrase at the start: {phrase}'
    if has_hint:
        return 'task', 'work hint present'
    return 'task', 'default: task'


def _dictation_fix(word):
    table = _dictation()
    folded = fold(word)
    if folded in table:
        return table[folded]
    for prefix in _PREFIXES:
        if folded.startswith(prefix) and len(folded) - len(prefix) >= 2:
            stem = folded[len(prefix):]
            if stem in table:
                return word[:len(prefix)] + table[stem]
            break
    return None


def understand(text):
    """Decode a message typed on the wrong keyboard layout, fix dictation slips, strip host wrappers, classify it."""
    original = '' if text is None else str(text)
    fixes, attachments = [], []
    work = original
    m = _CLAUDE_CODE.match(work)
    if m:
        fixes.append({'from': m.group(0).strip(), 'to': '', 'why': 'wrapper'})
        work = work[m.end():]

    def _attachment(mo):
        attachments.extend(p.strip() for p in mo.group(1).split(',') if p.strip())
        fixes.append({'from': mo.group(0), 'to': '', 'why': 'wrapper'})
        return ' '

    work = _ATTACH.sub(_attachment, work)
    if fixes:
        work = re.sub(r'\s+', ' ', work).strip()

    parts = re.split(r'(\s+)', work)
    en, commands = _en_words(), _commands()
    # Pass 1: weigh the whole message. Native Arabic words and layout-typed Latin tokens count for
    # Arabic; English-lexicon words and English-looking Latin tokens count for English.
    cands, ar_ev, en_ev, stop = [], 0, 0, False
    for i, chunk in enumerate(parts):
        if not chunk or chunk.isspace():
            continue
        bare = re.sub(r'^[^\w]+|[^\w]+$', '', chunk).lower()
        if stop:
            continue
        if bare in commands:
            stop = True
            continue
        if _AR_LETTER.search(chunk):
            ar_ev += 1
            continue
        lead_m = _LEAD.match(chunk)
        rest = chunk[lead_m.end():]
        core_m = _LATIN_CORE.match(rest)
        if not core_m or _never_decode(chunk):
            continue
        core = core_m.group(0)
        if not _mappable(core):
            continue
        trail = rest[len(core):]
        core_key = core.lower().rstrip(",.;/'`")
        if core_key in en:
            en_ev += 1
            continue
        score, letters = _en_likeness(core)
        if score is not None and len(letters) >= 4 and score >= EN_LIKE:
            en_ev += 1
            continue
        if score is not None and len(letters) >= 3 and score <= AR_LIKE:
            ar_ev += 1
        cands.append((i, lead_m.group(0), core, trail, chunk))
    # Pass 2 (majority rule): decode only when the message as a whole reads as Arabic.
    for i, lead, core, trail, chunk in cands:
        decoded = _decode_core(core)
        # message reads as Arabic: decode. No English evidence at all: decode only a known Arabic word.
        if ar_ev > en_ev or (en_ev == 0 and _decoded_ok(decoded)):
            replacement = lead + decoded + trail
            parts[i] = replacement
            fixes.append({'from': chunk, 'to': replacement, 'why': 'layout'})

    # dictation: Arabic words after decoding (stem-level, prefix-aware)
    for i, chunk in enumerate(parts):
        if not chunk or chunk.isspace() or not _ARABIC_RUN.search(chunk):
            continue
        new_chunk = chunk
        for mo in _ARABIC_RUN.finditer(chunk):
            word = mo.group(0)
            fixed = _dictation_fix(word)
            if fixed and fixed != word:
                new_chunk = new_chunk.replace(word, fixed, 1)
                fixes.append({'from': word, 'to': fixed, 'why': 'dictation'})
        parts[i] = new_chunk

    text_out = ''.join(parts)
    kind, reason = _kind(text_out)
    return {'text': text_out, 'original': original, 'changed': text_out != original,
            'fixes': fixes, 'kind': kind, 'kind_reason': reason, 'attachments': attachments}


# ----------------------------------------------------------------------------- route index

def _doc(kind, ident, fields):
    tf, length = Counter(), 0.0
    for values, weight in fields:
        for value in values:
            for term in _terms(value):
                if term in _stopwords():
                    continue
                tf[term] += weight
                length += weight
    return {'kind': kind, 'id': ident, 'tf': tf, 'len': length}


def _index():
    if 'index' in _CACHE:
        return _CACHE['index']
    import rose_recipes
    docs = []
    for rec in rose_recipes.load_all():
        if rec.get('status') != 'ready':
            continue
        docs.append(_doc('recipe', rec['id'], [
            (rec.get('when') or [], 3.0), (rec.get('tags') or [], 2.5),
            ([rec.get('title_ar', ''), rec.get('title_en', '')], 3.0)]))
    try:
        import rose_catalog
        for op_id, entry in rose_catalog.load()['entries'].items():
            docs.append(_doc('op', op_id, [
                ([entry.get('name_ar', '')], 3.0), ([entry.get('name_en', '')], 2.0),
                (entry.get('keywords') or [], 2.0), ([entry.get('summary', '')], 1.0)]))
    except Exception:  # catalogue unavailable: recipes still route
        pass
    df = Counter()
    for d in docs:
        df.update(d['tf'].keys())
    avgdl = sum(d['len'] for d in docs) / max(1, len(docs))
    examples = []
    for ex in _json('route_examples.json')['examples']:
        examples.append({'text': ex['text'], 'terms': set(t for t in _terms(ex['text']) if t not in _stopwords()),
                         'expect': ex['expect'], 'measure': ex.get('measure', True)})
    _CACHE['index'] = {'docs': docs, 'df': df, 'avgdl': avgdl or 1.0, 'N': len(docs), 'examples': examples}
    return _CACHE['index']


def _here(kind, ident):
    """(usable_here, reason) for a recipe or op id."""
    key = ('here', kind, ident)
    if key in _CACHE:
        return _CACHE[key]
    try:
        if kind == 'recipe':
            import rose_recipes
            ok, missing = rose_recipes.usable_here(rose_recipes.get(ident))
            result = (ok, 'ready here' if ok else 'missing here: ' + ', '.join(missing))
        else:
            import rose_env
            label = rose_env.readiness(ident)
            ok = label is not None and label not in UNREADY
            result = (ok, label or 'unknown op')
    except Exception as exc:  # readiness unknown: say so, do not hide the candidate
        result = (True, f'not checked: {type(exc).__name__}')
    _CACHE[key] = result
    return result


def _route_scores(text, exclude=None):
    idx = _index()
    q_all = [t for t in _terms(text) if t not in _stopwords()]
    q_orig = list(dict.fromkeys(q_all))
    if not q_orig:
        return [], {}, {}
    qweights = {t: 1.0 for t in q_orig}
    syn = _syn_map()
    for t in q_orig:
        for e in syn.get(t, []):
            if e and e not in qweights and e not in _stopwords():
                qweights[e] = 0.6
    qset = set(q_orig)
    votes, strong = Counter(), {}
    for ex in idx['examples']:
        if exclude is not None and ex['text'] == exclude:
            continue
        union = qset | ex['terms']
        if not union:
            continue
        sim = len(qset & ex['terms']) / len(union)
        if sim < 0.3:
            continue
        votes[ex['expect']] += sim * sim
        strong[ex['expect']] = max(strong.get(ex['expect'], 0.0), sim)
    scored = []
    N, avgdl, df = idx['N'], idx['avgdl'], idx['df']
    for d in idx['docs']:
        lex, hits = 0.0, []
        for term, weight in qweights.items():
            f = d['tf'].get(term)
            if not f:
                continue
            n_t = df[term]
            idf = math.log(1 + (N - n_t + 0.5) / (n_t + 0.5))
            lex += weight * idf * f * (K1 + 1) / (f + K1 * (1 - B + B * d['len'] / avgdl))
            hits.append(term)
        key = f"{d['kind']}:{d['id']}"
        vote = votes.get(key, 0.0)
        if lex <= 0 and vote <= 0:
            continue
        score = lex + 4.0 * vote
        if strong.get(key, 0.0) >= 0.9:   # near-exact match to a known example outranks lexical overlap
            score += 10.0
        if d['kind'] == 'recipe':
            score *= 1.15
        scored.append({'key': key, 'type': d['kind'], 'id': d['id'], 'score': score,
                       'hits': sorted(hits), 'strong': strong.get(key, 0.0)})
    return scored, strong, votes


def _route(text, exclude=None):
    scored, strong, votes = _route_scores(text, exclude)
    if strong.get('none', 0.0) >= 0.5 and strong.get('none', 0.0) >= max(
            [strong.get(c['key'], 0.0) for c in scored] or [0.0]):
        return _none_result(scored)
    for c in scored:
        usable, _ = _here(c['type'], c['id'])
        c['here'] = usable
        if not usable:
            c['score'] *= 0.5
    scored.sort(key=lambda c: (-round(c['score'], 9), c['type'] != 'recipe', c['id']))
    accepted = [c for c in scored if len(c['hits']) >= 2 or c['strong'] >= 0.5]
    candidates = [{'id': c['id'], 'type': c['type'], 'score': round(c['score'], 3), 'here': c['here']}
                  for c in scored[:3]]
    if not accepted:
        # no candidate has two shared terms or a near-exact example: answer with the best one only when it is strong enough
        if not scored or FALLBACK_MIN_SCORE is None or scored[0]['score'] < FALLBACK_MIN_SCORE:
            return _none_result(scored)
        accepted = scored[:1]
    top = accepted[0]
    alt = accepted[1] if len(accepted) > 1 and accepted[1]['score'] >= 0.85 * top['score'] else None
    return {'type': top['type'], 'id': top['id'], 'matched': top['hits'],
            'alternative': ({'id': alt['id'], 'type': alt['type']} if alt else None),
            'candidates': candidates, 'confidence': _confidence()}


def _none_result(scored):
    return {'type': 'none', 'id': None, 'matched': [], 'alternative': None,
            'candidates': [{'id': c['id'], 'type': c['type'], 'score': round(c['score'], 3),
                            'here': c.get('here', True)} for c in scored[:3]],
            'confidence': _confidence()}


def _confidence():
    freeze, report = ROUTING_EVALS / 'FREEZE.json', ROUTING_EVALS / 'REPORT.json'
    if freeze.is_file() and report.is_file():
        try:
            return json.loads(report.read_text(encoding='utf-8-sig')).get('tier', 'measured')
        except (OSError, json.JSONDecodeError):
            return 'unmeasured'
    return 'unmeasured'


# ----------------------------------------------------------------------------- V41 intent cards

INTENT_WEIGHT = 2.0      # how much one unit of intent evidence counts against lexical/example score
INTENT_MIN = 1.2         # combined score a winning adapter needs; below it the router abstains
GATE_RATIO = 2.0         # in-scope intent evidence must be this many times the outward evidence...
GATE_MIN_IN = 3.0        # ...and at least this much, or an outward request is refused


def _intents():
    """Intent cards from agent/intents.json: adapter -> default op + cue term tuples, with idf over adapters."""
    if 'intents' in _CACHE:
        return _CACHE['intents']
    raw = _json('intents.json')['intents']
    stop = _stopwords()
    cards, df = {}, Counter()
    for label, card in raw.items():
        cues = []
        for cue in card.get('cues', []):
            terms = tuple(dict.fromkeys(t for t in _terms(cue) if t not in stop))
            if terms:
                cues.append(terms)
        cards[label] = {'op': card.get('op'), 'cues': cues}
        df.update({t for c in cues for t in c})
    n = max(1, len(cards))
    idf = {t: math.log(1 + n / c) for t, c in df.items()}
    _CACHE['intents'] = {'cards': cards, 'idf': idf}
    return _CACHE['intents']


def _intent_scores(text):
    data = _intents()
    q = set(t for t in _terms(text) if t not in _stopwords())
    out = {}
    for label, card in data['cards'].items():
        score, hits = 0.0, []
        for cue in card['cues']:
            if all(t in q for t in cue):
                w = sum(data['idf'].get(t, 1.0) for t in cue) / len(cue)
                score += w * (1.5 * len(cue) if len(cue) > 1 else 1.0)
                hits.append(' '.join(cue))
        if score > 0:
            out[label] = (score, hits)
    return out


def _label_for(kind, ident):
    """Adapter label of a recipe or op id (recipe -> its first step op -> longest intent prefix)."""
    key = ('label', kind, ident)
    if key in _CACHE:
        return _CACHE[key]
    op = ident
    if kind == 'recipe':
        try:
            import rose_recipes
            steps = rose_recipes.get(ident).get('steps', [])
            op = steps[0].get('op', ident) if steps else ident
        except Exception:
            op = ident
    cards = _intents()['cards']
    cand = op
    while cand and cand not in cards:
        cand = cand.rsplit('.', 1)[0] if '.' in cand else ''
    _CACHE[key] = cand or None
    return _CACHE[key]


def _route_v41(text):
    """Combine intent-card evidence with the lexical/example router, per adapter."""
    scored, strong, votes = _route_scores(text)
    intents = _intent_scores(text)
    by_label = {}
    for c in scored:
        lab = _label_for(c['type'], c['id'])
        if not lab:
            continue
        best = by_label.get(lab)
        if best is None or c['score'] > best['score']:
            by_label[lab] = c
    totals = {}
    for lab in set(by_label) | set(intents):
        lex = by_label[lab]['score'] if lab in by_label else 0.0
        ev = intents.get(lab, (0.0, []))[0]
        totals[lab] = lex + INTENT_WEIGHT * ev
    if strong.get('none', 0.0) >= 0.5:
        totals['none'] = totals.get('none', 0.0) + 10.0
    # out-of-scope gate: an outward action (money, booking, reminder, calling someone, news...) makes
    # the router abstain unless the in-scope evidence is clearly stronger than the outward one
    none_ev = intents.get('none', (0.0, []))[0]
    in_ev = max([v[0] for k, v in intents.items() if k != 'none'] or [0.0])
    outward = none_ev > 0 and not (in_ev >= GATE_RATIO * none_ev and in_ev >= GATE_MIN_IN)
    ranked = sorted(totals.items(), key=lambda kv: (-round(kv[1], 9), kv[0]))

    def concrete(lab):
        if lab in by_label:
            c = by_label[lab]
            return {'id': c['id'], 'type': c['type'], 'hits': c['hits']}
        op = _intents()['cards'][lab]['op']
        return {'id': op, 'type': 'op', 'hits': []} if op else None

    candidates = []
    for lab, sc in ranked:
        if lab == 'none':
            continue
        cc = concrete(lab)
        if cc:
            candidates.append({'id': cc['id'], 'type': cc['type'], 'score': round(sc, 3),
                               'here': _here(cc['type'], cc['id'])[0]})
        if len(candidates) == 3:
            break
    if outward or not ranked or ranked[0][0] == 'none' or ranked[0][1] < INTENT_MIN:
        return {'type': 'none', 'id': None, 'matched': [], 'alternative': None,
                'candidates': candidates, 'confidence': _confidence()}
    lab, top = ranked[0]
    cc = concrete(lab)
    alt = None
    if len(ranked) > 1 and ranked[1][0] != 'none' and ranked[1][1] >= 0.85 * top:
        a = concrete(ranked[1][0])
        alt = {'id': a['id'], 'type': a['type']} if a else None
    return {'type': cc['type'], 'id': cc['id'],
            'matched': sorted(set(cc['hits']) | set(intents.get(lab, (0, []))[1])),
            'alternative': alt, 'candidates': candidates, 'confidence': _confidence()}


def route(text, prev=None):
    """Route a request to a recipe or catalogue op, or abstain (type 'none')."""
    # Decode a message typed on the wrong layout first: the index is Arabic (dialect, MSA and English terms).
    text = understand(text or '')['text']
    result = _route_v41(text)
    if result['type'] == 'none' and prev:
        fallback = _route_v41(f'{prev} {text or ""}')
        if fallback['type'] != 'none':
            fallback['used_context'] = True
            return fallback
    return result


# ----------------------------------------------------------------------------- brief helpers

def _rose_cmd():
    import rose_run as R
    return R.ROSE_CMD


def _rose_cmd_cached():
    try:
        return _rose_cmd()
    except Exception:
        return ''


def _approvals(text, rec):
    """Ordered approvals: write (from recipe steps), then outward words."""
    found = []
    if rec:
        if any(_is_write(s) for s in rec.get('steps', [])):
            found.append('write')
    t = fold(text).lower()
    words = set(_WORD.findall(t))
    stems = {s for w in words for s in _stems(w)}
    kinds = _json('kinds.json')['approval_words']
    for cat in ('publish', 'network', 'paid', 'install'):
        for phrase in kinds.get(cat, []):
            pf = fold(phrase).lower()
            hit = (pf in t) if any(ch in pf for ch in ' ./:') else (pf in words or pf in stems)
            if hit:
                if cat not in found:
                    found.append(cat)
                break
    order = ['write', 'network', 'paid', 'install', 'publish']
    return sorted(found, key=order.index)


def _is_write(step):
    return step.get('effect') == 'write' or bool(step.get('approval'))


def _input_value(key, spec, text, attachments):
    typ = spec.get('type', 'string')
    low = key.lower()
    if 'csv' in low or low.endswith('_csv'):
        hint = 'ledger' if 'ledger' in low else ('bank' if 'bank' in low else '')
        for name in attachments:
            if name.lower().endswith('.csv') and hint and hint in name.lower():
                return name
        return None
    if typ == 'json_file' or 'words' in low:
        for name in attachments:
            if name.lower().endswith('.json'):
                return name
        return None
    if typ == 'path':
        for name in attachments:
            if name.lower().endswith(MEDIA_EXT):
                return name
        return None
    if typ in ('number', 'integer') and ('duration' in low or 'max' in low):
        mo = _SECONDS.search(text)
        if mo:
            digits = mo.group(1).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
            return int(digits) if typ == 'integer' or digits.isdigit() else float(digits)
        return None
    if low == 'text' or low.endswith('_text'):
        mo = _BY_NAME.search(text)
        return mo.group(1).strip() if mo else None
    return None


def _slots(rec, text, attachments, optout):
    known, assumed, missing = [], [], []
    if not rec:
        return {'known': known, 'assumed': assumed, 'missing': missing}, [], {}
    must, values = [], {}
    for spec in rec.get('inputs', []):
        key = spec['key']
        value = _input_value(key, spec, text, attachments)
        required = bool(spec.get('required'))
        impact = 3 if required else 1
        redo = 2 if spec.get('redo') else 1
        if value is not None:
            known.append({'param': key, 'value': value, 'from': 'attachment' if isinstance(value, str)
                          and value in attachments else 'text'})
            values[key] = value
            continue
        if spec.get('default') is not None:
            assumed.append({'param': key, 'value': spec['default']})
            values[key] = spec['default']
            continue
        entry = {'param': key, 'risk': impact * 3}
        if optout and key not in SAFETY_KEYS and not required:
            continue
        if optout and key not in SAFETY_KEYS and required:
            assumed.append({'param': key, 'value': 'اختار أنا من مجلد الشغل'})
            continue
        missing.append(entry)
        if impact * 3 >= 6 or (impact * 3 >= 4 and redo >= 2):
            must.append({'param': key, 'question_ar': spec.get('question_ar', 'محتاج ' + key + '؟'),
                         'suggest_ar': spec.get('suggest_ar', ''), 'risk': impact * 3})
    must.sort(key=lambda m: -m['risk'])
    for m in must:
        m.pop('risk', None)
    return {'known': known, 'assumed': assumed, 'missing': missing}, must[:3], values


def _owner_rules(ids, approvals, must_ask, outward, is_write):
    rules = {r['id']: r for r in _json('owner_rules.json')['rules']}
    chosen = ['never_retype', 'example_only_never_delivered', 'measured_not_claimed']
    if is_write:
        chosen += ['approval_before_write', 'original_untouched']
    if approvals:
        chosen.append('continue_approves_nothing')
    if outward:
        chosen.append('no_outward_action')
    if must_ask:
        chosen.append('ask_once')
    chosen += [i for i in ids if i in rules]
    out, seen = [], set()
    for rid in chosen:
        if rid in rules and rid not in seen:
            seen.add(rid)
            out.append({'id': rid, 'text_ar': rules[rid]['text_ar']})
    return out


def _lessons(text, rec):
    request = set(_terms(text))
    if rec:
        request |= set(_terms(' '.join((rec.get('tags') or []) + [rec.get('title_ar', '')])))
    scored = []
    for lesson in _json('lessons.json')['lessons']:
        tags = set()
        for tag in lesson.get('tags', []):
            tags.update(_terms(tag))
        overlap = len(request & tags)
        if overlap:
            scored.append((-overlap, lesson['id'], lesson['lesson_ar']))
    scored.sort()
    return [{'id': lid, 'lesson_ar': txt} for _, lid, txt in scored[:3]]


def _short(text, limit=160):
    text = ' '.join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


# ----------------------------------------------------------------------------- brief

def _base(u, kind, depth, note=''):
    return {
        'understood': {'text': u['text'], 'fixes': u['fixes']},
        'kind': kind, 'depth': depth, 'approvals': [],
        'first_reply_ar': {'understood': 'فهمت إنك عايز: ' + _short(u['text']), 'will_do': [], 'estimate_min': 0},
        'route': {'type': 'none', 'id': None, 'matched': [], 'alternative': None, 'candidates': [],
                  'confidence': _confidence()},
        'slots': {'known': [], 'assumed': [], 'missing': []}, 'must_ask': [], 'decision': 'none',
        'steps': [], 'verify': [], 'done_when_ar': '', 'rules': [], 'lessons': [], 'readiness': [],
        'here': {'usable': True, 'reason': ''}, 'nearest': [], 'next_command': None, 'note_ar': note,
        'attachments': u.get('attachments', []), 'used_context': False, 'chars': 0,
    }


def _steps_for(rec, values, decision):
    """Per-step commands. Write steps lose --approve-write (exit 3 first); the rerun line keeps it."""
    out = []
    plan = []
    if decision not in ('ask', 'none'):
        try:
            import rose_recipes
            plan = rose_recipes.plan(rec['id'], inputs=values, work='<work>')
        except Exception:  # bad input value: steps stay visible without commands
            plan = []
    by_n = {p['n']: p for p in plan}
    for step in rec.get('steps', []):
        n = step['n']
        gate = ' / '.join(g.get('text_ar', '') for g in step.get('gate', []))
        item = {'n': n, 'do_ar': step.get('do_ar', ''), 'command': None, 'params_file_content': None,
                'effect': 'write' if _is_write(step) else 'read', 'gate_ar': gate,
                'rerun_with_approval': None}
        if n in by_n:
            cmd = by_n[n]['command']
            base = cmd.replace(' --approve-write', '')
            item['command'] = base
            item['params_file_content'] = by_n[n]['params_file_content']
            if _is_write(step):
                item['rerun_with_approval'] = base + ' --approve-write'
        out.append(item)
    return out


def _fit(b, render):
    budget = BUDGET[b['depth']]
    text = render(b)
    if len(text) > budget:
        b['lessons'] = []
        text = render(b)
    if len(text) > budget:
        b['rules'] = b['rules'][:3]
        for step in b['steps']:
            step['do_ar'] = _short(step['do_ar'], 80)
        text = render(b)
    if len(text) > budget:
        text = text[:budget - 1] + '…'
    b['chars'] = len(text)
    return text


def brief(text, prev=None, files=None, depth='auto'):
    """Brief for one request: understanding, route, decision, steps. Stateless; prev is the earlier message."""
    u = understand(text)
    prev_u = understand(prev) if prev else None
    attachments = list(u['attachments']) + [f for f in (files or []) if f]
    kind = u['kind']
    optout = any(fold(p).lower() in fold(u['text']).lower() for p in _json('optout_phrases.json')['phrases'])
    fixed_depth = depth if depth in ('0', '1', '2', '3') else None

    if kind in ('greet', 'thanks'):
        b = _base(u, kind, 'L0', 'رد عادي بالمصري، من غير خطة ولا أدوات.')
        b['first_reply_ar']['understood'] = 'فهمت إنك بتقول: ' + _short(u['text'], 60)
        b['decision'] = 'none'
    elif kind in ('continue', 'complaint', 'status') and not prev_u:
        b = _base(u, kind, 'L0', 'ابعتلي رسالتك اللي قبل دي عشان أعرف أكمل على إيه.')
        b['decision'] = 'ask'
    elif kind == 'link':
        b = _base(u, kind, 'L0', 'الرابط ده محتاج موافقتك قبل أي تحميل أو فتح. قولّي تعمل بيه إيه.')
        b['decision'] = 'ask'
        b['approvals'] = ['network']
    else:
        b = _task_brief(u, kind, prev_u, attachments, optout)

    if fixed_depth is not None:
        b['depth'] = 'L' + fixed_depth
    b['attachments'] = attachments
    b['depth'] = b['depth'] if b['depth'] in BUDGET else 'L3'
    text_out = _fit(b, render_brief)
    b['text'] = text_out
    return b


def _task_brief(u, kind, prev_u, attachments, optout):
    # follow-ups (continue, complaint, status) and delegations («نفذ اللي تشوفه») take their topic from prev
    used_context = prev_u is not None and (kind in ('continue', 'complaint', 'status') or optout)
    source_text = prev_u['text'] if used_context else u['text']
    r = route(source_text) if used_context else route(u['text'], prev=prev_u['text'] if prev_u else None)
    r['used_context'] = used_context
    rec = None
    if r['type'] == 'recipe':
        import rose_recipes
        rec = rose_recipes.get(r['id'])
    approvals = _approvals(u['text'], rec)
    outward = [a for a in approvals if a in OUTWARD]
    slots, must, values = _slots(rec, source_text, attachments, optout)

    if r['type'] == 'none':
        decision = 'none'
    elif must:
        decision = 'ask'
    elif outward:
        decision = 'confirm'
    elif slots['assumed']:
        decision = 'go_with_assumptions'
    else:
        decision = 'go'

    n_steps = len(rec['steps']) if rec else 0
    if r['type'] == 'recipe':
        steps = _steps_for(rec, {k: v for k, v in values.items()}, decision)
        verify = [f'{_rose_cmd()} check --request "<request>" --draft <reply.txt> --evidence <work>/step.json']
        done = rec.get('deliver_ar', '')
        rule_ids = list(rec.get('rules', []))
        readiness = []
        for step in rec['steps']:
            try:
                import rose_env
                readiness.append({'id': step['op'], 'label': rose_env.readiness(step['op'])})
            except Exception:
                readiness.append({'id': step['op'], 'label': None})
        usable, reason = _here('recipe', r['id'])
        here = {'usable': usable, 'reason': reason}
        will = [s['do_ar'] for s in steps][:5]
        estimate = 2 + 2 * n_steps
        depth = 'L1' if (n_steps <= 1 and not approvals and decision == 'go') else 'L2'
        nearest = []
        title = rec.get('title_ar', rec['id'])
        note = ''
    elif r['type'] == 'op':
        op = r['id']
        steps = [{'n': 1, 'do_ar': 'أشوف الوسايط اللي المهارة محتاجاها قبل ما أشغّلها', 'command':
                  f'{_rose_cmd()} describe {op}', 'params_file_content': None,
                  'effect': 'read', 'gate_ar': '', 'rerun_with_approval': None}]
        verify = []
        done = 'الناتج اتقاس بعينك وبـ verify قبل ما أقول خلص'
        rule_ids = []
        readiness = []
        try:
            import rose_env
            readiness = [{'id': op, 'label': rose_env.readiness(op)}]
        except Exception:
            pass
        usable, reason = _here('op', op)
        here = {'usable': usable, 'reason': reason}
        will = ['أشوف وسايط المهارة وأشغّلها']
        estimate = 4
        depth = 'L2'
        nearest = []
        title = op
        note = ''
        decision = 'confirm' if outward else 'go'
    elif not _has_work_hint(source_text):
        # not work on files (a poem, weather, small talk): a short plain answer, no plan
        steps, verify, done, rule_ids, readiness = [], [], '', [], []
        here = {'usable': True, 'reason': 'not a file job'}
        will, estimate, nearest, title = [], 0, [], ''
        depth = 'L0'
        note = 'ده مش شغل على ملفات. رد عادي بالمصري، من غير خطة ولا أوامر.'
    else:
        steps, verify, done, rule_ids, readiness = [], [], '', [], []
        here = {'usable': True, 'reason': 'no route'}
        will = ['أدوّر في الكتالوج على أقرب مهارة وأخطط منها']
        estimate = 5
        depth = 'L3'
        try:
            import rose_catalog
            nearest = [{'id': h['id'], 'command': f'{_rose_cmd()} describe {h["id"]}'}
                       for h in rose_catalog.find(source_text, limit=5)]
        except Exception:
            nearest = []
        title = ''
        note = 'مفيش طريق جاهز لده. نخطط من الأوامر دي.'

    if decision == 'none' and r['type'] != 'none':
        decision = 'go'
    must_ask = must[:3]
    lessons = _lessons(source_text, rec) if depth != 'L0' else []
    rules = (_owner_rules(rule_ids, approvals, must_ask, outward, 'write' in approvals)
             if depth != 'L0' else [])
    next_cmd = None
    if decision not in ('ask',) and steps:
        next_cmd = steps[0]['command']
    if r['type'] == 'none':
        next_cmd = f'{_rose_cmd()} find "{_short(source_text, 60)}"'
    if decision == 'ask':
        next_cmd = None

    b = _base(u, kind, depth)
    b.update({
        'approvals': approvals,
        'first_reply_ar': {'understood': 'فهمت إنك عايز: ' + _short(source_text),
                           'will_do': will, 'estimate_min': estimate},
        'route': {'type': r['type'], 'id': r['id'], 'matched': r['matched'],
                  'alternative': r['alternative'], 'candidates': r['candidates'],
                  'confidence': r['confidence'], 'title_ar': title, 'used_context': used_context},
        'slots': slots, 'must_ask': must_ask, 'decision': decision, 'steps': steps,
        'verify': verify, 'done_when_ar': done, 'rules': rules, 'lessons': lessons,
        'readiness': readiness, 'here': here, 'nearest': nearest, 'next_command': next_cmd,
        'note_ar': note, 'used_context': used_context,
    })
    if used_context:
        lead = {'continue': 'فهمت إنك عايز تكمل: ', 'complaint': 'فهمت إن فيه حاجة مش مظبوطة في: ',
                'status': 'فهمت إنك عايز تعرف وصلنا فين في: '}.get(kind, 'فهمت إنك عايز: ')
        b['first_reply_ar']['understood'] = lead + _short(source_text)
    return b


def _fmt_fixes(fixes):
    shown = [f"{x['from']}←{x['to']}" for x in fixes if x.get('why') in ('layout', 'dictation') and x.get('to')]
    return '، '.join(shown[:4])


def render_brief(b):
    """Plain text for the agent: approvals first, then the understanding, route, questions and commands."""
    lines = []
    lines.append('الموافقات: ' + (' / '.join(b['approvals']) if b['approvals'] else 'لا شيء'))
    lines.append(b['first_reply_ar']['understood'])
    fixed = _fmt_fixes(b['understood']['fixes'])
    if fixed:
        lines.append('فككتها من الكيبورد/الإملاء: ' + fixed)
    if b.get('note_ar'):
        lines.append(b['note_ar'])
    route = b['route']
    if route['type'] == 'recipe':
        alt = f" · بديل: {route['alternative']['id']}" if route.get('alternative') else ''
        lines.append(f"الطريق: وصفة {route['id']} ({route.get('title_ar', '')}){alt}")
    elif route['type'] == 'op':
        lines.append(f"الطريق: مهارة {route['id']}")
    elif b['nearest']:
        lines.append('الطريق: مفيش وصفة جاهزة. ' + ' · '.join(n['id'] for n in b['nearest'][:5]))
    if route['type'] != 'none':
        lines.append('القرار: ' + b['decision'])
    for q in b['must_ask']:
        lines.append(f"سؤال: {q['question_ar']} ⭐ {q['suggest_ar']}")
    if b['slots']['assumed']:
        lines.append('افتراضات: ' + '، '.join(f"{a['param']}={a['value']}" for a in b['slots']['assumed']))
    if b['slots']['missing'] and not b['must_ask']:
        lines.append('ناقص: ' + '، '.join(m['param'] for m in b['slots']['missing']))
    if b['first_reply_ar']['will_do']:
        lines.append('هعمل: ' + ' / '.join(b['first_reply_ar']['will_do']))
    root = _rose_cmd_cached()
    short = (lambda c: c.replace(root, 'ROSE', 1)) if root else (lambda c: c)
    if any(s['command'] for s in b['steps']) and root:
        lines.append(f'ROSE = {root}')
    for s in b['steps']:
        cmd = short(s['command']) if s['command'] else '(بعد الإجابة)'
        tag = ' [بيكتب: بعد موافقتك بس]' if s['effect'] == 'write' else ''
        lines.append(f"{s['n']}. {s['do_ar']} → {cmd}{tag}")
    if b['verify']:
        lines.append('تحقق: ' + ' | '.join(short(v) for v in b['verify']))
    if b['done_when_ar']:
        lines.append('خلص لما: ' + b['done_when_ar'])
    if b['rules']:
        lines.append('قواعد: ' + ' · '.join(r['text_ar'][:90] for r in b['rules']))
    if b['lessons']:
        lines.append('دروس: ' + ' · '.join(x['lesson_ar'][:110] for x in b['lessons']))
    if b['nearest'] and route['type'] == 'none':
        lines.append('أقرب: ' + ' · '.join(n['command'] for n in b['nearest'][:3]))
    if route['type'] != 'none' or b['first_reply_ar']['estimate_min']:
        lines.append(f"⏱ التقدير ~{b['first_reply_ar']['estimate_min']} د")
    return '\n'.join(line for line in lines if line)


# ----------------------------------------------------------------------------- CLI

def _h_understand(args):
    out = understand(args.text)
    rio.emit(out)
    return 0


def _h_brief(args):
    if not (args.request or '').strip():
        return rio.fail('empty request', hint='rose.py brief "<the owner words>" [--prev "..."]')
    b = brief(args.request, prev=args.prev, files=args.files, depth=args.depth)
    b.pop('text', None)
    if args.text:
        text = render_brief(b)
        sys.stdout.buffer.write((text + '\n').encode('utf-8'))
        return 0
    rio.emit(b)
    return 0


def register(subparsers):
    p = subparsers.add_parser('understand', help='decode a message typed on the wrong keyboard layout; fix dictation; classify kind')
    p.add_argument('text', nargs='?', default='')
    p.add_argument('--json', action='store_true', help='one JSON document (the default)')
    rio.json_usage_errors(p)
    p.set_defaults(ext_func=_h_understand)

    p = subparsers.add_parser('brief', help='route a request with abstention; ask-or-assume; first reply; steps and gates')
    p.add_argument('request', nargs='?', default='')
    p.add_argument('--prev', default=None, help='the owner previous message (for follow-ups)')
    p.add_argument('--files', nargs='*', default=None, help='attached file names or paths')
    p.add_argument('--depth', default='auto', choices=['auto', '0', '1', '2', '3'])
    p.add_argument('--json', action='store_true', help='one JSON document (the default)')
    p.add_argument('--text', action='store_true', help='plain text for the agent')
    rio.json_usage_errors(p)
    p.set_defaults(ext_func=_h_brief)
