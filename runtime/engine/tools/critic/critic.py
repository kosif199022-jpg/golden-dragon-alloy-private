#!/usr/bin/env python3
"""v1990 — the blind critic: a reviewer who never read the script scores every version on the same eight axes.

  critic axes                                         the eight axes and what each one asks
  critic brief FILM --out DIR [--ref REF] [--version N] [--title T]
                                                      review packet: stills with timecodes, the rules, an empty scorecard
  critic score SCORECARD.json [--film FILM] [--ledger FILE.jsonl] [--min X]
                                                      validate a filled scorecard, mean, weakest axes, append to the ledger
  critic compare OURS.json REF.json                   same axes, side by side: where we win and where we lose
  critic ledger FILE.jsonl                            the score of every version, in order

It measures nothing about the film by itself and it calls no model: a human or a separate agent fills the scorecard.
A scorecard filled by whoever built the film, or by anyone who read the script, is labelled SELF, never BLIND.
Exit: 0 ok, 1 scorecard not valid / below --min / film mismatch, 2 bad input.
"""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

AXES = [
    ("hook", "الهوك", "أول ثانيتين: هل بيوقّف الصباع؟ هل باين الفيلم عن إيه؟"),
    ("clarity", "الوضوح", "الفكرة أو الحكاية بتوصل من الصورة والصوت، من غير شرح مكتوب؟"),
    ("rhythm", "الإيقاع", "طول اللقطات والقطع على الصوت: فيه لقطة مملة أو مستعجلة؟"),
    ("picture", "الصورة", "الكادر والإضاءة واللون: كل لقطة ليها مصدر نور واحد مفهوم وباليتة واحدة؟"),
    ("subject", "البطل", "الوش أو الشخصية أو المنتج: الرسم والملامح والتمثيل وثبات الشكل"),
    ("motion", "الحركة", "وزن وتلامس: رجل طايرة؟ إيد داخلة في حاجة؟ فريم بينط؟"),
    ("sound", "الصوت", "الكلام واضح؟ المزيكا والمؤثرات في مكانها وعلى الفريم؟ المستوى ثابت؟"),
    ("finish", "التشطيب", "النص مقري وبعيد عن الوش، الحواف نضيفة، الكريدت موجود، مفيش سواد ولا رعشة"),
]
IDS = [a[0] for a in AXES]
SCHEMA = "black-dragon.critic.v1990"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        d = float(r.stdout.strip())
    except ValueError:
        raise ValueError("cannot read duration of " + str(path))
    if not d > 0:
        raise ValueError("zero duration: " + str(path))
    return d


def sheets(video, out, stem):
    """Evenly spaced stills with burned-in timecodes, 24 per page (plain tiles when drawtext is not available)."""
    d = duration(video)
    count = max(24, min(96, math.ceil(d / 1.5)))
    count = math.ceil(count / 24) * 24
    label = "drawtext=text='%{pts\\:hms}':x=6:y=6:fontsize=h/12:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=4,"
    made = []
    for vf in (f"fps={count}/{d:.6f},{label}scale=220:-2,tile=6x4:padding=3:margin=3", f"fps={count}/{d:.6f},scale=220:-2,tile=6x4:padding=3:margin=3"):
        for old in out.glob(f"{stem}_*.jpg"):
            old.unlink()
        r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(video), "-map", "0:v:0", "-vf", vf, "-q:v", "4",
                            str(out / f"{stem}_%02d.jpg")], capture_output=True, text=True)
        made = sorted(p.name for p in out.glob(f"{stem}_*.jpg"))
        if r.returncode == 0 and made:
            break
    if not made:
        raise ValueError("ffmpeg could not make stills for " + str(video))
    return made, round(d, 3)


def template(film, digest, version, title):
    return {"schema": SCHEMA, "film": film, "sha256": digest, "version": version, "title": title,
            "reviewer": {"name": "", "blind": None, "read_script": None, "is_builder": None},
            "axes": {i: {"score": None, "evidence": [{"t": None, "note": ""}]} for i in IDS},
            "top_fixes": ["", "", ""], "would_watch_again": None}


def cmd_axes(a):
    for i, ar, q in AXES:
        print(f"{i:<8} {ar}: {q}")
    return 0


