"""Blender Pro v10.5 bridge tests (never require or execute Blender)."""
from __future__ import annotations
import importlib.util
import json
import subprocess
import sys
import os
import shutil
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT.parent
BRIDGE = SKILL / 'tools' / 'blender-pro' / 'bridge.py'
SPEC = importlib.util.spec_from_file_location('blenderpro_v105', BRIDGE)
BP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BP)


def test_static_operations_139_without_bpy():
    with mock.patch.dict(sys.modules, {'bpy': None}):
        idx=BP.operation_index()
    assert len(idx)==12 and sum(len(x) for x in idx.values())==139
    assert {'text3d','camera','video','draw'}<=set(idx)
    assert 'text3d' in BP.all_ops() and 'text3d.text3d' in BP.all_ops()


@pytest.mark.parametrize('example', sorted(BP.PRESETS.glob('*.json')), ids=lambda p: p.name)
def test_all_uploaded_examples_validate(example):
    res=BP.validate_file(example)
    assert res['ok'],res['errors']
    assert res['sha256'] and res['execution_performed'] is False


def test_rejects_invalid_json_and_missing_file(tmp_path):
    p=tmp_path/'bad.json';p.write_text('{broken')
    assert not BP.validate_file(p)['ok']
    assert not BP.validate_file(tmp_path/'missing.json')['ok']


@pytest.mark.parametrize('bad',[
    {'steps':[{'op':'subprocess.run'}]},
    {'steps':[1]},
    {'steps':{}},
    {'scene':[],'steps':[]},
    {'steps':[],'render':{'out':'../escape.mp4'}},
    {'steps':[],'render':{'out':'C:\\Users\\Public\\escape.mp4'}},
    {'steps':[],'render':{'out':'foo\\..\\escape.mp4'}},
    {'steps':[],'render':['not-object']},
    []
])
def test_validation_rejects_bad_structure(bad):
    assert BP.validate_data(bad)


def test_plan_copies_only_to_new_path(tmp_path):
    src=BP.PRESETS/'arabic_gold_logo.json';dest=tmp_path/'plan.json'
    with mock.patch('subprocess.run', side_effect=AssertionError('subprocess should not run')):
        assert BP.main(['plan','arabic_gold_logo','--out',str(dest)])==0
    assert dest.read_bytes()==src.read_bytes()
    assert BP.main(['plan','arabic_gold_logo','--out',str(dest)])==1
    assert BP.main(['plan','../sneaky','--out',str(tmp_path/'copy2.json')])==1
    assert not (tmp_path/'copy2.json').exists()


def test_dry_run_never_executes(tmp_path):
    with mock.patch('subprocess.run', side_effect=AssertionError('Blender should not run')):
        assert BP.main(['render',str(BP.PRESETS/'product_shot.json'),'--out',str(tmp_path/'out')])==0
    assert not (tmp_path/'out').exists()


def test_explicit_render_without_blender_fails(tmp_path):
    with mock.patch.object(BP,'doctor',return_value={'blender_found':False}):
        with mock.patch('subprocess.run', side_effect=AssertionError('no Blender launch permitted')):
            assert BP.main(['render',str(BP.PRESETS/'product_shot.json'),'--out',str(tmp_path/'out'),'--execute'])==1


def test_doctor_is_readonly():
    with mock.patch('subprocess.run', side_effect=AssertionError('doctor executed program')):
        d=BP.doctor()
    assert d['modules']==12 and d['source_ops']==139 and d['runtime_execution_performed'] is False


def test_verify_text_evidence(tmp_path):
    f=tmp_path/'output.json';f.write_text('{"hello": "world"}')
    r=BP.verify(f)
    assert r['ok'] and r['sha256']==BP.digest(f) and not r['media_probed']
    f.write_text('{bad')
    assert BP.verify(f)['ok'] is False


def test_verify_real_media_probe(tmp_path):
    if not (shutil.which('ffmpeg') and shutil.which('ffprobe')):pytest.skip('ffmpeg not installed')
    p=tmp_path/'test.mp4'
    proc=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=160x90:r=10:d=0.2',
                        '-c:v','libx264','-pix_fmt','yuv420p','-y',str(p)],capture_output=True,text=True,timeout=20)
    if proc.returncode:pytest.skip('ffmpeg h264 encoder unavailable')
    r=BP.verify(p)
    assert r['ok'] and r['media_probed'] and r['streams'][0]['width']==160
    assert r['streams'][0]['codec']=='h264'


def test_registered_and_discoverable_entrypoint():
    sys.path.insert(0,str(ROOT))
    from dragon import capabilities
    rows=capabilities.read_registry()
    assert len(rows)>=35
    assert any(r["id"]=="rea-ultra" for r in rows)
    card=next(x for x in rows if x['id']=='blender-pro')
    found=capabilities.inspect_tool(card)
    assert found['entrypoint_found']
    assert found['status'] in ('discoverable','missing_dependencies')
    assert not found['executed']


def test_frontdoor_cli_no_blender_spawn(tmp_path):
    env=dict(os.environ,DRAGON_HOME=str(ROOT),PYTHONDONTWRITEBYTECODE='1')
    cmd=[sys.executable,str(SKILL/'scripts'/'dragon.py'),'tool','blender-pro','doctor']
    proc=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=15)
    assert proc.returncode==0 and json.loads(proc.stdout)['source_ops']==139
