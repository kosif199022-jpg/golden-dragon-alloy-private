"""Red Rose V29 (W03): small synthetic inputs for sample-media and for the tests.

Everything here is invented: a coloured clip with a tone, a PNG, a tone WAV, timed
Arabic words, a 3-row ledger and a 3-row bank statement that differ by 1.00, a tiny
SQLite file and a 5-playbook index. None of it is the owner's data. Media files are
skipped (with a reason in `skipped`) when FFmpeg or Pillow is missing; data files are
always written. make() never overwrites and never writes under ~/.red-rose.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import rose_io as rio

KEYS = ('SAMPLE_VIDEO', 'SAMPLE_PNG', 'SAMPLE_WAV', 'WORDS_JSON', 'LEDGER_CSV', 'BANK_CSV',
        'TMP_DB', 'PLAYBOOK_DB', 'WORK_DIR')
FILES = {'SAMPLE_VIDEO': 'clip.mp4', 'SAMPLE_PNG': 'frame.png', 'SAMPLE_WAV': 'tone.wav',
         'WORDS_JSON': 'words.json', 'LEDGER_CSV': 'ledger.csv', 'BANK_CSV': 'bank.csv',
         'TMP_DB': 'rose_tmp.sqlite3', 'PLAYBOOK_DB': 'playbooks_fixture.sqlite3', 'WORK_DIR': 'work'}
FFMPEG_TIMEOUT = 120

WORDS = [
    {'word': 'الوردة', 'start': 0.0, 'end': 0.6},
    {'word': 'الحَمْرَاءُ', 'start': 0.6, 'end': 1.4},
    {'word': 'تَفتَحُ', 'start': 1.4, 'end': 1.9},
    {'word': 'الآنَ', 'start': 1.9, 'end': 2.4},
]
LEDGER_ROWS = [
    ('L1', '2026-11-01', '2500.00', 'INV-1001'),
    ('L2', '2026-11-03', '-450.75', 'PAY-2207'),
    ('L3', '2026-11-05', '1200.00', 'INV-1002'),
]
BANK_ROWS = [
    ('B1', '2026-11-01', '2500.00', 'INV-1001'),
    ('B2', '2026-11-03', '-450.75', 'PAY-2207'),
    ('B3', '2026-11-05', '1201.00', 'INV-1002'),
]
PLAYBOOKS = [
    ('fixture.title-card', 'بطاقة عنوان', 'Synthetic title card with two Arabic words', ['عنوان', 'title']),
    ('fixture.caption-words', 'كابشن بالكلمات', 'Timed captions from a word list', ['كابشن', 'caption']),
    ('fixture.bank-reconcile', 'تسوية بنك', 'Match a bank statement against a ledger', ['بنك', 'reconcile']),
    ('fixture.loudness', 'ضبط الصوت', 'Measure and set loudness', ['صوت', 'loudness']),
    ('fixture.shot-report', 'تقرير اللقطات', 'Score shots of a clip', ['لقطات', 'shots']),
]


def _refuse_private(folder):
    private = Path.home() / '.red-rose'
    try:
        folder.resolve().relative_to(private.resolve())
    except ValueError:
        return
    raise ValueError(f'refusing to write fixtures under the owner\'s private folder {private}')


def _ffmpeg(args):
    done = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin'] + args,
                          capture_output=True, timeout=FFMPEG_TIMEOUT, check=False)
    if done.returncode != 0:
        tail = (done.stderr or b'').decode('utf-8', 'replace').strip().splitlines()[-3:]
        raise RuntimeError('ffmpeg failed: ' + ' | '.join(tail))


def _clip(path):
    # Two flat shots (blue 0-3 s, orange 3-6 s), 540x960, 30 fps, 180 frames, 440 Hz tone, H.264 + AAC.
    _ffmpeg(['-f', 'lavfi', '-i', 'color=c=0x1e5fd6:s=540x960:r=30:d=3',
             '-f', 'lavfi', '-i', 'color=c=0xff7a1a:s=540x960:r=30:d=3',
             '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=6',
             '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]',
             '-map', '[v]', '-map', '2:a', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
             '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-t', '6', '-movflags', '+faststart',
             str(path)])


def _wav(path):
    _ffmpeg(['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=2',
             '-ac', '1', '-c:a', 'pcm_s16le', str(path)])


def _png(path):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (540, 960), (30, 95, 214))
    ImageDraw.Draw(img).rectangle([0, 480, 540, 960], fill=(255, 122, 26))
    img.save(str(path), 'PNG')


def _csv(path, rows):
    lines = ['id,date,amount,ref'] + [','.join(r) for r in rows]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def _sqlite_tmp(path):
    con = sqlite3.connect(str(path))
    try:
        con.execute('CREATE TABLE fixture_note(id INTEGER PRIMARY KEY, note TEXT NOT NULL)')
        con.execute("INSERT INTO fixture_note(note) VALUES ('synthetic fixture, not owner data')")
        con.commit()
    finally:
        con.close()


def _playbook_index(path):
    from playbooks_v28 import _PB_SCHEMA, SCHEMA_VERSION
    con = sqlite3.connect(str(path))
    try:
        for stmt in _PB_SCHEMA:
            con.execute(stmt)
        con.execute('INSERT INTO meta(key, value) VALUES (?, ?)', ('schema', SCHEMA_VERSION))
        con.execute('INSERT INTO meta(key, value) VALUES (?, ?)', ('count', str(len(PLAYBOOKS))))
        for n, (pid, title, goal, triggers) in enumerate(PLAYBOOKS, start=1):
            digest = hashlib.sha256(pid.encode('utf-8')).hexdigest()
            row = (n, pid, title, goal, json.dumps(triggers, ensure_ascii=False), '[]', '[]', '[]', '[]',
                   'fixture', 'fixture', 'fixture', '[]', 0.9, 'high', '[]', 'catalog-skill', 'fixture',
                   digest, '[]', 'fixture', 'fixture', '[]', 1.0)
            con.execute('INSERT INTO playbooks(n, id, title, goal, triggers, inputs, steps, checks, outputs, '
                        'domain, category, family, related_adapters, confidence, band, flags, kind, license, '
                        'source_sha256, template_steps, steps_source, goal_source, derived_fields, completeness) '
                        'VALUES (' + ','.join(['?'] * 24) + ')', row)
            con.execute('INSERT INTO playbooks_fts(rowid, title, goal, triggers, steps) VALUES (?, ?, ?, ?, ?)',
                        (n, title, goal, ' | '.join(triggers), ''))
        con.commit()
    finally:
        con.close()


def make(out_dir):
    """Write the fixtures into out_dir (created when missing). Returns paths, skips and errors.

    Refuses when any target already exists (nothing is overwritten). Media keys are None when
    skipped; `skipped` maps the key to a reason; `errors` maps a key to the failure message.
    """
    out = Path(out_dir).expanduser().resolve()
    _refuse_private(out)
    targets = {key: out / FILES[key] for key in KEYS}
    existing = [str(p) for p in targets.values() if p.exists()]
    if existing:
        raise FileExistsError('refusing to overwrite existing fixture file(s): ' + ', '.join(existing))
    out.mkdir(parents=True, exist_ok=True)
    result = {key: None for key in KEYS}
    skipped, errors = {}, {}

    have_ffmpeg = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
    media = [('SAMPLE_VIDEO', _clip), ('SAMPLE_WAV', _wav)]
    for key, builder in media:
        if not have_ffmpeg:
            skipped[key] = 'ffmpeg/ffprobe missing'
            continue
        try:
            builder(targets[key])
            result[key] = str(targets[key])
        except Exception as exc:
            errors[key] = f'{type(exc).__name__}: {exc}'[:300]
    try:
        _png(targets['SAMPLE_PNG'])
        result['SAMPLE_PNG'] = str(targets['SAMPLE_PNG'])
    except ImportError:
        skipped['SAMPLE_PNG'] = 'Pillow missing'
    except Exception as exc:
        errors['SAMPLE_PNG'] = f'{type(exc).__name__}: {exc}'[:300]

    rio.write_json(str(targets['WORDS_JSON']), {'language': 'ar', 'source': 'synthetic fixture, not a recording',
                                                'words': WORDS}, overwrite=False)
    result['WORDS_JSON'] = str(targets['WORDS_JSON'])
    _csv(targets['LEDGER_CSV'], LEDGER_ROWS)
    result['LEDGER_CSV'] = str(targets['LEDGER_CSV'])
    _csv(targets['BANK_CSV'], BANK_ROWS)
    result['BANK_CSV'] = str(targets['BANK_CSV'])
    _sqlite_tmp(targets['TMP_DB'])
    result['TMP_DB'] = str(targets['TMP_DB'])
    _playbook_index(targets['PLAYBOOK_DB'])
    result['PLAYBOOK_DB'] = str(targets['PLAYBOOK_DB'])
    targets['WORK_DIR'].mkdir(parents=True, exist_ok=True)
    result['WORK_DIR'] = str(targets['WORK_DIR'])

    result['out_dir'] = str(out)
    result['skipped'] = skipped
    result['errors'] = errors
    return result
