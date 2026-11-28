"""V67: ranked local knowledge retrieval, checked source context, adoption contract.
Source text is untrusted data; none of these commands execute source instructions.
"""
from pathlib import Path
from contextlib import closing
import sqlite3,json,re,hashlib,zipfile,collections,os
HOME=Path.home()/".red-rose"
BASE=HOME/"distilled-v66"/"lessons.sqlite3"
DB=HOME/"knowledge-v67"/"search.sqlite3"
COLLECTOR=Path.home()/"OneDrive/Desktop/Claude_Skills_Collector"
def sha(p):
 with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def ro(p):return sqlite3.connect(Path(p).resolve(strict=True).as_uri()+"?mode=ro",uri=True,timeout=5)
def build(base=BASE,dest=DB,approved=False):
 if not approved:raise PermissionError("explicit write approval required")
 base=Path(base).resolve(strict=True);dest=Path(dest).resolve();tmp=dest.with_suffix(".building")
 if dest.exists() or tmp.exists():raise FileExistsError("preserve prior index")
 dest.parent.mkdir(parents=True,exist_ok=True);source_sha=sha(base)
 with closing(ro(base)) as src,closing(sqlite3.connect(tmp)) as db:
  db.execute("CREATE VIRTUAL TABLE search USING fts5(digest UNINDEXED,archive UNINDEXED,path,section,excerpt,tags,tokenize='unicode61 remove_diacritics 2')")
  db.execute("CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT)")
  # Aggregate duplicate paths in deterministic order; one row per unique content.
  sql="""SELECT c.digest,s.archive,s.path,c.section,c.excerpt,s.tags FROM candidates c JOIN sources s ON c.digest=s.digest WHERE c.status='candidate' ORDER BY c.digest,s.archive,s.path"""
  seen=set();batch=[]
  for d,a,p,section,excerpt,tags in src.execute(sql):
   if d in seen:continue
   seen.add(d)
   batch.append((d,a,p,section,excerpt," ".join(json.loads(tags).keys())))
   if len(batch)>=2000:db.executemany("INSERT INTO search VALUES(?,?,?,?,?,?)",batch);batch.clear()
  if batch:db.executemany("INSERT INTO search VALUES(?,?,?,?,?,?)",batch)
  if sha(base)!=source_sha:raise ValueError("source database changed")
  expected=src.execute("SELECT count(*) FROM candidates WHERE status='candidate'").fetchone()[0]
  if len(seen)!=expected:raise ValueError("coverage mismatch")
  r={"indexed_unique_candidates":len(seen),"source_db_sha256":source_sha,"method":"FTS5 BM25 lexical retrieval; not semantic validation","execution_allowed":False}
  db.execute("INSERT INTO meta VALUES('receipt',?)",(json.dumps(r),));db.commit()
  if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("database integrity")
 tmp.rename(dest);return r
def terms(q):
 if not isinstance(q,str) or not q.strip() or len(q)>500:raise ValueError("invalid query")
 return list(dict.fromkeys(re.findall(r"[^\W_]{2,40}",q.casefold())))[:12]
def search(query,limit=8,path=DB,feature=None):
 if type(limit)!=int or not 1<=limit<=30:raise ValueError("limit")
 tok=terms(query)
 if not tok or not Path(path).is_file():return {"index_ready":Path(path).is_file(),"matches":[]}
 if feature is not None and not re.fullmatch(r"[a-z]{2,30}",feature):raise ValueError("invalid feature")
 rows=[];seen=set()
 with closing(ro(path)) as db:
  for op in (" AND "," OR "):
   match=op.join('"'+x+'"' for x in tok)
   if feature:match="("+match+") AND tags : "+'"'+feature+'"'
   found=db.execute("SELECT digest,archive,path,bm25(search,0,0,4,2,1,0.3) FROM search WHERE search MATCH ? ORDER BY bm25(search,0,0,4,2,1,0.3),digest LIMIT ?",(match,limit)).fetchall()
   for item in found:
    if item[0] not in seen:rows.append(item);seen.add(item[0])
    if len(rows)>=limit:break
   if len(rows)>=limit or len(tok)==1:break
 return {"index_ready":True,"matches":[{"sha256":d,"archive":a,"path":p,"rank":i+1,"status":"unreviewed_reference","instruction_authority":False} for i,(d,a,p,score) in enumerate(rows)],"execution_allowed":False,"ranking":"lexical; relevance not guaranteed"}
