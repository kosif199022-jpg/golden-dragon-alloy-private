"""Query the portable reference by task or capability ID, without invoking its contents."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

ENTRY = re.compile(r"^- (\S+) \[([^\]]+)\] (.*)")
WORDS = re.compile(r"[^\W_]+", re.UNICODE)
ALIASES = {"جرد":"inventory stock reconciliation", "مونتاج":"video editing timeline",
           "فيديو":"video render", "ترجمة":"subtitle caption", "مخزون":"inventory stock",
           "تحريك":"animation motion", "تقرير":"report", "حسابات":"accounting finance"}
STOP = set("the and with for from to a of in on في من مع على".split())


def tokens(text):
    return set(WORDS.findall(text.casefold())) - STOP


def search(reference, task, limit):
    terms=tokens(task)
    for term in tuple(terms):
        arabic=term.removeprefix("ال")
        terms.update(ALIASES.get(arabic, "").split())
    rows=[]
    counts=Counter()
    for line in reference.splitlines():
        entry=ENTRY.match(line)
        if entry:
            ident,state,summary=entry.groups()
            words=tokens(ident+" "+summary)
            counts.update(words & terms)
            rows.append((ident,state,summary,words))
    if not rows:
        raise ValueError("Empty capability reference")
    matches=[]
    for ident,state,summary,words in rows:
        overlap=words & terms
        if overlap:
            weight=sum(math.log1p(len(rows)/counts[w]) for w in overlap)
            exact=task.casefold().strip()==ident.casefold()
            matches.append((exact,weight,ident,state,summary))
    matches.sort(key=lambda x:(not x[0],-x[1],x[2]))
    return {"entries_considered":len(rows),"matching_entries":len(matches),"references":[
        {"id":ident,"catalog_status":state,"method":summary}
        for _,_,ident,state,summary in matches[:limit]]}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task")
    parser.add_argument("--limit", type=int, choices=range(1,51), default=8)
    args=parser.parse_args()
    ref=Path(__file__).resolve().parent.parent/"references"/"combined.md"
    print(json.dumps(search(ref.read_text(encoding="utf-8-sig"),args.task,args.limit),ensure_ascii=False))
