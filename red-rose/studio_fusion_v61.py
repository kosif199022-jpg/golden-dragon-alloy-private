"""V61: original deterministic shot contract, prompt preflight, motion sampling and local skill index lookup."""
from __future__ import annotations
import json,math,re,sqlite3,unicodedata
from pathlib import Path

def num(v,lo,hi):
    if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError("numeric bounds")
    return v
def txt(v,maxlen=1200):
    if not isinstance(v,str) or not v.strip() or len(v)>maxlen or any(ord(c)<32 for c in v):raise ValueError("invalid text")
    return v.strip()
def words(s):
    clean="".join(c for c in unicodedata.normalize("NFC",s) if not unicodedata.category(c).startswith("M"))
    return len(re.findall(r"[^\W_]+(?:['’][^\W_]+)*",clean,re.UNICODE))
def shot_contract(j):
    # Operator supplies allowed durations for their actual provider/UI; default is a planning assumption.
    allowed=j.get("allowed_seconds",[8])
    if not isinstance(allowed,list) or not 1<=len(allowed)<=10 or any(type(x)!=int or not 1<=x<=30 for x in allowed):raise ValueError("invalid duration choices")
    allowed=sorted(set(allowed));duration=j.get("duration",8)
    if type(duration)!=int or duration not in allowed:raise ValueError("duration not in supplied provider choices")
    fps=j.get("fps",30)
    if type(fps)!=int or fps not in (24,25,30,60):raise ValueError("unsupported fps")
    identity=txt(j["identity"]);setting=txt(j["setting"]);style=txt(j["style"]);camera=txt(j["camera"],300)
    # The speaking rate is a conservative editable estimate, not measured voice alignment.
    rate=num(j.get("words_per_second",2.4),1,5);hold=num(j.get("end_hold",.5),0,3)
    beats=j["beats"]
    if not isinstance(beats,list) or not 1<=len(beats)<=6:raise ValueError("1–6 beats")
    cursor=0;rows=[];issues=[];lines=[]
    for i,b in enumerate(beats):
        seconds=num(b["seconds"],.25,30);frames=round(seconds*fps)
        if frames<1:raise ValueError("zero frames")
        action=txt(b["action"]);speaker=txt(b.get("speaker","none"),80)
        dialogue=b.get("dialogue","")
        if dialogue:dialogue=txt(dialogue,300)
        if dialogue and speaker=="none":raise ValueError("dialogue needs speaker")
        count=words(dialogue);available=frames/fps-(hold if i==len(beats)-1 else 0)
        needed=count/rate+(.25 if count else 0)
        if needed>available+1e-9:issues.append({"beat":i+1,"code":"speech_budget_exceeded","words":count,"estimated_seconds":round(needed,3),"available_seconds":round(available,3)})
        rows.append({"start_frame":cursor,"end_frame_exclusive":cursor+frames,"action":action,"speaker":speaker,"dialogue":dialogue,"estimated_speech_seconds":round(needed,3)})
        lines.append(f"{cursor/fps:.2f}–{(cursor+frames)/fps:.2f}s: {action}"+(f' {speaker} says exactly: "{dialogue}".' if dialogue else ""))
        cursor+=frames
    if cursor!=duration*fps:issues.append({"code":"timeline_duration_mismatch","expected_frames":duration*fps,"actual_frames":cursor})
    if j.get("reference_required",False) and not j.get("reference_id"):issues.append({"code":"missing_reference"})
    if str(j.get("kind","")).strip().casefold() in ("dua","duaa","azkar","prayer","دعاء","أذكار","اذكار","ريل دعاء"):issues.append({"code":"dua_requires_existing_mandatory_source_gate"})
    ref=txt(j["reference_id"],200) if j.get("reference_id") else None
    p="\n".join([f"Create a {duration}-second vertical 9:16 animated video.",f"Character identity: {identity}.",f"Use the supplied approved reference {ref} consistently." if ref else "Preserve the stated character design.",f"Setting: {setting}.",f"Visual direction: {style}.",f"Camera: {camera}.",*lines,"Audio: natural dialogue pronunciation, clear voice, subtle original ambience; synchronize lips to spoken words. No invented speech. Preserve identity, costume, lighting and spatial continuity. No on-screen text unless requested."])
    return {"status":"review_required" if issues else "plan_ready","issues":issues,"duration":duration,"fps":fps,"frames":cursor,"beats":rows,"prompt":p if not issues else None,"speech_estimate_only":True,"provider_duration_verified":False,"character_identity_verified":False,"actual_lip_sync_verified":False,"generation_performed":False,"qa_checklist":["first three seconds understandable without audio","character and outfit continuity","hands, face and eye stability","actual speech exactness and timing","no accidental flash or black frames","technical codec and frame count","review original audio rights"]}
def motion_curve(j):
    n=j["frames"]
    if type(n)!=int or not 2<=n<=18000:raise ValueError("frame count")
    keys=j["keyframes"]
    if not isinstance(keys,list) or not 2<=len(keys)<=100:raise ValueError("keyframes")
    parsed=[]
    for k in keys:
        f=k["frame"];v=num(k["value"],-100000,100000);e=k.get("ease","smooth")
        if type(f)!=int or not 0<=f<n or (parsed and f<=parsed[-1][0]) or e not in ("linear","smooth","ease-in","ease-out"):raise ValueError("invalid keyframe")
        parsed.append((f,v,e))
    if parsed[0][0]!=0 or parsed[-1][0]!=n-1:raise ValueError("explicit endpoint keys required")
    values=[];i=0
    for f in range(n):
        while i+1<len(parsed)-1 and f>parsed[i+1][0]:i+=1
        a,x,e=parsed[i];b,y,_=parsed[i+1];u=(f-a)/(b-a)
        t={"linear":lambda u:u,"smooth":lambda u:u*u*(3-2*u),"ease-in":lambda u:u*u,"ease-out":lambda u:1-(1-u)**2}[e](u)
        values.append(round(x+(y-x)*t,9))
    return {"frames":n,"values":values,"deterministic":True,"reference_motion_verified":False}
def catalog(query,limit=20,path=None):
    q=txt(query,100);limit=int(num(limit,1,100))
    p=Path(path) if path else Path.home()/".red-rose"/"skills-fusion-v61"/"skills-index.sqlite3"
    if not p.is_file():raise ValueError("local reference index missing")
    # Query strings never become SQL; index holds no executable instructions.
    db=sqlite3.connect(p.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        term="%"+q.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")+"%"
        rows=db.execute("SELECT path,digest,size,category,license,status FROM docs WHERE path LIKE ? ESCAPE '\\' ORDER BY path LIMIT ?",(term,limit)).fetchall()
        return {"matches":[dict(zip(("path","sha256","size","category","license_label","status"),r)) for r in rows],"license_verified":False,"execution_verified":False}
    finally:db.close()
def handle(a):
    try:
        if a.action=="find":r=catalog(a.source,a.limit)
        else:
            p=Path(a.source)
            if p.stat().st_size>256*1024:raise ValueError("input too large")
            j=json.loads(p.read_text(encoding="utf-8"))
            r=shot_contract(j) if a.action=="shot" else motion_curve(j)
        print(json.dumps(r,ensure_ascii=False,allow_nan=False));return 2 if r.get("status")=="review_required" else 0
    except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as e:print(json.dumps({"error":str(e)[:200]}));return 1
def register(sub):
    p=sub.add_parser("studio-fusion",help="native shot and motion contracts; indexed source references")
    p.add_argument("action",choices=["shot","curve","find"]);p.add_argument("source");p.add_argument("--limit",type=int,default=20);p.set_defaults(ext_func=handle)
