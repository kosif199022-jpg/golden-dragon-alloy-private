"""Red Rose V22: governance helpers for keeping Red Rose ONE independent skill.

Pure standard-library Python. No file I/O, no subprocess, no network, no
printing, no dynamic code execution. Registries, file listings and source
texts arrive as parameters; this module never reads the project itself and
never imports other project modules (legacy Golden/Black Dragon or Alloy code
in particular). Every op validates its inputs strictly (ValueError on wrong
types, unknown parameter names and out-of-range sizes), caps its work, and
returns the assumptions it makes and the limits it enforces next to its result.

These checks are bookkeeping aids: they report what the supplied data claims
and whether it is internally consistent. They do not execute adapters, read
files or prove that a test really passed.
"""
from __future__ import annotations

import ast
import datetime
import difflib
import hashlib
import json
import re
import unicodedata

MAX_PARAMS = 24
MAX_ITEMS = 500
MAX_TEXT = 100_000
MAX_AUDIT_FILES = 200
MAX_AUDIT_CHARS = 2_000_000
MAX_SNAPSHOT_FILES = 500
MAX_SNAPSHOT_BYTES = 5_000_000
MAX_DEPTH = 32

DEFAULT_LEGACY_NAMES = ('dragon', 'black_dragon', 'blackdragon', 'golden_dragon',
                        'alloy', 'rd.py', 'kosif')

LEVELS = ('proposed', 'approved', 'coded', 'unit_tested', 'e2e_verified')

SCHEMA_TYPES = frozenset({'string', 'number', 'integer', 'boolean', 'object',
                          'array', 'null', 'any'})

SPDX_LICENCES = frozenset({
    '0BSD', 'AFL-3.0', 'AGPL-3.0-only', 'AGPL-3.0-or-later', 'Apache-2.0',
    'Artistic-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'BSL-1.0', 'CC-BY-4.0',
    'CC-BY-SA-4.0', 'CC-BY-NC-4.0', 'CC-BY-NC-SA-4.0', 'CC-BY-ND-4.0', 'CC0-1.0',
    'EPL-2.0', 'EUPL-1.2', 'GPL-2.0-only', 'GPL-2.0-or-later', 'GPL-3.0-only',
    'GPL-3.0-or-later', 'ISC', 'LGPL-2.1-only', 'LGPL-2.1-or-later',
    'LGPL-3.0-only', 'LGPL-3.0-or-later', 'MIT', 'MIT-0', 'MPL-2.0', 'OFL-1.1',
    'PSF-2.0', 'Python-2.0', 'Unlicense', 'WTFPL', 'Zlib',
})
COPYLEFT = frozenset({'AGPL-3.0-only', 'AGPL-3.0-or-later', 'GPL-2.0-only',
                      'GPL-2.0-or-later', 'GPL-3.0-only', 'GPL-3.0-or-later',
                      'LGPL-2.1-only', 'LGPL-2.1-or-later', 'LGPL-3.0-only',
                      'LGPL-3.0-or-later', 'MPL-2.0', 'EPL-2.0', 'EUPL-1.2',
                      'CC-BY-SA-4.0', 'CC-BY-NC-SA-4.0'})
NON_COMMERCIAL = frozenset({'CC-BY-NC-4.0', 'CC-BY-NC-SA-4.0'})
NO_DERIVATIVES = frozenset({'CC-BY-ND-4.0'})

TOPICS = {
    '01.01': 'skill_contract',
    '01.02': 'provenance_card',
    '01.03': 'behaviour_compare',
    '01.04': 'capability_overlap',
    '01.05': 'legacy_import_audit',
    '01.06': 'adapter_reality',
    '01.07': 'capability_passport',
    '01.08': 'approval_lifecycle',
    '01.09': 'snapshot_restore',
    '01.10': 'completion_matrix',
}

TOPIC_NAMES_AR = {
    '01.01': 'تعريف عقد المهارة الواحدة',
    '01.02': 'خريطة المصادر وإثبات النسب',
    '01.03': 'استخلاص الخوارزمية دون نسخ',
    '01.04': 'كشف التكرار بين المهارات',
    '01.05': 'منع الاعتمادية على محركات التنين',
    '01.06': 'استبدال الواجهات الوصفية بمحولات فعلية',
    '01.07': 'جواز القدرة والحدود',
    '01.08': 'دورة اعتماد المقترحات',
    '01.09': 'حفظ النسخ من دون إتلاف الأصل',
    '01.10': 'تعريف معيار اكتمال الصهر',
}

_ID_RE = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$')
_DEP_RE = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.+\-]*$')
_FIELD_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_SEMVER_RE = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
_SYMBOL_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$')
_HEX64_RE = re.compile(r'^[0-9a-f]{64}$')


# --------------------------------------------------------------------------- validation

def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _str(value, name, *, max_len=256, allow_empty=False):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    if not allow_empty and not value.strip():
        raise ValueError(f'{name} must not be empty')
    if len(value) > max_len:
        raise ValueError(f'{name} must be at most {max_len} characters')
    if '\x00' in value:
        raise ValueError(f'{name} must not contain NUL characters')
    return value


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _num(value, low, high, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or value != value or value in (float('inf'), float('-inf'))):
        raise ValueError(f'{name} must be a finite number')
    if not low <= value <= high:
        raise ValueError(f'{name} must be in [{low}, {high}]')
    return float(value)


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _list(value, name, max_len=MAX_ITEMS, min_len=0):
    if not isinstance(value, (list, tuple)) or not min_len <= len(value) <= max_len:
        raise ValueError(f'{name} must be a list of {min_len}..{max_len} items')
    return list(value)


def _dict(value, name, max_len=MAX_ITEMS):
    if not isinstance(value, dict) or len(value) > max_len:
        raise ValueError(f'{name} must be a dict with at most {max_len} keys')
    if not all(isinstance(k, str) for k in value):
        raise ValueError(f'{name} keys must be strings')
    return value


def _jsonable(value, name):
    try:
        json.dumps(value, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError(f'{name} must be JSON-serialisable with string keys: {exc}') from exc
    return value


def _legacy_names(value):
    if value is None:
        return list(DEFAULT_LEGACY_NAMES)
    names = _list(value, 'legacy_names', 50, 1)
    out = []
    for i, n in enumerate(names):
        n = _str(n, f'legacy_names[{i}]', max_len=64).strip().casefold()
        if n not in out:
            out.append(n)
    return out


def _legacy_hits(text, names):
    """Legacy names found in text: case-insensitive, start must not follow a letter/digit."""
    if not isinstance(text, str) or not text:
        return []
    low = text.casefold()
    hits = []
    for n in names:
        start = low.find(n)
        while start != -1:
            if start == 0 or not low[start - 1].isalnum():
                hits.append(n)
                break
            start = low.find(n, start + 1)
    return hits


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False)


def _sha256_text(text):
    try:
        data = text.encode('utf-8')
    except UnicodeEncodeError as exc:
        raise ValueError(f'text is not encodable as UTF-8: {exc}') from exc
    return hashlib.sha256(data).hexdigest(), len(data)


def _iso_date(value, name):
    _str(value, name, max_len=10)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


# --------------------------------------------------------------------------- 01.01 skill_contract

