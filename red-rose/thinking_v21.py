"""Red Rose V21: small, bounded, deterministic structured-thinking helpers.

Pure standard-library Python. No file I/O, no subprocess, no network, no printing.
Every op validates its inputs strictly (ValueError on wrong types, bools-as-numbers,
non-finite values, unknown parameter names and out-of-range values) and caps its
work (list sizes, text lengths, bisection iterations) so it cannot run away.

These helpers check the *structure* of a piece of reasoning (is every hypothesis
falsifiable, is every risk controlled, is every plan input produced ...). They do
not understand meaning: text is compared as normalised word tokens only. Each op
returns the assumptions it makes and the limits it enforces next to its result.
"""
from __future__ import annotations

import json
import math
import re

MAX_PARAMS = 24
MAX_ITEMS = 200
MAX_TEXT = 2000
MAX_TOKENS_LIST = 50

TOPICS = {
    '04.01': 'first_principles',
    '04.02': 'alternatives',
    '04.03': 'causal',
    '04.04': 'decision_matrix',
    '04.05': 'premortem',
    '04.06': 'budget_filter',
    '04.07': 'plan_gaps',
    '04.08': 'lesson_match',
    '04.09': 'poc_gate',
    '04.10': 'aesthetic_decision',
}

TOPIC_NAMES_AR = {
    '04.01': 'تفكيك المشكلة إلى مبادئ أولية',
    '04.02': 'توليد بدائل تصميم أصيلة',
    '04.03': 'الاستدلال السببي للنتائج',
    '04.04': 'التقييم متعدد المعايير',
    '04.05': 'التفكير العكسي قبل التنفيذ',
    '04.06': 'الابتكار بقيود الموارد',
    '04.07': 'اكتشاف ثغرات الخطة',
    '04.08': 'الاستفادة من الأخطاء الماضية',
    '04.09': 'توليد تجارب صغيرة سريعة',
    '04.10': 'الموازنة بين الدقة والجمال',
}


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


def _text(value, name, *, required=True, max_len=MAX_TEXT):
    """Return a stripped string, '' if missing and not required."""
    if value is None:
        if required:
            raise ValueError(f'{name} is required')
        return ''
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    if len(value) > max_len:
        raise ValueError(f'{name} must be at most {max_len} characters')
    value = value.strip()
    if required and not value:
        raise ValueError(f'{name} must not be empty')
    return value


def _list(value, name, low=0, high=MAX_ITEMS):
    if not isinstance(value, (list, tuple)) or not low <= len(value) <= high:
        raise ValueError(f'{name} must be a list of {low}..{high} items')
    return list(value)


def _dict(value, name):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object/dict')
    if len(value) > 50:
        raise ValueError(f'{name} has too many keys (max 50)')
    if not all(isinstance(k, str) for k in value):
        raise ValueError(f'{name} keys must be strings')
    return value


def _keys(item, allowed, name):
    bad = set(item) - set(allowed)
    if bad:
        raise ValueError(f'{name} has unknown key(s): ' + ', '.join(sorted(bad)))


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


# --------------------------------------------------------------------------- text normalisation

_AR_DIACRITICS = re.compile('[ؐ-ًؚ-ٰٟۖ-ۭ]')
_AR_MAP = str.maketrans({
    'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',  # alef forms -> ا
    'ى': 'ي',  # ى -> ي
    'ة': 'ه',  # ة -> ه
    'ـ': None,      # tatweel
})
_TOKEN = re.compile(r'\w+', re.UNICODE)


def normalize_text(text):
    """Lowercase; strip Arabic diacritics and tatweel; unify alef / ya / ta-marbuta."""
    text = _AR_DIACRITICS.sub('', text.lower())
    return text.translate(_AR_MAP)


def tokens(text):
    return [t for t in _TOKEN.findall(normalize_text(text)) if t]


def _jaccard(a, b):
    a, b = set(a), set(b)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


# --------------------------------------------------------------------------- 04.01 first_principles

_FP_DEFAULT = [
    {'statement': 'The render is slow because the encoder preset is too slow.',
     'assumptions': ['CPU encoding dominates render time'],
     'prediction': 'Switching preset from slow to fast cuts render time by over 30%.',
     'counterexample': 'Render time barely changes when the preset changes.'},
    {'statement': 'The render is slow because of disk I/O on a network drive.',
     'assumptions': ['Source media is read from a network drive', 'Disk is the bottleneck'],
     'prediction': 'Copying the media locally cuts render time by over 30%.',
     'counterexample': 'Local media renders just as slowly.'},
]


