"""Red Rose V27: native kinetic typography and captions (Arabic-first).

Pure standard-library Python (math, unicodedata, re, html, json). No file I/O,
no subprocess, no network, no printing. Deterministic: the same inputs always
give the same SVG fragment / JSON data (glitch and hand-held jitter use an
internal seeded hash, not a global random state).

Owner rules enforced here:
- Arabic letters change shape by position, so Arabic words are NEVER split into
  per-letter <tspan>/<text> elements; only whole words or phrases animate.
  Latin words may reveal letter by letter (word_typewriter only, by showing a
  prefix of the word, still in one element).
- Burned text is only the caller's text (the speaker's exact words or trusted
  lyrics). Nothing is invented, translated or completed. An unclear word given
  as None or '' stays empty (it keeps its time slot but renders nothing).
- Arabic lines use direction="rtl" + unicode-bidi="embed"; strings are never
  reversed. Mixed Arabic/English lines keep the right order: whole-line
  elements leave ordering to the renderer's bidi algorithm; per-word animated
  layouts place words with a word-level implementation of the Unicode bidi
  levels (rules W2/W7/N1/N2/I1/I2/L2) and each word keeps its own direction.
- Video text: font size >= 3.5% of frame height for body text, and WCAG
  contrast >= 4.5 between the text and its plate (worst case over black and
  white footage when the plate is translucent) or its outline stroke.

Glyph shaping (Arabic joining, lam-alef ligatures, harakat placement) is NOT
done here: it is done by the SVG renderer (HarfBuzz / RAQM / browser). Widths
used for layout are estimates from per-character advance classes, not real
font metrics.
"""
from __future__ import annotations

import functools
import html
import inspect
import json
import math
import re
import unicodedata

MAX_PARAMS = 32
MAX_TEXT = 2000
MAX_WORDS = 400
MAX_TIMED = 5000
MAX_SRT_CHARS = 1_000_000
MAX_SRT_CUES = 20000

TITLE_SAFE = 0.90
ACTION_SAFE = 0.93
MIN_BODY_FRAC = 0.035          # body/caption text >= 3.5 % of frame height
MIN_STROKE_FRAC = 0.04         # an outline counts as a contrast surface if >= 4 % of font size
MIN_CONTRAST = 4.5             # WCAG AA
FONT_STACK = "'Noto Naskh Arabic','Noto Sans Arabic','Tahoma','Arial',sans-serif"
SHAPING_NOTE = ('glyph shaping (Arabic joining, lam-alef, harakat) is done by the renderer '
                '(HarfBuzz/RAQM/browser); this module only emits whole words with direction attributes')

EXAMPLE_AR = 'الوردة الحمراء تتفتّح مع أول ضوء'

_EXAMPLE_TIMED = [
    {'word': 'الوردة', 'start': 0.00, 'end': 0.42},
    {'word': 'الحمراء', 'start': 0.42, 'end': 0.95},
    {'word': 'تتفتّح', 'start': 1.00, 'end': 1.50},
    {'word': None, 'start': 1.50, 'end': 1.80},
    {'word': 'مع', 'start': 1.85, 'end': 2.00},
    {'word': 'أول', 'start': 2.00, 'end': 2.30},
    {'word': 'ضوء', 'start': 2.30, 'end': 2.80},
    {'word': 'Red', 'start': 3.10, 'end': 3.40},
    {'word': 'Rose', 'start': 3.40, 'end': 3.90},
    {'word': 'Studio', 'start': 3.90, 'end': 4.50},
]

STYLES = {
    'word_typewriter': 'كلمة كلمة زي الآلة الكاتبة؛ الكلمة العربية تظهر كاملة، واللاتيني بس ممكن حرف حرف',
    'fade_up': 'كل كلمة تظهر بشفافية وهي طالعة لفوق بنعومة',
    'slide_in': 'الكلمات تدخل من جهة بداية القراءة (من اليمين للعربي)',
    'pop_scale': 'الكلمة تكبر بنطّة صغيرة زيادة وترجع لحجمها',
    'mask_reveal': 'قناع مستطيل بيكشف النص في اتجاه القراءة',
    'blur_in': 'الكلمة تبدأ مغبّشة وتوضح تدريجيًا',
    'stagger_words': 'ظهور متتابع سريع بتكبير خفيف وشفافية',
    'highlight_sweep': 'شريط تظليل بيمسح السطر في اتجاه القراءة ولون الكلمة يتقلب للتباين',
    'underline_draw': 'خط تحت السطر بيترسم من بداية القراءة بعد ظهور الكلمات',
    'counter_numbers': 'الأرقام بتعدّ من الصفر لقيمتها بأرقام عربية أو لاتينية',
    'held_frames': 'إحساس الرسم باليد: وقفات ثابتة كل فريمين مع رعشة خفيفة بذرة ثابتة',
    'bounce_words': 'الكلمات بتقع من فوق وتنطّ لحد ما تستقر',
    'split_lines': 'كل سطر يطلع من ورا حافة مخفية سطر بعد سطر',
    'glitch_words': 'تشويش رقمي ببذرة ثابتة وبعدين الكلمة تثبت',
    'drift_zoom': 'النص كله بيقرّب ببطء مع ظهور ناعم',
}

PRESETS = {
    'social_bold': {'size_frac': 0.052, 'fill': '#FFFFFF', 'stroke': '#000000', 'stroke_frac': 0.12,
                    'plate': None, 'plate_opacity': 0.0, 'highlight': '#FFD400', 'weight': '800',
                    'position': 'lower', 'line_height': 1.32, 'max_chars': 24,
                    'desc_ar': 'خط عريض أبيض بحدود سودا تقيلة وتظليل أصفر للسوشيال'},
    'cinema_subtle': {'size_frac': 0.038, 'fill': '#F5F1E8', 'stroke': '#101010', 'stroke_frac': 0.06,
                      'plate': None, 'plate_opacity': 0.0, 'highlight': '#F5C97A', 'weight': '500',
                      'position': 'lower', 'line_height': 1.4, 'max_chars': 42,
                      'desc_ar': 'ترجمة سينمائية هادية بحجم أصغر وحدود رفيعة'},
    'punchy': {'size_frac': 0.06, 'fill': '#FFFFFF', 'stroke': None, 'stroke_frac': 0.0,
               'plate': '#111111', 'plate_opacity': 0.92, 'highlight': '#FFD400', 'weight': '900',
               'position': 'center', 'line_height': 1.3, 'max_chars': 18,
               'desc_ar': 'كلمات قليلة كبيرة على لوح غامق في النص، للإيقاع السريع'},
}

# ui margins are fractions of the frame reserved by app overlays (approximate, check the current app)
PLATFORMS = {
    'reels': {'width': 1080, 'height': 1920, 'fps': 30,
              'ui': {'top': 0.13, 'right': 0.12, 'bottom': 0.22, 'left': 0.05}},
    'shorts': {'width': 1080, 'height': 1920, 'fps': 30,
               'ui': {'top': 0.12, 'right': 0.12, 'bottom': 0.20, 'left': 0.05}},
    'tiktok': {'width': 1080, 'height': 1920, 'fps': 30,
               'ui': {'top': 0.10, 'right': 0.14, 'bottom': 0.25, 'left': 0.06}},
    'youtube': {'width': 1920, 'height': 1080, 'fps': 30,
                'ui': {'top': 0.0, 'right': 0.0, 'bottom': 0.0, 'left': 0.0}},
    'square': {'width': 1080, 'height': 1080, 'fps': 30,
               'ui': {'top': 0.0, 'right': 0.0, 'bottom': 0.0, 'left': 0.0}},
    'feed': {'width': 1080, 'height': 1350, 'fps': 30,
             'ui': {'top': 0.0, 'right': 0.0, 'bottom': 0.0, 'left': 0.0}},
}

_BIDI_CONTROLS = {'‎', '‏', '‪', '‫', '‬', '‭', '‮',
                  '⁦', '⁧', '⁨', '⁩', '؜'}

_WEAK_WORDS = {
    'و', 'في', 'من', 'على', 'إلى', 'الى', 'عن', 'مع', 'أو', 'او', 'ثم', 'يا', 'لا', 'ما', 'أن', 'ان',
    'إن', 'قد', 'لم', 'لن', 'بين', 'كل', 'هذا', 'هذه', 'التي', 'الذي', 'اللي', 'ده', 'دي',
    'a', 'an', 'the', 'of', 'to', 'and', 'or', 'in', 'on', 'at', 'for', 'with', 'by', 'but', 'is',
}

_DIGIT_RE = re.compile('[0-9٠-٩۰-۹]+(?:[.٫][0-9٠-٩۰-۹]+)?')
_SRT_TIME_RE = re.compile(
    r'^\s*(\d{1,3}):(\d{1,2}):(\d{1,2})[,.](\d{1,3})\s*-->\s*(\d{1,3}):(\d{1,2}):(\d{1,2})[,.](\d{1,3})')
_ID_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,31}$')
_COLOR_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
_M64 = 0xFFFFFFFFFFFFFFFF


# --------------------------------------------------------------------------- validation

def _no_extra(extra, allowed=None):
    if extra:
        msg = 'unknown parameter(s): ' + ', '.join(sorted(map(str, extra)))
        if allowed is not None:
            msg += '; allowed: ' + (', '.join(sorted(map(str, allowed))) or '(none)')
        raise ValueError(msg)


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


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _str(value, name, max_len, allow_empty=False):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    if len(value) > max_len:
        raise ValueError(f'{name} may have at most {max_len} characters')
    if not allow_empty and not value.strip():
        raise ValueError(f'{name} must not be empty')
    return value


def _color(value, name):
    if not isinstance(value, str) or not _COLOR_RE.match(value):
        raise ValueError(f'{name} must be a hex colour like #RRGGBB')
    h = value[1:]
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return '#' + h.upper()


def _opt_color(value, name):
    return None if value is None else _color(value, name)


def _id(value, name='id_prefix'):
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ValueError(f'{name} must match [A-Za-z][A-Za-z0-9_-]{{0,31}}')
    return value


def _weight(value, name='weight'):
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    return _choice(value, {'100', '200', '300', '400', '500', '600', '700', '800', '900',
                           'normal', 'bold'}, name)


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


# --------------------------------------------------------------------------- small maths

def _f(x, nd=2):
    s = f'{x:.{nd}f}'
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    if s in ('-0', '', '-'):
        s = '0'
    return s


def _clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def _ease_out(p):
    p = _clamp(p)
    return 1.0 - (1.0 - p) ** 3


def _ease_in_out(p):
    p = _clamp(p)
    return 4 * p * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def _back_out(p, s=1.70158):
    p = _clamp(p)
    q = p - 1.0
    return 1.0 + (s + 1.0) * q * q * q + s * q * q


def _bounce_out(p):
    p = _clamp(p)
    n1, d1 = 7.5625, 2.75
    if p < 1 / d1:
        return n1 * p * p
    if p < 2 / d1:
        p -= 1.5 / d1
        return n1 * p * p + 0.75
    if p < 2.5 / d1:
        p -= 2.25 / d1
        return n1 * p * p + 0.9375
    p -= 2.625 / d1
    return n1 * p * p + 0.984375


