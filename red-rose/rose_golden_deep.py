"""Evidence-backed Golden Dragon capability profile; read-only native search."""
from pathlib import Path
import json,argparse,sys
PROFILE=Path(__file__).resolve().with_name("GOLDEN_DRAGON_DEEP_PROFILE.json")
def load():
    return json.loads(PROFILE.read_text(encoding="utf-8"))
def search(query):
    terms=query.casefold().split()
    return [r for r in load()["recipes"] if all(t in (r["id"]+" "+r["title_ar"]+" "+" ".join(r.get("distilled_steps_ar",[]))).casefold() for t in terms)]
def handle(args):
    doc=load()
    if args.action=="status":
        result={k:doc[k] for k in ("source_binary_sha256","source_format","counts","library_readiness","notes")}
    elif args.action=="find":
        if not args.query.strip():return 2
        result={"matches":search(args.query),"executed":False}
    else:
        r=next(x for x in doc["recipes"] if x["id"]=="lyrics-film")
        result={"source_recipe":r,"rose_workflow":[
            {"stage":"authoritative_text","action":"Provide verified prayer or Quran text; do not use speech recognition as the authoritative source."},
            {"stage":"word_alignment","action":"Align verified text against supplied narration; inspect sync."},
            {"stage":"footage","action":"Use local dua_owner library after reviewing chosen clips.","library":"dua_owner"},
            {"stage":"render","action":"Use existing dua-reel plan and render engine; keep Arabic shaping correct.","command":"python rose.py dua-reel PLAN.json OUTPUT.mp4 --approve-write"},
            {"stage":"qa","action":"Decode and visually review final output; verify text and timing.","command":"python rose.py verify OUTPUT.mp4"}
        ],"executed":False,"note":"Plan, not generated video; commands require real inputs and approval."}
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0
def register(subparsers):
    p=subparsers.add_parser("golden-deep",help="read extracted Golden Dragon capability evidence")
    p.add_argument("action",choices=["status","find","dua-plan"])
    p.add_argument("query",nargs="?",default="")
    p.set_defaults(ext_func=handle)
if __name__=="__main__":
    p=argparse.ArgumentParser();s=p.add_subparsers(required=True);register(s)
    raise SystemExit(handle(p.parse_args(["golden-deep",*sys.argv[1:]])))
