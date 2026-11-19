"""Re-measure how THIS Windows machine reads commands (run after a Windows/PowerShell/Git update).

  python -X utf8 selftest.py            # full run, ~2-4 minutes (spawns ~150 short processes)
  python -X utf8 selftest.py --quick    # only Invoke-NativeExact + linter self-check

Prints a summary and compares it to the baseline measured on 2026-11-11.
Generated scratch files go to selftest/gen*, which is safe to delete.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ST = os.path.join(HERE, "selftest")
BASELINE = {"python_list": 26, "ps51_literal": 18, "cmd_batch": 18, "cmd_c_line": 20, "gitbash_literal": 23,
            "fixes_ok": 21, "fixes_total": 24, "nativeexact": "27/27"}


def run(script):
    p = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ST, script)], capture_output=True, timeout=900)
    return p.stdout.decode("utf-8", "replace"), p.returncode


def lint_selfcheck():
    sys.path.insert(0, HERE)
    from wincmd_lint import lint
    cases = [
        ("powershell", "python -c 'print(\"ok\")'", "PS002"), ("powershell", "git add -A && git commit -m x", "PS001"),
        ("powershell", "python s.py '' out", "PS003"), ("powershell", "Set-Content a.txt 'مرحبا'", "PS008"),
        ("powershell", "python -I x.py", "X001"), ("bash", "cmd /c dir", "SH001"), ("bash", "ls C:\\Users\\x", "SH002"),
        ("cmd", 'python p.py "100%"', "CMD001"),
        ("powershell", "python -c \"print('ok')\"", None), ("bash", "MSYS_NO_PATHCONV=1 cmd /c dir", None),
        ("bash", "ls 'C:\\Users\\x'", None), ("powershell", "Get-ChildItem -Recurse | Select-Object -First 5", None),
    ]
    bad = []
    for shell, cmd, want in cases:
        rules = {h["rule"] for h in lint(cmd, shell) if h["level"] != "info"}
        if (want and want not in rules) or (not want and rules):
            bad.append(f"{shell}: {cmd} -> {sorted(rules)} (want {want})")
    return len(cases) - len(bad), len(cases), bad


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    quick = "--quick" in sys.argv
    print("== linter self-check")
    ok, n, bad = lint_selfcheck()
    print(f"   {ok}/{n}", *bad, sep="\n   ")
    print("== Invoke-NativeExact (fresh Windows PowerShell 5.1)")
    out, _ = run("test_nativeexact.py")
    m = re.search(r"correct: (\d+/\d+)", out)
    print("  ", m.group(1) if m else out[-300:], "(baseline", BASELINE["nativeexact"] + ")")
    if quick:
        return
    print("== argument matrix (5 routes x 26 arguments)")
    out, _ = run("run_matrix.py")
    m = re.search(r"\*\*Correct out of \d+:\*\* (.*)", out)
    print("  ", m.group(1) if m else out[-300:])
    print("   baseline:", ", ".join(f"{k} {v}" for k, v in BASELINE.items() if k in ("python_list", "ps51_literal", "cmd_batch", "cmd_c_line", "gitbash_literal")))
    print("== fixes matrix")
    run("fixes_matrix.py")
    rows = json.load(open(os.path.join(ST, "fixes.json"), encoding="utf-8"))
    print(f"   {sum(r['ok'] for r in rows)}/{len(rows)} ok (baseline {BASELINE['fixes_ok']}/{BASELINE['fixes_total']}; the 3 expected failures are controls: two --% cases and the unquoted bash path)")
    print("== encoding (fresh PS 5.1 + python)")
    run("encoding_probe.py")
    rows = json.load(open(os.path.join(ST, "encoding.json"), encoding="utf-8"))
    for r in rows:
        print(f"   {'OK ' if r['ok'] else 'BAD'} {r['test']}")
    print("   (BAD = the Windows behaviour the rules guard against; expected. OK = the fix works.)")
    print("\nDetails: selftest/matrix.md, fixes.md, encoding.md. If numbers changed, update references/ and the rules.")


if __name__ == "__main__":
    main()
