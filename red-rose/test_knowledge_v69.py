"""Public synthetic fixture, 32 manually labelled bilingual queries. No owner DB."""
import tempfile, unittest, sqlite3, hashlib, json
from pathlib import Path
from rose_knowledge_v67 import build,search,search_v67_baseline
# Each topic's three independent short references describe the specified task.
# Negatives deliberately share terms in other contexts, not irrelevant lorem ipsum.
TOPICS=[
 ("media","ffmpeg frame timing","توقيت الاطارات ffmpeg",[
 ("ffmpeg-frame-timing","Video timeline","Preserve presentation timestamps at the export frame rate."),
 ("ffmpeg-pts-inspection","Timestamp checks","Probe decoded frame timestamps and compare against target fps."),
 ("ffmpeg-frame-timecode","Frame accurate editing","Compute cut boundaries in integer frames before encoding.")]),
 ("media","video transition crossfade","انتقالات المونتاج",[
 ("video-transition-design","Crossfade","Account for overlap in a video editing timeline."),
 ("montage-crossfade","Editing transitions","Blend the outgoing and incoming clips over measured frames."),
 ("video-editing-transitions","Cut design","Plan crossfade transitions before render.")]),
 ("media","audio loudness normalization","ضبط جهارة الصوت",[
 ("audio-loudness","LUFS measurement","Measure final integrated loudness and peak after export."),
 ("sound-volume-normalization","Audio finishing","Normalize loudness once and verify true peak."),
 ("audio-lufs-delivery","Sound quality","Use an integrated loudness target and measure the encoded result.")]),
 ("media","caption subtitle timing","توقيت الكابتشن",[
 ("caption-timing","Speech alignment","Bind subtitle starts and ends to word timestamps."),
 ("subtitle-timecode","Caption editing","Verify caption timecode and display durations."),
 ("captions-word-timestamps","Word alignment","Use measured words for each subtitle.")]),
 ("finance","bank reconciliation","مطابقة البنك",[
 ("bank-reconciliation","Reconciliation","Compare bank statement transactions with ledger entries."),
 ("bank-statement-reconcile","Bank control","Record unmatched cash movements and residuals."),
 ("bank-reconcile-review","Bank matching","Verify opening and closing balances after matching.")]),
 ("finance","inventory accounting","محاسبة المخزون",[
 ("inventory-accounting","Stock valuation","Compare counted quantities and stock ledger values."),
 ("warehouse-stock-accounting","Inventory control","Reconcile warehouse stock valuation against ledger."),
 ("inventory-bookkeeping","Inventory ledger","Record authorized adjustments and retain inventory evidence.")]),
 ("finance","payroll accounting","محاسبة الرواتب",[
 ("payroll-accounting","Salary controls","Reconcile payroll totals with bank payments."),
 ("salary-bookkeeping","Payroll journal","Account for salary deductions and gross pay."),
 ("payroll-ledger-accounting","Payroll review","Verify wages and employer liabilities before posting.")]),
 ("finance","trial balance audit","مراجعة ميزان المراجعة",[
 ("trial-balance-audit","Ledger review","Check equal debits and credits and suspicious balances."),
 ("ledger-balance-auditing","Trial balance","Compare ledger balance to supporting schedules."),
 ("trial-balance-review","Audit evidence","Investigate trial balance variances and obtain evidence.")]),
 ("design","typography design","تصميم الخطوط",[
 ("typography-design","Type hierarchy","Use measured font sizes and line spacing."),
 ("font-design","Typography","Check typeface consistency and text legibility."),
 ("design-typeface-system","Font system","Define a coherent type scale and baseline.")]),
 ("design","layout design","تصميم التخطيط",[
 ("layout-design","Grid composition","Design layout with consistent alignment and spacing."),
 ("design-composition","Visual layout","Group related content using a layout grid."),
 ("design-layout-grid","Composition","Use a responsive grid to maintain composition.")]),
 ("design","accessibility design","تصميم امكانية الوصول",[
 ("accessibility-design","Accessible interface","Check keyboard focus and contrast."),
 ("design-a11y","Accessibility","Design for accessible controls and clear labels."),
 ("design-accessibility-review","Accessibility review","Verify semantics, focus order and minimum contrast.")]),
 ("design","color palette design","تصميم الالوان",[
 ("color-palette-design","Color system","Design a restrained color palette."),
 ("colour-design","Color roles","Assign palette roles and check contrast."),
 ("design-color-tokens","Palette","Use design tokens to ensure consistent colors.")]),
 ("software","programming testing","اختبارات البرمجة",[
 ("programming-testing","Code verification","Write regression tests before changing behavior."),
 ("code-tests","Software testing","Test boundary cases and invariants."),
 ("software-test-design","Testing","Create deterministic fixtures for code tests.")]),
 ("software","debugging programming","تصحيح اخطاء البرمجة",[
 ("programming-debugging","Root cause","Reproduce the code failure and isolate its boundary."),
 ("code-debug","Debugging","Verify a hypothesis with a controlled experiment."),
 ("software-troubleshooting","Programming diagnosis","Locate the failing stage before applying a fix.")]),
 ("software","database sql","قاعدة بيانات sql",[
 ("database-sql","SQL schema","Design database constraints and transactions."),
 ("sql-database-query","Database query","Use parameterized SQL queries and indexes."),
 ("database-sql-migrations","SQL migration","Test schema migrations on a clean database.")]),
 ("software","performance cache","تحسين الاداء ذاكرة مؤقتة",[
 ("performance-cache","Caching","Measure cache hit rate and latency."),
 ("cache-optimization","Performance profiling","Invalidate cached data when inputs change."),
 ("performance-caching","Optimization","Benchmark cached and uncached paths with equal inputs.")]),
]
NEGATIVES=[
 ("media","video-reader","Video utility","A video reader may show ffmpeg frame timing, audio loudness normalization, subtitle timing and video transition crossfade while reading metadata."),
 ("media","cloudflare-browser","Browser utility","Examples include ffmpeg frame timing, audio loudness normalization, caption subtitle timing and transition crossfade when scraping pages."),
 ("finance","business-dashboard","Dashboard display","Show bank reconciliation, inventory accounting, payroll accounting and trial balance audit labels in a dashboard."),
 ("design","marketing-brief","Campaign","Mention typography design, layout design, accessibility design and color palette design in the creative brief."),
 ("software","project-summary","Release notes","Mention programming testing, debugging programming, database sql and performance cache in a release summary."),
]
def fixture(root):
 base=root/"fixture.sqlite3";idx=root/"search.sqlite3"
 with sqlite3.connect(base) as db:
  db.execute("CREATE TABLE candidates(digest,status,line,section,excerpt)")
  db.execute("CREATE TABLE sources(digest,archive,path,tags)")
  docs=[(f,*d) for f,_,_,ds in TOPICS for d in ds]+NEGATIVES
  for feature,name,section,excerpt in docs:
   d=hashlib.sha256(name.encode()).hexdigest()
   db.execute("INSERT INTO candidates VALUES(?,?,?,?,?)",(d,"candidate",1,section,excerpt))
   db.execute("INSERT INTO sources VALUES(?,?,?,?)",(d,"fixture.zip",name+"/SKILL.md",json.dumps({feature:1})))
 db.close()
 build(base,idx,True)
 return idx
