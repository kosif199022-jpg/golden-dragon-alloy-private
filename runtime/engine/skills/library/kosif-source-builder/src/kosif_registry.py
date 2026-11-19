"""Repository catalog and controlled clone operations; no automatic code execution."""
import json, os, shutil, subprocess, sys
from pathlib import Path

def repositories(root):
    data=json.loads((root/'manifest'/'repositories.json').read_text(encoding='utf-8'))
    return data['repos']

def selected(root,group):
    if group=='all': return repositories(root)
    if group=='own': return [r for r in repositories(root) if r['group'].startswith('own-')]
    return [r for r in repositories(root) if r['group']==group]

def catalog(root,group='all',json_mode=False):
    records=selected(root,group)
    if not records: raise ValueError('No repositories in group: '+group)
    if json_mode:
        print(json.dumps(records,ensure_ascii=False,indent=2)); return
    print(f'KOSIF REPOSITORY CATALOG — {len(records)} items — {group}')
    for r in records: print(f"[{r['group']:<13}] {r['name']:<23} {r['url']}")
    print('To download source on this machine: python kosif.py install --group '+group+' --execute')

def doctor(json_mode=False):
    tools=['python','git','gh','ffmpeg','ffprobe','node','npm','blender','nvidia-smi']
    result={x:(shutil.which(x) or 'NOT FOUND') for x in tools}
    result['python_version']=sys.version.split()[0]
    if json_mode: print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        print('KOSIF SYSTEM CHECK')
        for k,v in result.items(): print(f'  {k:17} {v}')
        if not shutil.which('ffmpeg'):print('  NOTE: FFmpeg is required for video rendering.')
        if not shutil.which('git'):print('  NOTE: Git is required to clone repositories.')

def install(root,group,dest,execute):
    items=selected(root,group)
    if not items: raise ValueError('Unknown/empty group: '+group)
    print(f'KOSIF SOURCE COLLECTION: group={group} count={len(items)} destination={dest}')
    if not execute:
        for r in items: print(' PLAN ',r['name'],r['clone'])
        print('This was PLAN ONLY. Add --execute to clone to your own machine.'); return
    if not shutil.which('git'): raise RuntimeError('Git not found. Install Git first.')
    dest.mkdir(parents=True,exist_ok=True)
    results=[]
    for r in items:
        target=dest/r['name']
        if target.exists():
            results.append(dict(repo=r['name'],status='skipped_existing',url=r['url']))
            print(' SKIP ',r['name'],'already exists'); continue
        print(' CLONE',r['name'],flush=True)
        cmd=['git','-c','core.longpaths=true','clone','--depth','1','--single-branch',r['clone'],str(target)]
        env=os.environ.copy(); env['GIT_LFS_SKIP_SMUDGE']='1'; env['GIT_TERMINAL_PROMPT']='0'
        try:
            cp=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,timeout=1200)
            if cp.returncode:
                print(' FAIL ',r['name'],'— See install-report.json. Authenticate privately using gh auth login if needed.')
                results.append(dict(repo=r['name'],status='failed',url=r['url'],error='Clone failed; check git credentials / network / repository availability'))
            else:
                commit=subprocess.run(['git','-C',str(target),'rev-parse','HEAD'],capture_output=True,text=True)
                results.append(dict(repo=r['name'],status='cloned',commit=commit.stdout.strip(),url=r['url']))
        except subprocess.TimeoutExpired:
            results.append(dict(repo=r['name'],status='timeout',url=r['url']))
            print(' TIMEOUT',r['name'])
    report=dest/'kosif-install-report.json'
    report.write_text(json.dumps({'group':group,'result':results},indent=2),encoding='utf-8')
    print('Results recorded:',report)
    print('Source cloning never installs dependencies, executables or model weights automatically.')
