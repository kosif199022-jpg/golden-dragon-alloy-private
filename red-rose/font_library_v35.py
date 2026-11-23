"""Red Rose font library: index the owner's font folders, check Arabic support and licence, preview, pick by name.

  rose.py fonts scan [FOLDER ...] --approve-write   index fonts into ~/.red-rose/fonts/library.json
  rose.py fonts list [--arabic] [--style S]         what is indexed
  rose.py fonts find "words"                        search by name / style / licence
  rose.py fonts show NAME                           one font: path, family, licence text, notes
  rose.py fonts preview OUT.png [--filter words] [--text "..."] --approve-write   a sheet of samples
  rose.py fonts path NAME                           the file path to use in a render

The index stores where fonts are; it never copies font files into the skill or into Git
(licences of fonts from chat channels are unknown: the owner decides before commercial use).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HOME = Path.home()
LIB = HOME / '.red-rose' / 'fonts' / 'library.json'
DEFAULT_DIRS = [HOME / '.red-rose' / 'fonts']
FONT_EXT = {'.ttf', '.otf'}
ARABIC_TEST = 'ابتثجحخدذرزسشصضطظعغفقكلمنهوي'
SAMPLE = 'اللهم في يوم الجمعة'

# known usage notes the owner should see (from the font's own guide)
NOTES = {
    'elgharib-omar alqadr': 'خط ليلة القدر (عمر حسن / أحمد الغريب): خط قطع مخطوطة، كل رقم إنجليزي 1–11 = قطعة. صاحبه لا يسمح باستخدامه على الموسيقى.',
}

# rough style words from the family / file name (for search)
STYLE_WORDS = {
    'ruqaa': 'رقعة', 'رقعة': 'رقعة', 'kufi': 'كوفي', 'كوفي': 'كوفي', 'naskh': 'نسخ', 'diwani': 'ديواني',
    'thuluth': 'ثلث', 'nastaliq': 'نستعليق', 'sans': 'سانس', 'serif': 'سيرف', 'display': 'عناوين',
    'calligraph': 'مخطوط', 'qadr': 'مخطوط', 'typo': 'عناوين', 'kufic': 'كوفي', 'maghribi': 'مغربي',
}


# category from family / file name words (English and Arabic). First match wins, in this order.
CATEGORY_WORDS = [
    ('quran', ('quran', 'qurani', 'mushaf', 'مصحف', 'قرآن', 'uthman', 'attari', 'hafs', 'muhammadi')),
    ('diwani', ('diwani', 'diwany', 'ديواني')),
    ('thuluth', ('thuluth', 'thulth', 'ثلث')),
    ('ruqaa', ('ruqaa', 'ruqa', 'roqa', 'reqa', 'رقعة', 'رقعه')),
    ('kufi', ('kufi', 'kufic', 'kufam', 'كوفي', 'kofi')),
    ('naskh', ('naskh', 'نسخ', 'amiri', 'scheherazade', 'lateef', 'harmattan', 'alkalami', 'markazi', 'typesetting')),
    ('nastaliq', ('nastaliq', 'nastaleeq', 'gulzar', 'نستعليق')),
    ('maghribi', ('maghribi', 'مغربي', 'ruwudu')),
    ('handwriting', ('hand', 'script', 'graphology', 'brush', 'marker', 'يدوي', 'خط يد', 'playpen', 'okies')),
    ('rounded', ('rounded', 'round', 'مدور')),
    ('sans', ('sans', 'cairo', 'tajawal', 'almarai', 'beiruti', 'somar', 'lama', 'noto sans', 'ibm plex', 'mada',
              'changa', 'zain', 'alan', 'steam', 'meral', 'dialogue')),
    ('display', ('display', 'poster', 'typo', 'headline', 'title', 'black', 'heavy', 'allexp', 'lalezar', 'rakkas',
                 'jomhuria', 'blaka', 'lemonada', 'vibes', 'katibeh', 'عناوين')),
]

# moods the owner asks for → categories that suit them (first is best)
MOODS = {
    'رومانسي': ['ruqaa', 'handwriting', 'diwani', 'nastaliq'], 'حب': ['ruqaa', 'handwriting', 'diwani'],
    'ديني': ['quran', 'naskh', 'thuluth', 'diwani'], 'دعاء': ['naskh', 'thuluth', 'diwani', 'quran'],
    'قرآن': ['quran', 'naskh'], 'رسمي': ['sans', 'kufi', 'naskh'], 'شركة': ['sans', 'kufi'],
    'محاسبة': ['sans'], 'فخم': ['diwani', 'thuluth', 'display'], 'فرح': ['diwani', 'display', 'rounded'],
    'أطفال': ['rounded', 'handwriting', 'display'], 'مرح': ['rounded', 'display', 'handwriting'],
    'عناوين': ['display', 'kufi', 'sans'], 'ترند': ['display', 'sans', 'ruqaa'], 'قوي': ['display', 'kufi'],
    'هادي': ['naskh', 'sans', 'nastaliq'], 'تراث': ['kufi', 'maghribi', 'thuluth', 'naskh'],
}
MOOD_ALIASES = {'romantic': 'رومانسي', 'love': 'حب', 'religious': 'ديني', 'dua': 'دعاء', 'quran': 'قرآن',
                'formal': 'رسمي', 'corporate': 'شركة', 'luxury': 'فخم', 'wedding': 'فرح', 'kids': 'أطفال',
                'fun': 'مرح', 'title': 'عناوين', 'trend': 'ترند', 'bold': 'قوي', 'calm': 'هادي', 'heritage': 'تراث'}


def _category(text: str) -> str:
    low = text.lower()
    for cat, words in CATEGORY_WORDS:
        if any(w in low for w in words):
            return cat
    return 'other'


def measure(path: str) -> dict:
    """Render-based facts: does Arabic join (shaped word much narrower than its letters apart), ink weight."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        f = ImageFont.truetype(path, 80, layout_engine=ImageFont.Layout.RAQM)
        joined = f.getlength('بيت', direction='rtl')
        apart = sum(f.getlength(c, direction='rtl') for c in 'بيت')
        ratio = round(joined / apart, 3) if apart else None
        img = Image.new('L', (520, 140), 0)
        ImageDraw.Draw(img).text((500, 70), 'الهدى نور', font=f, fill=255, anchor='rm', direction='rtl')
        box = img.getbbox()
        ink = 0.0
        if box:
            crop = img.crop(box)
            ink = round(sum(1 for v in crop.getdata() if v > 128) / (crop.width * crop.height), 3)
        return {'join_ratio': ratio, 'joins': bool(ratio is not None and ratio < 0.88), 'ink': ink}
    except Exception as exc:
        return {'join_ratio': None, 'joins': False, 'ink': None, 'render_error': type(exc).__name__}


