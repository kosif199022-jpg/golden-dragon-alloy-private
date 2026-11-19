"""Smart-effects gate (v10.3): an effect is allowed only when it does a job for THIS shot.

Owner rule, 2026-11-09: «شيل الكرات الذهبيه والاضاءه والضباب ملوش لازمه … بلاش تبوظ الصور والفيديوهات الجميله
بحاجات غبيه … المؤثرات مش مجرد استخدامها، يبقى استخدام ذكي».

    dragon fx rules                              the law, the five questions and the default bans
    dragon fx new OUT.json [--material footage]  an empty manifest (no effects = the cleanest valid film)
    dragon fx check MANIFEST.json [--html PAGE] [--json]
                                                 exit 1 when an effect has no real reason, is a banned overlay on
                                                 beautiful material, covers the subject, breaks the budget, or is
                                                 drawn by PAGE without being declared

The gate checks the declared reasoning and that the page draws nothing undeclared. It cannot see taste: the stills
and the QC sheet are still opened and judged by eye.
"""
import argparse
import json
import re
import sys
from pathlib import Path

MATERIALS = ("footage", "photo", "illustration", "type-only")
# what an effect may be FOR. "decoration" is deliberately missing.
SERVES = ("meaning", "subject", "readability", "transition", "brand", "continuity")
# full-frame layers drawn over the picture
OVERLAY_KINDS = ("particles", "bokeh", "haze", "fog", "vignette", "light-leak", "light-sweep", "glow", "flare",
                 "color-filter", "grain", "shade")
# on real footage or photos these spoil the picture unless the owner asked for them by name
BANNED_ON_REAL = ("particles", "bokeh", "haze", "fog", "vignette", "light-leak", "light-sweep", "glow", "flare",
                  "color-filter", "shade")
GENERIC = ("جميل", "حلو", "شكله", "ابداع", "إبداع", "سينمائي", "فخم", "احترافي", "جو", "لمسة", "يزين", "زينة",
           "nice", "cinematic", "beautiful", "pretty", "cool", "looks good", "polish", "vibe", "premium", "decor")
# drawing calls our page engines use for overlays; a page that calls one must declare it
KNOWN_CALLS = {
    "dust": "particles", "sparks": "particles", "petals": "particles", "hearts": "particles", "rain": "particles",
    "stars": "particles", "notes": "particles", "bokeh": "bokeh", "snow": "particles", "confetti": "particles",
    "vignette": "vignette", "topShade": "shade", "midShade": "shade", "fog": "fog", "haze": "haze",
    "lightLeak": "light-leak", "lightSweep": "light-sweep", "flare": "flare", "glow": "glow", "grain": "grain",
}
MAX_OVERLAY_KINDS_FILM = 2
MAX_OVERLAYS_PER_SHOT = 1
MAX_COVERAGE = 0.18

RULES = """قانون المؤثرات الذكية (شرط أساسي، v10.3)
المؤثر مش زينة. يتحط بس لما يعمل شغلانة للّقطة دي بالذات، ولو اتشال اللقطة تخسر حاجة.

الأسئلة الخمسة قبل أي مؤثر (لو واحد «لأ» = مايتحطش):
 1. بيخدم إيه بالظبط؟ معنى الكلمة، إبراز الموضوع، وضوح النص، نقلة، هوية، استمرارية. «شكله حلو» مش إجابة.
 2. لو شلته، اللقطة تخسر إيه؟ لو مفيش خسارة = شيله.
 3. بيغطي الموضوع أو الوش أو أجمل حتة في الكادر؟ = ممنوع.
 4. الصورة أصلًا جميلة (فوتيج أو صورة حقيقية)؟ = سيبها زي ما هي: مفيش كرات ولا ضباب ولا لمعة ولا فلتر لون فوقها.
 5. هو نفس المؤثر اللي اتحط في آخر فيلم من غير تفكير؟ = شيله وفكّر من الأول.

الممنوع افتراضيًا فوق الفوتيج والصور الحقيقية (إلا لو صاحب الشغل طلبه بالاسم):
 كرات/غبار دهبي وبوكيه، ضباب وهيز، فينييت، تسريب نور ولمعة ماشية، جلو، فلير، فلتر لون، تعتيم على الكادر كله.
وضوح النص يتحل في النص نفسه (حد غامق رفيع وظل قريب)، مش بتعتيم الصورة.

الميزانية: نوعين overlay بالكتير في الفيلم كله، واحد بالكتير في اللقطة، وتغطية ≤ 18٪ من الكادر.
أنضف فيلم = صورة جميلة + خط جميل + توقيت صح. صفر مؤثرات نتيجة مقبولة ومفضّلة.
"""


def template(material="footage"):
    return {"schema": "dragon.effects.v1", "material": material,
            "note": "اكتب كل مؤثر بيترسم فوق الصورة. القايمة الفاضية = فيلم نضيف وده مقبول.",
            "effects": [],
            "example_effect": {"name": "petals", "kind": "particles", "shots": ["s8"], "serves": "meaning",
                               "why": "الكلمة «ورد» بتتقال في اللقطة دي والورد نازل ورا الشخصية مش عليها",
                               "if_removed": "الكلمة تفضل من غير صورتها", "covers_subject": False,
                               "coverage": 0.06, "owner_asked": False}}


def _generic(why):
    w = why.strip().lower()
    words = [x for x in re.split(r"\s+", w) if x]
    if len(w) < 15 or len(words) < 4:
        return True
    return sum(1 for g in GENERIC if g in w) >= 1 and len(words) < 7


