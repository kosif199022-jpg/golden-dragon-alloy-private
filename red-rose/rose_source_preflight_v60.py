"""Static source preflight. No target execution, installation, network, extraction or secret scanning."""
from __future__ import annotations
import hashlib, importlib.util, json, os, re, stat, subprocess, sys, zipfile
from pathlib import Path

MAX_BYTES=2*1024**3
MAX_MEMBERS=20000
MAX_UNPACKED=4*1024**3
MAX_MANIFEST=4*1024**2
APK_MEMBER=re.compile(r"classes(?:[0-9]+)?\.dex$")
PACKAGE=re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
EXPECT={"apk","zip","office","pe","elf","wasm","mp4","matroska","wav","png","jpeg","unknown"}
def sha256(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def zip_inventory(p):
    names=set();roots=set();total=0;issues=set();dex=0;libs=0;manifest=False;manifest_count=0;office=False
    with zipfile.ZipFile(p) as z:
        infos=z.infolist()
        if len(infos)>MAX_MEMBERS:raise ValueError("archive member limit")
        for x in infos:
            name=x.filename.replace("\\","/");parts=name.rstrip("/").split("/")
            key="/".join(q.rstrip(". ").casefold() for q in parts)
            if (not key or name.startswith("/") or any(not q or q in (".","..") or ":" in q or q.rstrip(". ")!=q or any(ord(c)<32 for c in q) for q in parts)):
                issues.add("unsafe_member_name")
            if key in names:issues.add("duplicate_normalized_member")
            names.add(key)
            if stat.S_ISLNK(x.external_attr>>16):issues.add("symlink_member")
            if x.flag_bits&1:issues.add("encrypted_member")
            total+=x.file_size
            if x.file_size>MAX_BYTES or total>MAX_UNPACKED:issues.add("expansion_limit")
            if x.file_size>1024**2 and x.file_size/max(1,x.compress_size)>2000:issues.add("extreme_compression")
            if len(parts)==1 and APK_MEMBER.fullmatch(name):dex+=1
            if name=="AndroidManifest.xml":
                manifest=True;manifest_count+=1
                if x.file_size>MAX_MANIFEST:issues.add("manifest_size_limit")
            if len(parts)==3 and parts[0]=="lib" and name.endswith(".so"):libs+=1
            if name=="[Content_Types].xml":office=True
            if parts[0] in ("word","xl","ppt"):roots.add(parts[0])
        kind="apk" if manifest and dex else "office" if office and roots else "zip"
        return {"kind":kind,"entries":len(infos),"uncompressed_bytes":total,"dex_count":dex,"native_library_count":libs,"manifest_present":manifest,"manifest_count":manifest_count,"archive_issues":sorted(issues),"content_integrity_verified":False}

def header_kind(h):
    if h.startswith(b"MZ"):return "pe"
    if h.startswith(b"\x7fELF"):return "elf"
    if h.startswith(b"\0asm"):return "wasm"
    if h.startswith(b"\x89PNG\r\n\x1a\n"):return "png"
    if h.startswith(b"\xff\xd8\xff"):return "jpeg"
    if h[:4]==b"RIFF" and h[8:12]==b"WAVE":return "wav"
    if h[4:8]==b"ftyp":return "mp4"
    if h.startswith(b"\x1a\x45\xdf\xa3"):return "matroska"
    return "unknown"

# Use a fixed local parser for Android binary XML only; no decompiled code is executed.
_AXML = r"""
import json,sys,zipfile
from loguru import logger
logger.remove()
from androguard.core.axml import AXMLPrinter
with zipfile.ZipFile(sys.argv[1]) as z:
    i=z.getinfo('AndroidManifest.xml')
    if i.file_size>4194304:raise ValueError('manifest limit')
    a=AXMLPrinter(z.read(i))
    if not a.is_valid():raise ValueError('invalid binary manifest')
    root=a.get_xml_obj()
    if root.tag!='manifest':raise ValueError('not manifest')
    print(json.dumps({'package':root.get('package'),'version_name':root.get('{http://schemas.android.com/apk/res/android}versionName'),'version_code':root.get('{http://schemas.android.com/apk/res/android}versionCode')}))
"""
def apk_identity(p):
    isolated=Path.home()/"re-tools"/"pylibs"/"venv"/"Scripts"/"python.exe"
    py=str(isolated) if isolated.is_file() else sys.executable if importlib.util.find_spec("androguard") else None
    if not py:return {"status":"parser_unavailable"}
    try:
        r=subprocess.run([py,"-I","-c",_AXML,str(p)],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=30)
        if r.returncode:return {"status":"parser_failed"}
        d=json.loads(r.stdout)
        if not isinstance(d.get("package"),str) or not PACKAGE.fullmatch(d["package"]):return {"status":"invalid_package"}
        for k in ("version_name","version_code"):
            if d.get(k) is not None and (not isinstance(d[k],str) or len(d[k])>80):return {"status":"invalid_version"}
        return {"status":"parsed_manifest",**d}
    except (OSError,ValueError,subprocess.SubprocessError):return {"status":"parser_failed"}

def inspect(path,expected_kind=None,expected_package=None,expected_sha256=None):
    p=Path(path).resolve(strict=True)
    if not p.is_file() or not 0<p.stat().st_size<=MAX_BYTES:raise ValueError("bounded regular file required")
    if expected_kind is not None and expected_kind not in EXPECT:raise ValueError("unsupported expected kind")
    if expected_package is not None and not PACKAGE.fullmatch(expected_package):raise ValueError("invalid expected package")
    if expected_sha256 is not None and not re.fullmatch("[0-9a-f]{64}",expected_sha256):raise ValueError("invalid expected digest")
    digest=sha256(p)
    with p.open("rb") as f:h=f.read(32)
    z=None;app=None;issues=[];kind=header_kind(h)
    if h.startswith((b"PK\x03\x04",b"PK\x05\x06",b"PK\x07\x08")):
        try:z=zip_inventory(p);kind=z["kind"];issues.extend(z["archive_issues"])
        except (ValueError,zipfile.BadZipFile,NotImplementedError):kind="zip";issues.append("archive_inventory_failed")
    extension={".apk":"apk",".zip":"zip",".docx":"office",".xlsx":"office",".pptx":"office",".exe":"pe",".dll":"pe",".so":"elf",".wasm":"wasm",".mp4":"mp4",".mov":"mp4",".mkv":"matroska",".webm":"matroska",".wav":"wav",".png":"png",".jpg":"jpeg",".jpeg":"jpeg"}.get(p.suffix.lower())
    if extension and extension!=kind:issues.append("extension_content_mismatch")
    if expected_kind and expected_kind!=kind:issues.append("expected_kind_mismatch")
    if expected_sha256 and digest!=expected_sha256:issues.append("expected_digest_mismatch")
    if kind=="apk" and z and z["manifest_count"]==1 and not set(z["archive_issues"])-{"duplicate_normalized_member"}:
        app=apk_identity(p)
        if app["status"]!="parsed_manifest":issues.append("apk_identity_unresolved")
    if expected_package and (not app or app.get("package")!=expected_package):issues.append("expected_package_mismatch_or_unverified")
    if sha256(p)!=digest:issues.append("source_changed_during_inspection")
    # Header recognition alone is not a successful decode or signature validation.
    return {"sha256":digest,"bytes":p.stat().st_size,"kind":kind,"archive":z,"apk":app,"issues":sorted(set(issues)),"disposition":"blocked" if issues else "identity_candidate" if kind!="unknown" else "unresolved","authenticity_verified":False,"safe_to_execute":False,"signature_verified":False,"content_integrity_verified":False,"target_executed":False,"network_used":False}

def compare(receipts,expected_sha256):
    """Check explicit independent evidence records, not correctness of the underlying claims."""
    if not isinstance(receipts,list) or not 2<=len(receipts)<=16 or not re.fullmatch("[0-9a-f]{64}",expected_sha256):raise ValueError("invalid evidence set")
    families=set();values=set();unresolved=0;digests=set()
    for r in receipts:
        if set(r)!={"method_family","status","value","input_sha256","evidence_sha256"}:raise ValueError("invalid record")
        if r["input_sha256"]!=expected_sha256 or not re.fullmatch("[0-9a-f]{64}",r["evidence_sha256"]):raise ValueError("unbound evidence")
        if r["status"] not in ("observed","failed","partial","not_tested"):raise ValueError("invalid evidence status")
        fam=r["method_family"];val=r["value"]
        if not isinstance(fam,str) or not re.fullmatch("[a-z0-9_-]{1,64}",fam):raise ValueError("invalid method family")
        if r["status"]!="observed":unresolved+=1;continue
        if not isinstance(val,str) or not 1<=len(val)<=128:raise ValueError("invalid observed value")
        families.add(fam);digests.add(r["evidence_sha256"]);values.add(val)
    agreement=len(families)>=2 and len(digests)>=2 and len(values)==1
    return {"receipt_agreement":agreement,"distinct_method_labels":len(families),"distinct_evidence_digests":len(digests),"conflict":len(values)>1,"unresolved":unresolved,"semantic_verified":False,"evidence_files_verified":False,"independence_verified":False,"decision":"review_required" if not agreement or unresolved else "corroboration_candidate"}

def handle(a):
    try:
        if a.action=="inspect":d=inspect(a.source,a.expect_kind,a.expect_package,a.expect_sha256);rc=0 if d["disposition"]=="identity_candidate" else 2
        else:
            p=Path(a.source)
            if p.stat().st_size>128*1024:raise ValueError("receipt limit")
            d=compare(json.loads(p.read_text(encoding="utf-8")),a.expect_sha256 or "");rc=0 if d["decision"]=="corroboration_candidate" else 2
        print(json.dumps(d,ensure_ascii=False,allow_nan=False));return rc
    except (OSError,ValueError,TypeError,KeyError,RuntimeError,subprocess.SubprocessError) as e:print(json.dumps({"ok":False,"error":type(e).__name__,"detail":str(e)[:160]}));return 1
def register(sub):
    p=sub.add_parser("source-preflight",help="static source identity and evidence preflight")
    p.add_argument("action",choices=["inspect","compare"]);p.add_argument("source")
    p.add_argument("--expect-kind");p.add_argument("--expect-package");p.add_argument("--expect-sha256");p.set_defaults(ext_func=handle)