def cmd_brief(a):
    film, out = Path(a.film), Path(a.out)
    if not film.is_file() or (a.ref and not Path(a.ref).is_file()):
        raise ValueError("film or reference not found")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ValueError("ffmpeg and ffprobe are required")
    out.mkdir(parents=True, exist_ok=True)
    made, d = sheets(film, out, "film_sheet")
    digest = sha256_file(film)
    (out / "scorecard.json").write_text(json.dumps(template(film.name, digest, a.version, a.title), ensure_ascii=False, indent=1), encoding="utf-8")
    ref_made = []
    if a.ref:
        ref_made, rd = sheets(Path(a.ref), out, "ref_sheet")
        (out / "scorecard_ref.json").write_text(json.dumps(template(Path(a.ref).name, sha256_file(a.ref), 0, "reference"),
                                                            ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# مراجعة عمياء — {film.name} (النسخة {a.version}، {d} ث)", "",
             "إنت ناقد ماشافش السكريبت ولا الخطة ولا البرومبتات، وماتطلبهمش. احكم على اللي على الشاشة وفي السماعة بس.", "",
             "1. اتفرج على الفيلم مرة واحدة بالسرعة العادية والصوت شغال، واكتب أول انطباع في سطر.",
             "2. افتح ورق الكادرات (" + "، ".join(made) + ") وارجع للفيلم عند أي وقت شكّيت فيه.",
             "3. املا `scorecard.json`: لكل محور درجة من 0 لـ10 ودليل واحد على الأقل (`t` بالثانية + ملاحظة تتشاف).",
             "4. اكتب 3 تصليحات بالترتيب: الأهم الأول. وماتجاملش: 6 يعني مقبول، 8 يعني ممتاز، 10 مابتتكتبش.",
             "5. املا `reviewer`: `blind` و`read_script` و`is_builder` بصدق. درجة اللي بنى الفيلم بتتسجل SELF.", "",
             "## المحاور"] + [f"- **{ar}** (`{i}`): {q}" for i, ar, q in AXES]
    if a.ref:
        lines += ["", "## المرجع", f"قيّم المرجع على نفس المحاور في `scorecard_ref.json` ({'، '.join(ref_made)})، من صور متقابلة على نفس المحور.",
                  "بعدها: `critic compare scorecard.json scorecard_ref.json`."]
    (out / "critic_brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"brief": str(out / "critic_brief.md"), "scorecard": str(out / "scorecard.json"), "sheets": made,
                      "ref_sheets": ref_made, "sha256": digest}, ensure_ascii=False))
    return 0


def load_card(path):
    try:
        c = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read scorecard {path}: {e}")
    if not isinstance(c, dict) or c.get("schema") != SCHEMA or not isinstance(c.get("axes"), dict):
        raise ValueError("not a critic scorecard (schema " + SCHEMA + ")")
    return c


def problems(c):
    bad = []
    for i in IDS:
        ax = c["axes"].get(i)
        s = ax.get("score") if isinstance(ax, dict) else None
        if isinstance(s, bool) or not isinstance(s, (int, float)) or not 0 <= s <= 10:
            bad.append(f"{i}: score 0..10 missing")
            continue
        ev = [e for e in (ax.get("evidence") or []) if isinstance(e, dict) and str(e.get("note", "")).strip()
              and isinstance(e.get("t", e.get("frame")), (int, float)) and not isinstance(e.get("t", e.get("frame")), bool)]
        if not ev:
            bad.append(f"{i}: needs evidence with a time (t) or frame and a note")
    r = c.get("reviewer") if isinstance(c.get("reviewer"), dict) else {}
    for k in ("blind", "read_script", "is_builder"):
        if not isinstance(r.get(k), bool):
            bad.append(f"reviewer.{k}: true or false")
    if not [t for t in (c.get("top_fixes") or []) if str(t).strip()]:
        bad.append("top_fixes: at least one")
    return bad


def summary(c):
    scores = {i: float(c["axes"][i]["score"]) for i in IDS}
    r = c["reviewer"]
    label = "BLIND" if r["blind"] and not r["read_script"] and not r["is_builder"] else "SELF"
    order = sorted(IDS, key=lambda i: scores[i])
    return {"film": c.get("film"), "sha256": c.get("sha256"), "version": c.get("version"), "label": label,
            "mean": round(sum(scores.values()) / len(scores), 2), "axes": scores, "weakest": order[:2], "strongest": order[-2:][::-1],
            "top_fixes": [str(t).strip() for t in c.get("top_fixes", []) if str(t).strip()]}


