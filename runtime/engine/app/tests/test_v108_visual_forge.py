"""v10.8 visual-forge integration: source-aware, safe outputs, real local FX."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
BRIDGE=ROOT/'tools/visual_forge/bridge.py'
spec=importlib.util.spec_from_file_location('bd108_bridge',BRIDGE)
vf=importlib.util.module_from_spec(spec)
spec.loader.exec_module(vf)


def sample(kind='video'):
    v={'title':'Coffee in rain','brief':'Two cinematic shots of coffee in rain','kind':kind,'ratio':'9:16',
       'medium':'cinematic photograph',
       'look':{'lighting':'soft blue light with warm highlights','lens':'35mm lens',
               'atmosphere':'rain','style':'moody urban cinema',
               'anchors':'a small amber cup with a gold rim'},
       'shots':[{'id':1,'purpose':'hook','subject':'a small amber cup on a terrace',
                 'action':'steam rising slowly','setting':'covered terrace at night',
                 'camera':{'framing':'medium shot'},'motion':'steam slowly rises into the air',
                 'camera_move':'slow push in', 'duration':5, 'text':'العنوان'}]}
    return v


def plan_file(tmp_path, data=None):
    file=tmp_path/'plan.json';file.write_text(json.dumps(data or sample(),ensure_ascii=False))
    return file


def run_cli(*args):
    return subprocess.run([sys.executable,str(BRIDGE),*map(str,args)],capture_output=True,text=True,timeout=25)


def test_bundled_source_and_safety_doc():
    assert vf.SOURCE.is_file()
    assert (vf.SRC/'upstream/forge-original.py').is_file()
    assert (vf.SRC/'references/chatgpt-image.md').is_file()
    assert (vf.SRC/'references/kling-video.md').is_file()
    assert not vf.doctor()['paid_generators_called']


def test_atmos_count_is_21_not_20():
    assert vf.doctor()['atmosphere_presets']==21
    assert len(vf.original().ATMOS)==21


def test_no_paid_client_or_network_in_bridge():
    text=BRIDGE.read_text();assert 'requests.get(' not in text and 'eval(' not in text


@pytest.mark.parametrize('value',[-1,0,41,100])
def test_shot_count_limits(tmp_path,value):
    r=run_cli('plan','--brief','Scene','--shots',value,'--out',tmp_path/'empty')
    assert r.returncode==2


def test_plan_from_cli_and_existing_protection(tmp_path):
    out=tmp_path/'demo'
    first=run_cli('plan','--brief','A cinematic desert story','--shots',2,'--out',out)
    assert first.returncode==0,first.stderr
    before=(out/'plan.json').read_bytes()
    second=run_cli('plan','--brief','overwrite attempt','--shots',2,'--out',out)
    assert second.returncode==2
    assert (out/'plan.json').read_bytes()==before


def test_prompt_lint_receipt_and_tamper(tmp_path):
    p=plan_file(tmp_path)
    result=vf.prompts(p)
    assert result['ok'] and result['files_written']==3 and not result['generated_media']
    receipt=Path(result['receipt'])
    assert vf.verify(receipt)['ok']
    image=(receipt.parent/'image_01.txt')
    assert 'do not render any text' in image.read_text()
    image.write_text(image.read_text()+'tampered')
    assert not vf.verify(receipt)['ok']
    assert run_cli('verify-prompts',receipt).returncode==5


def test_plan_change_detected(tmp_path):
    p=plan_file(tmp_path);r=vf.prompts(p)
    p.write_text(p.read_text()+' ')
    assert 'source plan changed' in ' '.join(vf.verify(r['receipt'])['errors'])


def test_prompts_refuse_overwrite(tmp_path):
    p=plan_file(tmp_path);r=vf.prompts(p)
    original=(tmp_path/'prompts/image_01.txt').read_bytes()
    with pytest.raises(ValueError,match='already exist'):
        vf.prompts(p)
    assert (tmp_path/'prompts/image_01.txt').read_bytes()==original


@pytest.mark.parametrize('edit',[lambda p:p.update(ratio='99:20'),
                                 lambda p:p.update(shots=[]),
                                 lambda p:p['shots'][0].update(id='../../x'),
                                 lambda p:p.update(shots=[p['shots'][0],p['shots'][0].copy()]),
                                 lambda p:p['shots'][0].update(duration=123),
                                 lambda p:p['shots'][0].update(subject='')])
def test_invalid_plan_rejected_before_write(tmp_path,edit):
    p=sample();edit(p);file=plan_file(tmp_path,p)
    with pytest.raises(ValueError):vf.prompts(file)
    assert not (tmp_path/'prompts').exists()


def test_lint_failure_does_not_write(tmp_path):
    data=sample();data['shots'][0]['motion']='';data['shots'][0]['camera_move']=''
    p=plan_file(tmp_path,data)
    with pytest.raises(ValueError,match='motion'):
        vf.prompts(p)
    assert not (tmp_path/'prompts').exists()


@pytest.mark.parametrize('recipe',['@not-a-real-atmosphere','notanfx:0.3','grain:-0.5','fog:1.1','grade:nonsense:0.3','rain:nan','rain:inf'])
def test_invalid_fx_rejected(recipe):
    with pytest.raises(ValueError):vf.validate_recipe(recipe)


def test_deterministic_fx(tmp_path):
    import numpy as np, cv2
    img=np.zeros((80,90,3),dtype=np.uint8);img[:,:,:]=(35,74,120)
    src=tmp_path/'in.png';cv2.imwrite(str(src),img)
    vf.fx(src,tmp_path/'a.png','rain:0.7,fog:0.3',seed=17)
    vf.fx(src,tmp_path/'b.png','rain:0.7,fog:0.3',seed=17)
    assert (tmp_path/'a.png').read_bytes()==(tmp_path/'b.png').read_bytes()
    assert src.read_bytes()!= (tmp_path/'a.png').read_bytes()


def test_film_alpha_preserved(tmp_path):
    import numpy as np,cv2
    a=np.zeros((80,90,4),dtype=np.uint8);a[:,:,:3]=[22,55,88];a[:,:,3]=np.arange(90,dtype=np.uint8)[None,:]
    src=tmp_path/'alpha.png';cv2.imwrite(str(src),a)
    result=vf.fx(src,tmp_path/'fx.png','grain:0.3',seed=3)
    dst=cv2.imread(str(tmp_path/'fx.png'),cv2.IMREAD_UNCHANGED)
    assert dst.shape==a.shape
    assert np.array_equal(dst[:,:,3],a[:,:,3])
    assert result['media_created_locally']
    with pytest.raises(ValueError,match='JPEG'):
        vf.fx(src,tmp_path/'out.jpg','grain:0.3')


def test_fx_not_overwrite(tmp_path):
    import numpy as np,cv2
    src=tmp_path/'pic.png';cv2.imwrite(str(src),np.ones((24,24,3),dtype=np.uint8)*20)
    dst=tmp_path/'out.png';dst.write_bytes(b'KEEP THIS')
    with pytest.raises(ValueError,match='overwrit'):
        vf.fx(src,dst,'grain:0.5')
    assert dst.read_bytes()==b'KEEP THIS'
    with pytest.raises(ValueError):vf.fx(src,src,'grain:0.5')


def test_symlink_input_refused(tmp_path):
    x=tmp_path/'a.png';x.write_bytes(b'hello');s=tmp_path/'link.png'
    try:s.symlink_to(x)
    except OSError:pytest.skip('symlink unavailable')
    with pytest.raises(ValueError):vf.fx(s,tmp_path/'out.png','grain:0.4')


def test_actual_video_fx_keeps_aac_packets(tmp_path):
    if not vf.doctor()['local_video_fx_dependencies_ready']:pytest.skip('ffmpeg/numpy/cv2 missing')
    src=tmp_path/'in.mp4';dst=tmp_path/'out.mp4'
    r=subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=s=160x90:d=0.8:r=12',
                      '-f','lavfi','-i','sine=frequency=450:duration=0.8','-shortest',
                      '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(src)],capture_output=True,text=True,timeout=15)
    assert r.returncode==0,r.stderr
    res=vf.fx(src,dst,'@rain',seed=3)
    def audio_hash(path):
        p=subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_packets',
                          '-show_entries','packet=data_hash','-show_data_hash','SHA256',
                          '-of','compact',str(path)],capture_output=True,text=True,timeout=15)
        assert p.returncode==0,p.stderr
        return [ln for ln in p.stdout.splitlines() if 'data_hash=' in ln]
    assert audio_hash(src)==audio_hash(dst)
    assert res['audio_mode'].startswith('copy')
    stream=subprocess.run(['ffprobe','-v','error','-show_entries','stream=width,height,codec_name',
                           '-of','json',str(dst)],capture_output=True,text=True,timeout=15)
    assert stream.returncode==0
    streams=json.loads(stream.stdout)['streams']
    assert streams[0]['width']==160 and streams[0]['height']==90
    assert dst.stat().st_size>1000


def test_frontdoor_and_registry(tmp_path):
    full=ROOT/'scripts/dragon.py'
    a=subprocess.run([sys.executable,str(full),'tool','visual-forge','doctor'],capture_output=True,text=True,timeout=20)
    assert a.returncode==0
    assert json.loads(a.stdout)['source_script_present']
    j=json.loads((ROOT/'app/data/own_tools.json').read_text())
    assert sum(v['id']=='visual-forge' for v in j['tools'])==1
    assert 'visual-forge' in (ROOT/'app/dragon/capabilities.py').read_text()
