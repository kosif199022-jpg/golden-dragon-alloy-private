"""Native Golden Dragon workflow distillation. No GoldenDragon runtime dependency."""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path

def _number(v,low,high):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:
        raise ValueError("number out of bounds")
    return v

def _keys(p, required, optional=()):
    if not isinstance(p,dict) or set(required)-p.keys() or p.keys()-set(required)-set(optional):
        raise ValueError("invalid or missing parameters; required: "+", ".join(required))

def _file(name):
    p=Path(name).expanduser().resolve()
    if not p.is_file():raise FileNotFoundError(p)
    return p

def _output(name):
    p=Path(name).expanduser().resolve()
    if p.exists():raise FileExistsError(p)
    return p

def preflight(p):
    """Validate text and timeline; select real distinct footage using native Rose engine."""
    import dua_reel_v34 as d
    _keys(p,("lines",),("library","seed","transition","exclude"))
    lines=p["lines"]
    if not isinstance(lines,list) or not 1<=len(lines)<=30:raise ValueError("1..30 lines required")
    for ln in lines:
        text=ln if isinstance(ln,str) else ln.get("text") if isinstance(ln,dict) else None
        if not isinstance(text,str) or not text.strip() or len(text)>300:raise ValueError("invalid line")
        if isinstance(ln,dict):
            _keys(ln,("text",),("t0","t1"))
            if ("t0" in ln)!=("t1" in ln):raise ValueError("both timing boundaries required")
            for k in ("t0","t1"):
                if k in ln:_number(ln[k],0,300)
    if p.get("transition","fade") not in ("fade","spin"):raise ValueError("unknown transition")
    seed=p.get("seed",1)
    if isinstance(seed,bool) or not isinstance(seed,int):raise ValueError("invalid seed")
    exclude=p.get("exclude",[])
    if not isinstance(exclude,list) or not all(isinstance(x,str) for x in exclude):raise ValueError("invalid exclusions")
    timed=d.timed_lines(lines)
    lens,starts,total=(d.shot_plan_cut(timed) if p.get("transition")=="spin" else d.shot_plan(timed))
    _number(total,0.1,300)
    folder=d.resolve_library(p.get("library","dua_owner"))
    clips=d.choose_clips(lens,folder,seed,exclude)
    return {"ok":True,"lines":timed,"clips":clips,"shot_lengths":lens,"offsets":starts,"duration":total,
            "timing":"supplied_or_estimated_reading_pace","visual_review_required":True,
            "note":"Text source and exact selected intervals must be reviewed before publication."}

def render_dua(p,approve):
    import dua_reel_v34 as d
    import verify_media as v
    _keys(p,("plan","output"),("storyboard_only",))
    if not isinstance(p["plan"],dict):raise ValueError("plan object required")
    plan=dict(p["plan"])
    allowed=("lines","library","seed","transition","exclude","audio","style","fonts","fixed")
    if plan.keys()-set(allowed):raise ValueError("unsupported plan fields")
    shot=p.get("storyboard_only",False)
    if not isinstance(shot,bool):raise ValueError("storyboard_only must be boolean")
    out=_output(p["output"])
    if out.suffix.lower()!=".mp4":raise ValueError("output must be mp4")
    work=out.parent/(out.stem+"_golden_work")
    if work.exists():raise FileExistsError(work)
    if not approve:return {"ok":False,"outcome":"approval_required","would_write":[str(out),str(work)]}
    selected=preflight({k:plan[k] for k in ("lines","library","seed","transition","exclude") if k in plan})
    plan["lines"]=selected["lines"]
    plan["clips"]=selected["clips"]
    if plan.get("audio"):plan["audio"]=str(_file(plan["audio"]))
    result=d.build(plan,out,work=work,approve_write=True,storyboard_only=shot)
    if not result.get("ok"):return result
    if not shot:
        result["independent_qa"]=v.verify_video(out,expected_fps=d.FPS,width=d.W,height=d.H,expected_audio=True)
        result["visual_review_required"]=True
    return result

def execute(op,p,approve=False):
    if op in NATIVE:
        from importlib import import_module
        module, function = NATIVE[op]
        if not isinstance(p,dict):raise ValueError("object required")
        return getattr(import_module(module),function)(**p)
    if op=="dua-preflight":return preflight(p)
    if op=="dua-render":return render_dua(p,approve)
    if op=="word-sync":
        from speech_sync_v31 import run
        _keys(p,("script","words"),("fps",))
        return run(_file(p["script"]),_file(p["words"]),fps=int(_number(p.get("fps",30),1,120)))
    if op=="video-qa":
        from verify_media import verify_video
        _keys(p,("video",),("expected_fps","width","height","expected_audio"))
        return verify_video(_file(p["video"]),**{k:v for k,v in p.items() if k!="video"})
    if op=="scene-cuts":
        from scene_edit_v16 import analyze_cuts
        _keys(p,("source",),("threshold","sample_fps","min_shot_seconds"))
        kw={k:p[k] for k in ("threshold","sample_fps","min_shot_seconds") if k in p}
        return analyze_cuts(str(_file(p["source"])),**kw)
    if op=="audio-loudness":
        from audio_v25 import loudness
        _keys(p,("source",),())
        return loudness(source=str(_file(p["source"])))
    if op=="audio-normalize":
        from audio_v25 import loudness_normalise
        _keys(p,("source","output"),("target_lufs",))
        out=_output(p["output"])
        if not approve:return {"ok":False,"outcome":"approval_required","would_write":[str(out)]}
        return loudness_normalise(source=str(_file(p["source"])),output=str(out),approve_write=True,target_lufs=_number(p.get("target_lufs",-16),-30,-5))
    if op=="motion-ease":
        from motion_v27 import ease
        _keys(p,("name","samples"),())
        count=p["samples"]
        if isinstance(count,bool) or not isinstance(count,int) or not 2<=count<=600:raise ValueError("samples must be 2..600")
        return {"ok":True,"samples":[ease(p["name"],i/(count-1)) for i in range(count)]}
    if op=="motion-beats":
        from motion_v27 import beat_transitions
        _keys(p,("bpm","beats_per_transition","duration"),("transition_beats",))
        return beat_transitions(_number(p["bpm"],20,300),_number(p["beats_per_transition"],1,32),_number(p["duration"],.1,300),transition_beats=_number(p.get("transition_beats",1),.1,16))
    if op=="decision-matrix":
        from thinking_v21 import decision_matrix
        _keys(p,("options","criteria","weights","scores"),())
        return decision_matrix(**p)
    if op=="plan-gaps":
        from thinking_v21 import plan_gaps
        _keys(p,("steps","initial_inputs","final_outputs"),())
        return plan_gaps(**p)
    if op=="code-audit":
        from rose_maintenance import audit
        _keys(p,(),())
        return audit()
    raise ValueError("unknown operation")

