"""Red Rose V29: Arabic shaping for rasterisers that have no text shaper (CairoSVG).

CairoSVG draws one code point at a time with Cairo's toy text API: no
joining, no lam-alef ligatures, no bidi reordering and no ``paint-order``.
Arabic therefore comes out as isolated letters in reversed order with the
outline painted over the fill. This module fixes the SVG *before* it is
rasterised:

* ``shape(text)`` - contextual presentation forms (isolated/final/initial/
  medial) from the joining type of each letter, lam-alef ligatures, tashkeel
  kept with its base, then visual reordering of mixed Arabic/Latin/digit runs
  with a subset of the Unicode Bidirectional Algorithm (W1-W7, N1-N2, I1-I2,
  L1, L2 on grapheme clusters, L4 mirroring). No explicit embeddings.
* ``shape_svg_for_raster(svg)`` - shapes every text node of <text>/<tspan>/
  <textPath>, swaps text-anchor for direction="rtl" (CairoSVG ignores the
  direction), picks an installed font that really has the presentation forms,
  and splits a stroke that should be painted under the fill
  (``paint-order="stroke ..."``) into a separate element under the fill copy.
  It returns a NEW SVG string (callers keep the logical SVG) plus a report
  whose ``warnings`` carry ``arabic_unshaped: ...`` whenever Arabic letters
  would still reach the rasteriser unshaped (fail closed), or
  ``arabic_font_missing_forms: ...`` when the only fonts found lack the forms.

Standard library only (unicodedata, xml.etree, struct). Never shapes twice: a
string that already holds presentation forms is left alone, and a shaped SVG
root carries ``data-rr-shaped="1"``.
"""
from __future__ import annotations

import copy
import functools
import os
import re
import struct
import sys
import unicodedata
from pathlib import Path
import xml.etree.ElementTree as ET

__all__ = ['shape', 'needs_shaping', 'is_shaped', 'shape_svg_for_raster',
           'font_supports_forms', 'font_advance_em', 'resolve_raster_font', 'unshaped_runs',
           'selftest']

# Test hook: when True, shape_svg_for_raster leaves the SVG untouched (but still
# scans it), so callers can prove that unshaped Arabic is reported, never hidden.
_TEST_DISABLE_SHAPING = False

SVG_NS = 'http://www.w3.org/2000/svg'
XLINK_NS = 'http://www.w3.org/1999/xlink'
XML_NS = 'http://www.w3.org/XML/1998/namespace'
SHAPED_MARK = 'data-rr-shaped'
MAX_SVG_CHARS = 20_000_000

# --------------------------------------------------------------------------- tables
# base letter -> (isolated, final, initial, medial); None = form does not exist.
_FORMS = {
    0x0621: (0xFE80, None, None, None),
    0x0622: (0xFE81, 0xFE82, None, None),
    0x0623: (0xFE83, 0xFE84, None, None),
    0x0624: (0xFE85, 0xFE86, None, None),
    0x0625: (0xFE87, 0xFE88, None, None),
    0x0626: (0xFE89, 0xFE8A, 0xFE8B, 0xFE8C),
    0x0627: (0xFE8D, 0xFE8E, None, None),
    0x0628: (0xFE8F, 0xFE90, 0xFE91, 0xFE92),
    0x0629: (0xFE93, 0xFE94, None, None),
    0x062A: (0xFE95, 0xFE96, 0xFE97, 0xFE98),
    0x062B: (0xFE99, 0xFE9A, 0xFE9B, 0xFE9C),
    0x062C: (0xFE9D, 0xFE9E, 0xFE9F, 0xFEA0),
    0x062D: (0xFEA1, 0xFEA2, 0xFEA3, 0xFEA4),
    0x062E: (0xFEA5, 0xFEA6, 0xFEA7, 0xFEA8),
    0x062F: (0xFEA9, 0xFEAA, None, None),
    0x0630: (0xFEAB, 0xFEAC, None, None),
    0x0631: (0xFEAD, 0xFEAE, None, None),
    0x0632: (0xFEAF, 0xFEB0, None, None),
    0x0633: (0xFEB1, 0xFEB2, 0xFEB3, 0xFEB4),
    0x0634: (0xFEB5, 0xFEB6, 0xFEB7, 0xFEB8),
    0x0635: (0xFEB9, 0xFEBA, 0xFEBB, 0xFEBC),
    0x0636: (0xFEBD, 0xFEBE, 0xFEBF, 0xFEC0),
    0x0637: (0xFEC1, 0xFEC2, 0xFEC3, 0xFEC4),
    0x0638: (0xFEC5, 0xFEC6, 0xFEC7, 0xFEC8),
    0x0639: (0xFEC9, 0xFECA, 0xFECB, 0xFECC),
    0x063A: (0xFECD, 0xFECE, 0xFECF, 0xFED0),
    0x0641: (0xFED1, 0xFED2, 0xFED3, 0xFED4),
    0x0642: (0xFED5, 0xFED6, 0xFED7, 0xFED8),
    0x0643: (0xFED9, 0xFEDA, 0xFEDB, 0xFEDC),
    0x0644: (0xFEDD, 0xFEDE, 0xFEDF, 0xFEE0),
    0x0645: (0xFEE1, 0xFEE2, 0xFEE3, 0xFEE4),
    0x0646: (0xFEE5, 0xFEE6, 0xFEE7, 0xFEE8),
    0x0647: (0xFEE9, 0xFEEA, 0xFEEB, 0xFEEC),
    0x0648: (0xFEED, 0xFEEE, None, None),
    0x0649: (0xFEEF, 0xFEF0, None, None),
    0x064A: (0xFEF1, 0xFEF2, 0xFEF3, 0xFEF4),
    # Persian / Urdu letters most often met in Arabic-script titles
    0x0671: (0xFB50, 0xFB51, None, None),
    0x0679: (0xFB66, 0xFB67, 0xFB68, 0xFB69),
    0x067E: (0xFB56, 0xFB57, 0xFB58, 0xFB59),
    0x0686: (0xFB7A, 0xFB7B, 0xFB7C, 0xFB7D),
    0x0688: (0xFB88, 0xFB89, None, None),
    0x0691: (0xFB8C, 0xFB8D, None, None),
    0x0698: (0xFB8A, 0xFB8B, None, None),
    0x06A4: (0xFB6A, 0xFB6B, 0xFB6C, 0xFB6D),
    0x06A9: (0xFB8E, 0xFB8F, 0xFB90, 0xFB91),
    0x06AF: (0xFB92, 0xFB93, 0xFB94, 0xFB95),
    0x06BA: (0xFB9E, 0xFB9F, None, None),
    0x06BE: (0xFBAA, 0xFBAB, 0xFBAC, 0xFBAD),
    0x06C1: (0xFBA6, 0xFBA7, 0xFBA8, 0xFBA9),
    0x06CC: (0xFBFC, 0xFBFD, 0xFBFE, 0xFBFF),
    0x06D2: (0xFBAE, 0xFBAF, None, None),
}
_LAM = 0x0644
_LAM_ALEF = {0x0622: (0xFEF5, 0xFEF6), 0x0623: (0xFEF7, 0xFEF8),
             0x0625: (0xFEF9, 0xFEFA), 0x0627: (0xFEFB, 0xFEFC)}