def _h01(*keys):
    """Deterministic hash of integers -> [0, 1). splitmix64-style mixing."""
    x = 0x9E3779B97F4A7C15
    for k in keys:
        x = (x ^ ((int(k) & _M64) + 0x9E3779B97F4A7C15 + ((x << 6) & _M64) + (x >> 2))) & _M64
        x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & _M64
        x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & _M64
        x ^= x >> 31
    return (x >> 11) / float(1 << 53)


# --------------------------------------------------------------------------- colour / contrast

def _rgb(hexc):
    h = hexc[1:]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lum(hexc):
    def ch(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(hexc)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a, b):
    """WCAG 2.x contrast ratio between two #RRGGBB colours (1..21)."""
    la, lb = _lum(_color(a, 'a')), _lum(_color(b, 'b'))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _mix(top, bottom, alpha):
    t, b = _rgb(top), _rgb(bottom)
    return '#' + ''.join(f'{int(round(alpha * x + (1 - alpha) * y)):02X}' for x, y in zip(t, b))


def _check_contrast(fill, plate, plate_opacity, stroke, stroke_width, size, what):
    """Raise unless `fill` reaches WCAG 4.5 against its plate (worst case) or its stroke."""
    if plate is not None and plate_opacity > 0:
        worst = min(contrast_ratio(fill, _mix(plate, bg, plate_opacity)) for bg in ('#000000', '#FFFFFF'))
        if worst < MIN_CONTRAST:
            raise ValueError(f'{what} {fill} on plate {plate} at opacity {plate_opacity:g} has worst-case '
                             f'contrast {worst:.2f} < {MIN_CONTRAST} (video text needs WCAG AA or better)')
        return {'against': 'plate', 'ratio': round(worst, 2)}
    if stroke is not None and stroke_width > 0:
        if stroke_width < size * MIN_STROKE_FRAC - 1e-9:
            raise ValueError(f'{what}: stroke width {stroke_width:.2f}px is too thin to act as a contrast '
                             f'surface (needs >= {MIN_STROKE_FRAC * 100:g}% of font size = '
                             f'{size * MIN_STROKE_FRAC:.2f}px) — add a plate or a thicker stroke')
        ratio = contrast_ratio(fill, stroke)
        if ratio < MIN_CONTRAST:
            raise ValueError(f'{what} {fill} against stroke {stroke} has contrast {ratio:.2f} < {MIN_CONTRAST}')
        return {'against': 'stroke', 'ratio': round(ratio, 2)}
    raise ValueError(f'{what}: video text needs a plate or an outline stroke for contrast over footage')


def _font_size(value, height, default_frac, name, min_frac=MIN_BODY_FRAC):
    minimum = height * min_frac
    if value is None:
        return max(round(height * default_frac, 1), math.ceil(minimum * 10) / 10)
    value = _num(value, 1, 2000, name)
    if value < minimum - 1e-9:
        raise ValueError(f'{name} {value:g}px is below the video minimum {minimum:.1f}px '
                         f'({min_frac * 100:g}% of frame height {height}px)')
    return value


# --------------------------------------------------------------------------- text helpers

def _esc(s):
    return html.escape(s, quote=False)


def _norm_text(s):
    s = unicodedata.normalize('NFC', s)
    s = ''.join(c for c in s if c not in _BIDI_CONTROLS)
    return ' '.join(s.split())


def _is_mark(ch):
    return unicodedata.combining(ch) != 0 or unicodedata.category(ch) in ('Mn', 'Me')


def _is_arabic_char(ch):
    o = ord(ch)
    return (0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or 0x0870 <= o <= 0x08FF
            or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF)


def _has_arabic(s):
    return any(_is_arabic_char(c) for c in s)


def _clusters(word):
    """Grapheme clusters: base + following combining marks / joiners (simplified UAX #29)."""
    out = []
    for ch in word:
        if out and (_is_mark(ch) or ch in ('‍', '‌') or out[-1].endswith('‍')):
            out[-1] += ch
        else:
            out.append(ch)
    return out


def _advance(ch):
    """Estimated advance in em for one character (no font metrics available)."""
    if _is_mark(ch) or ch in _BIDI_CONTROLS or ch in ('‍', '‌'):
        return 0.0
    if ch.isspace():
        return 0.27
    if _is_arabic_char(ch):
        cat = unicodedata.category(ch)
        if cat == 'Nd':
            return 0.52
        if cat.startswith('P'):
            return 0.3
        return 0.5
    cat = unicodedata.category(ch)
    if unicodedata.east_asian_width(ch) in ('W', 'F'):
        return 1.0
    if cat == 'Nd':
        return 0.56
    if cat == 'Lu':
        return 0.70
    if cat.startswith('L'):
        return 0.57          # Latin advances measured too narrow at 0.53 ('Red Rose' touched)
    if cat.startswith('P'):
        return 0.32
    return 0.55


def _text_width(s, size):
    return size * sum(_advance(c) for c in s)


def _char_count(s):
    return sum(1 for c in s if not _is_mark(c) and c not in _BIDI_CONTROLS
               and c not in ('‍', '‌'))


def _strong_direction(text):
    for ch in text:
        b = unicodedata.bidirectional(ch)
        if b in ('R', 'AL'):
            return 'rtl'
        if b == 'L':
            return 'ltr'
    return None


def _resolve_dir(direction, text):
    if direction in ('rtl', 'ltr'):
        return direction
    return _strong_direction(text) or 'ltr'


def _lang_attr(direction, text):
    if direction == 'rtl' and _has_arabic(text):
        return ' xml:lang="ar"'
    return ''


def _word_class(word):
    """'R' / 'L' from the first strong character, 'N' for number-only words, 'O' neutral."""
    for ch in word:
        b = unicodedata.bidirectional(ch)
        if b in ('R', 'AL'):
            return 'R'
        if b == 'L':
            return 'L'
    for ch in word:
        if unicodedata.bidirectional(ch) in ('EN', 'AN'):
            return 'N'
    return 'O'


def _visual_order(words, base):
    """Word-level Unicode bidi: returns (logical indices in left-to-right visual order,
    per-word direction attribute). Strings themselves are never reversed."""
    n = len(words)
    base_t = 'R' if base == 'rtl' else 'L'
    resolved = []
    prev_strong = base_t
    for w in words:
        c = _word_class(w)
        if c in ('R', 'L'):
            resolved.append(c)
            prev_strong = c
        elif c == 'N':
            # W7: European numbers after a strong L (in an LTR paragraph) behave as L
            resolved.append('L' if (base == 'ltr' and prev_strong == 'L') else 'N')
        else:
            resolved.append('O')
    r0 = list(resolved)

    def strength(x):
        return 'R' if x == 'N' else x            # N1: numbers act as R for neutrals

    for i in range(n):
        if r0[i] != 'O':
            continue
        j = i - 1
        while j >= 0 and r0[j] == 'O':
            j -= 1
        k = i + 1
        while k < n and r0[k] == 'O':
            k += 1
        prev = strength(r0[j]) if j >= 0 else base_t
        nxt = strength(r0[k]) if k < n else base_t
        resolved[i] = prev if prev == nxt else base_t   # N1 / N2
    levels = []
    for x in resolved:
        if base == 'ltr':
            levels.append({'L': 0, 'R': 1, 'N': 2}[x])   # I1
        else:
            levels.append({'R': 1, 'L': 2, 'N': 2}[x])   # I2
    order = list(range(n))
    top = max(levels) if levels else 0
    for lev in range(top, 0, -1):                        # L2
        i = 0
        while i < n:
            if levels[order[i]] >= lev:
                j = i
                while j < n and levels[order[j]] >= lev:
                    j += 1
                order[i:j] = order[i:j][::-1]
                i = j
            else:
                i += 1
    dirs = []
    for x in resolved:
        dirs.append('rtl' if x == 'R' else 'ltr' if x in ('L', 'N') else base)
    return order, dirs


def _layout_line(words, base, size, x0, x1, align):
    """Estimated per-word centres for one line. Returns ([(cx, w, dir)] in logical order, (lx0, lx1))."""
    n = len(words)
    widths = [_text_width(w, size) for w in words]
    gap = _advance(' ') * size
    total = sum(widths) + gap * (n - 1)
    if align == 'center':
        start = (x0 + x1) / 2 - total / 2
    elif (align == 'start') == (base == 'rtl'):
        start = x1 - total
    else:
        start = x0
    order, dirs = _visual_order(words, base)
    out = [None] * n
    x = start
    for k in order:
        out[k] = (x + widths[k] / 2, widths[k], dirs[k])
        x += widths[k] + gap
    return out, (start, start + total)


def _is_weak(word):
    w = word.strip('.,;:!?،؛؟"\'«»()[]-–—').lower()
    return w in _WEAK_WORDS


def _wrap(words, max_chars):
    """Balanced line breaking (min sum of squared slack) that never splits a word.
    Blank words ('') take no space but keep their index. Works in logical order,
    so RTL text wraps correctly (direction is applied when drawing)."""
    n = len(words)
    if n == 0:
        return []
    lens = [_char_count(w) for w in words]
    inf = float('inf')
    best = [inf] * (n + 1)
    best[n] = 0.0
    nxt = [n] * (n + 1)
    for i in range(n - 1, -1, -1):
        length = 0
        nb = 0
        for j in range(i, n):
            if lens[j] > 0:
                length += lens[j] + (1 if nb > 0 else 0)
                nb += 1
            if length > max_chars and nb > 1:
                break
            slack = max_chars - length
            cost = float(slack * slack) if slack >= 0 else 1e6 + 10.0 * (length - max_chars) ** 2
            if j < n - 1 and words[j] and _is_weak(words[j]):
                cost += (max_chars * 0.5) ** 2
            total = cost + best[j + 1]
            if total < best[i]:
                best[i] = total
                nxt[i] = j + 1
    lines = []
    i = 0
    while i < n:
        j = nxt[i]
        lines.append(list(range(i, j)))
        i = j
    return lines


def _paginate(lines, max_lines):
    return [lines[k:k + max_lines] for k in range(0, len(lines), max_lines)]


def _words_input(value, name='words'):
    """str -> whitespace words; list of str/None -> words with None -> '' (unclear, stays empty)."""
    if isinstance(value, str):
        _str(value, name, MAX_TEXT)
        words = _norm_text(value).split()
    elif isinstance(value, (list, tuple)):
        if len(value) > MAX_WORDS:
            raise ValueError(f'{name} may have at most {MAX_WORDS} items')
        words = []
        for i, w in enumerate(value):
            if w is None:
                words.append('')
            elif isinstance(w, str):
                if len(w) > 200:
                    raise ValueError(f'{name}[{i}] is too long')
                words.append(_norm_text(w))
            else:
                raise ValueError(f'{name}[{i}] must be a string or None')
    else:
        raise ValueError(f'{name} must be a string or a list of strings/None')
    if not any(words):
        raise ValueError(f'{name} has no non-empty word')
    if len(words) > MAX_WORDS:
        raise ValueError(f'{name} may have at most {MAX_WORDS} words')
    return words