def _names(tt):
    out = {}
    for rec in tt['name'].names:
        try:
            out.setdefault(rec.nameID, rec.toUnicode())
        except Exception:
            continue
    return out


PERSONAL_WORDS = ('personal', 'شخصي', 'trial', 'demo', 'free for personal', 'non-commercial', 'noncommercial')


def _junk(path: Path) -> bool:
    """macOS resource forks and archive junk that look like fonts but are not."""
    return path.name.startswith('._') or '__MACOSX' in path.parts or path.stat().st_size < 1024


def _folder_licence(path: Path) -> str:
    """Licence from files shipped next to the font (OFL.txt, LICENSE, license.md), up to 3 folders up."""
    here = path.parent
    for _ in range(3):
        for f in here.iterdir() if here.is_dir() else []:
            n = f.name.lower()
            if f.is_file() and (n.startswith('ofl') or n.startswith('licen') or 'license' in n) and f.suffix.lower() in ('.txt', '.md', ''):
                try:
                    t = f.read_text(encoding='utf-8', errors='ignore')[:4000].lower()
                except OSError:
                    continue
                if 'open font license' in t or 'sil ofl' in t:
                    return 'OFL'
                if 'apache license' in t:
                    return 'Apache'
                return 'see text'
        if here.parent == here:
            break
        here = here.parent
    return ''


