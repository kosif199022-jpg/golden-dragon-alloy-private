"""V61: bounded, local reference corpus index. No archive extraction or execution."""
from __future__ import annotations
import hashlib,json,re,stat,zipfile,sqlite3,os,unicodedata
from pathlib import Path
from collections import Counter
from contextlib import closing

DEFAULT=Path.home()/".red-rose"/"knowledge"/"skills-v61.sqlite3"
DOMAINS={
"media":r"\b(video|reel|ffmpeg|remotion|veo[0-9]*|cinema\w*|montage|blender|storyboard|animation|subtitle\w*|motion.graphics|caption\w*|audio|film|typograph\w*)\b",
"engineering":r"\b(python|typescript|software|debug\w*|test\w*|code|api|database|git|architecture|deploy\w*)\b",
"finance":r"\b(accounting|finance|financial|audit|ifrs|bookkeeping|payroll|reconcil\w*|tax|spreadsheet)\b",
"reasoning":r"\b(reason\w*|planning|research|decision|critical.thinking|evaluation|verification|review|analysis)\b",
"design":r"\b(design|ux|ui|figma|illustration|graphic\w*|color|layout)\b"}
ALIASES={"مونتاج":"video","فيديو":"video","دعاء":"reel","صوت":"audio","خطوط":"typography","محاسبة":"accounting","مالية":"finance","اختبار":"testing","تفكير":"reasoning","تصميم":"design","موشن":"motion graphics","ترجمة":"subtitle"}
def norm(s):
    return unicodedata.normalize("NFKC",s).casefold()
def terms(s):
    for k,v in ALIASES.items():s=s.replace(k,v)
    return list(dict.fromkeys(re.findall(r"[\w]+",norm(s))))[:12]
def safe_member(x):
    n=x.filename
    return (len(n)<=1024 and not n.startswith(("/", "\\")) and "\\" not in n and
        not any(q in ("",".","..") or ":" in q or any(ord(c)<32 for c in q) for q in n.rstrip("/").split("/")) and not stat.S_ISLNK(x.external_attr>>16) and not x.flag_bits&1)
def filehash(p):
    with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def build(archive,out,approve=False):
    if not approve:raise PermissionError("write approval required")
    archive=Path(archive).resolve(strict=True);out=Path(out).resolve()
    if out.exists():raise FileExistsError("use a new index path")
    if archive.stat().st_size>2*1024**3:raise ValueError("archive too large")
    before=filehash(archive);tmp=out.with_suffix(out.suffix+".building")
    if tmp.exists():raise FileExistsError("unfinished index exists")
    out.parent.mkdir(parents=True,exist_ok=True)
    counts=Counter();domains=Counter();seen=set()
    try:
        with zipfile.ZipFile(archive) as z, closing(sqlite3.connect(tmp)) as db:
            infos=z.infolist()
            if len(infos)>250000 or sum(x.file_size for x in infos)>4*1024**3:raise ValueError("archive budget exceeded")
            db.executescript("CREATE TABLE refs(path TEXT PRIMARY KEY, digest TEXT, bytes INTEGER, domains TEXT, tokens TEXT); CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT); CREATE INDEX by_digest ON refs(digest);")
            counts["archive_entries"]=len(infos)
            collisions=Counter(norm(x.filename) for x in infos)
            for x in infos:
                if not (x.filename.lower().endswith("/skill.md") or x.filename.lower()=="skill.md"):continue
                counts["skill_documents"]+=1
                if not safe_member(x) or collisions[norm(x.filename)]!=1 or x.file_size>524288 or x.file_size/max(1,x.compress_size)>2000:
                    counts["skipped_unsafe_or_oversized"]+=1;continue
                try:
                    b=z.read(x);s=b.decode("utf-8-sig")
                except (UnicodeError,zipfile.BadZipFile,RuntimeError,NotImplementedError):
                    counts["skipped_unreadable"]+=1;continue
                digest=hashlib.sha256(b).hexdigest()
                # Retain only bounded vocabulary and paths, never skill instructions or scripts.
                key=norm(x.filename.replace("--"," ").replace("-"," ").replace("_"," "))
                vocab=set(re.findall(r"[a-z][a-z0-9]{2,31}",norm(s[:8192])))
                tag=[k for k,v in DOMAINS.items() if re.search(v,key+" "+norm(s[:4096]))]
                for k in tag:domains[k]+=1
                tokens=" ".join(sorted(vocab.intersection(set(re.findall(r"[a-z][a-z0-9]{2,31}",key))|{"video","audio","animation","ffmpeg","remotion","veo","subtitles","captions","typography","render","testing","reasoning","finance","accounting","audit","python","planning","verification","design","storyboard","motion","graphics","blender","security","research","review","timing","performance","quality","arabic","excel","database","reconciliation"})))
                db.execute("INSERT INTO refs VALUES (?,?,?,?,?)",(x.filename,digest,len(b)," ".join(tag),tokens))
                counts["indexed"]+=1
                if digest not in seen:seen.add(digest);counts["unique_content"]+=1
                if counts["indexed"]%10000==0:db.commit()
            counts["duplicate_content"]=counts["indexed"]-counts["unique_content"]
            if filehash(archive)!=before:raise ValueError("archive changed")
            info={"schema":1,"archive_sha256":before,"counts":dict(counts),"domain_candidates":dict(domains),"status":"reference_index_only","executable_count":0,"all_semantically_reviewed":False,"external_code_executed":False}
            db.execute("INSERT INTO meta VALUES ('receipt',?)",(json.dumps(info),));db.commit()
        tmp.rename(out);return info
    finally:
        tmp.unlink(missing_ok=True)
