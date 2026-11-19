"""Reel DNA offline execution tests. Never calls Higgsfield or a generation API."""
import importlib.util
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'tools' / 'reel_dna' / 'reel_dna.py'


def call(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True)


def sample(tmp_path):
    analysis=tmp_path/'analysis.json';energy=tmp_path/'energy.json';beats=tmp_path/'beats.json';words=tmp_path/'words.json'
    analysis.write_text(json.dumps({'duration':2.0,'fps':30,'cuts':[{'time':1.0,'confidence':.94}]}))
    energy.write_text(json.dumps({'events':[{'time':.15,'type':'flash','intensity':.75},{'time':1.25,'type':'shake'},{'time':1.5,'type':'no_known_type'}]}))
    beats.write_text(json.dumps({'beats':[.0,.5,1.,1.5]}))
    words.write_text(json.dumps({'words':[{'start':0.1,'end':0.3,'word':'مرحبا'}]}))
    return analysis, energy, beats, words


def test_extract_preserves_frame_boundaries_and_warnings(tmp_path):
    a,e,b,w=sample(tmp_path); output=tmp_path/'dna.json'
    r=call('extract','--analysis',a,'--energy',e,'--beats',b,'--words',w,'--out',output)
    assert r.returncode==0, r.stderr
    d=json.loads(output.read_text());assert d['schema']=='kosif.reel-dna.v1'
    assert d['total_frames']==60 and [x['duration_frames'] for x in d['shots']]==[30,30]
    assert d['cuts']==[{'frame':30,'confidence':.94}]
    assert [x['type'] for x in d['energy_events']]==['flash','shake']
    assert d['beat_frames']==[0,15,30,45]
    assert d['words'][0]['text']=='مرحبا'
    assert any('not mapped' in n for n in d['warnings'])
    assert d['sources']['analysis']['sha256']


def test_reject_unknown_analysis_schema(tmp_path):
    a=tmp_path/'a.json';a.write_text(json.dumps({'duration':4,'fps':30,'mystery':[1,2]}))
    r=call('extract','--analysis',a,'--out',tmp_path/'out.json')
    assert r.returncode!=0 and 'No supported cuts' in r.stderr


def test_reject_negative_out_of_range_cut(tmp_path):
    a=tmp_path/'a.json';a.write_text(json.dumps({'duration':2,'fps':30,'cuts':[-1]}))
    r=call('extract','--analysis',a,'--out',tmp_path/'out.json')
    assert r.returncode!=0 and not (tmp_path/'out.json').exists()
    a.write_text(json.dumps({'duration':2,'fps':30,'cuts':[4]}))
    r=call('extract','--analysis',a,'--out',tmp_path/'out.json')
    assert r.returncode!=0


def test_shot_input_without_cut_list(tmp_path):
    a=tmp_path/'a.json';a.write_text(json.dumps({'duration':2,'fps':30,'shots':[{'start':0,'end':.8},{'start':.8,'end':2}]}))
    r=call('extract','--analysis',a,'--out',tmp_path/'out.json')
    assert r.returncode==0,r.stderr
    assert [x['duration_frames'] for x in json.loads((tmp_path/'out.json').read_text())['shots']]==[24,36]


def test_katana_commands_only_prints_and_escapes_shell(tmp_path):
    url="https://example.com/?x=;touch /tmp/HELLO&y='" 
    r=call('katana-commands','--workdir',tmp_path/'my work','--url',url)
    assert r.returncode==0,r.stderr
    assert 'source "$HF_WORKFLOWS/katana/scripts/rr.sh"' in r.stdout
    assert 'Nothing here has been executed' in r.stdout
    fetch_line=next(line for line in r.stdout.splitlines() if "fetch_ref.py" in line)
    assert shlex.split(fetch_line)[-1] == url # passes as one literal URL argument


def test_guide_classifies_no_higgsfield_connection():
    r=call('doctor');assert r.returncode==0
    d=json.loads(r.stdout)
    assert d['higgsfield_connected'] is False and d['katana_scripts_bundled'] is False


