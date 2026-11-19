"""Black Dragon v10.2: Media Hunter integration regression, no network access."""
from __future__ import annotations
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
MH=ROOT/'tools'/'media_hunter'/'mh.py'
SPEC=importlib.util.spec_from_file_location('dragon_media_hunter_v102',MH)
mh=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mh)


def test_registry_is_real_and_declares_limitations():
    rows=mh.source_rows()
    assert 20 <= len(rows) < 615
    assert len({r['id'] for r in rows})==len(rows)
    assert next(x for x in rows if x['id']=='polyhaven')['adapter'] is None
    assert next(x for x in rows if x['id']=='nasa')['adapter']=='video'
    assert not any(x['adapter'] for x in rows if x['id']=='giphy')


def test_offline_sites_are_not_live_results(monkeypatch):
    monkeypatch.delenv('PEXELS_API_KEY',raising=False)
    rs=mh.shortlist('desert sunset','video',limit=35)
    assert rs and all(x['status']!='searched-successfully' for x in rs)
    assert any(x['status']=='needs-key' for x in rs)
    assert all('http' in x['search_url'] for x in rs)


def test_source_query_escaping_and_giphy_slug():
    r=next(x for x in mh.source_rows() if x['id']=='giphy')
    assert mh.query_url(r,'sunset & ocean').endswith('sunset-%26-ocean')
    r=next(x for x in mh.source_rows() if x['id']=='nasa')
    assert 'ocean' in mh.query_url(r,'ocean')


def test_offline_links_escape_html_and_disclose_licensing(tmp_path):
    r=mh.shortlist('cool <script>alert(1)</script>','art',limit=4)
    p=mh.write_links(r,tmp_path/'links.html','cool <script>alert(1)</script>')
    t=p.read_text(encoding='utf-8')
    assert '<script>' not in t and '&lt;script&gt;' in t
    assert 'لا تعني أن الملفات مرخّصة' in t and 'noopener noreferrer' in t


def test_arabic_fallback_labelled_not_full_translation():
    assert 'camel desert sunset'==mh.english_query('جمل صحراء غروب')
    assert 'اختراع' in mh.english_query('اختراع غير معروف')


def fake_clip(name,kind='video',**flags):
    lic={'name':'CC BY 4.0','url':'https://creativecommons.org/licenses/by/4.0/',
         'verified':True,'commercial':True,'derivatives':True}
    lic.update(flags)
    return {'id':f'nasa:{name}','source':'nasa','title':name,'page_url':f'https://images.nasa.gov/details/{name}',
            'file_url':f'https://images-assets.nasa.gov/{name}.mp4','width':1080,'height':1920,
            'duration':6.0,'licence':lic,'author':'NASA','attribution':f'NASA - {name}'}


def test_hunt_with_mocked_provider_produces_truthful_results(tmp_path,monkeypatch):
    monkeypatch.setattr(mh,'available_sources',lambda typ,req=None:[('video','nasa'),('photo','openverse')])
    def stub(kind,sid,query,count,orientation,commercial):
        if kind=='video':return {'kind':'video','source':'nasa','results':[fake_clip('a')],
                                 'status':{'status':'ok'},'warnings':[]}
        return {'kind':'photo','source':'openverse','results':[],
                'status':{'status':'error','detail':'network failure'},'warnings':[]}
    monkeypatch.setattr(mh,'_source_call',stub)
    report=mh.hunt('جمل صحراء غروب',typ='any',orientation='portrait',out=tmp_path)
    assert report['actual_results']==1
    assert report['results'][0]['media_url'].endswith('/a.mp4')
    assert report['searched_sources']['photo:openverse']['status']=='error'
    assert report['claims']['original_615_catalog_included'] is False
    assert (tmp_path/'last_hunt.json').is_file()
    assert (tmp_path/'last_video.json').is_file()
    assert mh.selected(tmp_path/'last_hunt.json',[1])[0]['source']=='nasa'
    with pytest.raises(ValueError):mh.selected(tmp_path/'last_hunt.json',[2])


def test_min_width_excludes_unknown_and_too_small(tmp_path,monkeypatch):
    monkeypatch.setattr(mh,'available_sources',lambda typ,req=None:[('video','nasa')])
    def stub(*a):
        r=fake_clip('a');r['width']=1080
        r2=fake_clip('b');r2['width']=None
        return {'kind':'video','source':'nasa','results':[r,r2], 'status':{'status':'ok'},'warnings':[]}
    monkeypatch.setattr(mh,'_source_call',stub)
    assert mh.hunt('dunes','video',min_width=3840,out=tmp_path)['actual_results']==0


def test_get_rejects_unknown_rights_without_network(tmp_path,monkeypatch):
    original=fake_clip('b',verified=False,commercial=None)
    r=mh.normalize_record(original,'video');r['n']=1
    (tmp_path/'last_video.json').write_text(json.dumps({'results':[original]}))
    def fail(*_args,**_kw):raise AssertionError('must not invoke network')
    monkeypatch.setattr(mh.FF,'main',fail)
    out=mh.get([r],tmp_path/'downloads',tmp_path/'last_hunt.json')
    assert out[0]['status']=='blocked-rights'
    assert not (tmp_path/'downloads').exists()


def test_get_uses_selected_native_id_and_dry_run(tmp_path,monkeypatch):
    orig=fake_clip('c')
    r=mh.normalize_record(orig,'video');r['n']=1
    (tmp_path/'last_video.json').write_text(json.dumps({'results':[orig]}))
    calls=[]
    monkeypatch.setattr(mh.FF,'main',lambda args:calls.append(args) or 0)
    out=mh.get([r],tmp_path/'dl',tmp_path/'last_hunt.json',dry_run=True,commercial=True)
    assert out[0]['status']=='ok' and out[0]['dry_run'] is True
    assert '--dry-run' in calls[0] and '--commercial' in calls[0]
    assert 'nasa:c' in calls[0]
    r['media_url']='https://example.net/changed'
    assert mh.get([r],tmp_path/'dl',tmp_path/'last_hunt.json')[0]['status']=='results-mismatch'
    assert len(calls)==1


def test_env_key_presence_not_value(tmp_path,monkeypatch):
    monkeypatch.setenv('PEXELS_API_KEY','super-secret-test-token')
    call=subprocess.run([sys.executable,str(MH),'keys'],capture_output=True,text=True,cwd=tmp_path,timeout=20)
    assert call.returncode==0,call.stderr
    assert 'super-secret-test-token' not in call.stdout
    assert json.loads(call.stdout)['keys']['PEXELS_API_KEY']


def test_cli_offline_integration(tmp_path):
    launch=ROOT/'scripts'/'dragon.py'
    cmds=[['tool','hunter','--help'],['tool','hunter','sites','sea','--type','video'],
          ['tool','hunter','links','moon','--type','hdri','--out',str(tmp_path/'links.html')],
          ['tool','hunter','build','--out',str(tmp_path/'sources.json')]]
    for args in cmds:
        p=subprocess.run([sys.executable,str(launch),*args],capture_output=True,text=True,cwd=tmp_path,timeout=30)
        assert p.returncode==0,(args,p.stderr,p.stdout)
    assert (tmp_path/'sources.json').is_file() and (tmp_path/'links.html').is_file()
    assert json.loads((tmp_path/'sources.json').read_text())['original_615_catalog'] is False
