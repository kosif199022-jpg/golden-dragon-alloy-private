#!/usr/bin/env python3
"""v1990 — measured free Higgsfield catalog, trend references, hosted Blender (3D Jutsu), higgsedit, Match Cut.

Offline and read-only: prints catalogs, templates and commands to paste. Never calls Higgsfield, never spends.
  hf free [--json] [--status measured|official|one_paid_step|unknown|paid] | hf free ID
  hf trend [list|live|show SLUG|commands SLUG_OR_URL|find WORDS] [--json]
  hf blender [template|rules]         hf higgsedit         hf apps [--json]         hf codefilm
"""
import json
import pathlib
import sys

for _s in (sys.stdout, sys.stderr):      # Windows consoles default to cp1252: Arabic output would crash
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE.parent          # standalone skill: scripts/ sits directly under the skill folder
MARK = {"measured": "✅", "official": "☑", "one_paid_step": "🟡", "unknown": "❓", "paid": "❌"}


def _load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def _flag(argv, name):
    if name in argv:
        argv.remove(name)
        return True
    return False


def _opt(argv, name):
    if name in argv:
        i = argv.index(name)
        if i + 1 >= len(argv):
            raise SystemExit(f"{name} needs a value")
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return None


def free(argv):
    d = _load("free.json")
    as_json, status = _flag(argv, "--json"), _opt(argv, "--status")
    if status and status not in d["status_legend"]:
        print(f"unknown status; one of: {', '.join(d['status_legend'])}", file=sys.stderr)
        return 2
    items = [i for i in d["items"] if not status or i["status"] == status]
    if argv:
        hit = [i for i in d["items"] if i["id"] == argv[0]]
        if not hit:
            print(f"no such id; ids: {' '.join(i['id'] for i in d['items'])}", file=sys.stderr)
            return 2
        print(json.dumps(hit[0], ensure_ascii=False, indent=1))
        return 0
    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=1))
        return 0
    print(f"Higgsfield المجاني — قياس {d['as_of']} (الرصيد قبل {d['balance_before']} / بعد {d['balance_after']})")
    print(d["method"] + "\n")
    for i in items:
        print(f"{MARK[i['status']]} {i['id']:<16} {i['name']}\n     كيف: {i['how']}\n     دليل: {i['evidence']}"
              + (f"\n     حدود: {i['limits']}" if i["limits"] else ""))
    print("\n" + " · ".join(f"{MARK[k]} {v}" for k, v in d["status_legend"].items()))
    return 0


def _style(d, slug):
    return next((s for s in d["what_if_styles"] if s["slug"] == slug), None)


def trend(argv):
    d = _load("trend_refs.json")
    as_json = _flag(argv, "--json")
    sub = argv[0] if argv else "list"
    if sub == "list":
        if as_json:
            print(json.dumps({"what_if_styles": d["what_if_styles"], "katana_presets": d["katana_presets"]},
                             ensure_ascii=False, indent=1))
            return 0
        print(f"{len(d['what_if_styles'])} What-If reference videos (public URL, free to analyse) — snapshot {d['as_of']}")
        for s in d["what_if_styles"]:
            print(f"  {s['slug']:<20} {s['look']}")
        print(f"\n{len(d['katana_presets'])} Katana presets (reference video comes from get_preset_instructions /katana/SLUG):")
        print("  " + " ".join(k["slug"] for k in d["katana_presets"]))
        print("\n" + d["note"])
        return 0
    if sub == "live":
        if as_json:
            print(json.dumps(d["live_sources"], ensure_ascii=False, indent=1))
            return 0
        print("مصادر الترند الحية (نادِها من أدوات Higgsfield؛ الأداة دي مش بتتصل):")
        for s in d["live_sources"]:
            print(f"- {s['tool']}  [{s['cost']}]" + "".join(f"\n    {k}: {s[k]}" for k in ("needs", "args", "measured", "warning") if k in s))
        print("\nلقطة Genjutsu trending يوم " + d["as_of"] + ": " + "، ".join(d["genjutsu_trending_snapshot"]))
        if d.get("genjutsu_trending_note"):
            print(d["genjutsu_trending_note"])
        return 0
    if sub == "show":
        s = _style(d, argv[1]) if len(argv) > 1 else None
        if not s:
            print("usage: hf trend show SLUG (see `hf trend list`)", file=sys.stderr)
            return 2
        print(json.dumps(s, ensure_ascii=False, indent=1))
        return 0
    if sub == "find":
        words = [w.lower() for w in argv[1:]]
        if not words:
            print("usage: hf trend find WORDS", file=sys.stderr)
            return 2
        hits = [s for s in d["what_if_styles"] if all(w in (s["slug"] + " " + s["title"] + " " + s["look"]).lower() for w in words)]
        hits_k = [k for k in d["katana_presets"] if all(w in k["slug"] for w in words)]
        if as_json:
            print(json.dumps({"what_if_styles": hits, "katana_presets": hits_k}, ensure_ascii=False, indent=1))
        else:
            for s in hits:
                print(f"what-if  {s['slug']:<20} {s['look']}")
            for k in hits_k:
                print(f"katana   {k['command']}")
        return 0 if hits or hits_k else 1
    if sub == "commands":
        if len(argv) < 2:
            print("usage: hf trend commands SLUG_OR_URL", file=sys.stderr)
            return 2
        target = argv[1]
        s = _style(d, target)
        if s:
            slug, url = s["slug"], s["reference_video"]
        elif target.startswith("https://") or target.startswith("/"):
            slug, url = "ref", target
        else:
            print("not a known What-If slug and not an https URL or sandbox path. Katana presets: load "
                  "get_preset_instructions /katana/SLUG to obtain the reference video URL first.", file=sys.stderr)
            return 2
        if "'" in url or "\n" in url:
            print("refusing a URL with quotes or newlines", file=sys.stderr)
            return 2
        script = (HERE / "templates" / "trend_dna.sh").read_text(encoding="utf-8")
        print("# paste into sandbox_exec with background:true (analysis only, no generation, no credit)\n"
              "mkdir -p ~/bdtools && cat > ~/bdtools/trend_dna.sh <<'XEOF'\n" + script + "XEOF\n"
              f"bash ~/bdtools/trend_dna.sh {slug} '{url}'")
        return 0
    print("unknown trend subcommand; see --help", file=sys.stderr)
    return 2