def _timed_words(value):
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError('words_with_times must be a non-empty list')
    if len(value) > MAX_TIMED:
        raise ValueError(f'words_with_times may have at most {MAX_TIMED} items')
    out = []
    prev = -1.0
    for i, item in enumerate(value):
        if isinstance(item, dict):
            unknown = set(item) - {'word', 'start', 'end'}
            if unknown:
                raise ValueError(f'words_with_times[{i}] has unknown key(s): {sorted(map(str, unknown))}')
            if 'start' not in item or 'end' not in item:
                raise ValueError(f'words_with_times[{i}] needs start and end')
            w, s, e = item.get('word'), item['start'], item['end']
        elif isinstance(item, (list, tuple)) and len(item) == 3:
            w, s, e = item
        else:
            raise ValueError(f'words_with_times[{i}] must be {{word,start,end}} or [word,start,end]')
        if w is None:
            w = ''
        elif isinstance(w, str):
            if len(w) > 200:
                raise ValueError(f'words_with_times[{i}].word is too long')
            w = _norm_text(w)
        else:
            raise ValueError(f'words_with_times[{i}].word must be a string or None')
        s = _num(s, 0, 86400, f'words_with_times[{i}].start')
        e = _num(e, 0, 86400, f'words_with_times[{i}].end')
        if e < s:
            raise ValueError(f'words_with_times[{i}]: end < start')
        if s < prev - 1e-9:
            raise ValueError(f'words_with_times[{i}]: starts must be non-decreasing')
        prev = s
        out.append({'word': w, 'start': s, 'end': e})
    if not any(w['word'] for w in out):
        raise ValueError('words_with_times has no non-empty word')
    return out


def _font_attrs(size, weight, fill):
    """Font + fill attributes. The outline is NOT set here: it is drawn as a separate text copy
    underneath (see _outline_attrs), because CairoSVG ignores paint-order and would paint the
    stroke over the fill."""
    return f' font-family="{FONT_STACK}" font-size="{_f(size)}" font-weight="{weight}" fill="{fill}"'


def _outline_attrs(stroke, stroke_width):
    """Attributes of the outline copy drawn under the fill copy ('' when there is no outline)."""
    if stroke is None or stroke_width <= 0:
        return ''
    return (f' fill="{stroke}" stroke="{stroke}" stroke-width="{_f(stroke_width)}"'
            f' stroke-linejoin="round"')


# --------------------------------------------------------------------------- canvas / safe areas

def _safe_box(width, height, platform=None, frac=TITLE_SAFE):
    mx = width * (1 - frac) / 2
    my = height * (1 - frac) / 2
    x0, y0, x1, y1 = mx, my, width - mx, height - my
    if platform is not None:
        ui = PLATFORMS[platform]['ui']
        x0 = max(x0, width * ui['left'])
        x1 = min(x1, width * (1 - ui['right']))
        y0 = max(y0, height * ui['top'])
        y1 = min(y1, height * (1 - ui['bottom']))
    return x0, y0, x1, y1


def _rect(box):
    x0, y0, x1, y1 = box
    return [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)]


def derive_canvas(platform='reels', fps=None, **extra):
    """Frame size, fps and safe areas for a delivery platform."""
    _no_extra(extra)
    platform = _choice(platform, PLATFORMS, 'platform')
    spec = PLATFORMS[platform]
    w, h = spec['width'], spec['height']
    fps = spec['fps'] if fps is None else _num(fps, 1, 240, 'fps')
    g = math.gcd(w, h)
    zone = _safe_box(w, h, platform)
    return {
        'platform': platform, 'width': w, 'height': h, 'aspect': f'{w // g}:{h // g}', 'fps': fps,
        'orientation': 'vertical' if h > w else 'horizontal' if w > h else 'square',
        'title_safe': _rect(_safe_box(w, h, None, TITLE_SAFE)),
        'action_safe': _rect(_safe_box(w, h, None, ACTION_SAFE)),
        'ui_margins': dict(spec['ui']),
        'caption_zone': _rect(zone),
        'min_caption_px': math.ceil(h * MIN_BODY_FRAC),
        'recommended_px': {'caption': round(h * 0.045), 'title': round(h * 0.07),
                           'lower_third_name': round(h * 0.05), 'lower_third_role': round(h * 0.036)},
        'rect_format': '[x, y, width, height] in pixels',
    }


# --------------------------------------------------------------------------- kinetic text

def _stagger(n, reveal, win_frac=0.4, win_max=0.6):
    if n <= 1:
        return [0.0], max(1e-3, min(reveal, win_max))
    win = min(win_max, max(0.12, reveal * win_frac), reveal)
    win = max(win, 1e-3)
    step = max(0.0, (reveal - win) / (n - 1))
    return [i * step for i in range(n)], win


_ARABIC_INDIC = '٠١٢٣٤٥٦٧٨٩'
_PERSIAN = '۰۱۲۳۴۵۶۷۸۹'


def _count_word(word, e, digits):
    """Replace numeric tokens in `word` by value * e, keeping decimals; returns (text, had_number)."""
    found = [False]

    def rep(m):
        tok = m.group(0)
        latin = ''.join(str(unicodedata.digit(c)) if unicodedata.category(c) == 'Nd' else c for c in tok)
        latin = latin.replace('٫', '.')
        intpart = latin.split('.')[0]
        if len(latin.replace('.', '')) > 15:
            return tok
        found[0] = True
        dec = len(latin.split('.')[1]) if '.' in latin else 0
        s = f'{float(latin) * e:.{dec}f}'
        ip, _, fp = s.partition('.')
        if len(intpart) > 1 and intpart.startswith('0'):
            ip = ip.zfill(len(intpart))
        style = digits
        if style == 'keep':
            if any(c in _ARABIC_INDIC for c in tok):
                style = 'arabic_indic'
            elif any(c in _PERSIAN for c in tok):
                style = 'persian'
            else:
                style = 'latin'
        if digits == 'latin':
            sep = '.'
        elif '٫' in tok or digits == 'arabic_indic':
            sep = '٫'
        else:
            sep = '.'
        out = ip + (sep + fp if fp else '')
        if style == 'arabic_indic':
            out = ''.join(_ARABIC_INDIC[int(c)] if c.isdigit() else c for c in out)
        elif style == 'persian':
            out = ''.join(_PERSIAN[int(c)] if c.isdigit() else c for c in out)
        return out

    text = _DIGIT_RE.sub(rep, word)
    return text, found[0]


def _st0():
    return {'op': 1.0, 'dx': 0.0, 'dy': 0.0, 'sc': 1.0, 'rot': 0.0, 'blur': 0.0,
            'fill': None, 'text': None, 'anchor': None, 'ghosts': [], 'filter': None}


def _word_svg(word, st, cx, baseline, size, dirattr, outline=''):
    if st['op'] <= 0.001 or st['sc'] <= 0.001:
        return ''
    txt = st['text'] if st['text'] is not None else word
    if not txt:
        return ''
    anchor = 'middle'
    x = cx + st['dx']
    if st['anchor'] is not None:
        anchor = 'start'
        x = st['anchor'] + st['dx']
    yc = baseline - size * 0.35 + st['dy']
    tr = f'translate({_f(x)},{_f(yc)})'
    if abs(st['rot']) > 1e-4:
        tr += f' rotate({_f(st["rot"], 3)})'
    if abs(st['sc'] - 1.0) > 1e-4:
        tr += f' scale({_f(st["sc"], 4)})'
    tr += f' translate(0,{_f(size * 0.35)})'
    attrs = f' transform="{tr}"'
    if st['op'] < 0.999:
        attrs += f' opacity="{_f(st["op"], 3)}"'
    if st['filter']:
        attrs += f' filter="url(#{st["filter"]})"'
    lang = _lang_attr(dirattr, txt)
    base_attrs = f'text-anchor="{anchor}" direction="{dirattr}" unicode-bidi="embed"{lang}'
    inner = ''
    for gdx, gcol, gop in st['ghosts']:
        inner += (f'<text x="{_f(gdx)}" y="0" {base_attrs} fill="{gcol}" stroke="none" '
                  f'opacity="{_f(gop, 3)}">{_esc(txt)}</text>')
    fill_attr = f' fill="{st["fill"]}"' if st['fill'] else ''
    if outline:
        inner += f'<text x="0" y="0" {base_attrs}{outline}>{_esc(txt)}</text>'
    inner += f'<text x="0" y="0" {base_attrs}{fill_attr}>{_esc(txt)}</text>'
    return f'<g{attrs}>{inner}</g>'


def _inv_ease_in_out(q):
    """Inverse of _ease_in_out on [0, 1]."""
    q = _clamp(q)
    if q < 0.5:
        return (q / 4.0) ** (1.0 / 3.0)
    return 1.0 - (2.0 * (1.0 - q)) ** (1.0 / 3.0) / 2.0


def _word_timings(style, words, lines, place, base, duration, fps, hold, latin_per_letter, x0, bw):
    """Reveal window of every word: start = first moment it can be seen, end = fully shown.
    Same schedule as the style code in _kinetic_core; the exit fade is not included."""
    n = len(words)
    sched = [(0.0, 0.0)] * n
    if style == 'word_typewriter':
        step = 0.7 * duration / n
        win = max(step * 0.9, 1e-3)
        for gi in range(n):
            s = gi * step
            typed = (latin_per_letter and not _has_arabic(words[gi]) and place[gi][2] == 'ltr'
                     and len(_clusters(words[gi])) > 1)
            sched[gi] = (s, s + win if typed else s)
    elif style in ('fade_up', 'slide_in', 'pop_scale', 'blur_in', 'stagger_words', 'bounce_words',
                   'glitch_words', 'underline_draw'):
        if style == 'stagger_words':
            starts, win = _stagger(n, 0.4 * duration, 0.5, 0.35)
        elif style == 'bounce_words':
            starts, win = _stagger(n, 0.65 * duration, 0.45, 0.8)
        elif style == 'underline_draw':
            starts, win = _stagger(n, 0.35 * duration, 0.5, 0.4)
        else:
            starts, win = _stagger(n, 0.6 * duration)
        sched = [(starts[gi], starts[gi] + win) for gi in range(n)]
    elif style == 'counter_numbers':
        sched = [(0.0, 0.75 * duration if _DIGIT_RE.search(w) else min(0.4, duration)) for w in words]
    elif style == 'held_frames':
        starts, _ = _stagger(n, 0.6 * duration, 0.3, 0.5)
        pose = hold / fps
        for gi in range(n):
            first = math.ceil(starts[gi] / pose - 1e-9) * pose
            sched[gi] = (first, first + 2 * pose)
    elif style == 'split_lines':
        lstarts, win = _stagger(len(lines), 0.6 * duration, 0.5, 0.7)
        for li, idxs in enumerate(lines):
            for gi in idxs:
                sched[gi] = (lstarts[li], lstarts[li] + win)
    elif style == 'mask_reveal':
        span = 0.6 * duration
        for gi in range(n):
            cx, w = place[gi][0], place[gi][1]
            if base == 'rtl':
                q0, q1 = (x0 + bw - (cx + w / 2)) / bw, (x0 + bw - (cx - w / 2)) / bw
            else:
                q0, q1 = (cx - w / 2 - x0) / bw, (cx + w / 2 - x0) / bw
            sched[gi] = (span * _inv_ease_in_out(q0), span * _inv_ease_in_out(q1))
    elif style == 'drift_zoom':
        sched = [(0.0, min(0.6, duration))] * n
    return [{'word': words[gi], 'start': round(min(duration, a), 3), 'end': round(min(duration, b), 3)}
            for gi, (a, b) in enumerate(sched)]


