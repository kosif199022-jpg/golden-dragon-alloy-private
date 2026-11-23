#!/usr/bin/env python3
"""Dua audio library by day: list a TikTok account's dua reels, label each by the day or occasion
named in its caption, then (in the Higgsfield sandbox) keep only the audio, sorted by label.

  python3 dua_audio.py list HANDLE [--pages N] [--out list.json]   # ScrapeCreators, 1 credit / 10 videos
  python3 dua_audio.py label videos.json --acc HANDLE --out list.json # from a saved video list
  python3 fetch_audio.py list.json [workers] [max_seconds]           # in the sandbox, resumable
  python3 dua_audio.py catalog AUDIO_DIR --out dua_audio_catalog.csv  # after the files are back

Labels: friday_night, friday, saturday ... thursday (with _morning when the caption says صباح),
ramadan, eid, arafah, shaban, rajab, mawlid, fajr, quran, new_month, other.
The voices belong to their creators: keep the library private, use it to study tone and pace,
and publish with the owner's own voice or TikTok's in-app sound.
"""
import argparse, csv, json, os, re, subprocess, sys, time, urllib.parse, datetime
from pathlib import Path

DAYS = [('friday_night', r'ليل[ةه]\s*(ال)?جمع'), ('friday', r'جمع[ةه]|الجمعه'), ('saturday', r'السبت'),
        ('sunday', r'الأحد|الاحد'), ('monday', r'الإثنين|الاثنين|الأثنين'), ('tuesday', r'الثلاثاء|الثلاثا'),
        ('wednesday', r'الأربعاء|الاربعاء|الاربعا'), ('thursday', r'الخميس')]
OCC = [('ramadan', r'رمضان'), ('eid', r'عيد'), ('arafah', r'عرف[ةه]'), ('shaban', r'شعبان'), ('rajab', r'رجب'),
       ('mawlid', r'المولد'), ('fajr', r'الفجر'), ('quran', r'سور[ةه]|قرآن|قران'), ('new_month', r'شهر\s*جديد|الشهر\s*الجديد|بداي[ةه]\s*شهر')]


def label(text):
    t = text or ''
    for name, rx in OCC[:5]:
        if re.search(rx, t): return name
    for name, rx in DAYS:
        if re.search(rx, t):
            return name + ('_morning' if re.search(r'صباح', t) and name != 'friday_night' else '')
    for name, rx in OCC[5:]:
        if re.search(rx, t): return name
    return 'other'


def items_from(videos, acc):
    out = []
    for v in videos:
        desc = v.get('desc', '')
        out.append({'acc': acc, 'id': str(v['id']), 'url': v.get('url') or f"https://www.tiktok.com/@{acc}/video/{v['id']}",
                    'date': v.get('date', ''), 'plays': v.get('plays', 0), 'label': label(desc.split('#')[0] or desc), 'title': desc[:120]})
    return out


def fetch_list(handle, pages):
    vids, cur = [], ''
    for n in range(pages):
        u = f'https://api.scrapecreators.com/v3/tiktok/profile/videos?handle={urllib.parse.quote(handle)}' + (f'&max_cursor={cur}' if cur else '')
        r = subprocess.run(['curl', '-s', '-m', '120', u], capture_output=True, text=True)
        try: d = json.loads(r.stdout)
        except ValueError: print('stop: bad answer on page', n + 1, file=sys.stderr); break
        for a in d.get('aweme_list') or []:
            ts = a.get('create_time') or 0
            vids.append({'id': a['aweme_id'], 'desc': a.get('desc', ''), 'plays': (a.get('statistics') or {}).get('play_count', 0),
                         'date': datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime('%Y-%m-%d') if ts else ''})
        cur = d.get('max_cursor')
        if not d.get('has_more') or not cur: break
        time.sleep(1)
    return vids


def catalog(root, out):
    rows = []
    for f in sorted(Path(root).rglob('*.m4a')):
        acc, lab = f.parts[-3], f.parts[-2]
        date, vid = f.stem.split('_', 1)
        rows.append({'account': acc, 'label': lab, 'date': date, 'tiktok': f'https://www.tiktok.com/@{acc}/video/{vid}',
                     'file': f'{acc}/{lab}/{f.name}', 'kb': f.stat().st_size // 1024})
    with open(out, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=['account', 'label', 'date', 'tiktok', 'file', 'kb']); w.writeheader(); w.writerows(rows)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('list'); a.add_argument('handle'); a.add_argument('--pages', type=int, default=20); a.add_argument('--out', default='audio_list.json')
    b = sp.add_parser('label'); b.add_argument('videos'); b.add_argument('--acc', required=True); b.add_argument('--out', default='audio_list.json')
    c = sp.add_parser('catalog'); c.add_argument('root'); c.add_argument('--out', default='dua_audio_catalog.csv')
    t = sp.add_parser('test')
    x = ap.parse_args()
    if x.cmd == 'test':
        cases = {'دعاء ليلة الجمعة يارب': 'friday_night', 'دعاء يوم الجمعة': 'friday', 'دعاء صباح يوم الأحد': 'sunday_morning',
                 'دعاء يوم الاثنين': 'monday', 'اللهم في رمضان': 'ramadan', 'بمناسبة المولد النبوي': 'mawlid', 'يارب': 'other'}
        bad = {k: (label(k), v) for k, v in cases.items() if label(k) != v}
        print('ok' if not bad else bad); sys.exit(1 if bad else 0)
    if x.cmd == 'catalog':
        rows = catalog(x.root, x.out); print(len(rows), 'files ->', x.out); return
    if x.cmd == 'list':
        items = items_from(fetch_list(x.handle, x.pages), x.handle)
    else:
        items = items_from(json.load(open(x.videos, encoding='utf-8')), x.acc)
    json.dump(items, open(x.out, 'w', encoding='utf-8'), ensure_ascii=False)
    from collections import Counter
    print(len(items), 'videos', dict(Counter(i['label'] for i in items).most_common()))


if __name__ == '__main__':
    main()
