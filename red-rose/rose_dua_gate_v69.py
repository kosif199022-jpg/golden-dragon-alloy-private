"""V69 mandatory preflight for the supported dua render entrypoints.

A receipt binds declared word timing to exact audio bytes; it is not proof that
an aligner actually ran. Asset ownership/rights and artistic QA remain separate.
"""
from pathlib import Path
from contextlib import closing
import argparse, collections, hashlib, json, math, re, shutil, subprocess, unicodedata

def roots():
    h=Path.home()/".red-rose"
    return h/"libraries"/"dua-telegram-complete"/"videos",h/"fonts"

def read_json(p):
    p=Path(p)
    if p.stat().st_size>8*1024*1024:raise ValueError("JSON size limit")
    return json.loads(p.read_text(encoding="utf-8-sig"))

def sha(p):
    with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def number(v):
    if type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError("invalid timestamp")
    return float(v)

def same(a,b):
    return abs(number(a)-number(b))<=0.001

def path(v):
    if not isinstance(v,str) or not v or len(v)>4096:raise ValueError("invalid path")
    p=Path(v).expanduser()
    if not p.is_absolute():raise ValueError("absolute asset path required")
    p=p.resolve(strict=True)
    if not p.is_file():raise ValueError("asset is not file")
    return p

def asset(entry,root=None,ext=None):
    p=path(entry["file"])
    if root is not None and not p.is_relative_to(Path(root).resolve(strict=True)):raise ValueError("asset outside approved library: "+p.name)
    if ext and p.suffix.lower() not in ext:raise ValueError("unsupported asset type")
    d=entry["sha256"]
    if not isinstance(d,str) or not re.fullmatch(r"[0-9a-f]{64}",d) or sha(p)!=d:raise ValueError("missing or mismatched SHA-256: "+p.name)
    return p

def duration(p,kind):
    r=subprocess.run(["ffprobe","-v","error","-protocol_whitelist","file,pipe","-select_streams",kind+":0","-show_entries","stream=duration:format=duration","-of","json",str(p)],capture_output=True,timeout=30,check=True)
    j=json.loads(r.stdout)
    if not j.get("streams"):raise ValueError("missing media stream")
    v=j["streams"][0].get("duration") or j["format"]["duration"]
    v=float(v)
    if not math.isfinite(v) or v<=0:raise ValueError("invalid media duration")
    return v

def words(s):
    if not isinstance(s,str) or not s.strip():raise ValueError("missing caption/word text")
    s="".join(c for c in unicodedata.normalize("NFC",s) if not unicodedata.category(c).startswith("M"))
    return re.findall(r"[^\W_]+",s.casefold(),re.UNICODE)

def check(job):
    if not isinstance(job,dict) or job.get("kind")!="dua":raise ValueError("explicit kind=dua required")
    video_root,font_root=roots()
    clips=job["clips"];fonts=job["fonts"];caps=job["captions"]
    if not isinstance(clips,list) or not 1<=len(clips)<=300:raise ValueError("explicit clips required")
    if not isinstance(fonts,dict) or not 1<=len(fonts)<=100:raise ValueError("registered fonts required")
    if not isinstance(caps,list) or not 1<=len(caps)<=1000:raise ValueError("caption word ranges required")
    verified_clips=[]
    for c in clips:
        p=asset(c,video_root,{".mp4",".mov",".m4v",".webm"})
        a,b=number(c["start"]),number(c["end"])
        if not a<b or b>duration(p,"v")+0.001:raise ValueError("invalid or out-of-bounds trim")
        verified_clips.append({"file":str(p),"sha256":c["sha256"],"start":a,"end":b})
    verified_fonts={k:str(asset(v,font_root,{".ttf",".otf",".ttc"})) for k,v in fonts.items()}
    audio=asset(job["audio"],None,{".wav",".m4a",".mp3",".aac",".flac",".mp4"})
    aud_dur=duration(audio,"a")
    timing=asset(job["word_timing"],None,{".json"})
    data=read_json(timing)
    if data.get("audio_sha256")!=job["audio"]["sha256"]:raise ValueError("word timing belongs to another audio")
    if data.get("method") not in ("whisper_word_timestamps","whisperx_alignment","manual_audio_alignment"):raise ValueError("no supported audio alignment provenance")
    if not isinstance(data.get("words"),list) or not 1<=len(data["words"])<=20000:raise ValueError("word timestamps required")
    aligned=data["words"];prev=0.;starts=[];ends=[]
    for w in aligned:
        a,b=number(w["start"]),number(w["end"])
        if not words(w["text"]) or a<prev-0.001 or not a<b or b>aud_dur+0.001:raise ValueError("invalid word chronology")
        starts.append(a);ends.append(b);prev=b
    if len(aligned)>=3:
        # Exact arithmetic-like equal subdivision is not accepted even when labelled aligned.
        lengths=[b-a for a,b in zip(starts,ends)]
        steps=[b-a for a,b in zip(starts,starts[1:])]
        if max(lengths)-min(lengths)<=0.001 and max(steps)-min(steps)<=0.001:raise ValueError("uniformly divided word timing")
    pos=0
    for c in caps:
        lo,hi=c["word_start"],c["word_end"]
        if type(lo)!=int or type(hi)!=int or lo!=pos or not lo<hi<=len(aligned):raise ValueError("caption word ranges must cover aligned words once, in order")
        if words(c["text"])!=[t for w in aligned[lo:hi] for t in words(w["text"])]:raise ValueError("caption text does not match aligned words")
        if not same(c["start"],starts[lo]) or not same(c["end"],ends[hi-1]):raise ValueError("caption timestamps differ from audio word times")
        pos=hi
    if pos!=len(aligned):raise ValueError("unmapped aligned words")
    return {"ok":True,"clips":verified_clips,"fonts":verified_fonts,"audio":str(audio),"captions":caps,"word_timing_sha256":job["word_timing"]["sha256"],"audio_alignment_independently_verified":False,"artistic_verified":False}

