"""Absolute Creativity v10.6: deterministic stimuli, honest human rubric, no automatic remote execution."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock
import pytest

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT.parent
BRIDGE=PKG/'tools/absolute_creativity/bridge.py'
SPEC=importlib.util.spec_from_file_location('bd106creativity',BRIDGE)
CR=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CR)


def filled():
    p=CR.brief('فيلم توعوي عن القراءة')
    p.update(audience='أطفال 10-12',emotion='الأمل',central_message='القراءة تفتح الآفاق',
             platform='ريلز',duration_s=30,aspect='9:16',creative_constraint='بدون وجوه',
             rejected_cliches=['كتب طائرة','مصباح فوق الرأس','طفل يبتسم أمام مكتبة'],
             chosen_id='C2', selection_reason='البديل الثاني أبلغ مع موارد الإنتاج')
    for i,c in enumerate(p['concepts']):
        c.update(name=f'فكرة {i}',logline=f'وصف الفكرة {i}',mechanism=f'آلية مختلفة {i}',
                 distinctive_image=f'صورة بارزة {i}',scorer='اختبار يدوي اصطناعي',
                 score_basis='قيمة تجريبية للاختبارات وليست مراجعة إنتاج')
        c['scores']=dict(originality=4,emotional_truth=4,clarity=4,feasibility=4,memorability=3)
    p['concepts'][1]['scores']['memorability']=5
    return p


def style():
    return {'title':'صفحة إبداعية', 'concept_id':'C2','story_beats':'3s Hook, 20s middle, 7s resolve',
            'camera':'wide to close-up', 'edit_rhythm':'alternating 1.5 and 3s cuts',
            'sound':'minimal Foley', 'typography':'Arabic Cairo bold PNG',
            'art_direction':'dark blue and cream on paper', 'palette':['#101820','#F5F5F0','#E9B44C'],
            'constraints':['no faces'],'assets':[]}


def test_source_9_guides_and_no_cache():
    d=CR.doctor()
    assert d['reference_guides']==9 and not d['font_cache_bundled']
    assert d['skill_loaded'] and d['idea_engine_present'] and not d['network_used']


def test_source_retained_original_decks():
    m=CR.load_ideas()
    assert len(m.DECKS)==10
    assert len(m.CARDS)==20


@pytest.mark.parametrize('n',[1,3,12,50,100])
def test_deterministic_spin(n):
    z=CR.load_ideas().spin('A creative task',n,7)
    assert z==CR.load_ideas().spin('A creative task',n,7)
    assert len(z)==n
    assert all(row['brief']=='A creative task' for row in z)


@pytest.mark.parametrize('n',[-2,0,101,1000])
def test_reject_oversized_seed_work(n):
    with pytest.raises(ValueError):CR.load_ideas().spin('task',n,3)


def test_empty_brief_fails_honestly():
    r=CR.audit(CR.brief('Task'))
    assert not r['ok'] and not r['originality_verified'] and not r['execution_performed']


def test_filled_manual_rubric_structure():
    r=CR.audit(filled())
    assert r['ok'] and len(r['scores'])==3
    assert r['scores'][1]['total']==21 and r['scores'][1]['passes_rubric']
    assert not r['agent_calls_verified'] and not r['originality_verified']


@pytest.mark.parametrize('edit',[lambda p:p.update(chosen_id='C9'),
                                lambda p:p.update(rejected_cliches=['one','one','three']),
                                lambda p:p['concepts'][2].update(name='فكرة 1'),
                                lambda p:p['concepts'][2].update(mechanism='آلية مختلفة 1'),
                                lambda p:p['concepts'][0]['scores'].update(originality=2),
                                lambda p:p['concepts'][1]['scores'].update(originality=True),
                                lambda p:p['concepts'][1].update(scorer=''),
                                lambda p:p.update(duration_s=-2),
                                lambda p:p.update(creative_constraint=''),
                                lambda p:p.update(concepts=p['concepts'][:2])])
def test_invalid_or_misleading_packet(edit):
    p=filled();edit(p)
    r=CR.audit(p)
    # non-chosen low originality may be allowed; it cannot be chosen.
    if p['concepts'][0]['scores'].get('originality')==2:
        assert r['ok'] and not r['scores'][0]['passes_rubric']
    else:
        assert not r['ok']


def test_winner_not_qualified():
    p=filled();p['concepts'][1]['scores']['originality']=3
    assert not CR.audit(p)['ok']


def test_style_valid_but_not_rights_verified():
    r=CR.style_bible_check(style())
    assert r['ok'] and not r['render_executed'] and not r['rights_checked_against_external_sources']


@pytest.mark.parametrize('issue',[lambda p:p.update(palette=['#111111','no','bad']),
                                 lambda p:p.update(palette=['#111111']),
                                 lambda p:p.update(story_beats=''),
                                 lambda p:p.update(constraints=[]),
                                 lambda p:p.update(assets=[{'source':'web','licence':'unknown','usage_permission':'pending'}]),
                                 lambda p:p.update(assets=[{'source':'web','licence':'','usage_permission':'verified'}])])
def test_style_rejects_incomplete_or_unlicensed(issue):
    p=style();issue(p)
    assert not CR.style_bible_check(p)['ok']


def test_fonts_are_never_bundled():
    assert not list((PKG/'skills/absolute-creativity').rglob('*.ttf'))
    assert not list((PKG/'skills/absolute-creativity').rglob('*.otf'))
    assert not list((PKG/'skills/absolute-creativity').rglob('.font_cache.json'))


def test_json_max_bytes(tmp_path):
    p=tmp_path/'too-big.json';p.write_bytes(b' '* (CR.MAX_JSON_BYTES+1))
    with pytest.raises(ValueError,match='too large'):CR.load_json(p)


def test_no_exec_from_untrusted_packet(tmp_path):
    p=filled();p['shell']='touch sentinel';file=tmp_path/'packet.json';file.write_text(json.dumps(p,ensure_ascii=False))
    with mock.patch('subprocess.run',side_effect=AssertionError('must not execute')):
        assert CR.main(['audit',str(file)])==0
    assert not (tmp_path/'sentinel').exists()


def test_cli_error_is_nonzero(tmp_path):
    f=tmp_path/'empty.json';f.write_text('{}')
    assert CR.main(['audit',str(f)])==2
    assert CR.main(['style-check',str(f)])==2


def test_cli_does_not_overwrite_brief(tmp_path):
    target=tmp_path/'brief.json';target.write_text('do-not-overwrite')
    assert CR.main(['brief','--task','ريل','--out',str(target)])==2
    assert target.read_text()=='do-not-overwrite'


def test_bridge_and_local_cli_registration():
    sys.path.insert(0,str(ROOT))
    from dragon import capabilities
    rows=capabilities.read_registry()
    assert len(rows)>=35
    assert any(r["id"]=="rea-ultra" for r in rows)
    assert any(r['id']=='absolute-creativity' for r in rows)
    args=[sys.executable,str(PKG/'scripts/dragon.py'),'tool','creativity','spin','فكرة','--seed','5','--n','3','--json']
    a=subprocess.run(args,capture_output=True,text=True,timeout=30)
    b=subprocess.run(args,capture_output=True,text=True,timeout=30)
    assert a.returncode==b.returncode==0
    assert json.loads(a.stdout)==json.loads(b.stdout)


def test_font_no_overwrite_even_when_ready(tmp_path):
    path=tmp_path/'existing.png';path.write_bytes(b'keep')
    if not CR.doctor()['arabic_title_render_ready']:pytest.skip('RAQM not available')
    # safe regardless of whether the chosen font is Arabic-capable
    fc=next(iter(Path('/usr/share/fonts').rglob('*.ttf')),None)
    if not fc:pytest.skip('no font in environment')
    a=type('Args',(),dict(cmd='font-title',text='صباح الخير',font=str(fc),out=str(path),size=36,stroke=0,shadow=0,width=100,
                           color='#ffffff',stroke_color='#000000'))()
    with pytest.raises(ValueError,match='already exists'):CR.call_font(a)
    assert path.read_bytes()==b'keep'


def test_portable_cache_location():
    txt=(PKG/'skills/absolute-creativity/scripts/font_lab.py').read_text(encoding='utf-8')
    assert '.cache/black-dragon/font_lab.json' in txt
    assert 'C:\\Users\\cinde' not in txt


def test_font_uses_no_bad_rtl_fallback():
    txt=(PKG/'skills/absolute-creativity/scripts/font_lab.py').read_text()
    assert 'refusing incorrect RTL rendering' in txt


def test_concept_score_boolean_rejected():
    p=filled();p['concepts'][1]['scores']['originality']=True
    assert not CR.audit(p)['ok']


def test_creative_query_routes_to_new_entrypoint_without_execution():
    sys.path.insert(0,str(ROOT))
    from dragon import capabilities
    a=capabilities.plan('عايز ابتكار حبكة سيناريو ريل',mode='smart',limit=4)
    assert not a['execution_performed']
    assert a['selected_tools'][0]['id']=='absolute-creativity'
    tool=next(t for t in capabilities.probe_tools()['tools'] if t['id']=='absolute-creativity')
    assert tool['status']=='discoverable' and tool['entrypoint_found'] and not tool['executed']


def test_actual_local_arabic_transparent_title_when_available(tmp_path):
    from PIL import Image
    if not CR.doctor()['arabic_title_render_ready']:pytest.skip('RAQM missing')
    font=Path('/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf')
    if not font.is_file():pytest.skip('test font unavailable; no bundled fonts')
    out=tmp_path/'out.png'
    a=type('Args',(),dict(cmd='font-title',text='الإبداع المطلق',font=str(font),out=str(out),size=72,stroke=2,shadow=4,width=900,
                           color='#F5C542',stroke_color='#000000'))()
    assert CR.call_font(a)==0
    with Image.open(out) as im:
        assert im.mode=='RGBA' and im.width==900 and im.height>50
        assert im.getextrema()[3][0]==0 and im.getextrema()[3][1]==255