def inspect(path: Path) -> dict | None:
    from fontTools.ttLib import TTFont
    try:
        tt = TTFont(str(path), lazy=True, fontNumber=0)
        cmap = tt.getBestCmap() or {}
        names = _names(tt)
    except Exception as exc:
        return {'file': str(path), 'error': f'{type(exc).__name__}'}
    arabic = sum(1 for ch in ARABIC_TEST if ord(ch) in cmap)
    digits_only = not arabic and all(ord(d) in cmap for d in '123')
    family = names.get(16) or names.get(1) or path.stem
    sub = names.get(17) or names.get(2) or ''
    lic = (names.get(13) or '').strip()
    lic_url = (names.get(14) or '').strip()
    key = f'{family} {sub}'.strip()
    low = (key + ' ' + path.stem).lower()
    styles = sorted({v for k, v in STYLE_WORDS.items() if k in low})
    note = next((v for k, v in NOTES.items() if k in low), '')
    if 'ofl' in lic.lower() or 'open font' in lic.lower() or 'scripts.sil.org/ofl' in lic_url.lower():
        lic_kind = 'OFL'
    elif 'apache' in lic.lower():
        lic_kind = 'Apache'
    elif lic:
        lic_kind = 'see text'
    else:
        lic_kind = _folder_licence(path) or 'unknown'
    where = (str(path) + ' ' + key + ' ' + lic).lower()
    personal = any(w in where for w in PERSONAL_WORDS)
    if personal and lic_kind in ('unknown', 'see text'):
        lic_kind = 'personal only'
    try:
        weight = int(tt['OS/2'].usWeightClass) if 'OS/2' in tt else 400
    except Exception:
        weight = 400
    facts = measure(str(path)) if arabic else {'join_ratio': None, 'joins': False, 'ink': None}
    return {
        'category': 'glyphs' if digits_only else _category(f'{key} {path.stem} {path.parent.name}'),
        'weight': weight, **facts,
        'name': key, 'family': family, 'subfamily': sub, 'file': str(path),
        'arabic_letters': f'{arabic}/{len(ARABIC_TEST)}', 'arabic': arabic >= len(ARABIC_TEST) - 2,
        'glyph_font': digits_only, 'glyphs': len(cmap), 'styles': styles,
        'licence': lic_kind, 'licence_text': lic[:400], 'licence_url': lic_url, 'note': note,
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()[:16],
    }