def _kinetic_core(text=EXAMPLE_AR, style='fade_up', t=1.2, duration=3.0, width=1080, height=1920, *,
                  font_size=None, weight='700', fill='#FFFFFF', stroke='#000000', stroke_width=None,
                  plate=None, plate_opacity=0.85, highlight='#FFD400', accent='#C8102E',
                  direction='auto', align='center', position='center', platform=None, max_lines=4,
                  digits='keep', latin_per_letter=True, seed=7, fps=24.0, hold=2, exit=0.35,
                  id_prefix='rr', **extra):
    _no_extra(extra)
    text = _str(text, 'text', MAX_TEXT)
    style = _choice(style, STYLES, 'style')
    t = _num(t, -1e5, 1e5, 't')
    duration = _num(duration, 0.2, 600, 'duration')
    width = _int(width, 64, 8192, 'width')
    height = _int(height, 64, 8192, 'height')
    weight = _weight(weight)
    fill = _color(fill, 'fill')
    stroke = _opt_color(stroke, 'stroke')
    plate = _opt_color(plate, 'plate')
    plate_opacity = _num(plate_opacity, 0.5, 1.0, 'plate_opacity')
    highlight = _color(highlight, 'highlight')
    accent = _color(accent, 'accent')
    direction = _choice(direction, {'auto', 'rtl', 'ltr'}, 'direction')
    align = _choice(align, {'center', 'start', 'end'}, 'align')
    position = _choice(position, {'center', 'lower', 'upper'}, 'position')
    if platform is not None:
        platform = _choice(platform, PLATFORMS, 'platform')
    max_lines = _int(max_lines, 1, 8, 'max_lines')
    digits = _choice(digits, {'keep', 'latin', 'arabic_indic'}, 'digits')
    latin_per_letter = _bool(latin_per_letter, 'latin_per_letter')
    seed = _int(seed, 0, 2 ** 31 - 1, 'seed')
    fps = _num(fps, 1, 120, 'fps')
    hold = _int(hold, 1, 12, 'hold')
    exit = min(_num(exit, 0, 10, 'exit'), duration / 2)
    id_prefix = _id(id_prefix)

    norm = _norm_text(text)
    words = norm.split()
    if not words:
        raise ValueError('text has no words')
    if len(words) > MAX_WORDS:
        raise ValueError(f'text may have at most {MAX_WORDS} words')
    base = _resolve_dir(direction, norm)
    x0, y0, x1, y1 = _safe_box(width, height, platform)
    bw = x1 - x0
    auto_size = font_size is None
    size = _font_size(font_size, height, 0.06, 'font_size')
    min_size = height * MIN_BODY_FRAC
    gap = _advance(' ')
    warnings = []
    while True:
        max_chars = max(4, int(bw / (0.52 * size)))
        lines = _wrap(words, max_chars)
        widest = max(sum(_text_width(words[i], size) for i in ln) + gap * size * (len(ln) - 1)
                     for ln in lines)
        fits = len(lines) <= max_lines and widest <= bw
        if fits or not auto_size or size * 0.92 < min_size:
            break
        size = round(size * 0.92, 2)
    if len(lines) > max_lines:
        warnings.append(f'text needs {len(lines)} lines > max_lines {max_lines}; all lines are drawn')
    if widest > bw:
        warnings.append('a line is estimated wider than the title-safe area; shorten the text or lower font_size')
    if stroke_width is None:
        sw = size * 0.08 if stroke is not None else 0.0
    else:
        sw = _num(stroke_width, 0, size * 0.5, 'stroke_width')
    contrast = _check_contrast(fill, plate, plate_opacity, stroke, sw, size, 'fill')
    hl_text = None
    if style == 'highlight_sweep':
        hl_text = max(('#111111', '#FFFFFF'), key=lambda c: contrast_ratio(c, highlight))
        r = contrast_ratio(hl_text, highlight)
        if r < MIN_CONTRAST:
            raise ValueError(f'highlight {highlight} cannot reach contrast {MIN_CONTRAST} with dark or light text')
        contrast = dict(contrast, highlight_text=hl_text, highlight_ratio=round(r, 2))

    meta = {'style': style, 'direction': base, 'font_size': round(size, 2), 'stroke_width': round(sw, 2),
            'lines': [' '.join(words[i] for i in ln) for ln in lines], 'line_count': len(lines),
            'word_count': len(words), 'contrast': contrast, 'warnings': warnings,
            't': t, 'duration': duration, 'safe_box': _rect((x0, y0, x1, y1)), 'shaping': SHAPING_NOTE,
            'per_letter_arabic': False}

    # ---- layout
    n = len(words)
    L = len(lines)
    lh = size * (1.45 if base == 'rtl' else 1.3)
    block_h = L * lh
    if position == 'center':
        top = (y0 + y1) / 2 - block_h / 2
    elif position == 'upper':
        top = y0
    else:
        top = y1 - block_h
    place = [None] * n            # gi -> (cx, w, dir, li, baseline)
    line_info = []                # li -> (lx0, lx1, line_top, baseline)
    for li, idxs in enumerate(lines):
        lw = [words[i] for i in idxs]
        pos, (lx0, lx1) = _layout_line(lw, base, size, x0, x1, align)
        ltop = top + li * lh
        baseline = ltop + lh / 2 + size * 0.35
        line_info.append((lx0, lx1, ltop, baseline))
        for k, gi in enumerate(idxs):
            cx, w, d = pos[k]
            place[gi] = (cx, w, d, li, baseline)
    meta['word_timings'] = _word_timings(style, words, lines, place, base, duration, fps, hold,
                                         latin_per_letter, x0, bw)
    if t < 0 or t > duration:
        meta['visible'] = False
        return '', meta
    g_op = 1.0 if exit <= 0 else _clamp((duration - t) / exit)

    rd = 1.0 if base == 'rtl' else -1.0     # x sign of "reading start" side
    states = [_st0() for _ in range(n)]
    defs = []
    back = []        # behind text (bands)
    front = []       # in front of text (underlines, caret)
    group_clip = None
    group_tr = None
    line_clip = {}
    frame = int(math.floor(t * fps))

    if style == 'word_typewriter':
        reveal = 0.7 * duration
        step = reveal / n
        win = max(step * 0.9, 1e-3)
        last = None
        for gi in range(n):
            s = gi * step
            st = states[gi]
            cx, w, d, li, bl = place[gi]
            if t < s:
                st['op'] = 0.0
                continue
            w_now = w
            word = words[gi]
            if latin_per_letter and not _has_arabic(word) and d == 'ltr':
                cl = _clusters(word)
                k = min(len(cl), int(len(cl) * _clamp((t - s) / win)) + 1)
                if k < len(cl):
                    st['text'] = ''.join(cl[:k])
                    st['anchor'] = cx - w / 2
                    w_now = _text_width(st['text'], size)
            last = (gi, w_now, st['anchor'] is not None)
        typing = t < reveal + step
        if last is not None and (typing or int(t * 2) % 2 == 0):
            gi, w_now, partial = last
            cx, w, d, li, bl = place[gi]
            if partial:
                cxr = cx - w / 2 + w_now + size * 0.06
            elif base == 'rtl':
                cxr = cx - w / 2 - size * 0.12
            else:
                cxr = cx + w / 2 + size * 0.06
            front.append(f'<rect x="{_f(cxr)}" y="{_f(bl - size * 0.82)}" width="{_f(size * 0.06)}" '
                         f'height="{_f(size * 1.0)}" fill="{fill}"'
                         + (f' stroke="{stroke}" stroke-width="{_f(max(1.0, sw * 0.5))}"' if stroke else '')
                         + '/>')
    elif style in ('fade_up', 'slide_in', 'pop_scale', 'blur_in', 'stagger_words', 'bounce_words',
                   'glitch_words'):
        if style == 'stagger_words':
            starts, win = _stagger(n, 0.4 * duration, 0.5, 0.35)
        elif style == 'bounce_words':
            starts, win = _stagger(n, 0.65 * duration, 0.45, 0.8)
        else:
            starts, win = _stagger(n, 0.6 * duration)
        for gi in range(n):
            st = states[gi]
            p = _clamp((t - starts[gi]) / win)
            e = _ease_out(p)
            if style == 'fade_up':
                st['op'] = e
                st['dy'] = (1 - e) * size * 0.6
            elif style == 'slide_in':
                st['op'] = _clamp(p * 1.5)
                st['dx'] = rd * (1 - e) * size * 1.6
            elif style == 'pop_scale':
                st['op'] = _clamp(p * 3)
                st['sc'] = 1.0 if p >= 1 else max(0.0, _back_out(p))
            elif style == 'blur_in':
                st['op'] = e
                blur = (1 - e) * size * 0.2
                if blur > 0.05:
                    fid = f'{id_prefix}-blur-{gi}'
                    defs.append(f'<filter id="{fid}" x="-50%" y="-50%" width="200%" height="200%">'
                                f'<feGaussianBlur stdDeviation="{_f(blur)}"/></filter>')
                    st['filter'] = fid
            elif style == 'stagger_words':
                st['op'] = e
                st['sc'] = 0.82 + 0.18 * e
                st['dy'] = (1 - e) * size * 0.25
            elif style == 'bounce_words':
                st['op'] = _clamp(p * 5)
                st['dy'] = -(1 - _bounce_out(p)) * size * 1.8
            else:  # glitch_words
                if p <= 0:
                    st['op'] = 0.0
                    continue
                if p < 1:
                    amp = 1 - p
                    st['op'] = 1.0 if _h01(seed, gi, frame, 2) > 0.15 else 0.45
                else:
                    amp = 0.3 if _h01(seed, gi, frame // 3, 7) < 0.05 else 0.0
                if amp > 0:
                    st['dx'] = (_h01(seed, gi, frame, 1) - 0.5) * size * 0.5 * amp
                    off = size * 0.08 * amp + 2.0
                    st['ghosts'] = [(-off, '#00E5FF', 0.75), (off, '#FF2D55', 0.75)]
    elif style == 'underline_draw':
        starts, win = _stagger(n, 0.35 * duration, 0.5, 0.4)
        for gi in range(n):
            states[gi]['op'] = _ease_out(_clamp((t - starts[gi]) / win))
        span = 0.4 * duration / L
        for li, (lx0, lx1, ltop, bl) in enumerate(line_info):
            p = _ease_in_out(_clamp((t - 0.35 * duration - li * span) / span))
            if p <= 0:
                continue
            uy = bl + size * 0.2
            length = (lx1 - lx0) * p
            xa, xb = (lx1, lx1 - length) if base == 'rtl' else (lx0, lx0 + length)
            front.append(f'<line x1="{_f(xa)}" y1="{_f(uy)}" x2="{_f(xb)}" y2="{_f(uy)}" stroke="{accent}" '
                         f'stroke-width="{_f(size * 0.07)}" stroke-linecap="round"/>')
    elif style == 'counter_numbers':
        e = _ease_out(_clamp(t / (0.75 * duration)))
        e_txt = _ease_out(_clamp(t / 0.4))
        for gi in range(n):
            txt, had = _count_word(words[gi], e, digits)
            if had:
                states[gi]['text'] = txt
            else:
                states[gi]['op'] = e_txt
    elif style == 'held_frames':
        pose = int(math.floor(t * fps / hold))
        tq = pose * hold / fps
        starts, _ = _stagger(n, 0.6 * duration, 0.3, 0.5)
        for gi in range(n):
            st = states[gi]
            if tq < starts[gi]:
                st['op'] = 0.0
                continue
            k = int((tq - starts[gi]) * fps / hold + 1e-9)
            st['sc'] = (1.18, 0.95)[k] if k < 2 else 1.0
            st['dx'] = (_h01(seed, gi, pose, 1) - 0.5) * size * 0.04
            st['dy'] = (_h01(seed, gi, pose, 2) - 0.5) * size * 0.04
            st['rot'] = (_h01(seed, gi, pose, 3) - 0.5) * 3.0
    elif style == 'split_lines':
        lstarts, win = _stagger(L, 0.6 * duration, 0.5, 0.7)
        for li, (lx0, lx1, ltop, bl) in enumerate(line_info):
            e = _ease_out(_clamp((t - lstarts[li]) / win))
            cid = f'{id_prefix}-line-{li}'
            defs.append(f'<clipPath id="{cid}"><rect x="{_f(x0 - size)}" y="{_f(ltop)}" '
                        f'width="{_f(bw + 2 * size)}" height="{_f(lh + size * 0.15)}"/></clipPath>')
            line_clip[li] = cid
            for gi in lines[li]:
                states[gi]['dy'] = (1 - e) * lh * 1.05
                if e <= 0:
                    states[gi]['op'] = 0.0
    elif style == 'mask_reveal':
        p = _ease_in_out(_clamp(t / (0.6 * duration)))
        cid = f'{id_prefix}-mask'
        mw = bw * p
        mx = x1 - mw if base == 'rtl' else x0
        defs.append(f'<clipPath id="{cid}"><rect x="{_f(mx)}" y="{_f(top - size * 0.4)}" '
                    f'width="{_f(mw)}" height="{_f(block_h + size * 0.8)}"/></clipPath>')
        group_clip = cid
        if p <= 0:
            meta['visible'] = False
            return '', meta
    elif style == 'highlight_sweep':
        span = 0.7 * duration / L
        pad = size * 0.18
        for li, (lx0, lx1, ltop, bl) in enumerate(line_info):
            p = _ease_in_out(_clamp((t - li * span) / span))
            full = (lx1 - lx0) + 2 * pad
            bwid = full * p
            if p > 0:
                bx = (lx1 + pad - bwid) if base == 'rtl' else (lx0 - pad)
                back.append(f'<rect x="{_f(bx)}" y="{_f(bl - size * 0.95)}" width="{_f(bwid)}" '
                            f'height="{_f(size * 1.3)}" rx="{_f(size * 0.12)}" fill="{highlight}"/>')
            lead = (lx1 + pad - bwid) if base == 'rtl' else (lx0 - pad + bwid)
            for gi in lines[li]:
                cx = place[gi][0]
                covered = (cx >= lead) if base == 'rtl' else (cx <= lead)
                if p > 0 and covered:
                    states[gi]['fill'] = hl_text
    elif style == 'drift_zoom':
        g_op *= _ease_out(_clamp(t / 0.6))
        s = 1.08 - 0.08 * _ease_in_out(_clamp(t / duration))
        cxb, cyb = (x0 + x1) / 2, top + block_h / 2
        group_tr = f'translate({_f(cxb)},{_f(cyb)}) scale({_f(s, 4)}) translate({_f(-cxb)},{_f(-cyb)})'

    if g_op <= 0.001:
        meta['visible'] = False
        return '', meta

    plates = []
    if plate is not None:
        ppad = size * 0.4
        for lx0, lx1, ltop, bl in line_info:
            plates.append(f'<rect x="{_f(lx0 - ppad)}" y="{_f(ltop + lh * 0.06)}" '
                          f'width="{_f(lx1 - lx0 + 2 * ppad)}" height="{_f(lh * 0.88)}" '
                          f'rx="{_f(size * 0.2)}" fill="{plate}" fill-opacity="{_f(plate_opacity, 3)}"/>')
    word_parts = []
    visible_words = 0
    outline = _outline_attrs(stroke, sw)
    for li, idxs in enumerate(lines):
        chunk = []
        for gi in idxs:
            cx, w, d, _, bl = place[gi]
            if states[gi]['anchor'] is not None:
                d = 'ltr'
            el = _word_svg(words[gi], states[gi], cx, bl, size, d, outline)
            if el:
                visible_words += 1
                chunk.append(el)
        if not chunk:
            continue
        if li in line_clip:
            word_parts.append(f'<g clip-path="url(#{line_clip[li]})">' + ''.join(chunk) + '</g>')
        else:
            word_parts.extend(chunk)

    g_attrs = f' class="rr-kinetic" data-style="{style}" data-direction="{base}"'
    if g_op < 0.999:
        g_attrs += f' opacity="{_f(g_op, 3)}"'
    if group_clip:
        g_attrs += f' clip-path="url(#{group_clip})"'
    if group_tr:
        g_attrs += f' transform="{group_tr}"'
    svg = (f'<g{g_attrs}>' + (f'<defs>{"".join(defs)}</defs>' if defs else '')
           + ''.join(plates) + ''.join(back)
           + f'<g{_font_attrs(size, weight, fill)}>' + ''.join(word_parts) + '</g>'
           + ''.join(front) + '</g>')
    meta['visible'] = True
    meta['visible_words'] = visible_words
    return svg, meta


def kinetic_text(text=EXAMPLE_AR, style='fade_up', t=1.2, duration=3.0, width=1080, height=1920,
                 **options):
    """SVG fragment (<g>…</g>) of `text` animated with `style` at time t (seconds).

    Options: font_size, weight, fill, stroke, stroke_width, plate, plate_opacity,
    highlight, accent, direction ('auto'|'rtl'|'ltr'), align, position, platform,
    max_lines, digits ('keep'|'latin'|'arabic_indic'), latin_per_letter, seed,
    fps, hold, exit, id_prefix. Returns '' when t is outside [0, duration].
    """
    svg, _ = _kinetic_core(text, style, t, duration, width, height, **options)
    return svg


def list_styles():
    return [{'name': k, 'description_ar': v} for k, v in STYLES.items()]


# --------------------------------------------------------------------------- captions

def wrap_caption(words=None, max_chars=42, max_lines=2, *, direction='auto', **extra):
    """Break words into caption lines/pages without ever splitting a word.

    `words` is a string or a list of strings/None; None or '' means an unclear
    word: it keeps its index (and time slot) but contributes no text."""
    _no_extra(extra)
    if words is None:
        words = [w['word'] or None for w in _EXAMPLE_TIMED]
    words = _words_input(words)
    max_chars = _int(max_chars, 4, 200, 'max_chars')
    max_lines = _int(max_lines, 1, 6, 'max_lines')
    direction = _choice(direction, {'auto', 'rtl', 'ltr'}, 'direction')
    lines = _wrap(words, max_chars)
    pages = []
    for pg in _paginate(lines, max_lines):
        out = []
        for ln in pg:
            txt = ' '.join(words[i] for i in ln if words[i])
            nonblank = [words[i] for i in ln if words[i]]
            out.append({'indices': ln, 'text': txt, 'direction': _resolve_dir(direction, txt),
                        'chars': _char_count(txt),
                        'overlong': len(nonblank) == 1 and _char_count(nonblank[0]) > max_chars})
        pages.append({'lines': out})
    all_text = ' '.join(w for w in words if w)
    return {'pages': pages, 'page_count': len(pages), 'line_count': len(lines),
            'blank_indices': [i for i, w in enumerate(words) if not w],
            'direction': _resolve_dir(direction, all_text), 'max_chars': max_chars, 'max_lines': max_lines}


def _caption_style(preset, width, height, platform, font_size, position, fill, highlight):
    preset = _choice(preset, PRESETS, 'preset')
    width = _int(width, 64, 8192, 'width')
    height = _int(height, 64, 8192, 'height')
    if platform is not None:
        platform = _choice(platform, PLATFORMS, 'platform')
    p = PRESETS[preset]
    box = _safe_box(width, height, platform)
    size = _font_size(font_size, height, p['size_frac'], 'font_size')
    fill = p['fill'] if fill is None else _color(fill, 'fill')
    hl = p['highlight'] if highlight is None else _color(highlight, 'highlight')
    sw = size * p['stroke_frac'] if p['stroke'] else 0.0
    c1 = _check_contrast(fill, p['plate'], p['plate_opacity'], p['stroke'], sw, size, 'fill')
    c2 = _check_contrast(hl, p['plate'], p['plate_opacity'], p['stroke'], sw, size, 'highlight')
    position = p['position'] if position is None else _choice(position, {'lower', 'center', 'upper'},
                                                               'position')
    pad = size * 0.35 if p['plate'] else 0.0
    fit_chars = max(4, int((box[2] - box[0] - 2 * pad) / (0.52 * size)))
    return {'preset': preset, 'width': width, 'height': height, 'box': box, 'size': size,
            'fill': fill, 'highlight': hl, 'stroke': p['stroke'], 'stroke_width': sw,
            'plate': p['plate'], 'plate_opacity': p['plate_opacity'], 'weight': p['weight'],
            'line_height': p['line_height'], 'position': position,
            'max_chars': min(p['max_chars'], fit_chars), 'fit_chars': fit_chars,
            'contrast': {'fill': c1, 'highlight': c2}}


def _draw_caption(lines, st, direction, css_class):
    """lines: list of lists of (word, fill-or-None); blank words are skipped but keep their line slot.

    Every word is its own <text> (text-anchor middle) placed with the word-level bidi model, so
    the result does not depend on how a renderer anchors <tspan> runs (CairoSVG anchors only the
    first tspan) or on direction-dependent text-anchor. Words are never split."""
    size = st['size']
    lh = size * st['line_height']
    x0, y0, x1, y1 = st['box']
    n = len(lines)
    block_h = n * lh
    if st['position'] == 'lower':
        top = y1 - block_h
    elif st['position'] == 'upper':
        top = y0
    else:
        top = (y0 + y1) / 2 - block_h / 2
    plates = []
    texts = []
    warn = []
    outline = _outline_attrs(st['stroke'], st['stroke_width'])
    for li, toks in enumerate(lines):
        toks = [(w, c) for w, c in toks if w]
        if not toks:
            continue
        line_text = ' '.join(w for w, _ in toks)
        d = _resolve_dir(direction, line_text)
        pos, (lx0, lx1) = _layout_line([w for w, _ in toks], d, size, x0, x1, 'center')
        if lx1 - lx0 > (x1 - x0):
            warn.append(f'line {li} is estimated wider than the safe area')
        ltop = top + li * lh
        bl = ltop + lh / 2 + size * 0.35
        if st['plate']:
            pad = size * 0.35
            plates.append(f'<rect x="{_f(lx0 - pad)}" y="{_f(ltop + lh * 0.04)}" '
                          f'width="{_f(lx1 - lx0 + 2 * pad)}" height="{_f(lh * 0.92)}" rx="{_f(size * 0.18)}" '
                          f'fill="{st["plate"]}" fill-opacity="{_f(st["plate_opacity"], 3)}"/>')
        words_svg = []
        for (w, c), (cx, _, wd) in zip(toks, pos):
            attrs = (f'x="{_f(cx)}" y="{_f(bl)}" text-anchor="middle" direction="{wd}" '
                     f'unicode-bidi="embed"{_lang_attr(wd, w)}')
            if outline:
                words_svg.append(f'<text {attrs}{outline}>{_esc(w)}</text>')
            fa = f' fill="{c}"' if c else ''
            words_svg.append(f'<text {attrs}{fa}>{_esc(w)}</text>')
        texts.append(f'<g class="rr-line" data-direction="{d}">' + ''.join(words_svg) + '</g>')
    svg = (f'<g class="{css_class}" data-preset="{st["preset"]}">' + ''.join(plates)
           + f'<g{_font_attrs(size, st["weight"], st["fill"])}>'
           + ''.join(texts) + '</g></g>')
    return svg, warn


def _caption_core(words=None, preset='social_bold', width=1080, height=1920, *, page=0, platform=None,
                  font_size=None, max_chars=None, max_lines=2, position=None, fill=None, highlight=None,
                  direction='auto', **extra):
    _no_extra(extra)
    if words is None:
        words = [w['word'] or None for w in _EXAMPLE_TIMED]
    words = _words_input(words)
    st = _caption_style(preset, width, height, platform, font_size, position, fill, highlight)
    max_lines = _int(max_lines, 1, 4, 'max_lines')
    direction = _choice(direction, {'auto', 'rtl', 'ltr'}, 'direction')
    warnings = []
    mc = st['max_chars'] if max_chars is None else _int(max_chars, 4, 200, 'max_chars')
    if mc > st['fit_chars']:
        warnings.append(f'max_chars {mc} exceeds the estimated fit {st["fit_chars"]} at this font size')
    pages = _paginate(_wrap(words, mc), max_lines)
    page = _int(page, 0, max(0, len(pages) - 1), 'page')
    lines = [[(words[i], None) for i in ln] for ln in pages[page]]
    svg, w2 = _draw_caption(lines, st, direction, 'rr-caption')
    meta = {'preset': st['preset'], 'page': page, 'page_count': len(pages), 'font_size': round(st['size'], 2),
            'max_chars': mc, 'lines': [' '.join(words[i] for i in ln if words[i]) for ln in pages[page]],
            'contrast': st['contrast'], 'safe_box': _rect(st['box']), 'warnings': warnings + w2,
            'shaping': SHAPING_NOTE}
    return svg, meta


def caption(words=None, preset='social_bold', width=1080, height=1920, **options):
    """Static burned caption (one page) as an SVG fragment using a preset."""
    svg, _ = _caption_core(words, preset, width, height, **options)
    return svg


def _karaoke_core(words_with_times=None, t=1.2, width=1080, height=1920, *, preset='social_bold',
                  platform=None, font_size=None, max_chars=None, max_lines=2, mode='current',
                  fill=None, highlight=None, position=None, direction='auto', linger=0.6, **extra):
    _no_extra(extra)
    tw = _timed_words(_EXAMPLE_TIMED if words_with_times is None else words_with_times)
    t = _num(t, -1e5, 1e5, 't')
    st = _caption_style(preset, width, height, platform, font_size, position, fill, highlight)
    max_lines = _int(max_lines, 1, 4, 'max_lines')
    mode = _choice(mode, {'current', 'progressive'}, 'mode')
    direction = _choice(direction, {'auto', 'rtl', 'ltr'}, 'direction')
    linger = _num(linger, 0, 10, 'linger')
    mc = st['max_chars'] if max_chars is None else _int(max_chars, 4, 200, 'max_chars')
    words = [w['word'] for w in tw]
    pages = _paginate(_wrap(words, mc), max_lines)
    spans = []
    for pg in pages:
        idx = [i for ln in pg for i in ln]
        spans.append((min(tw[i]['start'] for i in idx), max(tw[i]['end'] for i in idx)))
    meta = {'preset': st['preset'], 'mode': mode, 't': t, 'page_count': len(pages),
            'contrast': st['contrast'], 'font_size': round(st['size'], 2), 'max_chars': mc,
            'shaping': SHAPING_NOTE, 'page': None, 'current_index': None, 'current_word': None}
    cur_page = None
    for k, (s, e) in enumerate(spans):
        if s <= t:
            cur_page = k
    if cur_page is None:
        meta['visible'] = False
        return '', meta
    s, e = spans[cur_page]
    next_start = spans[cur_page + 1][0] if cur_page + 1 < len(spans) else None
    if t > e + linger and (next_start is None or t < next_start):
        meta['visible'] = False
        return '', meta
    current = None
    for ln in pages[cur_page]:
        for i in ln:
            if tw[i]['word'] and tw[i]['start'] <= t < tw[i]['end']:
                current = i
    lines = []
    for ln in pages[cur_page]:
        row = []
        for i in ln:
            w = tw[i]['word']
            col = None
            if i == current or (mode == 'progressive' and w and tw[i]['end'] <= t):
                col = st['highlight']
            row.append((w, col))
        lines.append(row)
    svg, warn = _draw_caption(lines, st, direction, 'rr-karaoke')
    meta.update({'visible': True, 'page': cur_page, 'page_span': [s, e], 'current_index': current,
                 'current_word': tw[current]['word'] if current is not None else None,
                 'lines': [' '.join(words[i] for i in ln if words[i]) for ln in pages[cur_page]],
                 'warnings': warn, 'safe_box': _rect(st['box'])})
    return svg, meta


def karaoke_caption(words_with_times=None, t=1.2, width=1080, height=1920, **options):
    """Caption page at time t with the current word (from the supplied timings) highlighted.
    Every word is one whole <text> placed with the module's word-level bidi order."""
    svg, _ = _karaoke_core(words_with_times, t, width, height, **options)
    return svg


def _ts(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def _srt_cues(words_with_times=None, max_chars=42, max_lines=2, min_duration=0.8, max_duration=7.0,
              rtl_marks=True, **extra):
    _no_extra(extra)
    tw = _timed_words(_EXAMPLE_TIMED if words_with_times is None else words_with_times)
    max_chars = _int(max_chars, 4, 200, 'max_chars')
    max_lines = _int(max_lines, 1, 4, 'max_lines')
    min_duration = _num(min_duration, 0, 10, 'min_duration')
    max_duration = _num(max_duration, 0.5, 60, 'max_duration')
    rtl_marks = _bool(rtl_marks, 'rtl_marks')
    words = [w['word'] for w in tw]
    pages = _paginate(_wrap(words, max_chars), max_lines)
    cues = []
    for pg in pages:
        idx = [i for ln in pg for i in ln if words[i]]
        if not idx:
            continue
        text_lines = []
        for ln in pg:
            txt = ' '.join(words[i] for i in ln if words[i])
            if not txt:
                continue
            if rtl_marks and _resolve_dir('auto', txt) == 'rtl':
                txt = '‏' + txt
            text_lines.append(txt)
        cues.append({'start': min(tw[i]['start'] for i in idx), 'end': max(tw[i]['end'] for i in idx),
                     'lines': text_lines})
    warnings = []
    for k, c in enumerate(cues):
        limit = cues[k + 1]['start'] - 0.001 if k + 1 < len(cues) else None
        end = max(c['end'], c['start'] + min_duration)
        if limit is not None:
            end = min(end, max(limit, c['end']))
        c['end'] = end
        if end - c['start'] > max_duration:
            warnings.append(f'cue {k + 1} lasts {end - c["start"]:.2f}s > max_duration {max_duration:g}s')
    return cues, warnings


def srt_from_timed_words(words_with_times=None, max_chars=42, max_lines=2, min_duration=0.8,
                         max_duration=7.0, rtl_marks=True, **extra):
    """SRT text built only from the supplied words; unclear (None/'') words are left out.
    rtl_marks prefixes RTL lines with U+200F (invisible) so players keep punctuation on the right side."""
    cues, _ = _srt_cues(words_with_times, max_chars, max_lines, min_duration, max_duration,
                        rtl_marks, **extra)
    blocks = [f'{k + 1}\n{_ts(c["start"])} --> {_ts(c["end"])}\n' + '\n'.join(c['lines'])
              for k, c in enumerate(cues)]
    return '\n\n'.join(blocks) + ('\n' if blocks else '')


def parse_srt(text):
    """Parse SRT text into cues [{index, start, end, text, text_clean, lines, direction}]."""
    if not isinstance(text, str):
        raise ValueError('srt text must be a string')
    if len(text) > MAX_SRT_CHARS:
        raise ValueError(f'srt text may have at most {MAX_SRT_CHARS} characters')
    text = text.lstrip('﻿').replace('\r\n', '\n').replace('\r', '\n')
    blocks = [b for b in re.split(r'\n[ \t]*\n', text.strip('\n')) if b.strip()]
    if len(blocks) > MAX_SRT_CUES:
        raise ValueError(f'srt may have at most {MAX_SRT_CUES} cues')
    cues = []
    for bi, block in enumerate(blocks):
        rows = block.split('\n')
        while rows and not rows[0].strip():
            rows.pop(0)
        index = None
        if rows and rows[0].strip().isdigit() and len(rows) > 1 and '-->' in rows[1]:
            index = int(rows[0].strip())
            rows = rows[1:]
        if not rows or '-->' not in rows[0]:
            raise ValueError(f'srt block {bi + 1}: missing "start --> end" timing line')
        m = _SRT_TIME_RE.match(rows[0])
        if not m:
            raise ValueError(f'srt block {bi + 1}: malformed timing line {rows[0]!r}')
        g = m.groups()

        def secs(h, mi, s, ms):
            if int(mi) > 59 or int(s) > 59:
                raise ValueError(f'srt block {bi + 1}: minutes/seconds must be < 60')
            return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, '0')) / 1000.0

        start, end = secs(*g[:4]), secs(*g[4:])
        if end < start:
            raise ValueError(f'srt block {bi + 1}: end before start')
        lines = [r for r in rows[1:]]
        while lines and not lines[-1].strip():
            lines.pop()
        body = '\n'.join(lines)
        clean = ''.join(c for c in body if c not in _BIDI_CONTROLS)
        cues.append({'index': index, 'start': round(start, 3), 'end': round(end, 3), 'text': body,
                     'text_clean': clean, 'lines': lines,
                     'direction': _resolve_dir('auto', clean)})
    return cues


