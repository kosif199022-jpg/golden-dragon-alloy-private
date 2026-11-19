"""Kling 4.0 master-prompt gate (port of living-site tools/kling_lint.py): text only, never calls Kling.

FAIL: headers (in order; blocks of 10 s or less may use the short set), duration (3..30 s, Flash 3..20 s),
timing (ranges start at 0, touch end to end, end at the duration), refs (roles; "not inherited"; storyboard
not rendered), limits (Omni 10 images / 5 videos / 7 elements; Keyframes takes images only), polish, brands,
mood-cam, arabic-dlg (no Arabic in AUDIO), wide-face (24 mm / 84° on a close-up).
warn: negatives, more than 2 moves in a shot, edited shots over 6 s, no "Exactly N people" lock."""
import json
import re
from pathlib import Path

R = json.loads((Path(__file__).resolve().parent / "data" / "lint_rules.json").read_text(encoding="utf-8"))
FULL, SHORT = R["headers_full"], R["headers_short"]
NEG_OK, NEG = re.compile(R["neg_ok"], re.I), re.compile(R["neg"], re.I)
ARABIC, RANGE = re.compile(R["arabic"]), re.compile(R["range"], re.M)
LIMITS = (("Image", 10), ("Video", 5), ("Element", 7))
WARN_SECTIONS = ("POSITIVE CONSTRAINTS", "QUALITY", "STYLE", "CAMERA", "ACTION TIMING", "LIGHTING", "PHYSICS")


def sections(text):
    """Header name -> body for lines that start with a known header in capitals; plus the order seen."""
    known = sorted(set(FULL), key=len, reverse=True)
    found, order, cur = {}, [], None
    for line in text.splitlines():
        s = line.strip()
        head = next((h for h in known if s.startswith(h) and (s == h or not s[len(h):len(h) + 1].isalpha())), None)
        if head and s.upper().startswith(head):
            cur = head
            order.append(head)
            found.setdefault(head, [])
            rest = s[len(head):].strip(" :—-")
            if rest:
                found[head].append(rest)
        elif cur:
            found[cur].append(line)
    return {k: "\n".join(v) for k, v in found.items()}, order


def _timing(ranges, duration):
    if not ranges:
        return False, 'no "0.0-4.0s" ranges in ACTION TIMING'
    ok, note = True, ""
    if ranges[0][0] != 0:
        ok, note = False, f"starts at {ranges[0][0]} s, not 0"
    for (_, b1, _), (a2, _, _) in zip(ranges, ranges[1:]):
        if abs(b1 - a2) > 1e-6:
            ok, note = False, f"gap or overlap between {b1} s and {a2} s (gaps get filled with shots you did not ask for)"
            break
    if any(b <= a for a, b, _ in ranges):
        ok, note = False, "a range ends before it starts"
    if ok and duration is not None and abs(ranges[-1][1] - duration) > 1e-6:
        ok, note = False, f"ranges end at {ranges[-1][1]} s but the block is {duration} s"
    return ok, note


def _refs(refs):
    bad = []
    for line in refs.splitlines():
        m = re.match(r"\s*(@(?:Image|Video|Element)\d+)\s*[—–-]+\s*(.*)", line)
        if not m:
            continue
        tag, body = m.groups()
        role = re.match(r"([A-Z][A-Z /]+?)\s*(?:[—–-]|:|$)", body)
        if not role:
            bad.append(f"{tag} has no ROLE")
            continue
        r = role.group(1).strip()
        if r.startswith(("CHARACTER", "LOCATION")) and "not inherited" not in body.lower():
            bad.append(f"{tag} {r} does not say what is not inherited")
        if r.startswith("STORYBOARD") and "do not render the storyboard itself" not in body.lower():
            bad.append(f'{tag} STORYBOARD lacks "Do not render the storyboard itself."')
    return bad


def _words(pattern, low):
    return sorted(set(m.group(0) for m in re.finditer(pattern, low)))


