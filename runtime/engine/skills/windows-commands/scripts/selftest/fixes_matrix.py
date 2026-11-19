"""Verify candidate FIXES for every failure seen in run_matrix.py. Each recipe is the literal text an agent
would type in that shell. Writes fixes.json / fixes.md."""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
PROBE = os.path.join(HERE, "argv_probe.py")
PYF, PROBEF = PY.replace("\\", "/"), PROBE.replace("\\", "/")
BASH = r"C:\Program Files\Git\usr\bin\bash.exe"
PS = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
WORK = os.path.join(HERE, "gen_fix")
os.makedirs(WORK, exist_ok=True)


def parse(out):
    for line in out.splitlines():
        if line.startswith("PROBE "):
            return json.loads(line[6:])["argv"]
    return None


def run(cmd, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run(cmd, capture_output=True, timeout=60, env=e)
    return parse(p.stdout.decode("utf-8", "replace")), (p.stderr.decode("utf-8", "replace") or p.stdout.decode("utf-8", "replace")).strip()[:200]


# (shell, case, intended argv list, literal argument text as typed, note)
PS_RECIPES = [
    ("empty", [""], "'\"\"'", "pass two double quotes inside a single-quoted literal"),
    ("inner_dq", ['say "hi"'], "'say \\\"hi\\\"'", "backslash-escape inner double quotes"),
    ("py_code_dq", ['print("ok")'], "'print(\\\"ok\\\")'", "backslash-escape inner double quotes"),
    ("py_code_sq", ["print('ok')"], "\"print('ok')\"", "or use single quotes inside the code"),
    ("json", ['{"k": "v"}'], "'{\\\"k\\\": \\\"v\\\"}'", "backslash-escape inner double quotes"),
    ("trailing_bs", ["C:\\dir with space\\"], "'C:\\dir with space\\\\'", "double the trailing backslash"),
    ("dashdash_pct_var", ["--%"], "$a", "pass via variable ($a='--%')"),
    ("dashdash_pct_bt", ["--%"], "'-`-%'", "nope: backtick is literal inside single quotes (control)"),
    ("lone_dq", ['"'], "'\\\"'", "backslash-escape"),
    ("stop_parsing", ['say "hi"', "x"], "--% \"say \\\"hi\\\"\" x", "--% then raw CRT text"),
]
CMD_RECIPES = [
    ("inner_dq", ['say "hi"'], '"say \\"hi\\""', "CRT escape \\\" inside the quotes"),
    ("json", ['{"k": "v"}'], '"{\\"k\\": \\"v\\"}"', "CRT escape"),
    ("trailing_bs", ["C:\\dir with space\\"], '"C:\\dir with space\\\\"', "double trailing backslash"),
    ("percent_lit_batch", ["100%"], '"100%%"', "%% in a batch file"),
    ("percent_var_batch", ["%PATH%"], '"%%PATH%%"', "%% in a batch file"),
    ("dashdash_pct", ["--%"], '"--%%"', "%% in a batch file"),
    ("amp_unquoted_caret", ["a&b"], "a^&b", "caret-escape when not quoted"),
]
BASH_RECIPES = [
    ("posix_flag_env", ["/c"], "'/c'", {"MSYS_NO_PATHCONV": "1"}, "MSYS_NO_PATHCONV=1"),
    ("posix_flag_dbl", ["/c"], "'//c'", None, "double leading slash"),
    ("posix_path_env", ["/tmp/x.txt"], "'/tmp/x.txt'", {"MSYS_NO_PATHCONV": "1"}, "MSYS_NO_PATHCONV=1"),
    ("eq_posix_excl", ["--out=/tmp/y"], "'--out=/tmp/y'", {"MSYS2_ARG_CONV_EXCL": "--out="}, "MSYS2_ARG_CONV_EXCL=--out="),
    ("unquoted_winpath", ["C:\\Users\\x"], "C:\\Users\\x", None, "control: unquoted backslashes in bash"),
    ("dq_winpath", ["C:\\Users\\x"], '"C:\\Users\\x"', None, "double-quoted backslashes in bash"),
    ("fwd_winpath", ["C:/Users/x"], "'C:/Users/x'", None, "forward slashes"),
]

rows = []
for cid, want, lit, note in PS_RECIPES:
    f = os.path.join(WORK, f"ps_{cid}.ps1")
    pre = "$a = '--%'\n" if lit == "$a" else ""
    with open(f, "w", encoding="utf-8-sig") as fh:
        fh.write(pre + f"& '{PY}' '{PROBE}' {lit}\n")
    got, err = run([PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", f])
    rows.append(("ps51", cid, lit, note, want, got, got == want, err))
for cid, want, lit, note in CMD_RECIPES:
    f = os.path.join(WORK, f"cmd_{cid}.cmd")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(f'@echo off\r\n"{PY}" "{PROBE}" {lit}\r\n')
    got, err = run(["cmd.exe", "/d", "/c", f])
    rows.append(("cmd_batch", cid, lit, note, want, got, got == want, err))
for cid, want, lit, env, note in BASH_RECIPES:
    f = os.path.join(WORK, f"sh_{cid}.sh")
    with open(f, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"'{PYF}' '{PROBEF}' {lit}\n")
    got, err = run([BASH, "--noprofile", "--norc", f], env=env)
    rows.append(("gitbash", cid, lit, note, want, got, got == want, err))

md = ["| shell | case | typed | note | got | ok |", "|---|---|---|---|---|---|"]
for sh, cid, lit, note, want, got, ok, err in rows:
    g = json.dumps(got, ensure_ascii=False) if got is not None else "ERR " + err[:60]
    md.append(f"| {sh} | {cid} | `{lit.replace('|', '/')}` | {note} | `{g.replace('|', '/')}` | {'✅' if ok else '❌'} |")
open(os.path.join(HERE, "fixes.md"), "w", encoding="utf-8").write("\n".join(md))
json.dump([dict(zip(["shell", "case", "typed", "note", "want", "got", "ok", "err"], r)) for r in rows],
          open(os.path.join(HERE, "fixes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n".join(md))
