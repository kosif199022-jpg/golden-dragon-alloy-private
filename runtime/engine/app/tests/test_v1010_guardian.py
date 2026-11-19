"""Black Dragon v10.10 selective Guardian backport: targeted offline tests."""
from __future__ import annotations
import hashlib, importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
LAUNCHER=ROOT/'scripts/dragon.py'
BASE_ZIP=Path('/mnt/data/black-dragon-v10.9.0.zip')  # not required at install time

def cmd(*args,env=None,timeout=45):
    return subprocess.run([sys.executable,str(LAUNCHER),*map(str,args)],env=env,capture_output=True,text=True,encoding='utf-8',timeout=timeout)

@pytest.fixture
def config(tmp_path):
    return dict(os.environ, PYTHONDONTWRITEBYTECODE='1', DRAGON_HOME=str(ROOT/'app'), DRAGON_STATE=str(tmp_path/'state'), MH_CACHE=str(tmp_path/'cache'), MH_OUT=str(tmp_path/'media'))

def test_merged_v109_skills_not_lost(config):
    d=json.loads((ROOT/'app/data/own_tools.json').read_text(encoding='utf-8'))['tools']
    ids={x['id'] for x in d}
    # v10.14: no duplicates, and nothing merged is lost (the registry grows each release, so no fixed count)
    assert len(ids)==len(d)>=50
    assert {'chrome-control','cloud-browser','kosif-downloads','lyric-ass','psd-studio',
            're-front-door','dragon-brain','superpowers-hub','atlas-picks'} <= ids
    assert {'physics-math','rea-ultra','visual-forge','blender-pro','absolute-creativity','media-hunter','ultra-mind','expert-council'}<=ids
    assert {'media-hunter-615','phone-play-check','dragon-status','dragon-last','dragon-resources','keyboard-layout-fix','repo-fusion'}<=ids
    assert cmd('tool','physics','doctor',env=config).returncode==0

def test_launcher_has_guardian_commands(config):
    assert cmd('tool','layout',';LG',env=config).stdout.strip()=='كمل'
    for arg in ('resources','status','last'):
        x=cmd(arg,'--json',env=config)
        assert x.returncode==0 and x.stdout.strip().startswith(('{','['))

def test_guardian_job_registration_only_local(config):
    x=cmd('status','--json',env=config)
    assert json.loads(x.stdout)=={'running':[],'recent':[]}
    x=cmd('tool','physics','doctor',env=config)
    assert x.returncode==0
    j=json.loads(cmd('status','--json',env=config).stdout)
    assert len(j['recent'])==1 and j['recent'][0]['state']=='done'
    assert j['recent'][0]['argv'][:2]==['tool','physics']

def test_missing_ffmpeg_graceful(config,monkeypatch,tmp_path):
    p=ROOT/'tools/care/care.py'
    spec=importlib.util.spec_from_file_location('temp_care_v1010',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    monkeypatch.setattr(m,'_exe',lambda _:None)
    sample=tmp_path/'test.mp4';sample.write_bytes(b'xxxxxxx')
    r=m.play_check(sample)
    assert not r['ok'] and r['errors']
    assert m.measure_loudness(sample) is None

def test_hunter_615_offline_index(config):
    x=cmd('tool','hunter615','sites','sea night','--type','video','--limit','6','--json',env=config,timeout=30)
    assert x.returncode==0,x.stderr
    rows=json.loads(x.stdout)
    assert len(rows)>2
    assert all('license' in r and 'url' in r for r in rows)
    import csv
    with (ROOT/'tools/media_hunter_615/data/media_sites_615.csv').open(encoding='utf-8-sig',newline='') as fh:
        assert sum(1 for _ in csv.reader(fh))-1==615

def test_hunter_requires_license_acknowledgment(config):
    x=cmd('tool','hunter615','get','1',env=config)
    assert x.returncode!=0 and 'acknowledge-license' in x.stderr
    assert not Path(config['MH_OUT']).exists()

def test_hunter_refuses_unverified_licence_without_network(config):
    Path(config['MH_CACHE']).mkdir(parents=True)
    (Path(config['MH_CACHE'])/'last_results.json').write_text(json.dumps({'query':'x','results':[{'media_url':'https://example.invalid/asset.mp4','title':'X','license':'unknown','source':'x','page_url':'https://example.invalid'}]}))
    x=cmd('tool','hunter615','get','1','--acknowledge-license',env=config)
    assert x.returncode!=0 and 'license unverified' in x.stdout
    assert not list(Path(config['MH_OUT']).rglob('*.mp4'))

def test_hunter_invalid_index_fails_cleanly(config):
    Path(config['MH_CACHE']).mkdir(parents=True)
    (Path(config['MH_CACHE'])/'last_results.json').write_text(json.dumps({'query':'x','results':[]}))
    x=cmd('tool','hunter615','get','99','--acknowledge-license',env=config)
    assert x.returncode!=0 and 'out of range' in x.stdout

def test_no_auto_package_install(config):
    x=cmd('setup',env=config)
    assert x.returncode==0 and 'dry-run' in x.stdout.lower()

def test_fusion_available_offline(config):
    x=cmd('tool','fusion','list',env=config)
    assert x.returncode==0 and 'librosa/librosa' in x.stdout

def test_content_version():
    # v10.13: the engine version follows the SKILL.md title (it was frozen at 10.10.0 through v10.12).
    import re
    eng = re.search(r'__version__ = "([\d.]+)"', (ROOT/'app/dragon/__init__.py').read_text()).group(1)
    title = re.search(r'^# Black Dragon .*\(v([\d.]+)', (ROOT/'SKILL.md').read_text(encoding='utf-8'), re.M).group(1)
    assert eng == title

@pytest.mark.skipif(not (shutil.which('ffmpeg') and shutil.which('ffprobe')),reason='FFmpeg unavailable')
def test_faststart_warning_fix_through_launcher(config,tmp_path):
    src=tmp_path/'slowstart.mp4'
    r=subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:s=320x568:d=1',
                      '-f','lavfi','-i','sine=d=1','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(src)],capture_output=True,text=True,timeout=30)
    assert r.returncode==0,r.stderr
    src_hash=hashlib.sha256(src.read_bytes()).hexdigest()
    x=cmd('play-check',src,'--fix','--json',env=config,timeout=50)
    assert x.returncode==0,(x.stdout,x.stderr)
    j=json.loads(x.stdout)[0]
    assert j.get('fixed') and Path(j['fixed']).exists()
    assert hashlib.sha256(src.read_bytes()).hexdigest()==src_hash
    assert j['fixed_check']['ok']
    from importlib import util
    sp=util.spec_from_file_location('care_atom',ROOT/'tools/care/care.py');m=util.module_from_spec(sp);sp.loader.exec_module(m)
    atoms=[p[0] for p in m.top_atoms(j['fixed'])]
    assert atoms.index('moov') < atoms.index('mdat')
