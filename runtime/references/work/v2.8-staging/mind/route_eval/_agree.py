import json
a={x["fid"]:x for x in json.load(open("labels_fresh.json",encoding="utf-8"))}
b={x["fid"]:x for x in json.load(open("labels_fresh_b.json",encoding="utf-8"))}
ids=[i for i in a if a[i]["best"]!="skip" and b.get(i,{}).get("best")!="skip"]
ex=sum(a[i]["best"]==b[i]["best"] for i in ids)
soft=sum(a[i]["best"] in {b[i]["best"],*b[i].get("ok",[])} or b[i]["best"] in {a[i]["best"],*a[i].get("ok",[])} for i in ids)
print(f"both-labeled={len(ids)} exact agreement={ex/len(ids):.0%} soft agreement={soft/len(ids):.0%}")
# consensus: best from A; acceptable = A.ok + B.best + B.ok
out=[]
for i in sorted(a):
    x=dict(a[i]); y=b.get(i,{})
    if x["best"]=="skip" or y.get("best")=="skip":
        x["best"]="skip" if x["best"]=="skip" else x["best"]
    ok=set(x.get("ok",[]))|({y.get("best")} if y.get("best") not in (None,"skip") else set())|set(o for o in y.get("ok",[]) if o!="skip")
    ok.discard(x["best"]); x["ok"]=sorted(ok); x["agree"]=x["best"]==y.get("best")
    out.append(x)
json.dump(out,open("labels_fresh_consensus.json","w",encoding="utf-8"),ensure_ascii=False,indent=0)
dis=[(i,a[i]["best"],b[i]["best"]) for i in ids if a[i]["best"]!=b[i]["best"]]
from collections import Counter
print("top disagreements:",Counter((x,y) for _,x,y in dis).most_common(8))
