"""Black Dragon v10: deterministic suite, negative tests and one actual local FFmpeg output."""
from __future__ import annotations
import json,sys,subprocess
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dragon import v10_cognition,v10_catalog,v10_media,v10_kling,v10_gate,v10_color


def put(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
    return p


def brief():return {'goal':'test ad','audience':'local','platform':'reels','aspect':'9:16',
                    'resolution':'256x448','duration_s':2,'message':'test only','hero':'product'}


def concept():return {'options':[{'id':f'c{i}','approach':f'different idea {i}','evidence':'user brief',
                                     'risk':'might fail'} for i in range(3)],
                      'selected':'c1','falsifier':'no improved audience result','baseline':'old cut','hook':'clear promise'}


def palette():return {'palette':['#161616','#EEEEDD','#D82020'],'ratios':[60,30,10],
                      'accent_on':'brand word', 'enforce_pixel_ratio':False}


def test_decision_gate_catches_missing_options():
    assert v10_cognition.validate_decision({'options':[{'id':'A'}]})
    assert not v10_cognition.validate_decision(concept())


def test_source_based_thinking_is_never_execution():
    x=v10_cognition.checklist('مونتاج فيلم',domain='video')
    assert x['execution_performed'] is False
    assert any(i['id']=='overconfidence' for i in x['methods'])


def test_full_coverage_not_inferred_from_catalog():
    a=v10_catalog.audit(limit=0)
    assert a['total_index_records']>=a['registered_local_tools']
    assert a['executed_in_this_audit']==0 and a['full_coverage'] is False
    assert (a['static_discoverable']+a['missing_dependencies']+a['unverified_entrypoint'])==a['registered_local_tools']


def test_kling_blocks_have_safe_lengths():
    from copy import deepcopy
    s={'title':'demo','goal':'save a letter','obstacle':'door shuts','reversal':'had key all along',
       'value_before':'fear','value_after':'relief','character':'adult actor','location':'library',
       'duration_s':61,'aspect':'9:16'}
    d=v10_kling.make_pack(s)
    assert len(d['blocks'])==3
    assert sum(b['duration_s'] for b in d['blocks'])==61
    assert all(3<=b['duration_s']<=30 for b in d['blocks'])
    assert d['actual_generation'] is False and d['paid_credits_spent']==0
    assert all(b['local_prompt_lint']['pass'] for b in d['blocks'])
    s['flash']=True
    x=v10_kling.make_pack(s)
    assert len(x['blocks'])==4
    assert all(3<=b['duration_s']<=20 for b in x['blocks'])


def test_kling_input_validation():
    with pytest.raises(ValueError):v10_kling.make_pack({'title':'x'})


def test_readonly_audit_missing_file(tmp_path):
    doc=v10_media.inspect([tmp_path/'absent.mp4'])
    assert not doc['all_probed'] and doc['files'][0]['status']=='missing'


def test_gate_init_rejects_incomplete_brief(tmp_path):
    with pytest.raises(ValueError):v10_gate.init(tmp_path/'job',put(tmp_path/'brief.json',{'goal':'x'}))


def test_gate_enforces_order_and_preview(tmp_path):
    j=tmp_path/'job';v10_gate.init(j,put(tmp_path/'brief.json',brief()))
    with pytest.raises(ValueError):v10_gate.record(j,'shots',put(tmp_path/'shots.json',{}))
    v10_gate.record(j,'brief',tmp_path/'brief.json')
    v10_gate.record(j,'concept',put(tmp_path/'concept.json',concept()))
    v10_gate.record(j,'color-design',put(tmp_path/'palette.json',palette()))
    board=tmp_path/'board.svg';board.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    shots={'shots':[{'start_s':0,'end_s':2,'reason':'hook','what':'show product'}],
           'storyboard':str(board),'preview_approved':False}
    with pytest.raises(ValueError):v10_gate.record(j,'shots',put(tmp_path/'shots.json',shots))
    shots['preview_approved']=True
    v10_gate.record(j,'shots',put(tmp_path/'shots.json',shots))
    assert not v10_gate.check(j)['pass']


def test_manual_qa_receipt_rejected(tmp_path):
    j=tmp_path/'job';v10_gate.init(j,put(tmp_path/'brief.json',brief()))
    with pytest.raises(ValueError):v10_gate.record(j,'qa-color',put(tmp_path/'fake.json',{}))


def test_render_preview_no_side_effect(tmp_path):
    p=tmp_path/'new.mp4';r=v10_gate.render_run(p,['ffmpeg','-y','-i','local.mp4',str(p)])
    assert r['execution_performed'] is False and not p.exists()


def test_render_execute_requires_approved_job(tmp_path):
    p=tmp_path/'now.mp4'
    with pytest.raises(ValueError,match='requires --job'):
        v10_gate.render_run(p,['ffmpeg','-i','input.mp4',str(p)],execute=True)


def test_render_rejects_remote_and_existing(tmp_path):
    p=tmp_path/'old.mp4';p.write_bytes(b'keep')
    with pytest.raises(ValueError):v10_gate.render_run(p,['ffmpeg','-i','user.mp4',str(p)])
    with pytest.raises(ValueError):v10_gate.render_run(tmp_path/'new.mp4',['ffmpeg','-i','https://example.org/asset.mp4',str(p)])
    with pytest.raises(ValueError):v10_gate.render_run(tmp_path/'new.mp4',['curl','-O','test'])


def test_link_index_is_clearly_unverified():
    p=ROOT/'data'/'v10_media_links.json'
    r=json.loads(p.read_text(encoding='utf-8'))
    assert r['count_numbered']==115 and r['count_extra']==12
    assert all(x['rights']=='unknown' and x['opened'] is False for x in r['numbered']+r['extras'])


def test_lab_color_distance():
    assert 0 <= v10_color._delta(v10_color._lab((23,23,23)),v10_color._lab((24,24,24))) < 2
    assert v10_color._delta(v10_color._lab((0,0,0)),v10_color._lab((255,255,255)))>=99


@pytest.mark.skipif(not __import__('shutil').which('ffmpeg'),reason='FFmpeg required')
def test_real_ffmpeg_delivery_gate_and_tamper(tmp_path):
    """Actual local render, checked by ffprobe, black-frame decoder and pixel sampler."""
    j=tmp_path/'job'
    v10_gate.init(j,put(tmp_path/'brief.json',brief()))
    v10_gate.record(j,'brief',tmp_path/'brief.json')
    v10_gate.record(j,'concept',put(tmp_path/'concept.json',concept()))
    v10_gate.record(j,'color-design',put(tmp_path/'palette.json',palette()))
    board=tmp_path/'storyboard.svg';board.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    v10_gate.record(j,'shots',put(tmp_path/'shots.json',
          {'shots':[{'start_s':0,'end_s':2,'what':'show red product','reason':'clarity'}],
           'storyboard':str(board),'preview_approved':True}))
    output=tmp_path/'video.mp4'
    ff='ffmpeg'
    cmd=[ff,'-hide_banner','-loglevel','error','-nostdin','-f','lavfi','-i',
         'color=c=red:s=256x448:r=30:d=2','-c:v','libx264','-pix_fmt','yuv420p',str(output)]
    receipt=v10_gate.render_run(output,cmd,execute=True,job=j)
    assert receipt['exit_code']==0 and receipt['output_sha256']
    rfile=put(tmp_path/'render.json',receipt)
    v10_gate.record(j,'produce',put(tmp_path/'produce.json',
          {'video_file':str(output),'renderer':'test ffmpeg color','render_receipt':str(rfile),'paid':False}))
    qa=v10_gate.qa(j)
    assert qa['recorded'] and qa['stage']=='qa-color'
    evidence=json.loads((j/'stages'/'qa-color.json').read_text())['data']
    assert evidence['color_qa']['sampled_frames']==7
    v10_gate.record(j,'deliver',put(tmp_path/'deliver.json',
           {'summary':'test file','executed':['ffmpeg locally'],'not_executed':['Kling'], 'rights_reviewed':True}))
    assert v10_gate.check(j)['pass']
    assert v10_gate.check(j)['render_executed_with_receipt']
    board.write_text(board.read_text()+' ')  # same path, new bytes
    fail=v10_gate.check(j)
    assert not fail['pass'] and any('artifact' in e for e in fail['errors'])
