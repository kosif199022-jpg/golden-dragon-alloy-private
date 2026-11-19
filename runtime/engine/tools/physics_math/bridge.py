#!/usr/bin/env python3
"""Black Dragon v10.9: guarded local physics/math CLI, upstream source retained.

Examples:
    python scripts/dragon.py tool physics doctor
    python scripts/dragon.py tool physics calc "sqrt(2*20/g)"
    python scripts/dragon.py tool physics fall --height 20 --fps 30 --keys
    python scripts/dragon.py tool physics beats --bpm 120 --duration 6 --out out/cuts.csv --receipt out/cuts.receipt.json
    python scripts/dragon.py tool physics verify out/cuts.receipt.json

The math script uses Python stdlib only. No renders, external APIs or models run.
"""
from __future__ import annotations

import hashlib
import importlib.util
from functools import lru_cache
import contextlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'skills' / 'physics-math' / 'scripts' / 'phys.py'
ORIGINAL = ROOT / 'skills' / 'physics-math' / 'upstream' / 'phys-original.py'
SCHEMA = 'black-dragon.physics-math.v1'
COMMANDS = {'calc','convert','shape','material','motion','fall','projectile','bounce','spring','ease',
            'camera','tc','speed','beats','frame','audio','track','scale'}
MAX_OUTPUT_BYTES = 6_000_000
MAX_FRAMES = 24000
MAX_SECONDS = 600


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def json_print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False))


def file_out(name):
    path = Path(name).absolute()
    if path.exists() or path.is_symlink():
        raise ValueError('refusing to overwrite existing file')
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError('output parent must exist and not be a symlink')
    if path.suffix.lower() not in ('.json', '.csv'):
        raise ValueError('output must end in .json or .csv')
    return path


def _opt(args, name):
    # Also support argparse --flag=value syntax.
    for i, val in enumerate(args):
        if val == name:
            if i+1 >= len(args):
                raise ValueError(f'{name} requires a value')
            return args[i+1]
        if val.startswith(name+'='):
            return val.split('=',1)[1]
    return None