def page_calls(html, extra=()):
    """overlay drawing calls a page really makes inside its code (name -> count), ignoring their definitions."""
    found = {}
    for name in sorted(set(KNOWN_CALLS) | set(extra)):
        calls = len(re.findall(r"(?<![\w.])" + re.escape(name) + r"\s*\(", html))
        defs = len(re.findall(r"function\s+" + re.escape(name) + r"\s*\(", html))
        if calls - defs > 0:
            found[name] = calls - defs
    return found


def check(manifest, html=None):
    fails, warns = [], []
    material = manifest.get("material")
    if material not in MATERIALS:
        fails.append(f"material لازم يكون واحد من {MATERIALS} (المكتوب: {material!r})")
    effects = manifest.get("effects")
    if not isinstance(effects, list):
        return {"ok": False, "fails": ["effects لازم تكون قايمة (فاضية = فيلم نضيف)"], "warns": [], "effects": 0}
    real = material in ("footage", "photo")
    per_shot, kinds = {}, set()
    for i, e in enumerate(effects):
        tag = f"#{i + 1} {e.get('name', '?')}"
        kind, serves, why = e.get("kind"), e.get("serves"), str(e.get("why", ""))
        asked = bool(e.get("owner_asked"))
        if not e.get("name"):
            fails.append(f"{tag}: من غير name")
        if serves not in SERVES:
            fails.append(f"{tag}: serves={serves!r} مش شغلانة. المسموح {SERVES}؛ الزينة مش سبب")
        if _generic(why):
            fails.append(f"{tag}: why عام أو قصير («{why}»). اكتب بيخدم إيه في اللقطة دي بالذات")
        if not str(e.get("if_removed", "")).strip():
            fails.append(f"{tag}: if_removed فاضي. لو شلته اللقطة تخسر إيه؟ لو مفيش = شيله")
        if e.get("covers_subject"):
            fails.append(f"{tag}: بيغطي الموضوع أو الوش = ممنوع")
        if not e.get("shots"):
            fails.append(f"{tag}: من غير shots. المؤثر يتحدد بلقطاته، مش على الفيلم كله")
        if kind in OVERLAY_KINDS:
            kinds.add(kind)
            for s in e.get("shots") or []:
                per_shot.setdefault(s, []).append(e.get("name"))
            cov = e.get("coverage")
            if not isinstance(cov, (int, float)):
                fails.append(f"{tag}: coverage (نسبة من الكادر 0..1) مش مكتوبة")
            elif cov > MAX_COVERAGE and not asked:
                fails.append(f"{tag}: تغطية {cov:.0%} أكبر من {MAX_COVERAGE:.0%}")
            if real and kind in BANNED_ON_REAL and not asked:
                fails.append(f"{tag}: «{kind}» فوق {material} حقيقي ممنوع افتراضيًا (بيبوّظ الصورة). "
                             "يتشال، أو owner_asked=true لو صاحب الشغل طلبه بالاسم")
            if asked and not str(e.get("owner_words", "")).strip():
                fails.append(f"{tag}: owner_asked من غير owner_words (كلامه بالحرف والتاريخ)")
    if len(kinds) > MAX_OVERLAY_KINDS_FILM and not all(e.get("owner_asked") for e in effects if e.get("kind") in kinds):
        fails.append(f"{len(kinds)} أنواع overlay في الفيلم ({', '.join(sorted(kinds))}): الحد {MAX_OVERLAY_KINDS_FILM}")
    for s, names in sorted(per_shot.items()):
        if len(names) > MAX_OVERLAYS_PER_SHOT:
            fails.append(f"اللقطة {s}: {len(names)} overlay فوق بعض ({', '.join(map(str, names))}): الحد {MAX_OVERLAYS_PER_SHOT}")
    drawn = {}
    if html is not None:
        declared = {e.get("name") for e in effects}
        drawn = page_calls(html, extra=[n for n in declared if n])
        for name, n in sorted(drawn.items()):
            if name not in declared:
                fails.append(f"الصفحة بترسم «{name}» ({n} مرة) ومش مكتوب في الـ manifest: شيله من الصفحة أو برّره")
        for name in sorted(n for n in declared if n and n not in drawn):
            warns.append(f"«{name}» مكتوب في الـ manifest والصفحة مابترسمهوش")
    if not effects and not fails:
        warns.append("صفر مؤثرات: فيلم نضيف (صورة + خط + توقيت)")
    return {"ok": not fails, "fails": fails, "warns": warns, "effects": len(effects),
            "overlay_kinds": sorted(kinds), "page_draws": drawn, "material": material}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dragon fx", description="smart-effects gate: every effect needs a job")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("rules")
    nw = sub.add_parser("new"); nw.add_argument("out"); nw.add_argument("--material", default="footage", choices=MATERIALS)
    ck = sub.add_parser("check"); ck.add_argument("manifest"); ck.add_argument("--html"); ck.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "rules":
        print(RULES)
        return 0
    if a.cmd == "new":
        Path(a.out).write_text(json.dumps(template(a.material), ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote", a.out)
        return 0
    try:
        manifest = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        print(f"FX FAIL: مش قادر أقرا الـ manifest: {ex}")
        return 1
    html = None
    if a.html:
        try:
            html = Path(a.html).read_text(encoding="utf-8")
        except OSError as ex:
            print(f"FX FAIL: مش قادر أقرا الصفحة: {ex}")
            return 1
    r = check(manifest, html)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        for f in r["fails"]:
            print("✗", f)
        for w in r["warns"]:
            print("·", w)
        print(("FX OK" if r["ok"] else "FX FAIL") + f"  effects={r['effects']}  overlay_kinds={len(r.get('overlay_kinds', []))}"
              + (f"  page_draws={sorted(r['page_draws'])}" if html is not None else "  (من غير --html: الصفحة ماتفحصتش)"))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