BLENDER_RULES = """3D Jutsu = Blender 5.2 LTS مستضاف عند Higgsfield (مقاس مجاني 2026-11-11). التنين مالوش Blender في الـsandbox، فده بديله.
الحلقة: create_project (مرة واحدة) → get_project → query_python (اقرأ revision و sceneSequence) → run_python بنفس الرقمين
        → get_operation لحد succeeded → get_artifact وافتح الصورة وبُص عليها → show_scene(revisionAfter) مرة واحدة.
- مشروع جديد مالوش World: اعمله قبل ما تلمس نودز العالم (أول تجربة وقعت هنا).
- المحركات: BLENDER_EEVEE / BLENDER_WORKBENCH / CYCLES بس. الإضاءة Sun/Spot/Point (الـArea بتقع من الـGLB).
- media_type قبل file_format، والملف مايخرجش غير بـ artifacts.file(...).publish(). حد أقصى 8 ملفات للعملية.
- مفيش نت ولا pip، ≈5 دقايق للعملية، كود ≤256 KiB: رندر صغير، وقسّم البناء، وتعديل واحد في المرة.
- الموديلات من scene_builder_3d_search_assets → import_asset بس. ممنوع تنزيل من جوه بايثون.
- نجاح العملية ≠ المشهد صح: لازم رندر من كاميرا التسليم وتتفرج عليه.
- مدفوع: scene_builder_3d_generate_angles و scene_builder_3d_generate_video (سعر + «موافق»).
- التسليم: get_glb / get_blend لما صاحب المشروع يطلب الملفات. الـPNG ينزل بـcurl جوه sandbox_exec للتركيب بـffmpeg/higgsedit.
القالب: `tool hf blender template`"""


def blender(argv):
    sub = argv[0] if argv else "rules"
    if sub == "template":
        print((HERE / "templates" / "jutsu_scene.py").read_text(encoding="utf-8"))
        return 0
    if sub == "rules":
        print(BLENDER_RULES)
        return 0
    print("usage: hf blender [template|rules]", file=sys.stderr)
    return 2


def higgsedit(argv):
    print((HERE / "templates" / "higgsedit_ar.js").read_text(encoding="utf-8"))
    return 0


def apps(argv):
    a = _load("free.json")["matchcut_app"]
    if _flag(argv, "--json"):
        print(json.dumps(a, ensure_ascii=False, indent=1))
        return 0
    print(f"Match Cut + Tracelab — app_id {a['app_id']} (manifest {a['manifest_revision']}؛ {a['note']})")
    print("actions: " + " ".join(a["actions"]))
    print(f"مقاس مجاني: {a['measured_action']} فقط. أي action تاني: balance قبل وبعد أول مرة.\n"
          f"الترتيب: apps_describe(app_id, action) → apps_invoke(...) → apps_invoke(get_render, render_id) لحد completed → curl result_url جوه الـsandbox.")
    return 0


def codefilm(argv):
    print((SKILL / "references" / "CODE_FILM_V1990.md").read_text(encoding="utf-8"))
    return 0


COMMANDS = {"free": free, "trend": trend, "blender": blender, "higgsedit": higgsedit, "apps": apps, "codefilm": codefilm}


def main(argv):
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in COMMANDS:
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    return COMMANDS[argv[0]](list(argv[1:]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