def read_db(path):
    return sqlite3.connect(Path(path).resolve(strict=True).as_uri()+"?mode=ro",uri=True)
def status(path):
    with closing(read_db(path)) as db:return json.loads(db.execute("SELECT v FROM meta WHERE k='receipt'").fetchone()[0])
def search(path,query,limit=12):
    if not isinstance(query,str) or len(query)>400 or type(limit)!=int or not 1<=limit<=40:raise ValueError("invalid query")
    ts=terms(query)
    if not ts:return []
    with closing(read_db(path)) as db:
        rows=db.execute("SELECT path,digest,bytes,domains,tokens FROM refs").fetchall()
    scores=[];seen=set()
    for name,digest,size,dom,tok in rows:
        words=set(terms(name.replace("-"," ").replace("_"," ")))|set(tok.split())
        n=sum(t in words for t in ts)
        if n:scores.append((n,sum(t in norm(name) for t in ts),name,digest,size,dom))
    out=[]
    for score,_,name,digest,size,dom in sorted(scores,key=lambda x:(-x[0],-x[1],x[2])):
        if digest in seen:continue
        seen.add(digest);out.append({"path":name,"sha256":digest,"bytes":size,"domains":dom.split(),"score":score,"status":"unreviewed_reference"})
        if len(out)>=limit:break
    return out
def handle(a):
    try:
        if a.action=="build":r=build(a.value,a.index,a.approve_write)
        elif a.action=="status":r=status(a.index)
        else:r={"matches":search(a.index,a.value,a.limit),"status":"reference_only"}
        print(json.dumps(r,ensure_ascii=False));return 0
    except (OSError,ValueError,PermissionError,sqlite3.Error,zipfile.BadZipFile) as e:
        print(json.dumps({"ok":False,"error":str(e)},ensure_ascii=False));return 1
def register(sub):
    p=sub.add_parser("skill-corpus");p.add_argument("action",choices=["build","status","search"]);p.add_argument("value",nargs="?",default="");p.add_argument("--index",default=str(DEFAULT));p.add_argument("--limit",type=int,default=12);p.add_argument("--approve-write",action="store_true");p.set_defaults(ext_func=handle)