_EXAMPLE_CONTRACT = {
    'id': 'video.verify', 'version': '1.0.0', 'effect': 'read',
    'inputs': {'path': 'string', 'expected_fps': 'number'},
    'outputs': {'ok': 'boolean', 'report': 'object'},
    'dependencies': ['ffprobe'], 'entry_point': 'media_qa.verify',
}


def _schema_errors(schema, name):
    errors = []
    if not isinstance(schema, dict):
        return [f'{name} must be an object mapping field -> type']
    if len(schema) > 100:
        return [f'{name} may have at most 100 fields']
    for key, spec in schema.items():
        if not isinstance(key, str) or not _FIELD_RE.match(key):
            errors.append(f'{name}: field name {key!r} is not an identifier')
            continue
        kind = spec.get('type') if isinstance(spec, dict) else spec
        if not isinstance(kind, str) or kind not in SCHEMA_TYPES:
            errors.append(f'{name}.{key}: type must be one of {sorted(SCHEMA_TYPES)}')
    return errors


def skill_contract(*, contract=None, legacy_names=None, **extra):
    """Validate one capability contract and reject references to legacy engines.

    contract = {id, inputs, outputs, effect: read|write, dependencies: [..],
    version: 'MAJOR.MINOR.PATCH', entry_point (optional 'module.symbol')}.
    Returns accepted plus every reason it was rejected (structure, legacy refs).
    """
    _no_extra(extra)
    names = _legacy_names(legacy_names)
    if contract is None:
        contract = _EXAMPLE_CONTRACT
    _dict(contract, 'contract', 20)
    _jsonable(contract, 'contract')
    reasons, legacy = [], []
    allowed = {'id', 'inputs', 'outputs', 'effect', 'dependencies', 'version',
               'entry_point', 'description'}
    for key in sorted(set(contract) - allowed):
        reasons.append(f'unknown contract field {key!r}')
    for key in ('id', 'inputs', 'outputs', 'effect', 'dependencies', 'version'):
        if key not in contract:
            reasons.append(f'missing field {key!r}')
    cid = contract.get('id')
    if 'id' in contract and not (isinstance(cid, str) and len(cid) <= 64 and _ID_RE.match(cid)):
        reasons.append('id must be lowercase dotted identifiers, e.g. video.verify (<= 64 chars)')
    if 'inputs' in contract:
        reasons += _schema_errors(contract['inputs'], 'inputs')
    if 'outputs' in contract:
        reasons += _schema_errors(contract['outputs'], 'outputs')
        if isinstance(contract['outputs'], dict) and not contract['outputs']:
            reasons.append('outputs must declare at least one field')
    if 'effect' in contract and contract['effect'] not in ('read', 'write'):
        reasons.append("effect must be 'read' or 'write'")
    if 'version' in contract and not (isinstance(contract['version'], str)
                                      and _SEMVER_RE.match(contract['version'])):
        reasons.append('version must be semantic MAJOR.MINOR.PATCH')
    deps = contract.get('dependencies')
    if 'dependencies' in contract:
        if not isinstance(deps, list) or len(deps) > 50:
            reasons.append('dependencies must be a list of at most 50 names')
            deps = []
        seen = set()
        for i, dep in enumerate(deps):
            if not isinstance(dep, str) or len(dep) > 64 or not _DEP_RE.match(dep):
                reasons.append(f'dependencies[{i}] is not a valid dependency name')
                continue
            if dep.casefold() in seen:
                reasons.append(f'dependency {dep!r} listed twice')
            seen.add(dep.casefold())
            for hit in _legacy_hits(dep, names):
                legacy.append({'field': f'dependencies[{i}]', 'value': dep, 'legacy_name': hit})
    entry = contract.get('entry_point')
    if 'entry_point' in contract:
        if not isinstance(entry, str) or len(entry) > 200 or not entry.strip():
            reasons.append('entry_point must be a non-empty string (<= 200 chars)')
        else:
            for hit in _legacy_hits(entry, names):
                legacy.append({'field': 'entry_point', 'value': entry, 'legacy_name': hit})
    for item in legacy:
        reasons.append(f"{item['field']} references legacy engine name {item['legacy_name']!r}")
    result = {'id': cid if isinstance(cid, str) else None, 'accepted': not reasons,
              'reasons': reasons, 'legacy_references': legacy,
              'effect': contract.get('effect'),
              'needs_write_approval': contract.get('effect') == 'write',
              'legacy_names_checked': names}
    return _pack('skill_contract', result,
                 ['legacy detection is a case-insensitive substring match whose start must not '
                  'follow a letter or digit (so "black_dragon" and "Dragon.x" match, "standard.py" '
                  'does not match "rd.py"); unrelated words such as "dragonfly" are also flagged',
                  'only dependencies and entry_point are scanned for legacy names, not description',
                  'schema types are a small JSON-like vocabulary; nested schemas are not validated'],
                 ['contract <= 20 fields, inputs/outputs <= 100 fields each, <= 50 dependencies',
                  'the contract is checked as data; the entry point is never imported or called'])


# --------------------------------------------------------------------------- 01.02 provenance_card

_CARD_FIELDS = ('idea', 'source', 'url_or_path', 'date', 'licence', 'author')
_EXAMPLE_CARD = {'idea': 'semi-implicit Euler integration for falling bodies',
                 'source': 'textbook numerical methods (public knowledge)',
                 'url_or_path': 'https://example.org/numerical-methods',
                 'date': '2026-11-21', 'licence': 'CC-BY-4.0', 'author': 'Red Rose maintainers'}


def _licence_set(allowed_licences):
    if allowed_licences is None:
        return set(SPDX_LICENCES)
    extra = _list(allowed_licences, 'allowed_licences', 50)
    out = set(SPDX_LICENCES)
    for i, lic in enumerate(extra):
        lic = _str(lic, f'allowed_licences[{i}]', max_len=64)
        if not re.fullmatch(r'LicenseRef-[A-Za-z0-9.\-]+|[A-Za-z0-9.+\-]+', lic):
            raise ValueError(f'allowed_licences[{i}] is not an SPDX-like identifier')
        out.add(lic)
    return out


def _licence_notes(lic):
    notes = []
    if lic in COPYLEFT:
        notes.append('copyleft: reuse of code may oblige releasing derived code under the same licence')
    if lic in NON_COMMERCIAL:
        notes.append('non-commercial only')
    if lic in NO_DERIVATIVES:
        notes.append('no derivatives allowed')
    return notes


def _verify_card(card, licences):
    reasons = []
    if not isinstance(card, dict):
        return {'valid': False, 'reasons': ['card must be an object'], 'recomputed_sha256': None}
    fields = {k: card.get(k) for k in _CARD_FIELDS}
    for key in sorted(set(card) - set(_CARD_FIELDS) - {'sha256'}):
        reasons.append(f'unexpected field {key!r} (not covered by the hash)')
    for key in _CARD_FIELDS:
        value = card.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 2000:
            reasons.append(f'field {key!r} missing or not a non-empty string')
    recomputed = None
    if not reasons:
        recomputed = hashlib.sha256(_canonical(fields).encode('utf-8')).hexdigest()
        if card.get('sha256') != recomputed:
            reasons.append('sha256 does not match the canonical JSON of the card (tampered or re-typed)')
        if card['licence'] not in licences:
            reasons.append(f"unknown licence {card['licence']!r} (not an accepted SPDX id)")
        if not _iso_date(card['date'][:10], 'date') or len(card['date']) != 10:
            reasons.append('date must be a real calendar date YYYY-MM-DD')
    return {'valid': not reasons, 'reasons': reasons, 'recomputed_sha256': recomputed}


