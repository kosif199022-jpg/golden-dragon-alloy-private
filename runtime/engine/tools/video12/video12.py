#!/usr/bin/env python3
"""Black Dragon Video 12: real tool detection, opt-in install, routing and evidence.

Run through `python scripts/dragon.py tool video12 ...` or directly.
All third-party dependencies live in this directory; detection is NOT proof of rendering.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REGISTRY = json.loads((HERE / 'registry.json').read_text(encoding='utf-8'))
TOOLS = {x['id']: x for x in REGISTRY['tools']}
STAGES = ('brief', 'concept', 'color-design', 'shots', 'produce', 'qa-color', 'deliver')


def emit(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def venv_bin(executable: str) -> Path:
    bin_dir = HERE / '.venv' / ('Scripts' if os.name == 'nt' else 'bin')
    return bin_dir / (executable + ('.exe' if os.name == 'nt' else ''))


def node_bin(executable: str) -> Path:
    return HERE / 'node_modules' / '.bin' / (executable + ('.cmd' if os.name == 'nt' else ''))


def process(cmd, *, timeout=15, cwd=None):
    try:
        r = subprocess.run(cmd, cwd=cwd or HERE, check=False, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def installed_node():
    package_names = sorted({p for item in TOOLS.values() if item['kind'] in ('node-cli','node-library','system-binary') for p in item['packages']})
    if not shutil.which('node'):
        return {p:False for p in package_names}
    code = 'const m=require("module").createRequire(process.cwd()+"/package.json"); const names='+json.dumps(package_names)+'; console.log(JSON.stringify(Object.fromEntries(names.map(n=>[n,(()=>{try {m.resolve(n);return true}catch(e){return false}})()]))));'
    text = process(['node', '-e', code])
    try:
        return json.loads(text or '')
    except (json.JSONDecodeError, TypeError):
        return {p:False for p in package_names}


def installed_python():
    names = sorted({x['module'] for x in TOOLS.values() if x['kind']=='python-cli'})
    py = venv_bin('python')
    py = str(py) if py.is_file() else sys.executable
    code = 'import importlib.util,json;names='+repr(names)+';print(json.dumps({n:importlib.util.find_spec(n) is not None for n in names}))'
    text = process([py, '-c', code])
    try:
        return json.loads(text or '')
    except (json.JSONDecodeError, TypeError):
        return {p:False for p in names}


def installed_binary(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    npm_package = {'ffmpeg':'@ffmpeg-installer/ffmpeg', 'ffprobe':'@ffprobe-installer/ffprobe'}.get(name)
    if not npm_package or not shutil.which('node'):
        return None
    code = 'try{console.log(require('+json.dumps(npm_package)+').path)}catch(e){process.exit(1)}'
    text = process(['node', '-e', code])
    return text if text and Path(text).is_file() else None


def doctor():
    js, py = installed_node(), installed_python()
    has_ff = bool(installed_binary('ffmpeg') and installed_binary('ffprobe'))
    rows = []
    for t in TOOLS.values():
        kind = t['kind']
        ready = (all(js.get(pkg,False) for pkg in t['packages']) if kind in ('node-cli','node-library') else
                 py.get(t['module'],False) if kind == 'python-cli' else has_ff)
        rows.append({'id':t['id'], 'kind':kind, 'available':bool(ready), 'category':t['category']})
    return {'schema':REGISTRY['schema'], 'status':'dependency-check-only',
            'detected_count':sum(int(x['available']) for x in rows), 'total_count':len(rows),
            'node': bool(shutil.which('node')), 'npm':bool(shutil.which('npm')),
            'ffmpeg_ffprobe':has_ff, 'tools':rows}


def plan(task: str):
    s = task.casefold()
    chosen = ['remotion','gsap','ffmpeg']
    def add(name, *words):
        if any(word in s for word in words) and name not in chosen:
            chosen.append(name)
    add('hyperframes','hyperframes','html','تفاعلي','متصفح','web')
    add('motion-canvas','motion canvas','motion-canvas','رسم متحرك','موشن','timeline')
    add('threejs','three','3d','ثلاثي','بلندر','blender')
    add('manim','manim','معادلة','رياضيات','mathematic','equation')
    add('roughjs','rough','يدوي','سبورة','sketch','مرسوم')
    add('animejs','anime.js','animejs','kinetic','نصوص متحركة')
    add('mojs','mo.js','mojs','particles','جزيئات','انفجار')
    add('whisperx','whisperx','كلام','تعليق','ترجمة','تفريغ','subtitles','voice','صوت')
    add('auto-editor','auto-editor','صمت','سكتات','pause','silence','حذف توقف')
    hints = ['Existing Black Dragon 7-stage video protocol and deliver verification remain mandatory',
             'An available library is not automatically an executed or rendered tool',
             'Keep Auto-Editor pause margins and manually review jump cuts',
             'Check Remotion license before commercial rendering and WhisperX model terms',
             'Prefer Blender/HF-Blender and Cinema Craft on packages that include them']
    return {'task':task, 'selected':chosen, 'registered':list(TOOLS), 'stages':STAGES,
            'execution_status':'planning-only', 'integration':{'blender':'compatible','cinema-craft':'compatible'},
            'notes':hints}


def install(args):
    scope = ['node' if args.node else '', 'python' if args.python else '']
    if args.all:
        scope=['node','python']
    scope = [s for s in scope if s]
    if not scope:
        print('Choose --all, --node or --python', file=sys.stderr);return 2
    cmds=[]
    if 'node' in scope:
        if not shutil.which('npm'):
            print('npm missing; install Node 22+ first',file=sys.stderr);return 2
        cmds.append(['npm','install','--no-audit','--no-fund'])
    if 'python' in scope:
        candidate=venv_bin('python')
        if not candidate.is_file():
            cmds.append([sys.executable,'-m','venv',str(HERE/'.venv')])
        pip=venv_bin('pip')
        cmds.append([str(pip),'install','-r',str(HERE/'requirements.txt')])
    emit({'mode':'dry-run' if not args.yes else 'install-requested','cwd':str(HERE),'commands':cmds,
          'external_scripts_will_run':True,'requires_explicit_yes':True})
    if not args.yes:
        return 0
    for cmd in cmds:
        try:
            rc=subprocess.run(cmd,cwd=HERE,check=False).returncode
        except OSError as ex:
            print('Launch failed:',ex,file=sys.stderr);return 1
        if rc:
            return rc
    return 0


def executable(tool_id: str):
    entry=TOOLS[tool_id]
    if entry['kind']=='system-binary':
        return installed_binary('ffmpeg')
    if entry['kind']=='node-cli':
        path=node_bin(entry['binary']); return str(path) if path.is_file() else None
    if entry['kind']=='python-cli':
        path=venv_bin(entry['binary'])
        if path.is_file():return str(path)
        return shutil.which(entry['binary'])
    return None


def run_tool(tool_id: str, args: list[str], receipt: str | None):
    tool=TOOLS[tool_id]
    if receipt and Path(receipt).expanduser().resolve().exists():
        print('Refusing to overwrite receipt or execute without a new evidence path',file=sys.stderr);return 3
    if tool['kind']=='node-library':
        print('This tool is an importable JS library, not a standalone command. Use it from a composition project.', file=sys.stderr);return 2
    if args and args[0]=='--':args=args[1:]
    if not args:
        print('Provide explicit CLI args after --',file=sys.stderr);return 2
    command=executable(tool_id)
    if not command:
        print(f'{tool_id} CLI not installed; use doctor/install',file=sys.stderr);return 2
    cmd=[command, *args]
    try:
        rc=subprocess.run(cmd,cwd=HERE,check=False).returncode
    except OSError as ex:
        print(ex,file=sys.stderr);return 1
    if receipt:
        path=Path(receipt).expanduser().resolve()
        # Do not overwrite existing review evidence.
        if path.exists():
            print('Refusing to overwrite receipt',file=sys.stderr);return 3
        path.parent.mkdir(parents=True,exist_ok=True)
        evidence={'schema':'kosif.black-dragon.video12.execution.v1','tool':tool_id,
                  'exit_code':rc, 'cmd':cmd,'time_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                  'executed':True, 'output_quality_verified':False}
        path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return rc


def main(argv=None):
    ap=argparse.ArgumentParser(prog='dragon.py tool video12',description=__doc__)
    sub=ap.add_subparsers(dest='action',required=True)
    doctor_p=sub.add_parser('doctor',help='Offline presence check (not a render test)')
    doctor_p.add_argument('--json',action='store_true')
    pl=sub.add_parser('plan',help='Pick libraries by task (does not render)');pl.add_argument('task')
    ins=sub.add_parser('install',help='Opt-in npm/Python downloads on this machine')
    ins.add_argument('--all',action='store_true');ins.add_argument('--node',action='store_true')
    ins.add_argument('--python',action='store_true');ins.add_argument('--yes',action='store_true')
    run=sub.add_parser('run',help='Invoke an installed CLI with explicit arguments')
    run.add_argument('--receipt',help='Write new execution evidence JSON; never overwrites')
    run.add_argument('tool',choices=sorted(TOOLS));run.add_argument('tool_args',nargs=argparse.REMAINDER)
    sub.add_parser('list',help='Print all 12 source-linked tools and their install methods')
    args=ap.parse_args(argv)
    if args.action=='list':emit(REGISTRY);return 0
    if args.action=='doctor':
        d=doctor()
        if args.json:emit(d)
        else:
            for row in d['tools']:
                print(('[READY]  ' if row['available'] else '[MISSING]'),row['id'],row['kind'])
            print(f"Resolved {d['detected_count']}/{d['total_count']}; no video rendered")
        return 0
    if args.action=='plan':emit(plan(args.task));return 0
    if args.action=='install':return install(args)
    if args.action=='run':return run_tool(args.tool,args.tool_args,args.receipt)
    return 2

if __name__=='__main__':
    raise SystemExit(main())