def validate_args(args):
    if not args or args[0] not in COMMANDS:
        raise ValueError('expected a physics command: '+', '.join(sorted(COMMANDS)))
    if sum(len(x) for x in args)>8000 or len(args)>120:
        raise ValueError('arguments too large')
    numeric_limits = {'--fps':(0,240),'--duration':(0,MAX_SECONDS),'--seconds':(0,MAX_SECONDS),
                      '--time':(0,MAX_SECONDS),'--height':(0,1e5),'--count':(0,1000),
                      '--frames':(0,MAX_FRAMES),'--g':(0,1000),'--drag':(0,500),
                      '--bpm':(0,3000),'--every':(0,200),'--per-bar':(0,128),
                      '--restitution':(0,1),'--mass':(0,1e8),'--density':(0,1e8),
                      '--stiffness':(0,1e8),'--damping':(0,1e8),'--focal':(0,10000),
                      '--focal2':(0,10000),'--distance':(-1e5,1e5),'--fill':(0,1),
                      '--fstop':(0,1000),'--coc':(0,100),'--angle':(-360,360),
                      '--px-per-m':(0,1e9),'--ref-px':(0,1e9),'--ref-m':(0,1e9),
                      '--model-scale':(0,1e6),'--timeline-fps':(0,240),'--shot-fps':(0,2000),
                      '--target':(0,MAX_SECONDS),'--factor':(0,1000),'--freq':(0,1e10),
                      '--to-fps':(0,240),'--speed':(-10000,10000),'--object':(0,1e5),
                      '--r':(0,1e5),'--r2':(0,1e5),'--a':(0,1e5),'--b':(0,1e5),
                      '--c':(0,1e5),'--h':(0,1e5),'--sensor-w':(0,1000),'--sensor-h':(0,1000)}
    strictly_positive={'--fps','--height','--g','--drag','--bpm','--every','--per-bar','--mass',
                       '--density','--stiffness','--focal','--focal2','--fstop','--coc',
                       '--px-per-m','--ref-px','--ref-m','--model-scale','--timeline-fps','--shot-fps',
                       '--target','--factor','--freq','--to-fps','--object','--sensor-w','--sensor-h'}
    for name,(low,high) in numeric_limits.items():
        raw=_opt(args,name)
        if raw is None:continue
        try:v=float(raw)
        except ValueError:raise ValueError(f'{name} must be numeric')
        if not math.isfinite(v) or not low<=v<=high or (name in strictly_positive and v<=0):
            raise ValueError(f'{name} outside safe range')
    fps = float(_opt(args,'--fps') or (24 if args[0]=='camera' else 30))
    seconds = next((float(s) for k in ('--seconds','--duration','--time') if (s:=_opt(args,k)) is not None),0)
    if seconds*fps > MAX_FRAMES:
        raise ValueError('excessive frame count')
    if args[0]=='camera' and _opt(args,'--fill') is not None and float(_opt(args,'--fill')) <= 0:
        raise ValueError('camera fill must be positive')
    if args[0] in ('motion','projectile') and _opt(args,'--speed') is not None and float(_opt(args,'--speed'))<=0:
        raise ValueError('speed must be positive')
    if args[0]=='fall':
        h=_opt(args,'--height');g=float(_opt(args,'--g') or 9.80665)
        if h is not None and math.sqrt(2*float(h)/g)*fps > MAX_FRAMES:
            raise ValueError('fall would exceed frame limit')
        drag=_opt(args,'--drag')
        if drag and h and float(h)*g/float(drag)**2 > 600:
            raise ValueError('drag calculation would overflow')
    if args[0]=='projectile':
        v=float(_opt(args,'--speed') or 0)
        if v > 10000 or v*2/max(float(_opt(args,'--g') or 9.80665),1e-7)*fps > MAX_FRAMES:
            raise ValueError('projectile would exceed frame limit')
    if args[0]=='spring' and seconds*fps*50>1_200_000:
        raise ValueError('spring would use too many integration steps')
    if args[0]=='beats':
        bpm=float(_opt(args,'--bpm') or 0); every=float(_opt(args,'--every') or 1)
        duration=float(_opt(args,'--duration') or 30)
        if bpm and duration*bpm/(60*every)>MAX_FRAMES:raise ValueError('too many beats')
    for name in ('--src','--dst'):
        val=_opt(args,name)
        if val and args[0]=='frame':
            import re
            if not re.fullmatch(r'[0-9]{1,5}x[0-9]{1,5}',val,flags=re.I) or any(not 1<=int(v)<=16384 for v in val.lower().split('x')):
                raise ValueError('invalid dimensions')
    path=_opt(args,'--out')
    if path:
        file_out(path)
    return path


