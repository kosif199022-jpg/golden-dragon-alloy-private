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
def search_v67_baseline(query,limit=8,path=DB,feature=None):
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
# V69: conservative term equivalences, grouped rather than flattening every
# synonym into an unrestricted OR. Phrases are kept as FTS phrase queries.
SYNONYM_GROUPS=(
 ("montage","video editing","editing","مونتاج","تحرير الفيديو"),
 ("frame","frames","frame rate","fps","اطار","اطارات","فريم","فريمات"),
 ("timing","timestamp","timestamps","timecode","توقيت","تزامن"),
 ("transition","transitions","crossfade","انتقال","انتقالات"),
 ("caption","captions","subtitle","subtitles","كابتشن","ترجمة","ترجمات"),
 ("audio","sound","voice","صوت","الصوت"),
 ("loudness","lufs","volume normalization","جهارة","مستوى الصوت"),
 ("render","rendering","export","رندر","تصدير"),
 ("accounting","bookkeeping","محاسبة","المحاسبة"),
 ("reconciliation","reconcile","مطابقة","تسوية","المطابقة"),
 ("bank","bank statement","بنك","البنك","بنكي"),
 ("inventory","stock","warehouse","مخزون","المخزون","مستودع"),
 ("payroll","salary","salaries","رواتب","الرواتب","اجور"),
 ("trial balance","ledger balance","ميزان المراجعة","ميزان"),
 ("audit","auditing","مراجعة","تدقيق"),
 ("design","تصميم","التصميم"),
 ("typography","font","fonts","typeface","خطوط","خط","الخطوط"),
 ("layout","composition","تخطيط","تنسيق","تكوين"),
 ("accessibility","a11y","اتاحة","امكانية الوصول"),
 ("color","colour","palette","الوان","الالوان","لون"),
 ("programming","coding","software","code","برمجة","البرمجة","كود"),
 ("testing","test","tests","اختبار","اختبارات"),
 ("debugging","debug","troubleshooting","تصحيح","اخطاء","استكشاف الاخطاء"),
 ("database","databases","sql","قاعدة بيانات","قواعد بيانات"),
 ("performance","optimization","profiling","اداء","تحسين الاداء"),
 ("cache","caching","ذاكرة مؤقتة","تخزين مؤقت"),
)
def normal(s):
 import unicodedata
 s="".join(c for c in unicodedata.normalize("NFKD",s.casefold()) if not unicodedata.combining(c))
 s=s.translate(str.maketrans("أإآىةـ","ااايه "))
 return " ".join(re.findall(r"[^\W_]+",s,re.UNICODE))
ALIASES={normal(a):tuple(dict.fromkeys(group)) for group in SYNONYM_GROUPS for a in group}
STOP=set(("how","to","the","a","an","in","for","with","and","or","of","what","is","can","using","use","best","كيف","هل","ما","في","من","عن","علي","مع","و","اي","افضل","عمل","طريقه"))
def concepts(query):
 if not isinstance(query,str) or not query.strip() or len(query)>500:raise ValueError("invalid query")
 raw=normal(query).split();out=[];i=0;seen=set()
 while i<len(raw) and len(out)<12:
  chosen=None
  for n in range(min(3,len(raw)-i),0,-1):
   phrase=" ".join(raw[i:i+n])
   if phrase in ALIASES:
    chosen=(phrase,n,ALIASES[phrase]);break
   if n==1 and phrase.startswith("ال") and phrase[2:] in ALIASES:
    chosen=(phrase,n,ALIASES[phrase[2:]]);break
  if chosen:
   term,n,variants=chosen;i+=n
  else:
   term=raw[i];i+=1
   if term in STOP or not 2<=len(term)<=40:continue
   variants=(term,)
  key=tuple(sorted(set(normal(x) for x in variants)))
  if key in seen:continue
  seen.add(key);out.append((term,tuple(dict.fromkeys((term,*variants)))))
 return out
def _quote(x):
 # Only bounded word/phrase tokens produced by concepts; no user FTS syntax.
 return '"'+x.replace('"','""')+'"'
def _contains(hay,term):
 return " "+normal(term)+" " in " "+hay+" "
def search(query,limit=8,path=DB,feature=None):
 if type(limit)!=int or not 1<=limit<=30:raise ValueError("limit")
 groups=concepts(query)
 if feature is not None and not re.fullmatch(r"[a-z]{2,30}",feature):raise ValueError("invalid feature")
 if not groups or not Path(path).is_file():return {"index_ready":Path(path).is_file(),"matches":[]}
 clauses=["("+" OR ".join(_quote(x) for x in v)+")" for _,v in groups]
 pool={}
 # Take candidates from title/path first, as well as full-content queries.
 # This avoids a long excerpt crowding out a named tool before reranking.
 with closing(ro(path)) as db:
  for expr in ("path : ("+" OR ".join(clauses)+")"," AND ".join(clauses)," OR ".join(clauses)):
   if feature:expr="("+expr+") AND tags : "+_quote(feature)
   rows=db.execute("SELECT digest,archive,path,section,excerpt,bm25(search,0,0,12,5,1,0.3) FROM search WHERE search MATCH ? ORDER BY bm25(search,0,0,12,5,1,0.3),digest LIMIT ?",(expr,max(60,limit*12))).fetchall()
   for d,a,p,section,excerpt,score in rows:
    if d not in pool or score<pool[d][-1]:pool[d]=(d,a,p,section,excerpt,score)
 def rank(row):
  d,a,p,section,excerpt,bm=row
  pn,sn,en=normal(p),normal(section or ""),normal(excerpt or "")
  def hit(h,v):return any(_contains(h,x) for x in v)
  exact=sum(_contains(pn,t) for t,_ in groups)
  title=sum(hit(pn,v) for _,v in groups)
  section_hits=sum(hit(sn,v) for _,v in groups)
  coverage=sum(hit(pn,v) or hit(sn,v) or hit(en,v) for _,v in groups)
  # A path/title match for a named tool or concept outranks incidental body matches.
  return (-title,-exact,-coverage,-section_hits,bm,d)
 rows=sorted(pool.values(),key=rank)[:limit]
 return {"index_ready":True,"matches":[{"sha256":d,"archive":a,"path":p,"rank":i+1,"status":"unreviewed_reference","instruction_authority":False} for i,(d,a,p,sec,ex,score) in enumerate(rows)],"execution_allowed":False,"ranking":"V69 bilingual concept groups + path/title-weighted lexical ranking; relevance not guaranteed"}
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