def first_principles(*, hypotheses=None, **extra):
    """Break a problem into falsifiable hypotheses.

    Each hypothesis: {statement, assumptions: [str], prediction, counterexample}.
    A hypothesis lacking a testable prediction or a counterexample (what would
    prove it wrong) is rejected with its index. Accepted hypotheses are ordered
    by parsimony: fewest assumptions first, then input order. Assumptions shared
    by several hypotheses are listed (they are the first things to test).
    """
    _no_extra(extra)
    if hypotheses is None:
        hypotheses = _FP_DEFAULT
    hyps = _list(hypotheses, 'hypotheses', 1)
    accepted, rejected = [], []
    seen = {}
    for i, h in enumerate(hyps):
        h = _dict(h, f'hypotheses[{i}]')
        _keys(h, {'statement', 'assumptions', 'prediction', 'counterexample'}, f'hypotheses[{i}]')
        statement = _text(h.get('statement'), f'hypotheses[{i}].statement')
        assumptions = [_text(a, f'hypotheses[{i}].assumptions[{j}]')
                       for j, a in enumerate(_list(h.get('assumptions', []),
                                                   f'hypotheses[{i}].assumptions', 0, MAX_TOKENS_LIST))]
        prediction = _text(h.get('prediction'), f'hypotheses[{i}].prediction', required=False)
        counter = _text(h.get('counterexample'), f'hypotheses[{i}].counterexample', required=False)
        reasons = []
        if not prediction:
            reasons.append('missing testable prediction')
        if not counter:
            reasons.append('missing counterexample (what would prove it wrong)')
        if reasons:
            rejected.append({'index': i, 'statement': statement, 'reasons': reasons})
            continue
        for a in assumptions:
            key = ' '.join(tokens(a))
            seen.setdefault(key, {'assumption': a, 'hypotheses': []})['hypotheses'].append(i)
        accepted.append({'index': i, 'statement': statement, 'assumptions': assumptions,
                         'assumption_count': len(assumptions), 'prediction': prediction,
                         'counterexample': counter})
    accepted.sort(key=lambda e: (e['assumption_count'], e['index']))
    for rank, e in enumerate(accepted, 1):
        e['rank'] = rank
    shared = [v for v in seen.values() if len(v['hypotheses']) > 1]
    result = {'status': 'accepted' if not rejected else 'rejected',
              'accepted': accepted, 'rejected': rejected,
              'rejected_indices': [r['index'] for r in rejected],
              'shared_assumptions': shared}
    return _pack('first_principles', result,
                 ['a hypothesis is usable only if it names a testable prediction and a counterexample',
                  'ordering is by parsimony (fewest stated assumptions), not by truth or probability',
                  'لا يفهم المعنى: يتحقق من وجود الحقول وتطابق الافتراضات بالكلمات فقط'],
                 [f'<= {MAX_ITEMS} hypotheses', f'<= {MAX_TOKENS_LIST} assumptions each',
                  f'texts <= {MAX_TEXT} characters'])


# --------------------------------------------------------------------------- 04.02 alternatives

_ALT_DEFAULT = [
    {'name': 'A', 'benefit': 0.8, 'risk': 0.3, 'cost': 0.6,
     'approach': 'render everything in Blender with full path tracing'},
    {'name': 'B', 'benefit': 0.6, 'risk': 0.2, 'cost': 0.3,
     'approach': 'composite stock footage with ffmpeg overlays'},
    {'name': 'C', 'benefit': 0.5, 'risk': 0.4, 'cost': 0.5,
     'approach': 'hand drawn frames scanned and animated in Krita'},
]


def alternatives(*, options=None, duplicate_threshold=0.8, **extra):
    """Compare >= 3 genuinely different design options and find the Pareto front.

    Each option: {name, benefit, risk, cost (all 0..1), approach (short text)}.
    Rejects fewer than 3 options and any pair whose approach texts have token
    Jaccard similarity >= duplicate_threshold (near-duplicates are not real
    alternatives). Pareto front: options not dominated on (benefit high, risk low,
    cost low).
    """
    _no_extra(extra)
    if options is None:
        options = _ALT_DEFAULT
    duplicate_threshold = _num(duplicate_threshold, 0.0, 1.0, 'duplicate_threshold')
    opts = _list(options, 'options', 0)
    if len(opts) < 3:
        raise ValueError('need at least 3 design options')
    rows = []
    names = set()
    for i, o in enumerate(opts):
        o = _dict(o, f'options[{i}]')
        _keys(o, {'name', 'benefit', 'risk', 'cost', 'approach'}, f'options[{i}]')
        name = _text(o.get('name', f'option_{i}'), f'options[{i}].name', max_len=200)
        if name in names:
            raise ValueError(f'duplicate option name: {name}')
        names.add(name)
        rows.append({'index': i, 'name': name,
                     'benefit': _num(o.get('benefit'), 0, 1, f'options[{i}].benefit'),
                     'risk': _num(o.get('risk'), 0, 1, f'options[{i}].risk'),
                     'cost': _num(o.get('cost'), 0, 1, f'options[{i}].cost'),
                     'approach': _text(o.get('approach'), f'options[{i}].approach', max_len=500)})
    toks = [tokens(r['approach']) for r in rows]
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            sim = _jaccard(toks[i], toks[j])
            if sim >= duplicate_threshold:
                raise ValueError(f'options {i} and {j} have near-duplicate approaches '
                                 f'(token Jaccard {sim:.3f} >= {duplicate_threshold})')

    def dominates(a, b):
        ge = a['benefit'] >= b['benefit'] and a['risk'] <= b['risk'] and a['cost'] <= b['cost']
        gt = a['benefit'] > b['benefit'] or a['risk'] < b['risk'] or a['cost'] < b['cost']
        return ge and gt

    table = []
    for r in rows:
        dom_by = [o['name'] for o in rows if o is not r and dominates(o, r)]
        table.append({**r, 'net': r['benefit'] - (r['risk'] + r['cost']) / 2,
                      'dominated_by': dom_by, 'pareto': not dom_by})
    max_sim = max((_jaccard(toks[i], toks[j]) for i in range(len(rows))
                   for j in range(i + 1, len(rows))), default=0.0)
    result = {'table': table, 'pareto_front': [r['name'] for r in table if r['pareto']],
              'max_approach_similarity': max_sim}
    return _pack('alternatives', result,
                 ['benefit, risk and cost are caller estimates on a 0..1 scale',
                  'Pareto: higher benefit, lower risk, lower cost; net = benefit - (risk + cost) / 2 is only a tie-hint',
                  'لا يفهم المعنى، يقارن كلمات فقط: نهجان بكلمات مختلفة ومعنى واحد لن يُكتشفا كتكرار'],
                 [f'3..{MAX_ITEMS} options', 'approach text <= 500 characters',
                  f'near-duplicate when token Jaccard >= {duplicate_threshold}'])


# --------------------------------------------------------------------------- 04.03 causal

