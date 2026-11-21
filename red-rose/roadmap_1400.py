"""Owner-approved 1,400-question roadmap: load, verify, and track real progress.

Source: questions/owner_1400/RED_ROSE_1400.json, supplied by the owner as
RED_ROSE_1400_QUESTIONS_WITH_ANSWERS.zip and approved in chat on 2026-11-21
with the words «نفذ الاجابات موافق على الكل». The file itself states it is a
newly drafted set, NOT a verbatim restoration of earlier conversations.

The 1,400 questions are 280 topics (28 chapters x 10 topics) each asked through
the same five lenses. Work is therefore tracked per topic; a question counts as
answered in code only when its topic reached unit_tested AND its own lens has
recorded evidence. Status can only be raised by entries that point at a real
module, a real symbol and a real test file; every claim is re-checked at load.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'questions' / 'owner_1400' / 'RED_ROSE_1400.json'
SOURCE_SHA256 = '0b878ab730aeeaeb4b5d59acf70c067557709091f8c8a71ff8a3aa3d6463541b'
STATUS_FILE = ROOT / 'ROADMAP_1400_STATUS.json'

APPROVAL = {
    'date': '2026-11-21', 'channel': 'chat',
    'owner_words': 'نفذ الاجابات موافق على الكل',
    'covers': 'the 1,400 suggested answers as design decisions to implement',
    'does_not_cover': ['pushing, merging or publishing', 'installing software',
                       'paid services', 'deleting or overwriting owner files',
                       'uploading private memory or data'],
    'verbatim_historical_questions': False,
}

LENSES = ('عقد القدرة وحدودها', 'الخوارزمية المستقلة', 'اختبار القبول والأخطاء',
          'ضوابط الصلاحية والخصوصية', 'الأداء والتكامل والقياس')
LENS_KEYS = ('contract', 'algorithm', 'acceptance', 'permission', 'performance')
LEVELS = ('proposed', 'coded', 'unit_tested', 'e2e_verified')


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_questions(path=SOURCE):
    """Return the 1,400 rows after checking hash, ids and the 280x5 structure."""
    path = Path(path)
    if _sha256(path) != SOURCE_SHA256:
        raise ValueError('RED_ROSE_1400.json changed: hash differs from the owner-approved file')
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = data['questions']
    if [r['id'] for r in rows] != list(range(1, 1401)):
        raise ValueError('question ids must be exactly 1..1400')
    if data.get('historical_verbatim_restored') is not False:
        raise ValueError('source must declare it is not a verbatim historical restoration')
    for r in rows:
        if r['lens'] not in LENSES:
            raise ValueError(f"question {r['id']}: unknown lens")
    return rows


def topic_key(row):
    return f"{row['chapter_number']:02d}.{row['topic_number']:02d}"


def topics(rows=None):
    rows = rows if rows is not None else load_questions()
    out = {}
    for r in rows:
        key = topic_key(r)
        t = out.setdefault(key, {'key': key, 'chapter': r['chapter'], 'topic': r['topic'],
                                 'method': r['implementation_method_hint'],
                                 'acceptance': r['acceptance_evidence_hint'],
                                 'question_ids': {}})
        if (t['method'], t['acceptance']) != (r['implementation_method_hint'], r['acceptance_evidence_hint']):
            raise ValueError(f'topic {key} has inconsistent hints')
        t['question_ids'][LENS_KEYS[LENSES.index(r['lens'])]] = r['id']
    if len(out) != 280 or any(len(t['question_ids']) != 5 for t in out.values()):
        raise ValueError('expected 280 topics with 5 lenses each')
    return out


def _check_entry(key, entry, registry, directory):
    level = entry.get('status')
    if level not in LEVELS[1:]:
        raise ValueError(f'{key}: status must be one of {LEVELS[1:]}')
    lenses = entry.get('lenses')
    if not isinstance(lenses, list) or not lenses or set(lenses) - set(LENS_KEYS):
        raise ValueError(f'{key}: lenses must be a non-empty subset of {LENS_KEYS}')
    module_name, symbol = entry.get('module'), entry.get('symbol')
    if not (directory / f'{module_name}.py').is_file():
        raise ValueError(f'{key}: module file {module_name}.py does not exist')
    module = importlib.import_module(module_name)
    mapping = getattr(module, 'TOPICS', None)
    if isinstance(mapping, dict) and key in mapping:
        if mapping[key] != symbol or symbol not in getattr(module, 'OPS', {}):
            raise ValueError(f'{key}: {module_name}.TOPICS/OPS do not expose {symbol}')
    elif not callable(getattr(module, symbol, None)):
        raise ValueError(f'{key}: {module_name}.{symbol} is not a callable')
    if entry.get('adapter') is not None and entry['adapter'] not in registry:
        raise ValueError(f'{key}: adapter {entry["adapter"]} is not registered')
    if level in ('unit_tested', 'e2e_verified'):
        test = directory / entry.get('test', '')
        if not test.is_file() or symbol not in test.read_text(encoding='utf-8'):
            raise ValueError(f'{key}: test file missing or does not exercise {symbol}')
    if level == 'e2e_verified' and not entry.get('artifact_receipt'):
        raise ValueError(f'{key}: e2e_verified needs an artifact receipt')
    return True


def load_status(*, registry, directory=ROOT, status_file=STATUS_FILE):
    """Status entries, each re-verified against the code; unknown keys rejected."""
    known = topics()
    data = json.loads(Path(status_file).read_text(encoding='utf-8'))
    entries = data.get('topics', {})
    for key, entry in entries.items():
        if key not in known:
            raise ValueError(f'unknown topic key {key}')
        _check_entry(key, entry, registry, Path(directory))
    return entries


def summary(*, registry):
    known = topics()
    status = load_status(registry=registry)
    by_level = Counter(status.get(k, {}).get('status', 'proposed') for k in known)
    answered = 0
    lens_counts = Counter()
    for key, entry in status.items():
        if entry['status'] in ('unit_tested', 'e2e_verified'):
            answered += len(entry['lenses'])
            lens_counts.update(entry['lenses'])
    chapters = {}
    for key, t in known.items():
        c = chapters.setdefault(key[:2], {'title': t['chapter'], **{lvl: 0 for lvl in LEVELS}})
        c[status.get(key, {}).get('status', 'proposed')] += 1
    return {'status': 'owner_approved_roadmap_partially_implemented',
            'approval': APPROVAL, 'source_sha256': SOURCE_SHA256,
            'questions': 1400, 'topics': len(known),
            'topics_by_level': {lvl: by_level.get(lvl, 0) for lvl in LEVELS},
            'questions_answered_in_tested_code': answered,
            'questions_remaining': 1400 - answered,
            'answered_by_lens': dict(lens_counts),
            'chapters': chapters,
            'complete': answered == 1400,
            'warning': ('A question counts only when its topic has unit-tested native code and its '
                        'lens has recorded evidence. Coded topics without tests do not count.')}


def explain_topic(key, *, registry):
    known = topics()
    if key not in known:
        raise ValueError('topic key must look like 08.01 and exist (01.01..28.10)')
    entry = load_status(registry=registry).get(key)
    t = known[key]
    return {**t, 'status': entry['status'] if entry else 'proposed', 'evidence': entry,
            'answered_lenses': entry['lenses'] if entry and entry['status'] in LEVELS[2:] else []}


def explain_question(question_id, *, registry):
    if type(question_id) is not int or not 1 <= question_id <= 1400:
        raise ValueError('question id must be an integer 1..1400')
    rows = load_questions()
    row = rows[question_id - 1]
    key = topic_key(row)
    topic = explain_topic(key, registry=registry)
    lens = LENS_KEYS[LENSES.index(row['lens'])]
    return {'id': question_id, 'topic_key': key, 'lens': lens, 'question': row['question'],
            'suggested_answer': row['suggested_answer'], 'owner_approved': True,
            'answered_in_tested_code': lens in topic['answered_lenses'],
            'topic_status': topic['status'], 'evidence': topic['evidence']}