def provenance_card(*, action='build', idea=None, source=None, url_or_path=None, date=None,
                    licence=None, author=None, card=None, allowed_licences=None, **extra):
    """Build or verify a provenance card hashed over its canonical JSON.

    action 'build': fields -> card + sha256 (all six fields given, or none for the
    built-in example). action 'verify': card -> valid/reasons (recomputes the hash,
    rejects tampering, unknown licence, bad date, missing or extra fields).
    """
    _no_extra(extra)
    _choice(action, {'build', 'verify'}, 'action')
    licences = _licence_set(allowed_licences)
    values = {'idea': idea, 'source': source, 'url_or_path': url_or_path, 'date': date,
              'licence': licence, 'author': author}
    if action == 'verify':
        if card is None:
            raise ValueError('verify needs card')
        if any(v is not None for v in values.values()):
            raise ValueError('verify takes card only, not individual fields')
        _jsonable(card, 'card')
        if isinstance(card, dict) and len(card) > 20:
            raise ValueError('card may have at most 20 fields')
        check = _verify_card(card, licences)
        lic = card.get('licence') if isinstance(card, dict) else None
        result = {'action': 'verify', **check,
                  'licence_notes': _licence_notes(lic) if isinstance(lic, str) else []}
    else:
        if card is not None:
            raise ValueError('build takes fields, not card')
        if all(v is None for v in values.values()):
            values = dict(_EXAMPLE_CARD)
        missing = [k for k, v in values.items() if v is None]
        if missing:
            raise ValueError('build needs all fields; missing: ' + ', '.join(missing))
        for k, v in values.items():
            _str(v, k, max_len=2000)
        if values['licence'] not in licences:
            raise ValueError(f"unknown licence {values['licence']!r}; use an SPDX id "
                             'or add it via allowed_licences')
        if not _iso_date(values['date'], 'date'):
            raise ValueError('date must be a real calendar date YYYY-MM-DD')
        built = dict(values)
        built['sha256'] = hashlib.sha256(_canonical(values).encode('utf-8')).hexdigest()
        result = {'action': 'build', 'card': built, 'canonical_json': _canonical(values),
                  'verification': _verify_card(built, licences),
                  'licence_notes': _licence_notes(values['licence'])}
    return _pack('provenance_card', result,
                 ['canonical JSON = sorted keys, UTF-8, no extra whitespace, over the six card '
                  'fields only; sha256 is an integrity checksum, not a cryptographic signature',
                  'anyone who edits a field can recompute the hash; it detects accidental or '
                  'naive tampering, not a deliberate forgery',
                  'licence must be an SPDX id from a built-in list (plus allowed_licences); '
                  'the licence is as declared by the caller and is not checked against the source'],
                 ['each field <= 2000 characters, <= 50 extra allowed licences',
                  'no network: the url_or_path is recorded, never fetched'])


# --------------------------------------------------------------------------- 01.03 behaviour_compare

_EXAMPLE_CASES = [
    {'input': [3, 4], 'expected': 5.0, 'observed': 5.0000001, 'tolerance': 1e-6},
    {'input': [0, 0], 'expected': 0.0, 'observed': 0.0},
    {'input': {'xs': [1, 2]}, 'expected': [1, 4], 'observed': [1, 4]},
]
_EXAMPLE_REFERENCE = 'def hyp(a, b):\n    return (a * a + b * b) ** 0.5\n'
_EXAMPLE_NEW = ('import math\n\n\ndef hypotenuse(legs):\n    """Euclidean norm of two legs."""\n'
                '    first, second = legs\n    return math.hypot(first, second)\n')


def _compare(expected, observed, tol, path='$', depth=0):
    """Return None when observed matches expected within tol, else a mismatch reason."""
    if depth > MAX_DEPTH:
        return f'{path}: nesting deeper than {MAX_DEPTH}'
    num = (int, float)
    if (isinstance(expected, num) and not isinstance(expected, bool)
            and isinstance(observed, num) and not isinstance(observed, bool)):
        diff = abs(expected - observed)
        return None if diff <= tol else f'{path}: |{expected} - {observed}| = {diff:.6g} > {tol:g}'
    if type(expected) is not type(observed) and not (
            isinstance(expected, (list, tuple)) and isinstance(observed, (list, tuple))):
        return f'{path}: type {type(expected).__name__} != {type(observed).__name__}'
    if isinstance(expected, (list, tuple)):
        if len(expected) != len(observed):
            return f'{path}: length {len(expected)} != {len(observed)}'
        for i, (e, o) in enumerate(zip(expected, observed)):
            r = _compare(e, o, tol, f'{path}[{i}]', depth + 1)
            if r:
                return r
        return None
    if isinstance(expected, dict):
        if set(expected) != set(observed):
            return f'{path}: keys {sorted(expected)} != {sorted(observed)}'
        for k in sorted(expected):
            r = _compare(expected[k], observed[k], tol, f'{path}.{k}', depth + 1)
            if r:
                return r
        return None
    return None if expected == observed else f'{path}: {expected!r} != {observed!r}'


def _norm_lines(text):
    return [' '.join(line.split()) for line in text.splitlines() if line.strip()]


def _similarity(new_code, reference_code):
    a_lines, b_lines = _norm_lines(new_code), _norm_lines(reference_code)
    if max(len(a_lines), len(b_lines)) > 5000:
        raise ValueError('code texts must have at most 5000 non-blank lines')
    line_ratio = difflib.SequenceMatcher(None, a_lines, b_lines, autojunk=False).ratio()
    tok = re.compile(r'\w+|[^\w\s]')
    a_tok, b_tok = tok.findall(new_code), tok.findall(reference_code)
    if max(len(a_tok), len(b_tok)) > 30000:
        raise ValueError('code texts must have at most 30000 tokens')
    token_ratio = difflib.SequenceMatcher(None, a_tok, b_tok).ratio()
    return round(line_ratio, 4), round(token_ratio, 4)