_ZWJ, _ZWNJ, _TATWEEL = 0x200D, 0x200C, 0x0640
_MIRROR = {'(': ')', ')': '(', '[': ']', ']': '[', '{': '}', '}': '{', '<': '>', '>': '<',
           '«': '»', '»': '«', '‹': '›', '›': '‹',
           '≤': '≥', '≥': '≤', '⁅': '⁆', '⁆': '⁅',
           '⁽': '⁾', '⁾': '⁽', '₍': '₎', '₎': '₍'}
_FORM_CHECK = (0xFE8D, 0xFE8E, 0xFE8F, 0xFE90, 0xFE91, 0xFE92, 0xFEDF, 0xFEE0, 0xFEFB, 0xFEFC)
_GENERIC = {'serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui',
            'ui-sans-serif', 'ui-serif', 'emoji', 'math', 'inherit', 'initial'}
_FALLBACK_FAMILIES = ('Noto Naskh Arabic', 'Noto Sans Arabic', 'Tahoma', 'Arial', 'Segoe UI',
                      'Times New Roman', 'DejaVu Sans', 'Amiri', 'Sakkal Majalla')


def _is_pf(cp):
    return 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF


def _is_arabic_letter(ch):
    cp = ord(ch)
    return ((0x0620 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0x08A0 <= cp <= 0x08FF)
            and unicodedata.category(ch) == 'Lo')


def _joining_type(ch):
    cp = ord(ch)
    forms = _FORMS.get(cp)
    if forms is not None:
        if forms[2] is not None:
            return 'D'
        if forms[1] is not None:
            return 'R'
        return 'U'
    if cp in (_TATWEEL, _ZWJ):
        return 'C'
    if cp == _ZWNJ:
        return 'U'
    if unicodedata.category(ch) in ('Mn', 'Me') or (unicodedata.category(ch) == 'Cf' and cp != _ZWNJ):
        return 'T'
    return 'U'


# --------------------------------------------------------------------------- predicates

def is_shaped(text):
    """True when `text` already holds Arabic presentation forms (already shaped)."""
    return isinstance(text, str) and any(_is_pf(ord(c)) for c in text)


def needs_shaping(text):
    """True when `text` has right-to-left letters that are not shaped yet."""
    if not isinstance(text, str) or not text or is_shaped(text):
        return False
    return any(unicodedata.bidirectional(c) in ('R', 'AL') for c in text)


def unshaped_runs(text):
    """Arabic letters that would reach a rasteriser without a presentation form."""
    if not isinstance(text, str):
        return []
    return sorted({f'U+{ord(c):04X}' for c in text if _is_arabic_letter(c)})


