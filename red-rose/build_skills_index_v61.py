from pathlib import Path
import zipfile,hashlib,json,sqlite3,collections,re,time,os,stat,argparse
parser=argparse.ArgumentParser(description="Build local reference-only skill index")
parser.add_argument("archive");parser.add_argument("--output-dir",default=str(Path.home()/".red-rose"/"skills-fusion-v61"));parser.add_argument("--approve-write",action="store_true");args=parser.parse_args()
if not args.approve_write:parser.error("--approve-write required")
p=Path(args.archive).resolve(strict=True);o=Path(args.output_dir).resolve();o.mkdir(parents=True,exist_ok=True)
temp=o/"skills-index.build.sqlite3";dest=o/"skills-index.sqlite3"
if temp.exists() or dest.exists():raise FileExistsError("index exists; avoid overwriting")
def sha(path):
 with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
digest=sha(p);st=p.stat();db=sqlite3.connect(temp)
db.execute("CREATE TABLE docs(path TEXT PRIMARY KEY,digest TEXT NOT NULL,size INTEGER NOT NULL,category TEXT NOT NULL,license TEXT,status TEXT NOT NULL)")
db.execute("CREATE INDEX digest_ix ON docs(digest)")
db.execute("CREATE INDEX category_ix ON docs(category)")
db.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
cats={"media":r"remotion|ffmpeg|blender|video|montage|cinema|animation|motion|subtitle|caption|typograph|storyboard|whisper|audio|sound|veo|film|reel|composit|grading|kdenlive|shotcut|manim|lottie","finance":r"accounting|financial|audit|bookkeep|reconcil|payroll|spreadsheet|excel|ifrs","engineering":r"test|debug|review|architecture|security|deploy|performance|python|typescript","reasoning":r"reason|planning|research|decision|analysis|learning|agent"}
counts=collections.Counter();unique=set();roots=set()
try:
 with zipfile.ZipFile(p) as z:
  docs=[x for x in z.infolist() if x.filename.lower().endswith("/skill.md") and not x.is_dir()]
  for i,x in enumerate(docs,1):
   name=x.filename;parts=name.replace("\\","/").split("/")
   if x.file_size>2*1024**2 or x.flag_bits&1 or any(q in ("",".","..") or ":" in q for q in parts) or stat.S_ISLNK(x.external_attr>>16):
    counts["skipped"]+=1;continue
   try:
    raw=z.read(x);d=hashlib.sha256(raw).hexdigest();t=raw[:8192].decode("utf-8",errors="replace")
    m=re.search(r"(?im)^license:\s*['\"]?([A-Za-z0-9 .+-]{1,64})",t)
    lic=m.group(1).strip() if m else None
    cat=next((k for k,v in cats.items() if re.search(v,name,re.I)),"other")
    db.execute("INSERT INTO docs VALUES(?,?,?,?,?,?)",(name,d,len(raw),cat,lic,"reference_only"))
    counts[cat]+=1;unique.add(d);roots.add(parts[0])
   except (OSError,ValueError,zipfile.BadZipFile,RuntimeError,sqlite3.IntegrityError):counts["skipped"]+=1
   if i%5000==0:print("INDEX",i,"/",len(docs),flush=True)
 if not (st.st_size==p.stat().st_size and st.st_mtime_ns==p.stat().st_mtime_ns and sha(p)==digest):raise ValueError("source changed")
 result={"archive_sha256":digest,"archive_bytes":st.st_size,"skill_documents":len(docs),"indexed":sum(v for k,v in counts.items() if k!="skipped"),"unique_documents":len(unique),"roots":len(roots),"categories":dict(counts),"source_code_executed":False,"native_capabilities_claimed":0}
 db.execute("INSERT INTO metadata VALUES('receipt',?)",(json.dumps(result),));db.commit()
 if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("index integrity failure")
 db.close();temp.rename(dest);(o/"index-receipt.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
 print("INDEX_COMPLETE",json.dumps(result),flush=True)
finally:
 db.close()