_CAUSAL_DEFAULT = {
    'nodes': ['budget', 'crew', 'quality', 'deadline_risk'],
    'edges': [['budget', 'crew', 0.5], ['crew', 'quality', 0.8], ['crew', 'deadline_risk', -0.4]],
    'base': {'budget': 10.0, 'crew': 1.0, 'quality': 2.0, 'deadline_risk': 5.0},
}


def _topo(nodes, children, indeg):
    indeg = dict(indeg)
    order = []
    ready = [n for n in nodes if indeg[n] == 0]
    while ready:
        n = ready.pop(0)
        order.append(n)
        for c, _ in children[n]:
            indeg[c] -= 1
            if indeg[c] == 0:
                ready.append(c)
    return order


def causal(*, nodes=None, edges=None, base=None, do=None, **extra):
    """Linear structural causal model on a DAG with one do()-intervention.

    value(n) = base[n] + sum(weight * value(parent)) for edges parent -> n.
    Cycles are rejected. do = {node: value} (exactly one variable) fixes that
    node, cuts its incoming edges and recomputes; only its descendants can change.
    """
    _no_extra(extra)
    if nodes is None and edges is None and base is None:
        nodes, edges, base = (_CAUSAL_DEFAULT['nodes'], _CAUSAL_DEFAULT['edges'],
                              _CAUSAL_DEFAULT['base'])
        if do is None:
            do = {'budget': 20.0}
    if nodes is None:
        raise ValueError('nodes is required')
    names = [_text(n, f'nodes[{i}]', max_len=200) for i, n in enumerate(_list(nodes, 'nodes', 1))]
    if len(set(names)) != len(names):
        raise ValueError('node names must be unique')
    known = set(names)
    children = {n: [] for n in names}
    parents = {n: [] for n in names}
    indeg = {n: 0 for n in names}
    pairs = set()
    for i, e in enumerate(_list(edges if edges is not None else [], 'edges', 0, 1000)):
        if not isinstance(e, (list, tuple)) or len(e) != 3:
            raise ValueError(f'edges[{i}] must be [source, target, weight]')
        s = _text(e[0], f'edges[{i}][0]', max_len=200)
        t = _text(e[1], f'edges[{i}][1]', max_len=200)
        w = _num(e[2], -1e3, 1e3, f'edges[{i}][2]')
        if s not in known or t not in known:
            raise ValueError(f'edges[{i}] refers to an unknown node')
        if s == t:
            raise ValueError(f'edges[{i}] is a self-loop (cycle) on {s}')
        if (s, t) in pairs:
            raise ValueError(f'edges[{i}] duplicates {s} -> {t}')
        pairs.add((s, t))
        children[s].append((t, w))
        parents[t].append((s, w))
        indeg[t] += 1
    base = _dict(base if base is not None else {}, 'base')
    for k in base:
        if k not in known:
            raise ValueError(f'base refers to unknown node {k}')
    b = {n: _num(base.get(n, 0.0), -1e6, 1e6, f'base[{n}]') for n in names}
    order = _topo(names, children, indeg)
    if len(order) != len(names):
        cyc = sorted(set(names) - set(order))
        raise ValueError('graph has a cycle among: ' + ', '.join(cyc))

    target = None
    if do is not None:
        do = _dict(do, 'do')
        if len(do) != 1:
            raise ValueError('do must fix exactly one variable: {node: value}')
        target, tval = next(iter(do.items()))
        if target not in known:
            raise ValueError(f'do refers to unknown node {target}')
        tval = _num(tval, -1e6, 1e6, f'do[{target}]')

    def evaluate(fixed=None):
        val = {}
        for n in order:
            if fixed is not None and n == fixed[0]:
                val[n] = fixed[1]
            else:
                val[n] = b[n] + sum(w * val[p] for p, w in parents[n])
            if not math.isfinite(val[n]) or abs(val[n]) > 1e300:
                raise ValueError('values overflow; reduce weights or base values')
        return val

    baseline = evaluate()
    result = {'order': order, 'values': baseline, 'intervention': None}
    if target is not None:
        desc, stack = set(), [target]
        while stack:
            for c, _ in children[stack.pop()]:
                if c not in desc:
                    desc.add(c)
                    stack.append(c)
        after = evaluate((target, tval))
        changed = [n for n in order if after[n] != baseline[n]]
        result['intervention'] = {
            'do': {target: tval}, 'values': after,
            'descendants': [n for n in order if n in desc],
            'changed': changed,
            'effect': {n: after[n] - baseline[n] for n in order},
            'only_descendants_changed': all(n == target or n in desc for n in changed)}
    return _pack('causal', result,
                 ['linear additive structural equations, no noise terms, no interaction effects',
                  'the graph is the caller\'s causal assumption; the op cannot discover causes from data',
                  'do() replaces the equation of one node (cuts its incoming edges)'],
                 [f'<= {MAX_ITEMS} nodes, <= 1000 edges', '|weight| <= 1e3, |base| <= 1e6',
                  'exactly one intervened variable per call'])


# --------------------------------------------------------------------------- 04.04 decision_matrix

_DM_DEFAULT = {
    'options': ['A', 'B'],
    'criteria': ['quality', 'speed'],
    'weights': [0.6, 0.4],
    'scores': [[8.0, 4.0], [5.0, 7.0]],
}


