"""Dua text catalogue: 112 themes by day / time / occasion, merged from the islamic-dua-reels skill.

  rose.py duas list [--section day|time|occasion|general]
  rose.py duas find "كلمات"            search theme id/ar/section and the dua lines
  rose.py duas day friday|الجمعة        the dua lines for a day (ready for a dua-reel plan)
  rose.py duas show ID                   one theme in full, with its note
  rose.py duas quran                     the Quran reference table (verify against a mushaf before rendering)

The authored lines are written in the channel's tone, not copied from the videos — edit freely.
Quran text is never given as ready overlay: `quran` lists سورة:آية to check against an approved mushaf.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'agent' / 'dua_catalog.json'

DAY_ALIASES = {
    'sunday': 'sunday', 'الأحد': 'sunday', 'الاحد': 'sunday',
    'monday': 'monday', 'الإثنين': 'monday', 'الاثنين': 'monday', 'الاتنين': 'monday',
    'tuesday': 'tuesday', 'الثلاثاء': 'tuesday', 'الثلاثا': 'tuesday',
    'wednesday': 'wednesday', 'الأربعاء': 'wednesday', 'الاربعاء': 'wednesday',
    'thursday': 'thursday', 'الخميس': 'thursday',
    'friday': 'friday', 'الجمعة': 'friday', 'الجمعه': 'friday',
    'saturday': 'saturday', 'السبت': 'saturday',
    'fajr': 'fajr', 'الفجر': 'fajr', 'morning': 'morning', 'الصباح': 'morning',
}


def _load() -> dict:
    return json.loads(DATA.read_text(encoding='utf-8'))


def _public(t: dict) -> dict:
    return {k: t[k] for k in ('id', 'ar', 'section', 'kind', 'lines', 'note', 'font_hint') if k in t}


def listing(section: str | None = None) -> dict:
    themes = _load()['themes']
    if section:
        themes = [t for t in themes if t['section'] == section]
    rows = [{'id': t['id'], 'ar': t['ar'], 'section': t['section'], 'lines': len(t['lines']),
             'kind': t['kind']} for t in themes]
    return {'ok': True, 'count': len(rows), 'themes': rows}


def find(query: str) -> dict:
    words = [w.lower() for w in re.split(r'\s+', query or '') if w]
    out = []
    for t in _load()['themes']:
        hay = ' '.join([t['id'], t['ar'], t['section'], ' '.join(t['lines']), t.get('note', '')]).lower()
        if all(w in hay for w in words):
            out.append(_public(t))
    return {'ok': True, 'count': len(out), 'themes': out}


def by_day(day: str) -> dict:
    key = DAY_ALIASES.get(day.strip().lower()) or DAY_ALIASES.get(day.strip())
    if not key:
        return {'ok': False, 'outcome': 'error', 'error': f'unknown day {day!r}',
                'days': sorted(set(DAY_ALIASES.values()))}
    for t in _load()['themes']:
        if t['id'] == key:
            return {'ok': True, 'day': key, 'ar': t['ar'], 'lines': t['lines'], 'note': t.get('note', ''),
                    'hint': 'put one or more of these lines into a dua-reel plan\'s "lines"'}
    return {'ok': False, 'outcome': 'error', 'error': f'no theme for {key}'}


def show(theme_id: str) -> dict:
    tid = theme_id.strip().lower()
    for t in _load()['themes']:
        if t['id'].lower() == tid or t['ar'] == theme_id.strip():
            return {'ok': True, 'theme': _public(t)}
    return {'ok': False, 'outcome': 'error', 'error': f'no theme {theme_id!r} (try: duas list)'}


def quran() -> dict:
    d = _load()
    return {'ok': True, 'warning': d['quran_note'], 'refs': d['quran_refs'],
            'count': len(d['quran_refs'])}
