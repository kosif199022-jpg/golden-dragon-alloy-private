"""Read-only Golden Dragon source reconstruction inventory. No MCP required.
Usage: python forge/unified_core/audit_tree.py apps/golden-dragon --out audit.json
"""
from __future__ import annotations
import argparse, ast, hashlib, json, re
from collections import Counter, defaultdict
from pathlib import Path

IGNORED={".git","node_modules","__pycache__",".venv","venv","dist","build"}
KINDS={".py":"python",".js":"javascript",".mjs":"javascript",".ts":"typescript",
".tsx":"typescript",".jsx":"javascript",".ps1":"powershell",".sh":"shell",
".md":"documentation",".json":"data",".yaml":"data",".yml":"data",
".html":"interface",".css":"interface",".exe":"binary",".dll":"binary"}
def inventory(root):
    files=[]; hashes=defaultdict(list); imports=Counter(); errors=[]
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(s in IGNORED for s in p.relative_to(root).parts):continue
        rel=p.relative_to(root).as_posix()
        try:
            data=p.read_bytes(); digest=hashlib.sha256(data).hexdigest()
            item={"path":rel,"bytes":len(data),"sha256":digest,"kind":KINDS.get(p.suffix.lower(),"other")}
            hashes[digest].append(rel)
            if p.suffix==".py" and len(data)<2_000_000:
                try:
                    tree=ast.parse(data.decode("utf-8-sig"))
                    item["functions"]=[n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
                    item["classes"]=[n.name for n in ast.walk(tree) if isinstance(n,ast.ClassDef)]
                    for n in ast.walk(tree):
                        if isinstance(n,ast.Import):
                            imports.update(x.name.split(".")[0] for x in n.names)
                        if isinstance(n,ast.ImportFrom) and n.module:
                            imports.update([n.module.split(".")[0]])
                except (SyntaxError,UnicodeError) as e:item["parse_error"]=str(e)
            files.append(item)
        except (OSError,PermissionError) as e:errors.append({"path":rel,"error":str(e)})
    return {"root":str(root),"files":files,"summary":{"file_count":len(files),
      "bytes":sum(f["bytes"] for f in files),"kinds":dict(Counter(f["kind"] for f in files)),
      "exact_duplicate_groups":[v for v in hashes.values() if len(v)>1],
      "top_python_imports":imports.most_common(40),"read_errors":errors},
      "verification":{"static_inventory":True,"execution_tests_run":False,
      "all_capabilities_working":"not established"}}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("root",type=Path)
    ap.add_argument("--out",type=Path,default=Path("golden-dragon-audit.json"))
    args=ap.parse_args()
    if not args.root.is_dir():ap.error("Root directory missing")
    report=inventory(args.root.resolve())
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report["summary"],ensure_ascii=False,indent=2))
if __name__=="__main__":main()
