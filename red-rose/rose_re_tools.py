"""Local authorized analysis toolbox: capability registry and file-type routing.
No process attachment, network interception, target execution, or installs.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path.home()/"re-tools"
SOURCES=ROOT/"sources"/"registry.json"
TOOLS={
"diec":("die","static"),"die":("die","gui"),"capa":("capa","static"),"floss":("floss","static"),
"yara":("yara","static"),"yr":("yara-x","static"),"upx":("upx","manual"),
"pe-sieve":("pe-sieve","runtime"),"ilspycmd":("ilspy","static"),"ILSpy":("ilspy","gui"),
"pyinstxtractor-ng":("pyinstxtractor-ng","manual"),"pydisasm":("xdis","static"),
"rizin":("rizin","static"),"rz-bin":("rizin","static"),"rz-diff":("rizin","static"),
"analyzeHeadless":("ghidra","static"),"jadx":("jadx","static"),"apktool":("apktool","static"),
"adb":("adb","runtime"),"apkleaks":("apkleaks","manual"),"androguard":("androguard","static"),
"frida":("frida","runtime"),"frida-ps":("frida-tools","runtime"),"frida-trace":("frida-tools","runtime"),
"tshark":("wireshark","offline_capture"),"mitmdump":("mitmproxy","runtime"),"webcrack":("webcrack","static"),
"wasm2wat":("wabt","static"),"wasm-objdump":("wabt","static"),"olevba":("oletools","static"),
"x64dbg":("x64dbg","gui"),"imhex":("imhex","gui"),"rea":("rea","manual")}
LIBS={"lief":"lief","capstone":"capstone","unicorn":"unicorn","pefile":"pefile","dnfile":"dnfile",
      "androguard":"androguard","oletools":"oletools","elftools":"pyelftools"}
GROUPS={
"pe":["diec","capa","floss","yara","yr","rz-bin","rizin","analyzeHeadless","ilspycmd","pyinstxtractor-ng","upx","rea"],
"elf":["diec","capa","floss","yara","yr","rz-bin","rizin","analyzeHeadless","rea"],
"apk":["jadx","apktool","androguard","apkleaks","rea"],
"wasm":["wasm-objdump","wasm2wat","rizin"],"python":["pydisasm","rea"],
"javascript":["webcrack","rea"],"office":["olevba","yara","yr"],
"pcap":["tshark"],"unknown":["diec","yara","yr"],
"media":["ffprobe"],"vn":["vn-dua-analyze"]}
ALIASES={"die":["die.exe","die64.exe"],"x64dbg":["x64dbg.exe","x32dbg.exe"],
         "yara":["yara64.exe","yara32.exe"],"pe-sieve":["pe-sieve64.exe","pe-sieve32.exe"],
         "analyzeHeadless":["analyzeHeadless.bat"],"jadx":["jadx.bat","jadx.exe"],
         "ILSpy":["ILSpy.exe"]}
def source_rows():
    try:return {r["name"]:r for r in json.loads(SOURCES.read_text(encoding="utf-8"))}
    except (OSError,ValueError,KeyError,TypeError):return {}
def locate():
    # Discover only configured tool directory, never traverse source clones or case evidence.
    by_name={}
    for dirpath,dirs,files in os.walk(ROOT):
        rel=Path(dirpath).relative_to(ROOT)
        dirs[:]=[x for x in dirs if x.casefold() not in {"sources","cases","_downloads",".git","node_modules","__pycache__"}]
        if len(rel.parts)>=6:dirs[:]=[]
        for f in files:
            if f.lower().endswith((".exe",".bat",".cmd",".ps1")):
                by_name.setdefault(f.casefold(),str(Path(dirpath)/f))
    return by_name
def status():
    src=source_rows(); paths=locate(); rows=[]
    python_env=ROOT/"pylibs"/"venv"/"Scripts"/"python.exe"
    isolated={}
    if python_env.is_file():
        try:
            code="import importlib.util as u,json,sys; print(json.dumps({n:bool(u.find_spec(n)) for n in sys.argv[1:]}))"
            result=subprocess.run([str(python_env),"-I","-c",code,*LIBS],capture_output=True,text=True,timeout=8,check=True)
            isolated=json.loads(result.stdout)
        except (OSError,ValueError,subprocess.SubprocessError):
            pass
    for name,(repo,kind) in TOOLS.items():
        executable=shutil.which(name)
        if name=="webcrack" and not executable:
            node_cli=ROOT/"webcrack"/"node_modules"/".bin"/"webcrack.cmd"
            if node_cli.is_file():executable=str(node_cli)
        if not executable:
            # Match basename only from the tool's own folder when case-sensitive aliases overlap.
            for f in ALIASES.get(name,[])+[name+".exe",name+".cmd",name+".bat",name+".ps1"]:
                candidate=paths.get(f.casefold())
                if candidate:
                    executable=candidate;break
        row={"name":name,"kind":kind,"source":repo,"source_status":src.get(repo,{}).get("status","not_verified"),
             "source_path":src.get(repo,{}).get("path"),"executable":executable,
             "status":"located_not_tested" if executable else "runtime_not_found"}
        rows.append(row)
    for name,repo in LIBS.items():
        try:available=importlib.util.find_spec(name) is not None
        except (ImportError,ValueError):available=False
        use_isolated=not available and isolated.get(name,False)
        available=available or use_isolated
        rows.append({"name":name,"kind":"python_library","python":str(python_env) if use_isolated else sys.executable if available else None,"source":repo,"source_status":src.get(repo,{}).get("status","not_verified"),
                     "source_path":src.get(repo,{}).get("path"),"status":"module_discoverable" if available else "module_not_found"})
    return {"ok":True,"tools":rows,"source_count":sum(r.get("status")=="cloned" for r in src.values()),
            "source_registry":str(SOURCES),"note":"Located is not a successful runtime test; source clone is not installation."}
def kind(path):
    with path.open("rb") as f:head=f.read(16)
    ext=path.suffix.casefold()
    if head.startswith(b"MZ"):return "pe"
    if head.startswith(b"\x7fELF"):return "elf"
    if head.startswith(b"\x00asm"):return "wasm"
    if ext==".apk":return "apk"
    if ext==".vn":return "vn"
    if ext in {".mp4",".mov",".mkv",".wav",".mp3",".m4a"}:return "media"
    if ext in {".pcap",".pcapng"}:return "pcap"
    if ext in {".doc",".docm",".xls",".xlsm",".ppt",".pptm",".docx",".xlsx",".pptx"}:return "office"
    if ext in {".js",".mjs",".cjs"}:return "javascript"
    if ext==".pyc":return "python"
    return "unknown"
def plan(path,mode="smart"):
    p=Path(path)
    if not p.is_file():raise ValueError("File not found")
    typ=kind(p); names=GROUPS[typ]
    if mode=="turbo":names=names[:1]
    elif mode=="smart":names=names[:4]
    rows={r["name"]:r for r in status()["tools"]}
    return {"ok":True,"type":typ,"mode":mode,"bytes":p.stat().st_size,
            "suggested":[rows.get(n,{"name":n,"status":"native_or_external"}) for n in names],
            "executed":False,"note":"Static planning only. GUI/runtime/network interception and unpacking require separate explicit approval."}
def handle(args):
    try:
        if args.action=="status":result=status()
        else:
            if not args.file:raise ValueError("plan requires a file")
            result=plan(args.file,args.mode)
    except (OSError,ValueError) as e:
        result={"ok":False,"error":str(e)}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["ok"] else 1
def register(subparsers):
    p=subparsers.add_parser("re-tools",help="discover local analysis tools and route authorized files")
    p.add_argument("action",choices=["status","plan"])
    p.add_argument("file",nargs="?")
    p.add_argument("--mode",choices=["turbo","smart","deep"],default="smart")
    p.set_defaults(ext_func=handle)
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();s=p.add_subparsers(required=True);register(s)
    raise SystemExit(handle(p.parse_args(["re-tools",*sys.argv[1:]])))