def bind_v34(plan,lengths):
    r=check(plan["dua_gate"])
    clips=plan.get("clips");lines=plan.get("lines");fonts=plan.get("fonts")
    if not isinstance(clips,list) or len(clips)!=len(r["clips"]) or len(clips)!=len(lengths):raise ValueError("explicit clip bindings required")
    if not isinstance(fonts,dict) or set(fonts)!={"line","calligraphy","title","latin"} or set(fonts)!=set(r["fonts"]):raise ValueError("all four actual font roles must be registered")
    for k,v in fonts.items():
        if str(path(v))!=r["fonts"][k]:raise ValueError("renderer font differs from gate")
    if str(path(plan["audio"]))!=r["audio"]:raise ValueError("renderer audio differs from gate")
    if not isinstance(lines,list) or len(lines)!=len(r["captions"]):raise ValueError("line/caption mismatch")
    for ln,c in zip(lines,r["captions"]):
        if not isinstance(ln,dict) or ln.get("tail") or ln.get("tail_emoji") or ln["text"]!=c["text"] or not same(ln["t0"],c["start"]) or not same(ln["t1"],c["end"]):raise ValueError("renderer caption differs from aligned caption; extra tails unsupported")
    for c,v,length in zip(clips,r["clips"],lengths):
        if not isinstance(c,dict) or c.get("kind","video")!="video" or str(path(c["file"]))!=v["file"] or not same(c["start"],v["start"]) or not same(c["end"],v["end"]) or not same(c["start"]+length,c["end"]):raise ValueError("renderer trim differs from gate")
    return r