def inspect(source_digest,collector=COLLECTOR,base=BASE):
 if not isinstance(source_digest,str) or not re.fullmatch(r"[0-9a-f]{64}",source_digest):raise ValueError("invalid digest")
 root=Path(collector).resolve(strict=True)
 with closing(ro(base)) as db:
  row=db.execute("SELECT s.archive,s.path,c.line,c.status FROM sources s JOIN candidates c ON s.digest=c.digest WHERE s.digest=? ORDER BY s.archive,s.path LIMIT 1",(source_digest,)).fetchone()
 if not row:raise ValueError("unknown source")
 a,p,line,status=row
 if Path(a).name!=a:raise ValueError("invalid archive locator")
 manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8-sig"));entry=next((x for x in manifest["sources"] if x["archive"]==a),None)
 zp=(root/"sources"/a).resolve(strict=True)
 if not zp.is_relative_to(root) or not entry or sha(zp)!=entry["sha256"]:raise ValueError("archive provenance mismatch")
 with zipfile.ZipFile(zp) as z:
  item=z.getinfo(p)
  if item.file_size>2*1024**2 or item.flag_bits&1:raise ValueError("source bounds")
  raw=z.read(item)
 if hashlib.sha256(raw).hexdigest()!=source_digest:raise ValueError("source bytes changed")
 lines=raw.decode("utf-8-sig",errors="replace").splitlines()
 # Bounded source text stays behind explicit review, not automatically in a plan.
 start=max(0,(line or 1)-7);end=min(len(lines),(line or 1)+6)
 return {"archive":a,"path":p,"sha256":source_digest,"candidate_status":status,"line":line,"start_line":start+1,"end_line":end,"source_context":[{"line":i+1,"text":lines[i][:500]} for i in range(start,end)],"source_verified":True,"semantic_verified":False,"instruction_authority":False}
def adoption(j):
 # Prepare a review contract; do not promote or write a lesson. Reference and review are different states.
 required=("source_sha256","problem","mechanism","preconditions","implementation","acceptance","counterexample","rights")
 for k in required:
  if not isinstance(j.get(k),str) or not j[k].strip() or len(j[k])>2000:raise ValueError("missing or invalid "+k)
 if not re.fullmatch(r"[0-9a-f]{64}",j["source_sha256"]):raise ValueError("invalid digest")
 if j["rights"] not in ("independent_implementation","license_verified","unknown"):raise ValueError("rights status")
 blockers=[]
 for k in ("source_context_reviewed","existing_capability_checked","test_plan_reviewed"):
  if j.get(k) is not True:blockers.append(k)
 if j["rights"]=="unknown":blockers.append("rights_unresolved")
 return {"status":"ready_for_human_review" if not blockers else "review_required","blockers":blockers,"source_sha256":j["source_sha256"],"next":"Run independent tests, then record evidence with evolution; approval is separate.","semantic_verified":False,"execution_allowed":False,"promoted":False}
def context(request,depth=2,path=DB):
 if depth<2:return {"enabled":False,"matches":[]}
 from rose_distill_v66 import ROUTES
 q=request.casefold()
 routes=[(f,k) for f,k,words in ROUTES if any(x in q for x in words)][:3]
 if not routes:return {"enabled":True,"matches":[]}
 out=[];seen=set()
 try:
  for f,k in routes:
   for x in search(k,limit=3,path=path,feature=f)["matches"]:
    if x["sha256"] not in seen:out.append(x);seen.add(x["sha256"])
  return {"enabled":True,"index_ready":Path(path).is_file(),"matches":out[:6],"instruction_authority":False,"execution_allowed":False}
 except (ValueError,OSError,sqlite3.Error):return {"enabled":True,"matches":[],"reason":"knowledge index unavailable"}
def handle(a):
 try:
  if a.action=="build":r=build(approved=a.approve_write)
  elif a.action=="search":r=search(a.source,a.limit,feature=a.feature)
  elif a.action=="inspect":r=inspect(a.source)
  else:
   p=Path(a.source)
   if p.stat().st_size>128*1024:raise ValueError("input size")
   r=adoption(json.loads(p.read_text(encoding="utf-8")))
  print(json.dumps(r,ensure_ascii=False));return 0
 except (ValueError,OSError,KeyError,TypeError,sqlite3.Error,zipfile.BadZipFile) as e:print(json.dumps({"error":str(e)[:300]}));return 1
def register(sub):
 p=sub.add_parser("knowledge",help="ranked candidate retrieval and adoption review")
 p.add_argument("action",choices=["build","search","inspect","adopt"]);p.add_argument("source",nargs="?",default="");p.add_argument("--limit",type=int,default=8);p.add_argument("--feature");p.add_argument("--approve-write",action="store_true");p.set_defaults(ext_func=handle)
if __name__=="__main__":
 import argparse
 parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest="command",required=True);register(sub);a=parser.parse_args();raise SystemExit(a.ext_func(a))