# --------------------------------------------------------------------------- lower third

def _lower_third_core(name='الوردة الحمراء', role='استوديو الطباعة الحركية', lang='auto', t=1.0,
                      duration=5.0, width=1920, height=1080, *, platform=None, name_size=None,
                      role_size=None, fill='#FFFFFF', role_fill='#E8E8E8', plate='#141414',
                      plate_opacity=0.9, accent='#C8102E', id_prefix='rr', **extra):
    _no_extra(extra)
    name = _norm_text(_str(name, 'name', 200))
    role = _norm_text(_str('' if role is None else role, 'role', 300, allow_empty=True))
    lang = _choice(lang, {'auto', 'ar', 'en'}, 'lang')
    t = _num(t, -1e5, 1e5, 't')
    duration = _num(duration, 1.2, 600, 'duration')
    width = _int(width, 64, 8192, 'width')
    height = _int(height, 64, 8192, 'height')
    if platform is not None:
        platform = _choice(platform, PLATFORMS, 'platform')
    fill = _color(fill, 'fill')
    role_fill = _color(role_fill, 'role_fill')
    plate = _color(plate, 'plate')
    plate_opacity = _num(plate_opacity, 0.6, 1.0, 'plate_opacity')
    accent = _color(accent, 'accent')
    id_prefix = _id(id_prefix)
    d = _resolve_dir('auto', name + ' ' + role) if lang == 'auto' else ('rtl' if lang == 'ar' else 'ltr')
    x0, y0, x1, y1 = _safe_box(width, height, platform)
    auto_n, auto_r = name_size is None, role_size is None
    ns = _font_size(name_size, height, 0.05, 'name_size')
    rs = _font_size(role_size, height, 0.036, 'role_size')
    warnings = []
    bar = max(4.0, ns * 0.14)
    for _ in range(12):
        pad = ns * 0.55
        wn = _text_width(name, ns)
        wr = _text_width(role, rs) if role else 0.0
        maxw = (x1 - x0) * 0.9 - bar - 2 * pad
        if max(wn, wr) <= maxw:
            break
        shrunk = False
        if auto_n and ns * 0.92 >= height * MIN_BODY_FRAC:
            ns = round(ns * 0.92, 2)
            shrunk = True
        if auto_r and rs * 0.92 >= height * MIN_BODY_FRAC:
            rs = round(rs * 0.92, 2)
            shrunk = True
        if not shrunk:
            break
        bar = max(4.0, ns * 0.14)
    pad = ns * 0.55
    wn = _text_width(name, ns)
    wr = _text_width(role, rs) if role else 0.0
    maxw = (x1 - x0) * 0.9 - bar - 2 * pad
    if max(wn, wr) > maxw:
        warnings.append('name/role estimated wider than the safe area; shorten them')
    c1 = _check_contrast(fill, plate, plate_opacity, None, 0, ns, 'fill')
    c2 = _check_contrast(role_fill, plate, plate_opacity, None, 0, rs, 'role_fill') if role else None
    meta = {'direction': d, 'side': 'right' if d == 'rtl' else 'left', 'name': name, 'role': role,
            'name_size': round(ns, 2), 'role_size': round(rs, 2),
            'contrast': {'name': c1, 'role': c2}, 'warnings': warnings, 't': t, 'duration': duration,
            'safe_box': _rect((x0, y0, x1, y1)), 'shaping': SHAPING_NOTE}
    if t < 0 or t > duration:
        meta['visible'] = False
        return '', meta
    pw = min(max(wn, wr), maxw) + 2 * pad
    ph = pad * 1.4 + ns * 1.3 + (rs * 1.45 if role else 0.0)
    bottom = y1
    top = bottom - ph
    k_out = _ease_out(_clamp((duration - t) / 0.45))
    kb = _ease_out(_clamp(t / 0.3)) * k_out
    kp = _ease_out(_clamp((t - 0.12) / 0.45)) * k_out
    k_name = _ease_out(_clamp((t - 0.25) / 0.45)) * k_out
    k_role = _ease_out(_clamp((t - 0.4) / 0.45)) * k_out
    sgn = -1.0 if d == 'rtl' else 1.0           # outward direction from the accent bar
    if d == 'rtl':
        bar_x = x1 - bar
        px1 = bar_x
        px0 = px1 - pw * kp
        text_x = bar_x - pad
    else:
        bar_x = x0
        px0 = x0 + bar
        px1 = px0 + pw * kp
        text_x = px0 + pad
    if kb <= 0.001 and kp <= 0.001:
        meta['visible'] = False
        return '', meta
    cid = f'{id_prefix}-lt-clip'
    parts = [f'<g class="rr-lower-third" data-direction="{d}">',
             f'<defs><clipPath id="{cid}"><rect x="{_f(px0)}" y="{_f(top)}" width="{_f(max(0.0, px1 - px0))}" '
             f'height="{_f(ph)}"/></clipPath></defs>']
    if kp > 0.001:
        parts.append(f'<rect x="{_f(px0)}" y="{_f(top)}" width="{_f(px1 - px0)}" height="{_f(ph)}" '
                     f'fill="{plate}" fill-opacity="{_f(plate_opacity, 3)}"/>')
    if kb > 0.001:
        bh = ph * kb
        parts.append(f'<rect x="{_f(bar_x)}" y="{_f(top + (ph - bh) / 2)}" width="{_f(bar)}" '
                     f'height="{_f(bh)}" fill="{accent}"/>')
    name_bl = top + pad * 0.7 + ns * 1.0
    role_bl = name_bl + rs * 1.45
    texts = []
    # text-anchor="middle" at the estimated centre: 'start' is the right edge for rtl in browsers
    # but the left edge in CairoSVG, which pushed Arabic names off the card.
    def centre(width_est):
        return text_x + sgn * width_est / 2
    if k_name > 0.001:
        dx = -sgn * (1 - k_name) * ns * 0.9
        texts.append(f'<text x="{_f(centre(wn) + dx)}" y="{_f(name_bl)}" text-anchor="middle" direction="{d}" '
                     f'unicode-bidi="embed"{_lang_attr(d, name)} font-size="{_f(ns)}" font-weight="700" '
                     f'fill="{fill}" opacity="{_f(min(1.0, k_name), 3)}">{_esc(name)}</text>')
    if role and k_role > 0.001:
        dx = -sgn * (1 - k_role) * rs * 0.9
        texts.append(f'<text x="{_f(centre(wr) + dx)}" y="{_f(role_bl)}" text-anchor="middle" direction="{d}" '
                     f'unicode-bidi="embed"{_lang_attr(d, role)} font-size="{_f(rs)}" font-weight="400" '
                     f'fill="{role_fill}" opacity="{_f(min(1.0, k_role), 3)}">{_esc(role)}</text>')
    if texts:
        parts.append(f'<g clip-path="url(#{cid})" font-family="{FONT_STACK}">' + ''.join(texts) + '</g>')
    parts.append('</g>')
    meta['visible'] = True
    meta['plate_box'] = [round(min(px0, px1), 1), round(top, 1), round(abs(px1 - px0), 1), round(ph, 1)]
    return ''.join(parts), meta