# --------------------------------------------------------------------------- joining

def _join(text):
    chars = list(text)
    jt = [_joining_type(c) for c in chars]
    n = len(chars)
    out, unsupported = [], set()

    def prev_idx(i):
        j = i - 1
        while j >= 0 and jt[j] == 'T':
            j -= 1
        return j

    def next_idx(i):
        j = i + 1
        while j < n and jt[j] == 'T':
            j += 1
        return j

    skip = set()
    for i, ch in enumerate(chars):
        if i in skip:
            continue
        cp = ord(ch)
        forms = _FORMS.get(cp)
        if forms is None:
            if _is_arabic_letter(ch):
                unsupported.add(f'U+{cp:04X}')
            out.append(ch)
            continue
        p, q = prev_idx(i), next_idx(i)
        joins_prev = p >= 0 and jt[p] in ('D', 'C') and jt[i] in ('R', 'D')
        if cp == _LAM and q < n and ord(chars[q]) in _LAM_ALEF:
            iso, fin = _LAM_ALEF[ord(chars[q])]
            out.append(chr(fin if joins_prev else iso))
            out.extend(chars[i + 1:q])          # tashkeel on the lam stays with the ligature
            skip.add(q)
            continue
        joins_next = jt[i] == 'D' and q < n and jt[q] in ('R', 'D', 'C')
        iso, fin, ini, med = forms
        if joins_prev and joins_next and med:
            form = med
        elif joins_prev and fin:
            form = fin
        elif joins_next and ini:
            form = ini
        else:
            form = iso
        out.append(chr(form))
    return ''.join(out), sorted(unsupported)


# --------------------------------------------------------------------------- bidi (subset)

def _base_level(types, direction):
    if direction == 'rtl':
        return 1
    if direction == 'ltr':
        return 0
    for t in types:
        if t == 'L':
            return 0
        if t in ('R', 'AL'):
            return 1
    return 0


def _reorder(text, direction='auto'):
    chars = list(text)
    n = len(chars)
    if not n:
        return text
    orig = [unicodedata.bidirectional(c) or 'L' for c in chars]
    t = list(orig)
    for i, x in enumerate(t):     # explicit controls are not modelled: treat as neutral
        if x in ('LRE', 'RLE', 'LRO', 'RLO', 'PDF', 'LRI', 'RLI', 'FSI', 'PDI', 'BN'):
            t[i] = 'ON'
    para = _base_level(t, direction)
    sos = 'R' if para % 2 else 'L'
    # W1
    for i in range(n):
        if t[i] == 'NSM':
            t[i] = t[i - 1] if i else sos
    # W2
    last = sos
    for i in range(n):
        if t[i] in ('R', 'L', 'AL'):
            last = t[i]
        elif t[i] == 'EN' and last == 'AL':
            t[i] = 'AN'
    # W3
    t = ['R' if x == 'AL' else x for x in t]
    # W4
    for i in range(1, n - 1):
        if t[i] == 'ES' and t[i - 1] == 'EN' and t[i + 1] == 'EN':
            t[i] = 'EN'
        elif t[i] == 'CS' and t[i - 1] == t[i + 1] and t[i - 1] in ('EN', 'AN'):
            t[i] = t[i - 1]
    # W5
    i = 0
    while i < n:
        if t[i] == 'ET':
            j = i
            while j < n and t[j] == 'ET':
                j += 1
            if (i > 0 and t[i - 1] == 'EN') or (j < n and t[j] == 'EN'):
                for k in range(i, j):
                    t[k] = 'EN'
            i = j
        else:
            i += 1
    # W6
    t = ['ON' if x in ('ES', 'ET', 'CS') else x for x in t]
    # W7
    last = sos
    for i in range(n):
        if t[i] in ('L', 'R'):
            last = t[i]
        elif t[i] == 'EN' and last == 'L':
            t[i] = 'L'
    # N1/N2
    neutral = ('B', 'S', 'WS', 'ON')

    def strong(x):
        return 'R' if x in ('R', 'EN', 'AN') else x

    e = sos
    i = 0
    while i < n:
        if t[i] in neutral:
            j = i
            while j < n and t[j] in neutral:
                j += 1
            before = strong(t[i - 1]) if i > 0 else sos
            after = strong(t[j]) if j < n else sos
            val = before if before == after else e
            for k in range(i, j):
                t[k] = val
            i = j
        else:
            i += 1
    # I1/I2
    levels = []
    for x in t:
        if para % 2 == 0:
            levels.append(para + (1 if x == 'R' else 2 if x in ('AN', 'EN') else 0))
        else:
            levels.append(para + (1 if x in ('L', 'EN', 'AN') else 0))
    # L1: trailing whitespace and segment/paragraph separators go back to the paragraph level
    j = n - 1
    while j >= 0 and orig[j] in ('WS', 'S', 'B', 'BN', 'LRE', 'RLE', 'LRO', 'RLO', 'PDF',
                                 'LRI', 'RLI', 'FSI', 'PDI'):
        levels[j] = para
        j -= 1
    for i in range(n):
        if orig[i] in ('S', 'B'):
            levels[i] = para
            k = i - 1
            while k >= 0 and orig[k] == 'WS':
                levels[k] = para
                k -= 1
    # clusters: a base plus its combining marks move together
    clusters = []
    for i, ch in enumerate(chars):
        if clusters and unicodedata.category(ch) in ('Mn', 'Me'):
            clusters[-1][1].append(i)
        else:
            clusters.append([levels[i], [i]])
    # L2
    hi = max(c[0] for c in clusters)
    lo_odd = min((c[0] for c in clusters if c[0] % 2), default=None)
    if lo_odd is not None:
        for lev in range(hi, lo_odd - 1, -1):
            k = 0
            while k < len(clusters):
                if clusters[k][0] >= lev:
                    m = k
                    while m < len(clusters) and clusters[m][0] >= lev:
                        m += 1
                    clusters[k:m] = clusters[k:m][::-1]
                    k = m
                else:
                    k += 1
    out = []
    for lev, idxs in clusters:
        for i in idxs:
            ch = chars[i]
            if levels[i] % 2 and unicodedata.mirrored(ch):
                ch = _MIRROR.get(ch, ch)
            out.append(ch)
    return ''.join(out)