def behaviour_compare(*, cases=None, new_code=None, reference_code=None, threshold=0.8,
                      **extra):
    """Compare expected vs observed outputs and guard against copied code text.

    cases: [{input, expected, observed, tolerance?}] from licensed examples.
    new_code / reference_code (both or neither): difflib similarity of
    whitespace-normalised lines and of tokens; >= threshold flags copy risk
    even when every behaviour case passes.
    """
    _no_extra(extra)
    threshold = _num(threshold, 0.0, 1.0, 'threshold')
    if cases is None and new_code is None and reference_code is None:
        cases, new_code, reference_code = _EXAMPLE_CASES, _EXAMPLE_NEW, _EXAMPLE_REFERENCE
    if (new_code is None) != (reference_code is None):
        raise ValueError('give both new_code and reference_code, or neither')
    if cases is None and new_code is None:
        raise ValueError('need cases and/or new_code + reference_code')
    report, passed = [], 0
    if cases is not None:
        cases = _list(cases, 'cases', MAX_ITEMS, 1)
        for i, case in enumerate(cases):
            _dict(case, f'cases[{i}]', 4)
            if set(case) - {'input', 'expected', 'observed', 'tolerance'}:
                raise ValueError(f'cases[{i}] has unknown keys')
            if 'expected' not in case or 'observed' not in case:
                raise ValueError(f'cases[{i}] needs expected and observed')
            _jsonable(case, f'cases[{i}]')
            tol = _num(case.get('tolerance', 0.0), 0.0, 1e12, f'cases[{i}].tolerance')
            reason = _compare(case['expected'], case['observed'], tol)
            passed += reason is None
            report.append({'index': i, 'input': case.get('input'),
                           'passed': reason is None, 'reason': reason})
    similarity = None
    copy_risk = False
    if new_code is not None:
        _str(new_code, 'new_code', max_len=MAX_TEXT)
        _str(reference_code, 'reference_code', max_len=MAX_TEXT)
        line_ratio, token_ratio = _similarity(new_code, reference_code)
        score = max(line_ratio, token_ratio)
        copy_risk = score >= threshold
        similarity = {'line_ratio': line_ratio, 'token_ratio': token_ratio,
                      'score': score, 'threshold': threshold, 'copy_risk': copy_risk}
    behaviour_ok = None if cases is None else passed == len(report)
    if copy_risk:
        verdict = 'rejected_copy_risk'
    elif behaviour_ok is False:
        verdict = 'rejected_behaviour_mismatch'
    else:
        verdict = 'accepted'
    result = {'cases': report, 'passed': passed, 'failed': len(report) - passed,
              'behaviour_ok': behaviour_ok, 'similarity': similarity, 'verdict': verdict}
    return _pack('behaviour_compare', result,
                 ['observed outputs are supplied by the caller; this op does not run any code',
                  'numbers match within the per-case absolute tolerance; bools never equal numbers; '
                  'lists/tuples compare element-wise and dicts key-wise',
                  'copy guard = max(difflib ratio of whitespace-normalised non-blank lines, '
                  'difflib ratio of word/punctuation tokens); renaming identifiers and reordering '
                  'can lower it, so a low score does not prove independent authorship'],
                 ['<= 500 cases, nesting <= 32, each code text <= 100000 characters, '
                  '<= 5000 non-blank lines and <= 30000 tokens'])


# --------------------------------------------------------------------------- 01.04 capability_overlap

_AR_MAP = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ئ': 'ي',
                         'ؤ': 'و', 'ة': 'ه', **{chr(0x0660 + d): str(d) for d in range(10)},
                         **{chr(0x06F0 + d): str(d) for d in range(10)}})
_EXAMPLE_CAPS = [
    {'id': 'video.verify', 'effect': 'read', 'inputs': {'path': 'string'}, 'outputs': {'ok': 'boolean'}},
    {'id': 'Video-Verify', 'effect': 'read', 'inputs': {'path': 'string'}, 'outputs': {'ok': 'boolean'}},
    {'id': 'media.export', 'effect': 'write', 'inputs': {'path': 'string'}, 'outputs': {'out': 'string'}},
    {'id': 'MEDIA_EXPORT', 'effect': 'read', 'inputs': {'path': 'string'}, 'outputs': {'out': 'string'}},
    {'id': 'تحقق_الفيديو', 'effect': 'read', 'inputs': {'clip': 'string'}, 'outputs': {'report': 'object'}},
    {'id': 'تَحقّق.الفيدیو', 'effect': 'read', 'inputs': {'clip': 'string'}, 'outputs': {'report': 'object'}},
]


def normalise_name(name):
    """Casefold, NFKC, strip Arabic diacritics/tatweel, unify letter variants and separators."""
    s = unicodedata.normalize('NFKC', name).casefold()
    s = ''.join(ch for ch in s if not ('ً' <= ch <= 'ٟ' or ch in 'ٰـ'))
    s = s.translate(_AR_MAP).replace('ی', 'ي').replace('ک', 'ك')
    return re.sub(r'[\s._\-/:\\]+', '.', s).strip('.')


def capability_overlap(*, capabilities=None, **extra):
    """Find merge candidates and conflicts among capability contracts.

    Names are grouped by normalise_name with separators removed. Within a
    group: different effects -> conflict 'effect_mismatch'; same effect but
    different inputs/outputs -> conflict 'signature_mismatch'; otherwise a
    'same_name' merge candidate. Different names with an identical non-empty
    contract (effect, inputs, outputs) -> 'same_contract' merge candidate.
    """
    _no_extra(extra)
    if capabilities is None:
        capabilities = _EXAMPLE_CAPS
    caps = _list(capabilities, 'capabilities', MAX_ITEMS, 1)
    groups, by_sig, normalised = {}, {}, []
    for i, cap in enumerate(caps):
        _dict(cap, f'capabilities[{i}]', 20)
        _jsonable(cap, f'capabilities[{i}]')
        cid = cap.get('id', cap.get('name'))
        _str(cid, f'capabilities[{i}].id', max_len=128)
        effect = _choice(cap.get('effect'), {'read', 'write'}, f'capabilities[{i}].effect')
        inputs = _dict(cap.get('inputs', {}), f'capabilities[{i}].inputs', 100)
        outputs = _dict(cap.get('outputs', {}), f'capabilities[{i}].outputs', 100)
        norm = normalise_name(cid)
        if not norm:
            raise ValueError(f'capabilities[{i}].id has no letters or digits')
        sig = _canonical([inputs, outputs])
        normalised.append({'id': cid, 'normalised': norm})
        groups.setdefault(norm.replace('.', ''), []).append((cid, norm, effect, sig))
        if inputs or outputs:
            by_sig.setdefault(_canonical([effect, inputs, outputs]), []).append((cid, norm))
    merge, conflicts = [], []
    for key in sorted(groups):
        members = groups[key]
        if len(members) < 2:
            continue
        ids = [m[0] for m in members]
        effects = sorted({m[2] for m in members})
        if len(effects) > 1:
            conflicts.append({'kind': 'effect_mismatch', 'normalised': members[0][1], 'ids': ids,
                              'effects': {m[0]: m[2] for m in members}})
        elif len({m[3] for m in members}) > 1:
            conflicts.append({'kind': 'signature_mismatch', 'normalised': members[0][1],
                              'ids': ids, 'effects': {m[0]: m[2] for m in members}})
        else:
            merge.append({'kind': 'same_name', 'normalised': members[0][1], 'ids': ids})
    for key in sorted(by_sig):
        members = by_sig[key]
        names = {m[1].replace('.', '') for m in members}
        if len(names) > 1:
            merge.append({'kind': 'same_contract', 'ids': [m[0] for m in members],
                          'normalised': sorted({m[1] for m in members})})
    result = {'count': len(caps), 'normalised': normalised, 'merge_candidates': merge,
              'conflicts': conflicts}
    return _pack('capability_overlap', result,
                 ['names compared after NFKC + casefold, removal of Arabic diacritics and tatweel, '
                  'alef/yeh/teh-marbuta/hamza-seat unification, Arabic-Indic digits to ASCII, and '
                  'removal of separators (space . _ - / : \\)',
                  'separator removal can merge distinct names such as a.bc and ab.c; results are '
                  'candidates for a human decision, not automatic merges',
                  'contracts are equal only when inputs and outputs are identical JSON; synonyms '
                  'and translations (e.g. Arabic vs English names) are not detected'],
                 ['<= 500 capabilities, each <= 20 fields and <= 100 input/output fields'])