def evaluate(idx):
 cases=[]
 for feature,en,ar,docs in TOPICS:
  expected={d[0]+"/SKILL.md" for d in docs}
  for q in (en,ar):
   a=search_v67_baseline(q,3,idx,feature)["matches"];b=search(q,3,idx,feature)["matches"]
   before=[x["path"] for x in a];after=[x["path"] for x in b]
   cases.append({"question":q,"feature":feature,"expected":sorted(expected),"before":before,"after":after,"before_hits":len(set(before)&expected),"after_hits":len(set(after)&expected)})
 n=len(cases)
 return {"fixture":"synthetic labelled; not representative production-corpus benchmark","questions":n,"denominator":3*n,"before_hits":sum(x["before_hits"] for x in cases),"after_hits":sum(x["after_hits"] for x in cases),"precision_at_3_before":sum(x["before_hits"] for x in cases)/(3*n),"precision_at_3_after":sum(x["after_hits"] for x in cases)/(3*n),"cases":cases}
class Knowledge69(unittest.TestCase):
 def test_fixture_precision(self):
  with tempfile.TemporaryDirectory() as d:
   result=evaluate(fixture(Path(d)))
   self.assertGreaterEqual(result["questions"],30);self.assertGreater(result["precision_at_3_after"],result["precision_at_3_before"])
   self.assertGreaterEqual(result["precision_at_3_after"],.80)
   first=result["cases"][0];self.assertIn(first["after"][0],first["expected"])
 def test_injection_no_raw_syntax(self):
  with tempfile.TemporaryDirectory() as d:
   idx=fixture(Path(d));self.assertEqual(search('" OR *',path=idx)["matches"],[])
if __name__=="__main__":
 import sys
 if "--report" in sys.argv:
  with tempfile.TemporaryDirectory() as d:print(json.dumps(evaluate(fixture(Path(d))),ensure_ascii=False,indent=2))
 else:unittest.main()
