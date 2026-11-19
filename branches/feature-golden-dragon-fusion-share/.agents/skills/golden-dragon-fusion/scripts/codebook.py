"""Build a local HTML codebook from Git sources and catalog-linked Python files."""
import argparse
import ast
import hashlib
from html import escape
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tokenize
from collections import Counter, defaultdict


def link(path, label):
    return '<a href="'+escape(path.as_uri(),quote=True)+'">'+escape(label)+'</a>'


def build(repo, target):
    units=json.loads((repo/"apps/golden-dragon/app/fusion/index.json").read_text(encoding="utf-8-sig"))["units"]
    tracked=subprocess.check_output(["git","-C",str(repo),"ls-files","-z","--","*.py"]).decode().split("\0")
    files={repo/name for name in tracked if name}
    owners=defaultdict(set)
    linked=defaultdict(list)
    excluded={".git",".venv","venv","__pycache__","node_modules",".tox","site-packages"}
    for unit in units:
        raw=unit.get("path")
        if not raw:
            continue
        path=Path(raw)
        if path.is_file() and path.suffix.lower()==".py":
            candidates=[path]
        elif unit["kind"]=="skill" and path.is_file():
            candidates=[]
            for parent,dirs,names in os.walk(path.parent):
                dirs[:]=[d for d in dirs if d not in excluded and not (Path(parent)/d).is_junction() and not (Path(parent)/d).is_symlink()]
                candidates.extend(Path(parent)/n for n in names if n.endswith(".py"))
        else:
            continue
        for candidate in candidates:
            files.add(candidate)
            owners[candidate].add(unit["id"])
            linked[unit["id"]].append(candidate)
    anchors={p:"module-"+str(i) for i,p in enumerate(sorted(files))}
    duplicates=defaultdict(list)
    stats=Counter()
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",dir=target.parent,encoding="utf-8",suffix=".html",delete=False) as f:
        f.write('<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>Golden Dragon | كتاب الكود</title><style>body{font:18px system-ui;margin:2rem auto;max-width:1050px;padding:1rem;background:#faf8f3;color:#232526}details{padding:.45em;border-bottom:1px solid #ddd}a{color:#185993}code{direction:ltr;unicode-bidi:isolate}li{margin:.3em}</style><h1>التنين الذهبي — كتاب الكود</h1><p>فهرس محلي لملفات بايثون. افتح اسم الملف لقراءة المصدر الأصلي. تطابق بصمة الدالة يحدد مرشحًا للمراجعة قبل الدمج.</p><nav><a href="#catalog">القدرات</a> · <a href="#modules">ملفات الكود</a> · <a href="#duplicates">التكرار</a></nav><h2 id="catalog">القدرات</h2>')
        for u in units:
            uid=u["id"]
            f.write('<details><summary>'+escape(uid)+' ('+str(len(linked[uid]))+')</summary>')
            f.write(escape(str(u.get("what_ar") or u.get("what") or "")))
            if u.get("path") and Path(u["path"]).exists():
                f.write(' '+link(Path(u["path"]).resolve(),"المصدر المسجّل"))
            for p in sorted(linked[uid]):
                f.write('<div><a href="#'+anchors[p]+'">'+escape(p.name)+'</a></div>')
            if not linked[uid]:
                f.write('<p>لم يثبت ارتباط مباشر بملف بايثون في هذا المسح.</p>')
            f.write('</details>')
        f.write('<h2 id="modules">ملفات الكود</h2>')
        for p in sorted(files):
            title=p.relative_to(repo).as_posix() if p.is_relative_to(repo) else p.as_posix()
            f.write('<details id="'+anchors[p]+'"><summary dir="ltr">'+escape(title)+'</summary>'+link(p,"افتح الكود الأصلي"))
            try:
                with tokenize.open(p) as source:
                    tree=ast.parse(source.read(),filename=p.name)
            except (ValueError,OSError,SyntaxError,UnicodeError,RecursionError) as err:
                stats["unparsed"]+=1
                f.write('<p>'+escape(type(err).__name__)+'</p></details>')
                continue
            stats["parsed"]+=1
            deps=set()
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    deps.update(a.name for a in node.names)
                elif isinstance(node,ast.ImportFrom):
                    deps.add("."*node.level+(node.module or ""))
            f.write('<p>الاستيرادات: <code>'+escape(", ".join(sorted(deps)))+'</code></p>')
            for node in tree.body:
                if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                    continue
                stats["definitions"]+=1
                f.write('<div><code>'+escape(node.name)+'</code> · '+str(node.lineno)+'–'+str(node.end_lineno)+'</div>')
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.end_lineno-node.lineno>=4:
                    digest=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
                    duplicates[digest].append((p,node.name,node.lineno))
            f.write('</details>')
        groups=[group for group in duplicates.values() if len({p for p,_,_ in group})>1]
        f.write('<h2 id="duplicates">دوال متطابقة بنيويًا في أكثر من ملف</h2>')
        for group in sorted(groups,key=len,reverse=True):
            f.write('<details><summary><code>'+escape(group[0][1])+'</code> × '+str(len(group))+'</summary>')
            for p,name,line in group:
                f.write('<div><a href="#'+anchors[p]+'">'+escape(p.name)+' · '+str(line)+'</a></div>')
            f.write('</details>')
        stats.update(entries=len(units),files=len(files),linked_entries=sum(bool(v) for v in linked.values()),duplicate_groups=len(groups))
        f.write('<p dir="ltr">'+escape(json.dumps(stats))+'</p></html>')
    Path(f.name).replace(target)
    return stats


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo",type=Path)
    ap.add_argument("output",type=Path)
    args=ap.parse_args()
    print(json.dumps(build(args.repo.resolve(),args.output.resolve())))
