"""Read-only VN archive evidence reader. No extraction, rendering or network."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import plistlib
import re
import statistics
import zipfile

MAX_MEMBERS = 12000
MAX_METADATA = 8 * 1024 * 1024
MAX_TOTAL = 48 * 1024 * 1024
MAX_NODES = 150000
MEDIA = {".mp4", ".mov", ".m4v", ".webm", ".jpg", ".jpeg", ".png", ".heic",
         ".wav", ".aac", ".m4a", ".mp3", ".ttf", ".otf", ".webp", ".gif"}
META = {".json", ".plist", ".txt", ".xml", ".draft", ".project", ".vnproj", ".data", ""}
GROUPS = {
    "timeline": ("track", "timeline", "segment", "clip", "layer"),
    "timing": ("start", "end", "duration", "time", "offset", "fps", "frame"),
    "typography": ("font", "text", "caption", "subtitle", "stroke", "shadow", "align", "letterspacing"),
    "motion": ("keyframe", "scale", "rotation", "position", "transform", "easing", "animation"),
    "transition": ("transition", "fade", "dissolve"),
    "audio": ("audio", "volume", "gain", "music", "voice", "sound"),
    "canvas": ("width", "height", "ratio", "resolution", "background"),
    "color": ("color", "colour", "filter", "lut", "saturation", "contrast", "brightness"),
}

def normalized(key):
    return re.sub(r"[^a-z0-9]", "", key.casefold())

def timing_unit(key):
    k = normalized(key)
    # Only explicit units; VN schemas vary and raw duration values are not seconds by default.
    for suffix, divisor in (("milliseconds",1000),("millisecond",1000),("msec",1000),
                            ("ms",1000),("microseconds",1000000),("microsecond",1000000),
                            ("us",1000000),("seconds",1),("second",1),("secs",1),("sec",1)):
        if k.endswith(suffix) and any(t in k for t in ("time","duration","start","end","offset")):
            return divisor
    return None

def quantiles(values):
    return {"count":len(values), "min":round(min(values),6),
            "median":round(statistics.median(values),6), "max":round(max(values),6)}

def walk(obj, report, *, limit=MAX_NODES):
    stack=[("$", "", obj, 0)]
    visited=0
    while stack and visited < limit:
        path,key,node,depth=stack.pop()
        visited+=1
        if depth>48:
            report["limited"]=True
            continue
        k=normalized(key)
        for group,terms in GROUPS.items():
            if any(t in k for t in terms):
                report["groups"][group][path]+=1
        if isinstance(node,dict):
            # Count structure without retaining arbitrary source strings or asset paths.
            if len(node)>limit:
                report["limited"]=True
            for name,value in list(node.items())[:limit]:
                name=str(name)
                # Report key names only; user content in string values is never collected.
                safe=name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}",name) else "<key>"
                stack.append((path+"."+safe,name,value,depth+1))
        elif isinstance(node,list):
            if len(node)>limit: report["limited"]=True
            stack.extend((path+"[]",key,value,depth+1) for value in node[:limit])
        elif isinstance(node,(int,float)) and not isinstance(node,bool):
            try: finite=math.isfinite(node)
            except OverflowError: finite=False
            if finite and k:
                if any(t in k for t in GROUPS["timing"]+GROUPS["canvas"]+GROUPS["motion"]+GROUPS["audio"]):
                    if len(report["numbers"])<3000 or path in report["numbers"]:
                        report["numbers"][path].append(float(node))
                        unit=timing_unit(key)
                        if unit:
                            report["seconds"][path].append(float(node)/unit)
        elif isinstance(node,str) and any(t in k for t in ("text","caption","subtitle")):
            # Retain counts only, not the actual prayer text.
            report["text_lengths"][path].append(len(node))
    if stack: report["limited"]=True
    return visited

def fresh():
    return {"groups":defaultdict(Counter),"numbers":defaultdict(list),
            "seconds":defaultdict(list),"text_lengths":defaultdict(list),"limited":False}

def summarize(report):
    return {"field_candidates":{k:dict(v.most_common(40)) for k,v in report["groups"].items()},
            "raw_numeric_fields":{k:quantiles(v) for k,v in sorted(report["numbers"].items())},
            "explicit_time_seconds":{k:quantiles(v) for k,v in sorted(report["seconds"].items())},
            "text_lengths":{k:quantiles(v) for k,v in sorted(report["text_lengths"].items())},
            "limited":report["limited"]}

def parse_metadata(data):
    # Do not interpret executable content, URLs or undocumented binary records.
    if data.startswith(b"bplist00"):
        return plistlib.loads(data)
    stripped=data.lstrip(b"\xef\xbb\xbf \r\n\t")
    if stripped.startswith((b"{",b"[")):
        return json.loads(data.decode("utf-8-sig"))
    if stripped.startswith(b"<?xml") and b"<plist" in stripped[:512] and b"<!ENTITY" not in data.upper():
        return plistlib.loads(data)
    return None

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def inspect(path, *, sha=False):
    p=Path(path)
    result={"file":p.name,"status":"unsupported","metadata_documents":0,
            "media_counts":{}, "warnings":[],"documents":[]}
    report=fresh()
    if not p.is_file(): return dict(result,status="missing")
    result["bytes"]=p.stat().st_size
    if sha: result["sha256"]=digest(p)
    try:
        if not zipfile.is_zipfile(p):
            if p.stat().st_size<=MAX_METADATA:
                obj=parse_metadata(p.read_bytes())
                if obj is not None:
                    walk(obj,report);result["metadata_documents"]=1
            return dict(result,status="parsed" if result["metadata_documents"] else "unsupported",
                        evidence=summarize(report))
        with zipfile.ZipFile(p) as z:
            infos=z.infolist()
            result["archive_members"]=len(infos)
            if len(infos)>MAX_MEMBERS:
                return dict(result,status="limit",warnings=["member count exceeds budget"])
            media=Counter()
            total=0
            remaining_nodes=MAX_NODES
            for info in infos:
                if info.is_dir(): continue
                suffix=PurePosixPath(info.filename.replace("\\","/")).suffix.casefold()
                if suffix in MEDIA:
                    media[suffix]+=1;continue
                if suffix not in META: continue
                if info.flag_bits & 1:
                    result["warnings"].append("encrypted metadata skipped");continue
                if info.file_size>MAX_METADATA or total+info.file_size>MAX_TOTAL:
                    result["warnings"].append("metadata size budget exceeded");continue
                if remaining_nodes<=0:
                    report["limited"]=True;break
                try:
                    with z.open(info) as f: data=f.read(MAX_METADATA+1)
                    total+=len(data)
                    if len(data)>MAX_METADATA: continue
                    obj=parse_metadata(data)
                    if obj is None: continue
                    remaining_nodes-=walk(obj,report,limit=remaining_nodes)
                    result["metadata_documents"]+=1
                    result["documents"].append({"member_index":len(result["documents"])+1,
                                                "bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
                except (ValueError, OSError, RuntimeError, zipfile.BadZipFile, RecursionError, OverflowError):
                    result["warnings"].append("unreadable metadata member")
            result["media_counts"]=dict(media)
            result["status"]="parsed" if result["metadata_documents"] else "schema_not_decoded"
    except (OSError,ValueError,RuntimeError,zipfile.BadZipFile,RecursionError,OverflowError):
        result["status"]="unreadable"
    result["evidence"]=summarize(report)
    result["warnings"]=sorted(set(result["warnings"]))
    return result

def evidence_profile(projects, *, verified_hashes):
    """Summarize independent metadata evidence, never a validated render style."""
    unique = [p for p in projects if p["status"] == "parsed" and "duplicate_of" not in p]
    timing = defaultdict(list)
    groups = Counter()
    limited = 0
    for p in unique:
        evidence = p.get("evidence", {})
        limited += bool(evidence.get("limited") or p.get("warnings"))
        groups.update(k for k, v in evidence.get("field_candidates", {}).items() if v)
        for path, stats in evidence.get("explicit_time_seconds", {}).items():
            if stats["min"] >= 0:
                timing[path].append(stats["median"])
    return {
        "status": "metadata_candidates_only",
        "unique_parsed_projects": len(unique) if verified_hashes else None,
        "content_dedup_verified": verified_hashes,
        "parsed_nonduplicate_inputs": len(unique),
        "limited_or_warned_projects": limited,
        "groups_project_support": dict(groups),
        "timing_candidates_seconds": {
            key: {"project_support": len(values), "project_medians": quantiles(values)}
            for key, values in sorted(timing.items()) if len(values) >= 2 and verified_hashes
        },
        "render_verified": False,
        "automatic_style_promotion": False,
    }

def batch(paths, *, sha=False):
    projects=[]; seen=set(); hashes={}
    for raw in paths:
        p=Path(raw)
        candidates=sorted(p.glob("*.vn")) if p.is_dir() else [p]
        for f in candidates:
            if len(projects)>=100: break
            key=str(f.resolve())
            if key in seen:continue
            seen.add(key)
            try:
                # Hash once, before parsing, to avoid repeating metadata work.
                fingerprint=digest(f) if sha and f.is_file() else None
                if fingerprint and fingerprint in hashes:
                    first=hashes[fingerprint]
                    projects.append({"file":f.name,"bytes":f.stat().st_size,
                                     "sha256":fingerprint,"status":first["status"],
                                     "duplicate_of":first["file"]})
                    continue
                result=inspect(f)
                if fingerprint:
                    result["sha256"]=fingerprint
                    hashes[fingerprint]=result
                projects.append(result)
            except OSError:
                projects.append({"file":f.name,"status":"unreadable","warnings":["input could not be read"]})
    parsed=sum(p["status"]=="parsed" for p in projects)
    duplicates=sum("duplicate_of" in p for p in projects)
    return {"ok":bool(projects) and parsed==len(projects),"projects":projects,
            "counts":{"inputs":len(projects),"metadata_parsed":parsed,"content_duplicates":duplicates},
            "profile":evidence_profile(projects,verified_hashes=sha),
            "limitations":["Field candidates are not confirmed track types or rendered visual effects.",
                           "Only explicit time units are converted; raw units must be mapped against a known schema.",
                           "Use --sha256 to verify independent projects; timing candidates require two independent sources.",
                           "Do not promote styles or claims until real project metadata and rendered reference are verified."]}

def handler(args):
    if args.render_job:
        from rose_dua_gate_v69 import check, read_json
        try:
            gate=check(read_json(args.render_job))
        except (ValueError,KeyError,TypeError,OSError,__import__('subprocess').SubprocessError) as e:
            print(json.dumps({'ok':False,'error':str(e)}));return 1
        print(json.dumps({'ok':True,'render_preflight':gate,'rendered':False},ensure_ascii=False));return 0
    if not args.paths:raise ValueError('VN input paths required')
    result=batch(args.paths,sha=args.sha256)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["ok"] else 1

def register(subparsers):
    p=subparsers.add_parser("vn-dua-analyze",help="Read-only VN project metadata evidence for dua reels")
    p.add_argument("paths",nargs="*")
    p.add_argument("--render-job",help="validate a proposed dua render job; never renders VN")
    p.add_argument("--sha256",action="store_true",help="stream full file hashes for duplicate detection")
    p.set_defaults(ext_func=handler)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    subs=p.add_subparsers(required=True)
    register(subs)
    raise SystemExit(handler(p.parse_args(["vn-dua-analyze",*__import__("sys").argv[1:]])))
