"""Expert Council bridge: no fake expert votes, no arbitrary commands, privacy by default."""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT.parent
sys.path.insert(0,str(ROOT))
from dragon import v104_council as co


def sample(size=5):
    p=co.plan('Evaluate editing at exact 00:12',domain='editing',size=size)
    seats=[]
    for i,seat in enumerate(p['seats']):
        seats.append({'seat_id':seat['id'],'lens':seat['lens'], 'position':f'position {i}',
                      'observations':[{'claim':f'distinct finding {i}','locator':f'00:{12+i:02d}',
                                       'action':f'specific corrective action {i}'}], 'confidence':0.5})
    return {'task':p['task'],'domain':'editing','size':size,'round1':seats,
            'debates':[{'topic':'rhythm vs clarity','steelman_a':'sound intention',
                        'steelman_b':'faster capture','discriminator':'measured A/B render'}],
            'red_team':{'premortem':'viewers may leave after 2s'},
            'verdict':{'decision':'favor clarity','reasoning':'readability before speed',
                       'strongest_dissent':'we may sacrifice rhythm',
                       'actions':['make 10-second test and compare retention']},'evidence':[]}

@pytest.mark.parametrize('size',co.SIZES)
@pytest.mark.parametrize('domain',co.DOMAINS)
def test_domain_size_scaffolds(size,domain):
    p=co.plan('test creative work',domain=domain,size=size)
    assert len(p['seats']) == size
    assert len({s['lens'] for s in p['seats']})==size
    assert not p['agents_called'] and not p['actual_expert_participation']


def test_custom_domain_uses_generic_lenses():
    p=co.plan('راجع عقداً',domain='legal-contracts',size=5)
    assert p['domain']=='legal-contracts' and len(p['seats'])==5


def test_scaffolding_invalid_inputs():
    for task,domain,size in [('', 'editing',5),('x',' ',5),('x','editing',4)]:
        with pytest.raises(ValueError):co.plan(task,domain,size)

@pytest.mark.parametrize('size',co.SIZES)
def test_valid_packet_structure_not_claimed_truth(size,tmp_path):
    result=co.audit(sample(size),tmp_path)
    assert result['structure_pass'] and result['factual_correctness_verified'] is False
    assert result['agent_calls_verified'] is False


def test_missing_dissent_fails(tmp_path):
    p=sample();del p['verdict']['strongest_dissent']
    assert not co.audit(p,tmp_path)['structure_pass']


def test_missing_debate_fails_full_but_not_mini(tmp_path):
    p=sample();p['debates']=[]
    assert not co.audit(p,tmp_path)['structure_pass']
    p=sample(3);p['debates']=[]
    assert co.audit(p,tmp_path)['structure_pass']


def test_duplicate_lenses_fails(tmp_path):
    p=sample();p['round1'][1]['lens']=p['round1'][0]['lens']
    assert any('duplicate seat lenses' in x for x in co.audit(p,tmp_path)['violations'])


def test_duplicate_findings_fails(tmp_path):
    p=sample();p['round1'][1]['observations'][0]['claim']=p['round1'][0]['observations'][0]['claim']
    assert any('duplicate findings' in x for x in co.audit(p,tmp_path)['violations'])


def test_empty_precise_locator_fails(tmp_path):
    p=sample();p['round1'][0]['observations'][0]['locator']=''
    assert not co.audit(p,tmp_path)['structure_pass']


def test_no_red_team_fails(tmp_path):
    p=sample();p['round1'][3]['lens']='separate-view'
    assert any('red-team seat' in x for x in co.audit(p,tmp_path)['violations'])


def test_no_user_seat_fails(tmp_path):
    p=sample();p['round1'][2]['lens']='studio-view'
    assert any('audience' in x for x in co.audit(p,tmp_path)['violations'])


def test_no_practical_seat_fails(tmp_path):
    p=sample();p['round1'][4]['lens']='independent-outlier'
    assert any('feasibility seat' in x for x in co.audit(p,tmp_path)['violations'])


def test_verified_hash_only_means_integrity(tmp_path):
    f=tmp_path/'clip.txt';f.write_text('not a real film',encoding='utf-8')
    p=sample();p['evidence']=[{'kind':'file-sha256','file':'clip.txt','sha256':hashlib.sha256(f.read_bytes()).hexdigest()}]
    r=co.audit(p,tmp_path)
    assert r['structure_pass'] and r['evidence'][0]['integrity_match'] is True
    assert r['factual_correctness_verified'] is False


def test_hash_mismatch_fails(tmp_path):
    (tmp_path/'a.txt').write_text('tampered')
    p=sample();p['evidence']=[{'kind':'file-sha256','file':'a.txt','sha256':'0'*64}]
    assert any('digest mismatch' in x for x in co.audit(p,tmp_path)['violations'])