# --------------------------------------------------------------------------- public shaping

def shape(text, direction='auto'):
    """Shape logical `text` for a rasteriser without a shaper.

    direction: 'auto' (first strong letter), 'rtl' or 'ltr' paragraph direction.
    Returns {'visual': str (presentation forms, left-to-right display order),
    'changed': bool, 'unsupported': ['U+XXXX', ...]}. Already shaped text is
    returned unchanged (never shaped twice).
    """
    if not isinstance(text, str):
        raise ValueError('text must be a string')
    if direction not in ('auto', 'rtl', 'ltr'):
        raise ValueError("direction must be 'auto', 'rtl' or 'ltr'")
    if not text or is_shaped(text) or not needs_shaping(text):
        return {'visual': text, 'changed': False, 'unsupported': []}
    logical = unicodedata.normalize('NFC', text)
    joined, unsupported = _join(logical)
    visual = _reorder(joined, direction)
    return {'visual': visual, 'changed': visual != text, 'unsupported': unsupported}


# --------------------------------------------------------------------------- fonts

def _read_tables(data, offset=0):
    if len(data) < offset + 12:
        return None
    num = struct.unpack_from('>H', data, offset + 4)[0]
    tables = {}
    for k in range(num):
        rec = offset + 12 + 16 * k
        if rec + 16 > len(data):
            return None
        tag, _, off, length = struct.unpack_from('>4sIII', data, rec)
        tables[tag] = (off, length)
    return tables


def _cmap_has(data, tables, cps):
    found = _cmap_lookup(data, tables, cps)
    return None if found is None else set(found)


def _cmap_lookup(data, tables, cps):
    """{code point: glyph id} for the code points the font maps (None if no cmap)."""
    cps = list(cps)
    if b'cmap' not in tables:
        return None
    base = tables[b'cmap'][0]
    try:
        _, count = struct.unpack_from('>HH', data, base)
        subs = []
        for k in range(count):
            pid, eid, off = struct.unpack_from('>HHI', data, base + 4 + 8 * k)
            fmt = struct.unpack_from('>H', data, base + off)[0]
            subs.append((pid, eid, fmt, base + off))
        best = None
        for pref in ((3, 10, 12), (0, 4, 12), (0, 6, 12), (3, 1, 4), (0, 3, 4), (0, 1, 4)):
            for s in subs:
                if s[0] == pref[0] and s[1] == pref[1] and s[2] == pref[2]:
                    best = s
                    break
            if best:
                break
        if best is None:
            best = next((s for s in subs if s[2] in (4, 12)), None)
        if best is None:
            return None
        fmt, pos = best[2], best[3]
        found = {}
        if fmt == 12:
            ngroups = struct.unpack_from('>I', data, pos + 12)[0]
            for g in range(ngroups):
                a, b, g0 = struct.unpack_from('>III', data, pos + 16 + 12 * g)
                for cp in cps:
                    if a <= cp <= b and g0 + cp - a:
                        found[cp] = g0 + cp - a
        else:
            segx2 = struct.unpack_from('>H', data, pos + 6)[0]
            seg = segx2 // 2
            ends = struct.unpack_from(f'>{seg}H', data, pos + 14)
            starts = struct.unpack_from(f'>{seg}H', data, pos + 16 + segx2)
            deltas = struct.unpack_from(f'>{seg}h', data, pos + 16 + 2 * segx2)
            ro_pos = pos + 16 + 3 * segx2
            ranges = struct.unpack_from(f'>{seg}H', data, ro_pos)
            for cp in cps:
                for k in range(seg):
                    if starts[k] <= cp <= ends[k]:
                        if ranges[k] == 0:
                            gid = (cp + deltas[k]) & 0xFFFF
                        else:
                            addr = ro_pos + 2 * k + ranges[k] + 2 * (cp - starts[k])
                            gid = struct.unpack_from('>H', data, addr)[0]
                            if gid:
                                gid = (gid + deltas[k]) & 0xFFFF
                        if gid:
                            found[cp] = gid
                        break
        return found
    except (struct.error, IndexError):
        return None