def decision_matrix(*, options=None, criteria=None, weights=None, scores=None,
                    tie_tol=1e-9, **extra):
    """Weighted decision matrix with per-criterion flip-point sensitivity.

    scores[i][j] = score of option i on criterion j (higher is better).
    Weights are normalised to sum 1. For each criterion j the raw weight w_j is
    changed by delta (others fixed, then renormalised); bisection finds the
    smallest increase and the smallest decrease that make the current winner stop
    being the sole winner (tie point). Ties within tie_tol are reported.
    """
    _no_extra(extra)
    if options is None and criteria is None and weights is None and scores is None:
        options, criteria, weights, scores = (_DM_DEFAULT['options'], _DM_DEFAULT['criteria'],
                                              _DM_DEFAULT['weights'], _DM_DEFAULT['scores'])
    if options is None or criteria is None or scores is None:
        raise ValueError('options, criteria and scores are required')
    tie_tol = _num(tie_tol, 0.0, 1e-3, 'tie_tol')
    opts = [_text(o, f'options[{i}]', max_len=200) for i, o in enumerate(_list(options, 'options', 2, 50))]
    crit = [_text(c, f'criteria[{i}]', max_len=200) for i, c in enumerate(_list(criteria, 'criteria', 1, 30))]
    if len(set(opts)) != len(opts) or len(set(crit)) != len(crit):
        raise ValueError('option and criterion names must be unique')
    if weights is None:
        weights = [1.0] * len(crit)
    w = [_num(x, 0, 1e6, f'weights[{j}]') for j, x in enumerate(_list(weights, 'weights', len(crit), len(crit)))]
    total_w = sum(w)
    if total_w <= 0:
        raise ValueError('weights must not all be zero')
    w = [x / total_w for x in w]
    sc = _list(scores, 'scores', len(opts), len(opts))
    s = []
    for i, row in enumerate(sc):
        row = _list(row, f'scores[{i}]', len(crit), len(crit))
        s.append([_num(v, -1e6, 1e6, f'scores[{i}][{j}]') for j, v in enumerate(row)])

    def totals(wts):
        tw = sum(wts)
        return [sum(a * b for a, b in zip(wts, row)) / tw for row in s]

    def winners(tot):
        best = max(tot)
        return [i for i, t in enumerate(tot) if best - t <= tie_tol]

    base_tot = totals(w)
    win = winners(base_tot)
    tie = len(win) > 1
    ranking = sorted(range(len(opts)), key=lambda i: (-base_tot[i], i))

    def sole(wts, k):
        tot = totals(wts)
        return all(tot[k] - t > tie_tol for i, t in enumerate(tot) if i != k)

    sensitivity = []
    for j in range(len(crit)):
        entry = {'criterion': crit[j], 'weight': w[j], 'increase': None, 'decrease': None}
        if not tie:
            k = win[0]
            for direction, bound in (('increase', 1e6), ('decrease', -w[j])):
                if direction == 'decrease' and 1 + bound <= 1e-12:
                    bound = -w[j] + 1e-9
                if bound == 0:
                    continue

                def at(d):
                    ww = list(w)
                    ww[j] = w[j] + d
                    return ww
                if sole(at(bound), k):
                    continue
                lo, hi = 0.0, bound
                for _ in range(200):
                    mid = 0.5 * (lo + hi)
                    if sole(at(mid), k):
                        lo = mid
                    else:
                        hi = mid
                    if abs(hi - lo) < 1e-13:
                        break
                ww = at(hi)
                new_tot = totals(ww)
                entry[direction] = {
                    'weight_delta': hi,
                    'flip_weight': ww[j] / sum(ww),
                    'new_winners': [opts[i] for i in winners(new_tot)]}
        cands = [abs(entry[d]['weight_delta']) for d in ('increase', 'decrease') if entry[d]]
        entry['smallest_flip_delta'] = min(cands) if cands else None
        sensitivity.append(entry)
    result = {'weights_normalised': dict(zip(crit, w)),
              'totals': dict(zip(opts, base_tot)),
              'ranking': [opts[i] for i in ranking],
              'winner': None if tie else opts[win[0]],
              'tie': tie, 'tied_options': [opts[i] for i in win] if tie else [],
              'sensitivity': sensitivity}
    return _pack('decision_matrix', result,
                 ['additive weighted sum: criteria are independent and compensatory',
                  'scores share one direction (higher is better) and comparable scales',
                  'sensitivity changes one raw weight at a time, then renormalises; flip = first tie with the winner',
                  'no sensitivity search when the winner is already tied'],
                 ['2..50 options, 1..30 criteria', 'bisection <= 200 iterations, tolerance ~1e-13',
                  'weight increase searched up to +1e6'])


# --------------------------------------------------------------------------- 04.05 premortem

_PM_DEFAULT = {
    'causes': [
        {'id': 'audio_silent', 'description': 'MP3 audio inside MP4 is silent on iPhone',
         'likelihood': 2, 'impact': 3},
        {'id': 'black_frames', 'description': 'black frames at the start', 'likelihood': 1, 'impact': 2},
        {'id': 'wrong_length', 'description': 'final length differs from the brief', 'likelihood': 2, 'impact': 2},
    ],
    'controls': [{'cause_id': 'audio_silent', 'action': 'force AAC audio and verify with ffprobe'}],
}