@lru_cache(maxsize=1)
def _load_source():
    # The local reviewed/patched stdlib module is imported from an exact path;
    # it has no network, install, external process or dynamic import functions.
    spec=importlib.util.spec_from_file_location('black_dragon_v109_phys',SOURCE)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_source(args):
    src=_load_source()
    values=[]
    old_argv=sys.argv
    old_out=src.out
    sys.argv=[str(SOURCE),*args]
    src.out=lambda obj: values.append(obj)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                src.main()
            except SystemExit as exc:
                raise ValueError(f'physics parser/calculator rejected input (exit {exc.code})') from exc
    finally:
        sys.argv=old_argv
        src.out=old_out
    if len(values)!=1 or not isinstance(values[0],dict):
        raise ValueError('calculator returned an unexpected result')
    result=values[0]
    # Reject nonfinite numeric output, do not convert it into misleading values.
    def check(value):
        if type(value) is float and (not math.isfinite(value)):
            return 'inf' if value>0 else '-inf'
        if isinstance(value,dict):return {k:check(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [check(v) for v in value]
        return value
    result=check(result)
    if len(json.dumps(result,ensure_ascii=False))>MAX_OUTPUT_BYTES:
        raise ValueError('physics engine generated excessive output')
    return result


def doctor():
    present=SOURCE.is_file() and ORIGINAL.is_file()
    checks=[]
    if present:
        for params,expected in ((['calc','2+2'],4),(['convert','36','km/h','m/s'],10)):
            try:
                result=run_source(params)
                value=result.get('result')
                checks.append({'command':params[0], 'passed': math.isclose(value,expected,rel_tol=1e-8)})
            except Exception as e:checks.append({'command':params[0],'passed':False,'reason':str(e)})
    return {'schema':SCHEMA,'source_skill_present':(ROOT/'skills/physics-math/SKILL.md').is_file(),
            'math_script_present':SOURCE.is_file(),'upstream_preserved':ORIGINAL.is_file(),
            'stdlib_only':True,'commands':len(COMMANDS),'smoke_checks':checks,
            'ready':present and all(x['passed'] for x in checks),
            'executed_render':False,'network_or_paid_service':False,
            'notes':'Computes idealized formulas, not measurement or physically validated footage.'}


def verify(receipt_path):
    rpath=Path(receipt_path)
    if not rpath.is_file() or rpath.is_symlink() or rpath.stat().st_size>1_000_000:
        raise ValueError('missing or unsafe receipt')
    r=json.loads(rpath.read_text(encoding='utf-8'))
    if r.get('schema')!=SCHEMA or r.get('kind')!='numeric-computation':
        raise ValueError('invalid receipt type')
    errors=[]
    result=r.get('result')
    if not isinstance(result,dict):errors.append('invalid result')
    else:
        checksum=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if checksum!=r.get('result_sha256'):errors.append('stored result changed')
    if r.get('source_sha256')!=sha(SOURCE):errors.append('calculator source changed')
    output_file=r.get('output_file')
    if output_file:
        p=Path(output_file)
        if not p.is_file() or p.is_symlink() or sha(p)!=r.get('output_sha256'):
            errors.append('keyframes file changed or missing')
    return {'ok':not errors,'errors':errors,'checked':'local SHA-256 only',
            'external_physical_accuracy_verified':False}


def main(argv):
    if not argv or argv[0] in ('-h','--help'):
        print(__doc__);return 0
    try:
        if argv[0]=='doctor':
            obj=doctor();json_print(obj);return 0 if obj['ready'] else 4
        if argv[0]=='verify':
            if len(argv)!=2:raise ValueError('verify requires a receipt JSON path')
            obj=verify(argv[1]);json_print(obj);return 0 if obj['ok'] else 5
        receipt_arg=_opt(argv,'--receipt')
        args=argv[:]
        if receipt_arg is not None:
            if '--receipt' in args:
                i=args.index('--receipt');del args[i:i+2]
            else:
                args=[x for x in args if not x.startswith('--receipt=')]
        filename=validate_args(args)
        receipt_path=file_out(receipt_arg) if receipt_arg else None
        result=run_source(args)
        result['black_dragon']={'schema':SCHEMA,'locally_computed':True,
                                'generated_media':False,'external_physical_accuracy_verified':False}
        if receipt_path:
            content={'schema':SCHEMA,'kind':'numeric-computation','command':args,
                     'result':result,'result_sha256':hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                     'source_sha256':sha(SOURCE),'output_file':str(Path(filename).absolute()) if filename else None,
                     'output_sha256':sha(filename) if filename else None,
                     'note':'Local checksum only: neither cryptographic signature nor real-world measurement'}
            with receipt_path.open('x',encoding='utf-8') as f:
                json.dump(content,f,ensure_ascii=False,indent=2)
            result['black_dragon']['receipt_file']=str(receipt_path)
        json_print(result)
        return 0
    except (ValueError,OSError,subprocess.TimeoutExpired,OverflowError,ArithmeticError) as e:
        json_print({'ok':False,'error':str(e)[:600]})
        return 2

if __name__=='__main__':
    sys.exit(main(sys.argv[1:]))
