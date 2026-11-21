"""Evidence-only route over the independently migrated Alloy descriptions."""
import re
import sqlite3
from pathlib import Path
from contextlib import closing
from fuse_alloy_v10 import setup
STOP={'about','with','from','this','that','some','will','have','make','find','using',
      'عايز','عايزة','اعمل','اعملي','التنين','الوردة','الحمراء','عندي','عشان','المهارة','فيها','اللي','ممكن','محتاج','محتاجين','على','الى','إلى'}
def route(db:sqlite3.Connection,task:str,limit:int=6):
    setup(db)
    if not isinstance(task,str) or not task.strip():raise ValueError('nonempty task required')
    tokens=[]
    for word in re.findall(r'[\w\u0600-\u06FF]{3,}',task.casefold()):
        if word not in STOP and word not in tokens:tokens.append(word)
    tokens=tokens[:12]
    refs=[]
    if tokens:
        cond=' OR '.join('(title LIKE ? OR summary LIKE ?)' for _ in tokens)
        args=[part for word in tokens for part in ('%'+word+'%','%'+word+'%')]
        rows=db.execute('SELECT id,kind,title,summary,origin,license,status FROM fused_knowledge WHERE '+cond+' LIMIT 2000',args).fetchall()
        for r in rows:
            ident,kind,title,summary,origin,license_id,status=r
            titlelow=title.casefold();summarylow=summary.casefold()
            score=4*sum(t in titlelow for t in tokens)+sum(t in summarylow for t in tokens)
            if kind in ('road','rule','thinking','lesson'):score+=2
            refs.append((score,ident,kind,title,origin,license_id,status))
    refs.sort(key=lambda r:(-r[0],r[1]))
    return {'task':task,'status':'reference_retrieved_not_executed','keywords':tokens,
            'matched_candidates':len(refs),
            'references':[{'id':r[1],'kind':r[2],'title':r[3],'origin':r[4],
                'license':r[5],'status':r[6],'score':r[0]}
                for r in refs[:max(1,min(int(limit),20))]],
            'next_steps':['inspect references and licenses','implement new capability','test','record evidence']}
if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('task')
    p.add_argument('--db',default=str(Path.home()/'.red-rose'/'memory.sqlite3'))
    a=p.parse_args()
    with closing(sqlite3.connect(Path(a.db).expanduser())) as db:
        print(json.dumps(route(db,a.task),ensure_ascii=False,indent=2))