def font_advance_em(font_path, text):
    """Advance width of `text` in em, read from the font's cmap + hmtx (no kerning).

    Shape first (shape(text)['visual']) to measure what a rasteriser draws.
    Returns None when the font cannot be read; unmapped characters count 0.5 em."""
    try:
        data = Path(font_path).read_bytes()
    except (OSError, TypeError, ValueError):
        return None
    faces = _faces(data)
    if not faces or not isinstance(text, str):
        return None
    tables = _read_tables(data, faces[0])
    if not tables or not all(t in tables for t in (b'head', b'hhea', b'hmtx')):
        return None
    try:
        upem = struct.unpack_from('>H', data, tables[b'head'][0] + 18)[0] or 1000
        nh = struct.unpack_from('>H', data, tables[b'hhea'][0] + 34)[0]
        gids = _cmap_lookup(data, tables, {ord(c) for c in text}) or {}
        hm = tables[b'hmtx'][0]
        total = 0.0
        for c in text:
            gid = gids.get(ord(c))
            if gid is None:
                total += 0.0 if unicodedata.category(c) in ('Mn', 'Me', 'Cf') else 0.5
                continue
            idx = min(gid, nh - 1)
            total += struct.unpack_from('>H', data, hm + 4 * idx)[0] / upem
        return round(total, 4)
    except struct.error:
        return None


def _faces(data):
    if data[:4] == b'ttcf':
        try:
            num = struct.unpack_from('>I', data, 8)[0]
            return list(struct.unpack_from(f'>{min(num, 64)}I', data, 12))
        except struct.error:
            return []
    if data[:4] in (b'\x00\x01\x00\x00', b'OTTO', b'true'):
        return [0]
    return []


def font_supports_forms(font_path):
    """True/False: the font's cmap maps the Arabic presentation forms; None if unreadable."""
    try:
        path = Path(font_path)
        if not path.is_file() or path.stat().st_size > 80_000_000:
            return None
        data = path.read_bytes()
    except (OSError, TypeError, ValueError):
        return None
    result = None
    for off in _faces(data):
        tables = _read_tables(data, off)
        if not tables:
            continue
        found = _cmap_has(data, tables, _FORM_CHECK)
        if found is None:
            continue
        if len(found) == len(_FORM_CHECK):
            return True
        result = False
    return result


def _family_names(data, off):
    tables = _read_tables(data, off)
    if not tables or b'name' not in tables:
        return set()
    base = tables[b'name'][0]
    names = set()
    try:
        _, count, string_off = struct.unpack_from('>HHH', data, base)
        for k in range(count):
            pid, eid, lid, nid, length, noff = struct.unpack_from('>HHHHHH', data, base + 6 + 12 * k)
            if nid not in (1, 16):
                continue
            raw = data[base + string_off + noff: base + string_off + noff + length]
            if pid == 3 or pid == 0:
                name = raw.decode('utf-16-be', 'ignore')
            elif pid == 1 and eid == 0:
                name = raw.decode('latin-1', 'ignore')
            else:
                continue
            name = name.strip()
            if name:
                names.add(name.lower())
    except struct.error:
        pass
    return names


def _font_dirs():
    dirs = []
    windir = os.environ.get('WINDIR') or os.environ.get('SystemRoot')
    if windir:
        dirs.append(Path(windir) / 'Fonts')
    local = os.environ.get('LOCALAPPDATA')
    if local:
        dirs.append(Path(local) / 'Microsoft' / 'Windows' / 'Fonts')
    if sys.platform == 'darwin':
        dirs += [Path('/System/Library/Fonts'), Path('/Library/Fonts'), Path.home() / 'Library' / 'Fonts']
    else:
        dirs += [Path('/usr/share/fonts'), Path('/usr/local/share/fonts'), Path.home() / '.fonts',
                 Path.home() / '.local' / 'share' / 'fonts']
    return [d for d in dirs if d.is_dir()]


@functools.lru_cache(maxsize=1)
def _font_index():
    """family (lower case) -> sorted font file paths, from installed font folders."""
    index = {}
    seen = 0
    for d in _font_dirs():
        try:
            walker = os.walk(d)
            for root, _, files in walker:
                for fn in files:
                    if not fn.lower().endswith(('.ttf', '.otf', '.ttc')):
                        continue
                    seen += 1
                    if seen > 4000:
                        break
                    p = Path(root) / fn
                    try:
                        with p.open('rb') as fh:
                            head = fh.read(4)
                            if head == b'ttcf' or p.stat().st_size <= 40_000_000:
                                fh.seek(0)
                                data = fh.read()
                            else:
                                continue
                    except OSError:
                        continue
                    for off in _faces(data):
                        for name in _family_names(data, off):
                            index.setdefault(name, []).append(str(p))
        except OSError:
            continue
    return {k: sorted(set(v)) for k, v in index.items()}


