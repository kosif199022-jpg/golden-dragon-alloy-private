#!/usr/bin/env python3
"""Safe(ish) offline Blender Pro integration for Black Dragon 10.5.

Preflight and provenance are intentionally separate from actual Blender execution:
  doctor, ops, validate, plan, verify -> no Blender jobs or network activity
  render                         -> dry-run unless --execute is explicitly passed

This is NOT a sandbox for arbitrary JSON recipes: Blender can execute operators, read
file references and run drivers. Only run reviewed files on an authorized device.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OP_DIR = HERE / 'scripts' / 'bpylib'
PRESETS = HERE / 'examples'
BL_CLI = HERE / 'scripts' / 'bl.py'


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def operation_index():
    """AST-only scan; never imports Blender/python from the source package."""
    found: dict[str, list[str]] = {}
    for p in sorted(OP_DIR.glob('*.py')):
        if p.stem in ('__init__','util'): continue
        parsed = ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p))
        for node in parsed.body:
            value = None
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'OPS' for t in node.targets):
                value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == 'OPS':
                value = node.value
            if isinstance(value, ast.Dict):
                keys = [k.value for k in value.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
                found[p.stem] = sorted(set(keys))
    return found


def all_ops():
    idx=operation_index()
    plain={k for vals in idx.values() for k in vals}
    qualified={f'{mod}.{key}' for mod, vals in idx.items() for key in vals}
    return plain|qualified


def validate_data(data):
    errors=[]
    if not isinstance(data,dict): return ['recipe must be a JSON object']
    if 'scene' in data and not isinstance(data['scene'],dict): errors.append('scene must be an object')
    steps=data.get('steps',[])
    if not isinstance(steps,list):return errors+['steps must be a list']
    if len(steps)>1000:errors.append('steps exceeds the safe preflight limit 1000')
    known=all_ops()
    for i,step in enumerate(steps):
        if not isinstance(step,dict):
            errors.append(f'steps[{i}] must be an object');continue
        name=step.get('op')
        if not isinstance(name,str) or name not in known:
            errors.append(f'steps[{i}] unknown operation {name!r}')
    renders=data.get('render')
    if renders is not None:
        rs=renders if isinstance(renders,list) else [renders]
        for i,r in enumerate(rs):
            if not isinstance(r,dict):errors.append(f'render[{i}] must be an object');continue
            out=r.get('out',r.get('filepath'))
            if out is not None:
                if not isinstance(out,str) or not out.strip():
                    errors.append(f'render[{i}] filename invalid')
                elif (Path(out).is_absolute() or re.match(r'^[A-Za-z]:', out) or '..' in out.replace('\\', '/').split('/')):
                    errors.append(f'render[{i}] absolute/traversal output path requires manual review')
        if len(rs)>100:errors.append('render list too long')
    return errors


def validate_file(path):
    p=Path(path)
    if not p.is_file():return {'ok':False,'path':str(p),'errors':['file not found']}
    try:
        data=json.loads(p.read_text(encoding='utf-8-sig'))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:
        return {'ok':False,'path':str(p),'errors':[f'invalid JSON: {exc}']}
    errors=validate_data(data)
    return {'ok':not errors,'path':str(p.resolve()),'sha256':digest(p),'steps':len(data.get('steps',[])) if isinstance(data.get('steps',[]),list) else None,
            'errors':errors,'execution_performed':False,'note':'Static preflight only; Blender/bpy behavior not executed.'}


def doctor():
    idx=operation_index()
    blender=os.environ.get('BLENDER')
    exe=blender if blender and Path(blender).is_file() else shutil.which('blender')
    return {'ok':True,'engine':'Blender Pro source', 'blender_found':bool(exe),'blender_path':str(exe) if exe else None,
            'ffmpeg_found':bool(shutil.which('ffmpeg')),'ffprobe_found':bool(shutil.which('ffprobe')),
            'arabic_reshaper':importlib.util.find_spec('arabic_reshaper') is not None,
            'python_bidi':importlib.util.find_spec('bidi') is not None,
            'modules':len(idx),'source_ops':sum(map(len,idx.values())),
            'recipes':len(list(PRESETS.glob('*.json'))),
            'runtime_execution_performed':False,
            'status':'ready_for_runtime_testing' if exe else 'missing_blender',
            'warning':'Static source inspection is not a render test; source specifies Blender 5.x.'}


def verify(path):
    p=Path(path)
    if not p.is_file() or p.stat().st_size==0:
        return {'ok':False,'error':'file missing or empty','file':str(p)}
    r={'ok':True,'file':str(p.resolve()),'bytes':p.stat().st_size,'sha256':digest(p),'media_probed':False}
    if p.suffix.lower() in ('.mp4','.mov','.mkv','.webm','.mp3','.wav'):
        probe=shutil.which('ffprobe')
        if not probe:
            r.update(ok=False,error='ffprobe not installed');return r
        proc=subprocess.run([probe,'-v','error','-show_streams','-show_format','-of','json',str(p)],text=True,capture_output=True,timeout=30)
        if proc.returncode:
            r.update(ok=False,error='media ffprobe failed',stderr=proc.stderr[-400:]);return r
        v=json.loads(proc.stdout)
        if not v.get('streams'):r.update(ok=False,error='no decodable media streams');return r
        r.update(media_probed=True,streams=[{'codec':s.get('codec_name'),'type':s.get('codec_type'),
             'width':s.get('width'),'height':s.get('height'),'r_frame_rate':s.get('r_frame_rate')} for s in v['streams']],
             duration=v.get('format',{}).get('duration'))
    elif p.suffix.lower()=='.json':
        try:json.loads(p.read_text(encoding='utf-8-sig'))
        except (ValueError,UnicodeDecodeError):r.update(ok=False,error='JSON parse failed')
    return r


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sub=ap.add_subparsers(dest='cmd',required=True)
    sub.add_parser('doctor')
    o=sub.add_parser('ops');o.add_argument('--module')
    v=sub.add_parser('validate');v.add_argument('recipe')
    p=sub.add_parser('plan');p.add_argument('preset',help='bundled example name without extension');p.add_argument('--out')
    r=sub.add_parser('render');r.add_argument('recipe');r.add_argument('--out',required=True);r.add_argument('--preview',action='store_true');r.add_argument('--execute',action='store_true');r.add_argument('--timeout',type=int,default=300)
    q=sub.add_parser('verify');q.add_argument('file')
    a=ap.parse_args(argv)
    if a.cmd=='doctor':result=doctor()
    elif a.cmd=='ops':
        idx=operation_index();found={a.module:idx[a.module]} if a.module in idx else idx if not a.module else {}
        result={'ok':bool(found),'modules':found,'total':sum(map(len,found.values())),'execution_performed':False}
        if a.module and not found:result['error']='unknown operation module'
    elif a.cmd=='validate':result=validate_file(a.recipe)
    elif a.cmd=='plan':
        if not a.preset.replace('-','').replace('_','').isalnum():result={'ok':False,'error':'invalid preset name'}
        else:
            src=PRESETS/f'{a.preset}.json'
            result=validate_file(src)
            if result['ok']:
                result['example']=a.preset
                result['message']='Planning/sample only; no Blender call made.'
                if a.out:
                    dst=Path(a.out)
                    if dst.exists():result={'ok':False,'error':'refusing to overwrite existing recipe'}
                    else:
                        dst.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(src,dst)
                        result['written_copy']=str(dst.resolve())
    elif a.cmd=='render':
        pre=validate_file(a.recipe)
        if not pre['ok']:result=pre
        else:
            cmd=[sys.executable,str(BL_CLI),'run',str(Path(a.recipe).resolve()),'--out',str(Path(a.out).resolve()),'--timeout',str(a.timeout)]
            if a.preview:cmd.append('--preview')
            if not a.execute:
                result={'ok':True,'dry_run':True,'execution_performed':False,'recipe_sha256':pre['sha256'],
                        'run_command':cmd,'warning':'Add --execute only after the user explicitly approves Blender execution and inputs are reviewed.'}
            elif not doctor()['blender_found']:
                result={'ok':False,'execution_performed':False,'error':'Blender not installed; cannot render.'}
            else:
                dest=Path(a.out)
                if dest.exists() and any(dest.iterdir()):
                    result={'ok':False,'execution_performed':False,'error':'output directory not empty; refusing to overwrite existing files'}
                else:
                    dest.mkdir(parents=True,exist_ok=True)
                    proc=subprocess.run(cmd,text=True,capture_output=True,timeout=a.timeout+30)
                    lines=proc.stdout.splitlines()
                    report=None
                    for line in reversed(lines):
                        try:
                            payload=json.loads(line)
                            if isinstance(payload,dict) and 'ok' in payload:
                                report=payload;break
                        except json.JSONDecodeError:continue
                    result={'ok':proc.returncode==0 and bool(report and report.get('ok')),
                            'execution_performed':True,'exit_code':proc.returncode,'recipe_sha256':pre['sha256'],
                            'blender_result':report,'stderr_tail':proc.stderr[-600:]}
    else: result=verify(a.file)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result.get('ok') else 1

if __name__=='__main__':
    raise SystemExit(main())
