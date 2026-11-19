#!/usr/bin/env python3
"""hf — Black Dragon Higgsfield helper. Prints offline guidance; never calls Higgsfield itself.

  dragon.py tool hf guide       # the free/paid table and the fixed recipe (references/HIGGSFIELD_FREE.md)
  dragon.py tool hf bootstrap   # shell to paste into sandbox_exec: job dirs + Arabic fonts + tool check
  dragon.py tool hf qc          # shell to paste into sandbox_exec: QC gate (size, frames, AAC, decode, black, LUFS/TP)
  dragon.py tool hf paste JOB   # one sandbox_exec command that writes bootstrap.sh + qc.sh + prender.sh (parallel frames) to ~/bdtools and runs bootstrap
  dragon.py tool hf check TOOL  # v10.15: free (exit 0) / paid or unknown cost (exit 3: needs the owner's yes, every time)
  dragon.py tool hf ask TOOL --price N [--balance B]   # v10.15: the exact approval request to send the owner
  dragon.py tool hf workflows [--json]   # v10.17.1: report-based catalog, no execution
  dragon.py tool hf workflow NAME        # v10.17.1: read one workflow record
  dragon.py tool hf route DESCRIPTION    # v10.17.1: suggest workflows by task; no execution
  dragon.py tool hf free [ID] [--json] [--status S]   # v1990: measured free catalog (balance before/after, 2026-11-11)
  dragon.py tool hf trend [list|live|find W|show SLUG|commands SLUG_OR_URL]   # v1990: trend sources + free reel teardown to paste
  dragon.py tool hf blender [rules|template]   # v1990: hosted Blender 5.2 (3D Jutsu) loop + a scene script that ran
  dragon.py tool hf higgsedit            # v1990: higgsedit starter with the Arabic font rule
  dragon.py tool hf apps [--json]        # v1990: Match Cut + Tracelab actions (create_typewriter measured free)
  dragon.py tool hf codefilm             # v1990: «film in code» method (Higgsfield blog study) as a dragon checklist

v10.12.1 rule: no Higgsfield tool that spends credits runs without the owner's explicit yes to THAT tool and THAT
price, every time. Unknown cost requires approval. Previous no-debit observations are historical, not guarantees.
"""
import pathlib
import re
import sys

for _s in (sys.stdout, sys.stderr):      # Windows consoles default to cp1252: Arabic output would crash
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SKILL = HERE.parent          # standalone skill: scripts/ sits directly under the skill folder

# Earlier observations of no generation-credit debit; not official billing terms. Other tools are paid or unknown -> ask.
FREE = {"sandbox_exec", "media_upload", "media_confirm", "media_upload_widget", "models_explore",
        "get_presets", "get_preset_instructions", "get_workflow_instructions", "get_workflow_bundle_file", "balance",
        "show_plans_and_credits", "transactions", "list_projects", "get_project", "list_project_assets", "show_medias",
        "show_generations", "show_generation_by_ids", "job_display", "jobs_wait", "list_voices", "show_result",
        "list_folders", "get_folder", "search_folders", "get_preferences", "list_workspaces", "apps_search",
        "apps_describe", "ads_studio_quote", "ai_influencer_prepare", "ai_influencer_get_options",
        "ai_influencer_list_presets", "ai_influencer_get_settings", "get_explainer_presets", "video_analysis_status",
        "video_analysis_jobs", "website_status", "list_websites", "list_website_categories", "show_characters",
        "show_reference_elements", "tiktok_music_trending", "tiktok_accounts", "tiktok_publish_status",
        # v1990, measured 2026-11-11 (balance 347.88 before and after, no transaction row):
        "scene_builder_3d_create_project", "scene_builder_3d_list_projects", "scene_builder_3d_get_project",
        "scene_builder_3d_query_python", "scene_builder_3d_run_python", "scene_builder_3d_get_operation",
        "scene_builder_3d_get_artifact", "scene_builder_3d_show_scene", "scene_builder_3d_search_assets",
        "scene_builder_3d_get_glb", "scene_builder_3d_get_blend"}