def lower_third(name='الوردة الحمراء', role='استوديو الطباعة الحركية', lang='auto', t=1.0, **options):
    """Animated name card. Arabic (rtl) sits on the right with the accent bar on the right edge and
    slides out leftwards; Latin (ltr) mirrors it on the left. In/out animated inside `duration`."""
    svg, _ = _lower_third_core(name, role, lang, t, **options)
    return svg


# --------------------------------------------------------------------------- text catalogue

def _catalogue(catalogue):
    if not isinstance(catalogue, dict) or not catalogue:
        raise ValueError('catalogue must be a non-empty dict {key: {lang: text}}')
    if len(catalogue) > 500:
        raise ValueError('catalogue may have at most 500 keys')
    for key, entry in catalogue.items():
        if not isinstance(key, str) or not isinstance(entry, dict) or not entry:
            raise ValueError('catalogue entries must be {key: {lang: text}}')
        for lg, txt in entry.items():
            if not isinstance(lg, str) or not re.match(r'^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$', lg):
                raise ValueError(f'catalogue[{key!r}] has a bad language code {lg!r}')
            if not isinstance(txt, str) or len(txt) > MAX_TEXT:
                raise ValueError(f'catalogue[{key!r}][{lg!r}] must be a string <= {MAX_TEXT} chars')
    return catalogue