@functools.lru_cache(maxsize=256)
def _family_forms(family):
    paths = _font_index().get(family.lower())
    if not paths:
        return None
    verdicts = [font_supports_forms(p) for p in paths[:6]]
    if any(v is True for v in verdicts):
        return True
    if any(v is False for v in verdicts):
        return False
    return None


def _families(value):
    out = []
    for part in (value or '').split(','):
        name = part.strip().strip('"\'').strip()
        if name:
            out.append(name)
    return out


@functools.lru_cache(maxsize=256)
def _pick_family(font_family):
    """Return (family_to_use or None, status, detail) for Arabic text."""
    fams = _families(font_family)
    lacking = []
    for fam in fams:
        if fam.lower() in _GENERIC:
            continue
        verdict = _family_forms(fam)
        if verdict is True:
            return fam, 'ok', fam
        if verdict is False:
            lacking.append(fam)
    for fam in _FALLBACK_FAMILIES:
        if _family_forms(fam) is True:
            return fam, ('fallback_after_missing_forms' if lacking else 'fallback'), fam
    if lacking:
        return None, 'missing_forms', ', '.join(lacking)
    return None, 'unverified', font_family or 'default'


def resolve_raster_font(font_family):
    """Which installed family shape_svg_for_raster will draw Arabic with.

    Returns {'family': str|None, 'status': 'ok'|'fallback'|'fallback_after_missing_forms'|
    'missing_forms'|'unverified', 'paths': [font files of that family]} - layout code can
    measure words with font_advance_em(path, shape(word)['visual'])."""
    fam, status, _ = _pick_family(font_family or '')
    paths = _font_index().get(fam.lower(), []) if fam else []
    return {'family': fam, 'status': status, 'paths': list(paths)}


# --------------------------------------------------------------------------- SVG helpers

def _local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _style_map(el):
    out = {}
    for item in (el.get('style') or '').split(';'):
        if ':' in item:
            k, v = item.split(':', 1)
            out[k.strip().lower()] = v.strip()
    return out


def _prop(el, name):
    st = _style_map(el)
    if name in st:
        return st[name]
    return el.get(name)


def _set_prop(el, name, value):
    st = el.get('style')
    if st is not None:
        items = [i for i in st.split(';') if i.strip() and i.split(':', 1)[0].strip().lower() != name]
        if items:
            el.set('style', ';'.join(items))
        else:
            del el.attrib['style']
    if value is None:
        el.attrib.pop(name, None)
    else:
        el.set(name, value)


def _has_own(el, name):
    return name in _style_map(el) or name in el.attrib


def _stroke_first(paint_order):
    if not paint_order:
        return False
    tokens = paint_order.split()
    if 'stroke' not in tokens or tokens == ['normal']:
        return False
    if 'fill' not in tokens:      # unlisted fill is painted after the listed ones
        return True
    return tokens.index('stroke') < tokens.index('fill')


_TEXT_TAGS = ('text', 'tspan', 'textPath')
_INHERITED = ('direction', 'text-anchor', 'stroke', 'paint-order', 'font-family')