FAST_FONTS={"Amiri-Bold.ttf","diwani.otf","IBMPlexSerif-Bold.ttf","IBMPlexSerif-Italic.ttf","panorama.ttf","sultan.ttf","Almarai-ExtraBold.ttf","Tajawal-Medium.ttf","Kufam.ttf"}
FAST_FAMILIES={"AmiriB","Diwani","PlexSerifB","PlexSerifI","Panorama","Sultan","AlmaraiXB","TajawalM","Kufam"}
def fast_glyph_check(s,r):
    # Browser canvas silently substitutes system fonts for missing glyphs.
    # Inspect each actual text family before staging; unsupported font collection
    # faces fail closed. This is a cmap check, not proof of correct shaping.
    try:
        from fontTools.ttLib import TTFont
    except ImportError as e:
        raise ValueError("fontTools required to check browser font fallback") from e
    family=dict(zip(("AmiriB","Diwani","PlexSerifB","PlexSerifI","Panorama","Sultan","AlmaraiXB","TajawalM","Kufam"),("Amiri-Bold.ttf","diwani.otf","IBMPlexSerif-Bold.ttf","IBMPlexSerif-Italic.ttf","panorama.ttf","sultan.ttf","Almarai-ExtraBold.ttf","Tajawal-Medium.ttf","Kufam.ttf")))
    use=collections.defaultdict(list)
    style=s["style"];header=s.get("header") or {}
    line=s.get("line") or {}
    linefile=path(line["font"]).name if line.get("font") else family[{"dxh":"AmiriB","day":"Sultan","oaun":"Sultan","adeiat":"AlmaraiXB"}[style]]
    for c in r["captions"]:use[linefile].append(c["text"])
    for e in s.get("elements",[]):use[path(e["font"]).name].append(e["text"])
    if style=="day" or (style=="oaun" and not s.get("noHeader")):
        for k,f in (("day","Panorama"),("date","PlexSerifB"),("hday","AmiriB"),("hmonth","Diwani")):
            use[family[f]].append(header[k])
    if style=="adeiat":
        for k,f in (("hday","Panorama"),("hmonth","Panorama"),("hline","AmiriB"),("hyear","AmiriB"),("day","Panorama"),("date","TajawalM")):
            use[family[f]].append(header.get(k,""))
        use[family["Kufam"]].append(s.get("ribbon") or "دعاء يوم الثلاثاء")
    elif not s.get("noHandle") or s.get("handleSpaced"):
        h=s.get("handleSpaced") or {}
        f=h.get("font","PlexSerifB") if h else ("PlexSerifI" if style=="day" else "PlexSerifB")
        use[family[f]].append((h.get("text") or s.get("handle") or "@elkosif").upper() if h or style=="dxh" else s.get("handle") or "@elkosif")
    if s.get("sticker_from") is not None:use[family["Diwani"]].extend(("صباح","الخير"))
    for name,texts in use.items():
        try:
            with TTFont(r["fonts"][name],lazy=True) as font:cmap=font.getBestCmap() or {}
        except Exception as e:raise ValueError("cannot verify font glyph coverage: "+name) from e
        for text in texts:
            if not isinstance(text,str):raise ValueError("invalid text element")
            if any(not c.isspace() and unicodedata.category(c)!="Cf" and ord(c) not in cmap for c in text):
                raise ValueError("unregistered font fallback would be required: "+name)

def bind_fast(work):
    w=Path(work).resolve(strict=True);s=read_json(w/"spec.json");r=check(s["dua_gate"])
    for p in (w/"web",w/"web"/"fonts",w/"web"/"fx",w/"web"/"spec.json",w/"web"/"index.html",w/"web"/"main.js",w/"web"/"clips.json"):
        if p.resolve()!=p:raise ValueError("staging path may not redirect outside workspace")
    # External lifted overlays and unvalidated traced shapes cannot establish font provenance.
    if s.get("overlay") or any(e.get("kind")!="text" or not e.get("font") for e in s.get("elements",[])):raise ValueError("unverified overlay/traced/fontless elements unsupported")
    if s.get("style") not in ("dxh","day","adeiat","oaun"):raise ValueError("unsupported fast-reel style")
    if (s.get("handleSpaced") or {}).get("font","PlexSerifB") not in FAST_FAMILIES:raise ValueError("unregistered handle font")
    required=set(FAST_FONTS)
    for e in s.get("elements",[])+[s.get("line") or {}]:
        if e.get("font"):
            p=path(e["font"]);required.add(p.name)
            if r["fonts"].get(p.name)!=str(p):raise ValueError("custom font differs from registered file")
    if set(r["fonts"])!=required:raise ValueError("all actual fast-reel font files must be registered")
    if str(path(str(w/"voice.m4a")))!=r["audio"]:raise ValueError("fast-reel voice differs from gate")
    sel=[x.strip() for x in (w/"sel.txt").read_text(encoding="utf-8-sig").splitlines() if x.strip()]
    scenes=s["scenes"]
    if len(sel)!=len(scenes) or len(sel)!=len(r["clips"]):raise ValueError("scene/clip mismatch")
    end=0.;extra=max(number(x.get("xf",0)) for x in scenes)+0.2
    for f,sc,c in zip(sel,scenes,r["clips"]):
        a,b=number(sc["a"]),number(sc["b"])
        if not same(a,end) or b<=a or str(path(f))!=c["file"] or not same(sc["ss"],c["start"]) or not same(c["start"]+(b-a)+extra,c["end"]):raise ValueError("fast-reel trim/scene differs from gate")
        end=b
    if number(s["dur"])>duration(Path(r["audio"]),"a")+0.001:raise ValueError("voice shorter than timeline")
    if not same(end,s["dur"]):raise ValueError("scene duration mismatch")
    if len(s["lines"])!=len(r["captions"]):raise ValueError("caption count mismatch")
    for ln,c in zip(s["lines"],r["captions"]):
        if len(ln)<2 or not same(ln[0],c["start"]) or ln[1]!=c["text"]:raise ValueError("fast-reel caption differs from word alignment")
    if r["captions"][-1]["end"]>number(s["dur"])+0.001:raise ValueError("caption beyond timeline")
    fast_glyph_check(s,r)
    return r

