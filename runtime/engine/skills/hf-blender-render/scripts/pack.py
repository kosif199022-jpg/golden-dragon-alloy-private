"""Review-only sandbox handoff packer; never uploads or executes code.

usage: python scripts/pack.py JOB SCENE.py [SOUND.py] --out command.sh [--force]
The generated command is intended for *manual approval* before remote use.
"""
import base64
import gzip
import io
import os
from pathlib import Path
import re
import sys
import tarfile

HERE=Path(__file__).resolve().parent
TOOLS=['hf_bootstrap.sh','hf_render.sh','hf_finish.sh']
NAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')


def main(argv=None):
    a=list(sys.argv[1:] if argv is None else argv)
    force=False
    if '--force' in a:
        a.remove('--force');force=True
    if '--out' not in a:raise ValueError('Specify --out FILE. Review the generated shell command before use.')
    i=a.index('--out')
    if i+1>=len(a):raise ValueError('--out requires file')
    out=Path(a[i+1]);del a[i:i+2]
    if len(a)<2:raise ValueError('usage: pack.py JOB SCENE.py [SOUND.py] --out FILE')
    job,files=a[0],a[1:]
    if not NAME.fullmatch(job):raise ValueError('Job name must be 1..64 ASCII letters, numbers, _ or -')
    if len(files)>10:raise ValueError('At most 10 input files')
    seen=set();scene_paths=[]
    for file in files:
        p=Path(file)
        if not p.is_file() or p.is_symlink():raise ValueError(f'Missing or non-regular input: {file}')
        if p.suffix!='.py':raise ValueError('Only reviewed Python scene/audio scripts allowed')
        if p.name in seen:raise ValueError('Duplicate basename not allowed')
        seen.add(p.name)
        if p.stat().st_size>1_000_000:raise ValueError(f'File exceeds 1MB: {p.name}')
        scene_paths.append(p)
    if out.exists() and not force:raise FileExistsError(f'{out} exists; use --force if intended')
    if out.resolve() in [p.resolve() for p in scene_paths]:raise ValueError('Output cannot overwrite input')
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w:gz',compresslevel=9) as tf:
        for name in TOOLS:
            path=HERE/name
            if not path.is_file():raise FileNotFoundError(path)
            tf.add(path,arcname=f'bdtools/{name}',recursive=False)
        for p in scene_paths:
            tf.add(p,arcname=f'jobs/{job}/in/{p.name}',recursive=False)
    b64=base64.b64encode(payload.getvalue()).decode('ascii')
    # Job validated as safe shell token. Tar members are all generated with controlled paths.
    cmd=("mkdir -p /home/user && cd /home/user && base64 -d > /tmp/kosif_blender_pack.tgz <<'KOSIF_DATA'\n"
         +b64+"\nKOSIF_DATA\n"
         +f"tar -xzf /tmp/kosif_blender_pack.tgz && chmod +x bdtools/*.sh && ls -l jobs/{job}/in && echo PACK_OK\n")
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists() and not force:raise FileExistsError(out)
    out.write_text(cmd,encoding='utf-8')
    print(f'PACK_ONLY: command={out} bytes={len(cmd)} files={len(scene_paths)+len(TOOLS)} job={job} | not executed')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,FileExistsError,FileNotFoundError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr);raise SystemExit(2)
