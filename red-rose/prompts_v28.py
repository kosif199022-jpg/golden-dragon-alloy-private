"""Red Rose V28: preparation layer for paid / external generation services.

Original re-implementation of the ideas behind the legacy families GEN, AMEDIA,
SUNO, GEMINI, PROMPT, FUTUREPEDIA and PROMPTSMOTION. Pure standard-library
Python. No file I/O, no subprocess, no network, no printing; deterministic.

This module NEVER calls any service. It only:
  * prepares prompts (image, video, music, voice) in layered, inspectable form,
  * screens them against a blocklist of protected character / franchise /
    living-artist names and suggests neutral style descriptors instead,
  * estimates cost from a price table the CALLER supplies (Decimal arithmetic),
  * builds an approval request that the owner must explicitly approve in chat.
There is deliberately no op (and no field) that can mark a request approved.

Interface mirrors physics_v20: OPS + run(op, params) returning
{'op', 'result', 'assumptions', 'limits'}; strict ValueError validation and
rejection of unknown parameter names (**extra).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

MAX_PARAMS = 24
MAX_TEXT = 2_000
MAX_LIST = 200
MAX_SHOTS = 60
MAX_SCRIPT = 5_000
MAX_LYRICS = 8_000

NO_SERVICE_LIMIT = 'prepares data only: no network, no service call, no money spent'

# --------------------------------------------------------------------------- style library (40, neutral terms)

STYLES = (
    # id, category, name, Arabic description, prompt fragment
    ('natural_window_portrait', 'photo', 'Window-light portrait',
     'بورتريه بضوء شباك طبيعي جانبي ناعم وملمس بشرة حقيقي',
     'soft side window light, natural skin texture, shallow depth of field'),
    ('golden_hour_documentary', 'photo', 'Golden-hour documentary',
     'تصوير وثائقي وقت الغروب بضوء دافئ منخفض',
     'documentary photo, low warm golden-hour sun, long soft shadows, candid moment'),
    ('overcast_street', 'photo', 'Overcast street',
     'شارع بإضاءة سما مغيّمة ناعمة من غير ظلال حادة',
     'overcast diffuse daylight, muted colours, candid street photography'),
    ('high_key_studio_product', 'photo', 'High-key studio product',
     'تصوير منتج في استوديو بخلفية فاتحة وإضاءة عالية',
     'high-key studio product shot, seamless light background, soft box lighting, crisp edges'),
    ('low_key_chiaroscuro', 'photo', 'Low-key chiaroscuro',
     'إضاءة درامية غامقة بتباين قوي بين النور والضل',
     'low-key lighting, strong chiaroscuro, single hard key light, deep shadows'),
    ('macro_detail', 'photo', 'Macro detail',
     'لقطة ماكرو قريبة جدًا لتفاصيل الخامة',
     'macro photography, extreme close detail, very shallow focus plane'),
    ('aerial_topdown', 'photo', 'Aerial top-down',
     'لقطة من فوق لتحت كأنها من طيارة درون',
     'aerial top-down view, graphic shapes, long shadows, drone perspective'),
    ('night_neon_street', 'photo', 'Night neon street',
     'شارع بالليل بلافتات نيون وأرض مبلولة عاكسة',
     'night street, coloured neon signage, wet reflective pavement, high contrast'),
    ('film_grain_35mm', 'photo', 'Analog 35mm look',
     'شكل فيلم 35 مم قديم بحبيبات ناعمة',
     'analog 35mm film look, fine grain, gentle highlight halation, slightly lifted colours'),
    ('bw_reportage', 'photo', 'Black and white reportage',
     'تصوير صحفي أبيض وأسود بتباين واضح',
     'black and white reportage photo, strong contrast, natural grain'),
    ('infrared_landscape', 'photo', 'False-colour infrared',
     'منظر طبيعي بألوان الأشعة تحت الحمرا وورق شجر فاتح',
     'false-colour infrared landscape, pale glowing foliage, dark sky'),
    ('miniature_tilt_shift', 'photo', 'Miniature tilt-shift',
     'لقطة بتخلّي المدينة شكلها ماكيت صغير',
     'tilt-shift miniature effect, narrow focus band, saturated toy-like scene'),
    ('anamorphic_widescreen', 'cinema', 'Anamorphic widescreen',
     'كادر سينما عريض بعدسة أنامورفيك ووهج عدسة أفقي خفيف',
     'anamorphic widescreen frame, oval bokeh, subtle horizontal lens flare, 2.39:1 feel'),
    ('handheld_verite', 'cinema', 'Handheld verite',
     'كاميرا محمولة باليد بإحساس واقعي قريب',
     'handheld camera, verite realism, natural available light, slight motion'),
    ('static_symmetric_frame', 'cinema', 'Static symmetric frame',
     'كادر ثابت متماثل في النص بألوان باستيل',
     'centered symmetrical composition, static locked-off camera, pastel palette, flat staging'),
    ('desert_epic_wide', 'cinema', 'Desert epic wide',
     'لقطة واسعة ملحمية في صحرا بأفق بعيد',
     'epic extreme wide shot, vast desert, tiny figure, heat haze on horizon'),
    ('practical_lit_interior', 'cinema', 'Practical-lit interior',
     'مكان داخلي منوّر بلمبات المكان نفسه بإحساس دافي',
     'moody interior lit by practical lamps, warm pools of light, dark corners'),
    ('silhouette_backlight', 'cinema', 'Silhouette backlight',
     'ظل أسود للشخص قدام مصدر نور قوي',
     'strong backlight, full silhouette, rim light edge, clean shapes'),
    ('watercolor_wash', 'illustration', 'Watercolor wash',
     'رسم ألوان مائية بطبقات شفافة وورق باين',
     'loose watercolor wash, transparent layered pigment, visible paper texture'),
    ('ink_line_drawing', 'illustration', 'Ink line drawing',
     'رسم بالحبر بخطوط واضحة من غير ألوان',
     'fine ink line drawing, hatching for shadows, white paper'),
    ('flat_vector_geometric', 'graphic', 'Flat vector geometric',
     'رسم فيكتور مسطح بأشكال هندسية بسيطة',
     'flat vector illustration, simple geometric shapes, limited colour palette, no gradients'),
    ('paper_cutout_layers', 'illustration', 'Paper cut-out layers',
     'طبقات ورق مقصوص فوق بعض بظلال خفيفة',
     'layered paper cut-out, soft drop shadows between layers, craft texture'),
    ('linocut_print', 'illustration', 'Linocut print',
     'طباعة حفر على اللينو بخطوط خشنة ولونين',
     'linocut print, bold carved lines, two-colour ink, rough edges'),
    ('gouache_poster', 'illustration', 'Gouache poster',
     'بوستر مرسوم بألوان جواش مطفية',
     'matte gouache painting, flat opaque colour areas, poster composition'),
    ('pencil_storyboard', 'illustration', 'Pencil storyboard',
     'رسم ستوري بورد بالقلم الرصاص سريع',
     'rough pencil storyboard frame, quick gestural lines, grey shading'),
    ('cel_shaded_2d', 'animation', 'Cel-shaded 2D animation',
     'أنيميشن 2D بخطوط خارجية واضحة وتلوين مسطح',
     'clean 2D cel-shaded animation, bold outlines, flat colour fills, simple shadows'),
    ('painterly_animation_background', 'animation', 'Painterly animation background',
     'خلفية أنيميشن مرسومة باليد بسحاب غني وضوء ناعم',
     'hand-painted 2D animation background, lush clouds, soft natural light, pastoral detail'),
    ('isometric_diorama', '3d', 'Isometric diorama',
     'ماكيت ثلاثي الأبعاد بزاوية أيزومتريك',
     'isometric 3D diorama, cut-away base, soft global illumination'),
    ('clay_stop_motion_look', '3d', 'Clay stop-motion look',
     'شخصيات صلصال كأنها أنيميشن إيقاف حركة',
     'handmade clay characters, visible fingerprints, stop-motion miniature set'),
    ('soft_stylized_3d', '3d', 'Soft stylized 3D',
     'شخصيات 3D مدوّرة ناعمة بإضاءة استوديو لطيفة',
     'rounded stylized 3D characters, soft subsurface materials, gentle studio lighting'),
    ('low_poly_3d', '3d', 'Low-poly 3D',
     'مجسمات 3D قليلة الأضلاع بألوان مسطحة',
     'low-poly 3D, faceted flat-shaded surfaces, simple palette'),
    ('photoreal_cg_product', '3d', 'Photoreal CG product',
     'منتج 3D واقعي جدًا بخامات دقيقة وانعكاسات',
     'photoreal CG product render, accurate materials, studio HDRI reflections'),
    ('islamic_geometric_pattern', 'graphic', 'Geometric star pattern',
     'زخرفة هندسية إسلامية بنجوم متشابكة',
     'interlaced geometric star pattern, tiled symmetry, precise linework'),
    ('arabic_calligraphic_ornament', 'graphic', 'Calligraphic ornament',
     'زخرفة بروح الخط العربي كملمس من غير كلام مقروء',
     'flowing Arabic calligraphic strokes as abstract ornament, no legible words'),
    ('mashrabiya_light_shadow', 'graphic', 'Lattice light and shadow',
     'ضل وشبابيك مشربية على الحيطة والأرض',
     'carved wooden lattice casting patterned light and shadow, warm afternoon'),
    ('retro_halftone_print', 'graphic', 'Retro halftone print',
     'طباعة قديمة بنقط هاف تون وألوان باهتة',
     'retro print, halftone dots, slight misregistration, aged paper'),
    ('duotone_poster', 'graphic', 'Duotone poster',
     'بوستر بلونين بس وتباين قوي',
     'duotone poster, two-ink palette, high contrast, bold crop'),
    ('swiss_grid_typographic', 'graphic', 'Swiss grid layout',
     'تصميم على شبكة صارمة بمساحات بيضا واسعة',
     'strict modular grid layout, generous white space, asymmetric balance'),
    ('oil_impasto', 'painting', 'Oil impasto',
     'لوحة زيت بطبقات سميكة وضربات فرشة باينة',
     'thick impasto oil paint, visible brush strokes, rich texture'),
    ('charcoal_sketch', 'painting', 'Charcoal sketch',
     'اسكتش فحم بتدرجات رمادي ولطخ',
     'charcoal sketch, smudged tonal values, expressive marks, toned paper'),
)
STYLE_INDEX = {s[0]: s for s in STYLES}

# --------------------------------------------------------------------------- default blocklist

# term -> neutral style ids to recommend instead. Living artists and protected
# characters / franchises only; the caller can add more via `blocklist`.
DEFAULT_BLOCKLIST = {
    'mickey mouse': ('cel_shaded_2d', 'soft_stylized_3d'),
    'disney': ('soft_stylized_3d', 'cel_shaded_2d'),
    'pixar': ('soft_stylized_3d', 'clay_stop_motion_look'),
    'studio ghibli': ('painterly_animation_background', 'watercolor_wash'),
    'ghibli': ('painterly_animation_background', 'watercolor_wash'),
    'miyazaki': ('painterly_animation_background', 'watercolor_wash'),
    'makoto shinkai': ('painterly_animation_background', 'golden_hour_documentary'),
    'spider man': ('cel_shaded_2d', 'retro_halftone_print'),
    'spiderman': ('cel_shaded_2d', 'retro_halftone_print'),
    'batman': ('low_key_chiaroscuro', 'retro_halftone_print'),
    'superman': ('retro_halftone_print', 'cel_shaded_2d'),
    'marvel': ('retro_halftone_print', 'cel_shaded_2d'),
    'pokemon': ('soft_stylized_3d', 'flat_vector_geometric'),
    'pikachu': ('soft_stylized_3d', 'flat_vector_geometric'),
    'harry potter': ('practical_lit_interior', 'oil_impasto'),
    'star wars': ('desert_epic_wide', 'anamorphic_widescreen'),
    'darth vader': ('silhouette_backlight', 'low_key_chiaroscuro'),
    'greg rutkowski': ('oil_impasto', 'painterly_animation_background'),
    'wes anderson': ('static_symmetric_frame',),
    'amr diab': (),
    'taylor swift': (),
    'beyonce': (),
    'ميكي ماوس': ('cel_shaded_2d', 'soft_stylized_3d'),
    'ديزني': ('soft_stylized_3d', 'cel_shaded_2d'),
    'بيكسار': ('soft_stylized_3d', 'clay_stop_motion_look'),
    'جيبلي': ('painterly_animation_background', 'watercolor_wash'),
    'ميازاكي': ('painterly_animation_background', 'watercolor_wash'),
    'سبايدر مان': ('cel_shaded_2d', 'retro_halftone_print'),
    'باتمان': ('low_key_chiaroscuro', 'retro_halftone_print'),
    'سوبرمان': ('retro_halftone_print', 'cel_shaded_2d'),
    'مارفل': ('retro_halftone_print', 'cel_shaded_2d'),
    'بوكيمون': ('soft_stylized_3d', 'flat_vector_geometric'),
    'بيكاتشو': ('soft_stylized_3d', 'flat_vector_geometric'),
    'هاري بوتر': ('practical_lit_interior', 'oil_impasto'),
    'حرب النجوم': ('desert_epic_wide', 'anamorphic_widescreen'),
    'عمرو دياب': (),
    'تايلور سويفت': (),
}
FALLBACK_STYLES = ('film_grain_35mm', 'watercolor_wash', 'soft_stylized_3d')
MUSIC_ADVICE_AR = ('بدل اسم الفنان: اوصف النوع والعصر والسرعة والآلات وطبقة الصوت '
                   '(مثلًا: بوب مصري تسعيناتي، 100 BPM، طبلة وكمان، صوت رجالي دافي).')

# --------------------------------------------------------------------------- validation helpers

_ARABIC_RE = re.compile('[؀-ۿ]')
_TASHKEEL_RE = re.compile('[ً-ْٰـ]')
_NON_WORD_RE = re.compile(r'[^\w]+', re.UNICODE)
_CURRENCY_RE = re.compile(r'^[A-Z][A-Z_]{1,11}$')


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


def _text(value, name, max_len=MAX_TEXT, *, required=True, strip=True):
    """String validation. strip=False keeps owner text byte-for-byte."""
    if value is None and not required:
        return ''
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    out = value.strip() if strip else value
    if required and not out.strip():
        raise ValueError(f'{name} must not be empty')
    if len(out) > max_len:
        raise ValueError(f'{name} must be at most {max_len} characters')
    if any((ord(c) < 32 and c not in '\n\t\r') or ord(c) == 127 for c in out):
        raise ValueError(f'{name} contains control characters')
    return out


def _str_list(value, name, *, max_items=MAX_LIST, max_len=300, min_items=0):
    if not isinstance(value, (list, tuple)):
        raise ValueError(f'{name} must be a list of strings')
    if not min_items <= len(value) <= max_items:
        raise ValueError(f'{name} must have {min_items}..{max_items} items')
    return [_text(v, f'{name}[{i}]', max_len) for i, v in enumerate(value)]


def _dict(value, name):
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ValueError(f'{name} must be an object with string keys')
    return value


def _check_keys(item, allowed, required, name):
    unknown = set(item) - set(allowed)
    if unknown:
        raise ValueError(f'{name}: unknown key(s): ' + ', '.join(sorted(unknown)))
    missing = [k for k in required if k not in item]
    if missing:
        raise ValueError(f'{name}: missing key(s): ' + ', '.join(missing))


def _dec(value, name, low, high, *, low_open=False):
    """Decimal from int / decimal string / finite float (via its shortest repr)."""
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a number or decimal string')
    if isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f'{name} must be finite')
        d = Decimal(repr(value))
    elif isinstance(value, str):
        s = value.strip()
        if not s or len(s) > 40:
            raise ValueError(f'{name} must be a short decimal string')
        try:
            d = Decimal(s)
        except InvalidOperation as exc:
            raise ValueError(f'{name} is not a valid decimal: {value!r}') from exc
    else:
        raise ValueError(f'{name} must be a number or decimal string')
    if not d.is_finite():
        raise ValueError(f'{name} must be finite')
    if d < low or d > high or (low_open and d <= low):
        bracket = '(' if low_open else '['
        raise ValueError(f'{name} must be in {bracket}{low}, {high}]')
    return d


def _dstr(d):
    """Plain decimal string without exponent and without trailing zeros."""
    s = format(d.normalize(), 'f')
    return '0' if s in ('-0', '') else s


def _currency(value, name):
    cur = _text(value, name, 12).upper()
    if not _CURRENCY_RE.match(cur):
        raise ValueError(f'{name} must be a currency code like USD, EGP or CREDITS')
    return cur


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


# --------------------------------------------------------------------------- blocklist screening

def _norm(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    text = _TASHKEEL_RE.sub('', text)
    text = (text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
            .replace('ى', 'ي').replace('ة', 'ه'))
    return ' ' + _NON_WORD_RE.sub(' ', text).strip() + ' '


def _blocklist(value):
    """Defaults are always active; the caller can only ADD terms."""
    table = dict(DEFAULT_BLOCKLIST)
    if value is not None:
        for term in _str_list(value, 'blocklist', max_len=80):
            table.setdefault(term, ())
    compiled = []
    for term, styles in table.items():
        n = _norm(term).strip()
        if n:
            compiled.append((term, n, bool(_ARABIC_RE.search(term)), styles))
    return compiled


def _screen(texts, compiled):
    """Return sorted blocked terms found in any of the texts.

    Latin terms match on word boundaries; Arabic terms match as substrings so
    attached prefixes (و، ب، ل، ك، ال) cannot hide them.
    """
    hits = {}
    for text in texts:
        if not text:
            continue
        n = _norm(text)
        for term, nterm, arabic, styles in compiled:
            found = (nterm in n) if arabic else (' ' + nterm + ' ' in n)
            if found:
                hits[term] = styles
    return dict(sorted(hits.items()))


def _style_card(sid):
    s = STYLE_INDEX[sid]
    return {'id': s[0], 'category': s[1], 'name': s[2], 'ar': s[3], 'fragment': s[4]}


def _refusal(hits, *, visual=True):
    recs = []
    for styles in hits.values():
        for sid in styles:
            if sid not in recs:
                recs.append(sid)
    if visual and not recs:
        recs = list(FALLBACK_STYLES)
    msg = ('الطلب فيه اسم محمي (شخصية أو سلسلة أو فنان حي): '
           + '، '.join(hits) + '. مش هجهّز برومبت بالاسم ده؛ استخدم وصف أسلوب محايد بداله.')
    out = {'status': 'refused', 'blocked_terms': list(hits), 'prompt': None,
           'message_ar': msg,
           'recommended_styles': [_style_card(s) for s in recs]}
    if not visual:
        out['advice_ar'] = MUSIC_ADVICE_AR
    return out


def _resolve_style(style, name='style'):
    """Style id from the library -> its card; any other text -> free fragment."""
    if style is None:
        return None, ''
    s = _text(style, name, 300, required=False)
    if not s:
        return None, ''
    if s in STYLE_INDEX:
        return s, STYLE_INDEX[s][4]
    return None, s


# --------------------------------------------------------------------------- image_prompt

IMAGE_LAYERS = (
    ('subject', 'الموضوع'),
    ('action', 'الفعل / الوضعية'),
    ('setting', 'المكان'),
    ('lighting', 'الإضاءة'),
    ('camera', 'الكاميرا / العدسة'),
    ('materials', 'الخامات / الملمس'),
    ('mood', 'الإحساس / الألوان'),
)
ASPECT_RATIOS = {'1:1': (1, 1), '4:5': (4, 5), '5:4': (5, 4), '3:2': (3, 2),
                 '2:3': (2, 3), '16:9': (16, 9), '9:16': (9, 16), '21:9': (21, 9)}
DEFAULT_NEGATIVE = ('نص مكتوب أو حروف مشوهة', 'علامة مائية أو لوجو', 'أصابع زيادة أو أطراف مشوهة',
                    'وشوش مكررة', 'تشبع ألوان مبالغ فيه', 'توهج أو ضباب أو فلتر مضاف فوق الصورة')


def _size_hint(ratio, long_edge):
    w, h = ASPECT_RATIOS[ratio]

    def snap(x):
        return max(64, int(round(x / 64.0)) * 64)
    if w >= h:
        return [snap(long_edge), snap(long_edge * h / w)]
    return [snap(long_edge * w / h), snap(long_edge)]


def image_prompt(*, subject='صياد عجوز بلحية بيضا',
                 action='بيشد شبكة صيد مبلولة من المية بإيديه الاتنين',
                 setting='مركب خشب صغير على النيل وقت الفجر',
                 lighting='شمس واطية دافية جاية من الشمال، ضل طويل على الخشب',
                 camera='عدسة 50 مم على مستوى العين، عمق ميدان ضحل',
                 materials='خشب متآكل، شبكة نايلون مبلولة، جلد إيدين مجعّد',
                 mood='هادي وتأملي، ألوان عسلي وأزرق باهت',
                 negative=None, aspect_ratio='4:5', long_edge=1536, style=None,
                 blocklist=None, **extra):
    """Seven ordered physical layers -> one prompt + negative list + aspect ratio.

    Empty layers are allowed but reported in missing_layers. `style` is either a
    style_library id or a short neutral descriptor. Any blocklisted name in any
    field returns status 'refused' with neutral style recommendations.
    """
    _no_extra(extra)
    values = {'subject': subject, 'action': action, 'setting': setting,
              'lighting': lighting, 'camera': camera, 'materials': materials, 'mood': mood}
    layers_text = {k: _text(v, k, 600, required=(k == 'subject')) for k, v in values.items()}
    neg = list(DEFAULT_NEGATIVE) if negative is None else _str_list(negative, 'negative', max_items=40)
    aspect_ratio = _choice(aspect_ratio, set(ASPECT_RATIOS), 'aspect_ratio')
    long_edge = _int(long_edge, 256, 8192, 'long_edge')
    style_id, style_fragment = _resolve_style(style)
    compiled = _blocklist(blocklist)

    assumptions = ['layer order is fixed: subject, action, setting, lighting, camera, materials, mood',
                   'text is kept in the language it was written in; no translation is done',
                   'size_hint rounds to multiples of 64 px; target services may snap differently']
    limits = [NO_SERVICE_LIMIT, 'each layer <= 600 chars, negative list <= 40 items',
              'blocklist screening is name matching only: it cannot detect a described '
              'look-alike or a misspelled name']

    hits = _screen(list(layers_text.values()) + neg + [style_fragment], compiled)
    if hits:
        return _pack('image_prompt', _refusal(hits), assumptions, limits)

    layers = [{'order': i + 1, 'layer': key, 'name_ar': ar, 'text': layers_text[key]}
              for i, (key, ar) in enumerate(IMAGE_LAYERS)]
    parts = [l['text'] for l in layers if l['text']]
    if style_fragment:
        parts.append(style_fragment)
    labeled = [f"{l['order']}. {l['name_ar']}: {l['text'] or '—'}" for l in layers]
    if style_fragment:
        labeled.append(f'+ الأسلوب: {style_fragment}')
    result = {
        'status': 'ready',
        'layers': layers,
        'missing_layers': [l['layer'] for l in layers if not l['text']],
        'style': {'id': style_id, 'fragment': style_fragment} if style_fragment else None,
        'prompt': ', '.join(parts),
        'prompt_labeled': '\n'.join(labeled),
        'negative': neg,
        'negative_prompt': ', '.join(neg),
        'aspect_ratio': aspect_ratio,
        'size_hint_px': _size_hint(aspect_ratio, long_edge),
    }
    return _pack('image_prompt', result, assumptions, limits)


# --------------------------------------------------------------------------- video_prompt

CAMERA_MOVES = {
    'static': 'locked-off static camera',
    'pan_left': 'slow pan left', 'pan_right': 'slow pan right',
    'tilt_up': 'tilt up', 'tilt_down': 'tilt down',
    'dolly_in': 'dolly in toward the subject', 'dolly_out': 'dolly out away from the subject',
    'truck_left': 'truck left alongside the subject', 'truck_right': 'truck right alongside the subject',
    'crane_up': 'crane up', 'crane_down': 'crane down',
    'orbit_left': 'orbit left around the subject', 'orbit_right': 'orbit right around the subject',
    'handheld': 'subtle handheld follow',
    'zoom_in': 'slow optical zoom in', 'zoom_out': 'slow optical zoom out',
}
_OPPOSITE = {('pan_left', 'pan_right'), ('tilt_up', 'tilt_down'), ('dolly_in', 'dolly_out'),
             ('truck_left', 'truck_right'), ('crane_up', 'crane_down'),
             ('orbit_left', 'orbit_right'), ('zoom_in', 'zoom_out')}
_OPPOSITE |= {(b, a) for a, b in _OPPOSITE}
SHOT_KEYS = ('description', 'camera_move', 'duration_s', 'motion_strength', 'anchors', 'notes')

DEFAULT_SHEETS = {
    'char_a': 'بنت عندها 10 سنين، ضفيرة سودا، جلابية زرقا، ماسكة فانوس أحمر صغير',
    'loc_alley': 'حارة قديمة في القاهرة، أرض حجر، مشربيات خشب، زينة رمضان',
}
DEFAULT_SHOTS = (
    {'description': 'البنت ماشية في الحارة والفانوس منوّر في إيدها',
     'camera_move': 'truck_left', 'duration_s': 4, 'motion_strength': 0.4,
     'anchors': ['char_a', 'loc_alley']},
    {'description': 'لقطة قريبة على وش البنت وهي بتبص لفوق على الزينة',
     'camera_move': 'dolly_in', 'duration_s': 3, 'motion_strength': 0.3,
     'anchors': ['char_a']},
    {'description': 'الحارة كلها من فوق والبنت نقطة نور صغيرة في النص',
     'camera_move': 'crane_up', 'duration_s': 5, 'motion_strength': 0.5,
     'anchors': ['char_a', 'loc_alley']},
)


def _motion_label(m):
    return 'low' if m < 0.34 else ('medium' if m < 0.67 else 'high')


def video_prompt(*, shots=None, character_sheets=None, aspect_ratio='9:16', fps=30,
                 style=None, negative=None, blocklist=None, **extra):
    """Shot list -> per-shot prompts + a consistency checklist.

    shots: list of {description, camera_move, duration_s, motion_strength,
    anchors: [sheet ids], notes?}. character_sheets: {id: description}; every
    anchor must exist there and its description is repeated verbatim in each
    shot prompt so the same character/location is described identically.
    """
    _no_extra(extra)
    shots_in = [dict(s) for s in DEFAULT_SHOTS] if shots is None else shots
    sheets_in = dict(DEFAULT_SHEETS) if character_sheets is None else character_sheets
    if not isinstance(shots_in, (list, tuple)) or not 1 <= len(shots_in) <= MAX_SHOTS:
        raise ValueError(f'shots must be a list of 1..{MAX_SHOTS} shot objects')
    sheets_in = _dict(sheets_in, 'character_sheets')
    if len(sheets_in) > 40:
        raise ValueError('character_sheets may have at most 40 entries')
    sheets = {}
    for sid, desc in sheets_in.items():
        sid_t = _text(sid, 'character_sheets id', 60)
        if not re.fullmatch(r'[A-Za-z0-9_\-]+', sid_t):
            raise ValueError(f'character sheet id {sid!r} must use letters, digits, _ or -')
        sheets[sid_t] = _text(desc, f'character_sheets[{sid_t}]', 600)
    aspect_ratio = _choice(aspect_ratio, set(ASPECT_RATIOS), 'aspect_ratio')
    fps = _int(fps, 12, 120, 'fps')
    style_id, style_fragment = _resolve_style(style)
    neg = (['وش بيتغير شكله من لقطة للتانية', 'هدوم أو ألوان بتتغير فجأة', 'نص مكتوب مشوه',
            'وميض أو فريمات سودا'] if negative is None
           else _str_list(negative, 'negative', max_items=40))
    compiled = _blocklist(blocklist)

    parsed = []
    for i, shot in enumerate(shots_in):
        name = f'shots[{i}]'
        shot = _dict(shot, name)
        _check_keys(shot, SHOT_KEYS, ('description', 'camera_move', 'duration_s'), name)
        anchors = _str_list(shot.get('anchors', []), f'{name}.anchors', max_items=10, max_len=60)
        for a in anchors:
            if a not in sheets:
                raise ValueError(f'{name}.anchors: unknown sheet id {a!r}')
        if len(set(anchors)) != len(anchors):
            raise ValueError(f'{name}.anchors has duplicates')
        parsed.append({
            'description': _text(shot['description'], f'{name}.description', 800),
            'camera_move': _choice(shot['camera_move'], set(CAMERA_MOVES), f'{name}.camera_move'),
            'duration_s': _num(shot['duration_s'], 0.5, 60, f'{name}.duration_s'),
            'motion_strength': _num(shot.get('motion_strength', 0.5), 0, 1, f'{name}.motion_strength'),
            'anchors': anchors,
            'notes': _text(shot.get('notes'), f'{name}.notes', 400, required=False),
        })
    total = sum(p['duration_s'] for p in parsed)
    if total > 600:
        raise ValueError(f'total shot duration {total:g}s exceeds 600s')

    assumptions = ['camera moves are named in English because most video models parse them best',
                   'motion_strength 0..1 is a model-neutral scale: <0.34 low, <0.67 medium, else high',
                   'frames per shot = round(duration_s * fps)']
    limits = [NO_SERVICE_LIMIT, f'<= {MAX_SHOTS} shots, each 0.5..60 s, total <= 600 s, <= 40 sheets',
              'continuity is only as good as the sheet text; the checklist cannot see generated frames',
              'blocklist screening is name matching only']

    texts = [p['description'] for p in parsed] + [p['notes'] for p in parsed]
    texts += list(sheets.values()) + neg + [style_fragment]
    hits = _screen(texts, compiled)
    if hits:
        return _pack('video_prompt', _refusal(hits), assumptions, limits)

    out_shots = []
    t = 0.0
    for i, p in enumerate(parsed):
        frames = int(round(p['duration_s'] * fps))
        label = _motion_label(p['motion_strength'])
        pieces = [p['description'],
                  f"Camera: {CAMERA_MOVES[p['camera_move']]}",
                  f"Duration: {p['duration_s']:g}s",
                  f"Motion: {label} ({p['motion_strength']:g})"]
        for a in p['anchors']:
            pieces.append(f'Keep identical [{a}]: {sheets[a]}')
        if style_fragment:
            pieces.append(f'Style: {style_fragment}')
        pieces.append(f'Aspect ratio {aspect_ratio}')
        if p['notes']:
            pieces.append(p['notes'])
        out_shots.append({
            'shot': i + 1, 'start_s': round(t, 3), 'end_s': round(t + p['duration_s'], 3),
            'frames': frames, 'camera_move': p['camera_move'], 'motion': label,
            'anchors': p['anchors'], 'prompt': '. '.join(pieces),
        })
        t += p['duration_s']

    checklist = []
    used = {a for p in parsed for a in p['anchors']}
    for sid in sheets:
        uses = [i + 1 for i, p in enumerate(parsed) if sid in p['anchors']]
        checklist.append({'check': f'sheet {sid} repeated verbatim',
                          'status': 'ok' if uses else 'warn',
                          'detail': f'shots {uses}' if uses else 'defined but never used'})
    if sheets:
        for i, p in enumerate(parsed):
            if not p['anchors']:
                checklist.append({'check': f'shot {i + 1} has continuity anchors', 'status': 'warn',
                                  'detail': 'no sheet id: character/location may drift'})
    for i, p in enumerate(parsed):
        if p['motion_strength'] >= 0.67 and p['duration_s'] > 6:
            checklist.append({'check': f'shot {i + 1} motion vs length', 'status': 'warn',
                              'detail': 'high motion over > 6 s tends to drift; split the shot'})
    for i in range(1, len(parsed)):
        pair = (parsed[i - 1]['camera_move'], parsed[i]['camera_move'])
        if pair in _OPPOSITE:
            checklist.append({'check': f'shots {i}->{i + 1} camera direction', 'status': 'warn',
                              'detail': f'{pair[0]} then {pair[1]} reverses screen motion'})
    checklist.append({'check': 'one aspect ratio and fps for all shots', 'status': 'ok',
                      'detail': f'{aspect_ratio} @ {fps} fps'})
    checklist.append({'check': 'same style fragment in every shot',
                      'status': 'ok' if style_fragment else 'manual',
                      'detail': style_fragment or 'no style set: add one so shots match'})
    for item in ('lighting direction and time of day match across shots',
                 'wardrobe, props and hand (left/right) stay the same',
                 '180-degree axis respected between consecutive shots',
                 'colour palette matches; no fade from black or black frames'):
        checklist.append({'check': item, 'status': 'manual', 'detail': 'review generated frames'})
    if len(used) == 0 and sheets:
        checklist.append({'check': 'any anchors used', 'status': 'warn', 'detail': 'no shot uses a sheet'})

    result = {'status': 'ready', 'shots': out_shots, 'character_sheets': sheets,
              'style': {'id': style_id, 'fragment': style_fragment} if style_fragment else None,
              'negative': neg, 'negative_prompt': ', '.join(neg),
              'aspect_ratio': aspect_ratio, 'fps': fps,
              'total_duration_s': round(total, 3), 'total_frames': sum(s['frames'] for s in out_shots),
              'consistency_checklist': checklist,
              'warnings': sum(1 for c in checklist if c['status'] == 'warn')}
    return _pack('video_prompt', result, assumptions, limits)


# --------------------------------------------------------------------------- music_prompt

SECTIONS = {'intro', 'verse', 'pre_chorus', 'chorus', 'bridge', 'hook', 'instrumental',
            'drop', 'break', 'outro'}
VOCAL_SECTIONS = {'verse', 'pre_chorus', 'chorus', 'bridge', 'hook'}
VOCALS = {'none': 'instrumental, no vocals', 'male': 'male lead vocal',
          'female': 'female lead vocal', 'duet': 'male and female duet', 'choir': 'choir vocals'}
TIME_SIGNATURES = {'4/4': 4, '3/4': 3, '6/8': 6, '2/4': 2, '7/8': 7}


def music_prompt(*, genre='بوب مصري خفيف', bpm=96, mood='دافي ومتفائل',
                 instruments=None, structure=None, language='Egyptian Arabic',
                 vocal='female', lyrics=None, time_signature='4/4', style_notes=None,
                 blocklist=None, **extra):
    """Music style prompt. Lyrics are NEVER invented: they come from the owner.

    If vocal != 'none' and lyrics are missing, status is 'needs_owner_lyrics'
    and the result carries an Arabic request for the exact lyrics. Owner lyrics
    are passed through byte-for-byte (with a sha256 for integrity).
    """
    _no_extra(extra)
    genre = _text(genre, 'genre', 120)
    bpm = _int(bpm, 40, 240, 'bpm')
    mood = _text(mood, 'mood', 200)
    instruments = (['طبلة', 'عود', 'كمان', 'باص'] if instruments is None
                   else _str_list(instruments, 'instruments', max_items=16, max_len=60, min_items=1))
    structure = (['intro', 'verse', 'chorus', 'verse', 'chorus', 'bridge', 'chorus', 'outro']
                 if structure is None else structure)
    if not isinstance(structure, (list, tuple)) or not 1 <= len(structure) <= 30:
        raise ValueError('structure must be a list of 1..30 sections')
    structure = [_choice(s, SECTIONS, f'structure[{i}]') for i, s in enumerate(structure)]
    language = _text(language, 'language', 60)
    vocal = _choice(vocal, set(VOCALS), 'vocal')
    lyrics_text = None if lyrics is None else _text(lyrics, 'lyrics', MAX_LYRICS, strip=False)
    time_signature = _choice(time_signature, set(TIME_SIGNATURES), 'time_signature')
    style_notes = _text(style_notes, 'style_notes', 300, required=False)
    compiled = _blocklist(blocklist)

    assumptions = ['bpm counts the time-signature denominator note; seconds_per_bar = beats * 60 / bpm',
                   'lyrics are the owner\'s exact text; this op never writes, fixes or completes lyrics',
                   'section names are generic tags; each service has its own tag syntax']
    limits = [NO_SERVICE_LIMIT, 'lyrics <= 8000 chars, <= 30 sections, <= 16 instruments',
              'artist-name screening uses the blocklist only (name matching)']

    hits = _screen([genre, mood, language, style_notes] + instruments + [lyrics_text or ''], compiled)
    if hits:
        return _pack('music_prompt', _refusal(hits, visual=False), assumptions, limits)

    sec_label = ' - '.join(s.replace('_', '-').title() for s in structure)
    parts = [genre, f'{bpm} BPM', time_signature, mood, 'instruments: ' + ', '.join(instruments),
             'structure: ' + sec_label, VOCALS[vocal]]
    if vocal != 'none':
        parts.append(f'sung in {language}')
    if style_notes:
        parts.append(style_notes)
    warnings = []
    if vocal != 'none' and not VOCAL_SECTIONS.intersection(structure):
        warnings.append('vocal requested but structure has no vocal section')
    if vocal == 'none' and lyrics_text is not None:
        warnings.append('vocal is none: lyrics will be ignored for an instrumental')

    result = {'style_prompt': ', '.join(parts), 'genre': genre, 'bpm': bpm,
              'time_signature': time_signature,
              'seconds_per_bar': round(TIME_SIGNATURES[time_signature] * 60 / bpm, 4),
              'mood': mood, 'instruments': instruments, 'structure': structure,
              'language': language, 'vocal': vocal, 'warnings': warnings}
    if vocal == 'none':
        result.update(status='ready', lyrics=None, lyrics_source='not_needed')
    elif lyrics_text is None:
        vocal_secs = [s for s in structure if s in VOCAL_SECTIONS]
        result.update(
            status='needs_owner_lyrics', lyrics=None, lyrics_source='missing',
            request_ar=('محتاج كلمات الأغنية منك بالحرف (مش هألّف كلام). ابعتها مقسومة على الأجزاء دي: '
                        + '، '.join(dict.fromkeys(vocal_secs)) + f'. اللغة: {language}. '
                        'أي كلمة مش متأكد منها سيبها فاضية وقولّي.'))
    else:
        result.update(status='ready', lyrics=lyrics_text, lyrics_source='owner',
                      lyrics_sha256=_sha(lyrics_text),
                      lyrics_lines=len([ln for ln in lyrics_text.splitlines() if ln.strip()]))
    return _pack('music_prompt', result, assumptions, limits)


# --------------------------------------------------------------------------- voice_prompt

EXAMPLE_SCRIPT = 'أهلًا بيكم. النهارده هنعرف إزاي نعمل قهوة تركي مظبوطة في خمس دقايق.'
VOICE_FORMATS = {'wav_48k', 'wav_44k', 'mp3_44k', 'aac_48k'}
BASE_WPM = 140


def voice_prompt(*, script=None, voice_id='owner_selected_voice', language='ar-EG',
                 stability=0.55, similarity=0.75, style=0.2, pace=1.0,
                 speaker_boost=True, output_format='wav_48k', **extra):
    """TTS settings + the owner's exact script (never edited, normalised or translated).

    Without `script` an example sentence is used and flagged as such; it must be
    replaced by the owner's text before anything is sent anywhere.
    """
    _no_extra(extra)
    source = 'example_default' if script is None else 'owner'
    text = EXAMPLE_SCRIPT if script is None else _text(script, 'script', MAX_SCRIPT, strip=False)
    voice_id = _text(voice_id, 'voice_id', 120)
    language = _text(language, 'language', 20)
    stability = _num(stability, 0, 1, 'stability')
    similarity = _num(similarity, 0, 1, 'similarity')
    style = _num(style, 0, 1, 'style')
    pace = _num(pace, 0.5, 2.0, 'pace')
    speaker_boost = _bool(speaker_boost, 'speaker_boost')
    output_format = _choice(output_format, VOICE_FORMATS, 'output_format')

    words = len(text.split())
    pauses = sum(text.count(c) for c in '.!?؟،,؛;…\n')
    seconds = words * 60.0 / (BASE_WPM * pace) + 0.25 * pauses
    warnings = []
    if source == 'example_default':
        warnings.append('example script: replace with the owner\'s exact script before use')
    if re.search(r'\d', text):
        warnings.append('digits present: TTS may read numbers differently; owner may spell them out')
    if _ARABIC_RE.search(text) and re.search('[A-Za-z]', text):
        warnings.append('mixed Arabic and Latin text: check pronunciation of Latin words')
    if stability < 0.3:
        warnings.append('stability < 0.3 can make delivery inconsistent between takes')

    result = {'status': 'ready' if source == 'owner' else 'example_only',
              'script': text, 'script_source': source, 'script_sha256': _sha(text),
              'chars': len(text), 'words': words,
              'estimated_seconds': round(seconds, 1),
              'settings': {'voice_id': voice_id, 'language': language, 'stability': stability,
                           'similarity': similarity, 'style': style, 'pace': pace,
                           'speaker_boost': speaker_boost, 'output_format': output_format},
              'warnings': warnings}
    assumptions = [f'duration estimate: {BASE_WPM} words/min at pace 1.0 plus 0.25 s per pause mark',
                   'settings are model-neutral names; map them to the chosen service\'s fields',
                   'script is passed through unchanged; sha256 lets the caller prove it was not edited']
    limits = [NO_SERVICE_LIMIT, f'script <= {MAX_SCRIPT} chars',
              'does not check voice ownership or consent for cloned voices: the owner must confirm']
    return _pack('voice_prompt', result, assumptions, limits)


# --------------------------------------------------------------------------- style_library

def style_library(*, query=None, category=None, **extra):
    """The 40 original neutral style descriptors, optionally filtered."""
    _no_extra(extra)
    q = _text(query, 'query', 80, required=False)
    cats = sorted({s[1] for s in STYLES})
    cat = None if category is None else _choice(category, set(cats), 'category')
    nq = _norm(q).strip() if q else ''
    items = []
    for s in STYLES:
        if cat and s[1] != cat:
            continue
        if nq and nq not in _norm(' '.join(s)):
            continue
        items.append(_style_card(s[0]))
    compiled = _blocklist(None)
    clean = not _screen([' '.join(s) for s in STYLES], compiled)
    result = {'count_total': len(STYLES), 'count': len(items), 'categories': cats,
              'styles': items, 'blocklist_clean': clean}
    return _pack('style_library', result,
                 ['descriptors are written in neutral terms (technique, light, medium), no protected names'],
                 [NO_SERVICE_LIMIT, 'query is a plain substring match over id, name, Arabic text and fragment'])


# --------------------------------------------------------------------------- cost_estimate

PRICE_KEYS = ('provider', 'model', 'unit', 'price_per_unit', 'currency', 'source', 'as_of')
JOB_KEYS = ('provider', 'model', 'unit', 'quantity', 'label')
EXAMPLE_PRICES = (
    {'provider': 'example_provider', 'model': 'image-model-x', 'unit': 'image',
     'price_per_unit': '0.04', 'currency': 'USD', 'source': 'example only, not a real price'},
    {'provider': 'example_provider', 'model': 'video-model-y', 'unit': 'second',
     'price_per_unit': '0.10', 'currency': 'USD', 'source': 'example only, not a real price'},
)
EXAMPLE_JOBS = (
    {'label': 'صور الغلاف', 'provider': 'example_provider', 'model': 'image-model-x', 'quantity': 4},
    {'label': 'فيديو الإعلان', 'provider': 'example_provider', 'model': 'video-model-y', 'quantity': 15},
)


def _price_table(entries):
    if not isinstance(entries, (list, tuple)) or not 1 <= len(entries) <= MAX_LIST:
        raise ValueError(f'price_table must be a list of 1..{MAX_LIST} entries')
    table = {}
    for i, e in enumerate(entries):
        name = f'price_table[{i}]'
        e = _dict(e, name)
        _check_keys(e, PRICE_KEYS, ('provider', 'model', 'unit', 'price_per_unit', 'currency'), name)
        key = (_text(e['provider'], f'{name}.provider', 80), _text(e['model'], f'{name}.model', 120),
               _text(e['unit'], f'{name}.unit', 40))
        if key in table:
            raise ValueError(f'{name}: duplicate entry for {key}')
        table[key] = {
            'price': _dec(e['price_per_unit'], f'{name}.price_per_unit', Decimal(0), Decimal(1_000_000)),
            'currency': _currency(e['currency'], f'{name}.currency'),
            'source': _text(e.get('source'), f'{name}.source', 200, required=False),
            'as_of': _text(e.get('as_of'), f'{name}.as_of', 40, required=False),
        }
    return table


def cost_estimate(*, price_table=None, jobs=None, budget_cap=None, budget_currency=None, **extra):
    """Totals from a caller-supplied price table and planned job sizes (Decimal).

    Each job names provider + model (+ unit when the pair has several units) and
    a quantity in that unit. Totals are kept per currency; nothing is converted.
    """
    _no_extra(extra)
    example = price_table is None and jobs is None
    table = _price_table(list(EXAMPLE_PRICES) if price_table is None else price_table)
    jobs_in = list(EXAMPLE_JOBS) if jobs is None else jobs
    if not isinstance(jobs_in, (list, tuple)) or not 1 <= len(jobs_in) <= MAX_LIST:
        raise ValueError(f'jobs must be a list of 1..{MAX_LIST} jobs')

    lines = []
    totals = {}
    with localcontext() as ctx:
        ctx.prec = 34
        for i, j in enumerate(jobs_in):
            name = f'jobs[{i}]'
            j = _dict(j, name)
            _check_keys(j, JOB_KEYS, ('provider', 'model', 'quantity'), name)
            provider = _text(j['provider'], f'{name}.provider', 80)
            model = _text(j['model'], f'{name}.model', 120)
            if 'unit' in j:
                unit = _text(j['unit'], f'{name}.unit', 40)
                key = (provider, model, unit)
                if key not in table:
                    raise ValueError(f'{name}: no price for {provider}/{model} per {unit}')
            else:
                keys = [k for k in table if k[0] == provider and k[1] == model]
                if len(keys) != 1:
                    raise ValueError(f'{name}: {len(keys)} price entries for {provider}/{model}; '
                                     'give "unit" explicitly' if keys else
                                     f'{name}: no price entry for {provider}/{model}')
                key = keys[0]
            qty = _dec(j['quantity'], f'{name}.quantity', Decimal(0), Decimal(1_000_000_000), low_open=True)
            entry = table[key]
            sub = qty * entry['price']
            totals[entry['currency']] = totals.get(entry['currency'], Decimal(0)) + sub
            lines.append({'label': _text(j.get('label'), f'{name}.label', 120, required=False) or f'job {i + 1}',
                          'provider': key[0], 'model': key[1], 'unit': key[2],
                          'quantity': _dstr(qty), 'price_per_unit': _dstr(entry['price']),
                          'currency': entry['currency'], 'subtotal': _dstr(sub),
                          'price_source': entry['source'], 'price_as_of': entry['as_of']})

    cents = Decimal('0.01')
    result = {'lines': lines,
              'totals_by_currency': {c: _dstr(v) for c, v in sorted(totals.items())},
              'totals_rounded_2dp': {c: format(v.quantize(cents, rounding=ROUND_HALF_UP), 'f')
                                     for c, v in sorted(totals.items())},
              'single_currency': len(totals) == 1,
              'example_prices': example}
    if budget_cap is not None:
        cap = _dec(budget_cap, 'budget_cap', Decimal(0), Decimal(1_000_000_000))
        if budget_currency is None:
            if len(totals) != 1:
                raise ValueError('budget_currency is required when totals use several currencies')
            bcur = next(iter(totals))
        else:
            bcur = _currency(budget_currency, 'budget_currency')
        spent = totals.get(bcur, Decimal(0))
        result['budget'] = {'cap': _dstr(cap), 'currency': bcur, 'total': _dstr(spent),
                            'within_budget': spent <= cap, 'remaining': _dstr(cap - spent)}
    elif budget_currency is not None:
        raise ValueError('budget_currency needs budget_cap')

    assumptions = ['prices are exactly what the caller supplied; they may be stale or wrong',
                   'subtotal = quantity * price_per_unit, exact Decimal; no currency conversion',
                   'taxes, fees, minimum billing increments, retries and failed generations are not modelled']
    if example:
        assumptions.insert(0, 'EXAMPLE price table: invented numbers for illustration, not real prices')
    limits = [NO_SERVICE_LIMIT, f'<= {MAX_LIST} price entries and <= {MAX_LIST} jobs',
              'an estimate is not an approval: use approval_request and wait for the owner']
    return _pack('cost_estimate', result, assumptions, limits)


# --------------------------------------------------------------------------- approval_request

ITEM_KEYS = ('label', 'quantity', 'unit', 'price_per_unit')


def approval_request(*, provider='example_provider', model='image-model-x', items=None,
                     currency='USD', purpose='4 صور غلاف لفيديو القهوة (مثال)',
                     expected_total=None, **extra):
    """Build a spend-approval request for the owner. Status is always
    'awaiting_owner_approval'; this module has no way to mark it approved.

    Approval exists only as the owner typing approval_phrase in chat; the
    request_id is a hash of the request, so any change produces a new phrase.
    """
    _no_extra(extra)
    provider = _text(provider, 'provider', 80)
    model = _text(model, 'model', 120)
    currency = _currency(currency, 'currency')
    purpose = _text(purpose, 'purpose', 400)
    items_in = ([{'label': 'صور الغلاف', 'quantity': 4, 'unit': 'image', 'price_per_unit': '0.04'}]
                if items is None else items)
    if not isinstance(items_in, (list, tuple)) or not 1 <= len(items_in) <= 50:
        raise ValueError('items must be a list of 1..50 items')

    items_out = []
    total = Decimal(0)
    with localcontext() as ctx:
        ctx.prec = 34
        for i, it in enumerate(items_in):
            name = f'items[{i}]'
            it = _dict(it, name)
            _check_keys(it, ITEM_KEYS, ITEM_KEYS, name)
            qty = _dec(it['quantity'], f'{name}.quantity', Decimal(0), Decimal(1_000_000_000), low_open=True)
            price = _dec(it['price_per_unit'], f'{name}.price_per_unit', Decimal(0), Decimal(1_000_000))
            sub = qty * price
            total += sub
            items_out.append({'label': _text(it['label'], f'{name}.label', 120),
                              'quantity': _dstr(qty), 'unit': _text(it['unit'], f'{name}.unit', 40),
                              'price_per_unit': _dstr(price), 'subtotal': _dstr(sub)})
    if expected_total is not None:
        exp = _dec(expected_total, 'expected_total', Decimal(0), Decimal(1_000_000_000_000))
        if exp != total:
            raise ValueError(f'expected_total {_dstr(exp)} does not match computed total {_dstr(total)}')

    core = {'provider': provider, 'model': model, 'items': items_out, 'total': _dstr(total),
            'currency': currency, 'purpose': purpose}
    request_id = 'RR-' + _sha(json.dumps(core, ensure_ascii=False, sort_keys=True))[:12]
    phrase = f'أوافق على صرف {_dstr(total)} {currency} على {provider} / {model} للطلب {request_id}'
    record = dict(core, request_id=request_id, irreversible=True, approval_phrase=phrase,
                  status='awaiting_owner_approval')
    lines = '\n'.join(f"- {it['label']}: {it['quantity']} {it['unit']} × {it['price_per_unit']} = "
                      f"{it['subtotal']} {currency}" for it in items_out)
    message = (f'طلب موافقة قبل أي صرف ({request_id})\n'
               f'الخدمة: {provider} / {model}\n'
               f'الغرض: {purpose}\n'
               f'البنود:\n{lines}\n'
               f'الإجمالي التقديري: {_dstr(total)} {currency}\n'
               'ده فعل مابيرجعش، والسعر الفعلي ممكن يختلف عن التقدير.\n'
               f'لو موافق اكتب في الشات بالحرف: «{phrase}»\n'
               'من غير الجملة دي مفيش أي أداة هتصرف.')
    result = {'request': record, 'message_ar': message}
    assumptions = ['total = sum(quantity * price_per_unit), exact Decimal, in one currency',
                   'request_id = first 12 hex of sha256 over the canonical request; '
                   'any change to items, total, provider, model, currency or purpose changes it']
    limits = [NO_SERVICE_LIMIT,
              'this module cannot mark a request approved; only the owner\'s explicit chat message '
              'matching approval_phrase counts, and the spending tool must check that itself',
              'one provider/model per request, <= 50 items; estimates are not invoices']
    return _pack('approval_request', result, assumptions, limits)


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'image_prompt': image_prompt, 'video_prompt': video_prompt,
    'music_prompt': music_prompt, 'voice_prompt': voice_prompt,
    'style_library': style_library, 'cost_estimate': cost_estimate,
    'approval_request': approval_request,
}


def run(op, params=None):
    """Validate and dispatch: run('image_prompt', {}) -> {'op','result','assumptions','limits'}."""
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
