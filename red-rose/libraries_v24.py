"""Red Rose V24: evaluate free/open-source libraries from supplied metadata and measurements.

Pure standard-library Python. No file I/O, no subprocess, no network, no printing,
no third-party imports. Nothing is installed, imported or executed: every op works
only on licence ids/texts, feature checklists, benchmark numbers and environment
facts that the CALLER supplies as data (someone else measured them).

Every op validates strictly (ValueError on wrong types, bools-as-numbers, non-finite
numbers, unknown parameter or field names, out-of-range values) and caps its work.
Each op returns {'op', 'result', 'assumptions', 'limits'}.

NOT LEGAL ADVICE. Licence classification is a coarse engineering triage of SPDX
identifiers; anything not recognised with confidence is reported as 'needs_review'
(evaluators) or 'rejected' (licence_check), never guessed.
"""
from __future__ import annotations

import json
import math
import re

MAX_PARAMS = 24
MAX_ITEMS = 200          # tools / libraries / options / stacks / scenes / targets
MAX_EVENTS = 10_000      # timestamps per list
MAX_TEXT = 200_000       # lockfile characters
MAX_LINES = 5_000        # lockfile logical lines
MAX_EXPR = 2_000         # SPDX expression characters
MAX_ALTERNATIVES = 64    # OR-alternatives after expanding an SPDX expression
MAX_NAME = 200

LEGAL_NOTE = 'not legal advice: a coarse engineering triage; have licences reviewed before shipping'

TOPICS = {
    '07.01': 'licence_check',
    '07.02': 'tool_benchmark',
    '07.03': 'vector_lib_eval',
    '07.04': 'web_anim_eval',
    '07.05': 'webgl_eval',
    '07.06': 'audio_lib_eval',
    '07.07': 'cv_lib_eval',
    '07.08': 'shot_detect_compare',
    '07.09': 'lockfile',
    '07.10': 'arabic_shaping_eval',
}