# apps_invoke: only Match Cut `create_typewriter` and `get_render` were measured at 0. It stays "ask" by default.
PAID_HINT = re.compile(r"generate|upscale|remove_background|reframe|dubbing|outpaint|relight|motion_control|"
                       r"voice_change|create_voice|execute_preset|ads_studio_generate|ai_influencer_generate|"
                       r"video_analysis_create|virality_predictor|scene_builder_3d_generate|apps_invoke", re.I)


def classify(tool):
    t = tool.split("__")[-1].strip()
    if t in FREE:
        return t, "free"
    return t, ("paid" if PAID_HINT.search(t) else "unknown")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "check":
        if len(argv) < 2:
            print("usage: hf check TOOL", file=sys.stderr); return 2
        t, kind = classify(argv[1])
        if kind == "free":
            print(f"{t}: ضمن الأدوات المصنفة بلا كريدت توليد في فحص سابق (ليس ضمانًا رسميًا بالمجانية). "
                  f"تحقق من السعر والرصيد قبل/بعد، ولا تبدأ استخدامًا مدفوعًا دون موافقة.")
            return 0
        print(f"{t}: {'بيصرف رصيد' if kind == 'paid' else 'تكلفته مش معروفة = اعتبره مدفوع'}. "
              f"ممنوع قبل موافقة صريحة على الأداة والسعر: `tool hf ask {t} --price N`")
        return 3
    if cmd == "ask":
        import argparse
        ap = argparse.ArgumentParser(prog="hf ask")
        ap.add_argument("tool"); ap.add_argument("--price", required=True, help="credits this call costs (from a quote)")
        ap.add_argument("--balance", help="balance right now (from `balance`)")
        ap.add_argument("--what", default="", help="one line: what it will make")
        a = ap.parse_args(argv[1:])
        t, kind = classify(a.tool)
        bal = f" الرصيد دلوقتي {a.balance}." if a.balance else ""
        print(f"محتاج موافقتك: هشغّل `{t}` على Higgsfield{(' عشان ' + a.what) if a.what else ''}، "
              f"وهيخصم {a.price} كريدت.{bal} أكمّل؟ (لازم «موافق» على الأداة دي والسعر ده بالظبط)")
        if kind == "free":
            print("(ملحوظة: الأداة دي في قايمة المجاني، فالسؤال احتياطي.)", file=sys.stderr)
        return 0
    if cmd in ("free", "trend", "blender", "higgsedit", "apps", "codefilm"):
        from free import main as free_main
        return free_main(argv)
    if cmd in ("workflows", "workflow", "route"):
        from workflows import main as workflows_main
        sub = "list" if cmd == "workflows" else "show" if cmd == "workflow" else "route"
        return workflows_main([sub] + argv[1:])
    if cmd == "guide":
        print((SKILL / "references" / "SANDBOX_RECIPE.md").read_text(encoding="utf-8"))
        return 0
    if cmd in ("bootstrap", "qc"):
        print((HERE / f"{cmd}.sh").read_text(encoding="utf-8"))
        return 0
    if cmd == "paste":
        job = argv[1] if len(argv) > 1 else "job"
        b = (HERE / "bootstrap.sh").read_text(encoding="utf-8")
        q = (HERE / "qc.sh").read_text(encoding="utf-8")
        pr = (HERE / "prender.sh").read_text(encoding="utf-8")
        print("mkdir -p ~/bdtools && cd ~/bdtools && cat > bootstrap.sh <<'XEOF'\n" + b + "XEOF\n"
              "cat > qc.sh <<'XEOF'\n" + q + "XEOF\n"
              "cat > prender.sh <<'XEOF'\n" + pr + "XEOF\n" + f"bash bootstrap.sh {job}")
        return 0
    print("unknown subcommand; see --help", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
