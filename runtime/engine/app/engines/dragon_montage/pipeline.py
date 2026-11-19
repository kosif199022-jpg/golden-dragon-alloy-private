"""The eight stations in order: plan (stop for the owner's yes) -> go (render, review, fix), or edit (no stop)."""
from __future__ import annotations

import json
import shutil
import sys
import time
import traceback
from pathlib import Path

from . import common as C

ARABIC = {"analyze": "العين الأولى", "brief": "يفهم المطلوب", "concepts": "يفكر بإبداع", "taste": "يختار الذوق",
          "direct": "يكتب المونتاج", "render": "ينفّذ", "review": "يتفرج وينقد", "generate": "اقتراحات التوليد",
          "mimic": "المحاكاة", "stock-search": "يدوّر في المواقع المفتوحة", "stock-fetch": "ينزّل اللقطات بترخيصها",
          "storyboard": "يوريك الشكل قبل ما ينفّذ"}
SNAP = (("render/final.mp4", "render/round{n}.mp4"), ("edl.json", "edl.round{n}.json"),
        ("review.json", "review.round{n}.json"), ("render.json", "render.round{n}.json"))


def station(name: str, fn, *args, log: list, **kw):
    """Run one station in-process with a log line; a failure stops the pipeline with its message."""
    t0 = time.time()
    try:
        out = fn(*args, **kw)
        rc, tail = 0, ""
    except (Exception, SystemExit) as exc:  # noqa: BLE001
        out, rc, tail = None, 1, (str(exc) or traceback.format_exc())[-500:]
    log.append({"station": name, "rc": rc, "seconds": round(time.time() - t0, 2), "stderr_tail": tail})
    sys.stderr.write(f"[{name}] {ARABIC.get(name, name)}: {'✓' if rc == 0 else '✗'}\n")
    if rc:
        raise SystemExit(f"station {name} failed:\n{tail}")
    return out


def job_status(job: Path, log: list, meta: dict) -> None:
    C.save(job / "job.json", C.new("job", **meta, stations=log))


def prepare(task, clips, music=None, job=None, platform=None, seconds=None, style=None, invent=False, reference=None,
            rounds=3, preview=False, no_transcribe=False, stock=None, stock_top=0, stock_commercial=False, animatic=False,
            stock_ids=None, reference_exact=False):
    """Stations 1-5 plus the preview: everything up to (not including) the render."""
    from .analyze import analyze
    from .direct import direct
    from .generate import gaps
    from .mimic import mimic
    from .storyboard import storyboard
    from .taste import pick
    from .think import brief, concepts
    job = C.job_dir(job or f"out/dragon-montage/{time.strftime('%Y%m%d-%H%M%S')}")
    log, clips = [], list(clips or [])
    meta = {"task": task, "clips": [str(Path(c).resolve()) for c in clips], "music": str(Path(music).resolve()) if music else None,
            "options": {"platform": platform, "seconds": seconds, "style": style, "invent": invent, "rounds": rounds, "preview": preview}}
    job_status(job, log, meta)
    if stock:                               # only when the owner asks: open-licence sites
        from . import stock as S  # noqa: F401 (module, not shadowed)
        orient = "portrait" if platform in ("reel", "story") else "landscape" if platform in ("youtube", "landscape") else None
        if not stock_ids:
            found = station("stock-search", S.search, job, stock, 6, stock_commercial, orient, log=log)
            job_status(job, log, {**meta, "status": "awaiting_stock_pick"})
            listing = "\n".join(f"  {r.get('id')}  {r.get('title') or ''}  {r.get('page_url') or r.get('url') or ''}"
                                 for r in found["results"][:12])
            raise SystemExit(f"stock: {len(found['results'])} results in {job / 'stock.json'} (match "
                             f"{S.match_mode(stock)}). Look at them (place, people, rights), then rerun with "
                             f"--stock-ids site:id,...\n{listing}")
        station("stock-search", S.search, job, stock, 6, stock_commercial, orient, log=log)
        got = station("stock-fetch", S.fetch, job, 0, stock_ids, log=log)
        meta["stock_clips"] = [g["path"] for g in got]
        clips += meta["stock_clips"]
        job_status(job, log, meta)
    if not clips:
        raise SystemExit("no footage: pass --clip and/or --stock \"<query>\"")
    station("analyze", analyze, job, clips, music, no_transcribe, log=log)
    station("brief", brief, job, task, platform, seconds, log=log)
    station("concepts", concepts, job, log=log)
    for stale in ("look_override.json", "reference_rhythm.json"):
        if not reference and (job / stale).exists():
            (job / stale).unlink()            # left over from an earlier --reference run
    if reference:
        station("mimic", mimic, job, reference, reference_exact, log=log)
    station("taste", pick, job, style, invent, log=log)
    station("direct", direct, job, log=log)
    station("generate", gaps, job, log=log)          # proposals only; nothing is spent
    station("storyboard", storyboard, job, animatic=animatic, log=log)
    meta["coverage"] = coverage(job)
    return job, log, meta


