"""Offline static and frame-checked Cinema Craft tests. No network or external services."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
TOOL=ROOT/'tools/cinema_craft/cinema_craft.py'

def run(*args):return subprocess.run([sys.executable,str(TOOL),*map(str,args)],capture_output=True,text=True)

def spec(tmp_path):
    a=tmp_path/'film.json'
    a.write_text(json.dumps({'duration':2,'shots':[{'d':1,'src':'a','tr':{'type':'dissolve','d':0.1},'kb':{'s0':1.15,'s1':1.0}},{'d':1,'src':'b','tr':{'type':'leak','d':.1}}],'texts':[{'text':'مرحبا','y':.86,'glow':True}]}))
    return a

def test_doctor_is_readonly():
    r=run('doctor');assert r.returncode==0,r.stderr
    d=json.loads(r.stdout)
    assert d['source']=='_skills.rar' and d['paid_generation'] is False
    assert d['reference_scripts_executed'] is False

def test_spec_audit_match(tmp_path):
    r=run('spec-audit','--input',spec(tmp_path));assert r.returncode==0,r.stderr
    d=json.loads(r.stdout);assert d['passed'] and d['shots']==2 and d['texts']==1

def test_spec_audit_mismatch(tmp_path):
    f=spec(tmp_path);d=json.loads(f.read_text());d['duration']=3;f.write_text(json.dumps(d))
    r=run('spec-audit','--input',f);assert r.returncode!=0 and 'not' not in r.stderr.lower()
    assert json.loads(r.stdout)['warnings']

def test_style_only_new_file(tmp_path):
    a=spec(tmp_path);h=hashlib.sha256(a.read_bytes()).digest();dst=tmp_path/'styled.json'
    r=run('style','--input',a,'--out',dst)
    assert r.returncode==0,r.stderr
    assert hashlib.sha256(a.read_bytes()).digest()==h
    d=json.loads(dst.read_text());assert [s['tr']['type'] for s in d['shots']]==['iris','iris']
    assert d['shots'][0]['kb']['s0']<d['shots'][0]['kb']['s1']
    assert d['texts'][0]['y']<=.72 and 'glow' not in d['texts'][0]
    assert run('style','--input',a,'--out',dst).returncode!=0

def test_invalid_specs(tmp_path):
    p=tmp_path/'bad.json';p.write_text('{"shots":[{"d":-1}]}')
    assert run('spec-audit','--input',p).returncode!=0
    assert run('style','--input',p,'--out',tmp_path/'new.json').returncode!=0

def test_genius_exact_match_manifest():
    m=json.loads((ROOT/'SOURCE_CINEMA_ARCHIVE.json').read_text())
    assert m['dragon_genius_exact_duplicate'] and m['dragon_genius_files_verified']==8
    assert m['source_file_count']==17
    for name,h in m['source_files_sha256'].items():
        if name.startswith(('black-dragon-cinema/','creative-studio/')):
            p=ROOT/'references/source_archives/skills-rar'/name
        elif name=='black-dragon/SKILL.md':p=ROOT/'references/source_archives/skills-rar/legacy-black-dragon-SKILL.md'
        elif name=='black-dragon/REBUILD_PLAN.md':p=ROOT/'references/source_archives/skills-rar/legacy-black-dragon-REBUILD_PLAN.md'
        else:raise AssertionError(name)
        assert hashlib.sha256(p.read_bytes()).hexdigest()==h, name

def test_router_help():
    r=subprocess.run([sys.executable,str(ROOT/'scripts/dragon.py'),'tool','cinema-craft','--help'],capture_output=True,text=True)
    assert r.returncode==0, r.stderr
    assert 'spec-audit' in r.stdout and 'style' in r.stdout and 'cut' in r.stdout

@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),reason='FFmpeg needed')
def test_cut_frame_exact_and_preserves_source(tmp_path):
    src=tmp_path/'in.mp4';out=tmp_path/'out.mp4'
    made=subprocess.run(['ffmpeg','-hide_banner','-nostdin','-loglevel','error','-f','lavfi','-i','testsrc2=size=160x240:rate=30:duration=2','-c:v','libx264','-pix_fmt','yuv420p','-y',str(src)],capture_output=True,text=True)
    assert made.returncode==0,made.stderr
    src_hash=hashlib.sha256(src.read_bytes()).digest()
    r=run('cut','--input',src,'--start','0.5','--end','1.5','--fps','30','--out',out)
    assert r.returncode==0,r.stderr
    assert json.loads(r.stdout)['frames_verified']==30
    assert src_hash==hashlib.sha256(src.read_bytes()).digest()
    assert run('cut','--input',src,'--start','.5','--end','1.5','--out',out).returncode!=0
    assert run('cut','--input',src,'--start','1.8','--end','1.1','--out',tmp_path/'bad.mp4').returncode!=0
    assert not (tmp_path/'bad.mp4').exists()
