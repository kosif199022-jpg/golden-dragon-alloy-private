"""Black Dragon v10.9 physics and math calculation, guardrails, roundtrip checks."""
from __future__ import annotations
import importlib.util
import io
import contextlib
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
BRIDGE=ROOT/'tools/physics_math/bridge.py'
SOURCE=ROOT/'skills/physics-math/scripts/phys.py'
ORIGINAL=ROOT/'skills/physics-math/upstream/phys-original.py'
spec=importlib.util.spec_from_file_location('bd109',BRIDGE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def call(*args):
    cap=io.StringIO()
    with contextlib.redirect_stdout(cap):
        code=mod.main([str(x) for x in args])
    try:obj=json.loads(cap.getvalue())
    except Exception as e:raise AssertionError(f'invalid JSON output {code}: {cap.getvalue()[:200]!r}') from e
    return code,obj


def test_bundle_and_doctor():
    assert SOURCE.is_file() and ORIGINAL.is_file()
    code,out=call('doctor')
    assert code==0 and out['ready'] and all(x['passed'] for x in out['smoke_checks'])
    assert len(mod.COMMANDS)==18
    assert not out['executed_render']

@pytest.mark.parametrize('expr,expected',[
    ('2+2',4),('sqrt(2*20/g)', math.sqrt(40/9.80665)),
    ('sin(pi/2)',1),('2^3',8),('abs(-4)+3',7),('log10(100)',2),('round(2.53,1)',2.5)])
def test_safe_calculator(expr,expected):
    code,out=call('calc',expr)
    assert code==0 and math.isclose(out['result'],expected,abs_tol=1e-5)

@pytest.mark.parametrize('expr',[
    '__import__("os").system("echo HACK")','(1).__class__','open("/etc/passwd")',
    '2**100000', '9'*300, '1/0','[1,2,3]', 'factorial(1000000)', 'float("nan")',
])
def test_calc_refuses_unsafe_or_excessive(expr):
    code,out=call('calc',expr)
    assert code!=0 and out['ok'] is False

@pytest.mark.parametrize('args,key,expected',[
    (('convert','72','km/h','m/s'),'result',20),
    (('convert','100','C','F'),'result',212),
    (('shape','sphere','--r','1'),'volume_m3',4*math.pi/3),
    (('motion','--distance','100','--speed','5'),'time_s',20),
    (('fall','--height','20'),'time_s',math.sqrt(40/9.80665)),
    (('camera','fov','--focal','50','--sensor','ff'),'hfov_deg',39.597753),
    (('camera','dolly','--focal','24','--focal2','48','--distance','3'),'end_distance_m',6),
    (('tc','--timecode','00:01:02:12','--fps','24'),'frames',1500),
    (('speed','--duration','10','--target','5'),'speed',2),
    (('frame','--src','1920x1080','--dst','1080x1920'),'dst_ratio',.5625),
    (('audio','--db','6'),'amplitude_ratio',10**(.3)),
    (('track','--px','40','--ref-px','420','--ref-m','1.75','--fps','30'),'speed_m_s',5),
])
def test_calculation_samples(args,key,expected):
    code,out=call(*args)
    assert code==0, out
    assert math.isclose(out[key],expected,abs_tol=1e-4), (args,out)

@pytest.mark.parametrize('args',[
    ('fall','--height','-3'),('fall','--height','20','--fps','0'),
    ('beats','--bpm','0'),('beats','--bpm','100','--duration','9999'),
    ('spring','--seconds','inf'),('camera','fit','--fill','0'),
    ('frame','--src','0x1080','--dst','1080x1920'),
    ('motion','--distance','10','--speed','0'),
    ('projectile','--speed','10000000'),
    ('bounce','--height','2','--restitution','1.5')
])
def test_bad_numeric_parameters(args):
    code,out=call(*args)
    assert code!=0 and out['ok'] is False


def test_keyframes_exclusive_write_and_receipt(tmp_path):
    dest=tmp_path/'beat.csv';receipt=tmp_path/'receipt.json'
    code,out=call('beats','--bpm','120','--fps','30','--duration','3','--out',dest,'--receipt',receipt)
    assert code==0,out
    assert dest.is_file() and receipt.is_file()
    assert out['beats_file']==str(dest)
    assert dest.read_text().count('\n')>=6
    assert call('verify',receipt)[1]['ok']
    data=dest.read_bytes()
    assert call('beats','--bpm','120','--out',dest)[0]!=0
    assert dest.read_bytes()==data
    dest.write_bytes(data+b'changed')
    code,check=call('verify',receipt)
    assert code==5 and not check['ok']


def test_receipt_result_tamper_detected(tmp_path):
    receipt=tmp_path/'c.json'
    code,_=call('calc','3*8','--receipt',receipt)
    assert code==0
    payload=json.loads(receipt.read_text(encoding='utf-8'))
    payload['result']['result']=100
    receipt.write_text(json.dumps(payload),encoding='utf-8')
    assert call('verify',receipt)[0]==5


def test_output_symlink_refused(tmp_path):
    target=tmp_path/'existing.json';target.write_text('SAFE')
    link=tmp_path/'ln.json'
    try:link.symlink_to(target)
    except OSError:pytest.skip('symlink unavailable')
    assert call('ease','linear','--frames','4','--out',link)[0]!=0
    assert target.read_text()=='SAFE'


def test_integrated_frontdoor_and_catalog():
    front=ROOT/'scripts/dragon.py'
    proc=subprocess.run([sys.executable,str(front),'tool','physics','doctor'],capture_output=True,text=True,timeout=20)
    assert proc.returncode==0,proc.stderr
    assert json.loads(proc.stdout)['ready']
    data=json.loads((ROOT/'app/data/own_tools.json').read_text())
    assert sum(r['id']=='physics-math' for r in data['tools'])==1
    assert 'physics-math' in (ROOT/'app/dragon/capabilities.py').read_text()


def test_outside_maths_not_claimed():
    code,out=call('calc','2+3')
    assert code==0 and not out['black_dragon']['generated_media']
    assert not out['black_dragon']['external_physical_accuracy_verified']

@pytest.mark.parametrize('args,key',[
    (('material',),'materials'),
    (('projectile','--speed','20','--angle','45'),'range_m'),
    (('bounce','--height','2','--restitution','.75'),'contacts'),
    (('spring','--start','0','--end','100','--seconds','0.5','--keys'),'keyframes'),
    (('ease','easeOutBack','--frames','12'),'keyframes'),
    (('scale','--model-scale','16','--fps','24'),'shoot_fps_for_real_look'),
])
def test_remaining_calculation_families(args,key):
    code,out=call(*args)
    assert code==0,out
    assert key in out