def stage_fast(work):
    w=Path(work).resolve(strict=True);r=bind_fast(w);dest=w/"web"/"fonts"
    if dest.resolve()!=dest:raise ValueError("staged font folder symlink")
    dest.mkdir(parents=True,exist_ok=True)
    for name,p in r["fonts"].items():
        q=dest/name
        if q.is_symlink():raise ValueError("staged font symlink")
        shutil.copyfile(p,q)
    shutil.copyfile(w/"spec.json",w/"web"/"spec.json")
    return r

def prepared_fast(work,seal=False):
    w=Path(work).resolve(strict=True);r=bind_fast(w);web=w/"web"
    for name in ('index.html','main.js'):
        if sha(web/name)!=sha(Path(__file__).resolve().parent/'agent'/'fast_reel'/'web'/name):raise ValueError('staged renderer code mismatch')
    if sha(web/"spec.json")!=sha(w/"spec.json"):raise ValueError("stale staged spec")
    for name,p in r["fonts"].items():
        if sha(web/"fonts"/name)!=sha(p):raise ValueError("staged font mismatch")
    c=read_json(web/"clips.json")
    if len(c["clips"])!=len(r["clips"]):raise ValueError("prepared clip count")
    frames={}
    for i,(item,src) in enumerate(zip(c["clips"],r["clips"])):
        if item["src"]!=Path(src["file"]).name:raise ValueError("prepared clip source mismatch")
        folder=web/"fx"/f"c{i:02d}"
        if folder.resolve()!=folder:raise ValueError("prepared folder redirection")
        files=sorted(folder.glob("*.jpg"))
        expected=math.ceil((src["end"]-src["start"])*30-0.001)
        if not files or len(files)!=item["frames"] or abs(len(files)-expected)>1:raise ValueError("prepared frames missing or wrong trim length")
        for k,f in enumerate(files,1):
            if f.name!=f"{k:04d}.jpg" or not f.resolve().is_relative_to(web.resolve()):raise ValueError("invalid prepared frame")
            frames[f.relative_to(web).as_posix()]=sha(f)
    receipt={"spec":sha(w/"spec.json"),"clips":sha(web/"clips.json"),"frames":frames}
    p=w/"dua-gate-prepared.json"
    if seal:
        if p.is_symlink():raise ValueError("receipt symlink")
        p.write_text(json.dumps(receipt,sort_keys=True),encoding="utf-8")
    elif read_json(p)!=receipt:raise ValueError("prepared footage changed since local extraction")
    return {"ok":True,"prepared_frames":len(frames),"semantic_verified":False}

def handle(a):
    try:
        if a.action in ("fast-stage","fast-seal") and not a.approve_write:raise PermissionError("--approve-write required")
        if a.action=="check":r=check(read_json(a.source))
        elif a.action=="fast-check":r=bind_fast(a.source)
        elif a.action=="fast-stage":r=stage_fast(a.source)
        else:r=prepared_fast(a.source,seal=a.action=="fast-seal")
        print(json.dumps(r,ensure_ascii=False));return 0
    except (ValueError,KeyError,TypeError,IndexError,AttributeError,OverflowError,OSError,subprocess.SubprocessError) as e:
        print(json.dumps({"ok":False,"error":"dua-gate: "+str(e)[:400]},ensure_ascii=False));return 1

def register(sub):
    p=sub.add_parser("dua-gate",help="mandatory approved dua media/word timing preflight")
    p.add_argument("action",choices=["check","fast-check","fast-stage","fast-seal","fast-prepared"]);p.add_argument("source");p.add_argument("--approve-write",action="store_true");p.set_defaults(ext_func=handle)
if __name__=="__main__":
    p=argparse.ArgumentParser();sub=p.add_subparsers(required=True);register(sub)
    a=p.parse_args();raise SystemExit(a.ext_func(a))