def cmd_score(a):
    c = load_card(a.scorecard)
    bad = problems(c)
    if bad:
        print("scorecard not valid:\n  " + "\n  ".join(bad), file=sys.stderr)
        return 1
    s = summary(c)
    if a.film:
        if not Path(a.film).is_file():
            raise ValueError("film not found")
        if sha256_file(a.film) != s["sha256"]:
            print("الدرجة دي لرندر تاني: بصمة الفيلم مش زي اللي في البطاقة. اعمل brief جديد للنسخة دي.", file=sys.stderr)
            return 1
    names = {i: ar for i, ar, _ in AXES}
    print(f"{s['film']} v{s['version']}: {s['mean']}/10  [{s['label']}]")
    print("  " + " · ".join(f"{names[i]} {s['axes'][i]:g}" for i in IDS))
    print(f"  الجولة الجاية هنا: {names[s['weakest'][0]]} ثم {names[s['weakest'][1]]}  (الأقوى: {names[s['strongest'][0]]})")
    if s["label"] == "SELF":
        print("  ⚠ الدرجة دي من اللي بنى الفيلم أو من حد قرا السكريبت: مش مراجعة عمياء، وماتتكتبش في التسليم كحكم مستقل.")
    if a.ledger:
        row = dict(s, at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        with open(a.ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    if a.min is not None and s["mean"] < a.min:
        print(f"  أقل من الحد {a.min:g}", file=sys.stderr)
        return 1
    return 0


def cmd_compare(a):
    ours, ref = load_card(a.ours), load_card(a.ref)
    for name, c in (("ours", ours), ("ref", ref)):
        bad = problems(c)
        if bad:
            print(f"{name} scorecard not valid:\n  " + "\n  ".join(bad), file=sys.stderr)
            return 1
    so, sr = summary(ours), summary(ref)
    names = {i: ar for i, ar, _ in AXES}
    print(f"{'المحور':<10} {'إحنا':>6} {'المرجع':>7} {'الفرق':>7}")
    rows = []
    for i in IDS:
        d = so["axes"][i] - sr["axes"][i]
        rows.append((d, i))
        print(f"{names[i]:<10} {so['axes'][i]:>6g} {sr['axes'][i]:>7g} {d:>+7.1f}")
    rows.sort()
    print(f"المتوسط: {so['mean']} ضد {sr['mean']}  [{so['label']} / {sr['label']}]")
    print(f"بنخسر في: {names[rows[0][1]]} ({rows[0][0]:+.1f})  ·  بنكسب في: {names[rows[-1][1]]} ({rows[-1][0]:+.1f})")
    print("الجولة الجاية تروح للمحور اللي بنخسر فيه، مش لزيادة في اللي كسبانين فيه.")
    return 0


def cmd_ledger(a):
    p = Path(a.ledger)
    if not p.is_file():
        raise ValueError("ledger not found")
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    for r in rows:
        print(f"v{r.get('version')}  {r.get('mean')}/10  [{r.get('label')}]  أضعف: {', '.join(r.get('weakest', []))}  {r.get('at', '')}")
    blind = [r["mean"] for r in rows if r.get("label") == "BLIND"]
    if len(blind) >= 2:
        print(f"اتجاه المراجعات العمياء: {blind[0]} ← {blind[-1]} ({blind[-1] - blind[0]:+.2f})")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="critic", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("axes")
    b = sub.add_parser("brief")
    b.add_argument("film")
    b.add_argument("--out", required=True)
    b.add_argument("--ref")
    b.add_argument("--version", type=int, default=1)
    b.add_argument("--title", default="")
    s = sub.add_parser("score")
    s.add_argument("scorecard")
    s.add_argument("--film")
    s.add_argument("--ledger")
    s.add_argument("--min", type=float)
    c = sub.add_parser("compare")
    c.add_argument("ours")
    c.add_argument("ref")
    g = sub.add_parser("ledger")
    g.add_argument("ledger")
    a = ap.parse_args(argv)
    fn = {"axes": cmd_axes, "brief": cmd_brief, "score": cmd_score, "compare": cmd_compare, "ledger": cmd_ledger}.get(a.cmd)
    if not fn:
        ap.print_help()
        return 2
    try:
        return fn(a)
    except ValueError as e:
        print(f"critic: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
