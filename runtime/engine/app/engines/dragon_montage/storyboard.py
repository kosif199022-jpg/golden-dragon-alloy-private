"""Station 5b «يوريك الشكل قبل ما ينفّذ»: before anything is rendered, draw the edit so the owner can approve it.

preview/storyboard.jpg  one frame per cut in the delivery aspect, a timeline strip on top (width = length, colour = role)
preview/PLAN_AR.md      concept, look and the movement matrix «مصفوفة التحركات» in Egyptian Arabic
preview/plan.json       the same matrix as data (kosif.dm.plan.v1)
preview/animatic.mp4    with --animatic: a fast low-res draft render of the same EDL
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from . import common as C
from . import edl as E
from ..media import ffmpeg

ROLE_AR = {"hook": "خطّاف", "setup": "تمهيد", "journey": "رحلة", "turn": "تحوّل", "climax": "ذروة", "outro": "نهاية",
           "payoff": "النتيجة", "proof": "دليل", "problem": "المشكلة", "solution": "الحل", "cta": "دعوة للفعل",
           "context": "سياق", "broll": "لقطة مساعدة", "speech": "كلام"}
ROLE_RGB = {"hook": (230, 57, 70), "climax": (244, 162, 97), "turn": (233, 196, 106), "outro": (42, 157, 143),
            "cta": (42, 157, 143), "payoff": (244, 162, 97)}


def frame(src: str, t: float, w: int, h: int, dst: Path) -> bool:
    r = ffmpeg("-ss", f"{max(0.0, t):.3f}", "-i", src, "-frames:v", 1, "-vf",
               f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}", "-q:v", 3, dst, check=False)
    return r.returncode == 0 and dst.exists()


def words_in(clip: dict, a: float, b: float) -> str:
    txt = " ".join(str(w.get("w", "")).strip() for w in clip.get("words") or []
                   if float(w.get("start", 0)) >= a - 0.05 and float(w.get("end", 0)) <= b + 0.05).strip()
    return (txt[:60] + "…") if len(txt) > 60 else txt


def matrix(job: Path) -> dict:
    edl = E.reflow(json.loads(json.dumps(C.read(job, "edl"))))
    clips = E.clip_index(C.read(job, "analysis"))
    rows = []
    for ev in edl["events"]:
        clip = clips.get(ev.get("clip"), {})
        rows.append({"id": ev["id"], "rec_in": round(ev["rec_in"], 2), "rec_out": round(ev["rec_in"] + E.event_seconds(ev), 2),
                     "clip": ev.get("clip"), "src": Path(str(clip.get("path", ""))).name, "src_in": ev["src_in"],
                     "src_out": ev["src_out"], "role": ev.get("role") or ev.get("kind") or "", "kind": ev.get("kind") or "",
                     "camera": (ev.get("camera") or {}).get("id", "static"),
                     "transition": (ev.get("transition_in") or {}).get("id", "cut"), "speed": ev.get("speed", 1.0),
                     "grade": (ev.get("grade") or {}).get("id") if isinstance(ev.get("grade"), dict) else ev.get("grade"),
                     "mute": bool(ev.get("mute")), "words": words_in(clip, ev["src_in"], ev["src_out"]),
                     "reason": str(ev.get("reason", ""))})
    return {"schema": "kosif.dm.plan.v1", "width": edl["width"], "height": edl["height"], "fps": edl["fps"],
            "duration": edl["duration"], "grade": (edl.get("grade") or {}).get("id"), "captions": edl.get("captions"),
            "music": ((edl.get("audio") or {}).get("music") or {}).get("path"), "rows": rows, "status": "awaiting_owner_approval"}


def sheet(job: Path, plan: dict, cols: int):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    paths = {c["id"]: c["path"] for c in C.read(job, "analysis").get("clips", [])}
    W, H, rows = plan["width"], plan["height"], plan["rows"]
    tw = 200
    th = max(60, round(tw * H / W))
    tmp = job / "preview" / "frames"
    tmp.mkdir(parents=True, exist_ok=True)
    cols = max(1, min(cols, len(rows)))
    pad, label_h, strip_h = 10, 44, 46
    img = Image.new("RGB", (pad + cols * (tw + pad), strip_h + pad + -(-len(rows) // cols) * (th + label_h + pad)), (18, 18, 22))
    d = ImageDraw.Draw(img)
    font = None
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "Arial.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(name, 12)       # labels are Latin; the Arabic lives in PLAN_AR.md
            break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    total, x0, x1 = max(plan["duration"], 0.01), pad, img.width - pad
    for r in rows:
        a, b = x0 + (x1 - x0) * r["rec_in"] / total, x0 + (x1 - x0) * min(r["rec_out"], total) / total
        d.rectangle([a, 8, max(a + 1, b - 1), 30], fill=ROLE_RGB.get(r["role"], (90, 110, 140)))
        d.text((a + 2, 12), r["id"][1:], fill=(255, 255, 255), font=font)
    d.text((x0, 32), f"0s  ->  {plan['duration']:.1f}s   {W}x{H}  grade={plan['grade']}", fill=(170, 170, 180), font=font)
    for i, r in enumerate(rows):
        cx, cy = pad + (i % cols) * (tw + pad), strip_h + pad + (i // cols) * (th + label_h + pad)
        f = tmp / f"{r['id']}.jpg"
        if r["clip"] in paths and frame(paths[r["clip"]], (r["src_in"] + r["src_out"]) / 2, tw, th, f):
            img.paste(Image.open(f).convert("RGB"), (cx, cy))
        else:
            d.rectangle([cx, cy, cx + tw, cy + th], outline=(90, 90, 90))
        d.rectangle([cx, cy, cx + tw, cy + 4], fill=ROLE_RGB.get(r["role"], (90, 110, 140)))
        d.text((cx, cy + th + 3), f"#{i + 1} {r['rec_in']:.1f}-{r['rec_out']:.1f}s  {r['role']}", fill=(235, 235, 235), font=font)
        d.text((cx, cy + th + 21), f"cam:{r['camera']}  in:{r['transition']}", fill=(160, 200, 255), font=font)
    out = job / "preview" / "storyboard.jpg"
    img.save(out, quality=88)
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def arabic_reason(reason: str) -> str:
    """Reasons are "en | ar; en | ar": keep every Arabic part."""
    ar = [p.strip() for chunk in reason.split("|") for p in chunk.split(";") if re.search(r"[؀-ۿ]", p)]
    return ("؛ ".join(ar) or reason).replace("|", "/")[:160]


def plan_md(job: Path, plan: dict, board) -> str:
    concepts, look, brief = C.read(job, "concepts"), C.read(job, "look"), C.read(job, "brief")
    chosen = concepts["decision"]["chosen"]
    con = next((c for c in concepts["concepts"] if c.get("id") == chosen), concepts["concepts"][0])
    cap = plan.get("captions") or {}
    L = ["# الشكل التقريبي قبل التنفيذ", "",
         "> ده اللي التنين ناوي يعمله. **مفيش رندر نهائي لحد ما توافق.** قول «موافق» أو قول تعديلك "
         "(مثلاً: «ابدأ بلقطة 3»، «شيل الزووم»، «خليه أسرع»، «ستايل تاني»).", "",
         f"- **الطلب:** {brief.get('task', '')}",
         f"- **المقاس والمدة:** {plan['width']}×{plan['height']} · {plan['fps']} fps · {plan['duration']:.1f} ث "
         f"(المطلوب منك: {brief.get('owner_seconds') or 'مش محدد'} ث · هدف المحرك {brief.get('target_seconds', '?')} ث"
         + (f" · المادة الصالحة {brief.get('footage_seconds')} ث" if brief.get("footage_seconds") else "") + ")",
         f"- **الفكرة المختارة ({chosen}):** {con.get('title', '')} — {con.get('logline', '')}",
         f"- **ليه الفكرة دي:** {str(concepts['decision'].get('why', ''))[:300]}",
         f"- **الستايل:** {look.get('style_name', '')} (`{look.get('style_id', '')}`) · اللون: `{plan.get('grade')}`",
         f"- **الكابشن:** {'شغّال، ستايل ' + str(cap.get('style')) if cap.get('enabled') else 'مقفول'} · "
         f"**المزيكا:** {Path(plan['music']).name if plan.get('music') else 'من غير'}", ""]
    alts = [c for c in concepts["concepts"] if c.get("id") != chosen]
    if alts:
        L += ["**أفكار تانية ممكن تختارها بدالها:** " + " · ".join(f"{c['id']}: {c.get('title', '')}" for c in alts), ""]
    if board:
        L += ["![الستوري بورد](storyboard.jpg)", "", "_الشريط اللي فوق: كل مستطيل قطعة، عرضه = طولها، ولونه = دورها._", ""]
    L += ["## مصفوفة التحركات", "", "| # | الوقت | من فين | الدور | حركة الكاميرا | الانتقال | الكلام | ليه |",
          "|---|---|---|---|---|---|---|---|"]
    L += [f"| {i} | {r['rec_in']:.1f}–{r['rec_out']:.1f} | {r['src']} {r['src_in']:.1f}–{r['src_out']:.1f} "
          f"| {ROLE_AR.get(r['role'], r['role'])} | {r['camera']} | {r['transition']} | {r['words'].replace('|', '/') or '—'} "
          f"| {arabic_reason(r['reason'])} |" for i, r in enumerate(plan["rows"], 1)]
    L += ["", "بعد موافقتك: `python3 <skill>/scripts/dragon.py run dragon_montage go --job <المجلد>` يرندر ويراجع ويصلّح (لحد 3 جولات)."]
    return "\n".join(L) + "\n"


def storyboard(job, cols: int = 6, animatic: bool = False) -> dict:
    job = C.job_dir(job)
    (job / "preview").mkdir(exist_ok=True)
    plan = matrix(job)
    board = sheet(job, plan, cols)
    plan["storyboard"] = "preview/storyboard.jpg" if board else None
    if animatic:
        from .render import render
        try:
            render(job, preview=True, do_verify=False, do_export=False)
            shutil.copy2(job / "render" / "preview.mp4", job / "preview" / "animatic.mp4")
            plan["animatic"] = "preview/animatic.mp4"
        except (OSError, RuntimeError, ValueError):
            pass
    C.save(job / "preview" / "plan.json", plan)
    (job / "preview" / "PLAN_AR.md").write_text(plan_md(job, plan, board), encoding="utf-8")
    return plan


def main(argv=None) -> int:
    C.utf8_stdio()
    p = argparse.ArgumentParser(prog="dragon_montage storyboard", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("storyboard")
    s.add_argument("--job", required=True)
    s.add_argument("--cols", type=int, default=6)
    s.add_argument("--animatic", action="store_true")
    a = p.parse_args(argv)
    plan = storyboard(a.job, a.cols, a.animatic)
    job = Path(a.job).resolve()
    print(json.dumps({"plan": str(job / "preview" / "PLAN_AR.md"), "storyboard": str(job / plan["storyboard"]) if plan["storyboard"] else None,
                      "animatic": str(job / plan["animatic"]) if plan.get("animatic") else None,
                      "cuts": len(plan["rows"]), "duration": plan["duration"]}, ensure_ascii=False))
    return 0
