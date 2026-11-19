"""Release tests for procedural Ultra Mind + measurable independent evidence."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT.parent
sys.path.insert(0,str(ROOT))
from dragon import v103_ultra


def packet():
    return {'task':'Is a full code rewrite warranted?', 'domain':'decision', 'level':'L2',
            'hypotheses':[{'id':'A','approach':'fix monolith','discriminator':'measure bottlenecks'},
                          {'id':'B','approach':'split one module','discriminator':'A/B integration test'}],
            'selected':'A','falsifier':'If measurable failures persist',
            'outside_view':'prior incident counts and comparable teams',
            'checks':[{'kind':'external-reference','reference':'first party project incident records'}]}


@pytest.mark.parametrize('level,stages,branches', [('L0',1,0),('L1',3,2),('L2',7,2),('L3',7,3)])
def test_stage_routing(level,stages,branches):
    p=v103_ultra.plan('فكّر بعمق',level=level)
    assert len(p['stages'])==stages and p['branches_required']==branches
    assert not p['execution_performed'] and not p['agents_called']


@pytest.mark.parametrize('domain',v103_ultra.DOMAINS)
def test_domains_supported(domain):
    assert len(v103_ultra.plan('analyze specific evidence',domain=domain)['task_focus'])==3


def test_empty_task_and_bad_level_rejected():
    with pytest.raises(ValueError):v103_ultra.plan(' ')
    with pytest.raises(ValueError):v103_ultra.plan('x',level='L4')


def test_manual_reference_not_marked_verified(tmp_path):
    r=v103_ultra.audit(packet(),tmp_path)
    assert r['structure_pass'] and r['reasoning_correctness_verified'] is False
    assert r['evidence'][0]['status']=='declared-not-verified'


def test_falsifier_required(tmp_path):
    p=packet();p.pop('falsifier')
    assert not v103_ultra.audit(p,tmp_path)['structure_pass']


def test_competing_hypotheses_and_selected(tmp_path):
    p=packet();p['hypotheses']=p['hypotheses'][:1]
    assert not v103_ultra.audit(p,tmp_path)['structure_pass']
    p=packet();p['hypotheses'][1]['approach']=p['hypotheses'][0]['approach']
    assert any('duplicate' in x for x in v103_ultra.audit(p,tmp_path)['violations'])
    p=packet();p['selected']='C';assert not v103_ultra.audit(p,tmp_path)['structure_pass']


def test_l3_requires_three(tmp_path):
    p=packet();p['level']='L3'
    assert not v103_ultra.audit(p,tmp_path)['structure_pass']


def test_read_only_hash_real_proof(tmp_path):
    data=tmp_path/'output.txt';data.write_text('actual',encoding='utf8')
    p=packet();p['checks']=[{'kind':'file-sha256','file':'output.txt','sha256':hashlib.sha256(data.read_bytes()).hexdigest()}]
    r=v103_ultra.audit(p,tmp_path)
    assert r['structure_pass'] and r['files_with_matching_sha256']==1 and not r['reasoning_correctness_verified']
    assert data.read_text()=='actual'


def test_mismatched_sha_fails(tmp_path):
    (tmp_path/'f').write_text('modified')
    p=packet();p['checks']=[{'kind':'file-sha256','file':'f','sha256':'0'*64}]
    r=v103_ultra.audit(p,tmp_path)
    assert not r['structure_pass'] and r['files_with_matching_sha256']==0


def test_reject_directory_traversal(tmp_path):
    p=packet();p['checks']=[{'kind':'file-sha256','file':'../secret.txt','sha256':'0'*64}]
    assert not v103_ultra.audit(p,tmp_path)['structure_pass']


def _symlink_or_skip(link, target):
    # Windows needs SeCreateSymbolicLinkPrivilege (or Developer Mode) for symlinks; skip rather than error.
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"symlinks unavailable on this machine ({e.__class__.__name__}: {e}); enable Developer Mode to run this check")


def test_reject_symlink_escape(tmp_path):
    outside=tmp_path.parent/'not-inside.txt';outside.write_text('x')
    _symlink_or_skip(tmp_path/'escape', outside)
    p=packet();p['checks']=[{'kind':'file-sha256','file':'escape','sha256':hashlib.sha256(b'x').hexdigest()}]
    assert not v103_ultra.audit(p,tmp_path)['structure_pass']


def test_no_commands_from_packet(tmp_path):
    p=packet();p['checks']=[{'kind':'shell','command':'touch danger'}]
    r=v103_ultra.audit(p,tmp_path)
    assert not r['structure_pass'] and not (tmp_path/'danger').exists()


def test_calibration_perfect_and_baseline():
    a=v103_ultra.calibrate([{'probability':0,'outcome':0},{'probability':1,'outcome':1}])
    assert a['brier_score']==0 and a['constant_base_rate_brier']==0.25
    assert a['n']==2 and sum(x['n'] for x in a['bins'])==2


def test_brier_arithmetic_and_bins():
    a=v103_ultra.calibrate([{'probability':0.25,'outcome':1},{'probability':0.75,'outcome':0}])
    assert a['brier_score']==pytest.approx(0.5625)
    assert a['base_rate']==0.5


@pytest.mark.parametrize('rows', [[{'probability':True,'outcome':1}], [{'probability':float('nan'),'outcome':0}],
                                    [{'probability':1.2,'outcome':0}], [{'probability':0.2,'outcome':True}], []])
def test_calibration_reject_invalid(rows):
    with pytest.raises(ValueError):v103_ultra.calibrate(rows)


def test_original_source_preserved():
    assert (SKILL/'skills/ultra-mind/SKILL.md').is_file()
    assert (SKILL/'skills/ultra-mind/references/creativity.md').is_file()
    assert len(json.loads((SKILL/'skills/ultra-mind/evals/evals.json').read_text())['evals'])==7


def test_cli_plan_audit_calibrate(tmp_path):
    runner=SKILL/'scripts/dragon.py'
    # scripts/dragon.py calls Path.home() at import; on Windows that needs USERPROFILE (not just PATH).
    base_env={k:os.environ[k] for k in ('SYSTEMROOT','USERPROFILE','HOME','HOMEDRIVE','HOMEPATH','TEMP','TMP') if k in os.environ}
    base_env.update({'DRAGON_MODE':'cloud','PATH':os.environ.get('PATH','/usr/bin:/bin')})
    for tail in [ ['v10','ultra','plan','حل عطل','--domain','code','--level','L2'],
                  ['v10','ultra','audit',str(SKILL/'examples/ultra-review-sample.json')],
                  ['v10','ultra','calibrate',str(SKILL/'examples/ultra-calibration-sample.json')]]:
        r=subprocess.run([sys.executable,str(runner),*tail],cwd=SKILL,env=base_env,capture_output=True,text=True,timeout=30)
        assert r.returncode==0, (r.stdout,r.stderr)
        assert 'black-dragon.v10.3' in r.stdout


def test_registered_tool_in_manifest():
    tools=json.loads((SKILL/'app/data/own_tools.json').read_text())['tools']
    assert sum(t['id']=='ultra-mind' for t in tools)==1
