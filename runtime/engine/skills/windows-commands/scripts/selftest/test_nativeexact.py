"""Run all matrix cases through Invoke-NativeExact in a fresh PowerShell 5.1 and compare the argv the child received."""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
HELPER = os.path.join(HERE, "..", "NativeExact.ps1")
PROBE = os.path.join(HERE, "argv_probe.py")
src = open(os.path.join(HERE, "run_matrix.py"), encoding="utf-8").read()
CASES = eval(src.split("CASES = ", 1)[1].split("\n]\n", 1)[0] + "\n]")
# plus a multi-arg case that broke PS 5.1 badly
CASES.append(("multi", None))
MULTI = ['print("ok")', "", "C:\\dir with space\\", 'say "hi there"', "--%", "مرحبا عالم"]

def lit(s):
    return "'" + s.replace("'", "''") + "'"

os.makedirs(os.path.join(HERE, "gen_fix"), exist_ok=True)
ok = 0
lines = []
for cid, val in CASES:
    args = MULTI if cid == "multi" else [val]
    arr = "@(" + ",".join(lit(a) for a in args) + ")"
    code = (f". {lit(os.path.abspath(HELPER))}\n"
            f"$r = Invoke-NativeExact {lit(sys.executable)} (@({lit(PROBE)}) + {arr})\n"
            "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false\n"
            "[Console]::Out.Write($r.StdOut)\n")
    f = os.path.join(HERE, "gen_fix", f"ne_{cid}.ps1")
    open(f, "w", encoding="utf-8-sig").write(code)
    p = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", f], capture_output=True, timeout=60)
    out = p.stdout.decode("utf-8", "replace")
    got = None
    for l in out.splitlines():
        if l.startswith("PROBE "):
            got = json.loads(l[6:])["argv"]
    good = got == args
    ok += good
    lines.append(f"{'OK ' if good else 'BAD'} {cid:14} {json.dumps(got, ensure_ascii=False)[:90] if not good else ''} {p.stderr.decode('utf-8','replace')[:120] if not good else ''}")
print("\n".join(lines))
print(f"Invoke-NativeExact correct: {ok}/{len(CASES)}")
