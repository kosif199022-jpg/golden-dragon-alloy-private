"""Optional original V19 alternative; technical proxy only, no writes."""
import json
from shot_detail_legacy_v19 import shot_quality

def handle(a):
    try:
        result=shot_quality(a.source,sample_fps=a.sample_fps,max_clips=a.max_clips,max_duration=a.max_duration,min_score=a.min_score)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError,RuntimeError) as e:
        print(json.dumps({"ok":False,"error":str(e)},ensure_ascii=False))
        return 1

def register(sub):
    p=sub.add_parser("shot-detail",help="alternate Laplacian, contrast and motion analysis (read only)")
    p.add_argument("source")
    p.add_argument("--sample-fps",type=int,default=4)
    p.add_argument("--max-clips",type=int,default=3)
    p.add_argument("--max-duration",type=float,default=30)
    p.add_argument("--min-score",type=float,default=.5)
    p.set_defaults(ext_func=handle)