def lint(text, duration=None, flash=False):
    """[{name, status: ok|warn|FAIL, note}] for one master prompt."""
    res = []

    def test(name, ok, note="", warn=False):
        res.append({"name": name, "status": "ok" if ok else ("warn" if warn else "FAIL"), "note": note})

    secs, order = sections(text)
    if duration is None:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)\b", secs.get("SCENE CONTEXT", ""))
        duration = float(m.group(1)) if m else None
    top = 20 if flash else 30
    test("duration", duration is not None and 3 <= duration <= top,
         f"{duration} s (allowed 3..{top})" if duration is not None else "no duration in SCENE CONTEXT; pass --duration")

    want = SHORT if duration is not None and duration <= 10 and not all(h in order for h in FULL) else FULL
    missing = [h for h in want if h not in order]
    seq = [h for h in order if h in want]
    in_order = seq == sorted(seq, key=want.index)
    test("headers", not missing and in_order,
         ("missing: " + ", ".join(missing)) if missing else ("" if in_order else "blocks out of order: " + " > ".join(seq)))

    ranges = [(float(a), float(b), rest) for a, b, rest in RANGE.findall(secs.get("ACTION TIMING", ""))]
    ok, note = _timing(ranges, duration)
    test("timing", ok, note or f"{len(ranges)} shots/phases add up to {ranges[-1][1] if ranges else 0} s")

    bad = _refs(secs.get("ACTIVE REFERENCES", ""))
    used = {k: set(re.findall(r"@" + k + r"(\d+)", text)) for k, _ in LIMITS}
    test("refs", not bad, "; ".join(bad) if bad else f"{sum(len(v) for v in used.values())} references with roles")
    over = [f"{k} {len(used[k])}>{lim}" for k, lim in LIMITS if len(used[k]) > lim]
    if re.search(r"\bkeyframes?\s+mode\b", text, re.I) and (used["Video"] or used["Element"]):
        over.append("Keyframes mode takes images only; it cannot be combined with Omni references")
    test("limits", not over, "; ".join(over))

    low = text.lower()
    for name, key, hint in (("polish", "polish", " (use fine film grain, natural skin texture with pores)"),
                            ("brands", "brands", " (describe the look instead)"),
                            ("mood-cam", "mood_cam", " (name the move: dolly-in, side-tracking, crane up)")):
        hits = _words(R[key], low)
        test(name, not hits, ", ".join(hits) + hint if hits else "")
    arabic = ARABIC.search(secs.get("AUDIO", ""))
    test("arabic-dlg", not arabic, "Arabic script in AUDIO: Kling 4.0 has no Arabic lip sync" if arabic else "")
    wide = [f"{a}-{b}s" for a, b, rest in ranges
            if re.search(r"close-?up", rest, re.I) and re.search(r"\b(24\s*mm|84\s*°|84 deg)", rest, re.I)]
    test("wide-face", not wide, ("24 mm / 84° on a close-up at " + ", ".join(wide) + " (use 50 or 85 mm)") if wide else "")

    negs = [line.strip()[:60] for name in WARN_SECTIONS for line in secs.get(name, "").splitlines()
            if NEG.search(NEG_OK.sub("", line))]
    test("negatives", not negs, (f"{len(negs)} negative line(s), rewrite as positive constraints: " + " | ".join(negs[:3])) if negs else "", warn=True)
    many = []
    for a, b, rest in ranges:
        n = sum(1 for mv in R["moves"] if re.search(r"\b" + re.escape(mv) + r"\b", rest, re.I))
        if n > 2:
            many.append(f"{a}-{b}s ({n})")
    test("moves", not many, ("more than 2 moves: " + ", ".join(many)) if many else "", warn=True)
    multi = re.search(r"multi-?shot|hard cuts?", secs.get("FORMAT MODE", ""), re.I)
    long_ = [f"{a}-{b}s" for a, b, _ in ranges if multi and b - a > 6]
    test("shot-len", not long_, ("edited shots over 6 s: " + ", ".join(long_)) if long_ else "", warn=True)
    head = re.search(r"\bexactly\s+(\w+)\s+(people|person|characters?|men|women)", low)
    test("headcount", head, "" if head else 'no "Exactly N people" lock', warn=True)
    return res


def report(res, as_json):
    """Print the lint like the gate does; 0 = pass, 1 = a FAIL."""
    passed = all(r["status"] != "FAIL" for r in res)
    if as_json:
        print(json.dumps({"result": "PASS" if passed else "FAIL", "tests": res}, ensure_ascii=False, indent=1))
    else:
        for r in res:
            print(f"{r['status']:<4} {r['name']}" + (f": {r['note']}" if r["note"] else ""))
        print("PASS" if passed else "FAIL")
    return 0 if passed else 1
