"""Red Rose V21: small, bounded, deterministic decision and reasoning helpers.

Pure standard-library Python. No file I/O, no subprocess, no network, no printing.
Every op validates its inputs strictly (ValueError on unknown parameter or field
names, wrong types, oversize lists) and caps its work so it cannot run away.

These are explicit rule engines, not language understanding: they fold, label,
rank and check structured inputs that the caller supplies. Registries, status
maps and logs are always passed in as parameters; this module imports no other
project module. Each op returns the assumptions it makes and the limits it
enforces next to its result.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

MAX_PARAMS = 24
MAX_ITEMS = 500
MAX_TEXT = 2000
MAX_KEY = 100
MAX_JSON_CHARS = 200_000
MAX_JSON_DEPTH = 20
MAX_JSON_NODES = 10_000

TOPICS = {
    '09.01': 'intent_state',
    '09.02': 'confidence',
    '09.03': 'tool_choice',
    '09.04': 'phase_machine',
    '09.05': 'blind_review',
    '09.06': 'resolve_conflict',
    '09.07': 'failure_log',
    '09.08': 'route_tested',
    '09.09': 'incomplete_info',
    '09.10': 'decision_record',
}

TOPIC_NAMES_AR = {
    '09.01': 'فهم نية المستخدم المتتابعة',
    '09.02': 'تحديد درجة الثقة',
    '09.03': 'مفاضلة أدوات متعددة',
    '09.04': 'الاستدلال في المهام الطويلة',
    '09.05': 'إدارة الخلاف بين نتائج الوكلاء',
    '09.06': 'حل التعارضات في الأوامر',
    '09.07': 'التفكير الذاتي بعد الفشل',
    '09.08': 'توجيه المهام وفق الخبرة',
    '09.09': 'القرار تحت معلومات ناقصة',
    '09.10': 'توليد تفسير قابل للتدقيق',
}

RULES_NOT_NLU = 'قواعد صريحة، مش فهم لغة (explicit rules, not language understanding)'


# --------------------------------------------------------------------------- validation

def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _num(value, low, high, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise ValueError(f'{name} must be a finite number')
    value = float(value)
    if value < low or value > high:
        raise ValueError(f'{name} must be in [{low}, {high}]')
    return value


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _text(value, name, *, allow_empty=False, max_len=MAX_TEXT):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    if len(value) > max_len:
        raise ValueError(f'{name} must be at most {max_len} characters')
    value = value.strip()
    if not value and not allow_empty:
        raise ValueError(f'{name} must not be empty')
    return value


def _list(value, name, *, min_items=0, max_items=MAX_ITEMS):
    if not isinstance(value, (list, tuple)) or not min_items <= len(value) <= max_items:
        raise ValueError(f'{name} must be a list of {min_items}..{max_items} items')
    return list(value)


def _dict(value, name, *, max_items=MAX_ITEMS):
    if not isinstance(value, dict) or len(value) > max_items:
        raise ValueError(f'{name} must be an object with at most {max_items} keys')
    if not all(isinstance(k, str) for k in value):
        raise ValueError(f'{name} keys must be strings')
    return value


def _fields(item, name, required=(), optional=()):
    if not isinstance(item, dict):
        raise ValueError(f'{name} must be an object')
    unknown = set(item) - set(required) - set(optional)
    if unknown:
        raise ValueError(f'{name} has unknown field(s): ' + ', '.join(sorted(map(str, unknown))))
    missing = [k for k in required if k not in item]
    if missing:
        raise ValueError(f'{name} is missing field(s): ' + ', '.join(missing))
    return item


def _scalar(value, name):
    """JSON scalar: None, bool, bounded int, finite float or bounded string."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if abs(value) > 10 ** 15:
            raise ValueError(f'{name} integer is out of range')
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f'{name} must be finite')
        return value
    if isinstance(value, str):
        if len(value) > MAX_TEXT:
            raise ValueError(f'{name} must be at most {MAX_TEXT} characters')
        return value
    raise ValueError(f'{name} must be a JSON scalar (string, number, bool or null)')


def _json_value(value, name):
    """Validate a nested JSON value with bounded depth and node count; returns a copy."""
    count = [0]

    def walk(v, depth):
        count[0] += 1
        if count[0] > MAX_JSON_NODES:
            raise ValueError(f'{name} has more than {MAX_JSON_NODES} nodes')
        if depth > MAX_JSON_DEPTH:
            raise ValueError(f'{name} is nested deeper than {MAX_JSON_DEPTH}')
        if isinstance(v, dict):
            out = {}
            for k, item in v.items():
                if not isinstance(k, str):
                    raise ValueError(f'{name} object keys must be strings')
                out[k] = walk(item, depth + 1)
            return out
        if isinstance(v, (list, tuple)):
            return [walk(item, depth + 1) for item in v]
        return _scalar(v, name)
    copy = walk(value, 0)
    if len(_canonical(copy)) > MAX_JSON_CHARS:
        raise ValueError(f'{name} is larger than {MAX_JSON_CHARS} characters of JSON')
    return copy


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def _sha256(value):
    return hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()


def _norm(text):
    return ' '.join(text.lower().split())


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


# --------------------------------------------------------------------------- shared rule engine

_COND_OPS = {'==', '!=', '<', '<=', '>', '>=', 'in', 'not_in'}