def localize(catalogue, lang, **extra):
    """Resolve every key of a {key: {lang: text}} catalogue for one language.
    A missing translation raises: the module never invents or machine-translates text."""
    _no_extra(extra)
    catalogue = _catalogue(catalogue)
    if not isinstance(lang, str):
        raise ValueError('lang must be a string')
    out = {}
    for key, entry in catalogue.items():
        if lang not in entry:
            raise ValueError(f'catalogue key {key!r} has no {lang!r} text (no text is invented)')
        txt = _norm_text(entry[lang])
        out[key] = {'text': txt, 'lang': lang, 'direction': _resolve_dir('auto', txt)}
    return out


def _resolve_keys(params, catalogue, lang):
    out = {}
    for k, v in params.items():
        if isinstance(k, str) and k.endswith('_key'):
            target = k[:-4]
            if target in params:
                raise ValueError(f'give either {target} or {k}, not both')
            if not isinstance(v, str) or v not in catalogue:
                raise ValueError(f'{k} {v!r} is not in the catalogue')
            if lang not in catalogue[v]:
                raise ValueError(f'catalogue key {v!r} has no {lang!r} text (no text is invented)')
            out[target] = catalogue[v][lang]
        else:
            out[k] = v
    return out


# --------------------------------------------------------------------------- timeline layer

LAYER_OPS = ('kinetic_text', 'caption', 'karaoke', 'lower_third')


def _layer(op, params, t, width, height):
    if not isinstance(op, str) or op not in LAYER_OPS:
        raise ValueError(f'layer op must be one of {list(LAYER_OPS)}')
    if params is None:
        params = {}
    if not isinstance(params, dict) or len(params) > MAX_PARAMS:
        raise ValueError(f'params must be a dict with at most {MAX_PARAMS} keys')
    if not all(isinstance(k, str) for k in params):
        raise ValueError('param names must be strings')
    for k in ('t', 'width', 'height'):
        if k in params:
            raise ValueError(f'{k} is supplied by the timeline, not by layer params')
    t = _num(t, -1e5, 1e5, 't')
    width = _int(width, 64, 8192, 'width')
    height = _int(height, 64, 8192, 'height')
    p = dict(params)
    start = _num(p.pop('start', 0.0), -1e5, 1e5, 'start')
    catalogue = p.pop('catalogue', None)
    clang = p.pop('catalogue_lang', None)
    if catalogue is not None or any(k.endswith('_key') for k in p):
        if catalogue is None or clang is None:
            raise ValueError('*_key params need catalogue and catalogue_lang')
        p = _resolve_keys(p, _catalogue(catalogue), clang)
        if op == 'lower_third' and 'lang' not in p:
            p['lang'] = 'ar' if clang.split('-')[0].lower() == 'ar' else 'auto'
    local = t - start
    if op == 'kinetic_text':
        return _kinetic_core(t=local, width=width, height=height, **p)
    if op == 'lower_third':
        return _lower_third_core(t=local, width=width, height=height, **p)
    if op == 'karaoke':
        return _karaoke_core(t=local, width=width, height=height, **p)
    dur = p.pop('duration', None)
    if dur is not None:
        dur = _num(dur, 0.05, 86400, 'duration')
        if local < 0 or local > dur:
            return '', {'visible': False}
    svg, meta = _caption_core(width=width, height=height, **p)
    meta['visible'] = True
    return svg, meta


def render_layer(op, params, t, width, height):
    """Timeline hook: SVG fragment of one layer at absolute time t ('' when not visible).

    op: 'kinetic_text' | 'caption' | 'karaoke' | 'lower_third'. params are that
    function's options plus optional 'start' (layer offset, s) and, for text
    catalogues, 'catalogue' + 'catalogue_lang' with '<param>_key' entries
    (e.g. text_key, name_key, role_key, words_key). caption accepts 'duration'."""
    svg, _ = _layer(op, params, t, width, height)
    return svg