NATIVE={'3d-machine-mesh': ('modeling3d_v23', 'machine_mesh'), '3d-car-rig': ('modeling3d_v23', 'car_rig'), '3d-cloth': ('modeling3d_v23', 'cloth3d'), '3d-camera': ('modeling3d_v23', 'camera3d'), '3d-skinning': ('modeling3d_v23', 'skinning'), '3d-uv-atlas': ('modeling3d_v23', 'uv_atlas'), '3d-lighting': ('modeling3d_v23', 'area_lighting'), '3d-mesh-export-data': ('modeling3d_v23', 'export_mesh'), '3d-lod': ('modeling3d_v23', 'lod_budget'), '3d-cutaway': ('modeling3d_v23', 'cutaway'), 'agent-contract': ('agents_v22', 'task_contract'), 'agent-stage-dag': ('agents_v22', 'stage_dag'), 'agent-roster': ('agents_v22', 'agent_roster'), 'agent-parallel-plan': ('agents_v22', 'parallel_plan'), 'agent-critique': ('agents_v22', 'solution_critique'), 'agent-handoff-check': ('agents_v22', 'handoff_check'), 'agent-injection-check': ('agents_v22', 'injection_guard'), 'agent-claim-check': ('agents_v22', 'claim_check'), 'agent-progress': ('agents_v22', 'progress_monitor'), 'agent-rigor': ('agents_v22', 'rigor_mode'), 'think-first-principles': ('thinking_v21', 'first_principles'), 'think-alternatives': ('thinking_v21', 'alternatives'), 'think-causal': ('thinking_v21', 'causal'), 'think-premortem': ('thinking_v21', 'premortem'), 'think-budget': ('thinking_v21', 'budget_filter'), 'think-lesson-match': ('thinking_v21', 'lesson_match'), 'think-poc-gate': ('thinking_v21', 'poc_gate'), 'think-aesthetic': ('thinking_v21', 'aesthetic_decision')}

OPS={
"dua-preflight":"lyrics-film / reel-footage-song",
"dua-render":"lyrics-film / reel-footage-song",
"word-sync":"arabic-captions / lyrics-film",
"video-qa":"reel-footage-song / independent verification",
"scene-cuts":"reel-footage-song",
"audio-loudness":"voice-over",
"audio-normalize":"voice-over",
"motion-ease":"motion-html-film",
"motion-beats":"motion-html-film / reel-footage-song",
"decision-matrix":"hard-decision",
"plan-gaps":"begin-with-the-end / constraint-ledger",
"code-audit":"app-self-develop"
}
OPS.update({k: ("machine-teardown / blender-3d-shot" if k.startswith("3d-") else "task orchestration / planning" if k.startswith("agent-") else "hard-decision / thinking") for k in NATIVE})

def handle(a):
    try:
        if a.action=="list":
            result={"operations":[{"id":k,"source_recipe":v,"status":"native_adapter","scope":"calculation_or_planning" if k in NATIVE else "media_or_validation"} for k,v in OPS.items()]}
        else:
            if not a.op or not a.params:raise ValueError("operation and parameters JSON required")
            path=_file(a.params)
            if path.stat().st_size>1024*1024:raise ValueError("parameters too large")
            result=execute(a.op,json.loads(path.read_text(encoding="utf-8-sig")),a.approve_write)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 3 if isinstance(result,dict) and result.get("outcome")=="approval_required" else 1 if isinstance(result,dict) and (result.get("ok") is False or result.get("passed") is False) else 0
    except (ValueError,TypeError,RuntimeError,OSError) as e:
        print(json.dumps({"ok":False,"error":str(e)},ensure_ascii=False));return 1
def register(sub):
    p=sub.add_parser("golden-native",help="execute distilled Golden Dragon workflows with native Rose engines")
    p.add_argument("action",choices=["list","run"])
    p.add_argument("op",nargs="?",choices=list(OPS))
    p.add_argument("params",nargs="?")
    p.add_argument("--approve-write",action="store_true")
    p.set_defaults(ext_func=handle)
if __name__=="__main__":
    p=argparse.ArgumentParser();s=p.add_subparsers(required=True);register(s)
    raise SystemExit(handle(p.parse_args(["golden-native",*sys.argv[1:]])))
