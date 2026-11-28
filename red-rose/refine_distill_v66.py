from pathlib import Path
import sys,sqlite3,zipfile,hashlib,json,collections,re,shutil,os,time
from contextlib import closing
import argparse
from rose_distill_v66 import ACTION,RULE,RESTRICT,STUB,MARK,BADLINE,SECTION,PREFERRED
p=argparse.ArgumentParser(description="Refine unselected V66 skill candidates")
p.add_argument("collector");p.add_argument("--database",default=str(Path.home()/".red-rose"/"distilled-v66"/"lessons.sqlite3"));p.add_argument("--approve-write",action="store_true");args=p.parse_args()
if not args.approve_write:p.error("--approve-write required")
root=Path(args.collector).resolve(strict=True);dbpath=Path(args.database).resolve(strict=True)
new=dbpath.with_name("lessons.refined.sqlite3");backup=dbpath.with_name("lessons.first-pass.sqlite3")
if new.exists() or backup.exists():raise FileExistsError("preserve prior databases")
with closing(sqlite3.connect(dbpath.resolve().as_uri()+"?mode=ro",uri=True)) as src,closing(sqlite3.connect(new)) as dst:src.backup(dst)
manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8-sig"))
def hashfile(p):
 with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def fallback(raw):
 t=raw.decode("utf-8-sig",errors="replace")
 # Known empty/translation stubs are not knowledge.
 if len(t)<1000 and STUB.search(t):return None
 header="";fence=False;front=False;best=None
 for i,line in enumerate(t.splitlines(),1):
  line=line.strip()
  if i==1 and line=="---":front=True;continue
  if front:
   if line=="---":front=False
   continue
  if line.startswith((chr(96)*3,"~~~")):fence=not fence;continue
  if fence or not line:continue
  m=SECTION.match(line)
  if m:header=m.group(1)[:120];continue
  if not 15<=len(line)<=450:continue
  v=MARK.sub("",line).replace("**","").replace("__","").strip()
  if len(v)<15 or BADLINE.search(v) or RESTRICT.search(v) or STUB.search(v):continue
  # Second pass accepts shorter procedural sentences and specific declarative relationships.
  action=bool(ACTION.search(v));rule=bool(RULE.search(v))
  relation=bool(re.search(r"\b(?:returns?|requires?|supports?|prevents?|produces?|contains?|ensures?|differs?|uses?|depends on|consists of|is used to|can be used to|means that)\b",v,re.I))
  ar=bool(re.match(r"^(?:استخدم|استخدام|تحقق|تأكد|احفظ|اختبر|قارن|تجنب|يجب|لا تستخدم|راجع|حدد|افصل|احسب|يستخدم|يتطلب)\b",v))
  if not (action or rule or relation or ar):continue
  if len(v.split())<3:continue
  score=5*action+4*rule+3*relation+5*ar+2*bool(PREFERRED.search(header))
  if score<3:continue
  if best is None or score>best[0]:best=(score,i,header,v)
 return best
with closing(sqlite3.connect(new)) as db:
 rows=db.execute("SELECT c.digest,s.archive,s.path FROM candidates c JOIN sources s ON s.digest=c.digest WHERE c.status='no_supported_candidate' ORDER BY s.archive,s.path").fetchall()
 reps={};seen=set()
 for d,a,p in rows:
  if d not in seen:reps.setdefault(a,{})[p]=d;seen.add(d)
 attempted=0;added=0
 for a,paths in reps.items():
  source=next(s for s in manifest["sources"] if s["archive"]==a);zpath=root/"sources"/a
  if hashfile(zpath)!=source["sha256"]:raise ValueError("archive digest mismatch")
  with zipfile.ZipFile(zpath) as z:
   for item in z.infolist():
    if item.filename not in paths:continue
    raw=z.read(item);d=hashlib.sha256(raw).hexdigest()
    if d!=paths[item.filename]:raise ValueError("document digest mismatch")
    q=fallback(raw);attempted+=1
    if q:
     score,line,header,v=q
     db.execute("UPDATE candidates SET status='candidate',line=?,section=?,excerpt=?,score=?,reason='secondary_short_or_declarative_candidate' WHERE digest=?",(line,header,v,score,d));added+=1
    if attempted%2000==0:db.commit();print("REFINE",attempted,"of",len(seen),"additional candidates",added,flush=True)
  if hashfile(zpath)!=source["sha256"]:raise ValueError("source changed")
  db.commit()
 if attempted!=len(seen):raise ValueError("incomplete fallback")
 r=json.loads(db.execute("SELECT v FROM meta WHERE k='receipt'").fetchone()[0])
 count=dict(db.execute("SELECT status,count(*) FROM candidates GROUP BY status"))
 r.update({"unique_candidates":count.get("candidate",0),"no_supported_candidate":count.get("no_supported_candidate",0),"secondary_attempted":attempted,"secondary_candidates":added,"method":"two-pass heuristic source-grounded passage selection, second pass short procedural/declarative sentences; unreviewed candidates, not full semantic review"})
 r["file_paths_with_candidate"]=db.execute("SELECT count(*) FROM sources s JOIN candidates c ON c.digest=s.digest WHERE c.status='candidate'").fetchone()[0]
 r["file_paths_without_candidate"]=r["documents_read"]-r["file_paths_with_candidate"]
 db.execute("UPDATE meta SET v=? WHERE k='receipt'",(json.dumps(r),));db.commit()
 if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("integrity failure")
# Switch only after successful verification; preserve first-pass database.
os.replace(dbpath,backup)
try:os.replace(new,dbpath)
except Exception:os.replace(backup,dbpath);raise
(dbpath.parent/"receipt.json").write_text(json.dumps(r,indent=2),encoding="utf-8")
print("REFINED_COMPLETE",json.dumps(r),flush=True)
