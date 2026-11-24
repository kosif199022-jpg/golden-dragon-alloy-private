#!/usr/bin/env python3
"""Offline read-only impact navigator for Graphify NetworkX node-link graph.json."""
import argparse,collections,json,sys
from pathlib import Path

def norm(s):return str(s or '').replace('\\','/').lstrip('./').casefold()

def scan(data,path,max_depth=2):
    if not isinstance(data,dict) or not isinstance(data.get('nodes'),list): raise ValueError('Unsupported node-link graph')
    edges=data.get('links',data.get('edges'))
    if not isinstance(edges,list):raise ValueError('Expected links/edges')
    if len(data['nodes'])>150000 or len(edges)>500000:raise ValueError('Graph exceeds safe in-memory limits')
    nodes={str(n['id']):n for n in data['nodes'] if isinstance(n,dict) and 'id' in n}
    target=norm(path)
    matches={nid for nid,n in nodes.items() if norm(n.get('source_file'))==target or norm(n.get('source_file')).endswith('/'+target)}
    near=collections.defaultdict(list); skipped=0
    for e in edges:
        if not isinstance(e,dict):skipped+=1;continue
        a,b=str(e.get('source')),str(e.get('target'))
        if a not in nodes or b not in nodes:skipped+=1;continue
        conf=str(e.get('confidence','UNKNOWN')).upper()
        if conf not in {'EXTRACTED','INFERRED','AMBIGUOUS'}:conf='UNKNOWN'
        rel=str(e.get('relation','relates'))
        near[a].append((b,rel,conf,'outgoing'));near[b].append((a,rel,conf,'incoming'))
    seen={x:0 for x in matches};q=collections.deque(matches);links=[]
    while q:
        n=q.popleft();d=seen[n]
        if d>=max_depth:continue
        for neighbor,rel,conf,direction in near[n]:
            if len(links)<20000:links.append({'source':n,'neighbor':neighbor,'relation':rel,'confidence':conf,'direction':direction})
            if neighbor not in seen:seen[neighbor]=d+1;q.append(neighbor)
    overview=[]
    for nid,d in sorted(seen.items(),key=lambda v:(v[1],v[0]))[:1000]:
        node=nodes[nid];overview.append({'id':nid,'label':str(node.get('label',''))[:200], 'source_file':str(node.get('source_file',''))[:500], 'distance':d})
    return {'status':'REVIEW_REQUIRED' if matches else 'NO_MATCH', 'requested_file':path,'match_count':len(matches),
            'graph_nodes':len(nodes),'graph_edges':len(edges),'skipped_invalid_edges':skipped,
            'hop_limit':max_depth,'reachable_nodes':len(seen),'nodes':overview,'observed_links':links[:1000],
            'truncated':len(seen)>1000 or len(links)>1000,
            'warning':'Potential relationships only; graph gaps, inferred edges, cross-file symbols and runtime paths require independent tests.'}

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--graph',type=Path,required=True);p.add_argument('--changed',required=True);p.add_argument('--depth',type=int,choices=[1,2,3],default=2)
    a=p.parse_args(argv)
    if not a.graph.is_file() or a.graph.stat().st_size>25*1024*1024:p.error('graph missing or exceeds 25 MiB')
    try:o=scan(json.loads(a.graph.read_text(encoding='utf-8')),a.changed,a.depth)
    except (ValueError,KeyError,UnicodeError) as e:p.error(str(e))
    print(json.dumps(o,ensure_ascii=False,indent=2));return 0 if o['match_count'] else 2
if __name__=='__main__':sys.exit(main())
