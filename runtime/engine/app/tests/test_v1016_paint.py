"""v10.16: Paint Studio (the owner's paint-studio skill) bundled verbatim behind a guarded front door."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / 'tools' / 'paint' / 'bridge.py'
SKILL_DIR = ROOT / 'skills' / 'paint-studio'

pytest.importorskip('PIL')
pytest.importorskip('numpy')
from PIL import Image  # noqa: E402


def cli(*args, cwd=None, env=None):
    e = dict(os.environ, PYTHONIOENCODING='utf-8')
    e.update(env or {})
    return subprocess.run([sys.executable, str(BRIDGE), *[str(a) for a in args]], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', env=e, cwd=cwd, timeout=300)


def as_json(r):
    try:
        return json.loads(r.stdout)
    except Exception as exc:
        raise AssertionError(f'not JSON (rc={r.returncode}): {r.stdout[:300]!r} {r.stderr[-500:]!r}') from exc


OPS = [
    {"op": "rectangle", "box": [100, 80, 500, 300], "fill": "gold", "outline": "black", "size": 4},
    {"op": "text", "x": 120, "y": 120, "width": 360, "align": "center", "text": "أهلاً Paint", "size": 40,
     "color": "black"},
]


def test_help_exits_zero():
    for args in ([], ['--help'], ['ai', '--help']):
        r = cli(*args)
        assert r.returncode == 0, r.stderr
        assert 'paint' in r.stdout.lower()


def test_doctor_json():
    r = cli('doctor')
    assert r.returncode == 0, r.stderr
    d = as_json(r)
    assert d['schema'] == 'black-dragon.paint.v1'
    for key in ('pillow', 'opencv', 'rembg', 'sd_turbo_venv', 'mspaint'):
        assert key in d
    assert d['pillow']['available'] is True
    assert d['source_hashes_match'] is True and d['ready'] is True
    assert d['network'] is False and d['installs'] is False
    assert 'available' in d['opencv'] and 'available' in d['rembg'] and 'exists' in d['sd_turbo_venv']


def test_doctor_venv_override(tmp_path):
    fake = tmp_path / 'nope' / 'python.exe'
    d = as_json(cli('doctor', env={'BD_TOON_VENV_PY': str(fake)}))
    assert d['sd_turbo_venv']['exists'] is False and d['sd_turbo_venv']['env_override'] is True


def test_ops_lists_operations():
    r = cli('ops')
    assert r.returncode == 0 and 'rectangle' in r.stdout


def _new_and_draw(folder: Path):
    canvas, out, ops = folder / 'canvas.png', folder / 'card.png', folder / 'ops.json'
    ops.write_text(json.dumps(OPS, ensure_ascii=False), encoding='utf-8')
    r = cli('new', canvas, '--size', '640x360', '--bg', 'white')
    assert r.returncode == 0, r.stdout + r.stderr
    r = cli('draw', canvas, out, '--ops', ops)
    assert r.returncode == 0, r.stdout + r.stderr
    im = Image.open(out)
    assert im.size == (640, 360)
    rgb = im.convert('RGB')
    assert rgb.getpixel((300, 280)) != (255, 255, 255)   # inside the gold rectangle
    assert rgb.getpixel((20, 20)) == (255, 255, 255)     # untouched corner
    return canvas, out, ops


def test_new_draw_rectangle_text(tmp_path):
    _new_and_draw(tmp_path)


def test_refuses_overwrite(tmp_path):
    canvas, out, ops = _new_and_draw(tmp_path)
    before = hashlib.sha256(out.read_bytes()).hexdigest()
    r = cli('draw', canvas, out, '--ops', ops)
    assert r.returncode == 2 and 'overwrite' in as_json(r)['error']
    assert hashlib.sha256(out.read_bytes()).hexdigest() == before
    r = cli('new', canvas)
    assert r.returncode == 2
    r = cli('draw', canvas, canvas, '--ops', ops)          # same PNG in/out is still refused
    assert r.returncode == 2


def test_same_dpaint_editing_allowed(tmp_path):
    proj = tmp_path / 'proj.dpaint'
    assert cli('new', proj, '--size', '320x200').returncode == 0
    r = cli('draw', proj, proj, '--op', json.dumps(OPS[0]))
    assert r.returncode == 0, r.stdout + r.stderr
    final = tmp_path / 'final.png'
    assert cli('export', proj, final).returncode == 0
    assert Image.open(final).size == (320, 200)


def test_guards(tmp_path):
    img = tmp_path / 'a.png'
    Image.new('RGB', (10, 10), 'white').save(img)
    assert cli('new', tmp_path / 'x.txt').returncode == 2           # not an image
    assert cli('draw', tmp_path / 'missing.png', tmp_path / 'o.png', '--op', '{"op":"flip"}').returncode == 2
    assert cli('nonsense').returncode == 2
    r = cli('wallpaper', img)
    assert r.returncode == 3 and as_json(r)['needs_yes'] is True
    r = cli('print', img)
    assert r.returncode == 3


def test_ai_missing_venv_is_clear(tmp_path):
    r = cli('ai', 'create', tmp_path / 'o.png', '--prompt', 'cat',
            env={'BD_TOON_VENV_PY': str(tmp_path / 'none' / 'python.exe')})
    assert r.returncode == 2
    d = as_json(r)
    assert d['ok'] is False and 'venv' in d['error'] and not (tmp_path / 'o.png').exists()


def test_source_hashes_match_bundle():
    data = json.loads((SKILL_DIR / 'SOURCE_PAINT_STUDIO.json').read_text(encoding='utf-8'))
    paths = {f['path'] for f in data['files']}
    assert paths == {'SKILL.md', 'reference/analysis.md', 'reference/features.md',
                     'scripts/paint.py', 'scripts/paint_ai.py'}
    for f in data['files']:
        b = (SKILL_DIR / f['path']).read_bytes()
        assert hashlib.sha256(b).hexdigest() == f['sha256'] and len(b) == f['size']
        assert f['source'].startswith('%USERPROFILE%') and 'cinde' not in f['source']
    assert not list(SKILL_DIR.rglob('__pycache__'))
    assert cli('verify').returncode == 0


def test_no_hardcoded_user_paths():
    text = BRIDGE.read_text(encoding='utf-8')
    assert 'cinde' not in text and 'C:\\Users' not in text


def test_arabic_folder(tmp_path):
    folder = tmp_path / 'رسم الكوسيف' / 'شغل'
    folder.mkdir(parents=True)
    _new_and_draw(folder)
    # also from inside the Arabic folder with relative paths
    r = cli('new', 'نسخة.png', '--size', '200x100', cwd=folder)
    assert r.returncode == 0, r.stdout + r.stderr
    assert Image.open(folder / 'نسخة.png').size == (200, 100)
    r = cli('preview', 'نسخة.png', 'معاينة.png', '--zoom', '2', cwd=folder)
    assert r.returncode == 0, r.stdout + r.stderr
    assert Image.open(folder / 'معاينة.png').size[0] >= 400


def _venv():
    p = os.environ.get('BD_TOON_VENV_PY') or str(Path(os.environ.get('USERPROFILE') or Path.home())
                                                 / 'dragon-models' / 'toon' / 'venv' / 'Scripts' / 'python.exe')
    return Path(p)


@pytest.mark.skipif(not _venv().is_file(), reason='SD-Turbo venv not installed')
def test_ai_styles_with_venv():
    r = cli('ai', 'styles')
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'watercolor' in r.stdout


@pytest.mark.skipif(not _venv().is_file(), reason='SD-Turbo venv not installed')
def test_ai_refuses_overwrite_with_venv(tmp_path):
    out = tmp_path / 'o.png'
    out.write_bytes(b'x')
    r = cli('ai', 'create', out, '--prompt', 'cat')
    assert r.returncode == 2 and out.read_bytes() == b'x'