def premortem(*, causes=None, controls=None, threshold=4, **extra):
    """Imagine the delivery failed: rank failure causes and flag uncontrolled ones.

    causes: [{id, description, likelihood 0..3, impact 0..3}], risk = likelihood * impact (0..9).
    controls: [{cause_id, action}]. Every cause with risk >= threshold and no
    control is flagged; status is 'blocked' while any flag remains.
    """
    _no_extra(extra)
    if causes is None:
        if controls is not None:
            raise ValueError('causes is required')
        causes, controls = _PM_DEFAULT['causes'], _PM_DEFAULT['controls']
    threshold = _num(threshold, 0, 9, 'threshold')
    rows, ids = [], set()
    for i, c in enumerate(_list(causes, 'causes', 1)):
        c = _dict(c, f'causes[{i}]')
        _keys(c, {'id', 'description', 'likelihood', 'impact'}, f'causes[{i}]')
        cid = _text(c.get('id'), f'causes[{i}].id', max_len=200)
        if cid in ids:
            raise ValueError(f'duplicate cause id: {cid}')
        ids.add(cid)
        lk = _num(c.get('likelihood'), 0, 3, f'causes[{i}].likelihood')
        im = _num(c.get('impact'), 0, 3, f'causes[{i}].impact')
        rows.append({'index': i, 'id': cid,
                     'description': _text(c.get('description', ''), f'causes[{i}].description', required=False),
                     'likelihood': lk, 'impact': im, 'risk': lk * im, 'controls': []})
    by_id = {r['id']: r for r in rows}
    for i, k in enumerate(_list(controls if controls is not None else [], 'controls', 0)):
        k = _dict(k, f'controls[{i}]')
        _keys(k, {'cause_id', 'action'}, f'controls[{i}]')
        cid = _text(k.get('cause_id'), f'controls[{i}].cause_id', max_len=200)
        if cid not in by_id:
            raise ValueError(f'controls[{i}] refers to unknown cause {cid}')
        by_id[cid]['controls'].append(_text(k.get('action'), f'controls[{i}].action'))
    rows.sort(key=lambda r: (-r['risk'], -r['impact'], r['index']))
    flagged = []
    for r in rows:
        r['high_risk'] = r['risk'] >= threshold
        r['uncontrolled'] = r['high_risk'] and not r['controls']
        if r['uncontrolled']:
            flagged.append(r['id'])
    result = {'ranked': rows, 'flagged': flagged, 'threshold': threshold,
              'status': 'blocked' if flagged else 'clear'}
    return _pack('premortem', result,
                 ['risk = likelihood x impact on 0..3 ordinal scales (a heuristic, not a probability)',
                  'a control counts if it is mapped to the cause; its effectiveness is not checked',
                  'only causes the caller imagined are considered'],
                 [f'<= {MAX_ITEMS} causes and controls', 'likelihood and impact in [0, 3], threshold in [0, 9]'])


# --------------------------------------------------------------------------- 04.06 budget_filter

_BF_DEFAULT = {
    'options': [
        {'name': '4k_raytrace', 'time_s': 3600, 'memory_mb': 14000, 'quality': 0.95},
        {'name': '1080p_eevee', 'time_s': 600, 'memory_mb': 6000, 'quality': 0.8},
        {'name': 'proxy_preview', 'time_s': 60, 'memory_mb': 1500, 'quality': 0.4},
    ],
    'time_budget_s': 900, 'memory_budget_mb': 8000,
}


def budget_filter(*, options=None, time_budget_s=None, memory_budget_mb=None, **extra):
    """Pick the best-quality option that fits a time and memory budget.

    options: [{name, time_s, memory_mb, quality}]. An option exceeding either
    budget is rejected (with the exceeded resources) whatever its quality. The
    best feasible option has the highest quality; ties go to lower time, then
    lower memory, then input order.
    """
    _no_extra(extra)
    if options is None and time_budget_s is None and memory_budget_mb is None:
        options = _BF_DEFAULT['options']
        time_budget_s = _BF_DEFAULT['time_budget_s']
        memory_budget_mb = _BF_DEFAULT['memory_budget_mb']
    if options is None or time_budget_s is None or memory_budget_mb is None:
        raise ValueError('options, time_budget_s and memory_budget_mb are required')
    tb = _num(time_budget_s, 0, 1e7, 'time_budget_s')
    mb = _num(memory_budget_mb, 0, 1e7, 'memory_budget_mb')
    feasible, rejected = [], []
    for i, o in enumerate(_list(options, 'options', 1)):
        o = _dict(o, f'options[{i}]')
        _keys(o, {'name', 'time_s', 'memory_mb', 'quality'}, f'options[{i}]')
        row = {'index': i, 'name': _text(o.get('name'), f'options[{i}].name', max_len=200),
               'time_s': _num(o.get('time_s'), 0, 1e7, f'options[{i}].time_s'),
               'memory_mb': _num(o.get('memory_mb'), 0, 1e7, f'options[{i}].memory_mb'),
               'quality': _num(o.get('quality'), -1e6, 1e6, f'options[{i}].quality')}
        exceeded = []
        if row['time_s'] > tb:
            exceeded.append({'resource': 'time_s', 'needed': row['time_s'], 'budget': tb})
        if row['memory_mb'] > mb:
            exceeded.append({'resource': 'memory_mb', 'needed': row['memory_mb'], 'budget': mb})
        if exceeded:
            rejected.append({**row, 'exceeded': exceeded})
        else:
            feasible.append({**row, 'time_headroom_s': tb - row['time_s'],
                             'memory_headroom_mb': mb - row['memory_mb']})
    feasible.sort(key=lambda r: (-r['quality'], r['time_s'], r['memory_mb'], r['index']))
    result = {'best': feasible[0]['name'] if feasible else None,
              'feasible': feasible, 'rejected': rejected,
              'budget': {'time_s': tb, 'memory_mb': mb}}
    return _pack('budget_filter', result,
                 ['time_s and memory_mb are caller estimates (peak memory, wall time); not measured here',
                  'budgets are hard limits: equal to the budget is allowed, above is rejected',
                  'quality is a single caller-supplied score (higher is better)'],
                 [f'<= {MAX_ITEMS} options', 'time and memory values in [0, 1e7]'])


# --------------------------------------------------------------------------- 04.07 plan_gaps

_PG_DEFAULT = {
    'steps': [
        {'id': 'load', 'inputs': ['brief'], 'outputs': ['clips'], 'kind': 'action'},
        {'id': 'cut', 'inputs': ['clips', 'music'], 'outputs': ['edit', 'notes'], 'kind': 'action'},
        {'id': 'render', 'inputs': ['edit'], 'outputs': ['video.mp4'], 'kind': 'write'},
    ],
    'initial_inputs': ['brief'],
    'final_outputs': ['video.mp4'],
}


