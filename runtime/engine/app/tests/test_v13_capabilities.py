"""v1.3 regression gates: safe, read-only adapter discovery; controlled setup; unified CLI."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT.parent
sys.path.insert(0, str(ROOT))
from dragon import capabilities, catalog


def test_registry_unique_and_complete():
    cards = capabilities.read_registry()
    assert len(cards) >= 35
    assert len({x['id'] for x in cards}) == len(cards)
    assert {'visual-forge', 'rea-ultra', 'absolute-creativity', 'image-studio', 'blender-engine', 'cinema-film', 'dragon-montage'} <= {x['id'] for x in cards}


def test_probe_does_not_execute_binaries():
    with mock.patch('subprocess.run', side_effect=AssertionError('executed')), \
         mock.patch('subprocess.call', side_effect=AssertionError('executed')), \
         mock.patch('subprocess.Popen', side_effect=AssertionError('executed')):
        result = capabilities.probe_tools()
    assert result['inspection_only'] and result['total'] == len(capabilities.read_registry())
    assert all(x['executed'] is False and x['proof_level'] == 'static_inspection_only' for x in result['tools'])
    assert sum(result[k] for k in ('discoverable','missing_dependencies','unverified_entrypoint')) == len(capabilities.read_registry())


def test_unknown_entrypoint_stays_unverified():
    fake = {'id':'shell-unknown', 'ar':'اسم', 'en':'name', 'what':'what', 'cmd':'sh -c dangerous'}
    row = capabilities.inspect_tool(fake)
    assert row['status'] == 'unverified_entrypoint' and not row['entrypoint_found']


def test_missing_dependency_visible():
    with mock.patch.object(capabilities, '_exists', side_effect=lambda typ, name: not (typ == 'program' and name == 'blender')):
        row = capabilities.inspect_tool({'id':'blender-engine', 'ar':'', 'en':'', 'cmd':'', 'what':''})
    assert row['status'] == 'missing_dependencies'
    assert 'program:blender' in row['missing']


def test_smart_and_full_plan_do_not_run_anything():
    smart = capabilities.plan('اعمل مونتاج ريل فيديو', mode='smart', limit=4)
    full = capabilities.plan('اعمل مونتاج ريل فيديو', mode='full', limit=4)
    for r in (smart, full):
        assert not r['execution_performed']
        assert len(r['selected_tools']) <= 4
        assert len(r['approval_gates']) >= 4
        assert all(x['proof_level']=='static_inspection_only' for x in r['selected_tools'])
    assert full['all_tools_examined'] == len(capabilities.read_registry())
    assert full['full_inspection']['total'] == len(capabilities.read_registry())
    assert smart['full_inspection'] is None


def test_empty_plan_rejected():
    with pytest.raises(ValueError):
        capabilities.plan('  ')
    with pytest.raises(ValueError):
        capabilities.plan('thing', mode='dangerous')


def test_setup_help_does_not_install(monkeypatch):
    spec = importlib.util.spec_from_file_location('launcher_test', SKILL / 'scripts' / 'dragon.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with mock.patch.object(module.subprocess, 'call', side_effect=AssertionError('installation executed')):
        assert module.main(['setup', '--help']) == 0
        assert module.main(['setup', '--dry-run']) == 0
        assert module.main(['setup']) == 0
        assert module.main(['setup', '--bad-option']) == 2


def test_content_fingerprint_detects_same_mtime_same_length(tmp_path):
    spec = importlib.util.spec_from_file_location('launcher_stamp_test', SKILL / 'scripts' / 'dragon.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    f = tmp_path / 'foo.py'; f.write_text('alpha')
    a = module.bundle_stamp(tmp_path)
    stat = f.stat()
    f.write_text('bravo')
    os.utime(f, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert module.bundle_stamp(tmp_path) != a


def test_readonly_cli_json_runs():
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    p = subprocess.run([sys.executable, '-m', 'dragon', 'probe-tools', '--json'], cwd=str(SKILL),
                       capture_output=True, text=True, env=env, timeout=20)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)['inspection_only']
    p = subprocess.run([sys.executable, '-m', 'dragon', 'plan', 'مونتاج فيديو', '--mode', 'full', '--json'],
                       cwd=str(SKILL), capture_output=True, text=True, env=env, timeout=20)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)['full_inspection']['total'] == len(capabilities.read_registry())


def test_build_own_is_idempotent_and_preserves_index():
    # isolated DB copy to avoid mutation of the original shipped user catalog
    import sqlite3
    from shutil import copy2
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as folder:
        db=Path(folder)/'catalog.sqlite'
        copy2(catalog.DB, db)
        probe=sqlite3.connect(db)  # v10.13: closed explicitly, Windows cannot delete an open file (WinError 32)
        before=probe.execute('SELECT count(*) FROM items').fetchone()[0]
        probe.close()
        con=sqlite3.connect(db)
        catalog.register_own(con=con)
        catalog.register_own(con=con)
        con.commit()
        after=con.execute('SELECT count(*) FROM items').fetchone()[0]
        own=con.execute("SELECT count(*) FROM items WHERE source='black-dragon'").fetchone()[0]
        assert own == len(capabilities.read_registry()) and after >= before
        assert after - before <= 30
        con.close()


def test_superpowers_bridge_is_read_only(tmp_path):
    from dragon.superpowers import bridge
    root = tmp_path/'kosif-superpowers';root.mkdir()
    (root/'SKILL.md').write_text('name: kosif-superpowers')
    (root/'LOADER.md').write_text('# loader')
    (root/'scripts').mkdir()
    (root/'scripts'/'hub.py').write_text('raise Exception("must never execute")')
    result = bridge('مونتاج', root=root, full=True)
    assert result['connected_locally'] and result['full_power_requested']
    assert not result['executed']
    assert any('hub.py find' in x['command_template'] for x in result['steps'])
    assert all(x['run'] is False for x in result['steps'])