def test_path_traversal_rejected(tmp_path):
    p=sample();p['evidence']=[{'kind':'file-sha256','file':'../hidden','sha256':'0'*64}]
    assert not co.audit(p,tmp_path)['structure_pass']


def _symlink_or_skip(link, target):
    # Windows needs SeCreateSymbolicLinkPrivilege (or Developer Mode) for symlinks; skip rather than error.
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"symlinks unavailable on this machine ({e.__class__.__name__}: {e}); enable Developer Mode to run this check")


def test_symlink_escape_rejected(tmp_path):
    outside=tmp_path.parent/'outside';outside.write_text('private')
    _symlink_or_skip(tmp_path/'jump', outside)
    p=sample();p['evidence']=[{'kind':'file-sha256','file':'jump','sha256':hashlib.sha256(b'private').hexdigest()}]
    assert not co.audit(p,tmp_path)['structure_pass']


def test_reject_shell_from_packet(tmp_path):
    p=sample();p['evidence']=[{'kind':'command','shell':'touch pwned'}]
    assert not co.audit(p,tmp_path)['structure_pass']
    assert not (tmp_path/'pwned').exists()


def test_declared_reference_is_not_fact_checked(tmp_path):
    p=sample();p['evidence']=[{'kind':'declared-reference','citation':'timestamp 00:12 in source'}]
    r=co.audit(p,tmp_path)
    assert r['structure_pass'] and r['evidence'][0]['status']=='declared-unverified' and r['warnings']


def test_lessons_add_search_reinforce(tmp_path):
    store=tmp_path/'private'/'lessons.jsonl'
    assert co.lessons(store,'stats')['total']==0
    added=co.add_lesson(store,'editing','too much music','voice lost','duck music for speech',source='user')
    assert added['status']=='added' and added['lesson']['id']==1
    hit=co.add_lesson(store,'editing','again','lost','duck music for speech',source='user')
    assert hit['status']=='reinforced-existing' and hit['lesson']['hits']==1
    assert co.lessons(store,'search',query='voice music',domain='editing')['results'][0]['id']==1
    assert co.lessons(store,'stats')['total']==1
    assert 'voice' in co.lessons(store,'list')['results'][0]['mistake']


def test_lessons_reject_invalid_and_corrupt_file(tmp_path):
    store=tmp_path/'l.jsonl'
    with pytest.raises(ValueError):co.add_lesson(store,' ','x','x','x')
    assert not store.exists()
    store.write_text('broken json\n')
    with pytest.raises(ValueError,match='corrupt ledger'):co.read_lessons(store)


def test_lessons_no_network_or_external_exec(tmp_path):
    store=tmp_path/'l.jsonl'
    co.add_lesson(store,'software','install','missing dependency','require consent before installation')
    assert not any(x.name.endswith('.sh') for x in tmp_path.rglob('*'))
    assert co.read_lessons(store)[0]['source']=='user'


def call(*args):
    return subprocess.run([sys.executable,'-m','dragon','v10','council',*args],cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT)},capture_output=True,text=True,timeout=12)


def test_cli_plan_and_audit(tmp_path):
    r=call('plan','review a clip','--domain','editing','--size','5')
    assert r.returncode==0,r.stderr
    assert len(json.loads(r.stdout)['seats'])==5
    file=tmp_path/'p.json';file.write_text(json.dumps(sample()))
    audit=call('audit',str(file))
    assert audit.returncode==0,audit.stderr
    assert json.loads(audit.stdout)['structure_pass']
    p=sample();p.pop('verdict')
    file.write_text(json.dumps(p))
    assert call('audit',str(file)).returncode==5


def test_cli_private_ledger(tmp_path):
    store=tmp_path/'lessons.jsonl'
    r=call('lessons','--store',str(store),'add','--domain','editing','--trigger','noise','--mistake','voice lost','--lesson','duck music')
    assert r.returncode==0,r.stderr
    assert store.exists()
    r=call('lessons','--store',str(store),'search','voice','--domain','editing')
    assert r.returncode==0,r.stderr
    assert json.loads(r.stdout)['total_matched']==1


def test_skill_source_preserved():
    for path in ('SKILL.md','references/council-protocol.md','references/personas.md',
                 'references/domains/editing.md','references/domains/directing.md',
                 'references/domains/cinematography.md','references/domains/literary-criticism.md',
                 'references/learning-loop.md','scripts/lessons.py','evals/evals.json'):
        assert (PKG/'skills'/'expert-council'/path).is_file()