def plan_gaps(*, steps=None, initial_inputs=None, final_outputs=None, gap_log=None, **extra):
    """Adversarial plan check with a closing log.

    steps: [{id, inputs: [], outputs: [], kind: 'action'|'write'|'verify'}] in order.
    Gap types:
      unproduced_input  a step consumes an item no earlier step produced and not in initial_inputs
      unused_output     an output no later step consumes and not in final_outputs
      unverified_write  a 'write' step with no later 'verify' step consuming one of its outputs
    gap_log: [{gap_id, status: 'open'|'closed', closed_by}]. A gap counts as closed
    only when its log entry is 'closed' and records how (non-empty closed_by).
    """
    _no_extra(extra)
    if steps is None:
        if any(v is not None for v in (initial_inputs, final_outputs, gap_log)):
            raise ValueError('steps is required')
        steps = _PG_DEFAULT['steps']
        initial_inputs = _PG_DEFAULT['initial_inputs']
        final_outputs = _PG_DEFAULT['final_outputs']

    def items(v, name):
        return [_text(x, f'{name}[{k}]', max_len=200)
                for k, x in enumerate(_list(v if v is not None else [], name, 0, MAX_TOKENS_LIST))]

    init = set(items(initial_inputs, 'initial_inputs'))
    final = set(items(final_outputs, 'final_outputs'))
    plan, ids = [], set()
    for i, st in enumerate(_list(steps, 'steps', 1)):
        st = _dict(st, f'steps[{i}]')
        _keys(st, {'id', 'inputs', 'outputs', 'kind'}, f'steps[{i}]')
        sid = _text(st.get('id', f'step_{i}'), f'steps[{i}].id', max_len=200)
        if sid in ids:
            raise ValueError(f'duplicate step id: {sid}')
        ids.add(sid)
        plan.append({'id': sid, 'inputs': items(st.get('inputs'), f'steps[{i}].inputs'),
                     'outputs': items(st.get('outputs'), f'steps[{i}].outputs'),
                     'kind': _choice(st.get('kind', 'action'), {'action', 'write', 'verify'},
                                     f'steps[{i}].kind')})
    gaps = []
    produced = set(init)
    for st in plan:
        for x in st['inputs']:
            if x not in produced:
                gaps.append({'gap_id': f'unproduced_input:{st["id"]}:{x}', 'type': 'unproduced_input',
                             'step': st['id'], 'item': x})
        produced |= set(st['outputs'])
    for i, st in enumerate(plan):
        later = plan[i + 1:]
        later_inputs = {x for s in later for x in s['inputs']}
        for x in st['outputs']:
            if x not in later_inputs and x not in final:
                gaps.append({'gap_id': f'unused_output:{st["id"]}:{x}', 'type': 'unused_output',
                             'step': st['id'], 'item': x})
        if st['kind'] == 'write':
            outs = set(st['outputs'])
            if not any(s['kind'] == 'verify' and outs & set(s['inputs']) for s in later):
                gaps.append({'gap_id': f'unverified_write:{st["id"]}', 'type': 'unverified_write',
                             'step': st['id'], 'item': None})
    gap_ids = {g['gap_id'] for g in gaps}
    log, invalid, unknown = {}, [], []
    for i, e in enumerate(_list(gap_log if gap_log is not None else [], 'gap_log', 0)):
        e = _dict(e, f'gap_log[{i}]')
        _keys(e, {'gap_id', 'status', 'closed_by'}, f'gap_log[{i}]')
        gid = _text(e.get('gap_id'), f'gap_log[{i}].gap_id', max_len=500)
        status = _choice(e.get('status', 'open'), {'open', 'closed'}, f'gap_log[{i}].status')
        how = _text(e.get('closed_by'), f'gap_log[{i}].closed_by', required=False)
        if gid not in gap_ids:
            unknown.append({'index': i, 'gap_id': gid})
            continue
        if status == 'closed' and not how:
            invalid.append({'index': i, 'gap_id': gid,
                            'reason': "status 'closed' requires closed_by (how the gap was closed)"})
            continue
        log[gid] = {'status': status, 'closed_by': how or None}
    for g in gaps:
        rec = log.get(g['gap_id'])
        g['status'] = rec['status'] if rec else 'open'
        g['closed_by'] = rec['closed_by'] if rec and rec['status'] == 'closed' else None
    open_gaps = [g['gap_id'] for g in gaps if g['status'] == 'open']
    counts = {t: sum(1 for g in gaps if g['type'] == t)
              for t in ('unproduced_input', 'unused_output', 'unverified_write')}
    result = {'gaps': gaps, 'counts': counts, 'open_gaps': open_gaps,
              'invalid_log_entries': invalid, 'unknown_log_entries': unknown,
              'status': 'ok' if not open_gaps else 'gaps_open'}
    return _pack('plan_gaps', result,
                 ['items are matched by exact name; the same artefact under two names looks like a gap',
                  'steps run in the given order; no parallelism or loops are modelled',
                  'a verify step counts if it consumes the written output; what it checks is not inspected'],
                 [f'<= {MAX_ITEMS} steps', f'<= {MAX_TOKENS_LIST} inputs/outputs per step',
                  f'<= {MAX_ITEMS} gap log entries'])


# --------------------------------------------------------------------------- 04.08 lesson_match

_LM_DEFAULT = {
    'lessons': [
        {'id': 'L1', 'cause': 'الصوت ساكت على الآيفون لأن الصوت MP3 جوه MP4',
         'fix': 'استخدم AAC دايما', 'bad_action': 'encode audio as mp3 inside mp4'},
        {'id': 'L2', 'cause': 'glow overlay lifted the blacks and was rejected',
         'fix': 'no overlays unless requested by name', 'bad_action': 'add bloom overlay'},
    ],
    'failure': 'الفيديو طلع من غير صوت على الايفون',
    'plan_actions': ['cut the clips', 'encode audio as MP3 inside MP4'],
}