def _esc_text(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _esc_attr(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('"', '&quot;')
            .replace('\n', '&#10;').replace('\r', '&#13;').replace('\t', '&#9;'))


def _serialize(root):
    prefixes = {SVG_NS: '', XLINK_NS: 'xlink', XML_NS: 'xml'}
    extra = {}

    def qname(tag):
        if tag.startswith('{'):
            ns, local = tag[1:].split('}', 1)
            if ns not in prefixes:
                extra[ns] = f'ns{len(extra)}'
                prefixes[ns] = extra[ns]
            p = prefixes[ns]
            return f'{p}:{local}' if p else local
        return tag

    for el in root.iter():       # collect namespaces first
        if isinstance(el.tag, str):
            qname(el.tag)
            for k in el.attrib:
                qname(k)
    parts = []

    def walk(el, is_root):
        if not isinstance(el.tag, str):     # comments / PIs are dropped
            if el.tail:
                parts.append(_esc_text(el.tail))
            return
        name = qname(el.tag)
        attrs = []
        if is_root:
            if root.tag.startswith('{' + SVG_NS + '}'):
                attrs.append(f'xmlns="{SVG_NS}"')
            attrs.append(f'xmlns:xlink="{XLINK_NS}"')
            for ns, p in extra.items():
                attrs.append(f'xmlns:{p}="{_esc_attr(ns)}"')
        for k, v in el.attrib.items():
            attrs.append(f'{qname(k)}="{_esc_attr(v)}"')
        parts.append('<' + name + (' ' + ' '.join(attrs) if attrs else ''))
        if el.text or len(el):
            parts.append('>')
            if el.text:
                parts.append(_esc_text(el.text))
            for child in el:
                walk(child, False)
            parts.append(f'</{name}>')
        else:
            parts.append('/>')
        if el.tail and not is_root:
            parts.append(_esc_text(el.tail))

    walk(root, True)
    return ''.join(parts)


_TEXT_RE = re.compile(r'<(?:\w+:)?(text|tspan|textPath)\b[^>]*>(.*?)</(?:\w+:)?\1\s*>', re.S)


def _regex_scan(svg):
    bad = []
    for m in _TEXT_RE.finditer(svg):
        body = re.sub(r'<[^>]+>', '', m.group(2))
        if unshaped_runs(body):
            bad.append(body.strip()[:40])
    return bad


def _scan_tree(root):
    bad = []
    for el in root.iter():
        if _local(el.tag) not in _TEXT_TAGS:
            continue
        for s in [el.text] + [c.tail for c in el]:
            if s and unshaped_runs(s):
                bad.append(' '.join(s.split())[:40])
    return bad


def _report(**kw):
    rep = {'nodes_shaped': 0, 'stroke_split': 0, 'anchor_swapped': 0, 'fonts': {},
           'unsupported': [], 'already_shaped': False, 'parsed': True, 'warnings': []}
    rep.update(kw)
    return rep


def shape_svg_for_raster(svg_text):
    """Return (svg_for_raster, report) - see the module docstring.

    report: {nodes_shaped:int, stroke_split:int, anchor_swapped:int,
    fonts:{family: status}, unsupported:[...], already_shaped:bool, parsed:bool,
    warnings:['arabic_unshaped: ...' | 'arabic_font_missing_forms: ...']}.
    The input string is never modified; the caller keeps the logical SVG.
    """
    if not isinstance(svg_text, str):
        raise ValueError('svg_text must be a string')
    if len(svg_text) > MAX_SVG_CHARS:
        raise ValueError(f'svg_text must be at most {MAX_SVG_CHARS} characters')
    has_arabic = any(_is_arabic_letter(c) for c in svg_text)
    if not has_arabic and not needs_shaping(svg_text) and 'paint-order' not in svg_text:
        return svg_text, _report()
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        bad = _regex_scan(svg_text)
        warn = [f'arabic_unshaped: SVG could not be parsed for shaping ({exc}); text: {b}' for b in bad[:5]]
        return svg_text, _report(parsed=False, warnings=warn)
    if root.get(SHAPED_MARK) == '1' or _TEST_DISABLE_SHAPING:
        bad = _scan_tree(root)
        warn = [f'arabic_unshaped: {b}' for b in bad[:8]]
        return svg_text, _report(already_shaped=root.get(SHAPED_MARK) == '1', warnings=warn)

    rep = _report()
    unsupported = set()
    font_warn = []
    parent = {c: p for p in root.iter() for c in p}
    splits = []

    def visit(el, ctx):
        local = _local(el.tag)
        ctx = dict(ctx)
        for name in _INHERITED:
            v = _prop(el, name)
            if v is not None and v != 'inherit':
                ctx[name] = v.strip()
        if local in _TEXT_TAGS:
            direction = ctx.get('direction', 'ltr')
            base = 'rtl' if direction == 'rtl' else 'ltr'
            segments = [('text', el)] + [('tail', c) for c in el]
            arabic_here = False
            for kind, node in segments:
                s = node.text if kind == 'text' else node.tail
                if not s:
                    continue
                if any(_is_arabic_letter(c) for c in s):
                    arabic_here = True
                res = shape(s, base)
                unsupported.update(res['unsupported'])
                if res['changed']:
                    rep['nodes_shaped'] += 1
                    if kind == 'text':
                        node.text = res['visual']
                    else:
                        node.tail = res['visual']
            if direction == 'rtl':
                if local == 'text' or _has_own(el, 'text-anchor'):
                    anchor = ctx.get('text-anchor', 'start')
                    swapped = {'start': 'end', 'end': 'start'}.get(anchor, anchor)
                    _set_prop(el, 'text-anchor', swapped)
                    if swapped != anchor:
                        rep['anchor_swapped'] += 1
                    ctx['text-anchor'] = swapped
                if local == 'text' or _has_own(el, 'direction'):
                    _set_prop(el, 'direction', 'ltr')
                # ctx keeps the logical 'rtl' so nested tspans shape with the right base
            if arabic_here:
                fam, status, detail = _pick_family(ctx.get('font-family', ''))
                rep['fonts'][ctx.get('font-family', 'default')] = status
                if fam is not None:
                    _set_prop(el, 'font-family', fam if ' ' not in fam else f"'{fam}'")
                    ctx['font-family'] = fam
                elif status == 'missing_forms':
                    font_warn.append(f'arabic_font_missing_forms: {detail}')
            if local == 'text' and _stroke_first(ctx.get('paint-order')) \
                    and ctx.get('stroke', 'none') not in ('none', '', 'transparent'):
                splits.append(el)
        for child in list(el):
            if isinstance(child.tag, str):
                visit(child, ctx)

    visit(root, {})
    for el in splits:
        p = parent.get(el)
        if p is None:
            continue
        stroke_el = copy.deepcopy(el)
        for node in stroke_el.iter():
            if node is stroke_el or _has_own(node, 'fill'):
                _set_prop(node, 'fill', 'none')
            if _has_own(node, 'paint-order'):
                _set_prop(node, 'paint-order', None)
            node.attrib.pop('id', None)
        _set_prop(stroke_el, 'paint-order', None)
        for node in el.iter():
            if node is el or _has_own(node, 'stroke'):
                _set_prop(node, 'stroke', 'none')
            if _has_own(node, 'paint-order'):
                _set_prop(node, 'paint-order', None)
        idx = list(p).index(el)
        stroke_el.tail = None
        p.insert(idx, stroke_el)
        rep['stroke_split'] += 1
    root.set(SHAPED_MARK, '1')
    bad = _scan_tree(root)
    warnings = [f'arabic_unshaped: {b}' for b in bad[:8]]
    warnings += sorted(set(font_warn))
    rep['unsupported'] = sorted(unsupported)
    rep['warnings'] = warnings
    return _serialize(root), rep


def summarize(reports, max_warnings=12):
    """Merge several shape_svg_for_raster reports (e.g. one per video frame).

    Returns {'applied', 'nodes_shaped', 'stroke_split', 'fonts', 'warnings', 'ok'};
    ok is False whenever any report carried a warning (fail closed)."""
    warnings = []
    fonts = {}
    nodes = split = 0
    applied = False
    for rep in reports or []:
        for w in rep.get('warnings', []):
            if w not in warnings and len(warnings) < max_warnings:
                warnings.append(w)
        nodes += rep.get('nodes_shaped', 0)
        split += rep.get('stroke_split', 0)
        fonts.update(rep.get('fonts', {}))
        applied = applied or bool(rep.get('already_shaped'))
    any_warn = any(rep.get('warnings') for rep in reports or [])
    return {'applied': bool(applied or nodes or split), 'nodes_shaped': nodes,
            'stroke_split': split, 'fonts': fonts, 'warnings': warnings, 'ok': not any_warn}


class RasterShaper:
    """Collect shaping reports across many frames while keeping memory bounded."""

    def __init__(self, keep=6):
        self.keep = keep
        self.reports = []
        self.frames = 0

    def __call__(self, svg):
        shaped, rep = shape_svg_for_raster(svg)
        self.frames += 1
        if rep['warnings'] or ((rep['nodes_shaped'] or rep['stroke_split'])
                               and len(self.reports) < self.keep):
            if len(self.reports) < 200:
                self.reports.append(rep)
        return shaped

    def summary(self):
        out = summarize(self.reports)
        out['frames_checked'] = self.frames
        return out


# --------------------------------------------------------------------------- selftest

_GOLDEN = {
    # 'الوردة الحمراء'
    'الوردة الحمراء':
        'ﺀﺍﺮﻤﺤﻟﺍ ﺓﺩﺭﻮﻟﺍ',
    'سلام': 'ﻡﻼﺳ',                 # سلام (lam-alef)
    'لا': 'ﻻ',                                          # لا
    'مَرْحَبًا':          # مَرْحَبًا (tashkeel)
        'ﺎﺒًﺣَﺮْﻣَ',
    'عرض 50%': '%50 ﺽﺮﻋ',                # عرض 50%
    'مرحبا Red': 'Red ﺎﺒﺣﺮﻣ',  # مرحبا Red
    'Red Rose 2026': 'Red Rose 2026',
}


def selftest():
    """Golden shaping cases (pure Python). Returns {'status': 'pass'|'fail', 'reason'}."""
    failed = []
    for logical, visual in _GOLDEN.items():
        got = shape(logical)['visual']
        if got != visual:
            failed.append(f'{logical!r}: got {got.encode("unicode_escape").decode()}')
        if shape(got)['visual'] != got:
            failed.append(f'{logical!r}: shaping twice changed the text')
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><g stroke="#000" '
           'paint-order="stroke fill"><text direction="rtl" text-anchor="middle">لا</text></g></svg>')
    out, rep = shape_svg_for_raster(svg)
    if rep['warnings'] or rep['stroke_split'] != 1 or 'ﻻ' not in out:
        failed.append(f'svg: {rep}')
    if shape_svg_for_raster(out)[0] != out:
        failed.append('svg: shaping an already shaped SVG changed it')
    if failed:
        return {'status': 'fail', 'reason': '; '.join(failed)[:2000]}
    return {'status': 'pass', 'reason': f'{len(_GOLDEN)} golden strings + 1 SVG case'}