_DEFAULT_CATALOGUE = {
    'title': {'ar': 'الوردة الحمراء', 'en': 'The Red Rose'},
    'role': {'ar': 'استوديو الطباعة الحركية', 'en': 'Kinetic Type Studio'},
}
_DEFAULT_TIMELINE = [
    {'op': 'kinetic_text', 'start': 0.0,
     'params': {'text_key': 'title', 'style': 'fade_up', 'duration': 3.0, 'position': 'upper'}},
    {'op': 'lower_third', 'start': 0.5, 'params': {'name_key': 'title', 'role_key': 'role', 'duration': 4.0}},
]


def render_catalogue_timeline(catalogue=None, timeline=None, langs=('ar', 'en'), t=1.5, platform='youtube',
                              **extra):
    """Same timeline rendered once per language: strings come from the catalogue, direction follows the text."""
    _no_extra(extra)
    catalogue = _catalogue(_DEFAULT_CATALOGUE if catalogue is None else catalogue)
    timeline = _DEFAULT_TIMELINE if timeline is None else timeline
    if not isinstance(timeline, (list, tuple)) or not timeline or len(timeline) > 64:
        raise ValueError('timeline must be a list of 1..64 layers {op, start, params}')
    if not isinstance(langs, (list, tuple)) or not langs or len(langs) > 12:
        raise ValueError('langs must be a list of 1..12 language codes')
    platform = _choice(platform, PLATFORMS, 'platform')
    w, h = PLATFORMS[platform]['width'], PLATFORMS[platform]['height']
    out = []
    for lg in langs:
        if not isinstance(lg, str):
            raise ValueError('language codes must be strings')
        layers = []
        frag = []
        for i, layer in enumerate(timeline):
            if not isinstance(layer, dict) or set(layer) - {'op', 'start', 'params'} or 'op' not in layer:
                raise ValueError(f'timeline[{i}] must be {{op, start, params}}')
            params = dict(layer.get('params') or {})
            params['start'] = layer.get('start', 0.0)
            params['catalogue'] = catalogue
            params['catalogue_lang'] = lg
            svg, meta = _layer(layer['op'], params, t, w, h)
            frag.append(svg)
            layers.append({'op': layer['op'], 'visible': bool(meta.get('visible')),
                           'direction': meta.get('direction')})
        out.append({'lang': lg, 'layers': layers,
                    'svg': f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                           f'viewBox="0 0 {w} {h}">' + ''.join(frag) + '</svg>'})
    return {'platform': platform, 'width': w, 'height': h, 't': t, 'renders': out}


# --------------------------------------------------------------------------- run() ops

_COMMON_ASSUMPTIONS = [
    SHAPING_NOTE,
    'Arabic words are never split into per-letter elements; only whole words/phrases animate',
    'text widths are estimated from character classes (no font metrics); real fonts may differ by ~10-20%',
    f'font-family stack: {FONT_STACK}',
]


def _op_kinetic_text(document=False, background='#000000', **params):
    document = _bool(document, 'document')
    background = _color(background, 'background')
    svg, meta = _kinetic_core(**params)
    meta['svg'] = svg
    if document:
        w = params.get('width', 1080)
        h = params.get('height', 1920)
        meta['document'] = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                            f'viewBox="0 0 {w} {h}"><rect x="0" y="0" width="{w}" height="{h}" '
                            f'fill="{background}"/>{svg}</svg>')
    return _pack('kinetic_text', meta, _COMMON_ASSUMPTIONS + [
        'mixed Arabic/English word order uses a word-level bidi model (W2/W7/N1/N2/I1/I2/L2); '
        'each word keeps its own direction attribute, strings are never reversed',
        'glitch_words and held_frames use a seeded integer hash: same seed -> same frames',
        'word_timings are each word\'s reveal window (start = can first be seen, end = fully shown); '
        'the exit fade is not included',
        'outlines are a separate text copy under the fill (renderers that ignore paint-order still '
        'show the fill)'],
        [f'text <= {MAX_TEXT} chars and <= {MAX_WORDS} words', 'duration 0.2-600 s, max_lines 1-8',
         'font_size >= 3.5% of frame height; contrast >= 4.5 against plate (worst case) or stroke',
         'title-safe 90% box (intersected with platform UI margins when platform is set)',
         'document=True adds result.document: a standalone <svg> with width/height and a '
         'background rect (background is used only then)'])


def _op_wrap_caption(**params):
    return _pack('wrap_caption', wrap_caption(**params), [
        'balanced breaking: minimum sum of squared line slack, penalty for ending a line on a short '
        'function word (Arabic/English list)',
        'character count ignores harakat and joiners; lines are broken in logical order so RTL works',
        'None/\'\' words are kept as empty slots, never filled in'],
        ['max_chars 4-200, max_lines 1-6, at most 400 words', 'a single word longer than max_chars '
         'gets its own line and is flagged overlong (never split)'])


def _op_karaoke_caption(**params):
    svg, meta = _karaoke_core(**params)
    meta['svg'] = svg
    return _pack('karaoke_caption', meta, _COMMON_ASSUMPTIONS + [
        'timings come only from the caller; the current word is start <= t < end',
        'a page shows from its first word start until the next page starts (or last end + linger)',
        'each word is one whole <text> (anchor middle) placed by a word-level bidi model'],
        [f'at most {MAX_TIMED} timed words', 'presets: ' + ', '.join(PRESETS),
         'contrast of fill and highlight >= 4.5 against plate (worst case) or stroke'])


def _op_srt(srt_text=None, **params):
    if srt_text is not None:
        if params:
            raise ValueError('give srt_text alone to parse, or timed-word params to build')
        cues = parse_srt(srt_text)
        return _pack('srt', {'mode': 'parse', 'cues': cues, 'cue_count': len(cues)},
                     ['SRT timing "HH:MM:SS,mmm --> HH:MM:SS,mmm" (dot accepted); optional numeric index line',
                      'text_clean removes bidi control marks; text keeps them as supplied'],
                     [f'<= {MAX_SRT_CHARS} chars and <= {MAX_SRT_CUES} cues'])
    cues, warnings = _srt_cues(**params)
    srt = srt_from_timed_words(**params)
    return _pack('srt', {'mode': 'build', 'srt': srt, 'cue_count': len(cues),
                         'round_trip': parse_srt(srt), 'warnings': warnings},
                 ['cues = caption pages from wrap_caption; cue start/end from the first/last supplied word',
                  'cues are extended to min_duration without overlapping the next cue',
                  'unclear words (None/\'\') are omitted; no text is invented',
                  'rtl_marks adds an invisible U+200F at the start of RTL lines'],
                 ['max_chars 4-200, max_lines 1-4, min_duration 0-10 s',
                  'over-long cues are reported in warnings, not split'])


def _op_lower_third(**params):
    svg, meta = _lower_third_core(**params)
    meta['svg'] = svg
    return _pack('lower_third', meta, _COMMON_ASSUMPTIONS + [
        'Arabic (rtl): card on the right, accent bar on the right edge, text slides out leftwards; '
        'Latin mirrors it on the left',
        'in: bar 0-0.3 s, plate 0.12-0.57 s, name 0.25-0.7 s, role 0.4-0.85 s; out: last 0.45 s'],
        ['duration 1.2-600 s', 'name/role sizes >= 3.5% of frame height; contrast >= 4.5 on the plate',
         'plate_opacity 0.6-1.0'])


def _op_derive_canvas(**params):
    return _pack('derive_canvas', derive_canvas(**params), [
        'title-safe 90% and action-safe 93% of the frame (broadcast convention)',
        'platform UI margins are approximate overlays for captions/buttons; check the current app UI'],
        ['platforms: ' + ', '.join(PLATFORMS)])


def _op_list_styles(**params):
    _no_extra(params)
    return _pack('list_styles', {'styles': list_styles(), 'count': len(STYLES),
                                 'presets': [{'name': k, 'description_ar': v['desc_ar']}
                                             for k, v in PRESETS.items()]},
                 ['descriptions are one-line Arabic summaries'], ['read-only'])


def _op_caption(**params):
    svg, meta = _caption_core(**params)
    meta['svg'] = svg
    return _pack('caption', meta, _COMMON_ASSUMPTIONS + ['one page of wrap_caption drawn with a preset'],
                 ['presets: ' + ', '.join(PRESETS), 'max_lines 1-4'])


def _op_catalogue(**params):
    return _pack('catalogue', render_catalogue_timeline(**params), _COMMON_ASSUMPTIONS + [
        'one timeline, one render per language; strings from the catalogue, direction from each string',
        'a missing translation raises an error instead of inventing text'],
        ['<= 64 layers, <= 12 languages, <= 500 catalogue keys'])


def _named(impl, doc, *sources, extra=(), drop=()):
    """Op callable with keyword-only named parameters taken from the source functions' signatures
    (defaults included), a one-line docstring and an 'allowed: ...' guard for unknown names."""
    params, seen = [], set()
    for src in sources:
        for q in inspect.signature(src).parameters.values():
            if q.kind is inspect.Parameter.VAR_KEYWORD or q.name in seen or q.name in drop:
                continue
            seen.add(q.name)
            params.append(q.replace(kind=inspect.Parameter.KEYWORD_ONLY))
    for name, default in extra:
        params.append(inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=default))
    names = tuple(q.name for q in params)

    @functools.wraps(impl)
    def op(**kwargs):
        _no_extra([k for k in kwargs if k not in names], allowed=names)
        return impl(**kwargs)
    op.__doc__ = doc
    op.__signature__ = inspect.Signature(params)
    op.allowed_params = names
    return op


OPS = {
    'kinetic_text': _op_kinetic_text,
    'wrap_caption': _op_wrap_caption,
    'karaoke_caption': _op_karaoke_caption,
    'srt': _op_srt,
    'lower_third': _op_lower_third,
    'derive_canvas': _op_derive_canvas,
    'list_styles': _op_list_styles,
    'caption': _op_caption,
    'catalogue': _op_catalogue,
}
OPS = {
    'kinetic_text': _named(_op_kinetic_text, 'Animated kinetic title (SVG <g>, optional full <svg> document) '
                           'with per-word reveal timings at time t.', _kinetic_core,
                           extra=(('document', False), ('background', '#000000'))),
    'wrap_caption': _named(_op_wrap_caption, 'Break words into caption lines and pages without '
                           'splitting any word.', wrap_caption),
    'karaoke_caption': _named(_op_karaoke_caption, 'Caption page at time t with the current word '
                              '(from supplied timings) highlighted.', _karaoke_core),
    'srt': _named(_op_srt, 'Build SRT from supplied timed words, or parse srt_text into cues.',
                  _op_srt, _srt_cues),
    'lower_third': _named(_op_lower_third, 'Animated name/role card (RTL on the right, LTR on the '
                          'left) at time t.', _lower_third_core),
    'derive_canvas': _named(_op_derive_canvas, 'Frame size, fps and safe areas for a delivery '
                            'platform.', derive_canvas),
    'list_styles': _named(_op_list_styles, 'List the kinetic text styles and caption presets with '
                          'Arabic descriptions.'),
    'caption': _named(_op_caption, 'Static burned caption page (SVG) drawn with a preset.', _caption_core),
    'catalogue': _named(_op_catalogue, 'Render one text timeline once per language from a '
                        '{key: {lang: text}} catalogue.', render_catalogue_timeline),
}


def run(op, params=None):
    """Validate and dispatch: run('kinetic_text', {'style': 'pop_scale'}) -> {'op','result','assumptions','limits'}."""
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