def _parse_rules(rules, name, max_rules=100):
    rules = _list(rules, name, max_items=max_rules)
    out = []
    for i, rule in enumerate(rules):
        r = _fields(rule, f'{name}[{i}]', ('when', 'then'), ('name',))
        conds = _list(r['when'], f'{name}[{i}].when', min_items=1, max_items=10)
        parsed = []
        for j, cond in enumerate(conds):
            c = _fields(cond, f'{name}[{i}].when[{j}]', ('input', 'op', 'value'))
            op = _choice(c['op'], _COND_OPS, f'{name}[{i}].when[{j}].op')
            if op in ('in', 'not_in'):
                val = [_scalar(v, f'{name}[{i}].when[{j}].value')
                       for v in _list(c['value'], f'{name}[{i}].when[{j}].value',
                                      min_items=1, max_items=50)]
            else:
                val = _scalar(c['value'], f'{name}[{i}].when[{j}].value')
            parsed.append({'input': _text(c['input'], f'{name}[{i}].when[{j}].input',
                                          max_len=MAX_KEY),
                           'op': op, 'value': val})
        entry = {'when': parsed, 'then': _scalar(r['then'], f'{name}[{i}].then')}
        if 'name' in r:
            entry['name'] = _text(r['name'], f'{name}[{i}].name', max_len=200)
        out.append(entry)
    return out


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _cond_true(cond, values):
    key = cond['input']
    if key not in values or values[key] is None:
        return False
    a, op, b = values[key], cond['op'], cond['value']
    if op == '==':
        return a == b and type(a) is type(b) or (_is_number(a) and _is_number(b) and a == b)
    if op == '!=':
        return not _cond_true({'input': key, 'op': '==', 'value': b}, values)
    if op in ('in', 'not_in'):
        inside = any(_cond_true({'input': key, 'op': '==', 'value': x}, values) for x in b)
        return inside if op == 'in' else not inside
    if _is_number(a) and _is_number(b):
        pass
    elif isinstance(a, str) and isinstance(b, str):
        pass
    else:
        return False
    return {'<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b}[op]


def _apply_rules(rules, values, default):
    for i, rule in enumerate(rules):
        if all(_cond_true(c, values) for c in rule['when']):
            return rule['then'], i
    return default, None


def _rule_text(rule):
    parts = [f"{c['input']} {c['op']} {json.dumps(c['value'], ensure_ascii=False)}"
             for c in rule['when']]
    return 'if ' + ' and '.join(parts) + ' then ' + json.dumps(rule['then'], ensure_ascii=False)


# --------------------------------------------------------------------------- 09.01 intent_state

_INTENT_EXAMPLE = [
    {'set': {'language': 'ar', 'aspect': '9:16'}},
    {'set': {'duration_s': 30}},
    {'set': {'music': 'soft'}},
    {'unset': ['music']},
    {'set': {'duration_s': 45}},
]


def intent_state(*, turns=None, at_turn=None, **extra):
    """Fold a sequence of turns into the active constraint set with provenance.

    Each turn is {'set': {key: scalar}, 'unset': [key, ...]} (both optional).
    Turns are numbered from 1. A constraint stays active until a later turn
    unsets it or sets a new value (the new value carries the new turn as its
    provenance; earlier values are kept in `history`). Within one turn, unset
    is applied before set, and the same key may not be both set and unset.
    `at_turn` folds only the first N turns. With no turns, a 5-turn example runs.
    """
    _no_extra(extra)
    example = turns is None
    if example:
        turns = _INTENT_EXAMPLE
    turns = _list(turns, 'turns', min_items=1, max_items=200)
    n = len(turns)
    at = n if at_turn is None else _int(at_turn, 1, n, 'at_turn')
    active, removed, events = {}, {}, []
    for i, turn in enumerate(turns[:at], start=1):
        t = _fields(turn, f'turns[{i}]', optional=('set', 'unset'))
        sets = _dict(t.get('set', {}), f'turns[{i}].set', max_items=50)
        unsets = [_text(k, f'turns[{i}].unset', max_len=MAX_KEY)
                  for k in _list(t.get('unset', []), f'turns[{i}].unset', max_items=50)]
        clean_sets = {}
        for k, v in sets.items():
            clean_sets[_text(k, f'turns[{i}].set key', max_len=MAX_KEY)] = _scalar(
                v, f'turns[{i}].set[{k}]')
        both = set(clean_sets) & set(unsets)
        if both:
            raise ValueError(f'turns[{i}] both sets and unsets: ' + ', '.join(sorted(both)))
        for key in unsets:
            if key in active:
                prev = active.pop(key)
                removed[key] = {'last_value': prev['value'], 'set_turn': prev['turn'],
                                'unset_turn': i}
                events.append({'turn': i, 'key': key, 'action': 'unset'})
            else:
                events.append({'turn': i, 'key': key, 'action': 'unset_not_active'})
        for key in sorted(clean_sets):
            value = clean_sets[key]
            prev = active.get(key)
            if prev is None:
                history, action = [], 'set'
            else:
                history = (prev['history'] + [{'value': prev['value'], 'turn': prev['turn']}])[-20:]
                action = 'override' if prev['value'] != value else 'restate'
            active[key] = {'value': value, 'turn': i, 'history': history}
            removed.pop(key, None)
            events.append({'turn': i, 'key': key, 'action': action})
        if len(active) > 200:
            raise ValueError('more than 200 active constraints')
    result = {
        'at_turn': at, 'turns_total': n, 'example': example,
        'active': {k: active[k] for k in sorted(active)},
        'removed': {k: removed[k] for k in sorted(removed)},
        'events_total': len(events), 'events': events[-1000:],
    }
    return _pack('intent_state', result,
                 [RULES_NOT_NLU,
                  'each turn is already reduced to explicit set/unset updates by the caller',
                  'silence keeps a constraint active; only an explicit unset or a new value changes it',
                  'provenance is the 1-based turn index of the latest value'],
                 ['turns <= 200, set/unset <= 50 keys per turn, active constraints <= 200',
                  'values are JSON scalars; history keeps the last 20 values per key',
                  'events list keeps the last 1000 entries'])


# --------------------------------------------------------------------------- 09.02 confidence

_LABEL_RANK = {'guess': 0, 'inference': 1, 'fact': 2}

_CONFIDENCE_EXAMPLE = [
    {'id': 'c1', 'text': 'الفيديو مدته 31.2 ثانية', 'evidence': ['ffprobe:duration=31.2']},
    {'id': 'c2', 'text': 'الفيديو أطول من حد الريلز 30 ثانية', 'derived_from': ['c1'],
     'reasoning': '31.2 > 30'},
    {'id': 'c3', 'text': 'الجمهور هيحب النسخة الأقصر', 'claimed_label': 'fact'},
]


def confidence(*, claims=None, **extra):
    """Label claims as fact / inference / guess and report the source of each.

    fact      = has at least one non-empty evidence reference (measurement, file, log line).
    inference = no evidence of its own, but has `reasoning` and `derived_from` ids that
                all resolve (transitively) to fact or inference claims.
    guess     = everything else. A claim with no evidence can never be a fact,
                whatever `claimed_label` says; a downgrade is reported.
    """
    _no_extra(extra)
    example = claims is None
    if example:
        claims = _CONFIDENCE_EXAMPLE
    claims = _list(claims, 'claims', min_items=1, max_items=300)
    parsed, ids = [], set()
    for i, c in enumerate(claims):
        c = _fields(c, f'claims[{i}]', ('id', 'text'),
                    ('evidence', 'derived_from', 'reasoning', 'claimed_label'))
        cid = _text(c['id'], f'claims[{i}].id', max_len=MAX_KEY)
        if cid in ids:
            raise ValueError(f'duplicate claim id: {cid}')
        ids.add(cid)
        evidence = [_text(e, f'claims[{i}].evidence', allow_empty=True, max_len=500)
                    for e in _list(c.get('evidence', []), f'claims[{i}].evidence', max_items=20)]
        evidence = [e for e in evidence if e]
        derived = [_text(d, f'claims[{i}].derived_from', max_len=MAX_KEY)
                   for d in _list(c.get('derived_from', []), f'claims[{i}].derived_from',
                                  max_items=20)]
        reasoning = _text(c.get('reasoning', ''), f'claims[{i}].reasoning', allow_empty=True)
        claimed = c.get('claimed_label')
        if claimed is not None:
            claimed = _choice(claimed, set(_LABEL_RANK), f'claims[{i}].claimed_label')
        parsed.append({'id': cid, 'text': _text(c['text'], f'claims[{i}].text'),
                       'evidence': evidence, 'derived_from': derived,
                       'reasoning': reasoning, 'claimed_label': claimed})
    labels = {p['id']: 'fact' for p in parsed if p['evidence']}
    for _ in range(len(parsed)):
        changed = False
        for p in parsed:
            if p['id'] in labels or not p['reasoning'] or not p['derived_from']:
                continue
            if all(d in labels and d != p['id'] for d in p['derived_from']):
                labels[p['id']] = 'inference'
                changed = True
        if not changed:
            break
    out, counts = [], {'fact': 0, 'inference': 0, 'guess': 0}
    for p in parsed:
        label = labels.get(p['id'], 'guess')
        counts[label] += 1
        if label == 'fact':
            source, basis = {'evidence': p['evidence']}, 'قياس أو دليل مرجعي'
        elif label == 'inference':
            source, basis = {'derived_from': p['derived_from'], 'reasoning': p['reasoning']}, \
                'استنتاج من حقائق'
        else:
            source = None
            missing = [d for d in p['derived_from'] if d not in ids]
            if missing:
                basis = 'تخمين: مراجع مش موجودة ' + ', '.join(missing)
            elif p['derived_from'] and not p['reasoning']:
                basis = 'تخمين: مراجع من غير استدلال مكتوب'
            elif p['derived_from']:
                basis = 'تخمين: المراجع نفسها مش مثبتة'
            else:
                basis = 'تخمين: مفيش دليل ولا استدلال'
        claimed = p['claimed_label']
        out.append({'id': p['id'], 'text': p['text'], 'label': label, 'source': source,
                    'basis': basis, 'claimed_label': claimed,
                    'downgraded': claimed is not None and _LABEL_RANK[claimed] > _LABEL_RANK[label],
                    'missing_refs': [d for d in p['derived_from'] if d not in ids]})
    total = len(out)
    summary = dict(counts, total=total, fact_ratio=counts['fact'] / total,
                   overall='all_grounded' if counts['guess'] == 0 else 'contains_guesses',
                   downgraded=sum(1 for o in out if o['downgraded']))
    return _pack('confidence', {'claims': out, 'summary': summary, 'example': example},
                 [RULES_NOT_NLU,
                  'evidence references are taken as given; the op does not open or re-measure them',
                  'an inference is only as good as its reasoning text, which is not checked for logic',
                  'cyclic or self-referencing derivations stay guesses'],
                 ['claims <= 300, evidence/derived_from <= 20 per claim',
                  'labels are structural (what support exists), not probabilities'])


# --------------------------------------------------------------------------- 09.03 tool_choice

_CRITERIA = ('accuracy', 'readiness', 'cost')
_DEFAULT_WEIGHTS = {'accuracy': 0.5, 'readiness': 0.3, 'cost': 0.2}

_TOOL_EXAMPLE = {
    'candidates': [
        {'id': 'video.verify', 'cost': 0.2, 'accuracy': 0.9, 'readiness': 1.0},
        {'id': 'video.shot_score', 'cost': 0.4, 'accuracy': 0.7, 'readiness': 1.0},
        {'id': 'external.magic_check', 'cost': 0.0, 'accuracy': 1.0, 'readiness': 1.0},
    ],
    'registry': ['video.verify', 'video.shot_score', 'video.scene_analyze'],
}


def tool_choice(*, candidates=None, registry=None, weights=None, **extra):
    """Pick the best registered tool by weighted accuracy / readiness / (1 - cost).

    Each candidate: {'id', 'cost', 'accuracy', 'readiness'} with values in [0, 1]
    (cost: lower is better). Only ids present in `registry` are eligible; others are
    listed as excluded even if they score higher. score = sum(w_c * value_c) with
    weights normalised to sum 1. The deciding criterion is the one whose weighted
    contribution gives the chosen tool its largest lead over the runner-up.
    """
    _no_extra(extra)
    example = candidates is None and registry is None
    if example:
        candidates, registry = _TOOL_EXAMPLE['candidates'], _TOOL_EXAMPLE['registry']
    if candidates is None:
        raise ValueError('candidates is required')
    if registry is None:
        raise ValueError('registry is required (list of registered tool ids)')
    reg = {_text(r, 'registry[]', max_len=MAX_KEY)
           for r in _list(registry, 'registry', max_items=1000)}
    w = dict(_DEFAULT_WEIGHTS)
    if weights is not None:
        given = _dict(weights, 'weights', max_items=3)
        for k, v in given.items():
            _choice(k, set(_CRITERIA), 'weights key')
            w[k] = _num(v, 0, 1, f'weights[{k}]')
    wsum = sum(w.values())
    if wsum <= 0:
        raise ValueError('weights must not all be zero')
    w = {k: w[k] / wsum for k in _CRITERIA}
    cands = _list(candidates, 'candidates', min_items=1, max_items=200)
    scored, seen = [], set()
    for i, c in enumerate(cands):
        c = _fields(c, f'candidates[{i}]', ('id',) + _CRITERIA)
        cid = _text(c['id'], f'candidates[{i}].id', max_len=MAX_KEY)
        if cid in seen:
            raise ValueError(f'duplicate candidate id: {cid}')
        seen.add(cid)
        vals = {k: _num(c[k], 0, 1, f'candidates[{i}].{k}') for k in _CRITERIA}
        contrib = {'accuracy': w['accuracy'] * vals['accuracy'],
                   'readiness': w['readiness'] * vals['readiness'],
                   'cost': w['cost'] * (1 - vals['cost'])}
        scored.append({'id': cid, 'values': vals, 'contributions': contrib,
                       'score': sum(contrib.values()), 'registered': cid in reg})
    eligible = sorted((s for s in scored if s['registered']), key=lambda s: (-s['score'], s['id']))
    excluded = [{'id': s['id'], 'score': s['score'], 'reason': 'not_registered'}
                for s in sorted(scored, key=lambda s: (-s['score'], s['id'])) if not s['registered']]
    best_overall = max(scored, key=lambda s: s['score'])
    chosen = eligible[0] if eligible else None
    runner = eligible[1] if len(eligible) > 1 else None
    if chosen is None:
        criterion, reason, status = None, 'مفيش أداة مسجّلة في الريجستري من المرشحين (no registered candidate)', \
            'no_eligible_tool'
    else:
        status = 'chosen'
        if runner is None:
            criterion = 'only_eligible'
            reason = f'اختيرت {chosen["id"]} لأنها الوحيدة المسجّلة (deciding criterion: only_eligible)'
        elif math.isclose(chosen['score'], runner['score'], abs_tol=1e-12):
            criterion = 'tie_break_id'
            reason = (f'اختيرت {chosen["id"]} بالتساوي مع {runner["id"]}، والفصل بالترتيب الأبجدي '
                      f'(deciding criterion: tie_break_id)')
        else:
            diffs = {k: chosen['contributions'][k] - runner['contributions'][k] for k in _CRITERIA}
            criterion = max(_CRITERIA, key=lambda k: (diffs[k], -_CRITERIA.index(k)))
            reason = (f'اختيرت {chosen["id"]} على {runner["id"]}: المعيار الحاسم «{criterion}» '
                      f'(deciding criterion: {criterion}) بفارق {diffs[criterion]:+.3f} من '
                      f'{chosen["score"] - runner["score"]:+.3f} في المجموع')
        if not best_overall['registered'] and best_overall['score'] > chosen['score']:
            reason += f'؛ {best_overall["id"]} أعلى درجة لكنها مش مسجّلة فاستبعدت'
    result = {'status': status, 'chosen': chosen['id'] if chosen else None,
              'deciding_criterion': criterion, 'reason': reason,
              'runner_up': runner['id'] if runner else None, 'weights': w,
              'ranking': [{'id': s['id'], 'score': s['score'], 'contributions': s['contributions']}
                          for s in eligible],
              'excluded': excluded, 'example': example}
    return _pack('tool_choice', result,
                 [RULES_NOT_NLU,
                  'cost, accuracy and readiness are caller-supplied estimates in [0, 1]',
                  'linear weighted sum; criteria are treated as independent',
                  'registry membership is the only eligibility test (it does not run the tool)'],
                 ['candidates <= 200, registry <= 1000 ids',
                  'ties are broken by tool id, deterministically'])


# --------------------------------------------------------------------------- 09.04 phase_machine

PHASES = ('understand', 'plan', 'execute', 'review', 'done')
ALLOWED_TRANSITIONS = {
    'understand': ('plan',),
    'plan': ('execute', 'understand'),
    'execute': ('review', 'plan'),
    'review': ('done', 'execute', 'plan'),
    'done': (),
}

_PHASE_EXAMPLE = [
    {'to': 'plan'}, {'to': 'execute'}, {'error': 'render failed: wrong codec'},
    {'to': 'done'}, {'to': 'review'}, {'to': 'execute'}, {'to': 'review'}, {'to': 'done'},
]


def phase_machine(*, events=None, start='understand', previous_errors=None, strict=False,
                  **extra):
    """Run a long task through understand -> plan -> execute -> review -> done.

    events: list of {'to': phase} (transition request) or {'error': text}
    (an error observed in the current phase). Only ALLOWED_TRANSITIONS are
    accepted; anything else (e.g. execute -> done, skipping review) is rejected
    and recorded, and the phase stays put. strict=True raises ValueError on the
    first rejection instead. previous_errors (error_counts from an earlier run)
    yields a per-phase and total error trend.
    """
    _no_extra(extra)
    example = events is None
    if example:
        events = _PHASE_EXAMPLE
    events = _list(events, 'events', max_items=2000)
    state = _choice(start, set(PHASES) - {'done'}, 'start')
    strict = _bool(strict, 'strict')
    prev = None
    if previous_errors is not None:
        prev = {}
        for k, v in _dict(previous_errors, 'previous_errors', max_items=len(PHASES)).items():
            prev[_choice(k, set(PHASES), 'previous_errors key')] = _int(
                v, 0, 10 ** 9, f'previous_errors[{k}]')
    errors = {p: 0 for p in PHASES}
    history = [{'step': 0, 'phase': state}]
    rejected, error_log = [], []
    for i, ev in enumerate(events, start=1):
        ev = _fields(ev, f'events[{i}]', optional=('to', 'error'))
        if ('to' in ev) == ('error' in ev):
            raise ValueError(f'events[{i}] must have exactly one of to / error')
        if 'error' in ev:
            errors[state] += 1
            error_log.append({'step': i, 'phase': state,
                              'error': _text(ev['error'], f'events[{i}].error', max_len=500)})
            continue
        to = _choice(ev['to'], set(PHASES), f'events[{i}].to')
        if to in ALLOWED_TRANSITIONS[state]:
            state = to
            history.append({'step': i, 'phase': state})
            continue
        if state == 'execute' and to == 'done':
            reason = 'skipping review is not allowed (execute -> done)'
        elif state == 'done':
            reason = 'task already done'
        else:
            reason = f'{state} -> {to} is not an allowed transition'
        if strict:
            raise ValueError(f'events[{i}]: {reason}')
        rejected.append({'step': i, 'from': state, 'to': to, 'reason': reason})
    total = sum(errors.values())
    trend = None
    if prev is not None:
        prev_full = {p: prev.get(p, 0) for p in PHASES}
        prev_total = sum(prev_full.values())
        trend = {'previous_total': prev_total, 'current_total': total,
                 'change': total - prev_total, 'improved': total < prev_total,
                 'per_phase_change': {p: errors[p] - prev_full[p] for p in PHASES},
                 'dropped_phases': [p for p in PHASES if errors[p] < prev_full[p]],
                 'rose_phases': [p for p in PHASES if errors[p] > prev_full[p]]}
    result = {'final_phase': state, 'completed': state == 'done',
              'reviewed': any(h['phase'] == 'review' for h in history),
              'history': history[-500:], 'rejected': rejected[-500:],
              'rejected_total': len(rejected), 'error_counts': errors, 'errors_total': total,
              'error_log': error_log[-500:], 'error_trend': trend,
              'allowed_transitions': {k: list(v) for k, v in ALLOWED_TRANSITIONS.items()},
              'example': example}
    return _pack('phase_machine', result,
                 [RULES_NOT_NLU,
                  'phases and transitions are fixed; done is reachable only from review',
                  'errors are counted in the phase that is current when they are reported',
                  'a rejected transition leaves the phase unchanged'],
                 ['events <= 2000; history, rejections and error log keep the last 500 entries'])


# --------------------------------------------------------------------------- 09.05 blind_review

_REVIEW_EXAMPLE = {
    'candidates': [
        {'author': 'agent_alpha', 'content': 'cut at 00:12 and 00:31, keep original audio'},
        {'author': 'agent_beta', 'content': 'cut at 00:10 only, add music bed'},
        {'author': 'agent_gamma', 'content': 'no cuts, trim tail to 30 s'},
    ],
    'scores': [
        {'evaluator': 'agent_alpha', 'candidate': 0, 'mode': 'blind', 'criteria': {'correctness': 6, 'clarity': 6}},
        {'evaluator': 'agent_alpha', 'candidate': 0, 'mode': 'known', 'criteria': {'correctness': 9, 'clarity': 9}},
        {'evaluator': 'agent_alpha', 'candidate': 1, 'mode': 'blind', 'criteria': {'correctness': 7, 'clarity': 7}},
        {'evaluator': 'agent_alpha', 'candidate': 1, 'mode': 'known', 'criteria': {'correctness': 7, 'clarity': 7}},
        {'evaluator': 'agent_beta', 'candidate': 1, 'mode': 'blind', 'criteria': {'correctness': 7, 'clarity': 8}},
        {'evaluator': 'agent_beta', 'candidate': 1, 'mode': 'known', 'criteria': {'correctness': 7, 'clarity': 8}},
        {'evaluator': 'agent_beta', 'candidate': 2, 'mode': 'blind', 'criteria': {'correctness': 8, 'clarity': 8}},
        {'evaluator': 'agent_beta', 'candidate': 2, 'mode': 'known', 'criteria': {'correctness': 8, 'clarity': 8}},
        {'evaluator': 'agent_gamma', 'candidate': 0, 'mode': 'blind', 'criteria': {'correctness': 6, 'clarity': 7}},
    ],
}


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def blind_review(*, candidates=None, scores=None, criteria=None, salt='red-rose',
                 bias_threshold=1.0, **extra):
    """Anonymise candidate results, score them blind, de-anonymise, and flag self-bias.

    candidates: [{'author', 'content'}] -> stable labels 'R-' + sha256(salt, content)[:10].
    scores: [{'evaluator', 'candidate' (index), 'mode' ('blind'|'known'), 'criteria': {name: 0..10}}].
    criteria: {name: weight}; default = equal weights over the criteria names used.
    Ranking uses blind scores only. Bias: for an evaluator who authored a candidate,
    bias = (known - blind on own work) - (known - blind on others' work, 0 if absent);
    flagged when bias >= bias_threshold (score points on the 0..10 scale).
    """
    _no_extra(extra)
    example = candidates is None and scores is None
    if example:
        candidates, scores = _REVIEW_EXAMPLE['candidates'], _REVIEW_EXAMPLE['scores']
    if candidates is None:
        raise ValueError('candidates is required')
    if scores is None:
        raise ValueError('scores is required')
    salt = _text(salt, 'salt', allow_empty=True, max_len=200)
    bias_threshold = _num(bias_threshold, 0, 10, 'bias_threshold')
    cands = []
    for i, c in enumerate(_list(candidates, 'candidates', min_items=2, max_items=50)):
        c = _fields(c, f'candidates[{i}]', ('author', 'content'))
        cands.append({'author': _text(c['author'], f'candidates[{i}].author', max_len=MAX_KEY),
                      'content': _text(c['content'], f'candidates[{i}].content', max_len=5000)})
    labels, used = [], set()
    for i, c in enumerate(cands):
        counter = 0
        while True:
            h = hashlib.sha256(f'{salt}\x00{c["content"]}\x00{counter}'.encode('utf-8')).hexdigest()
            label = 'R-' + h[:10]
            hides = all(o['author'].lower() not in label.lower()
                        for o in cands if len(o['author']) >= 3)
            if label not in used and hides:
                break
            counter += 1
            if counter > 10_000:
                raise ValueError('could not derive distinct anonymous labels')
        used.add(label)
        labels.append(label)
    raw = _list(scores, 'scores', max_items=2000)
    parsed = []
    for i, s in enumerate(raw):
        s = _fields(s, f'scores[{i}]', ('evaluator', 'candidate', 'mode', 'criteria'))
        crit = _dict(s['criteria'], f'scores[{i}].criteria', max_items=20)
        if not crit:
            raise ValueError(f'scores[{i}].criteria must not be empty')
        parsed.append({'evaluator': _text(s['evaluator'], f'scores[{i}].evaluator', max_len=MAX_KEY),
                       'candidate': _int(s['candidate'], 0, len(cands) - 1, f'scores[{i}].candidate'),
                       'mode': _choice(s['mode'], {'blind', 'known'}, f'scores[{i}].mode'),
                       'criteria': {k: _num(v, 0, 10, f'scores[{i}].criteria[{k}]')
                                    for k, v in crit.items()}})
    if criteria is None:
        names = sorted({k for p in parsed for k in p['criteria']})
        weights = {k: 1.0 for k in names}
    else:
        weights = {k: _num(v, 0, 1000, f'criteria[{k}]')
                   for k, v in _dict(criteria, 'criteria', max_items=20).items()}
    if parsed and (not weights or sum(weights.values()) <= 0):
        raise ValueError('criteria weights must not all be zero')
    for i, p in enumerate(parsed):
        if set(p['criteria']) != set(weights):
            raise ValueError(f'scores[{i}].criteria must score exactly: ' + ', '.join(sorted(weights)))
        p['total'] = sum(weights[k] * v for k, v in p['criteria'].items()) / sum(weights.values())
    ranking = []
    for i, label in enumerate(labels):
        blind = [p['total'] for p in parsed if p['candidate'] == i and p['mode'] == 'blind']
        ranking.append({'label': label, 'blind_mean': _mean(blind), 'blind_n': len(blind)})
    ranking.sort(key=lambda r: (r['blind_mean'] is None, -(r['blind_mean'] or 0.0), r['label']))
    author_of = {labels[i]: c['author'] for i, c in enumerate(cands)}
    de_anon = [dict(r, author=author_of[r['label']], rank=k + 1) for k, r in enumerate(ranking)]
    bias = []
    authors = sorted({c['author'] for c in cands})
    for ev in sorted({p['evaluator'] for p in parsed}):
        if ev not in authors:
            continue
        own = {i for i, c in enumerate(cands) if c['author'] == ev}

        def avg(mode, mine):
            return _mean([p['total'] for p in parsed if p['evaluator'] == ev and p['mode'] == mode
                          and (p['candidate'] in own) == mine])
        ko, bo, kx, bx = avg('known', True), avg('blind', True), avg('known', False), avg('blind', False)
        if ko is None or bo is None:
            bias.append({'evaluator': ev, 'status': 'insufficient_data', 'bias': None,
                         'flagged': False})
            continue
        own_delta = ko - bo
        other_delta = (kx - bx) if kx is not None and bx is not None else 0.0
        b = own_delta - other_delta
        bias.append({'evaluator': ev, 'status': 'measured', 'own_known_minus_blind': own_delta,
                     'others_known_minus_blind': other_delta, 'bias': b,
                     'flagged': b >= bias_threshold,
                     'note': 'confirmation bias: يرفع شغله لما يعرف إنه بتاعه' if b >= bias_threshold
                     else 'no systematic self-favouring above threshold'})
    result = {'blind_view': sorted(({'label': labels[i], 'content': c['content']}
                                    for i, c in enumerate(cands)), key=lambda x: x['label']),
              'blind_ranking': ranking, 'de_anonymised': de_anon, 'criteria_weights': weights,
              'bias': bias, 'flagged_evaluators': [b['evaluator'] for b in bias if b['flagged']],
              'bias_threshold': bias_threshold, 'example': example}
    return _pack('blind_review', result,
                 [RULES_NOT_NLU,
                  'labels hash the content only (plus salt), so they hide the author but identical '
                  'texts from different authors get distinct labels via a counter',
                  'ranking uses blind-mode scores only; known-mode scores are used only for bias',
                  'bias is a difference of means; with few scores it is noisy, not a statistical test'],
                 ['candidates <= 50, scores <= 2000, criteria <= 20, scores on a 0..10 scale',
                  'the caller must actually keep evaluators blind; the op cannot enforce that'])


# --------------------------------------------------------------------------- 09.06 resolve_conflict

PRIORITY = ('safety_rule', 'explicit_owner_now', 'earlier_owner', 'repo_rule', 'agent_suggestion')
_RANK = {lvl: i for i, lvl in enumerate(PRIORITY)}

_CONFLICT_EXAMPLE = [
    {'subject': 'publish', 'value': 'no_without_consent', 'source': 'safety_rule'},
    {'subject': 'publish', 'value': 'auto_publish', 'source': 'agent_suggestion'},
    {'subject': 'aspect', 'value': '16:9', 'source': 'earlier_owner'},
    {'subject': 'aspect', 'value': '9:16', 'source': 'explicit_owner_now'},
    {'subject': 'music', 'value': 'none', 'source': 'repo_rule'},
    {'subject': 'music', 'value': 'soft_bed', 'source': 'repo_rule'},
]


def resolve_conflict(*, commands=None, **extra):
    """Resolve contradictory commands per subject by a fixed priority hierarchy.

    PRIORITY (strongest first): safety_rule > explicit_owner_now > earlier_owner >
    repo_rule > agent_suggestion. Each command: {'subject', 'value', 'source'}.
    The strongest level present on a subject wins. If that level holds two or more
    different values, the subject is a conflict that needs a question to the owner
    (no winner is picked). Nothing outranks safety_rule, so a safety value can never
    be overridden; lower commands that contradict it are reported as blocked_by_safety.
    """
    _no_extra(extra)
    example = commands is None
    if example:
        commands = _CONFLICT_EXAMPLE
    commands = _list(commands, 'commands', min_items=1, max_items=500)
    groups = {}
    for i, c in enumerate(commands):
        c = _fields(c, f'commands[{i}]', ('subject', 'value', 'source'), ('id',))
        subject = _norm(_text(c['subject'], f'commands[{i}].subject', max_len=200))
        entry = {'index': i, 'subject': subject,
                 'value': _scalar(c['value'], f'commands[{i}].value'),
                 'source': _choice(c['source'], set(PRIORITY), f'commands[{i}].source')}
        if 'id' in c:
            entry['id'] = _text(c['id'], f'commands[{i}].id', max_len=MAX_KEY)
        groups.setdefault(subject, []).append(entry)
    subjects, questions = {}, []
    for subject in sorted(groups):
        items = sorted(groups[subject], key=lambda e: (_RANK[e['source']], e['index']))
        top_level = items[0]['source']
        top = [e for e in items if e['source'] == top_level]
        distinct = sorted({_canonical(e['value']) for e in top})
        if len(distinct) > 1:
            status = 'safety_conflict' if top_level == 'safety_rule' else 'needs_question'
            options = [json.loads(v) for v in distinct]
            subjects[subject] = {'status': status, 'winner': None, 'level': top_level,
                                 'options': options, 'commands': items}
            questions.append({'subject': subject, 'level': top_level, 'options': options,
                              'question': f'فيه أمرين متعارضين بنفس الأولوية ({top_level}) على '
                                          f'«{subject}»: أنهي واحد؟'})
            continue
        winner = top[0]['value']
        overridden, agreeing = [], []
        for e in items:
            if e in top:
                continue
            if _canonical(e['value']) == distinct[0]:
                agreeing.append(e)
            else:
                overridden.append(dict(e, overridden_by=top_level,
                                       blocked_by_safety=top_level == 'safety_rule'))
        subjects[subject] = {'status': 'resolved', 'winner': winner, 'level': top_level,
                             'overridden': overridden, 'agreeing': agreeing,
                             'commands': items}
    counts = {'resolved': 0, 'needs_question': 0, 'safety_conflict': 0}
    for s in subjects.values():
        counts[s['status']] += 1
    result = {'subjects': subjects, 'questions': questions, 'summary': counts,
              'priority': list(PRIORITY), 'example': example}
    return _pack('resolve_conflict', result,
                 [RULES_NOT_NLU,
                  'subjects are matched by normalised text equality; synonyms are not merged',
                  'source levels are caller-assigned; the op trusts the label it is given',
                  'safety_rule is the top level and cannot be outranked by any other level'],
                 ['commands <= 500; values are JSON scalars',
                  'ties at the winning level are never auto-resolved; they become questions'])


# --------------------------------------------------------------------------- 09.07 failure_log

_FAILURE_EXAMPLE = {
    'log': [
        {'action': 'render reel', 'cause_signature': 'audio silent on iPhone',
         'hypothesis': 'MP3 inside MP4', 'experiment': 'play on iPhone', 'fix': '',
         'outcome': 'fail'},
        {'action': 'render reel', 'cause_signature': 'audio silent on iPhone',
         'hypothesis': 'MP3 inside MP4', 'experiment': 'play on iPhone', 'fix': 'raise volume',
         'outcome': 'fail'},
    ],
    'attempt': {'action': 'render reel', 'cause_signature': 'audio silent on iPhone',
                'fix': 'raise volume'},
}


def failure_log(*, log=None, attempt=None, **extra):
    """Check a new attempt against a failure log before retrying.

    log: [{'action', 'cause_signature', 'outcome' ('fail'|'partial'|'success'),
           'hypothesis'?, 'experiment'?, 'fix'?}].
    attempt: {'action', 'cause_signature'?, 'fix'?}. Strings are compared after
    lower-casing and whitespace collapsing. If the same action already failed with the
    same cause signature (any signature when the attempt gives none) and the attempt's
    fix is empty or one already tried in those failures, verdict = 'blocked_repeat'.
    A different, non-empty fix gives 'allowed_new_fix'.
    """
    _no_extra(extra)
    example = log is None and attempt is None
    if example:
        log, attempt = _FAILURE_EXAMPLE['log'], _FAILURE_EXAMPLE['attempt']
    if log is None:
        raise ValueError('log is required')
    entries = []
    for i, e in enumerate(_list(log, 'log', max_items=MAX_ITEMS)):
        e = _fields(e, f'log[{i}]', ('action', 'cause_signature', 'outcome'),
                    ('hypothesis', 'experiment', 'fix'))
        entries.append({
            'index': i,
            'action': _text(e['action'], f'log[{i}].action', max_len=500),
            'cause_signature': _text(e['cause_signature'], f'log[{i}].cause_signature', max_len=500),
            'outcome': _choice(e['outcome'], {'fail', 'partial', 'success'}, f'log[{i}].outcome'),
            'hypothesis': _text(e.get('hypothesis', ''), f'log[{i}].hypothesis', allow_empty=True),
            'experiment': _text(e.get('experiment', ''), f'log[{i}].experiment', allow_empty=True),
            'fix': _text(e.get('fix', ''), f'log[{i}].fix', allow_empty=True, max_len=500),
        })
    by_sig = {}
    for e in entries:
        s = by_sig.setdefault(_norm(e['cause_signature']), {
            'cause_signature': e['cause_signature'], 'attempts': 0, 'fail': 0, 'partial': 0,
            'success': 0, 'fixes_tried': [], 'working_fixes': []})
        s['attempts'] += 1
        s[e['outcome']] += 1
        if e['fix'] and e['fix'] not in s['fixes_tried']:
            s['fixes_tried'].append(e['fix'])
        if e['outcome'] == 'success' and e['fix'] and e['fix'] not in s['working_fixes']:
            s['working_fixes'].append(e['fix'])
    check = None
    if attempt is not None:
        a = _fields(attempt, 'attempt', ('action',), ('cause_signature', 'fix'))
        action = _norm(_text(a['action'], 'attempt.action', max_len=500))
        sig = a.get('cause_signature')
        sig = None if sig is None else _norm(_text(sig, 'attempt.cause_signature', max_len=500))
        fix = _norm(_text(a.get('fix', ''), 'attempt.fix', allow_empty=True, max_len=500))
        failed = [e for e in entries if e['outcome'] == 'fail' and _norm(e['action']) == action
                  and (sig is None or _norm(e['cause_signature']) == sig)]
        tried = sorted({_norm(e['fix']) for e in failed})
        working = []
        for e in entries:
            if (e['outcome'] == 'success' and e['fix']
                    and (sig is None or _norm(e['cause_signature']) == sig)
                    and e['fix'] not in working):
                working.append(e['fix'])
        if not failed:
            verdict = 'allowed'
            reason = 'مفيش فشل مسجّل لنفس الفعل ونفس السبب'
        elif fix and fix not in tried:
            verdict = 'allowed_new_fix'
            reason = 'نفس الفعل فشل قبل كده، بس التصليح ده جديد'
        else:
            verdict = 'blocked_repeat'
            reason = ('نفس الفعل فشل لنفس السبب ' + str(len(failed)) + ' مرة، '
                      + ('ومن غير تصليح جديد' if not fix else 'والتصليح ده اتجرب وفشل')
                      + ': غيّر الطريقة أو جرّب فرضية تانية')
        check = {'verdict': verdict, 'flagged': verdict == 'blocked_repeat', 'reason': reason,
                 'matched_failures': [e['index'] for e in failed],
                 'fixes_already_failed': [f for f in tried if f],
                 'known_working_fixes': working}
    result = {'check': check, 'signatures': [by_sig[k] for k in sorted(by_sig)],
              'entries_total': len(entries), 'example': example}
    return _pack('failure_log', result,
                 [RULES_NOT_NLU,
                  'actions, cause signatures and fixes match only after case/space normalisation; '
                  'paraphrases are treated as different',
                  'only outcome "fail" blocks a repeat; "partial" is reported but does not block'],
                 ['log <= 500 entries, strings <= 500 characters',
                  'the op does not judge whether a "new" fix is meaningfully different'])


# --------------------------------------------------------------------------- 09.08 route_tested

_ADAPTER_STATUS = {'tested', 'untested', 'descriptive', 'blocked'}

DEFAULT_ROUTE_RULES = {
    'verify': ['video.verify'], 'تحقق': ['video.verify'], 'افحص': ['video.verify'],
    'cut': ['video.scene_analyze', 'video.recut'], 'cuts': ['video.scene_analyze', 'video.recut'],
    'قص': ['video.scene_analyze', 'video.recut'],
    'render': ['video.preview', 'video.produce'], 'رندر': ['video.preview', 'video.produce'],
    'physics': ['physics.simulate'], 'فيزياء': ['physics.simulate'],
    'search': ['knowledge.search', 'knowledge.route'], 'بحث': ['knowledge.search', 'knowledge.route'],
}

DEFAULT_ADAPTER_STATUS = {
    'video.verify': 'tested', 'video.scene_analyze': 'tested', 'video.recut': 'tested',
    'video.preview': 'tested', 'video.produce': 'untested', 'physics.simulate': 'tested',
    'knowledge.search': 'tested', 'knowledge.route': 'descriptive',
}

_AR_PREFIXES = ('وبال', 'وال', 'بال', 'فال', 'كال', 'لل', 'ال', 'و', 'ب', 'ف', 'ل')


def _tokens(text):
    toks = set()
    for tok in re.findall(r'[\w.]+', text.lower()):
        toks.add(tok)
        for p in _AR_PREFIXES:
            if tok.startswith(p) and len(tok) - len(p) >= 2:
                toks.add(tok[len(p):])
    return toks


def route_tested(*, task=None, rules=None, status=None, max_results=5, **extra):
    """Route a task to adapters by keyword rules, selecting only tested adapters.

    rules: {keyword: [adapter_id, ...]} (keywords are case-insensitive; Arabic tokens
    are also matched without common prefixes like ال/و/ب). status: {adapter_id:
    'tested'|'untested'|'descriptive'|'blocked'}; adapters missing from status count
    as 'unknown'. Matched adapters are ranked by number of keyword hits; only
    'tested' ones are selectable, the rest come back as «not executable».
    Defaults (when rules/status are omitted) are a small illustrative map, not the
    live registry: pass the real registry status for production use.
    """
    _no_extra(extra)
    example = task is None
    if example:
        if rules is not None or status is not None:
            raise ValueError('task is required')
        task = 'افحص الفيديو وبعدين رندر النسخة النهائية'
    task = _text(task, 'task', max_len=MAX_TEXT)
    max_results = _int(max_results, 1, 50, 'max_results')
    rules = DEFAULT_ROUTE_RULES if rules is None else rules
    status = DEFAULT_ADAPTER_STATUS if status is None else status
    rmap = {}
    for k, v in _dict(rules, 'rules', max_items=MAX_ITEMS).items():
        kw = _norm(_text(k, 'rules key', max_len=MAX_KEY))
        rmap[kw] = [_text(a, f'rules[{k}][]', max_len=MAX_KEY)
                    for a in _list(v, f'rules[{k}]', min_items=1, max_items=20)]
    smap = {_text(k, 'status key', max_len=MAX_KEY): _choice(v, _ADAPTER_STATUS, f'status[{k}]')
            for k, v in _dict(status, 'status', max_items=1000).items()}
    toks = _tokens(task)
    padded = ' ' + ' '.join(re.findall(r'[\w.]+', task.lower())) + ' '
    hits = {}
    for kw in sorted(rmap):
        matched = (kw in toks) if ' ' not in kw else (f' {kw} ' in padded)
        if not matched:
            continue
        for a in rmap[kw]:
            hits.setdefault(a, []).append(kw)
    ranked = sorted(hits, key=lambda a: (-len(hits[a]), a))
    selected = [{'adapter': a, 'hits': len(hits[a]), 'keywords': hits[a]}
                for a in ranked if smap.get(a) == 'tested'][:max_results]
    not_exec = [{'adapter': a, 'status': smap.get(a, 'unknown'), 'label': 'not executable',
                 'label_ar': 'غير قابل للتنفيذ', 'keywords': hits[a]}
                for a in ranked if smap.get(a) != 'tested']
    if not hits:
        route_status = 'no_match'
    elif selected:
        route_status = 'routed'
    else:
        route_status = 'no_tested_adapter'
    result = {'status': route_status, 'chosen': selected[0]['adapter'] if selected else None,
              'selected': selected, 'not_executable': not_exec, 'task_tokens': sorted(toks),
              'example': example}
    return _pack('route_tested', result,
                 [RULES_NOT_NLU,
                  'keyword match on tokens; Arabic prefix stripping is a fixed list, not morphology',
                  'tested status comes from the supplied status map; the op does not run tests',
                  'built-in defaults are illustrative and may differ from the live registry'],
                 ['rules <= 500 keywords x 20 adapters, status <= 1000 adapters, task <= 2000 chars',
                  f'at most {max_results} selected adapters returned'])


# --------------------------------------------------------------------------- 09.09 incomplete_info

_TYPES = {'number', 'string', 'bool', 'any'}

_INCOMPLETE_EXAMPLE = {
    'required': [{'name': 'duration_s', 'type': 'number'}, {'name': 'platform', 'type': 'string'}],
    'provided': {'duration_s': 42},
    'rules': [
        {'when': [{'input': 'platform', 'op': '==', 'value': 'reels'},
                  {'input': 'duration_s', 'op': '>', 'value': 90}], 'then': 'trim_to_90'},
        {'when': [{'input': 'platform', 'op': '==', 'value': 'reels'}], 'then': 'keep'},
    ],
    'default_decision': 'keep',
}


def _type_ok(value, typ):
    if typ == 'any':
        return True
    if typ == 'number':
        return _is_number(value)
    if typ == 'string':
        return isinstance(value, str)
    return isinstance(value, bool)


def incomplete_info(*, required=None, provided=None, rules=None, default_decision=None,
                    safe_default='ask_owner', **extra):
    """Decide only when every required input is present; otherwise return gaps.

    required: [name | {'name', 'type': number|string|bool|any}]. provided: {name: scalar}.
    rules: [{'when': [{'input', 'op', 'value'}], 'then': decision}] evaluated in order;
    default_decision applies when inputs are complete but no rule matches.
    A required input that is absent, None or an empty string is 'missing'; a wrong
    type is 'wrong_type'. With any gap: status 'needs_input', decision None, the
    safe_default action, and the gap list. Missing values are reported as None,
    never filled in.
    """
    _no_extra(extra)
    example = required is None and provided is None and rules is None
    if example:
        ex = _INCOMPLETE_EXAMPLE
        required, provided, rules = ex['required'], ex['provided'], ex['rules']
        default_decision = ex['default_decision']
    if required is None:
        raise ValueError('required is required (list of input names)')
    if provided is None:
        raise ValueError('provided is required (object of input values)')
    req = []
    for i, r in enumerate(_list(required, 'required', min_items=1, max_items=100)):
        if isinstance(r, str):
            req.append({'name': _text(r, f'required[{i}]', max_len=MAX_KEY), 'type': 'any'})
        else:
            r = _fields(r, f'required[{i}]', ('name',), ('type',))
            req.append({'name': _text(r['name'], f'required[{i}].name', max_len=MAX_KEY),
                        'type': _choice(r.get('type', 'any'), _TYPES, f'required[{i}].type')})
    names = [r['name'] for r in req]
    if len(set(names)) != len(names):
        raise ValueError('required names must be unique')
    prov = {k: _scalar(v, f'provided[{k}]')
            for k, v in _dict(provided, 'provided', max_items=200).items()}
    parsed_rules = _parse_rules([] if rules is None else rules, 'rules')
    for i, rule in enumerate(parsed_rules):
        for c in rule['when']:
            if c['input'] not in names:
                raise ValueError(f'rules[{i}] uses input {c["input"]!r} that is not in required')
    default_decision = _scalar(default_decision, 'default_decision')
    safe_default = _scalar(safe_default, 'safe_default')
    gaps, values = [], {}
    for r in req:
        v = prov.get(r['name'])
        if v is None or (isinstance(v, str) and not v.strip()):
            gaps.append({'name': r['name'], 'problem': 'missing', 'expected_type': r['type']})
            values[r['name']] = None
        elif not _type_ok(v, r['type']):
            gaps.append({'name': r['name'], 'problem': 'wrong_type', 'expected_type': r['type'],
                         'got_type': type(v).__name__})
            values[r['name']] = None
        else:
            values[r['name']] = v
    ignored = sorted(k for k in prov if k not in names)
    if gaps:
        result = {'status': 'needs_input', 'decision': None, 'rule_applied': None,
                  'safe_action': safe_default, 'gaps': gaps, 'values': values,
                  'ignored_inputs': ignored, 'example': example}
    else:
        decision, idx = _apply_rules(parsed_rules, values, default_decision)
        result = {'status': 'decided' if idx is not None or decision is not None
                  else 'no_rule_matched',
                  'decision': decision, 'rule_applied': idx,
                  'rule_text': _rule_text(parsed_rules[idx]) if idx is not None else None,
                  'safe_action': None, 'gaps': [], 'values': values,
                  'ignored_inputs': ignored, 'example': example}
    return _pack('incomplete_info', result,
                 [RULES_NOT_NLU,
                  'a gap is never filled by guessing: missing values stay None and no decision is made',
                  'empty strings count as missing; type checks are shallow (number/string/bool)',
                  'rules are evaluated in order; the first fully matching rule wins'],
                 ['required <= 100, provided <= 200, rules <= 100 with <= 10 conditions each',
                  'the safe action is whatever the caller supplies (default ask_owner)'])


# --------------------------------------------------------------------------- 09.10 decision_record

RECORD_VERSION = 'red-rose/decision_record/1'

_RECORD_EXAMPLE = {
    'inputs': {'duration_s': 31.2, 'platform': 'reels', 'max_duration_s': 30},
    'rules': [{'name': 'too_long', 'when': [{'input': 'duration_s', 'op': '>', 'value': 30}],
               'then': 'trim'}],
    'default': 'keep',
    'evidence': ['ffprobe:format.duration=31.2', 'owner_rule:A12'],
}


def _build_record(inputs, rules, default, evidence):
    canonical = _canonical(inputs)
    decision, idx = _apply_rules(rules, inputs, default)
    body = {'version': RECORD_VERSION,
            'input_canonical_json': canonical,
            'input_sha256': hashlib.sha256(canonical.encode('utf-8')).hexdigest(),
            'evidence': evidence, 'rules': rules, 'default': default,
            'rule_applied': idx,
            'rule_applied_text': _rule_text(rules[idx]) if idx is not None else 'default',
            'result': decision}
    return dict(body, record_sha256=_sha256(body))


def decision_record(*, mode='build', inputs=None, rules=None, default=None, evidence=None,
                    record=None, **extra):
    """Build or verify an auditable decision record.

    build: inputs (JSON object), rules (same format as incomplete_info; conditions
    read top-level input keys), default, evidence (list of reference strings).
    The record holds sha256 of the canonical JSON of the inputs (sorted keys, compact,
    UTF-8), the evidence refs, the rules, the rule applied and the result, plus a
    record_sha256 over all of that.
    verify: record (+ optional current inputs; default = the record's own inputs).
    Recomputes both hashes and the decision; ok only when all match.
    """
    _no_extra(extra)
    mode = _choice(mode, {'build', 'verify'}, 'mode')
    if mode == 'build':
        if record is not None:
            raise ValueError('record is only used with mode="verify"')
        example = inputs is None and rules is None and evidence is None
        if example:
            ex = _RECORD_EXAMPLE
            inputs, rules, default, evidence = ex['inputs'], ex['rules'], ex['default'], ex['evidence']
        if inputs is None:
            raise ValueError('inputs is required')
        inputs = _json_value(_dict(inputs, 'inputs', max_items=MAX_ITEMS), 'inputs')
        parsed = _parse_rules([] if rules is None else rules, 'rules')
        default = _scalar(default, 'default')
        ev = [_text(e, 'evidence[]', max_len=500)
              for e in _list([] if evidence is None else evidence, 'evidence', max_items=100)]
        rec = _build_record(inputs, parsed, default, ev)
        result = {'mode': 'build', 'record': rec, 'example': example}
    else:
        if record is None:
            raise ValueError('record is required for mode="verify"')
        if rules is not None or default is not None or evidence is not None:
            raise ValueError('verify takes only record and optional inputs')
        rec = _fields(record, 'record',
                      ('version', 'input_canonical_json', 'input_sha256', 'evidence', 'rules',
                       'default', 'rule_applied', 'rule_applied_text', 'result', 'record_sha256'))
        try:
            rec_text = _canonical(rec)
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError(f'record is not JSON-serialisable: {exc}') from exc
        if len(rec_text) > 4 * MAX_JSON_CHARS:
            raise ValueError('record is too large')
        rec = json.loads(rec_text)
        if not isinstance(rec['record_sha256'], str):
            raise ValueError('record.record_sha256 must be a string')
        if rec['version'] != RECORD_VERSION:
            raise ValueError(f'record.version must be {RECORD_VERSION}')
        stored_inputs_text = _text(rec['input_canonical_json'], 'record.input_canonical_json',
                                   allow_empty=True, max_len=MAX_JSON_CHARS)
        try:
            stored_inputs = json.loads(stored_inputs_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f'record.input_canonical_json is not JSON: {exc}') from exc
        if inputs is None:
            current = _json_value(_dict(stored_inputs, 'record inputs'), 'record inputs')
        else:
            current = _json_value(_dict(inputs, 'inputs', max_items=MAX_ITEMS), 'inputs')
        parsed = _parse_rules(rec['rules'], 'record.rules')
        ev = [_text(e, 'record.evidence[]', max_len=500)
              for e in _list(rec['evidence'], 'record.evidence', max_items=100)]
        body = {k: v for k, v in rec.items() if k != 'record_sha256'}
        rebuilt = _build_record(current, parsed, _scalar(rec['default'], 'record.default'), ev)
        checks = {
            'record_hash_matches': _sha256(body) == rec['record_sha256'],
            'input_hash_matches': rebuilt['input_sha256'] == rec['input_sha256'],
            'decision_matches': (rebuilt['result'] == rec['result']
                                 and rebuilt['rule_applied'] == rec['rule_applied']),
        }
        result = {'mode': 'verify', 'ok': all(checks.values()), 'checks': checks,
                  'recomputed_input_sha256': rebuilt['input_sha256'],
                  'recomputed_result': rebuilt['result'],
                  'recomputed_rule_applied': rebuilt['rule_applied'], 'example': False}
    return _pack('decision_record', result,
                 [RULES_NOT_NLU,
                  'canonical JSON = sorted keys, compact separators, UTF-8, no NaN/Infinity',
                  'hashes prove the record matches these inputs and rules, not that the inputs '
                  'or evidence are true',
                  'sha256 detects changes; it is not a signature (no key, no author proof)'],
                 [f'inputs <= {MAX_JSON_CHARS} JSON characters, depth <= {MAX_JSON_DEPTH}, '
                  f'nodes <= {MAX_JSON_NODES}',
                  'rules <= 100, evidence refs <= 100'])


def verify(record, inputs=None):
    """Recompute a decision record: run('decision_record', mode='verify')."""
    params = {'mode': 'verify', 'record': record}
    if inputs is not None:
        params['inputs'] = inputs
    return run('decision_record', params)


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'intent_state': intent_state, 'confidence': confidence, 'tool_choice': tool_choice,
    'phase_machine': phase_machine, 'blind_review': blind_review,
    'resolve_conflict': resolve_conflict, 'failure_log': failure_log,
    'route_tested': route_tested, 'incomplete_info': incomplete_info,
    'decision_record': decision_record,
}


def run(op, params=None):
    """Validate and dispatch: run('confidence', {...}) -> {'op','result','assumptions','limits'}."""
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