def lesson_match(*, lessons=None, failure=None, plan_actions=None, min_score=0.1,
                 repeat_threshold=0.8, top_k=5, **extra):
    """Rank documented lessons against a current failure and flag repeated bad actions.

    lessons: [{id, cause (text or token list), fix, bad_action (optional)}].
    Text is normalised (lowercase; Arabic diacritics and tatweel removed;
    أ/إ/آ/ٱ -> ا, ى -> ي, ة -> ه) and compared by token Jaccard. The best lesson
    with score >= min_score is the match. repeat_risk is raised when a plan action
    contains every token of a documented bad_action, or has Jaccard >= repeat_threshold with it.
    """
    _no_extra(extra)
    if lessons is None and failure is None:
        lessons, failure = _LM_DEFAULT['lessons'], _LM_DEFAULT['failure']
        if plan_actions is None:
            plan_actions = _LM_DEFAULT['plan_actions']
    if lessons is None or failure is None:
        raise ValueError('lessons and failure are required')
    min_score = _num(min_score, 0, 1, 'min_score')
    repeat_threshold = _num(repeat_threshold, 0, 1, 'repeat_threshold')
    top_k = _int(top_k, 1, MAX_ITEMS, 'top_k')
    ftoks = tokens(_text(failure, 'failure'))
    if not ftoks:
        raise ValueError('failure has no word tokens')
    rows, ids = [], set()
    for i, l in enumerate(_list(lessons, 'lessons', 1)):
        l = _dict(l, f'lessons[{i}]')
        _keys(l, {'id', 'cause', 'fix', 'bad_action'}, f'lessons[{i}]')
        lid = _text(l.get('id', f'lesson_{i}'), f'lessons[{i}].id', max_len=200)
        if lid in ids:
            raise ValueError(f'duplicate lesson id: {lid}')
        ids.add(lid)
        cause = l.get('cause')
        if isinstance(cause, (list, tuple)):
            ctoks = []
            for j, t in enumerate(_list(cause, f'lessons[{i}].cause', 1, MAX_TOKENS_LIST)):
                ctoks += tokens(_text(t, f'lessons[{i}].cause[{j}]', max_len=200))
        else:
            ctoks = tokens(_text(cause, f'lessons[{i}].cause'))
        bad = _text(l.get('bad_action'), f'lessons[{i}].bad_action', required=False)
        rows.append({'index': i, 'id': lid, 'fix': _text(l.get('fix'), f'lessons[{i}].fix'),
                     'bad_action': bad or None, '_ctoks': ctoks, '_btoks': tokens(bad) if bad else [],
                     'score': _jaccard(ftoks, ctoks) if ctoks else 0.0,
                     'shared_tokens': sorted(set(ftoks) & set(ctoks))})
    ranked = sorted(rows, key=lambda r: (-r['score'], r['index']))
    actions = [_text(a, f'plan_actions[{k}]', max_len=500)
               for k, a in enumerate(_list(plan_actions if plan_actions is not None else [],
                                           'plan_actions', 0))]
    repeats = []
    for k, a in enumerate(actions):
        atoks = tokens(a)
        for r in rows:
            if not r['_btoks'] or not atoks:
                continue
            sim = _jaccard(atoks, r['_btoks'])
            if set(r['_btoks']) <= set(atoks) or sim >= repeat_threshold:
                repeats.append({'plan_index': k, 'plan_action': a, 'lesson_id': r['id'],
                                'bad_action': r['bad_action'], 'similarity': sim, 'fix': r['fix']})
    public = [{key: v for key, v in r.items() if not key.startswith('_')} for r in ranked[:top_k]]
    best = public[0] if public and public[0]['score'] >= min_score else None
    result = {'failure_tokens': ftoks, 'ranked': public, 'matched': best,
              'repeat_risk': bool(repeats), 'repeats': repeats}
    return _pack('lesson_match', result,
                 ['لا يفهم المعنى، يقارن كلمات فقط: المرادفات واختلاف الصياغة لا تتطابق',
                  'Arabic normalisation: diacritics/tatweel removed, alef/ya/ta-marbuta unified; no stemming (ال prefix is kept)',
                  'repeat risk is a token match against documented bad actions, not a semantic judgement'],
                 [f'<= {MAX_ITEMS} lessons and plan actions', f'texts <= {MAX_TEXT} characters',
                  f'top_k <= {MAX_ITEMS}'])


# --------------------------------------------------------------------------- 04.09 poc_gate

_HEX64 = re.compile(r'[0-9a-f]{64}')
_POC_DEFAULT = {
    'artifact_path': 'output/poc_reel.mp4',
    'sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    'metric_name': 'render_seconds', 'metric_value': 12.4,
    'target': 20.0, 'direction': 'min',
}


def poc_gate(*, record=None, **extra):
    """Gate a proof-of-concept record: tangible artifact + hash + measured metric.

    record: {artifact_path, sha256 (64 hex chars), metric_name, metric_value,
    target, direction: 'max' (value >= target) | 'min' (value <= target)}.
    Returns 'accepted' only when everything is present and the metric meets the
    target; otherwise 'rejected' with every reason. The hash is checked for
    format only; the file itself is not read.
    """
    _no_extra(extra)
    rec = _dict(_POC_DEFAULT if record is None else record, 'record')
    _keys(rec, {'artifact_path', 'sha256', 'metric_name', 'metric_value', 'target', 'direction'},
          'record')
    reasons = []
    path = _text(rec.get('artifact_path'), 'record.artifact_path', required=False, max_len=1000)
    if not path:
        reasons.append('missing artifact_path (no tangible artifact)')
    digest = _text(rec.get('sha256'), 'record.sha256', required=False, max_len=200).lower()
    if not digest:
        reasons.append('missing sha256 hash')
    elif not _HEX64.fullmatch(digest):
        reasons.append('sha256 must be exactly 64 hexadecimal characters')
    name = _text(rec.get('metric_name'), 'record.metric_name', required=False, max_len=200)
    if not name:
        reasons.append('missing metric_name')
    value = rec.get('metric_value')
    if value is None:
        reasons.append('missing measured metric_value')
    else:
        value = _num(value, -1e12, 1e12, 'record.metric_value')
    target = rec.get('target')
    if target is None:
        reasons.append('missing target')
    else:
        target = _num(target, -1e12, 1e12, 'record.target')
    direction = _choice(rec.get('direction', 'max'), {'max', 'min'}, 'record.direction')
    meets = None
    if value is not None and target is not None:
        meets = value >= target if direction == 'max' else value <= target
        if not meets:
            reasons.append(f'metric {value} does not meet target '
                           f'({">=" if direction == "max" else "<="} {target})')
    result = {'status': 'accepted' if not reasons else 'rejected', 'reasons': reasons,
              'artifact_path': path or None, 'sha256': digest or None,
              'metric': {'name': name or None, 'value': value, 'target': target,
                         'direction': direction, 'meets_target': meets}}
    return _pack('poc_gate', result,
                 ['the record is self-reported: the file is not read and the hash is not recomputed here',
                  'sha256 is checked for format (64 hex characters) only',
                  'one metric per record; direction says whether higher or lower is better'],
                 ['artifact_path <= 1000 characters', '|metric_value|, |target| <= 1e12'])