TOPIC_NAMES_AR = {
    '07.01': 'فحص رخصة مكتبة مونتاج',
    '07.02': 'مقارنة FFmpeg مع بدائل',
    '07.03': 'مكتبات الرسم المتجهي',
    '07.04': 'أطر التحريك بالويب',
    '07.05': 'تقنيات WebGL وThree.js',
    '07.06': 'مكتبات تحرير الصوت',
    '07.07': 'مكتبات رؤية حاسوبية',
    '07.08': 'أدوات اكتشاف اللقطات',
    '07.09': 'إدارة تبعيات Python',
    '07.10': 'مكتبات دعم تشكيل العربية',
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


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _opt_bool(value, name):
    if value is None:
        return None
    return _bool(value, name)


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _str(value, name, max_len=MAX_NAME, *, allow_empty=False):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    value = value.strip()
    if (not value and not allow_empty) or len(value) > max_len:
        raise ValueError(f'{name} must be a non-empty string of at most {max_len} characters')
    return value


def _list(value, name, max_len=MAX_ITEMS, *, min_len=0):
    if not isinstance(value, (list, tuple)) or not min_len <= len(value) <= max_len:
        raise ValueError(f'{name} must be a list of {min_len}..{max_len} items')
    return list(value)


def _dict(value, name, allowed=None, required=()):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object/dict')
    if not all(isinstance(k, str) for k in value):
        raise ValueError(f'{name} keys must be strings')
    if allowed is not None:
        bad = set(value) - set(allowed)
        if bad:
            raise ValueError(f'{name} has unknown field(s): ' + ', '.join(sorted(bad)))
    for key in required:
        if key not in value:
            raise ValueError(f'{name} is missing required field {key!r}')
    return value


def _times(value, name):
    items = _list(value, name, MAX_EVENTS)
    return sorted(_num(t, 0, 1e7, f'{name}[{i}]') for i, t in enumerate(items))


def _unique_names(entries, name):
    seen = set()
    for e in entries:
        key = e['name'].lower()
        if key in seen:
            raise ValueError(f'{name}: duplicate name {e["name"]!r}')
        seen.add(key)


def _r(x, nd=6):
    return None if x is None else round(x, nd)


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


# --------------------------------------------------------------------------- licence data

PERMISSIVE, WEAK, STRONG = 'permissive', 'weak_copyleft', 'strong_copyleft'
NON_COMMERCIAL, PROPRIETARY, CUSTOM, UNKNOWN = ('non_commercial', 'proprietary',
                                                'custom_needs_review', 'unknown')

# id -> (class, family, deprecated_alias_of or None)
_LIC = {}


def _add(ids, cls, family, deprecated=None):
    for lid in ids:
        _LIC[lid] = (cls, family, deprecated.get(lid) if deprecated else None)


# binary_attribution: does redistributing compiled/minified code require shipping the notice?
_FAMILY = {
    'mit': {'binary_attribution': True, 'note': 'keep copyright + permission notice in all copies'},
    'mit0': {'binary_attribution': False, 'note': 'no attribution condition'},
    'bsd2': {'binary_attribution': True, 'note': 'binary redistribution must reproduce the notice in docs/materials'},
    'bsd3': {'binary_attribution': True, 'note': 'reproduce notice; no endorsement using contributor names'},
    'apache': {'binary_attribution': True, 'note': 'ship licence text, keep NOTICE file contents, mark modified files; patent grant ends on patent litigation'},
    'isc': {'binary_attribution': True, 'note': 'keep copyright + permission notice in all copies'},
    'zlib': {'binary_attribution': False, 'note': 'notice must stay in source distributions; altered versions must be marked; no attribution needed in binaries'},
    '0bsd': {'binary_attribution': False, 'note': 'no attribution condition'},
    'bsl': {'binary_attribution': False, 'note': 'notice required in source copies, not in machine-executable object code'},
    'unlicense': {'binary_attribution': False, 'note': 'public-domain dedication with permissive fallback'},
    'hpnd': {'binary_attribution': True, 'note': 'keep notice in copies and supporting documentation'},
    'lgpl2': {'binary_attribution': True, 'note': 'LGPL-2.x: ship licence, offer library source (incl. your changes to it), allow users to relink/replace the library'},
    'lgpl3': {'binary_attribution': True, 'note': 'LGPL-3.0: as LGPL-2.x plus GPL-3.0 terms (installation information for consumer devices)'},
    'mpl': {'binary_attribution': True, 'note': 'MPL-2.0: file-level copyleft; source of MPL-covered files (incl. your edits) must be available; the larger work may use other terms'},
    'gpl2': {'binary_attribution': True, 'note': 'GPL-2.0: whole combined work distributed under GPL with complete corresponding source'},
    'gpl3': {'binary_attribution': True, 'note': 'GPL-3.0: whole combined work under GPL-3.0 with corresponding source and installation information'},
    'agpl': {'binary_attribution': True, 'note': 'AGPL-3.0: GPL-3.0 duties plus section 13: users interacting over a network with a modified version must be offered its source'},
    'ccnc': {'binary_attribution': True, 'note': 'Creative Commons NonCommercial: commercial use is not licensed; attribution required'},
}

_add(['MIT'], PERMISSIVE, 'mit')
_add(['MIT-0'], PERMISSIVE, 'mit0')
_add(['BSD-2-Clause'], PERMISSIVE, 'bsd2')
_add(['BSD-3-Clause'], PERMISSIVE, 'bsd3')
_add(['Apache-2.0'], PERMISSIVE, 'apache')
_add(['ISC'], PERMISSIVE, 'isc')
_add(['Zlib'], PERMISSIVE, 'zlib')
_add(['0BSD'], PERMISSIVE, '0bsd')
_add(['BSL-1.0'], PERMISSIVE, 'bsl')
_add(['Unlicense'], PERMISSIVE, 'unlicense')
_add(['HPND', 'MIT-CMU'], PERMISSIVE, 'hpnd')
_DEP = {'LGPL-2.0': 'LGPL-2.0-only', 'LGPL-2.0+': 'LGPL-2.0-or-later',
        'LGPL-2.1': 'LGPL-2.1-only', 'LGPL-2.1+': 'LGPL-2.1-or-later',
        'LGPL-3.0': 'LGPL-3.0-only', 'LGPL-3.0+': 'LGPL-3.0-or-later',
        'GPL-2.0': 'GPL-2.0-only', 'GPL-2.0+': 'GPL-2.0-or-later',
        'GPL-3.0': 'GPL-3.0-only', 'GPL-3.0+': 'GPL-3.0-or-later',
        'AGPL-3.0': 'AGPL-3.0-only'}
_add(['LGPL-2.0-only', 'LGPL-2.0-or-later', 'LGPL-2.1-only', 'LGPL-2.1-or-later',
      'LGPL-2.0', 'LGPL-2.0+', 'LGPL-2.1', 'LGPL-2.1+'], WEAK, 'lgpl2', _DEP)
_add(['LGPL-3.0-only', 'LGPL-3.0-or-later', 'LGPL-3.0', 'LGPL-3.0+'], WEAK, 'lgpl3', _DEP)
_add(['MPL-2.0', 'MPL-2.0-no-copyleft-exception'], WEAK, 'mpl')
_add(['GPL-2.0-only', 'GPL-2.0-or-later', 'GPL-2.0', 'GPL-2.0+'], STRONG, 'gpl2', _DEP)
_add(['GPL-3.0-only', 'GPL-3.0-or-later', 'GPL-3.0', 'GPL-3.0+'], STRONG, 'gpl3', _DEP)
_add(['AGPL-3.0-only', 'AGPL-3.0-or-later', 'AGPL-3.0'], STRONG, 'agpl', _DEP)
_add(['CC-BY-NC-3.0', 'CC-BY-NC-4.0', 'CC-BY-NC-SA-3.0', 'CC-BY-NC-SA-4.0',
      'CC-BY-NC-ND-3.0', 'CC-BY-NC-ND-4.0'], NON_COMMERCIAL, 'ccnc')
_LIC_LOWER = {k.lower(): k for k in _LIC}

_EXCEPTIONS = {e.lower(): e for e in (
    'Classpath-exception-2.0', 'LLVM-exception', 'GCC-exception-3.1',
    'Autoconf-exception-3.0', 'Bison-exception-2.2', 'Font-exception-2.0')}

USAGE_MODES = ('internal', 'distributed_binary', 'saas')

# Reference facts for named libraries (lower-case key). spdx None => no confident SPDX id.
KNOWN_LIBRARIES = {
    'ffmpeg': {'spdx': 'LGPL-2.1-or-later',
               'note': 'GPL-2.0-or-later (or GPL-3.0) when built with GPL components such as libx264 (--enable-gpl); check the actual build configuration'},
    'cairosvg': {'spdx': 'LGPL-3.0-or-later', 'note': 'CairoSVG is LGPLv3+'},
    'librsvg': {'spdx': 'LGPL-2.1-or-later', 'note': 'librsvg library is LGPL-2.1-or-later'},
    'inkscape': {'spdx': 'GPL-2.0-or-later', 'note': 'mostly GPL-2.0-or-later, some parts GPL-3.0; used as an external program it is not linked into your code'},
    'resvg': {'spdx': None, 'note': 'licence changed between releases (older releases MPL-2.0, newer releases dual Apache-2.0 OR MIT): verify the exact version used'},
    'three.js': {'spdx': 'MIT', 'note': 'three.js is MIT'},
    'anime.js': {'spdx': 'MIT', 'note': 'anime.js is MIT'},
    'gsap': {'spdx': None, 'note': 'GSAP uses its own custom (non-SPDX) standard licence: review the current terms'},
    'opencv': {'spdx': None, 'note': 'OpenCV >= 4.5.0 is Apache-2.0; earlier releases BSD-3-Clause'},
    'opencv-python': {'spdx': None, 'note': 'bundles OpenCV (Apache-2.0 for >= 4.5.0) plus third-party binaries (e.g. FFmpeg LGPL-2.1, Qt LGPL-3.0 on some platforms): review bundled licences'},
    'harfbuzz': {'spdx': None, 'note': 'HarfBuzz uses the "Old MIT" licence text (MIT-like, permissive); no confident SPDX id recorded here'},
    'pango': {'spdx': None, 'note': 'Pango is LGPL (2.x-or-later family, weak copyleft); confirm the exact version string in the release'},
    'fribidi': {'spdx': 'LGPL-2.1-or-later', 'note': 'GNU FriBidi is LGPL-2.1-or-later'},
    'libraqm': {'spdx': 'MIT', 'note': 'libraqm is MIT'},
    'pillow': {'spdx': 'MIT-CMU', 'note': 'Pillow uses the HPND-style MIT-CMU licence; Arabic shaping needs libraqm (and FriBiDi) at runtime'},
    'librosa': {'spdx': 'ISC', 'note': 'librosa is ISC'},
    'pyscenedetect': {'spdx': 'BSD-3-Clause', 'note': 'PySceneDetect is BSD-3-Clause'},
    'moviepy': {'spdx': 'MIT', 'note': 'MoviePy is MIT'},
}


# --------------------------------------------------------------------------- SPDX parsing

_TOKEN_RE = re.compile(r'\s*(\(|\)|[A-Za-z0-9.\-+:]+)')


def _tokenize(expr):
    tokens, pos = [], 0
    expr = expr.rstrip()
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if not m or m.end() == pos:
            raise ValueError(f'licence expression has an invalid character at position {pos}')
        tokens.append(m.group(1))
        pos = m.end()
    if not tokens:
        raise ValueError('licence expression is empty')
    return tokens


def _parse_spdx(expr):
    """Return a tree: ('lic', id, exception|None) | ('and'|'or', left, right)."""
    tokens = _tokenize(expr)
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def op_is(tok, word):
        return tok is not None and tok in (word, word.lower())

    def take():
        tok = peek()
        pos[0] += 1
        return tok

    def parse_or():
        node = parse_and()
        while op_is(peek(), 'OR'):
            take()
            node = ('or', node, parse_and())
        return node

    def parse_and():
        node = parse_atom()
        while op_is(peek(), 'AND'):
            take()
            node = ('and', node, parse_atom())
        return node

    def parse_atom():
        tok = take()
        if tok is None:
            raise ValueError('licence expression ended unexpectedly')
        if tok == '(':
            node = parse_or()
            if take() != ')':
                raise ValueError('licence expression has an unbalanced parenthesis')
            return node
        if tok == ')' or tok.upper() in ('AND', 'OR', 'WITH'):
            raise ValueError(f'licence expression has an unexpected {tok!r}')
        exc = None
        if op_is(peek(), 'WITH'):
            take()
            exc = take()
            if exc is None or exc in ('(', ')') or exc.upper() in ('AND', 'OR', 'WITH'):
                raise ValueError('WITH must be followed by an exception id')
        return ('lic', tok, exc)

    tree = parse_or()
    if pos[0] != len(tokens):
        raise ValueError(f'licence expression has trailing token {tokens[pos[0]]!r}')
    return tree


def _alternatives(tree):
    kind = tree[0]
    if kind == 'lic':
        return [[(tree[1], tree[2])]]
    left, right = _alternatives(tree[1]), _alternatives(tree[2])
    if kind == 'or':
        out = left + right
    else:
        if len(left) * len(right) > MAX_ALTERNATIVES:
            raise ValueError(f'licence expression expands to more than {MAX_ALTERNATIVES} alternatives')
        out = [a + b for a in left for b in right]
    if len(out) > MAX_ALTERNATIVES:
        raise ValueError(f'licence expression expands to more than {MAX_ALTERNATIVES} alternatives')
    return out


def _term_duties(lid, exc, mode, linking, commercial, modified):
    """Classify one licence term and derive its duties for the usage mode."""
    notes = []
    canon = _LIC_LOWER.get(lid.lower())
    if canon is None:
        if lid.lower() == 'licenseref-proprietary':
            cls, family = PROPRIETARY, None
        elif lid.lower().startswith('licenseref-') or lid.lower().startswith('documentref-'):
            cls, family = CUSTOM, None
        else:
            cls, family = UNKNOWN, None
    else:
        cls, family, dep = _LIC[canon]
        if dep:
            notes.append(f'{canon} is a deprecated SPDX id; current id is {dep}')
    term = {'id': canon or lid, 'class': cls, 'exception': None,
            'attribution': False, 'source_disclosure': False, 'duties': [], 'notes': notes}
    if exc is not None:
        term['exception'] = _EXCEPTIONS.get(exc.lower(), exc)
        notes.append(f'WITH {term["exception"]}: the exception changes the duties; review its text'
                     + ('' if exc.lower() in _EXCEPTIONS else ' (exception id not recognised)'))
    if cls == UNKNOWN:
        term['status'] = 'rejected'
        notes.append('licence id not recognised: rejected until someone identifies it')
        return term
    if cls == PROPRIETARY:
        term['status'] = 'needs_review'
        term['duties'].append('use only under a separate written licence agreement')
        return term
    if cls == CUSTOM:
        term['status'] = 'needs_review'
        term['duties'].append('custom licence text: read the referenced terms')
        return term
    info = _FAMILY[family]
    status = 'needs_review' if exc is not None else 'allowed'
    duties = term['duties']
    if cls == NON_COMMERCIAL:
        term['attribution'] = True
        duties.append(info['note'])
        status = 'not_allowed' if commercial else ('needs_review' if exc else 'allowed')
        term['status'] = status
        return term
    if mode == 'distributed_binary':
        term['attribution'] = info['binary_attribution']
        if term['attribution']:
            duties.append('include the licence text / copyright notice with the distribution')
        if family in ('apache',):
            duties.append('include NOTICE contents if the project has a NOTICE file; state changes in modified files')
        if family in ('lgpl2', 'lgpl3'):
            term['source_disclosure'] = True
            duties.append('provide (or offer) source of the LGPL library including your modifications to it')
            if linking == 'static':
                duties.append('static linking: also provide object files (or source) so users can relink with a modified library')
            else:
                duties.append('dynamic linking: users must be able to replace the shared library')
        elif family == 'mpl':
            term['source_disclosure'] = True
            duties.append('make source of MPL-covered files (incl. your changes) available; inform recipients how to get it')
        elif cls == STRONG:
            term['source_disclosure'] = True
            duties.append('license the combined work under the same GPL terms and provide complete corresponding source')
    elif mode == 'saas':
        if family == 'agpl':
            term['source_disclosure'] = True
            term['attribution'] = True
            duties.append('AGPL section 13: offer the corresponding source to remote network users'
                          + ('' if modified else ' (strictly triggered by modified versions; flagged conservatively)'))
        else:
            notes.append('running as a network service is not distribution under this licence; '
                         'duties apply again if code (e.g. JavaScript, apps) is shipped to users')
    else:  # internal
        notes.append('internal use without distribution triggers no copyleft/attribution duty; '
                     'giving copies to another legal entity (clients, contractors) is distribution')
        if family == 'agpl':
            notes.append('AGPL: if users outside the organisation reach a modified version over a network, section 13 applies')
    if info['note'] and info['note'] not in duties:
        notes.append(info['note'])
    term['status'] = status
    return term


_STATUS_RANK = {'allowed': 0, 'needs_review': 1, 'not_allowed': 2, 'rejected': 3}
_CLASS_BURDEN = {PERMISSIVE: 0, WEAK: 1, STRONG: 2, NON_COMMERCIAL: 3, PROPRIETARY: 3,
                 CUSTOM: 3, UNKNOWN: 4}


def _evaluate_expression(expr, mode='distributed_binary', linking='dynamic',
                         commercial=True, modified=False):
    tree = _parse_spdx(expr)
    alts = []
    for i, alt in enumerate(_alternatives(tree)):
        terms = [_term_duties(lid, exc, mode, linking, commercial, modified) for lid, exc in alt]
        status = max((t['status'] for t in terms), key=_STATUS_RANK.__getitem__)
        burden = sum(_CLASS_BURDEN[t['class']] + (1 if t['source_disclosure'] else 0) for t in terms)
        worst = max((t['class'] for t in terms), key=_CLASS_BURDEN.__getitem__)
        alts.append({'index': i, 'licences': [t['id'] for t in terms], 'status': status,
                     'worst_class': worst, 'burden': burden,
                     'attribution': any(t['attribution'] for t in terms),
                     'source_disclosure': any(t['source_disclosure'] for t in terms),
                     'terms': terms})
    chosen = min(alts, key=lambda a: (_STATUS_RANK[a['status']], a['burden'],
                                      a['attribution'], a['index']))
    return alts, chosen


def _licence_info(licence, name=None):
    """Licence triage for evaluators: ok / needs_review; never guesses."""
    ref = KNOWN_LIBRARIES.get(name.lower()) if name else None
    notes = []
    if ref:
        notes.append('reference: ' + ref['note'])
    if licence is None:
        if ref and ref['spdx']:
            licence = ref['spdx']
            notes.append('licence taken from the built-in reference table')
        else:
            return {'expression': None, 'class': 'not_supplied' if not ref else CUSTOM,
                    'status': 'needs_review', 'notes': notes + ['no confident SPDX licence: review terms']}
    licence = _str(licence, 'licence', MAX_EXPR)
    try:
        _, chosen = _evaluate_expression(licence)
    except ValueError:
        return {'expression': licence, 'class': CUSTOM, 'status': 'needs_review',
                'notes': notes + ['not a valid SPDX expression (custom/non-SPDX licence): review terms']}
    if chosen['status'] == 'rejected' or chosen['worst_class'] in (UNKNOWN, CUSTOM, PROPRIETARY):
        return {'expression': licence, 'class': CUSTOM, 'status': 'needs_review',
                'notes': notes + ['licence id(s) not recognised as known SPDX ids: review terms']}
    status = 'ok' if chosen['status'] == 'allowed' else 'needs_review'
    if chosen['worst_class'] == NON_COMMERCIAL:
        status = 'needs_review'
        notes.append('non-commercial licence')
    if ref and ref['spdx'] and ref['spdx'].lower() != licence.lower():
        status = 'needs_review'
        notes.append(f'supplied licence {licence!r} differs from reference {ref["spdx"]!r}')
    if ref and not ref['spdx']:
        status = 'needs_review'
        notes.append('reference table has no confident SPDX id for this library: review')
    if chosen['worst_class'] == STRONG:
        notes.append('strong copyleft: fine as a separate program, but linking/bundling spreads GPL terms')
    return {'expression': licence, 'class': chosen['worst_class'], 'status': status,
            'chosen_alternative': chosen['licences'], 'notes': notes}


# --------------------------------------------------------------------------- 07.01 licence_check

def licence_check(*, expression='MIT OR GPL-3.0-only', usage='distributed_binary',
                  linking='dynamic', commercial=True, modified=False, **extra):
    """Parse an SPDX expression and derive duties for a usage mode.

    usage: 'internal' | 'distributed_binary' | 'saas'. OR offers a choice (the least
    burdensome allowed alternative is picked), AND requires all, WITH attaches an
    exception (always flagged for review). Unknown ids are rejected.
    """
    _no_extra(extra)
    expression = _str(expression, 'expression', MAX_EXPR)
    usage = _choice(usage, set(USAGE_MODES), 'usage')
    linking = _choice(linking, {'dynamic', 'static'}, 'linking')
    commercial = _bool(commercial, 'commercial')
    modified = _bool(modified, 'modified')
    alts, chosen = _evaluate_expression(expression, usage, linking, commercial, modified)
    verdict = {'allowed': 'allowed', 'needs_review': 'needs_review',
               'not_allowed': 'rejected', 'rejected': 'rejected'}[chosen['status']]
    reason = {
        'allowed': 'a fully recognised alternative is usable with the listed duties',
        'needs_review': 'usable only after a human reviews custom terms or exceptions',
        'not_allowed': 'non-commercial terms conflict with commercial use',
        'rejected': 'unrecognised licence id(s): cannot classify',
    }[chosen['status']]
    unknown = sorted({t['id'] for a in alts for t in a['terms'] if t['class'] == UNKNOWN})
    result = {
        'expression': expression, 'usage': usage, 'linking': linking,
        'commercial': commercial, 'verdict': verdict, 'reason': reason,
        'chosen': chosen['licences'], 'chosen_class': chosen['worst_class'],
        'attribution_required': chosen['attribution'],
        'source_disclosure_required': chosen['source_disclosure'],
        'duties': [d for t in chosen['terms'] for d in t['duties']],
        'alternatives': alts, 'unknown_ids': unknown, 'disclaimer': LEGAL_NOTE,
    }
    return _pack('licence_check', result,
                 [LEGAL_NOTE,
                  'SPDX precedence: WITH binds tighter than AND, AND tighter than OR; ids matched case-insensitively',
                  'OR = licensee may choose; the least burdensome fully allowed alternative is chosen',
                  'deprecated ids (GPL-3.0, LGPL-2.1+, ...) are accepted and mapped to their -only/-or-later meaning',
                  "'internal' means no copies leave the organisation; 'saas' means users only interact over a network",
                  'AGPL section 13 is flagged for SaaS conservatively even when modified=False (it strictly binds modified versions)'],
                 [f'expression <= {MAX_EXPR} characters and <= {MAX_ALTERNATIVES} expanded alternatives',
                  'only the licence ids in the built-in table are classified; everything else is rejected (or needs_review for LicenseRef-*)',
                  'patent, trademark, export and font-embedding questions are out of scope',
                  'does not read licence texts or verify that a package really uses the declared licence'])


# --------------------------------------------------------------------------- 07.02 tool_benchmark

_TOOL_FIELDS = {'name', 'features', 'wall_time_s', 'output_size_bytes', 'quality_score', 'licence', 'notes'}
_EXAMPLE_TOOLS = [
    {'name': 'ffmpeg', 'features': {'cut': True, 'audio': True, 'encode': True},
     'wall_time_s': 4.0, 'output_size_bytes': 12_000_000, 'quality_score': 92.0},
    {'name': 'tool_b', 'features': {'cut': True, 'audio': False, 'encode': True},
     'wall_time_s': 2.0, 'output_size_bytes': 10_000_000, 'quality_score': 95.0},
    {'name': 'tool_c', 'features': {'cut': True, 'audio': True, 'encode': True},
     'wall_time_s': 8.0, 'output_size_bytes': 9_000_000, 'quality_score': 93.0},
    {'name': 'tool_d', 'features': {'cut': True, 'audio': True, 'encode': True},
     'wall_time_s': None, 'output_size_bytes': 11_000_000, 'quality_score': 90.0},
]


def tool_benchmark(*, tools=None, required_features=None, rank_by='efficiency',
                   sample='example clip (illustrative numbers, not measurements)', **extra):
    """Rank tools measured on ONE sample. Tools lacking a required feature cannot win.

    efficiency = quality_score / wall_time_s (quality points per second of wall time).
    rank_by: 'efficiency' | 'quality' | 'time' | 'size'.
    """
    _no_extra(extra)
    tools = _EXAMPLE_TOOLS if tools is None else tools
    tools = _list(tools, 'tools', MAX_ITEMS, min_len=1)
    if required_features is None:
        required_features = ['cut', 'audio', 'encode']
    required_features = [_str(f, f'required_features[{i}]', 60)
                         for i, f in enumerate(_list(required_features, 'required_features', 50))]
    rank_by = _choice(rank_by, {'efficiency', 'quality', 'time', 'size'}, 'rank_by')
    sample = _str(sample, 'sample', 500)
    rows = []
    for i, t in enumerate(tools):
        t = _dict(t, f'tools[{i}]', _TOOL_FIELDS, ('name',))
        name = _str(t['name'], f'tools[{i}].name')
        feats = _dict(t.get('features', {}), f'tools[{i}].features')
        feats = {k: _opt_bool(v, f'tools[{i}].features.{k}') for k, v in feats.items()}
        meas = {}
        missing = []
        for key, low, high in (('wall_time_s', 0, 1e7), ('output_size_bytes', 0, 1e15),
                               ('quality_score', 0, 1e6)):
            v = t.get(key)
            if v is None:
                missing.append(key)
                meas[key] = None
            else:
                meas[key] = _num(v, low, high, f'tools[{i}].{key}', low_open=(key == 'wall_time_s'))
        missing_features = [f for f in required_features if feats.get(f) is not True]
        unmeasured_features = [f for f in required_features if feats.get(f) is None]
        eff = (meas['quality_score'] / meas['wall_time_s']
               if meas['quality_score'] is not None and meas['wall_time_s'] is not None else None)
        rows.append({'name': name, 'eligible': not missing_features,
                     'missing_features': missing_features,
                     'unmeasured_features': unmeasured_features,
                     'missing_measurements': missing,
                     'wall_time_s': meas['wall_time_s'],
                     'output_size_bytes': meas['output_size_bytes'],
                     'quality_score': meas['quality_score'],
                     'efficiency_quality_per_s': _r(eff),
                     'licence': (_licence_info(t.get('licence'), name)
                                 if t.get('licence') is not None or name.lower() in KNOWN_LIBRARIES else None)})
    _unique_names(rows, 'tools')
    metric = {'efficiency': ('efficiency_quality_per_s', True), 'quality': ('quality_score', True),
              'time': ('wall_time_s', False), 'size': ('output_size_bytes', False)}[rank_by]
    key, higher = metric
    rankable = [r for r in rows if r['eligible'] and r[key] is not None]
    rankable.sort(key=lambda r: ((-r[key]) if higher else r[key], r['name'].lower()))
    for pos, r in enumerate(rankable, 1):
        r['rank'] = pos
    for r in rows:
        r.setdefault('rank', None)
        if r['rank'] is None:
            r['unranked_reason'] = ('missing required feature(s): ' + ', '.join(r['missing_features'])
                                    if not r['eligible'] else f'missing measurement for {key}')
    fastest = min((r['wall_time_s'] for r in rows if r['wall_time_s'] is not None), default=None)
    for r in rows:
        r['time_vs_fastest'] = (_r(r['wall_time_s'] / fastest, 4)
                                if fastest and r['wall_time_s'] is not None else None)
    result = {'sample': sample, 'rank_by': rank_by, 'required_features': required_features,
              'winner': rankable[0]['name'] if rankable else None,
              'ranking': [r['name'] for r in rankable], 'tools': rows,
              'missing_measurements': {r['name']: r['missing_measurements']
                                       for r in rows if r['missing_measurements']}}
    return _pack('tool_benchmark', result,
                 ['all numbers were measured by the caller on the same single sample and machine',
                  'quality_score is whatever metric the caller used (e.g. VMAF); higher is better',
                  'efficiency = quality_score / wall_time_s; it is not comparable across different samples',
                  'a feature counts only when explicitly true; null/absent means not measured and disqualifies',
                  'the default example uses illustrative numbers, not real measurements of any tool'],
                 [f'<= {MAX_ITEMS} tools', 'one sample cannot show variance: rerun several times before deciding',
                  'no statistical significance test; ties broken by name'])


# --------------------------------------------------------------------------- 07.03 vector_lib_eval

_OPTION_FIELDS = {'name', 'library', 'licence', 'checks', 'notes'}
ARABIC_CHECK = 'arabic_text_shaped'
_EXAMPLE_SVG = [
    {'name': 'svg_option_A', 'library': 'librsvg',
     'checks': {'renders_basic_shapes': True, 'gradients': True, ARABIC_CHECK: True}},
    {'name': 'svg_option_B', 'licence': 'LGPL-3.0-or-later',
     'checks': {'renders_basic_shapes': True, 'gradients': True, ARABIC_CHECK: False}},
    {'name': 'svg_option_C', 'licence': 'GPL-2.0-or-later',
     'checks': {'renders_basic_shapes': True, 'gradients': True, ARABIC_CHECK: None}},
]


def _eval_checks(checks, required, label):
    checks = _dict(checks, label)
    vals = {k: _opt_bool(v, f'{label}.{k}') for k, v in checks.items()}
    failed = [c for c in required if vals.get(c) is False]
    untested = [c for c in required if vals.get(c) is None]
    return vals, failed, untested


def vector_lib_eval(*, options=None, required_checks=None, **extra):
    """Evaluate SVG pipeline options on a supplied checklist; recommend only those whose
    Arabic shaping check ('arabic_text_shaped') passed and all required checks passed."""
    _no_extra(extra)
    options = _list(_EXAMPLE_SVG if options is None else options, 'options', MAX_ITEMS, min_len=1)
    if required_checks is None:
        required_checks = ['renders_basic_shapes', ARABIC_CHECK]
    required_checks = [_str(c, f'required_checks[{i}]', 80)
                       for i, c in enumerate(_list(required_checks, 'required_checks', 50))]
    if ARABIC_CHECK not in required_checks:
        required_checks.append(ARABIC_CHECK)
    rows = []
    for i, o in enumerate(options):
        o = _dict(o, f'options[{i}]', _OPTION_FIELDS, ('name', 'checks'))
        name = _str(o['name'], f'options[{i}].name')
        lib = _str(o['library'], f'options[{i}].library') if o.get('library') is not None else None
        vals, failed, untested = _eval_checks(o['checks'], required_checks, f'options[{i}].checks')
        lic = _licence_info(o.get('licence'), lib or name)
        passed = not failed and not untested
        status = ('recommended' if passed and lic['status'] == 'ok'
                  else 'recommended_pending_licence_review' if passed
                  else 'not_recommended')
        rows.append({'name': name, 'library': lib, 'checks': vals, 'failed': failed,
                     'untested': untested, 'arabic_ok': vals.get(ARABIC_CHECK) is True,
                     'licence': lic, 'status': status})
    _unique_names(rows, 'options')
    result = {'required_checks': required_checks,
              'recommended': [r['name'] for r in rows if r['status'] == 'recommended'],
              'pending_licence_review': [r['name'] for r in rows
                                         if r['status'] == 'recommended_pending_licence_review'],
              'not_recommended': [r['name'] for r in rows if r['status'] == 'not_recommended'],
              'options': rows,
              'reference_licences': {k: KNOWN_LIBRARIES[k] for k in
                                     ('cairosvg', 'librsvg', 'inkscape', 'resvg')}}
    return _pack('vector_lib_eval', result,
                 ['check results are supplied by the caller (e.g. visual comparison of a rendered Arabic sample)',
                  f"'{ARABIC_CHECK}' is always required: an option failing or not testing it is never recommended",
                  'licence status is a triage only; ' + LEGAL_NOTE,
                  'default example options are placeholders with illustrative results'],
                 [f'<= {MAX_ITEMS} options', 'does not render SVG or inspect glyphs itself',
                  'reference licences reflect known releases; verify the version you ship'])


# --------------------------------------------------------------------------- 07.04 web_anim_eval

_ANIM_FIELDS = {'name', 'licence', 'needs_browser', 'bundle_kb', 'notes'}
_EXAMPLE_ANIM = [
    {'name': 'anime.js', 'licence': 'MIT', 'needs_browser': True, 'bundle_kb': 17.0},
    {'name': 'gsap', 'licence': 'GSAP Standard License', 'needs_browser': True, 'bundle_kb': 70.0},
    {'name': 'example_heavy_lib', 'licence': 'Apache-2.0', 'needs_browser': True, 'bundle_kb': 900.0},
]


def web_anim_eval(*, libraries=None, max_bundle_kb=200.0, browser_available=True, **extra):
    """Record licences and limits of web animation libraries; custom/non-SPDX licences are
    needs_review (never 'permissive'); constraint violations are recorded per library."""
    _no_extra(extra)
    libraries = _list(_EXAMPLE_ANIM if libraries is None else libraries, 'libraries', MAX_ITEMS, min_len=1)
    max_bundle_kb = _num(max_bundle_kb, 0, 1e6, 'max_bundle_kb', low_open=True)
    browser_available = _bool(browser_available, 'browser_available')
    rows = []
    for i, lib in enumerate(libraries):
        lib = _dict(lib, f'libraries[{i}]', _ANIM_FIELDS, ('name',))
        name = _str(lib['name'], f'libraries[{i}].name')
        needs_browser = _opt_bool(lib.get('needs_browser'), f'libraries[{i}].needs_browser')
        bundle = (None if lib.get('bundle_kb') is None
                  else _num(lib['bundle_kb'], 0, 1e6, f'libraries[{i}].bundle_kb'))
        lic = _licence_info(lib.get('licence'), name)
        problems, unknowns = [], []
        if needs_browser is None:
            unknowns.append('needs_browser not supplied')
        elif needs_browser and not browser_available:
            problems.append('needs a browser runtime but none is available (headless render requires one)')
        if bundle is None:
            unknowns.append('bundle size not supplied')
        elif bundle > max_bundle_kb:
            problems.append(f'bundle {bundle} kB exceeds limit {max_bundle_kb} kB')
        status = ('rejected' if problems else
                  'needs_review' if lic['status'] != 'ok' or unknowns else 'ok')
        rows.append({'name': name, 'licence': lic, 'licence_class': lic['class'],
                     'needs_browser': needs_browser, 'bundle_kb': bundle,
                     'problems': problems, 'unknowns': unknowns, 'status': status})
    _unique_names(rows, 'libraries')
    result = {'max_bundle_kb': max_bundle_kb, 'browser_available': browser_available,
              'ok': [r['name'] for r in rows if r['status'] == 'ok'],
              'needs_review': [r['name'] for r in rows if r['status'] == 'needs_review'],
              'rejected': [r['name'] for r in rows if r['status'] == 'rejected'],
              'libraries': rows,
              'reference_licences': {k: KNOWN_LIBRARIES[k] for k in ('anime.js', 'gsap', 'three.js')}}
    return _pack('web_anim_eval', result,
                 ['bundle sizes are supplied by the caller (minified, state whether gzip)',
                  'any licence that is not a fully recognised SPDX expression is needs_review, never permissive',
                  LEGAL_NOTE],
                 [f'<= {MAX_ITEMS} libraries', 'does not download, bundle or run any library',
                  'runtime performance is not evaluated here (see webgl_eval for fps facts)'])


# --------------------------------------------------------------------------- 07.05 webgl_eval

_ENV_FIELDS = {'webgl1', 'webgl2', 'max_texture_size', 'fps_modest_scene', 'description'}
_SCENE_FIELDS = {'name', 'needs_webgl2', 'min_texture_size', 'target_fps', 'relative_cost'}
_EXAMPLE_ENV = {'webgl1': True, 'webgl2': False, 'max_texture_size': 4096,
                'fps_modest_scene': 60.0, 'description': 'illustrative low-end laptop'}
_EXAMPLE_SCENES = [
    {'name': 'logo_spin', 'needs_webgl2': False, 'min_texture_size': 2048, 'target_fps': 30.0,
     'relative_cost': 1.0},
    {'name': 'volumetric_title', 'needs_webgl2': True, 'min_texture_size': 4096, 'target_fps': 30.0,
     'relative_cost': 1.5},
    {'name': 'particle_storm', 'needs_webgl2': False, 'min_texture_size': 1024, 'target_fps': 60.0,
     'relative_cost': 3.0},
]


def webgl_eval(*, environment=None, scenes=None, **extra):
    """Decide feasible / infeasible / unknown per scene from supplied environment facts.
    Estimated fps = measured fps on the modest scene / scene relative_cost."""
    _no_extra(extra)
    env = _dict(_EXAMPLE_ENV if environment is None else environment, 'environment', _ENV_FIELDS)
    scenes = _list(_EXAMPLE_SCENES if scenes is None else scenes, 'scenes', MAX_ITEMS, min_len=1)
    webgl1 = _opt_bool(env.get('webgl1'), 'environment.webgl1')
    webgl2 = _opt_bool(env.get('webgl2'), 'environment.webgl2')
    max_tex = (None if env.get('max_texture_size') is None
               else _int(env['max_texture_size'], 1, 1 << 20, 'environment.max_texture_size'))
    fps = (None if env.get('fps_modest_scene') is None
           else _num(env['fps_modest_scene'], 0, 10_000, 'environment.fps_modest_scene'))
    rows = []
    for i, s in enumerate(scenes):
        s = _dict(s, f'scenes[{i}]', _SCENE_FIELDS, ('name',))
        name = _str(s['name'], f'scenes[{i}].name')
        needs2 = _bool(s.get('needs_webgl2', False), f'scenes[{i}].needs_webgl2')
        min_tex = _int(s.get('min_texture_size', 1), 1, 1 << 20, f'scenes[{i}].min_texture_size')
        target = _num(s.get('target_fps', 30.0), 0, 1000, f'scenes[{i}].target_fps', low_open=True)
        cost = _num(s.get('relative_cost', 1.0), 0.01, 1000, f'scenes[{i}].relative_cost')
        reasons, unknown = [], []
        if needs2:
            if webgl2 is False:
                reasons.append('scene needs WebGL2 but the environment has no WebGL2')
            elif webgl2 is None:
                unknown.append('WebGL2 support not supplied')
        else:
            if webgl1 is False and webgl2 is not True:
                reasons.append('no WebGL context available')
            elif webgl1 is None and webgl2 is None:
                unknown.append('WebGL support not supplied')
        if max_tex is None:
            unknown.append('max texture size not supplied')
        elif min_tex > max_tex:
            reasons.append(f'needs {min_tex}px textures; environment max is {max_tex}px')
        est = None
        if fps is None:
            unknown.append('measured fps not supplied')
        else:
            est = fps / cost
            if est < target:
                reasons.append(f'estimated {est:.1f} fps < target {target:g} fps')
        decision = 'infeasible' if reasons else ('unknown' if unknown else 'feasible')
        rows.append({'name': name, 'decision': decision, 'reasons': reasons, 'unknown': unknown,
                     'estimated_fps': _r(est, 3), 'target_fps': target})
    _unique_names(rows, 'scenes')
    result = {'environment': {'webgl1': webgl1, 'webgl2': webgl2, 'max_texture_size': max_tex,
                              'fps_modest_scene': fps,
                              'description': _str(env.get('description', ''), 'environment.description',
                                                  500, allow_empty=True)},
              'feasible': [r['name'] for r in rows if r['decision'] == 'feasible'],
              'infeasible': [r['name'] for r in rows if r['decision'] == 'infeasible'],
              'unknown': [r['name'] for r in rows if r['decision'] == 'unknown'],
              'scenes': rows,
              'library': {'name': 'three.js', 'licence': 'MIT', 'licence_class': PERMISSIVE}}
    return _pack('webgl_eval', result,
                 ['environment facts were measured by the caller on the target device/browser',
                  'fps scales inversely with relative_cost (a linear previz heuristic, not a profiler)',
                  'a WebGL2 context also provides WebGL1-level features',
                  'three.js is MIT-licensed (keep its licence notice when shipping it)'],
                 [f'<= {MAX_ITEMS} scenes', 'GPU memory, shader limits and extensions are not modelled',
                  'any missing fact yields "unknown", never "feasible"'])


# --------------------------------------------------------------------------- event matching

def _match_events(reference, detected, tol):
    """Optimal one-to-one matching of sorted 1D events within +-tol (two-pointer)."""
    i = j = 0
    pairs = []
    unmatched_ref, unmatched_det = [], []
    while i < len(reference) and j < len(detected):
        r, d = reference[i], detected[j]
        if abs(r - d) <= tol + 1e-12:
            pairs.append([r, d])
            i += 1
            j += 1
        elif d < r:
            unmatched_det.append(d)
            j += 1
        else:
            unmatched_ref.append(r)
            i += 1
    unmatched_ref.extend(reference[i:])
    unmatched_det.extend(detected[j:])
    tp = len(pairs)
    fp, fn = len(unmatched_det), len(unmatched_ref)
    precision = tp / (tp + fp) if tp + fp else (1.0 if not reference else 0.0)
    recall = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': _r(precision), 'recall': _r(recall),
            'f_measure': _r(f), 'false_positives': unmatched_det, 'misses': unmatched_ref,
            'matched': pairs}