def scan(folders=None, approve_write=False) -> dict:
    dirs = [Path(f).expanduser() for f in (folders or [])] + DEFAULT_DIRS
    files = []
    for d in dirs:
        if d.is_dir():
            files += [p for p in d.rglob('*') if p.suffix.lower() in FONT_EXT]
        elif d.is_file() and d.suffix.lower() in FONT_EXT:
            files.append(d)
    junk = [p for p in files if _junk(p)]
    files = [p for p in files if not _junk(p)]
    seen, names, rows, errors = set(), {}, [], []
    # TTF before OTF so the TrueType copy wins a name tie (Pillow and libass both like it)
    for p in sorted(files, key=lambda q: (q.suffix.lower() != '.ttf', str(q))):
        info = inspect(p)
        if not info:
            continue
        if 'error' in info:
            errors.append(info)
            continue
        if info['sha256'] in seen:
            continue
        seen.add(info['sha256'])
        nk = info['name'].lower()
        if nk in names:              # same family + weight from another archive or format
            names[nk].setdefault('also', []).append(info['file'])
            continue
        names[nk] = info
        rows.append(info)
    rows.sort(key=lambda r: r['name'].lower())
    kinds = ('OFL', 'Apache', 'see text', 'personal only', 'unknown')
    families = sorted({r['family'] for r in rows})
    summary = {'fonts': len(rows), 'families': len(families), 'arabic': sum(r['arabic'] for r in rows),
               'glyph_fonts': sum(r['glyph_font'] for r in rows),
               'licence': {k: sum(1 for r in rows if r['licence'] == k) for k in kinds},
               'unreadable': len(errors), 'junk_skipped': len(junk),
               'duplicates_merged': len(files) - len(rows) - len(errors)}
    if not approve_write:
        return {'ok': False, 'outcome': 'approval_required', 'would_write': [str(LIB)], **summary,
                'hint': 'rerun with --approve-write after the owner says yes'}
    LIB.parent.mkdir(parents=True, exist_ok=True)
    LIB.write_text(json.dumps({'folders': [str(d) for d in dirs], 'fonts': rows}, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    return {'ok': True, 'saved': [str(LIB)], **summary}


def load() -> list[dict]:
    if not LIB.is_file():
        return []
    return json.loads(LIB.read_text(encoding='utf-8')).get('fonts', [])


def _match(rows, words):
    ws = [w.lower() for w in re.split(r'\s+', words or '') if w]
    if not ws:
        return rows
    def hay(r):
        return ' '.join([r['name'], Path(r['file']).name, ' '.join(r['styles']), r['licence'], r['note']]).lower()
    return [r for r in rows if all(w in hay(r) for w in ws)]


def listing(arabic=False, style=None, words=None):
    rows = load()
    if arabic:
        rows = [r for r in rows if r['arabic']]
    if style:
        rows = [r for r in rows if style in r['styles']]
    rows = _match(rows, words)
    slim = [{k: r.get(k) for k in ('name', 'category', 'weight', 'arabic', 'joins', 'glyph_font', 'licence', 'note')} for r in rows]
    return {'ok': True, 'count': len(slim), 'fonts': slim}


def find_one(name: str) -> dict | None:
    rows = load()
    low = name.lower()
    exact = [r for r in rows if r['name'].lower() == low or Path(r['file']).stem.lower() == low]
    if exact:
        return exact[0]
    part = _match(rows, name)
    return part[0] if part else None


def preview(out, words=None, text=SAMPLE, arabic_only=True, limit=60, approve_write=False) -> dict:
    rows = [r for r in load() if (r['arabic'] or not arabic_only)]
    rows = _match(rows, words)[:limit]
    out = Path(out).expanduser()
    if not rows:
        return {'ok': False, 'outcome': 'error', 'error': 'no fonts match; run fonts scan first'}
    if not approve_write:
        return {'ok': False, 'outcome': 'approval_required', 'would_write': [str(out)], 'fonts': len(rows)}
    from PIL import Image, ImageDraw, ImageFont
    raqm = ImageFont.Layout.RAQM
    label_font = ImageFont.load_default()
    cell_h, width = 110, 1400
    img = Image.new('RGB', (width, cell_h * len(rows) + 10), (24, 22, 28))
    d = ImageDraw.Draw(img)
    for i, r in enumerate(rows):
        y = i * cell_h + 8
        d.text((14, y + 4), f"{i + 1}. {r['name']}  [{r['licence']}]", fill=(200, 200, 200), font=label_font)
        try:
            f = ImageFont.truetype(r['file'], 56, layout_engine=raqm)
            sample = '1 2 3 4 5' if r['glyph_font'] else text
            d.text((width - 20, y + 62), sample, font=f, fill=(255, 236, 170), anchor='rm', direction=None if r['glyph_font'] else 'rtl')
        except Exception as exc:
            d.text((width - 20, y + 62), f'(cannot draw: {type(exc).__name__})', fill=(255, 120, 120), anchor='rm')
        d.line([(10, y + cell_h - 6), (width - 10, y + cell_h - 6)], fill=(60, 58, 66))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {'ok': True, 'saved': [str(out)], 'fonts': len(rows)}


# ----------------------------------------------------------------- using fonts

LICENCE_RANK = {'OFL': 0, 'Apache': 0, 'see text': 1, 'personal only': 2, 'unknown': 3}


def suggest(mood: str, limit: int = 8, commercial: bool = False) -> dict:
    """Fonts that suit a mood. Joined Arabic only; free licences first; one weight per family."""
    key = MOOD_ALIASES.get(mood.strip().lower(), mood.strip())
    cats = MOODS.get(key)
    if not cats:
        return {'ok': False, 'outcome': 'error', 'error': f'unknown mood {mood!r}', 'moods': sorted(MOODS)}
    rows = [r for r in load() if r.get('arabic') and r.get('joins') and not r.get('glyph_font')]
    if commercial:
        rows = [r for r in rows if r['licence'] in ('OFL', 'Apache')]
    picked, families = [], set()
    for rank, cat in enumerate(cats):
        pool = sorted((r for r in rows if r.get('category') == cat),
                      key=lambda r: (LICENCE_RANK.get(r['licence'], 3), abs(r.get('weight', 400) - 600), r['name']))
        for r in pool:
            if r['family'] in families:
                continue
            families.add(r['family'])
            picked.append({'name': r['name'], 'category': cat, 'licence': r['licence'], 'weight': r.get('weight'),
                           'file': r['file']})
            if len(picked) >= limit:
                break
        if len(picked) >= limit:
            break
    return {'ok': True, 'mood': key, 'categories': cats, 'count': len(picked), 'fonts': picked,
            'note': 'commercial use: only OFL/Apache are safe' if not commercial else 'free licences only'}


def ass_name(name: str) -> dict:
    """What to write in an ASS/SSA subtitle style (Fontname, Bold) and the folder for ffmpeg fontsdir."""
    r = find_one(name)
    if not r:
        return {'ok': False, 'outcome': 'error', 'error': f'font not in the library: {name}'}
    bold = 1 if (r.get('weight') or 400) >= 600 or 'bold' in r.get('subfamily', '').lower() else 0
    return {'ok': True, 'fontname': r['family'], 'bold': bold, 'fontsdir': str(Path(r['file']).parent),
            'file': r['file'], 'hint': 'copy the file into the ffmpeg working folder and pass fontsdir=<that folder>'}


def render_text(text: str, out, font: str, size: int = 120, colour: str = 'gold', width: int = 1080,
                approve_write: bool = False) -> dict:
    """Shaped Arabic text as a transparent PNG (gold gradient or white) with a soft shadow, to lay over video."""
    r = find_one(font)
    if not r:
        return {'ok': False, 'outcome': 'error', 'error': f'font not in the library: {font}'}
    if r.get('glyph_font'):
        return {'ok': False, 'outcome': 'error', 'error': 'calligraphy-piece font: type digits 1-11, not words'}
    out = Path(out).expanduser()
    if not approve_write:
        return {'ok': False, 'outcome': 'approval_required', 'would_write': [str(out)], 'font': r['name']}
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    f = ImageFont.truetype(r['file'], size, layout_engine=ImageFont.Layout.RAQM)
    while f.getlength(text, direction='rtl') > width - 80 and size > 24:
        size -= 4
        f = ImageFont.truetype(r['file'], size, layout_engine=ImageFont.Layout.RAQM)
    h = int(size * 2.2)
    mask = Image.new('L', (width, h), 0)
    ImageDraw.Draw(mask).text((width / 2, h / 2), text, font=f, fill=255, anchor='mm', direction='rtl')
    shadow = mask.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(12)).point(lambda v: int(v * 0.8))
    img = Image.new('RGBA', (width, h), (0, 0, 0, 0))
    img.putalpha(0)
    img = Image.composite(Image.new('RGBA', (width, h), (20, 10, 0, 255)), img, shadow)
    if colour == 'white':
        fill = Image.new('RGBA', (width, h), (255, 255, 255, 255))
    else:
        top, bot = (255, 236, 150), (214, 150, 40)
        box = mask.getbbox() or (0, 0, width, h)
        col = Image.new('RGBA', (1, h))
        for y in range(h):
            t = min(1.0, max(0.0, (y - box[1]) / max(1, box[3] - box[1])))
            col.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
        fill = col.resize((width, h))
    layer = Image.new('RGBA', (width, h), (0, 0, 0, 0))
    layer.paste(fill, (0, 0), mask)
    img.alpha_composite(layer)
    img = img.crop(img.getbbox() or (0, 0, width, h))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {'ok': True, 'saved': [str(out)], 'font': r['name'], 'licence': r['licence'], 'size_px': size,
            'image': list(img.size)}
