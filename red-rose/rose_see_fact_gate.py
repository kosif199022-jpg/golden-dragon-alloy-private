#!/usr/bin/env python3
"""Conservative local rewrite anchor checker; read-only, stdlib, no network."""
import argparse,json,re,sys,unicodedata
from collections import Counter
from pathlib import Path

ARABIC_DIGITS=str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹','01234567890123456789')
EMAIL=re.compile(r'(?<![\w.-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])')
URL=re.compile(r'https?://[^\s<>"\')]+',re.I)
NUMBER=re.compile(r'(?<!\w)\d+(?:[.,،٫٬]\d+)*(?:\s?[%٪])?(?!\w)')
VERSION=re.compile(r'\bv\d+(?:\.\d+){1,4}\b',re.I)

def extract(text):
    s=unicodedata.normalize('NFKC',text).translate(ARABIC_DIGITS)
    all_items=[]
    for kind,reg in [('email',EMAIL),('url',URL),('version',VERSION)]:
        for m in reg.finditer(s):all_items.append((kind,m.group().strip('.,؛،.')))
        s=reg.sub(' ',s)
    for m in NUMBER.finditer(s):
        t=m.group().strip().replace('،',',').replace('٫','.').replace('٬',',').replace('٪','%').replace(' ','')
        all_items.append(('number',t))
    return Counter(all_items)

def compare(before,after):
    a,b=extract(before),extract(after)
    return {'dropped':[{'kind':k,'value':v,'count':n} for (k,v),n in sorted((a-b).items())],
            'added':[{'kind':k,'value':v,'count':n} for (k,v),n in sorted((b-a).items())],
            'unchanged_anchor_count':sum((a&b).values()),'status':'PASS' if a==b else 'REVIEW_REQUIRED',
            'disclaimer':'Anchor check only; does not prove meaning, names or citations were preserved.'}

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True)
    args=p.parse_args(argv)
    for name,path in [('before',args.before),('after',args.after)]:
        if not path.is_file() or path.stat().st_size>5*1024*1024:p.error(f'{name}: file missing or too large')
    out=compare(args.before.read_text(encoding='utf-8'),args.after.read_text(encoding='utf-8'))
    print(json.dumps(out,ensure_ascii=False,indent=2));return 0 if out['status']=='PASS' else 2
if __name__=='__main__':sys.exit(main())
