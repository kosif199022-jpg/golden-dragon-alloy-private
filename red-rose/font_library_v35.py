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


def _names(tt):
    out = {}
    for rec in tt['name'].names:
        try:
            out.setdefault(rec.nameID, rec.toUnicode())
        except Exception:
            continue
    return out


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
        lic_kind = 'unknown'
    return {
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
    seen, rows, errors = set(), [], []
    for p in sorted(files):
        info = inspect(p)
        if not info:
            continue
        if 'error' in info:
            errors.append(info)
            continue
        if info['sha256'] in seen:
            continue
        seen.add(info['sha256'])
        rows.append(info)
    old = load()
    keep = [r for r in old if Path(r['file']).is_file() and r['sha256'] not in seen]
    rows = keep + rows
    summary = {'fonts': len(rows), 'arabic': sum(r['arabic'] for r in rows),
               'glyph_fonts': sum(r['glyph_font'] for r in rows),
               'licence': {k: sum(1 for r in rows if r['licence'] == k) for k in ('OFL', 'Apache', 'see text', 'unknown')},
               'unreadable': len(errors), 'duplicates_skipped': len(files) - len(rows) - len(errors) + len(keep)}
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
    slim = [{k: r[k] for k in ('name', 'arabic', 'glyph_font', 'styles', 'licence', 'note')} for r in rows]
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
