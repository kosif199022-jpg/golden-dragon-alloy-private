"""Apply the compiled quality policy in the source tree or the standalone archive."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile


def load_policy():
    archive = getattr(globals().get("__loader__"), "archive", None)
    if archive:
        with zipfile.ZipFile(archive) as package:
            return json.loads(package.read("policy.json"))
    return json.loads(Path(__file__).with_name("policy.json").read_bytes())


def review(request, policy, anchors=()):
    tokens=set(re.findall(r"[^\W_]+",request.casefold()))
    checks=policy["checks"]
    direct={k for k,v in checks.items() if tokens.intersection(v["cues"])}
    direct.update(anchors)
    if not direct:
        direct.add("validation")
    # A joint count estimates how frequently two concerns occurred in one source.
    scores={k:sum(checks[d]["joint"].get(k,0)/max(1,checks[d]["joint"].get(d,0))
                  for d in direct)/len(direct) for k in checks}
    ordered=sorted(checks,key=lambda k:(k not in direct,-scores[k],k))
    return [{"area":k,"check":checks[k]["check"]} for k in ordered if k in direct or scores[k]>=0.40]


def media_info(path):
    raw=subprocess.check_output(["ffprobe","-v","error","-show_entries",
                                 "stream=codec_type,width,height,avg_frame_rate:format=duration",
                                 "-of","json",str(path)])
    return json.loads(raw)


def verify(result, sources):
    evidence={}
    media=result.get("vertical_video") or result.get("media")
    if media:
        actual=media_info(media["output"])
        stream=next(s for s in actual["streams"] if s["codec_type"]=="video")
        if (stream["width"],stream["height"],stream["avg_frame_rate"])!=(1080,1920,"30/1"):
            raise ValueError("Export verification failed")
        evidence["geometry"]=[stream["width"],stream["height"]]
        evidence["timing"]={"seconds":float(actual["format"]["duration"]),"fps":30}
        videos=[p for p in sources if p.suffix.lower() not in {".exe",".dll",".csv"}]
        if videos:
            audio=lambda v:sum(x["codec_type"]=="audio" for x in v["streams"])
            original=media_info(videos[0])
            if audio(original)!=audio(actual):
                raise ValueError("Audio stream count changed")
            evidence["sound"]={"input_streams":audio(original),"output_streams":audio(actual)}
    if "counts" in result:
        evidence["identity"]={"classified_items":sum(result["counts"].values())}
    for entry,path in zip(result.get("binary_inspections",[]),[p for p in sources if p.suffix.lower() in {".exe",".dll"}]):
        with path.open("rb") as source:
            digest=hashlib.file_digest(source,"sha256").hexdigest()
        if digest!=entry["sha256"]:
            raise ValueError("Input identity changed")
        evidence.setdefault("provenance",[]).append({"file":path.name,"sha256":digest})
    return evidence