# --------------------------------------------------------------------------- 01.05 legacy_import_audit

_IMPORT_CALLS = frozenset({'import_module', '__import__', 'find_spec', 'spec_from_file_location',
                           'run_module', 'run_path', 'load_source', 'SourceFileLoader',
                           'module_from_spec'})
_SHELL_CALLS = frozenset({'run', 'Popen', 'call', 'check_call', 'check_output', 'system',
                          'popen', 'startfile', 'getoutput', 'getstatusoutput', 'spawnl',
                          'spawnlp', 'spawnv', 'spawnvp', 'execl', 'execlp', 'execv', 'execvp',
                          'execve', 'create_subprocess_exec', 'create_subprocess_shell',
                          'ShellExecute', 'ShellExecuteW'})
_EXAMPLE_FILES = {
    'bad_engine.py': 'import black_dragon\nimport importlib\n'
                     "eng = importlib.import_module('golden_dragon.x')\n"
                     "import subprocess\nsubprocess.run(['python', 'rd.py', 'plan'])\n",
    'clean.py': 'import json\nimport math\n\n\ndef area(r):\n    return math.pi * r * r\n',
}


def _call_name(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _string_constants(node, limit=200):
    out = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append(sub.value)
            if len(out) >= limit:
                break
    return out


def _audit_source(fname, source, names):
    findings, warnings = [], []
    try:
        tree = ast.parse(source, filename=fname)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        return None, [], [f'{fname}: not parseable as Python ({type(exc).__name__}); not audited']

    def add(node, kind, target):
        for hit in _legacy_hits(target, names):
            findings.append({'file': fname, 'line': getattr(node, 'lineno', 0), 'kind': kind,
                             'target': target[:200], 'legacy_name': hit})

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                add(node, 'import', alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            add(node, 'from_import', '.' * node.level + base)
            for alias in node.names:
                if alias.name != '*':
                    add(node, 'from_import_name', (base + '.' if base else '') + alias.name)
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in _IMPORT_CALLS:
                args = list(node.args) + [k.value for k in node.keywords]
                consts = [s for a in args for s in _string_constants(a)]
                if node.args and not (isinstance(node.args[0], ast.Constant)
                                      and isinstance(node.args[0].value, str)):
                    warnings.append(f'{fname}:{node.lineno}: dynamic {name}() target cannot be '
                                    'resolved statically')
                for s in consts:
                    add(node, 'dynamic_import', s)
            elif name in _SHELL_CALLS:
                for s in _string_constants(node):
                    add(node, 'command_string', s)
    return findings, len(findings) == 0, warnings


def legacy_import_audit(*, files=None, legacy_names=None, **extra):
    """AST-scan {filename: python source} for imports/commands that reach legacy engines.

    Flags `import x` / `from x import y`, string targets of import_module,
    __import__, find_spec, spec_from_file_location, run_module/run_path, and
    string constants passed to subprocess/os.system-like calls.
    """
    _no_extra(extra)
    names = _legacy_names(legacy_names)
    if files is None:
        files = _EXAMPLE_FILES
    _dict(files, 'files', MAX_AUDIT_FILES)
    if not files:
        raise ValueError('files must contain at least one {filename: source} entry')
    total = 0
    for fname, src in files.items():
        _str(fname, 'filename', max_len=260)
        _str(src, f'files[{fname!r}]', max_len=MAX_AUDIT_CHARS, allow_empty=True)
        total += len(src)
    if total > MAX_AUDIT_CHARS:
        raise ValueError(f'total source size must be <= {MAX_AUDIT_CHARS} characters')
    findings, clean, flagged, unparsed, warnings = [], [], [], [], []
    for fname in sorted(files):
        got, ok, warn = _audit_source(fname, files[fname], names)
        warnings += warn
        if got is None:
            unparsed.append(fname)
            continue
        findings += got
        (clean if ok else flagged).append(fname)
    result = {'passed': not findings and not unparsed, 'findings': findings,
              'flagged_files': flagged, 'clean_files': clean, 'unparsed_files': unparsed,
              'warnings': warnings, 'legacy_names_checked': names}
    return _pack('legacy_import_audit', result,
                 ['static AST scan only; the sources are parsed, never executed',
                  'only string literals are resolved: computed module names, f-strings, '
                  'string concatenation, getattr tricks and data files are not followed '
                  '(non-literal import targets are reported as warnings)',
                  'shell-like calls are recognised by function name (run, Popen, system, ...); '
                  'any legacy name inside their string arguments is flagged',
                  'legacy match: case-insensitive substring whose start does not follow a letter '
                  'or digit; paths containing such words (e.g. a parent folder named alloy) are '
                  'flagged too, pass legacy_names to narrow'],
                 [f'<= {MAX_AUDIT_FILES} files, <= {MAX_AUDIT_CHARS} characters in total',
                  'unparseable files are reported and make passed false'])


# --------------------------------------------------------------------------- 01.06 adapter_reality

_EXAMPLE_REGISTRY = {
    'qa.trace': ['Find attributed decisions', 'read', 'builtin'],
    'fusion.render': ['Render an illustrated MP4', 'write', 'pillow_cairosvg'],
    'media.colour_grade': ['Grade footage with a LUT', 'write', 'ffmpeg'],
}
_EXAMPLE_EVIDENCE = {
    'qa.trace': {'handler_present': True, 'sample_output': {'matches': 1},
                 'test_file': 'test_qa_trace.py'},
    'fusion.render': {'handler_present': True, 'sample_output': None, 'test_file': None},
    'media.colour_grade': {'handler_present': False, 'sample_output': None, 'test_file': None},
}


def _registry_entry(ident, entry):
    if isinstance(entry, str):
        return {'description': entry, 'effect': None, 'dependency': None}
    if isinstance(entry, (list, tuple)) and len(entry) == 3 and all(isinstance(x, str) for x in entry):
        return {'description': entry[0], 'effect': entry[1], 'dependency': entry[2]}
    if isinstance(entry, dict):
        return {'description': entry.get('description'), 'effect': entry.get('effect'),
                'dependency': entry.get('dependency')}
    raise ValueError(f'registry[{ident!r}] must be [description, effect, dependency], '
                     'a description string or a dict')


def _evidence_entry(ident, ev):
    if ev is None:
        return False, None, None
    _dict(ev, f'evidence[{ident!r}]', 3)
    if set(ev) - {'handler_present', 'sample_output', 'test_file'}:
        raise ValueError(f'evidence[{ident!r}] has unknown keys')
    handler = ev.get('handler_present', False)
    if not isinstance(handler, bool):
        raise ValueError(f'evidence[{ident!r}].handler_present must be true or false')
    test = ev.get('test_file')
    if test is not None:
        _str(test, f'evidence[{ident!r}].test_file', max_len=260)
    _jsonable(ev.get('sample_output'), f'evidence[{ident!r}].sample_output')
    return handler, ev.get('sample_output'), test


def adapter_reality(*, registry=None, evidence=None, **extra):
    """Classify registry adapters as executable_with_evidence / executable_no_evidence /
    description_only from a per-id evidence map.

    with_evidence needs handler_present and a non-null sample_output and a test_file.
    An id without a handler is description_only however well it is documented.
    """
    _no_extra(extra)
    if registry is None and evidence is None:
        registry, evidence = _EXAMPLE_REGISTRY, _EXAMPLE_EVIDENCE
    if registry is None or evidence is None:
        raise ValueError('need both registry and evidence')
    _dict(registry, 'registry', 2000)
    _dict(evidence, 'evidence', 2000)
    rows, counts = [], {'executable_with_evidence': 0, 'executable_no_evidence': 0,
                        'description_only': 0}
    for ident in sorted(registry):
        _str(ident, 'registry id', max_len=128)
        meta = _registry_entry(ident, registry[ident])
        handler, sample, test = _evidence_entry(ident, evidence.get(ident))
        missing = []
        if not handler:
            cls = 'description_only'
            missing.append('handler')
        else:
            if sample is None:
                missing.append('sample_output')
            if not test:
                missing.append('test_file')
            cls = 'executable_no_evidence' if missing else 'executable_with_evidence'
        counts[cls] += 1
        rows.append({'id': ident, 'class': cls, 'missing': missing, 'effect': meta['effect'],
                     'dependency': meta['dependency'],
                     'documented': bool(isinstance(meta['description'], str)
                                        and meta['description'].strip())})
    unregistered = sorted(set(evidence) - set(registry))
    total = len(rows)
    result = {'adapters': rows, 'counts': counts, 'unregistered_evidence': unregistered,
              'executable_with_evidence_pct': round(100.0 * counts['executable_with_evidence']
                                                    / total, 2) if total else 0.0}
    return _pack('adapter_reality', result,
                 ['handler_present, sample_output and test_file are claims supplied by the caller; '
                  'this op does not import handlers, run them or read test files',
                  'an id missing from evidence is treated as having no handler',
                  'documentation (a description) never upgrades the class'],
                 ['<= 2000 registry ids and evidence entries'])


# --------------------------------------------------------------------------- 01.07 capability_passport

_EXAMPLE_PASSPORT_CAPS = [
    {'id': 'qa.trace', 'effect': 'read', 'inputs': {'question_id': 'string'},
     'dependencies': ['builtin'], 'handler_present': True, 'limits': ['read-only lookup']},
    {'id': 'media.iphone_export', 'effect': 'write', 'inputs': {'path': 'string'},
     'dependencies': ['ffmpeg'], 'handler_present': True,
     'limits': ['authorized local video only']},
    {'id': 'media.colour_grade', 'effect': 'write', 'inputs': {'path': 'string'},
     'dependencies': ['ffmpeg'], 'handler_present': False, 'limits': []},
]
_EXAMPLE_AVAILABLE = {'ffmpeg': False}


def capability_passport(*, capabilities=None, available=None, **extra):
    """Passport per capability: permissions, inputs, dependencies, ready flag, limits, status.

    status 'executable' only with a handler and every dependency available;
    'description_only' without a handler; otherwise 'blocked' naming the
    missing dependencies. 'builtin' counts as available unless overridden.
    """
    _no_extra(extra)
    if capabilities is None and available is None:
        capabilities, available = _EXAMPLE_PASSPORT_CAPS, _EXAMPLE_AVAILABLE
    if capabilities is None:
        raise ValueError('need capabilities')
    caps = _list(capabilities, 'capabilities', MAX_ITEMS, 1)
    avail = {'builtin': True}
    for k, v in _dict(available or {}, 'available', 500).items():
        if not isinstance(v, bool):
            raise ValueError(f'available[{k!r}] must be true or false')
        avail[k] = v
    passports, counts = [], {'executable': 0, 'blocked': 0, 'description_only': 0}
    allowed = {'id', 'effect', 'inputs', 'outputs', 'dependencies', 'handler_present', 'limits',
               'description', 'version'}
    for i, cap in enumerate(caps):
        _dict(cap, f'capabilities[{i}]', 20)
        if set(cap) - allowed:
            raise ValueError(f'capabilities[{i}] has unknown keys: {sorted(set(cap) - allowed)}')
        _jsonable(cap, f'capabilities[{i}]')
        cid = _str(cap.get('id'), f'capabilities[{i}].id', max_len=128)
        effect = _choice(cap.get('effect'), {'read', 'write'}, f'capabilities[{i}].effect')
        inputs = _dict(cap.get('inputs', {}), f'capabilities[{i}].inputs', 100)
        deps = cap.get('dependencies', [])
        if isinstance(deps, str):
            deps = [deps]
        deps = [_str(d, f'capabilities[{i}].dependencies', max_len=64)
                for d in _list(deps, f'capabilities[{i}].dependencies', 50)]
        handler = cap.get('handler_present', False)
        if not isinstance(handler, bool):
            raise ValueError(f'capabilities[{i}].handler_present must be true or false')
        limits = [_str(x, f'capabilities[{i}].limits', max_len=300)
                  for x in _list(cap.get('limits', []), f'capabilities[{i}].limits', 50)]
        dep_state = {d: avail.get(d) for d in deps}
        missing = [d for d in deps if dep_state[d] is not True]
        unknown = [d for d in deps if dep_state[d] is None]
        ready = not missing
        if not handler:
            status, reason = 'description_only', 'no executable handler registered'
        elif missing:
            status = 'blocked'
            reason = 'missing dependencies: ' + ', '.join(missing)
            if unknown:
                reason += ' (availability unknown for: ' + ', '.join(unknown) + ')'
        else:
            status, reason = 'executable', None
        counts[status] += 1
        passports.append({
            'id': cid, 'status': status, 'reason': reason,
            'permissions': {'effect': effect, 'reads': True, 'writes': effect == 'write',
                            'needs_explicit_approval': effect == 'write'},
            'inputs': sorted(inputs), 'dependencies': dep_state, 'missing_dependencies': missing,
            'dependencies_ready': ready, 'handler_present': handler, 'limits': limits})
    result = {'passports': passports, 'counts': counts}
    return _pack('capability_passport', result,
                 ['dependency availability comes from the supplied map; it is not probed here',
                  'a dependency absent from the map counts as unavailable (unknown)',
                  "'builtin' is available unless the map overrides it",
                  'write effect always needs explicit owner approval before execution'],
                 ['<= 500 capabilities, <= 50 dependencies and <= 50 limit notes each'])


# --------------------------------------------------------------------------- 01.08 approval_lifecycle

_EVIDENCE_KEYS = {
    'approved': ('owner_quote', 'date'),
    'coded': ('file', 'symbol'),
    'unit_tested': ('test_file', 'passing'),
    'e2e_verified': ('artifact_sha256',),
}
_EXAMPLE_STEPS = [
    {'to': 'approved', 'evidence': {'owner_quote': 'نعم، اعتمد عقد المهارة', 'date': '2026-11-20'}},
    {'to': 'coded', 'evidence': {'file': 'governance_v22.py', 'symbol': 'skill_contract'}},
    {'to': 'unit_tested', 'evidence': {'test_file': 'test_governance_v22.py', 'passing': 3}},
    {'to': 'e2e_verified', 'evidence': {}},
]


def _evidence_problem(level, ev):
    if not isinstance(ev, dict) or not ev:
        return f'{level} needs evidence {list(_EVIDENCE_KEYS[level])}'
    allowed = set(_EVIDENCE_KEYS[level]) | {'note', 'failing'} if level == 'unit_tested' \
        else set(_EVIDENCE_KEYS[level]) | {'note'}
    unknown = sorted(set(ev) - allowed)
    if unknown:
        return f'{level}: unexpected evidence keys {unknown}'
    missing = [k for k in _EVIDENCE_KEYS[level] if k not in ev]
    if missing:
        return f'{level}: missing evidence {missing}'
    if 'note' in ev and (not isinstance(ev['note'], str) or len(ev['note']) > 500):
        return 'note must be a string <= 500 characters'

    def text(key, min_len=1, max_len=500):
        v = ev[key]
        return isinstance(v, str) and min_len <= len(v.strip()) and len(v) <= max_len

    if level == 'approved':
        if not text('owner_quote', 3, 2000):
            return 'approved: owner_quote must be the owner\'s words (3..2000 characters)'
        if not isinstance(ev['date'], str) or not _iso_date(ev['date'][:10], 'date') \
                or len(ev['date']) != 10:
            return 'approved: date must be a real calendar date YYYY-MM-DD'
    elif level == 'coded':
        if not text('file', 1, 260):
            return 'coded: file must be a non-empty path'
        if not isinstance(ev['symbol'], str) or not _SYMBOL_RE.match(ev['symbol']):
            return 'coded: symbol must be a Python identifier (dotted allowed)'
    elif level == 'unit_tested':
        if not text('test_file', 1, 260):
            return 'unit_tested: test_file must be a non-empty path'
        p = ev['passing']
        if isinstance(p, bool) or not isinstance(p, int) or not 1 <= p <= 1_000_000:
            return 'unit_tested: passing must be an integer >= 1'
        f = ev.get('failing', 0)
        if isinstance(f, bool) or not isinstance(f, int) or f != 0:
            return 'unit_tested: failing must be 0'
    elif level == 'e2e_verified':
        v = ev['artifact_sha256']
        if not isinstance(v, str) or not _HEX64_RE.match(v.lower()):
            return 'e2e_verified: artifact_sha256 must be 64 hex characters'
    return None


def approval_lifecycle(*, item=None, steps=None, **extra):
    """Apply promotions proposed -> approved -> coded -> unit_tested -> e2e_verified.

    item = {id, status, history?}; steps = [{to, evidence}]. Each step must go
    exactly one level up with evidence of the right kind; the first rejected
    step stops processing (later steps are reported as not_attempted).
    """
    _no_extra(extra)
    if item is None and steps is None:
        item, steps = {'id': 'governance.skill_contract', 'status': 'proposed'}, _EXAMPLE_STEPS
    if steps is None:
        raise ValueError('need steps')
    if item is None:
        raise ValueError('need item')
    _dict(item, 'item', 3)
    if set(item) - {'id', 'status', 'history'}:
        raise ValueError('item keys must be id, status, history')
    iid = _str(item.get('id'), 'item.id', max_len=128)
    status = _choice(item.get('status', 'proposed'), set(LEVELS), 'item.status')
    history = _list(item.get('history', []), 'item.history', 100)
    _jsonable(history, 'item.history')
    steps = _list(steps, 'steps', 20, 1)
    log, stopped = [], False
    history = list(history)
    for i, step in enumerate(steps):
        _dict(step, f'steps[{i}]', 2)
        if stopped:
            log.append({'index': i, 'to': step.get('to'), 'outcome': 'not_attempted'})
            continue
        target = step.get('to')
        if target not in LEVELS:
            raise ValueError(f'steps[{i}].to must be one of {list(LEVELS)}')
        _jsonable(step.get('evidence'), f'steps[{i}].evidence')
        cur, nxt = LEVELS.index(status), LEVELS.index(target)
        if nxt <= cur:
            problem = f'cannot move from {status} to {target}: only forward promotion is allowed'
        elif nxt > cur + 1:
            problem = (f'cannot skip from {status} to {target}: next level is '
                       f'{LEVELS[cur + 1]}')
        else:
            problem = _evidence_problem(target, step.get('evidence'))
        if problem:
            stopped = True
            log.append({'index': i, 'from': status, 'to': target, 'outcome': 'rejected',
                        'reason': problem})
        else:
            history.append({'from': status, 'to': target, 'evidence': step['evidence']})
            log.append({'index': i, 'from': status, 'to': target, 'outcome': 'promoted'})
            status = target
    result = {'id': iid, 'final_status': status, 'steps': log,
              'all_promoted': not stopped, 'history': history, 'levels': list(LEVELS)}
    return _pack('approval_lifecycle', result,
                 ['evidence is checked for kind and shape only (quote + date, file + symbol, '
                  'test file + passing count with 0 failing, artifact sha256); its truth is not '
                  'verified: no file is read and no test is run',
                  'only one-level forward promotions; demotion or reopening is not modelled',
                  'the first rejected step stops the sequence so the state never jumps past a gap'],
                 ['<= 20 steps per call, <= 100 history entries, quote <= 2000 characters'])


# --------------------------------------------------------------------------- 01.09 snapshot_restore

_EXAMPLE_TREE = {'SKILL.md': '# Red Rose\nOne independent skill.\n',
                 'rose.py': 'print_ready = True\n', 'notes/ar.txt': 'الوردة الحمراء\n'}


def _check_path(path):
    _str(path, 'path', max_len=260)
    if path.startswith(('/', '\\')) or re.match(r'^[A-Za-z]:', path) or '..' in re.split(r'[\\/]', path):
        raise ValueError(f'path {path!r} must be relative without ..')
    return path


def _snapshot(files):
    _dict(files, 'files', MAX_SNAPSHOT_FILES)
    entries, store, total = {}, {}, 0
    for path in sorted(files):
        _check_path(path)
        text = files[path]
        if not isinstance(text, str):
            raise ValueError(f'files[{path!r}] must be text')
        digest, size = _sha256_text(text)
        total += size
        if total > MAX_SNAPSHOT_BYTES:
            raise ValueError(f'snapshot exceeds {MAX_SNAPSHOT_BYTES} bytes')
        entries[path] = {'sha256': digest, 'bytes': size}
        store[digest] = text
    manifest = {'files': entries,
                'manifest_sha256': hashlib.sha256(_canonical(entries).encode('utf-8')).hexdigest(),
                'file_count': len(entries), 'total_bytes': total}
    return manifest, store


def _check_manifest(manifest, name):
    _dict(manifest, name, 4)
    entries = manifest.get('files')
    _dict(entries, f'{name}.files', MAX_SNAPSHOT_FILES)
    for path, entry in entries.items():
        _check_path(path)
        if not isinstance(entry, dict) or not isinstance(entry.get('sha256'), str) \
                or not _HEX64_RE.match(entry['sha256']):
            raise ValueError(f'{name}.files[{path!r}] needs a sha256')
    want = hashlib.sha256(_canonical(entries).encode('utf-8')).hexdigest()
    if manifest.get('manifest_sha256') != want:
        raise ValueError(f'{name}.manifest_sha256 does not match its file list (tampered)')
    return entries


def _restore(manifest, store):
    entries = _check_manifest(manifest, 'manifest')
    _dict(store, 'store', MAX_SNAPSHOT_FILES)
    out = {}
    for path in sorted(entries):
        digest = entries[path]['sha256']
        if digest not in store:
            raise ValueError(f'store is missing the blob for {path!r}')
        text = store[digest]
        if not isinstance(text, str) or _sha256_text(text)[0] != digest:
            raise ValueError(f'blob for {path!r} is corrupted (hash mismatch)')
        out[path] = text
    return out


def _diff(a, b):
    ea, eb = _check_manifest(a, 'manifest'), _check_manifest(b, 'other')
    added = sorted(set(eb) - set(ea))
    removed = sorted(set(ea) - set(eb))
    common = sorted(set(ea) & set(eb))
    changed = [p for p in common if ea[p]['sha256'] != eb[p]['sha256']]
    return {'added': added, 'removed': removed, 'changed': changed,
            'unchanged_count': len(common) - len(changed),
            'identical': not (added or removed or changed)}


def snapshot_restore(*, action='demo', files=None, manifest=None, store=None, other=None,
                     **extra):
    """Content-addressed snapshots of {path: text}.

    action 'snapshot' (files) -> manifest + store {sha256: text};
    'restore' (manifest, store) -> exact files, after verifying every hash;
    'diff' (manifest, other) -> added/removed/changed paths;
    'demo' -> snapshot, modify, diff, restore on a tiny built-in tree.
    """
    _no_extra(extra)
    _choice(action, {'demo', 'snapshot', 'restore', 'diff'}, 'action')
    given = {'files': files, 'manifest': manifest, 'store': store, 'other': other}
    need = {'demo': (), 'snapshot': ('files',), 'restore': ('manifest', 'store'),
            'diff': ('manifest', 'other')}[action]
    for key, value in given.items():
        if key in need and value is None:
            raise ValueError(f'{action} needs {key}')
        if key not in need and value is not None:
            raise ValueError(f'{action} does not take {key}')
    if action == 'snapshot':
        man, st = _snapshot(files)
        result = {'action': action, 'manifest': man, 'store': st}
    elif action == 'restore':
        restored = _restore(manifest, store)
        result = {'action': action, 'files': restored,
                  'sha256': {p: _sha256_text(t)[0] for p, t in restored.items()}}
    elif action == 'diff':
        result = {'action': action, **_diff(manifest, other)}
    else:
        man, st = _snapshot(_EXAMPLE_TREE)
        edited = dict(_EXAMPLE_TREE)
        edited['rose.py'] = 'print_ready = False\n'
        man2, st2 = _snapshot(edited)
        restored = _restore(man, {**st, **st2})
        result = {'action': action, 'manifest': man, 'modified_manifest': man2,
                  'diff': _diff(man, man2), 'restored_equals_original': restored == _EXAMPLE_TREE}
    return _pack('snapshot_restore', result,
                 ['files are UTF-8 text; hashes are sha256 of the UTF-8 bytes, so binary files and '
                  'newline/encoding conversions are outside this model',
                  'nothing is written to disk: the caller keeps manifest and store and decides '
                  'where (and whether) to persist or restore them; originals are never touched here',
                  'identical contents share one blob (content addressing)'],
                 [f'<= {MAX_SNAPSHOT_FILES} files and <= {MAX_SNAPSHOT_BYTES} bytes per snapshot',
                  'paths must be relative, <= 260 characters, without ..',
                  'restore fails (ValueError) on any missing or corrupted blob rather than '
                  'returning a partial tree'])


# --------------------------------------------------------------------------- 01.10 completion_matrix

_LINKS = ('implementation', 'test', 'evidence')
_EXAMPLE_REQUIREMENTS = [
    {'id': 'R1', 'text': 'reject legacy engine contracts',
     'implementation': 'governance_v22.py::skill_contract',
     'test': 'test_governance_v22.py::test_legacy_contract_rejected',
     'evidence': 'unittest run 2026-11-21: OK'},
    {'id': 'R2', 'text': 'snapshot restore keeps originals',
     'implementation': 'governance_v22.py::snapshot_restore', 'test': None, 'evidence': None},
    {'id': 'R3', 'text': 'capability passport per adapter', 'implementation': None,
     'test': None, 'evidence': None},
]


def _link(value, name):
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    items = _list(value, name, 50)
    return [_str(v, name, max_len=500) for v in items]


def completion_matrix(*, requirements=None, existing_paths=None, **extra):
    """Traceability requirement -> implementation -> test -> evidence.

    A requirement is complete only when all three links are present (and, if
    existing_paths is given, its implementation and test references point at
    listed paths; 'file.py::symbol' is checked by the part before '::').
    """
    _no_extra(extra)
    if requirements is None:
        requirements = _EXAMPLE_REQUIREMENTS
    reqs = _list(requirements, 'requirements', 2000, 1)
    known = None
    if existing_paths is not None:
        known = {_str(p, 'existing_paths', max_len=260)
                 for p in _list(existing_paths, 'existing_paths', 10000)}
    rows, seen, complete = [], set(), 0
    for i, req in enumerate(reqs):
        _dict(req, f'requirements[{i}]', 6)
        if set(req) - {'id', 'text', *_LINKS}:
            raise ValueError(f'requirements[{i}] has unknown keys')
        rid = _str(req.get('id'), f'requirements[{i}].id', max_len=64)
        if rid in seen:
            raise ValueError(f'duplicate requirement id {rid!r}')
        seen.add(rid)
        if req.get('text') is not None:
            _str(req['text'], f'requirements[{i}].text', max_len=2000)
        links = {k: _link(req.get(k), f'requirements[{i}].{k}') for k in _LINKS}
        missing = [k for k in _LINKS if not links[k]]
        dangling = []
        if known is not None:
            for k in ('implementation', 'test'):
                for ref in links[k]:
                    if ref.split('::', 1)[0] not in known:
                        dangling.append({'link': k, 'ref': ref})
        done = not missing and not dangling
        complete += done
        rows.append({'id': rid, 'complete': done, 'missing_links': missing,
                     'first_missing': missing[0] if missing else None,
                     'dangling_refs': dangling, 'links': links})
    total = len(rows)
    result = {'requirements': rows, 'total': total, 'complete': complete,
              'completion_pct': round(100.0 * complete / total, 2),
              'incomplete_ids': [r['id'] for r in rows if not r['complete']]}
    return _pack('completion_matrix', result,
                 ['a link counts as present when it is a non-empty string (or list of them); '
                  'its content is not verified unless existing_paths is supplied',
                  'existing_paths checks only that a referenced file is listed, not that the '
                  'symbol or test exists or passes',
                  'completion is a count of fully linked requirements, not a quality judgement'],
                 ['<= 2000 requirements, <= 50 references per link, <= 10000 existing paths'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'skill_contract': skill_contract, 'provenance_card': provenance_card,
    'behaviour_compare': behaviour_compare, 'capability_overlap': capability_overlap,
    'legacy_import_audit': legacy_import_audit, 'adapter_reality': adapter_reality,
    'capability_passport': capability_passport, 'approval_lifecycle': approval_lifecycle,
    'snapshot_restore': snapshot_restore, 'completion_matrix': completion_matrix,
}


def run(op, params=None):
    """Validate and dispatch: run('skill_contract', {...}) -> {'op','result','assumptions','limits'}."""
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
