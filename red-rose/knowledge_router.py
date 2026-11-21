"""Evidence-only task routing over migrated descriptions.

This is deterministic information retrieval, not autonomous AI or execution.
"""
import re
import sqlite3
from alloy_fusion import init
STOP = {'about','with','from','this','that','some','will','have','make','find','using',
        'عايز','عايزة','اعمل','اعملي','التنين','الوردة','الحمراء','عندي','عشان','المهارة','فيها','اللي','ممكن','محتاج','محتاجين','على','الى','إلى'}

def route(db: sqlite3.Connection, task: str, limit: int = 6) -> dict:
    init(db)
    if not isinstance(task,str) or not task.strip():
        raise ValueError('nonempty task required')
    tokens=[]
    for token in re.findall(r'[\w\u0600-\u06FF]{3,}', task.casefold()):
        if token not in STOP and token not in tokens:
            tokens.append(token)
    tokens=tokens[:12]
    matches=[]
    if tokens:
        clauses=' OR '.join('(title LIKE ? OR summary LIKE ?)' for _ in tokens)
        args=[x for tok in tokens for x in ('%'+tok+'%', '%'+tok+'%')]
        rows=db.execute('SELECT id,kind,title,summary,origin,license,status FROM fused_knowledge WHERE '+clauses+' LIMIT 2000',args).fetchall()
        for ident, kind, title, summary, origin, license_id, status in rows:
            titlelow=title.casefold(); summarylow=summary.casefold()
            score=4*sum(tok in titlelow for tok in tokens)+sum(tok in summarylow for tok in tokens)
            if kind in ('road','rule','thinking','lesson'):score+=2
            matches.append((score,ident,kind,title,origin,license_id,status))
    matches.sort(key=lambda r:(-r[0],r[1]))
    refs=[{'id':r[1],'kind':r[2],'title':r[3],'origin':r[4],
           'license':r[5],'status':r[6], 'score':r[0]}
          for r in matches[:max(1,min(int(limit),20))]]
    return {'task':task,'status':'reference_retrieved_not_executed',
            'keywords':tokens,'matched_candidates':len(matches),'references':refs,
            'next_steps':['inspect source rules and license','select implementation approach',
                          'implement independently','execute tests','record evidence']}
