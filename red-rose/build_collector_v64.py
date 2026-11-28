from pathlib import Path
import zipfile,json,hashlib,sqlite3,collections,re,time,sys,argparse
parser=argparse.ArgumentParser(description="Build local collector content-feature index")
parser.add_argument("collector");parser.add_argument("--output-dir",default=str(Path.home()/".red-rose"/"deep-skills-v64"));parser.add_argument("--approve-write",action="store_true");args=parser.parse_args()
if not args.approve_write:parser.error("--approve-write required")
base=Path(args.collector).resolve(strict=True);out=Path(args.output_dir).resolve();out.mkdir(parents=True,exist_ok=True)
target=out/"corpus.sqlite3";tmp=out/"corpus.building"
if target.exists() or tmp.exists():raise FileExistsError("existing index")
manifest=json.loads((base/"manifest.json").read_text(encoding="utf-8-sig"))
features={
"reasoning":"hypothesis|hypotheses|causal|root cause|inference|counterexample|assumption|critical thinking",
"evidence":"verification|verify|evidence|provenance|citation|ground truth",
"planning":"dependency|dependencies|decomposition|critical path|milestone|acceptance criteria|work breakdown",
"decision":"decision matrix|tradeoff|trade off|reversibility|expected value|sensitivity analysis",
"risk":"risk register|failure mode|premortem|pre mortem|mitigation|rollback|contingency",
"learning":"feedback loop|lessons learned|retrospective|postmortem|self correction|reflection",
"testing":"regression test|property based|invariant|test driven|edge case|reproduction",
"media":"video|ffmpeg|animation|keyframe|storyboard|caption|remotion|compositing|cinematic",
"finance":"accounting|ledger|reconciliation|audit|ifrs|financial statement|cash flow|valuation",
"data":"sql|data analysis|statistics|visualization|database|etl|data pipeline",
"software":"software|api|python|javascript|typescript|architecture|debugging|code review",
"design":"ux|ui design|typography|graphic design|accessibility|layout|design system",
"research":"research|literature review|scientific method|experiment|systematic review",
"business":"market research|strategy|sales|marketing|product management|customer|operations",
"security":"threat model|least privilege|sandbox|access control|security|validation",
"performance":"benchmark|profiling|latency|bottleneck|throughput",
"communication":"communication|technical writing|translation|documentation|presentation",
"automation":"automation|workflow|orchestration|scheduling|integration",
"education":"learning objectives|curriculum|teaching|instructional design",
"engineering":"engineering|simulation|mechanical|electrical|mathematics|physics"}
sep=re.compile(r"[-_/]+")
terms={k:v.split("|") for k,v in features.items()}
db=sqlite3.connect(tmp);db.execute("CREATE TABLE docs(archive TEXT,path TEXT,digest TEXT,words INTEGER,tags TEXT,license_label TEXT,PRIMARY KEY(archive,path))");db.execute("CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT)")
seen={};counts=collections.Counter();per=[];skipped=[];wordcount=0
def hashfile(p):
 with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def analyze(b):
 d=hashlib.sha256(b).hexdigest()
 if d in seen:return d,seen[d]
 try:t=b.decode("utf-8-sig")
 except UnicodeError:t=b.decode("utf-8",errors="replace")
 norm=sep.sub(" ",t.lower());tags={k:sum(norm.count(term) for term in a) for k,a in terms.items()};tags={k:v for k,v in tags.items() if v}
 m=re.search(r"(?im)^license:\s*([^\r\n]{1,80})",t)
 data=(len(t.split()),tags,m.group(1) if m else None);seen[d]=data
 return d,data
for source in manifest["sources"]:
 name=source["archive"]
 if not isinstance(name,str) or Path(name).name!=name or not name.endswith(".zip"):raise ValueError("invalid archive name")
 p=base/"sources"/name
 if hashfile(p)!=source["sha256"]:raise ValueError("archive digest mismatch")
 n=0;found=0
 with zipfile.ZipFile(p) as z:
  docs=[x for x in z.infolist() if not x.is_dir() and (x.filename.lower().endswith("/skill.md") or x.filename.lower()=="skill.md")]
  # The corpus may store individual text skills in a different directory/filename convention.
  if len(docs)!=source["recognized_skill_files"]:
   with (base/"index.csv").open(encoding="utf-8-sig",newline="") as f:
    import csv
    names={r["skill_file"] for r in csv.DictReader(f) if r["archive"]==name}
   docs=[x for x in z.infolist() if x.filename in names and not x.is_dir()]
  found=len(docs)
  if found!=source["recognized_skill_files"]:raise ValueError("manifest count mismatch")
  for i,x in enumerate(docs,1):
   try:
    if x.file_size>2*1024**2 or x.flag_bits&1:raise ValueError("size/encryption")
    b=z.read(x);d,(wc,tags,lic)=analyze(b)
    db.execute("INSERT INTO docs VALUES(?,?,?,?,?,?)",(name,x.filename,d,wc,json.dumps(tags),lic))
    n+=1;wordcount+=wc
   except (ValueError,RuntimeError,zipfile.BadZipFile,sqlite3.IntegrityError) as e:skipped.append({"archive":name,"path":x.filename,"reason":type(e).__name__})
   if i%5000==0:print("SCAN",name,i,found,flush=True);db.commit()
 if hashfile(p)!=source["sha256"]:raise ValueError("archive changed")
 per.append({"archive":name,"sha256":source["sha256"],"declared":source["recognized_skill_files"],"read":n})
 print("ARCHIVE_COMPLETE",name,n,flush=True)
for wc,tags,lic in seen.values():counts.update(tags.keys())
db.execute("CREATE INDEX digest_index ON docs(digest)")
r={"collections":per,"total_declared":sum(x["declared"] for x in per),"read":sum(x["read"] for x in per),"unique_byte_hashes":len(seen),"words_scanned_including_duplicates":wordcount,"unique_docs_by_overlapping_feature":dict(counts),"skipped":skipped,"method":"full text lexical analysis, byte-level deduplication, replacement decoding for invalid UTF-8; not semantic reading or code execution","executed_sources":False}
db.execute("INSERT INTO meta VALUES('receipt',?)",(json.dumps(r),));db.commit()
if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("index integrity failure")
db.close();tmp.rename(target);(out/"receipt.json").write_text(json.dumps(r,indent=2),encoding="utf-8")
print("COLLECTION_COMPLETE",json.dumps({k:v for k,v in r.items() if k!="skipped"}),flush=True)