# --------------------------------------------------------------------------- 07.06 audio_lib_eval

_AUDIO_LIB_FIELDS = {'name', 'licence', 'beats', 'silence'}


def _intervals(value, name):
    items = _list(value, name, MAX_EVENTS // 2)
    out = []
    for i, iv in enumerate(items):
        iv = _list(iv, f'{name}[{i}]', 2, min_len=2)
        s, e = _num(iv[0], 0, 1e7, f'{name}[{i}][0]'), _num(iv[1], 0, 1e7, f'{name}[{i}][1]')
        if e < s:
            raise ValueError(f'{name}[{i}] end must be >= start')
        out.append((s, e))
    return sorted(t for iv in out for t in iv)


_EXAMPLE_AUDIO_REF = {'beats': [1.0, 2.0, 3.0, 4.0], 'silence': [[5.0, 6.0]]}
_EXAMPLE_AUDIO_LIBS = [
    {'name': 'audio_lib_A', 'beats': [1.02, 2.5, 3.0], 'silence': [[5.05, 6.3]]},
    {'name': 'audio_lib_B', 'beats': [1.0, 2.01, 2.98, 4.03]},
]


def audio_lib_eval(*, reference=None, libraries=None, beat_tolerance_s=0.07,
                   silence_tolerance_s=0.1, **extra):
    """Score supplied beat times and silence intervals against reference annotations.

    Silence intervals are scored on their boundaries (each start and end is an event).
    Matching is one-to-one within +-tolerance; F = 2PR/(P+R).
    """
    _no_extra(extra)
    ref = _dict(_EXAMPLE_AUDIO_REF if reference is None else reference, 'reference', {'beats', 'silence'})
    if not ref:
        raise ValueError('reference needs at least one of beats / silence')
    libraries = _list(_EXAMPLE_AUDIO_LIBS if libraries is None else libraries, 'libraries', MAX_ITEMS, min_len=1)
    tol = {'beats': _num(beat_tolerance_s, 0, 10, 'beat_tolerance_s', low_open=True),
           'silence': _num(silence_tolerance_s, 0, 10, 'silence_tolerance_s', low_open=True)}
    ref_events = {}
    if 'beats' in ref:
        ref_events['beats'] = _times(ref['beats'], 'reference.beats')
    if 'silence' in ref:
        ref_events['silence'] = _intervals(ref['silence'], 'reference.silence')
    rows = []
    for i, lib in enumerate(libraries):
        lib = _dict(lib, f'libraries[{i}]', _AUDIO_LIB_FIELDS, ('name',))
        name = _str(lib['name'], f'libraries[{i}].name')
        tasks = {}
        for task, events in ref_events.items():
            if lib.get(task) is None:
                tasks[task] = {'status': 'not_measured'}
                continue
            det = (_times(lib[task], f'libraries[{i}].beats') if task == 'beats'
                   else _intervals(lib[task], f'libraries[{i}].silence'))
            m = _match_events(events, det, tol[task])
            m['status'] = 'measured'
            tasks[task] = m
        measured = [t['f_measure'] for t in tasks.values() if t['status'] == 'measured']
        rows.append({'name': name, 'tasks': tasks,
                     'licence': (_licence_info(lib.get('licence'), name)
                                 if lib.get('licence') is not None or name.lower() in KNOWN_LIBRARIES else None),
                     'mean_f_measured': _r(sum(measured) / len(measured)) if measured else None,
                     'all_tasks_measured': len(measured) == len(ref_events)})
    _unique_names(rows, 'libraries')
    best = {}
    for task in ref_events:
        cands = [(r['tasks'][task]['f_measure'], r['name']) for r in rows
                 if r['tasks'][task]['status'] == 'measured']
        best[task] = min(cands, key=lambda c: (-c[0], c[1].lower()))[1] if cands else None
    result = {'tolerances_s': {k: tol[k] for k in ref_events}, 'best_per_task': best,
              'libraries': rows}
    return _pack('audio_lib_eval', result,
                 ['reference annotations are ground truth supplied by the caller',
                  'one-to-one greedy matching on sorted times (optimal for equal 1D windows)',
                  'beat tolerance default +-70 ms (common MIREX-style window); silence boundaries +-100 ms',
                  'precision = 1 when nothing is detected and nothing is expected',
                  'default example data is illustrative'],
                 [f'<= {MAX_EVENTS} events per list, <= {MAX_ITEMS} libraries',
                  'no tempo/phase (continuity) metrics; silence overlap duration is not scored',
                  'does not run any audio library'])


# --------------------------------------------------------------------------- 07.07 cv_lib_eval

_PKG_FIELDS = {'name', 'version', 'licence', 'wheels'}
_COMBO_FIELDS = {'os', 'python', 'arch'}
_EXAMPLE_PKGS = [
    {'name': 'opencv-python', 'version': '4.10.0.84',
     'wheels': [{'os': 'windows', 'python': '3.12', 'arch': 'x86_64'},
                {'os': 'linux', 'python': '3.12', 'arch': 'x86_64'}]},
]
_EXAMPLE_TARGETS = [{'os': 'windows', 'python': '3.12', 'arch': 'x86_64'},
                    {'os': 'linux', 'python': '3.12', 'arch': 'aarch64'},
                    {'os': 'macos', 'python': '3.13', 'arch': 'arm64'}]
_VERSION_RE = re.compile(r'^(\d+)(?:\.(\d+))?')


def _combo(value, name):
    c = _dict(value, name, _COMBO_FIELDS, ('os', 'python', 'arch'))
    return (_str(c['os'], f'{name}.os', 40).lower(), _str(c['python'], f'{name}.python', 20).lower(),
            _str(c['arch'], f'{name}.arch', 40).lower())


def _opencv_licence(version):
    m = _VERSION_RE.match(version or '')
    if not m:
        return None, 'version unknown: OpenCV is Apache-2.0 from 4.5.0, BSD-3-Clause before'
    major, minor = int(m.group(1)), int(m.group(2) or 0)
    if (major, minor) >= (4, 5):
        return 'Apache-2.0', 'OpenCV >= 4.5.0 is Apache-2.0'
    return 'BSD-3-Clause', 'OpenCV < 4.5.0 is BSD-3-Clause'


def cv_lib_eval(*, packages=None, targets=None, **extra):
    """Wheel/binary availability matrix per (os, python, arch) target plus licence triage."""
    _no_extra(extra)
    packages = _list(_EXAMPLE_PKGS if packages is None else packages, 'packages', 50, min_len=1)
    targets = [_combo(t, f'targets[{i}]') for i, t in
               enumerate(_list(_EXAMPLE_TARGETS if targets is None else targets, 'targets', 100, min_len=1))]
    rows, unsupported = [], []
    for i, p in enumerate(packages):
        p = _dict(p, f'packages[{i}]', _PKG_FIELDS, ('name', 'wheels'))
        name = _str(p['name'], f'packages[{i}].name')
        version = _str(p['version'], f'packages[{i}].version', 60) if p.get('version') is not None else None
        wheels = {_combo(w, f'packages[{i}].wheels[{j}]')
                  for j, w in enumerate(_list(p['wheels'], f'packages[{i}].wheels', 500))}
        matrix = []
        for t in targets:
            ok = t in wheels
            matrix.append({'os': t[0], 'python': t[1], 'arch': t[2],
                           'status': 'available' if ok else 'missing'})
            if not ok:
                unsupported.append({'package': name, 'os': t[0], 'python': t[1], 'arch': t[2],
                                    'note': 'no wheel supplied: pip would need a source build or fail'})
        lic_expr = p.get('licence')
        if lic_expr is not None:
            lic_expr = _str(lic_expr, f'packages[{i}].licence', MAX_EXPR)
        notes = []
        if name.lower().startswith('opencv'):
            derived, note = _opencv_licence(version)
            notes.append(note)
            if lic_expr is None and derived:
                lic_expr = derived
            elif lic_expr is not None and derived and lic_expr.strip().lower() != derived.lower():
                notes.append(f'supplied licence {lic_expr!r} differs from {derived!r} expected for this version')
        lic = _licence_info(lic_expr, name if lic_expr is None else None)
        if any('differs' in n for n in notes):
            lic['status'] = 'needs_review'
        lic['notes'] = notes + lic['notes'] + (
            ['opencv-python wheels bundle third-party binaries (e.g. FFmpeg LGPL-2.1, Qt LGPL-3.0 on some platforms): review'
             ] if name.lower().startswith('opencv-') else [])
        rows.append({'name': name, 'version': version, 'matrix': matrix, 'licence': lic,
                     'supported_targets': sum(m['status'] == 'available' for m in matrix)})
    _unique_names(rows, 'packages')
    result = {'targets': [{'os': t[0], 'python': t[1], 'arch': t[2]} for t in targets],
              'packages': rows, 'unsupported': unsupported, 'all_supported': not unsupported}
    return _pack('cv_lib_eval', result,
                 ['wheel availability lists are supplied by the caller (e.g. copied from the package index)',
                  'os/python/arch strings are compared case-insensitively and literally (no alias mapping: x86_64 != amd64)',
                  'abi3 or universal wheels must be listed explicitly for each target they cover',
                  LEGAL_NOTE],
                 ['<= 50 packages, <= 100 targets, <= 500 wheels per package',
                  'does not query PyPI or install anything; manylinux/musllinux glibc levels not modelled'])


# --------------------------------------------------------------------------- 07.09 lockfile

_NAME_RE = re.compile(r'^\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)\s*(\[[^\]]*\])?\s*(.*)$')
_SPEC_RE = re.compile(r'^(===|==|~=|!=|<=|>=|<|>)\s*([^\s,;]+)$')
_HASH_RE = re.compile(r'(?:^|\s)--hash[=\s]+(\S+)')
_HASH_LEN = {'sha256': 64, 'sha384': 96, 'sha512': 128}

_EXAMPLE_LOCK = (
    '# example lock (hashes are dummy placeholders)\n'
    'requests==2.32.3 \\\n'
    '    --hash=sha256:' + 'a' * 64 + '\n'
    'numpy>=1.26\n'
    'pillow==10.4.0\n'
    'Pillow==11.0.0\n'
)
_EXAMPLE_LICENCE_MAP = {'requests': 'Apache-2.0', 'numpy': 'BSD-3-Clause', 'pillow': 'MIT-CMU'}


def _norm(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def lockfile(*, text=None, licences=None, require_hashes=True, **extra):
    """Parse a requirements/lock text and give a reproducibility verdict and licence summary."""
    _no_extra(extra)
    if text is None:
        text = _EXAMPLE_LOCK
        if licences is None:
            licences = _EXAMPLE_LICENCE_MAP
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        raise ValueError(f'text must be a string of at most {MAX_TEXT} characters')
    require_hashes = _bool(require_hashes, 'require_hashes')
    lic_map = {}
    if licences is not None:
        licences = _dict(licences, 'licences')
        if len(licences) > 5000:
            raise ValueError('licences may have at most 5000 entries')
        lic_map = {_norm(_str(k, 'licences key')): v for k, v in licences.items()}
    # join continuation lines
    logical, buf, start = [], '', None
    for no, raw in enumerate(text.splitlines(), 1):
        if start is None:
            start = no
        line = raw.rstrip()
        if line.endswith('\\'):
            buf += line[:-1] + ' '
            continue
        logical.append((start, buf + line))
        buf, start = '', None
        if len(logical) > MAX_LINES:
            raise ValueError(f'text may have at most {MAX_LINES} logical lines')
    if buf:
        logical.append((start, buf))
    reqs, issues, options = [], [], []
    for no, line in logical:
        line = re.sub(r'(^|\s)#.*$', '', line).strip()
        if not line:
            continue
        hashes = _HASH_RE.findall(' ' + line)
        body = _HASH_RE.sub(' ', ' ' + line).strip()
        if body.startswith('-'):
            opt = body.split()[0]
            options.append({'line': no, 'option': opt})
            if opt in ('-e', '--editable'):
                issues.append({'line': no, 'kind': 'editable', 'detail': 'editable install is not reproducible'})
            elif opt in ('-r', '--requirement', '-c', '--constraint'):
                issues.append({'line': no, 'kind': 'include_not_followed',
                               'detail': f'{opt} includes another file which this op cannot read'})
            continue
        req_part, _, marker = body.partition(';')
        marker = ' '.join(marker.split())
        if ' @ ' in req_part or '://' in req_part:
            nm = req_part.split('@')[0].strip()
            issues.append({'line': no, 'kind': 'direct_reference',
                           'detail': f'{nm or req_part}: URL/VCS reference is not a version pin; review'})
            reqs.append({'line': no, 'name': _norm(nm) if nm else req_part, 'raw': body,
                         'pinned': False, 'version': None, 'marker': marker, 'hashes': hashes})
            continue
        m = _NAME_RE.match(req_part)
        if not m:
            issues.append({'line': no, 'kind': 'unparsed', 'detail': f'cannot parse {body[:80]!r}'})
            continue
        name, spec_text = m.group(1), m.group(3).strip()
        specs = []
        bad_spec = False
        for part in [s.strip() for s in spec_text.split(',') if s.strip()]:
            sm = _SPEC_RE.match(part)
            if not sm:
                bad_spec = True
                break
            specs.append((sm.group(1), sm.group(2)))
        if bad_spec:
            issues.append({'line': no, 'kind': 'unparsed', 'detail': f'bad version specifier in {body[:80]!r}'})
            continue
        pinned = (len(specs) == 1 and specs[0][0] in ('==', '===') and '*' not in specs[0][1])
        bad_hashes = []
        for h in hashes:
            algo, _, hexd = h.partition(':')
            if algo not in _HASH_LEN or len(hexd) != _HASH_LEN[algo] or not re.fullmatch(r'[0-9a-fA-F]+', hexd):
                bad_hashes.append(h)
        if bad_hashes:
            issues.append({'line': no, 'kind': 'malformed_hash', 'detail': f'{name}: {len(bad_hashes)} malformed hash(es)'})
        reqs.append({'line': no, 'name': _norm(name), 'raw': body, 'pinned': pinned,
                     'version': specs[0][1] if pinned else None,
                     'specifiers': [op + v for op, v in specs], 'marker': marker,
                     'hashes': hashes})
    unpinned = [r['name'] for r in reqs if not r['pinned']]
    for r in reqs:
        if not r['pinned'] and not any(i['line'] == r['line'] for i in issues):
            issues.append({'line': r['line'], 'kind': 'unpinned',
                           'detail': f'{r["name"]}: needs exactly one ==version pin'})
    groups = {}
    for r in reqs:
        groups.setdefault((r['name'], r['marker']), []).append(r)
    conflicts, duplicates = [], []
    for (name, marker), rs in sorted(groups.items()):
        if len(rs) < 2:
            continue
        versions = sorted({r['version'] or '(unpinned)' for r in rs})
        entry = {'name': name, 'marker': marker, 'versions': versions, 'lines': [r['line'] for r in rs]}
        (conflicts if len(versions) > 1 else duplicates).append(entry)
    for c in conflicts:
        issues.append({'line': c['lines'][1], 'kind': 'conflicting_pins',
                       'detail': f'{c["name"]}: {", ".join(c["versions"])}'})
    for d in duplicates:
        issues.append({'line': d['lines'][1], 'kind': 'duplicate', 'detail': f'{d["name"]} listed twice'})
    missing_hashes = sorted({r['name'] for r in reqs if not r['hashes']})
    any_hashes = any(r['hashes'] for r in reqs)
    fail = []
    if unpinned:
        fail.append('unpinned requirement(s): ' + ', '.join(sorted(set(unpinned))))
    if conflicts:
        fail.append('conflicting pins: ' + ', '.join(c['name'] for c in conflicts))
    if any(i['kind'] in ('editable', 'direct_reference', 'unparsed', 'malformed_hash', 'include_not_followed')
           for i in issues):
        fail.append('unreproducible or unreadable entries (see issues)')
    if missing_hashes and (require_hashes or any_hashes):
        fail.append('missing hashes: ' + ', '.join(missing_hashes)
                    + (' (pip hash-checking mode would refuse a partially hashed file)' if any_hashes else ''))
    if not reqs:
        fail.append('no requirements found')
    verdict = 'reproducible' if not fail else 'not_reproducible'
    lic_rows, counts = {}, {}
    for name in sorted({r['name'] for r in reqs}):
        if name in lic_map:
            info = _licence_info(lic_map[name])
            cls = info['class']
        else:
            info, cls = None, 'not_supplied'
        lic_rows[name] = {'class': cls, 'expression': info['expression'] if info else None,
                          'status': info['status'] if info else 'needs_review'}
        counts[cls] = counts.get(cls, 0) + 1
    result = {'verdict': verdict, 'fail_reasons': fail, 'require_hashes': require_hashes,
              'requirements': reqs, 'issues': sorted(issues, key=lambda i: (i['line'], i['kind'])),
              'options': options, 'conflicts': conflicts, 'duplicates': duplicates,
              'missing_hashes': missing_hashes,
              'licence_summary': {'counts': dict(sorted(counts.items())), 'packages': lic_rows,
                                  'needs_review': sorted(n for n, v in lic_rows.items()
                                                         if v['status'] != 'ok')}}
    return _pack('lockfile', result,
                 ['pip requirements syntax: one requirement per line, "\\" continuations, "#" comments, --hash=algo:hex',
                  'names normalised per PEP 503 (case, "-", "_", "." equivalent)',
                  'pinned = exactly one == (or ===) specifier without wildcard',
                  'same name with different environment markers is allowed (not a conflict)',
                  'licence summary uses the caller-supplied package->licence map only; ' + LEGAL_NOTE],
                 [f'text <= {MAX_TEXT} characters, <= {MAX_LINES} logical lines',
                  'does not resolve transitive dependencies, follow -r/-c includes or contact an index',
                  'poetry.lock / uv.lock / Pipfile.lock formats are not parsed',
                  'hash values are checked for format only, not against real artefacts'])


# --------------------------------------------------------------------------- 07.08 shot_detect_compare

_EXAMPLE_REF_CUTS = [1.0, 2.0, 3.0]
_EXAMPLE_TOOL_CUTS = [{'name': 'detector_A', 'cuts': [1.05, 2.0, 5.0]},
                      {'name': 'detector_B', 'cuts': [1.0, 2.1, 3.0]}]


def shot_detect_compare(*, reference=None, tools=None, tolerance_s=0.2, fps=None, **extra):
    """Precision / recall / F1 of supplied cut timestamps per tool against a reference list."""
    _no_extra(extra)
    reference = _times(_EXAMPLE_REF_CUTS if reference is None else reference, 'reference')
    tools = _list(_EXAMPLE_TOOL_CUTS if tools is None else tools, 'tools', MAX_ITEMS, min_len=1)
    tol = _num(tolerance_s, 0, 10, 'tolerance_s', low_open=True)
    fps_v = None if fps is None else _num(fps, 1, 1000, 'fps')
    rows = []
    for i, t in enumerate(tools):
        t = _dict(t, f'tools[{i}]', {'name', 'cuts', 'licence'}, ('name', 'cuts'))
        name = _str(t['name'], f'tools[{i}].name')
        m = _match_events(reference, _times(t['cuts'], f'tools[{i}].cuts'), tol)
        m['name'] = name
        m['f1'] = m.pop('f_measure')
        if t.get('licence') is not None or name.lower() in KNOWN_LIBRARIES:
            m['licence'] = _licence_info(t.get('licence'), name)
        rows.append(m)
    _unique_names(rows, 'tools')
    ranking = sorted(rows, key=lambda r: (-r['f1'], r['name'].lower()))
    result = {'reference_count': len(reference), 'tolerance_s': tol,
              'tolerance_frames': _r(tol * fps_v, 3) if fps_v else None,
              'best': ranking[0]['name'], 'ranking': [r['name'] for r in ranking], 'tools': rows}
    return _pack('shot_detect_compare', result,
                 ['reference cut list is ground truth supplied by the caller',
                  'a detection within +-tolerance of an unmatched reference cut is a hit; one-to-one matching',
                  'gradual transitions are treated as single timestamps'],
                 [f'<= {MAX_EVENTS} cuts per list, <= {MAX_ITEMS} tools',
                  'no separate scoring for dissolves/fades; does not run any detector'])


# --------------------------------------------------------------------------- 07.10 arabic_shaping_eval

SHAPING_CHECKS = ('joined_letters', 'lam_alef_ligature', 'harakat_placement', 'mixed_digits_order')
_STACK_FIELDS = {'name', 'components', 'licence', 'results', 'notes'}
_EXAMPLE_STACKS = [
    {'name': 'stack_A', 'components': ['harfbuzz', 'fribidi'],
     'results': {'joined_letters': True, 'lam_alef_ligature': True,
                 'harakat_placement': True, 'mixed_digits_order': True}},
    {'name': 'stack_B', 'components': ['pillow', 'libraqm'],
     'results': {'joined_letters': True, 'lam_alef_ligature': False,
                 'harakat_placement': True, 'mixed_digits_order': True}},
    {'name': 'stack_C', 'components': ['pango'],
     'results': {'joined_letters': True, 'lam_alef_ligature': True,
                 'harakat_placement': None, 'mixed_digits_order': True}},
]


def arabic_shaping_eval(*, stacks=None, **extra):
    """A shaping stack passes only if all four RTL checks passed on the supplied samples."""
    _no_extra(extra)
    stacks = _list(_EXAMPLE_STACKS if stacks is None else stacks, 'stacks', MAX_ITEMS, min_len=1)
    rows = []
    for i, s in enumerate(stacks):
        s = _dict(s, f'stacks[{i}]', _STACK_FIELDS, ('name', 'results'))
        name = _str(s['name'], f'stacks[{i}].name')
        comps = [_str(c, f'stacks[{i}].components[{j}]', 80)
                 for j, c in enumerate(_list(s.get('components', []), f'stacks[{i}].components', 20))]
        results = _dict(s['results'], f'stacks[{i}].results', set(SHAPING_CHECKS))
        vals = {c: _opt_bool(results.get(c), f'stacks[{i}].results.{c}') for c in SHAPING_CHECKS}
        failed = [c for c in SHAPING_CHECKS if vals[c] is False]
        untested = [c for c in SHAPING_CHECKS if vals[c] is None]
        if s.get('licence') is not None:
            lic = {'stack': _licence_info(s['licence'])}
        else:
            lic = {c: _licence_info(None, c) for c in comps}
        lic_review = sorted(k for k, v in lic.items() if v['status'] != 'ok')
        rows.append({'name': name, 'components': comps, 'results': vals, 'failed': failed,
                     'untested': untested, 'passed': not failed and not untested,
                     'licences': lic, 'licence_needs_review': lic_review})
    _unique_names(rows, 'stacks')
    result = {'checks': list(SHAPING_CHECKS),
              'passed': [r['name'] for r in rows if r['passed']],
              'failed': [r['name'] for r in rows if not r['passed']],
              'stacks': rows,
              'reference_licences': {k: KNOWN_LIBRARIES[k] for k in
                                     ('harfbuzz', 'pango', 'pillow', 'libraqm', 'fribidi')}}
    return _pack('arabic_shaping_eval', result,
                 ['check results come from the caller rendering real Arabic RTL samples and inspecting them',
                  'all four checks must be true; an untested check counts as not passed',
                  'component licences come from the reference table; ' + LEGAL_NOTE,
                  'default example stacks have illustrative results, not measurements of the named libraries'],
                 [f'<= {MAX_ITEMS} stacks', 'does not shape or render text itself',
                  'font coverage (e.g. missing glyphs) must be part of the supplied results'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'licence_check': licence_check, 'tool_benchmark': tool_benchmark,
    'vector_lib_eval': vector_lib_eval, 'web_anim_eval': web_anim_eval,
    'webgl_eval': webgl_eval, 'audio_lib_eval': audio_lib_eval,
    'cv_lib_eval': cv_lib_eval, 'shot_detect_compare': shot_detect_compare,
    'lockfile': lockfile, 'arabic_shaping_eval': arabic_shaping_eval,
}


def run(op, params=None):
    """Validate and dispatch: run('licence_check', {'expression': 'MIT'}) -> {'op','result','assumptions','limits'}."""
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