def coverage(job: Path) -> dict:
    """PROTOCOL «الطلبات بالحرف»: the request is kept word for word, and a hook that only repeats it is WEAK."""
    from .think import fold
    brief = C.read_opt(job, "brief") or {}
    concepts = C.read_opt(job, "concepts") or {}
    chosen = (concepts.get("decision") or {}).get("chosen")
    con = next((c for c in concepts.get("concepts", []) if c.get("id") == chosen), {}) or {}
    hook = str((con.get("hook") or {}).get("text") or "")
    task = str(brief.get("task") or "")
    norm = lambda t: " ".join(fold(t).replace("«", "").replace("»", "").split())  # noqa: E731
    problems = []
    if task and not brief.get("requirements"):
        problems.append("brief.requirements فاضي: الطلب لازم يتكتب بالحرف")
    if hook and task and (norm(hook) == norm(task) or norm(hook) in norm(task)):
        problems.append("WEAK hook: الهوك هو نص الطلب نفسه — اكتب هوك بإيدك")
    if "{{" in hook:
        problems.append("WEAK hook: فيه {{placeholder}} لسه")
    out = {"requirements": brief.get("requirements") or [], "hook": hook, "problems": problems,
           "verdict": "WEAK" if problems else "ok"}
    C.save(job / "coverage.json", out)
    return out


def plan(task, clips, **kw) -> dict:
    """Stop before the render: the owner sees preview/PLAN_AR.md + storyboard.jpg and says yes or asks for changes."""
    job, log, meta = prepare(task, clips, **kw)
    meta["status"] = "awaiting_owner_approval"
    job_status(job, log, meta)
    pv = job / "preview"
    return {"job": str(job), "status": "awaiting_owner_approval", "plan": str(pv / "PLAN_AR.md"),
            "storyboard": str(pv / "storyboard.jpg") if (pv / "storyboard.jpg").exists() else None,
            "animatic": str(pv / "animatic.mp4") if (pv / "animatic.mp4").exists() else None,
            "next": f"python3 <skill>/scripts/dragon.py run dragon_montage go --job {job}"}


