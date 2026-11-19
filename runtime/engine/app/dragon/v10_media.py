"""Read-only sample media audit: ffprobe metadata, fingerprints and honest QA scopes."""
from __future__ import annotations
import hashlib, json, subprocess, shutil
from pathlib import Path


def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def inspect(paths, *, deep=False, expect=None) -> dict:
    files=[]
    binary=shutil.which('ffprobe')
    for path in paths:
        p=Path(path).resolve()
        r={"path":str(p),"exists":p.is_file(),"metadata_only":not deep}
        if not r["exists"]:
            r.update(status="missing",error="file does not exist"); files.append(r);continue
        r.update(bytes=p.stat().st_size,sha256=digest(p))
        if not binary:
            r.update(status="unverified",error="ffprobe is unavailable");files.append(r);continue
        call=subprocess.run([binary,"-v","error","-show_format","-show_streams","-of","json",str(p)],
                            capture_output=True,text=True,timeout=30)
        if call.returncode:
            r.update(status="failed",error=(call.stderr or 'ffprobe failed')[:500]);files.append(r);continue
        data=json.loads(call.stdout)
        fmt=data.get('format',{});streams=data.get('streams',[])
        vid=next((x for x in streams if x.get('codec_type')=='video'),{})
        aud=next((x for x in streams if x.get('codec_type')=='audio'),{})
        r.update(status="probed",duration_s=float(fmt.get('duration') or 0),
                 video={k:vid.get(k) for k in ('codec_name','width','height','r_frame_rate','avg_frame_rate','pix_fmt') if k in vid},
                 audio={k:aud.get(k) for k in ('codec_name','channels','sample_rate') if k in aud})
        if expect and vid and f"{vid.get('width')}x{vid.get('height')}"!=expect:
            r['size_warning']=f"not {expect}"
        if deep:
            from .verify import probe_file
            v=probe_file(p,expect=expect,black=True)
            # Full verify is an actual scan, but a visual editorial review is still required.
            r.update(status="qa_pass" if v.get('ok') else "qa_fail",metadata_only=False,
                     qa_ok=v.get('ok',False),qa_errors=v.get('errors',[]),qa_warnings=v.get('warnings',[]),
                     qa_black=v.get('black',{}),qa_frame_count=v.get('frame_check'))
        files.append(r)
    return {"kind":"black-dragon.v10/media-audit", "files":files,"source_files_unchanged":True,
            "deep":bool(deep),"all_probed":all(f.get('status') in ('probed','qa_pass') for f in files),
            "note":"Metadata inspection is not creative/visual review; deep mode uses the existing technical video verifier."}
