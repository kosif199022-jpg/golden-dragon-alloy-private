"""Compile cross-source quality signals into a single portable policy."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

# Only observable production concerns are exported, never local instructions or paths.
DIMENSIONS = {
    "geometry": ("dimensions resolution aspect ratio viewport frame width height ابعاد أبعاد رأسي", "Measure output geometry and compare it with the requested format."),
    "timing": ("timeline duration fps timestamp cadence frame rate timing توقيت مدة", "Measure timing in the exported result against the requested timing."),
    "identity": ("identifier identifiers schema mapping column key reconciliation stock inventory جرد مطابقة أعمدة", "Preserve source identifiers and reconcile the counts against the inputs."),
    "legibility": ("caption subtitle text font contrast accessibility rtl arabic ترجمة كابشن عربي", "Inspect rendered text, direction and legibility at delivery size."),
    "sound": ("speech audio voice music narration loudness صوت موسيقى كلام", "Check that the required audio stream is present and aligned."),
    "provenance": ("source input metadata signature digest sha256 origin provenance بصمة مصدر", "Trace observations back to the supplied input and record its identity."),
    "validation": ("verify validate test acceptance assert expected compare فحص تحقق اختبار", "Check the real output through its normal entry point."),
    "continuity": ("scene character reference color palette materials composition continuity شخصية مشهد", "Compare visual continuity across shots using a shared reference."),
    "delivery": ("deliver output export render package encoding artifact تصدير تسليم فيديو", "Open the delivered artifact and verify its format and contents."),
}
TOKENS = re.compile(r"[^\W_]+", re.UNICODE)


def words(text):
    return set(TOKENS.findall(text.casefold()))


def compile_policy(repo):
    folder=repo/"apps/golden-dragon/app/fusion"
    catalog=json.loads((folder/"index.json").read_text(encoding="utf-8-sig"))["units"]
    recipes=json.loads((folder/"recipes.json").read_text(encoding="utf-8-sig"))
    lessons=json.loads((folder/"lessons.json").read_text(encoding="utf-8-sig"))
    vocabulary={key:words(value[0]) for key,value in DIMENSIONS.items()}
    joint={key:Counter() for key in vocabulary}
    used=Counter()
    scanned=Counter()
    readiness=Counter()
    missing=0
    signature=hashlib.sha256()

    def observe(body,group):
        signature.update(hashlib.sha256(body.encode()).digest())
        tokens=words(body)
        active=[name for name,terms in vocabulary.items() if terms & tokens]
        scanned[group]+=1
        if active:
            used[group]+=1
        for name in active:
            joint[name].update(active)

    for unit in catalog:
        readiness[(unit["kind"],unit["status"])]+=1
        body=" ".join(str(unit.get(k) or "") for k in ("name","what","what_ar"))
        if unit["kind"]=="skill":
            path=Path(unit["path"])
            if path.is_file():
                body+="\n"+path.read_text(encoding="utf-8-sig",errors="replace")
            else:
                missing+=1
        observe(body,"catalog")
    for item in recipes:
        observe(json.dumps(item,ensure_ascii=False),"recipes")
    for item in lessons:
        observe(str(item.get("rule_en",""))+" "+str(item.get("lesson_ar","")),"lessons")
    return {"format":1,"source_digest":signature.hexdigest(),"scanned":dict(scanned),
            "matched":dict(used),"readiness_by_role":{role:dict((status,count) for (kind,status),count in readiness.items() if kind==role) for role in sorted({kind for kind,status in readiness})},"unavailable_skill_files":missing,
            "checks":{k:{"cues":sorted(vocabulary[k]),"check":DIMENSIONS[k][1],"joint":dict(joint[k])} for k in vocabulary}}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("repo",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    model=compile_policy(args.repo)
    args.output.write_text(json.dumps(model,ensure_ascii=False,sort_keys=True),"utf-8")
    print(model["scanned"],model["matched"],model["unavailable_skill_files"])