def go(job, rounds=None, preview=None) -> dict:
    """The owner approved the preview: render, review and fix the EDL that is in the job now."""
    from .storyboard import storyboard
    job = C.job_dir(job)
    if not (job / "edl.json").exists():
        raise SystemExit(f"no edl.json in {job}: run `plan` first")
    brief = C.read_opt(job, "brief") or {}
    if brief.get("task") and not brief.get("requirements"):
        raise SystemExit("go: brief.requirements is empty (plan made by an older engine): rerun `plan` so the request is "
                         "kept word for word")
    old = json.loads((job / "job.json").read_text(encoding="utf-8")) if (job / "job.json").exists() else {}
    log = list(old.get("stations") or [])
    meta = {k: v for k, v in old.items() if k not in ("schema", "stations")}
    opts = meta.get("options") or {}
    station("storyboard", storyboard, job, log=log)   # the plan file matches the EDL that gets rendered
    meta.update(status="approved", approved_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    return finish(job, log, meta, preview=preview if preview is not None else bool(opts.get("preview")),
                  rounds=rounds or opts.get("rounds") or 3)


def edit(task, clips, **kw) -> dict:
    job, log, meta = prepare(task, clips, **kw)
    return finish(job, log, meta, preview=kw.get("preview", False), rounds=kw.get("rounds", 3))


def finish(job: Path, log: list, meta: dict, *, preview: bool, rounds: int) -> dict:
    from .direct import apply_review
    from .render import render
    from .review import review
    rounds, rv, scores = max(1, min(3, int(rounds))), None, {}
    for n in range(1, rounds + 1):
        station("render", render, job, preview=preview, log=log)
        rv = station("review", review, job, n, log=log)
        for src, dst in SNAP:
            if (job / src).exists():
                shutil.copy2(job / src, job / dst.format(n=n))
        scores[n] = float(rv.get("score") or 0.0)
        if rv["verdict"] == "ship" or not rv["fixes"] or n == rounds:
            break
        station("direct", apply_review, job, log=log)
    best = max(scores, key=lambda k: (scores[k], k))
    if best != max(scores):                   # a fix round made it worse: keep the better cut
        for src, dst in SNAP:
            if (job / dst.format(n=best)).exists():
                shutil.copy2(job / dst.format(n=best), job / src)
        rv = C.read(job, "review")
    meta["rounds"] = {"scores": scores, "kept": best}
    job_status(job, log, meta)
    write_report(job, log, rv)
    return {"job": str(job), "final": str(job / C.read(job, "render")["final"]), "verdict": rv["verdict"] if rv else None,
            "report": str(job / "report.md")}


def write_report(job: Path, log: list, review) -> None:
    """report.md in Egyptian Arabic with the three honest numbers: consulted, ran on your video, missing."""
    ran = sorted({r["tool"] for r in C.receipts(job) if r.get("owner_media") and r["rc"] == 0})
    analysis, brief, concepts, look, edl, render = (C.read(job, k) for k in ("analysis", "brief", "concepts", "look", "edl", "render"))
    chosen = next((c for c in concepts["concepts"] if c["id"] == concepts["decision"].get("chosen")), {})
    consulted = sum(len(c.get("frameworks", [])) for c in concepts["concepts"]) + len(brief.get("frameworks", []))
    L = ["# تقرير مونتاج التنين الأسود", "", f"**المهمة:** {brief['task']}", "",
         f"**الفيديو النهائي:** `{render['final']}` · المدة {edl['duration']:.1f} ثانية · {edl['width']}×{edl['height']}", "",
         f"**الفكرة المختارة:** {chosen.get('title', '—')} — {chosen.get('logline', '')}",
         f"**الهوك المقترح في الفكرة:** {chosen.get('hook', {}).get('text', '—')}",
         f"**أول لقطة فعلاً في المونتاج:** {edl['events'][0]['reason'] if edl['events'] else '—'}",
         f"**ليه الفكرة دي:** {concepts['decision'].get('why', '')}", "",
         f"**اللوك:** {look['style_id']} · لون {look['grade'].get('id')} · كابشن {look['captions'].get('style')}",
         f"**ليه:** {look.get('why', '')}", "", "## الأرقام بأمانة",
         f"- أطر تفكير اتقرت واتطبقت على الفكرة: {consulted}",
         f"- أدوات اشتغلت على فيديوك إنت: {len(ran)} ({', '.join(ran)})",
         f"- أدوات ناقصة: {', '.join(analysis.get('missing', [])) or 'مفيش'}",
         f"- قطعات في المونتاج: {len(edl['events'])}",
         f"- فحص الجودة التقني: {'عدّى' if render['verify'].get('pass') else 'ما عدّاش'}",
         f"- لفات النقد والتصليح: {review['round'] if review else 0} · الحكم: {review['verdict'] if review else '—'} · "
         f"الدرجة: {review.get('score', '—') if review else '—'}", "", "## كل قطعة وسببها"]
    L += [f"- `{ev['id']}` {ev['clip']} {ev['src_in']:.2f}→{ev['src_out']:.2f}: {ev['reason']}" for ev in edl["events"]]
    failed = [c for c in (review or {}).get("checks", []) if not c.get("pass")]
    if failed:
        L += ["", "## ملاحظات لسه مفتوحة"] + [f"- {c['id']}: {c.get('evidence', '')}" for c in failed]
    gen = json.loads((job / "generate.json").read_text(encoding="utf-8")).get("proposals", []) if (job / "generate.json").exists() else []
    if gen:
        L += ["", "## اقتراحات توليد (محتاجة موافقتك قبل أي صرف)"]
        L += [f"- {p['id']}: {p['kind']} لـ {p.get('role', '')} ({p.get('seconds', '?')} ث)" for p in gen]
    got = json.loads((job / "stock.json").read_text(encoding="utf-8")).get("downloaded", []) if (job / "stock.json").exists() else []
    if got:
        L += ["", "## لقطات من مواقع مفتوحة المصدر (بترخيصها)"] + [f"- {g.get('attribution') or g['path']}" for g in got]
        L += ["- ملف النسب الكامل: `stock/ATTRIBUTION.md`"]
    L += ["", "## المراحل", *[f"- {ARABIC.get(s['station'], s['station'])}: {'✓' if s['rc'] == 0 else '✗'} ({s['seconds']} ث)" for s in log]]
    (job / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