def test_apply_fingerprints_media(tmp_path):
    a,e,b,w=sample(tmp_path);r=call('extract','--analysis',a,'--out',tmp_path/'dna.json')
    assert r.returncode==0
    file1=tmp_path/'one.png';file2=tmp_path/'two.png'
    file1.write_bytes(b'owned media 1');file2.write_bytes(b'owned media 2')
    r=call('apply','--recipe',tmp_path/'dna.json','--clips',file1,file2,'--out',tmp_path/'edl.json')
    assert r.returncode==0,r.stderr
    d=json.loads((tmp_path/'edl.json').read_text())
    assert [x['duration_frames'] for x in d['clips']]==[30,30]
    assert all(x['file_sha256'] for x in d['clips'])
    assert 'original' not in json.dumps(d).lower()
    r=call('apply','--recipe',tmp_path/'dna.json','--clips',file1,'--out',tmp_path/'one-clips.json')
    assert r.returncode!=0


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),reason='requires FFmpeg')
def test_render_owned_media_frame_verified(tmp_path):
    a,e,b,w=sample(tmp_path)
    assert call('extract','--analysis',a,'--energy',e,'--out',tmp_path/'dna.json').returncode==0
    clips=[]
    for name,color in [('one','red'),('two','blue')]:
        path=tmp_path/f'{name}.png'
        proc=subprocess.run(['ffmpeg','-hide_banner','-v','error','-f','lavfi','-i',f'color={color}:s=160x160:d=0.1','-frames:v','1',str(path)],capture_output=True,text=True)
        assert proc.returncode==0,proc.stderr
        clips.append(path)
    r=call('apply','--recipe',tmp_path/'dna.json','--clips',*clips,'--out',tmp_path/'edl.json')
    assert r.returncode==0,r.stderr
    r=call('render','--edl',tmp_path/'edl.json','--out',tmp_path/'preview.mp4','--width','160','--height','240','--preview')
    assert r.returncode==0,r.stderr
    d=json.loads(r.stdout)
    assert d['frames']==60 and d['no_paid_generation'] is True
    assert (tmp_path/'preview.mp4').stat().st_size>1000
    # Refuse to clobber finished output
    r=call('render','--edl',tmp_path/'edl.json','--out',tmp_path/'preview.mp4')
    assert r.returncode!=0 and 'exists' in r.stderr
    # EDL enforces own-media SHA-256 fingerprint
    clips[0].write_bytes(b'tampered')
    r=call('render','--edl',tmp_path/'edl.json','--out',tmp_path/'other.mp4')
    assert r.returncode!=0 and 'fingerprint' in r.stderr


def test_dragon_launcher_help_integrated():
    r=subprocess.run([sys.executable,str(ROOT/'scripts'/'dragon.py'),'tool','reel-dna','--help'],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    assert 'katana-commands' in r.stdout


def test_offline_library_save_search_show(tmp_path):
    a,e,b,w=sample(tmp_path)
    r=call('extract','--analysis',a,'--out',tmp_path/'dna.json')
    assert r.returncode==0
    lib=tmp_path/'dna-vault'
    r=call('library','add','--library',lib,'--recipe',tmp_path/'dna.json','--name','ريل اختبار','--tags','دراما,سريع', '--description','اختبار قصير')
    assert r.returncode==0,r.stderr
    uid=json.loads(r.stdout)['added']
    r=call('library','list','--library',lib,'--query','ريل','--json')
    assert r.returncode==0
    assert json.loads(r.stdout)[0]['name']=='ريل اختبار'
    r=call('library','list','--library',lib,'--tag','غيرموجود','--json')
    assert json.loads(r.stdout)==[]
    r=call('library','show','--library',lib,uid)
    assert json.loads(r.stdout)['recipe']['total_frames']==60
    r=call('library','add','--library',lib,'--recipe',tmp_path/'dna.json','--name','ريل اختبار')
    assert r.returncode!=0 # duplicate name+content when exact description and tags? this version differs tags, same uid
