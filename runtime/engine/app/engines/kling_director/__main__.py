"""python -m engines.kling_director plan|build|check [...]   |   --self-test

  plan SECONDS [--flash] [--json]
  build --task "the story" --seconds N --out DIR [--ratio 9:16] [--flash] [--json]
  check PROMPT.txt [--duration N] [--flash] [--json]
Exit 0 = every block passes the lint, 1 = a block fails, 2 = usage error. Never calls Kling; spends no credits."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

from . import RATIOS, build, lint_prompt, plan, report, self_test


def run_self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        checks = self_test(tmp)
    for name, ok in checks:
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
    passed = all(ok for _, ok in checks)
    print("SELF-TEST PASS" if passed else "SELF-TEST FAIL")
    return 0 if passed else 1


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--self-test"]:
        return run_self_test()
    ap = argparse.ArgumentParser(prog="python -m engines.kling_director", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true", help="known-answer checks, then exit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="split a film into generation blocks")
    p.add_argument("seconds", type=int)
    b = sub.add_parser("build", help="write master prompts, storyboards and plan.json, then lint them")
    b.add_argument("--task", required=True, help="the story line, in any language")
    b.add_argument("--seconds", type=int, required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--ratio", choices=RATIOS, default="9:16")
    c = sub.add_parser("check", help="lint one master prompt")
    c.add_argument("prompt", type=Path)
    c.add_argument("--duration", type=float)
    for x in (p, b, c):
        x.add_argument("--flash", action="store_true")
        x.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd in ("plan", "build") and a.seconds < 3:
        ap.error("seconds must be 3 or more (Kling's shortest generation)")
    if a.cmd == "plan":
        rows = plan(a.seconds, a.flash)
        if a.json:
            print(json.dumps({"blocks": [list(r) for r in rows]}))
        else:
            for i, (x, y) in enumerate(rows, 1):
                print(f"block {i}: {x}-{y} s ({y - x} s)")
        return 0
    if a.cmd == "build":
        if not a.task.strip():
            ap.error("--task is empty")
        doc = build(a.task, a.seconds, a.out, a.ratio, a.flash)
        if a.json:
            print(json.dumps(doc, ensure_ascii=False, indent=1))
        else:
            for r in doc["blocks"]:
                extra = f" (failed: {', '.join(r['lint']['failed'])})" if r["lint"]["failed"] else ""
                print(f"block {r['block']}: {r['film_range_s'][0]}-{r['film_range_s'][1]} s -> {r['prompt']}, "
                      f"{r['storyboard']}: {r['lint']['result']}{extra}")
            print(doc["result"], "-", a.out / "plan.json", "- no credits spent")
        return 0 if doc["result"] == "PASS" else 1
    try:
        text = a.prompt.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read {a.prompt}: {exc}", file=sys.stderr)
        return 2
    return report(lint_prompt(text, a.duration, a.flash), a.json)


if __name__ == "__main__":
    sys.exit(main())