# --------------------------------------------------------------------------- 04.10 aesthetic_decision

_AD_DEFAULT = {
    'decision': 'use warm grade on the corniche reel',
    'example_id': 'frame_0420_warm',
    'criteria': [
        {'name': 'black_level_ire', 'measured': 2.0, 'threshold': 4.0, 'direction': '<='},
        {'name': 'skin_hue_deg', 'measured': 22.0, 'threshold': 18.0, 'direction': '>='},
    ],
    'human_review': None,
}


def aesthetic_decision(*, decision=None, **extra):
    """Tie an aesthetic choice to a visual example and measurable criteria.

    decision: {decision (text), example_id, criteria: [{name, measured, threshold,
    direction '>=' | '<='}], human_review: {reviewer, approved: bool, note} | None}.
    Status: 'rejected' (no example_id, no criteria, or a criterion without a
    measured value/threshold), 'failed_criteria', 'pending_review' (all criteria
    pass but no human review), 'rejected_by_review', or 'approved'.
    """
    _no_extra(extra)
    d = _dict(_AD_DEFAULT if decision is None else decision, 'decision')
    _keys(d, {'decision', 'example_id', 'criteria', 'human_review'}, 'decision')
    text = _text(d.get('decision'), 'decision.decision', required=False)
    reasons = []
    example = _text(d.get('example_id'), 'decision.example_id', required=False, max_len=200)
    if not example:
        reasons.append('missing example_id (link to a visual example)')
    crit_in = _list(d.get('criteria') if d.get('criteria') is not None else [], 'decision.criteria', 0, 50)
    if not crit_in:
        reasons.append('no observable criterion')
    crit = []
    for i, c in enumerate(crit_in):
        c = _dict(c, f'criteria[{i}]')
        _keys(c, {'name', 'measured', 'threshold', 'direction'}, f'criteria[{i}]')
        name = _text(c.get('name', f'criterion_{i}'), f'criteria[{i}].name', max_len=200)
        direction = _choice(c.get('direction', '>='), {'>=', '<='}, f'criteria[{i}].direction')
        m, t = c.get('measured'), c.get('threshold')
        if m is None or t is None:
            reasons.append(f'criterion {i} ({name}) lacks a measured value or threshold')
            crit.append({'name': name, 'measured': None, 'threshold': None,
                         'direction': direction, 'passes': None})
            continue
        m = _num(m, -1e12, 1e12, f'criteria[{i}].measured')
        t = _num(t, -1e12, 1e12, f'criteria[{i}].threshold')
        crit.append({'name': name, 'measured': m, 'threshold': t, 'direction': direction,
                     'passes': m >= t if direction == '>=' else m <= t})
    review = d.get('human_review')
    rev = None
    if review is not None:
        review = _dict(review, 'decision.human_review')
        _keys(review, {'reviewer', 'approved', 'note'}, 'decision.human_review')
        approved = review.get('approved')
        if not isinstance(approved, bool):
            raise ValueError('human_review.approved must be true or false')
        rev = {'reviewer': _text(review.get('reviewer'), 'human_review.reviewer', max_len=200),
               'approved': approved,
               'note': _text(review.get('note'), 'human_review.note', required=False) or None}
    if reasons:
        status = 'rejected'
    elif not all(c['passes'] for c in crit):
        status = 'failed_criteria'
    elif rev is None:
        status = 'pending_review'
    elif not rev['approved']:
        status = 'rejected_by_review'
    else:
        status = 'approved'
    result = {'status': status, 'reasons': reasons, 'decision': text or None,
              'example_id': example or None, 'criteria': crit, 'human_review': rev,
              'failed_criteria': [c['name'] for c in crit if c['passes'] is False]}
    return _pack('aesthetic_decision', result,
                 ['measured values are supplied by the caller; nothing is measured from pixels here',
                  'criteria are necessary, not sufficient: taste still needs a named human reviewer',
                  'لا يحكم على الجمال بنفسه؛ يتحقق فقط من الربط بمثال ومعايير مقاسة ومراجعة بشرية'],
                 ['<= 50 criteria', 'measured/threshold in [-1e12, 1e12]'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'first_principles': first_principles, 'alternatives': alternatives, 'causal': causal,
    'decision_matrix': decision_matrix, 'premortem': premortem, 'budget_filter': budget_filter,
    'plan_gaps': plan_gaps, 'lesson_match': lesson_match, 'poc_gate': poc_gate,
    'aesthetic_decision': aesthetic_decision,
}


def run(op, params=None):
    """Validate and dispatch: run('premortem', {...}) -> {'op','result','assumptions','limits'}."""
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
