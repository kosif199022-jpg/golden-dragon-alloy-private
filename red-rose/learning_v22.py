"""Red Rose V22: evidence-tied learning helpers (topics 26.02-26.10).

Pure standard-library Python. No file I/O, no subprocess, no network, no
printing. Lessons, error logs, registries and stores arrive as in-memory
parameters (lists/dicts) and every op returns new data; nothing is persisted.

"Learning" here means recorded lessons tied to evidence (source audit ids,
defect records, measured task counts). It is never model retraining and never
an automatic code change: rule proposals stay 'pending_human_review' until a
named human reviewer records a decision, and no op emits code, diffs or patches.

Every op validates strictly (ValueError on unknown parameters, wrong types,
bools-as-numbers, out-of-range values), bounds its work, is deterministic and
returns {'op', 'result', 'assumptions', 'limits'}.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import math
import re
import unicodedata

MAX_PARAMS = 24
MAX_RECORDS = 2_000
MAX_TEXT = 4_000
MAX_LESSONS = 2_000
MAX_PLAN = 500
MAX_REGISTRY = 5_000
MAX_OPERATIONS = 1_000
MAX_TABLES = 50
MAX_ROWS = 20_000
MAX_TERMS = 50
MAX_VERSIONS = 200
MAX_RULES_JSON = 200_000
EXAMPLE_NOW = '2026-11-21'

TOPICS = {
    '26.02': 'similar_errors',
    '26.03': 'rank_lessons',
    '26.04': 'rule_proposal',
    '26.05': 'capability_gaps',
    '26.06': 'regression_from_defect',
    '26.07': 'rule_versions',
    '26.08': 'lesson_benefit',
    '26.09': 'local_only_guard',
    '26.10': 'forget_request',
}

TOPIC_NAMES_AR = {
    '26.02': 'استرجاع الأخطاء المشابهة',
    '26.03': 'ترتيب الدروس حسب الصلاحية',
    '26.04': 'تحديث الاقتراحات دون تعديل ذاتي',
    '26.05': 'اكتشاف فجوات المهارات',
    '26.06': 'بناء اختبارات من أعطال سابقة',
    '26.07': 'إدارة إصدارات نموذج القرار',
    '26.08': 'قياس فائدة الدروس',
    '26.09': 'فصل ذاكرة المستخدم عن التدريب',
    '26.10': 'نسيان معلومات حساسة عند الطلب',
}


# --------------------------------------------------------------------------- validation

def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _num(value, low, high, name, *, low_open=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise ValueError(f'{name} must be a finite number')
    value = float(value)
    if value < low or value > high or (low_open and value <= low):
        bracket = '(' if low_open else '['
        raise ValueError(f'{name} must be in {bracket}{low}, {high}]')
    return value


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _str(value, name, *, max_len=MAX_TEXT, allow_empty=False):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    if len(value) > max_len:
        raise ValueError(f'{name} must be at most {max_len} characters')
    if not allow_empty and not value.strip():
        raise ValueError(f'{name} must not be empty')
    return value


def _list(value, name, max_len, *, min_len=0):
    if not isinstance(value, (list, tuple)):
        raise ValueError(f'{name} must be a list')
    if not min_len <= len(value) <= max_len:
        raise ValueError(f'{name} must have {min_len}..{max_len} items')
    return list(value)


def _dict(value, name, required, optional=()):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be a dict')
    keys = set(value)
    if not all(isinstance(k, str) for k in keys):
        raise ValueError(f'{name} keys must be strings')
    missing = [k for k in required if k not in keys]
    if missing:
        raise ValueError(f'{name} is missing: ' + ', '.join(missing))
    unknown = keys - set(required) - set(optional)
    if unknown:
        raise ValueError(f'{name} has unknown key(s): ' + ', '.join(sorted(unknown)))
    return value


def _audit_id(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer audit id')
    return value


def _date(value, name):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be an ISO date string YYYY-MM-DD')
    try:
        return datetime.date.fromisoformat(value[:10])
    except ValueError:
        raise ValueError(f'{name} must be an ISO date string YYYY-MM-DD') from None


def _json_value(value, name, max_chars=MAX_RULES_JSON):
    try:
        text = json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError(f'{name} must be JSON-serialisable') from None
    if len(text) > max_chars:
        raise ValueError(f'{name} is too large (max {max_chars} JSON characters)')
    return text


def _sha256(value):
    return hashlib.sha256(_json_value(value, 'value', 10 ** 8).encode('utf-8')).hexdigest()


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


# --------------------------------------------------------------------------- text normalisation

_DIACRITICS = re.compile('[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]')
_LETTER_MAP = str.maketrans({'\u0623': '\u0627', '\u0625': '\u0627', '\u0622': '\u0627',
                             '\u0671': '\u0627', '\u0649': '\u064a', '\u0629': '\u0647',
                             '\u0640': None})
_TOKEN = re.compile(r'[^\W\d_]{2,}')


def normalise_text(text):
    """NFKC, strip Arabic diacritics and tatweel, unify alef/ya/ta-marbuta, casefold."""
    text = unicodedata.normalize('NFKC', text)
    text = _DIACRITICS.sub('', text).translate(_LETTER_MAP)
    return text.casefold()


def tokens(text):
    """Letter-only tokens (>= 2 letters); digits, punctuation and path separators split/drop."""
    return _TOKEN.findall(normalise_text(text))


# --------------------------------------------------------------------------- 26.02 similar_errors

_EXAMPLE_ERRORS = [
    {'signature': 'FileNotFoundError', 'message': r"No such file or directory: 'C:\work\clip_17.mp4'",
     'fix': 'check the input path exists before rendering', 'source_audit_id': 11},
    {'signature': 'UnicodeEncodeError', 'message': "'charmap' codec can't encode character '\\u0627' in position 4",
     'fix': 'run python with -X utf8', 'source_audit_id': 12},
    {'signature': 'خطأ في الترميز', 'message': 'فشل حفظ الملفّ العربيّ بسبب الترميز',
     'fix': 'افتح الملف بترميز utf-8', 'source_audit_id': 13},
]


def similar_errors(*, records=None, query=None, top_k=5, min_score=0.0, **extra):
    """Rank past error records by TF-IDF cosine similarity to a new error text.

    records: [{signature, message, fix, source_audit_id}, ...]; query: the new
    error text (signature + message). The signature is counted twice. Numbers,
    path separators and punctuation are dropped by the tokenizer so a recurring
    error with different numbers/paths still matches its earlier record.
    """
    _no_extra(extra)
    if records is None and query is None:
        records, query = _EXAMPLE_ERRORS, "UnicodeEncodeError: 'charmap' codec can't encode character in position 9"
    if records is None or query is None:
        raise ValueError('records and query are both required (or omit both for the example)')
    records = _list(records, 'records', MAX_RECORDS, min_len=1)
    query = _str(query, 'query')
    top_k = _int(top_k, 1, 100, 'top_k')
    min_score = _num(min_score, 0.0, 1.0, 'min_score')
    docs = []
    for i, rec in enumerate(records):
        _dict(rec, f'records[{i}]', ('signature', 'message', 'fix', 'source_audit_id'))
        sig = _str(rec['signature'], f'records[{i}].signature')
        msg = _str(rec['message'], f'records[{i}].message', allow_empty=True)
        _str(rec['fix'], f'records[{i}].fix', allow_empty=True)
        _audit_id(rec['source_audit_id'], f'records[{i}].source_audit_id')
        docs.append(tokens(sig) * 2 + tokens(msg))
    qtok = tokens(query)
    if not qtok:
        raise ValueError('query has no letter tokens to compare')
    n = len(docs)
    df = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1

    def vec(toks):
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        v = {t: c * (math.log((1 + n) / (1 + df.get(t, 0))) + 1.0) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values()))
        return v, norm

    qv, qn = vec(qtok)
    scored = []
    for i, d in enumerate(docs):
        dv, dn = vec(d)
        if not dn:
            continue
        dot = sum(w * dv[t] for t, w in qv.items() if t in dv)
        score = dot / (qn * dn)
        if score >= min_score and score > 0:
            scored.append((-round(score, 12), i, score, sorted(set(qv) & set(dv))))
    scored.sort()
    matches = []
    for rank, (_, i, score, shared) in enumerate(scored[:top_k], 1):
        rec = records[i]
        matches.append({'rank': rank, 'index': i, 'source_audit_id': rec['source_audit_id'],
                        'signature': rec['signature'], 'fix': rec['fix'],
                        'score': round(score, 6), 'shared_terms': shared[:20]})
    return _pack('similar_errors',
                 {'query_tokens': qtok[:50], 'records_searched': n, 'matches': matches},
                 ['bag-of-words TF-IDF cosine (smoothed idf) over letter tokens; no semantic embeddings',
                  'Arabic normalisation: diacritics/tatweel stripped, alef forms -> ا, ى -> ي, ة -> ه; casefold',
                  'digits are dropped so varying numbers/line numbers do not affect similarity; path parts '
                  'remain as tokens and can lower scores', 'signature tokens are weighted x2',
                  'a match is a retrieval hint linked to its source_audit_id, not proof the old fix applies'],
                 [f'records <= {MAX_RECORDS}, text <= {MAX_TEXT} chars per field, top_k <= 100',
                  'no stemming, no synonyms, no cross-language matching (Arabic vs English words)'])


# --------------------------------------------------------------------------- 26.03 rank_lessons

_EXAMPLE_LESSONS = [
    {'id': 'L1', 'topic': 'audio codec', 'text': 'use MP3 audio in MP4', 'created': '2026-03-01',
     'confidence': 0.6, 'confirmations': 1, 'review_by': '2027-03-01', 'source_audit_id': 3},
    {'id': 'L2', 'topic': 'audio codec', 'text': 'use AAC audio in MP4 (MP3 silent on iPhone)',
     'created': '2026-11-01', 'confidence': 0.9, 'confirmations': 3, 'review_by': '2027-05-01',
     'source_audit_id': 9},
    {'id': 'L3', 'topic': 'fonts', 'text': 'embed Arabic fonts before render', 'created': '2026-10-15',
     'confidence': 0.8, 'confirmations': 2, 'review_by': '2026-11-01', 'source_audit_id': 7},
]


def _lesson(rec, i):
    _dict(rec, f'lessons[{i}]', ('id', 'topic', 'text', 'created', 'source_audit_id'),
          ('confidence', 'confirmations', 'review_by', 'last_confirmed'))
    out = {'id': _str(rec['id'], f'lessons[{i}].id', max_len=200),
           'topic': _str(rec['topic'], f'lessons[{i}].topic', max_len=200),
           'text': _str(rec['text'], f'lessons[{i}].text'),
           'created': _date(rec['created'], f'lessons[{i}].created'),
           'source_audit_id': _audit_id(rec['source_audit_id'], f'lessons[{i}].source_audit_id'),
           'confidence': _num(rec.get('confidence', 0.5), 0.0, 1.0, f'lessons[{i}].confidence'),
           'confirmations': _int(rec.get('confirmations', 0), 0, 1_000_000, f'lessons[{i}].confirmations'),
           'review_by': None, 'last_confirmed': None}
    if rec.get('review_by') is not None:
        out['review_by'] = _date(rec['review_by'], f'lessons[{i}].review_by')
    if rec.get('last_confirmed') is not None:
        out['last_confirmed'] = _date(rec['last_confirmed'], f'lessons[{i}].last_confirmed')
    return out


def rank_lessons(*, lessons=None, now=None, half_life_days=90.0, expired_factor=0.25,
                 superseded_factor=0.5, **extra):
    """Score lessons by recency, confidence, confirmations and review validity.

    score = 0.5^(age/half_life) * (0.5 + 0.5*confidence) * (1 + ln(1+confirmations))
            * (expired_factor if review_by < now) ; normalised to the best = 1.
    Lessons sharing a normalised topic compete: the most recent evidence
    (last_confirmed or created; ties -> higher score) is 'current' and the
    others are 'superseded', scaled by superseded_factor and kept below it.
    """
    _no_extra(extra)
    if lessons is None and now is None:
        lessons, now = _EXAMPLE_LESSONS, EXAMPLE_NOW
    if lessons is None or now is None:
        raise ValueError('lessons and now (ISO date) are both required (or omit both for the example)')
    lessons = _list(lessons, 'lessons', MAX_LESSONS, min_len=1)
    today = _date(now, 'now')
    hl = _num(half_life_days, 1.0, 36_500.0, 'half_life_days')
    ef = _num(expired_factor, 0.0, 1.0, 'expired_factor')
    sf = _num(superseded_factor, 0.0, 1.0, 'superseded_factor')
    items = [_lesson(rec, i) for i, rec in enumerate(lessons)]
    ids = [it['id'] for it in items]
    if len(set(ids)) != len(ids):
        raise ValueError('lesson ids must be unique')
    rows = []
    for it in items:
        evidence = max(d for d in (it['created'], it['last_confirmed']) if d is not None)
        age = max(0, (today - evidence).days)
        recency = 0.5 ** (age / hl)
        expired = it['review_by'] is not None and it['review_by'] < today
        raw = recency * (0.5 + 0.5 * it['confidence']) * (1 + math.log1p(it['confirmations']))
        if expired:
            raw *= ef
        rows.append({'id': it['id'], 'topic': it['topic'], 'text': it['text'],
                     'source_audit_id': it['source_audit_id'], 'evidence_date': evidence.isoformat(),
                     'age_days': age, 'recency': round(recency, 6), 'expired_review': expired,
                     'status': 'current', 'raw': raw})
    groups = {}
    for r in rows:
        groups.setdefault(' '.join(tokens(r['topic'])) or normalise_text(r['topic']), []).append(r)
    conflicts = []
    for key in sorted(groups):
        grp = groups[key]
        if len(grp) < 2:
            continue
        winner = sorted(grp, key=lambda r: (r['evidence_date'], r['raw'], r['id']), reverse=True)[0]
        for r in grp:
            if r is not winner:
                r['status'] = 'superseded'
                r['superseded_by'] = winner['id']
                r['raw'] = min(r['raw'] * sf, winner['raw'] * 0.999)
        conflicts.append({'topic': key, 'current': winner['id'],
                          'superseded': sorted(r['id'] for r in grp if r is not winner)})
    best = max(r['raw'] for r in rows) or 1.0
    for r in rows:
        r['score'] = round(r.pop('raw') / best, 6) if best else 0.0
    rows.sort(key=lambda r: (-r['score'], r['id']))
    for rank, r in enumerate(rows, 1):
        r['rank'] = rank
    return _pack('rank_lessons', {'now': today.isoformat(), 'ranked': rows, 'conflicts': conflicts},
                 [f'exponential recency decay with half-life {hl:g} days from the latest evidence date',
                  'lessons with the same normalised topic are treated as competing versions; newest evidence wins',
                  f'an expired review_by multiplies the score by {ef:g}; it is demoted, not deleted',
                  'confidence and confirmations are taken as supplied; they are not re-verified here',
                  'scores are relative (best = 1) and only meaningful within one call'],
                 [f'lessons <= {MAX_LESSONS}', 'no semantic conflict detection beyond equal topics',
                  'dates are calendar days (UTC assumed), time of day ignored'])


# --------------------------------------------------------------------------- 26.04 rule_proposal

_FORBIDDEN_RULE_KEYS = {'code', 'diff', 'patch', 'edit', 'edits', 'file_changes', 'script', 'command'}
_EXAMPLE_REPEATS = [
    {'topic': 'audio codec', 'text': 'use AAC audio in MP4', 'source_audit_id': 9},
    {'topic': 'Audio  Codec', 'text': 'use AAC audio in MP4', 'source_audit_id': 14},
    {'topic': 'audio codec', 'text': 'MP3 inside MP4 is silent on iPhone, use AAC', 'source_audit_id': 21},
    {'topic': 'fonts', 'text': 'embed Arabic fonts', 'source_audit_id': 7},
]


def _check_rule(rule):
    _dict(rule, 'rule', ('rule_id', 'topic', 'statement', 'evidence_audit_ids', 'support',
                         'status', 'effect', 'review_log'))
    if _FORBIDDEN_RULE_KEYS & set(rule):
        raise ValueError('rules must not carry code or diff fields')
    _str(rule['rule_id'], 'rule.rule_id', max_len=100)
    _str(rule['topic'], 'rule.topic', max_len=200)
    _str(rule['statement'], 'rule.statement')
    for i, a in enumerate(_list(rule['evidence_audit_ids'], 'rule.evidence_audit_ids', MAX_LESSONS, min_len=1)):
        _audit_id(a, f'rule.evidence_audit_ids[{i}]')
    _int(rule['support'], 1, MAX_LESSONS, 'rule.support')
    _choice(rule['status'], {'pending_human_review', 'approved', 'rejected'}, 'rule.status')
    _choice(rule['effect'], {'advisory_only'}, 'rule.effect')
    _list(rule['review_log'], 'rule.review_log', 1_000)
    return rule


def approve(rule, reviewer, decision, note=''):
    """Record a human decision on a pending rule; returns a new rule dict (input untouched)."""
    _check_rule(rule)
    if rule['status'] != 'pending_human_review':
        raise ValueError('only a pending_human_review rule can be decided')
    reviewer = _str(reviewer, 'reviewer', max_len=200)
    decision = _choice(decision, {'approved', 'rejected'}, 'decision')
    note = _str(note, 'note', max_len=1_000, allow_empty=True)
    out = copy.deepcopy(rule)
    out['status'] = decision
    out['review_log'].append({'reviewer': reviewer.strip(), 'decision': decision, 'note': note})
    return out


def rule_proposal(*, action='propose', lessons=None, min_repeats=2, rule=None, reviewer=None,
                  decision=None, note='', **extra):
    """Turn repeated lessons into advisory rule proposals, or record a human decision.

    action='propose': lessons [{topic, text, source_audit_id}]; topics seen in
    >= min_repeats lessons from distinct audit ids become a rule with status
    'pending_human_review'. action='approve': rule + reviewer + decision
    ('approved'|'rejected') -> the same rule with the decision logged.
    Never returns code, diffs or file edits.
    """
    _no_extra(extra)
    action = _choice(action, {'propose', 'approve'}, 'action')
    if action == 'approve':
        if lessons is not None:
            raise ValueError('lessons is only used with action=propose')
        if rule is None or reviewer is None or decision is None:
            raise ValueError('action=approve requires rule, reviewer and decision')
        out = approve(rule, reviewer, decision, note)
        return _pack('rule_proposal', {'action': 'approve', 'rule': out},
                     ['the reviewer name is recorded as given; identity is not authenticated here',
                      'approval changes only the status field; applying the rule anywhere is a separate, '
                      'explicitly authorised step'],
                     ['one decision per call; an already decided rule cannot be re-decided'])
    if rule is not None or reviewer is not None or decision is not None:
        raise ValueError('rule/reviewer/decision are only used with action=approve')
    if lessons is None:
        lessons = _EXAMPLE_REPEATS
    lessons = _list(lessons, 'lessons', MAX_LESSONS, min_len=1)
    min_repeats = _int(min_repeats, 2, 1_000, 'min_repeats')
    groups = {}
    for i, rec in enumerate(lessons):
        _dict(rec, f'lessons[{i}]', ('topic', 'text', 'source_audit_id'))
        topic = _str(rec['topic'], f'lessons[{i}].topic', max_len=200)
        text = _str(rec['text'], f'lessons[{i}].text')
        aid = _audit_id(rec['source_audit_id'], f'lessons[{i}].source_audit_id')
        key = ' '.join(tokens(topic)) or normalise_text(topic).strip()
        groups.setdefault(key, []).append((text.strip(), aid))
    proposals, skipped = [], []
    for key in sorted(groups):
        items = groups[key]
        audits = sorted({a for _, a in items})
        if len(audits) < min_repeats:
            skipped.append({'topic': key, 'distinct_evidence': len(audits)})
            continue
        counts = {}
        for text, _ in items:
            counts[text] = counts.get(text, 0) + 1
        statement = sorted(counts, key=lambda t: (-counts[t], t))[0]
        rid = 'rule-' + _sha256({'topic': key, 'statement': statement, 'audits': audits})[:12]
        proposals.append({'rule_id': rid, 'topic': key, 'statement': statement,
                          'evidence_audit_ids': audits, 'support': len(audits),
                          'status': 'pending_human_review', 'effect': 'advisory_only',
                          'review_log': []})
    return _pack('rule_proposal', {'action': 'propose', 'proposals': proposals, 'below_threshold': skipped},
                 ['repetition = the same normalised topic backed by distinct source_audit_ids',
                  'the proposed statement is the most frequent lesson text verbatim; it is not rewritten',
                  'proposals are advisory text only: no code, diff or file change is ever produced',
                  'status stays pending_human_review until approve() records a human decision'],
                 [f'lessons <= {MAX_LESSONS}, min_repeats >= 2',
                  'does not judge whether repeated lessons are correct; a human reviewer must'])


# --------------------------------------------------------------------------- 26.05 capability_gaps

_NOT_IMPLEMENTED_KINDS = {'description', 'planned', 'index', 'design', 'doc'}
_EXAMPLE_REGISTRY = {
    'memory.recall': ('Recall stored lessons', 'read', 'database'),
    'learning.record': ('Store an approved lesson tied to an observed execution', 'write', 'database'),
    'video.subtitle_burn': {'description': 'Burn Arabic subtitles into video', 'implemented': False},
}


def _registry_entry(key, value):
    if isinstance(value, str):
        return value, True
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], str):
        kind = value[2] if len(value) > 2 and isinstance(value[2], str) else ''
        return value[0], kind.lower() not in _NOT_IMPLEMENTED_KINDS
    if isinstance(value, dict) and isinstance(value.get('description', ''), str):
        impl = value.get('implemented', True)
        if not isinstance(impl, bool):
            raise ValueError(f'registry[{key!r}].implemented must be a bool')
        return value.get('description', ''), impl
    raise ValueError(f'registry[{key!r}] must be a description string, a (description, effect, kind) '
                     'tuple or a {description, implemented} dict')


def capability_gaps(*, plan=None, registry=None, **extra):
    """Compare a descriptive plan with a capability registry.

    plan: list of capability ids or keyword phrases. registry: {id: entry}.
    implemented     - exact id match on an entry that is implemented;
    description_only- id exists but is marked not implemented, or the phrase
                      only matches words in registry ids/descriptions (candidates);
    missing         - no id and no keyword match.
    """
    _no_extra(extra)
    if plan is None and registry is None:
        plan, registry = ['learning.record', 'video.subtitle_burn', 'lesson recall', 'voice.clone'], _EXAMPLE_REGISTRY
    if plan is None or registry is None:
        raise ValueError('plan and registry are both required (or omit both for the example)')
    plan = _list(plan, 'plan', MAX_PLAN, min_len=1)
    if not isinstance(registry, dict) or len(registry) > MAX_REGISTRY:
        raise ValueError(f'registry must be a dict with at most {MAX_REGISTRY} entries')
    entries = {}
    for key in sorted(registry, key=str):
        if not isinstance(key, str):
            raise ValueError('registry ids must be strings')
        desc, impl = _registry_entry(key, registry[key])
        entries[key] = (impl, set(tokens(key)), set(tokens(key + ' ' + desc)))
    implemented, desc_only, missing = [], [], []
    for i, item in enumerate(plan):
        item = _str(item, f'plan[{i}]', max_len=500).strip()
        if item in entries:
            (implemented if entries[item][0] else desc_only).append(
                {'item': item, 'match': 'id', 'ids': [item]} if entries[item][0] else
                {'item': item, 'match': 'id_not_implemented', 'ids': [item]})
            continue
        words = set(tokens(item))
        cands = sorted(k for k, (_, _, alltok) in entries.items() if words and words <= alltok)
        if cands:
            desc_only.append({'item': item, 'match': 'keywords_only', 'ids': cands[:20]})
        else:
            missing.append({'item': item})
    return _pack('capability_gaps',
                 {'implemented': implemented, 'description_only': desc_only, 'missing': missing,
                  'counts': {'implemented': len(implemented), 'description_only': len(desc_only),
                             'missing': len(missing)}},
                 ['only an exact registry id on an implemented entry counts as implemented',
                  'keyword matches (all plan words found in an id/description) are candidates needing '
                  'human confirmation, never proof of implementation',
                  "tuple entries whose kind is description/planned/index/design/doc, or dicts with "
                  "implemented=False, are treated as not implemented",
                  'registry presence is not proof the capability was executed or tested'],
                 [f'plan <= {MAX_PLAN} items, registry <= {MAX_REGISTRY} entries',
                  'no stemming or synonyms; Arabic and English words do not cross-match'])


# --------------------------------------------------------------------------- 26.06 regression_from_defect

_EXAMPLE_DEFECT = {'id': 'D-42', 'input': {'audio': 'mp3', 'container': 'mp4'},
                   'expected': 'aac', 'observed_before': 'mp3'}


def regression_from_defect(*, defect=None, before=None, after=None, comparator='equals', **extra):
    """Build a regression case from a defect and judge before/after outcomes given as data.

    A regression is valid only if the 'before' outcome fails the expectation
    (reproduces the defect) and the 'after' outcome passes it.
    before defaults to defect.observed_before; after=None -> 'pending_after'.
    comparator: 'equals' (canonical JSON equality) or 'contains' (string containment).
    """
    _no_extra(extra)
    if defect is None:
        if before is not None or after is not None:
            raise ValueError('defect is required when before/after are given')
        defect, after = _EXAMPLE_DEFECT, 'aac'
    _dict(defect, 'defect', ('id', 'input', 'expected', 'observed_before'))
    did = _str(defect['id'], 'defect.id', max_len=200)
    for k in ('input', 'expected', 'observed_before'):
        _json_value(defect[k], f'defect.{k}', 50_000)
    comparator = _choice(comparator, {'equals', 'contains'}, 'comparator')
    expected = defect['expected']
    if comparator == 'contains' and not isinstance(expected, str):
        raise ValueError("comparator 'contains' needs a string expected value")
    if before is None:
        before = defect['observed_before']
    _json_value(before, 'before', 50_000)
    if after is not None:
        _json_value(after, 'after', 50_000)

    def passes(obs):
        if comparator == 'equals':
            return _json_value(obs, 'observed') == _json_value(expected, 'expected')
        return isinstance(obs, str) and expected in obs

    before_pass = passes(before)
    after_pass = None if after is None else passes(after)
    if before_pass:
        verdict, reason = 'invalid_does_not_reproduce', 'the before-fix outcome already passes; the case does not reproduce the defect'
    elif after is None:
        verdict, reason = 'pending_after', 'reproduces the defect; no after-fix outcome supplied yet'
    elif not after_pass:
        verdict, reason = 'invalid_fix_not_verified', 'the after-fix outcome still fails'
    else:
        verdict, reason = 'valid_regression', 'fails before the fix and passes after it'
    case = {'case_id': 'reg-' + _sha256({'defect': did, 'input': defect['input'],
                                         'expected': expected, 'comparator': comparator})[:12],
            'defect_id': did, 'input': defect['input'], 'expected': expected, 'comparator': comparator}
    return _pack('regression_from_defect',
                 {'case': case, 'before_passes': before_pass, 'after_passes': after_pass,
                  'before_matches_recorded': _json_value(before, 'before') == _json_value(defect['observed_before'], 'o'),
                  'valid': verdict == 'valid_regression', 'verdict': verdict, 'reason': reason},
                 ['outcomes are supplied as data; this op does not execute the system under test',
                  'the case is a data record for a test harness, not generated or applied code',
                  "'equals' compares canonical JSON (key order ignored); 'contains' is plain substring"],
                 ['each value <= 50000 JSON characters',
                  'a valid verdict only covers this one input; it is not proof of general correctness'])


# --------------------------------------------------------------------------- 26.07 rule_versions

def _check_state(state):
    _dict(state, 'state', ('versions', 'active', 'activation_log', 'changelog'))
    versions = _list(state['versions'], 'state.versions', MAX_VERSIONS)
    for i, v in enumerate(versions):
        _dict(v, f'state.versions[{i}]', ('version', 'hash', 'rules', 'note'))
        if _int(v['version'], 1, MAX_VERSIONS, f'state.versions[{i}].version') != i + 1:
            raise ValueError('state.versions must be numbered 1..n in order')
        _json_value(v['rules'], f'state.versions[{i}].rules')
        if _sha256(v['rules']) != v['hash']:
            raise ValueError(f'state.versions[{i}] hash does not match its rules (tampered or corrupted)')
        _str(v['note'], f'state.versions[{i}].note', max_len=1_000, allow_empty=True)
    log = _list(state['activation_log'], 'state.activation_log', 10_000)
    for i, n in enumerate(log):
        _int(n, 1, len(versions), f'state.activation_log[{i}]')
    if state['active'] is not None:
        _int(state['active'], 1, len(versions), 'state.active')
    if (log[-1] if log else None) != state['active']:
        raise ValueError('state.active must equal the last activation_log entry')
    _list(state['changelog'], 'state.changelog', 10_000)
    return copy.deepcopy(state)


def _new_state():
    return {'versions': [], 'active': None, 'activation_log': [], 'changelog': []}


def _commit(state, rules, note):
    if len(state['versions']) >= MAX_VERSIONS:
        raise ValueError(f'at most {MAX_VERSIONS} versions')
    n = len(state['versions']) + 1
    h = _sha256(rules)
    state['versions'].append({'version': n, 'hash': h, 'rules': copy.deepcopy(rules), 'note': note})
    state['changelog'].append({'seq': len(state['changelog']) + 1, 'event': 'commit',
                               'version': n, 'hash': h, 'note': note})
    return n


def _activate(state, n, event='activate'):
    prev = state['active']
    state['active'] = n
    state['activation_log'].append(n)
    state['changelog'].append({'seq': len(state['changelog']) + 1, 'event': event,
                               'version': n, 'from_version': prev,
                               'hash': state['versions'][n - 1]['hash']})


def rule_versions(*, action='status', state=None, rules=None, note='', version=None, **extra):
    """Versioned decision-rule sets with content hashes, changelog, activate and rollback.

    action: 'status' | 'commit' (rules, note) | 'activate' (version) | 'rollback'.
    state is the dict returned previously in result['state'] (None = empty);
    hashes are re-verified on every call. rollback re-activates the version
    that was active before the current one. History is append-only.
    """
    _no_extra(extra)
    action = _choice(action, {'status', 'commit', 'activate', 'rollback'}, 'action')
    note = _str(note, 'note', max_len=1_000, allow_empty=True)
    if state is None and action == 'status' and rules is None and version is None:
        st = _new_state()
        _commit(st, [{'when': 'audio', 'then': 'use AAC'}], 'v1 example')
        _activate(st, 1)
        _commit(st, [{'when': 'audio', 'then': 'use AAC'}, {'when': 'fonts', 'then': 'embed'}], 'v2 example')
        _activate(st, 2)
    else:
        st = _new_state() if state is None else _check_state(state)
    if action != 'commit' and rules is not None:
        raise ValueError('rules is only used with action=commit')
    if action != 'activate' and version is not None:
        raise ValueError('version is only used with action=activate')
    if action == 'commit':
        if rules is None:
            raise ValueError('action=commit requires rules')
        _json_value(rules, 'rules')
        _commit(st, rules, note)
    elif action == 'activate':
        if version is None:
            raise ValueError('action=activate requires version')
        if not st['versions']:
            raise ValueError('no versions to activate')
        _activate(st, _int(version, 1, len(st['versions']), 'version'))
    elif action == 'rollback':
        log = st['activation_log']
        cur = st['active']
        prev = next((v for v in reversed(log[:-1]) if v != cur), None) if log else None
        if prev is None:
            raise ValueError('nothing to roll back to: no earlier, different active version')
        _activate(st, prev, 'rollback')
    active = st['active']
    act = st['versions'][active - 1] if active else None
    return _pack('rule_versions',
                 {'action': action, 'active_version': active,
                  'active_hash': act['hash'] if act else None,
                  'active_rules': copy.deepcopy(act['rules']) if act else None,
                  'version_count': len(st['versions']), 'state': st},
                 ['hash = SHA-256 of canonical JSON (sorted keys, compact) of the rule set',
                  'versions are immutable and append-only; activate/rollback only move the active pointer',
                  'rollback returns to the most recent earlier active version that differs from the current one',
                  'state lives in memory and is returned to the caller; nothing is persisted here'],
                 [f'<= {MAX_VERSIONS} versions, each rule set <= {MAX_RULES_JSON} JSON characters',
                  'hash verification detects accidental or naive edits, not a forger who recomputes hashes'])


# --------------------------------------------------------------------------- 26.08 lesson_benefit

def _group(value, name):
    _dict(value, name, ('tasks', 'repeated_errors'), ('group',))
    n = _int(value['tasks'], 0, 10_000_000, f'{name}.tasks')
    k = _int(value['repeated_errors'], 0, n, f'{name}.repeated_errors')
    g = _str(value.get('group', ''), f'{name}.group', max_len=200, allow_empty=True)
    return n, k, g


def lesson_benefit(*, before=None, after=None, min_tasks=30, z_threshold=1.96, **extra):
    """Compare repeated-error rates before vs after a lesson on comparable task groups.

    before/after: {tasks, repeated_errors, group}. Reports rates, absolute and
    relative reduction and a pooled two-proportion z-score. Verdict is
    'insufficient_data' when either side has < min_tasks tasks or fewer than
    5 expected successes/failures under the pooled rate.
    """
    _no_extra(extra)
    if before is None and after is None:
        before = {'tasks': 120, 'repeated_errors': 36, 'group': 'reel exports'}
        after = {'tasks': 110, 'repeated_errors': 9, 'group': 'reel exports'}
    if before is None or after is None:
        raise ValueError('before and after are both required (or omit both for the example)')
    nb, kb, gb = _group(before, 'before')
    na, ka, ga = _group(after, 'after')
    min_tasks = _int(min_tasks, 1, 1_000_000, 'min_tasks')
    zt = _num(z_threshold, 0.5, 6.0, 'z_threshold')
    rb = kb / nb if nb else None
    ra = ka / na if na else None
    res = {'before': {'tasks': nb, 'repeated_errors': kb, 'rate': None if rb is None else round(rb, 6)},
           'after': {'tasks': na, 'repeated_errors': ka, 'rate': None if ra is None else round(ra, 6)},
           'absolute_reduction': None, 'relative_reduction': None, 'z': None}
    if gb and ga and normalise_text(gb).strip() != normalise_text(ga).strip():
        res['verdict'] = 'not_comparable'
        res['reason'] = 'task groups differ'
    elif nb < min_tasks or na < min_tasks:
        res['verdict'] = 'insufficient_data'
        res['reason'] = f'need at least {min_tasks} tasks on each side'
    else:
        res['absolute_reduction'] = round(rb - ra, 6)
        res['relative_reduction'] = round((rb - ra) / rb, 6) if rb > 0 else None
        p = (kb + ka) / (nb + na)
        if min(p * nb, (1 - p) * nb, p * na, (1 - p) * na) < 5:
            res['verdict'] = 'insufficient_data'
            res['reason'] = 'fewer than 5 expected errors/non-errors on a side; normal approximation unreliable'
        else:
            z = (rb - ra) / math.sqrt(p * (1 - p) * (1 / nb + 1 / na))
            res['z'] = round(z, 4)
            if z >= zt:
                res['verdict'], res['reason'] = 'reduction', f'z >= {zt:g}'
            elif z <= -zt:
                res['verdict'], res['reason'] = 'increase', f'z <= -{zt:g}'
            else:
                res['verdict'], res['reason'] = 'no_clear_change', f'|z| < {zt:g}'
    return _pack('lesson_benefit', res,
                 ['tasks are independent and the two groups are comparable (same kind of work)',
                  'pooled two-proportion z-test, normal approximation, two-sided threshold',
                  'a before/after difference is association, not proof that the lesson caused it',
                  'counts are supplied by the caller; they are not re-derived from logs here'],
                 [f'min_tasks per side = {min_tasks}; expected counts >= 5 required',
                  'no correction for multiple comparisons, seasonality or changing task difficulty'])


# --------------------------------------------------------------------------- 26.09 local_only_guard

_SAFE_PAYLOADS = {'none', 'aggregate_counts', 'public', 'code', 'hash'}
_NETWORK_TYPES = {'upload', 'send', 'sync', 'post', 'http', 'https', 'webhook', 'email', 'publish',
                  'api_call', 'share', 'cloud'}
_TRAINING_WORDS = ('train', 'fine_tune', 'finetune', 'fine-tune', 'export', 'dataset', 'telemetry',
                   'analytics', 'rlhf', 'feedback_upload')
_LOCAL_TYPES = {'write', 'store', 'save', 'read', 'delete', 'update', 'index', 'local_write'}
_WIN_PATH = re.compile(r'^[A-Za-z]:[\\/]')


def _classify_destination(dest, typ):
    d = dest.strip().lower()
    t = typ.strip().lower()
    if any(w in d or w in t for w in _TRAINING_WORDS):
        return 'training_or_export'
    if '://' in d and not d.startswith('file://') or d.startswith('\\\\') or d.startswith('//') \
            or t in _NETWORK_TYPES or d in _NETWORK_TYPES:
        return 'network'
    if (d.startswith('local:') or d.startswith('file://') or _WIN_PATH.match(dest.strip())
            or d.startswith(('/', '~', './', '.\\')) or d in {'memory', 'local', 'sqlite', 'disk'}):
        return 'local'
    return 'unknown'


def local_only_guard(*, operations=None, **extra):
    """Block plans that would send memory or user text off the device or into training/export.

    operations: [{type, destination, payload_kind}]. Destinations are
    classified network / training_or_export / local / unknown. Sensitive
    payloads (anything not in a small safe list, e.g. memory, user_text, chat)
    may only go to local storage; unknown destinations fail closed.
    """
    _no_extra(extra)
    if operations is None:
        operations = [
            {'type': 'write', 'destination': 'local:~/.red-rose/memory.sqlite3', 'payload_kind': 'memory'},
            {'type': 'upload', 'destination': 'https://example.invalid/collect', 'payload_kind': 'memory'},
            {'type': 'export', 'destination': 'training_dataset', 'payload_kind': 'user_text'},
        ]
    operations = _list(operations, 'operations', MAX_OPERATIONS, min_len=1)
    decisions = []
    for i, op in enumerate(operations):
        _dict(op, f'operations[{i}]', ('type', 'destination', 'payload_kind'))
        typ = _str(op['type'], f'operations[{i}].type', max_len=100)
        dest = _str(op['destination'], f'operations[{i}].destination', max_len=2_000)
        kind = _str(op['payload_kind'], f'operations[{i}].payload_kind', max_len=100).strip().lower()
        dclass = _classify_destination(dest, typ)
        sensitive = kind not in _SAFE_PAYLOADS
        if dclass == 'local' and typ.strip().lower() in _LOCAL_TYPES:
            decision, why = 'allow', 'local storage'
        elif dclass == 'local':
            decision, why = 'needs_review', f'unrecognised local operation type {typ!r}'
        elif sensitive:
            decision, why = 'block', f'{kind} payload to a {dclass} destination'
        else:
            decision, why = 'needs_review', f'non-sensitive payload to a {dclass} destination needs explicit approval'
        decisions.append({'index': i, 'type': typ, 'destination_class': dclass,
                          'payload_kind': kind, 'sensitive': sensitive,
                          'decision': decision, 'reason': why})
    blocked = sum(d['decision'] == 'block' for d in decisions)
    review = sum(d['decision'] == 'needs_review' for d in decisions)
    verdict = 'blocked' if blocked else ('needs_review' if review else 'allowed')
    return _pack('local_only_guard',
                 {'verdict': verdict, 'blocked': blocked, 'needs_review': review,
                  'allowed': len(decisions) - blocked - review, 'decisions': decisions},
                 ['this checks a declared plan; it does not intercept real I/O and cannot see undeclared operations',
                  "payload kinds outside {none, aggregate_counts, public, code, hash} are treated as sensitive",
                  'training/export/telemetry/dataset words in type or destination are blocked for sensitive payloads',
                  'unknown destinations fail closed (never auto-allowed)'],
                 [f'operations <= {MAX_OPERATIONS}', 'keyword/scheme based classification; a mislabelled '
                  'destination can be misclassified, so payload_kind must be declared honestly'])


# --------------------------------------------------------------------------- 26.10 forget_request

def _row_matches(row, terms, ids):
    if 'id' in row and _json_value(row['id'], 'id') in ids:
        return True
    if not terms:
        return False
    for value in row.values():
        if isinstance(value, str):
            text = normalise_text(value)
            if any(t in text for t in terms):
                return True
    return False


def forget_request(*, stores=None, request=None, authorised_tables=None, **extra):
    """Plan and apply (to a copy) the deletion of rows matching a forget request.

    stores: {table: [row dicts]}; request: {terms: [...], ids: [...], tables: [...]}
    (tables optional = all authorised); authorised_tables: tables this request
    may touch. Returns the plan (table -> row indexes), the updated copy,
    a verification and a receipt with counts only (no deleted content).
    """
    _no_extra(extra)
    if stores is None and request is None and authorised_tables is None:
        stores = {'memory': [{'id': 1, 'text': 'رقم تليفون أحمد 0100'},
                             {'id': 2, 'text': 'prefers AAC audio'}],
                  'chats': [{'id': 7, 'text': 'call Ahmed tomorrow'}, {'id': 8, 'text': 'render at 30 fps'}],
                  'audit': [{'id': 3, 'text': 'أحمد approved export'}]}
        request = {'terms': ['احمد', 'ahmed']}
        authorised_tables = ['memory', 'chats']
    if stores is None or request is None or authorised_tables is None:
        raise ValueError('stores, request and authorised_tables are all required (or omit all for the example)')
    if not isinstance(stores, dict) or not 1 <= len(stores) <= MAX_TABLES:
        raise ValueError(f'stores must be a dict of 1..{MAX_TABLES} tables')
    total = 0
    for name, rows in stores.items():
        if not isinstance(name, str):
            raise ValueError('table names must be strings')
        rows = _list(rows, f'stores[{name!r}]', MAX_ROWS)
        for j, r in enumerate(rows):
            if not isinstance(r, dict):
                raise ValueError(f'stores[{name!r}][{j}] must be a dict')
        total += len(rows)
    if total > MAX_ROWS:
        raise ValueError(f'at most {MAX_ROWS} rows in total')
    _json_value(stores, 'stores', 50_000_000)
    _dict(request, 'request', (), ('terms', 'ids', 'tables'))
    terms = [normalise_text(_str(t, f'request.terms[{i}]', max_len=200)).strip()
             for i, t in enumerate(_list(request.get('terms', []), 'request.terms', MAX_TERMS))]
    if any(len(t) < 2 for t in terms):
        raise ValueError('each term must have at least 2 characters after normalisation')
    ids = {_json_value(v, f'request.ids[{i}]', 500)
           for i, v in enumerate(_list(request.get('ids', []), 'request.ids', 10_000))}
    if not terms and not ids:
        raise ValueError('request needs at least one term or id')
    auth = _list(authorised_tables, 'authorised_tables', MAX_TABLES, min_len=1)
    for i, t in enumerate(auth):
        _str(t, f'authorised_tables[{i}]', max_len=200)
    auth = set(auth)
    wanted = request.get('tables')
    if wanted is None:
        wanted = sorted(auth & set(stores))
    else:
        wanted = [_str(t, f'request.tables[{i}]', max_len=200)
                  for i, t in enumerate(_list(wanted, 'request.tables', MAX_TABLES, min_len=1))]
    refused = sorted({t for t in wanted if t not in auth})
    unknown = sorted({t for t in wanted if t in auth and t not in stores})
    scope = sorted({t for t in wanted if t in auth and t in stores})
    after = copy.deepcopy(stores)
    plan, receipt_tables = {}, {}
    for t in scope:
        rows = stores[t]
        idx = [j for j, r in enumerate(rows) if _row_matches(r, terms, ids)]
        plan[t] = idx
        drop = set(idx)
        after[t] = [copy.deepcopy(r) for j, r in enumerate(rows) if j not in drop]
        receipt_tables[t] = {'matched': len(idx), 'deleted': len(rows) - len(after[t]),
                             'kept': len(after[t])}
    remaining = sum(_row_matches(r, terms, ids) for t in scope for r in after[t])
    kept_ok = all(_sha256(after[t]) == _sha256([r for j, r in enumerate(stores[t]) if j not in set(plan[t])])
                  for t in scope)
    others_ok = all(_sha256(after[t]) == _sha256(stores[t]) for t in stores if t not in scope)
    outside = sum(_row_matches(r, terms, ids) for t in stores if t not in scope for r in stores[t])
    verification = {'no_matches_remain_in_scope': remaining == 0, 'remaining_in_scope': remaining,
                    'unrelated_rows_untouched': kept_ok, 'other_tables_untouched': others_ok,
                    'passed': remaining == 0 and kept_ok and others_ok}
    receipt = {'request_hash': _sha256({'terms': sorted(terms), 'ids': sorted(ids), 'tables': scope})[:16],
               'tables': receipt_tables, 'total_deleted': sum(v['deleted'] for v in receipt_tables.values()),
               'refused_tables': len(refused), 'unknown_tables': len(unknown),
               'matches_outside_scope': outside, 'verified': verification['passed']}
    return _pack('forget_request',
                 {'plan': {'tables_in_scope': scope, 'refused_tables': refused, 'unknown_tables': unknown,
                           'row_indexes': plan},
                  'stores_after': after, 'verification': verification, 'receipt': receipt},
                 ['applied to an in-memory copy only; the caller must apply the plan to real storage '
                  'with its own write authorisation and re-verify there',
                  'a row matches if its id is listed or any string field contains a term '
                  '(normalised Arabic, casefold substring)',
                  'tables outside authorised_tables are never touched; their matches are only counted',
                  'the receipt holds counts and a request hash, never deleted content or the terms themselves'],
                 [f'<= {MAX_TABLES} tables, <= {MAX_ROWS} rows, <= {MAX_TERMS} terms',
                  'nested values and non-string fields are not searched for terms; backups, logs and '
                  'derived indexes outside the given stores are not covered',
                  'substring matching can over-match short terms; review the plan before applying it'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'similar_errors': similar_errors, 'rank_lessons': rank_lessons, 'rule_proposal': rule_proposal,
    'capability_gaps': capability_gaps, 'regression_from_defect': regression_from_defect,
    'rule_versions': rule_versions, 'lesson_benefit': lesson_benefit,
    'local_only_guard': local_only_guard, 'forget_request': forget_request,
}


def run(op, params=None):
    """Validate and dispatch: run('rank_lessons', {...}) -> {'op','result','assumptions','limits'}."""
    if not isinstance(op, str) or op not in OPS:
        raise ValueError(f'op must be one of {sorted(OPS)}')
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError('params must be a dict')
    if len(params) > MAX_PARAMS:
        raise ValueError(f'params may have at most {MAX_PARAMS} keys')
    if not all(isinstance(key, str) for key in params):
        raise ValueError('param names must be strings')
    out = OPS[op](**params)
    try:
        json.dumps(out, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f'{op} produced a non-JSON-serialisable result: {exc}') from exc
    return out
