"""Argument-passing matrix: send the same intended argument through each Windows shell the way an agent
would naturally write it, and record what the target program actually received.

Run:  python -X utf8 run_matrix.py   -> writes matrix.json and matrix.md next to this file.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
PROBE = os.path.join(HERE, "argv_probe.py")
BASH = r"C:\Program Files\Git\usr\bin\bash.exe"
PS = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
WORK = os.path.join(HERE, "gen")
os.makedirs(WORK, exist_ok=True)

CASES = [
    ("space", "hello world"),
    ("empty", ""),
    ("inner_dq", 'say "hi"'),
    ("py_code_dq", 'print("ok")'),
    ("json", '{"k": "v"}'),
    ("trailing_bs", "C:\\dir with space\\"),
    ("bs_dq", 'a\\"b'),
    ("percent_var", "%PATH%"),
    ("percent_lit", "100%"),
    ("bang", "!x!"),
    ("amp_pipe", "a&b|c"),
    ("caret", "a^b"),
    ("redir", "<x>"),
    ("dollar", "$HOME"),
    ("backtick", "a`tb"),
    ("comma", "1,2"),
    ("at", "@x"),
    ("braces", "{x}"),
    ("semicolon", "a;b"),
    ("arabic", "مرحبا عالم"),
    ("posix_flag", "/c"),
    ("posix_path", "/tmp/x.txt"),
    ("eq_posix", "--out=/tmp/y"),
    ("win_path", "C:\\Users\\x"),
    ("dashdash_pct", "--%"),
    ("lone_dq", '"'),
]


def parse(out):
    for line in out.splitlines():
        if line.startswith("PROBE "):
            return json.loads(line[6:])
    return None


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, timeout=60, **kw)
    out = p.stdout.decode("utf-8", "replace")
    err = p.stderr.decode("utf-8", "replace")
    return parse(out), (err.strip() or out.strip())[:300]


def ps_lit(s):  # PowerShell single-quoted literal
    return "'" + s.replace("'", "''") + "'"


def sh_lit(s):  # bash single-quoted literal
    return "'" + s.replace("'", "'\\''") + "'"


def cmd_lit(s):  # the "natural" quoting an agent writes in cmd: wrap in double quotes
    return '"' + s + '"'


results = []
for cid, val in CASES:
    row = {"id": cid, "intended": val}
    # A. Python subprocess list (CreateProcess via list2cmdline) - the reference
    row["python_list"] = run([PY, PROBE, val])
    # B. PowerShell 5.1, single-quoted literal (the textbook-correct way to write a literal)
    ps1 = os.path.join(WORK, f"{cid}.ps1")
    with open(ps1, "w", encoding="utf-8-sig") as f:
        f.write(f"& {ps_lit(PY)} {ps_lit(PROBE)} {ps_lit(val)}\n")
    row["ps51_literal"] = run([PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1])
    # C. cmd.exe batch file, value wrapped in double quotes
    bat = os.path.join(WORK, f"{cid}.cmd")
    with open(bat, "w", encoding="utf-8") as f:
        f.write("@echo off\r\nchcp 65001 >nul\r\n" + f'"{PY}" "{PROBE}" {cmd_lit(val)}\r\n')
    row["cmd_batch"] = run(["cmd.exe", "/d", "/c", bat])
    # D. cmd /c interactive-style line, value wrapped in double quotes (what `cmd /c ...` from another shell does)
    line = f'cmd.exe /d /c ""{PY}" "{PROBE}" {cmd_lit(val)}"'
    row["cmd_c_line"] = run(line)
    # E. Git Bash (MSYS2), single-quoted literal
    sh = os.path.join(WORK, f"{cid}.sh")
    with open(sh, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{sh_lit(PY.replace(chr(92), '/'))} {sh_lit(PROBE.replace(chr(92), '/'))} {sh_lit(val)}\n")
    row["gitbash_literal"] = run([BASH, "--noprofile", "--norc", sh])
    results.append(row)

SHELLS = ["python_list", "ps51_literal", "cmd_batch", "cmd_c_line", "gitbash_literal"]
summary = {s: 0 for s in SHELLS}
md = ["| case | intended | " + " | ".join(SHELLS) + " |", "|---|---|" + "---|" * len(SHELLS)]
for row in results:
    cells = []
    for s in SHELLS:
        got, err = row[s]
        if got is None:
            cells.append("ERR " + err.replace("|", "/").replace("\n", " ")[:60])
            row[s] = {"ok": False, "got": None, "err": err}
            continue
        argv = got["argv"]
        ok = argv == [row["intended"]]
        summary[s] += ok
        row[s] = {"ok": ok, "got": argv, "raw_tail": got["raw"][-120:]}
        cells.append("✅" if ok else "❌ " + json.dumps(argv, ensure_ascii=False).replace("|", "/")[:60])
    md.append(f"| {row['id']} | `{json.dumps(row['intended'], ensure_ascii=False)}` | " + " | ".join(cells) + " |")
md.append("")
md.append("**Correct out of %d:** " % len(results) + ", ".join(f"{s} {summary[s]}" for s in SHELLS))
json.dump(results, open(os.path.join(HERE, "matrix.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(HERE, "matrix.md"), "w", encoding="utf-8").write("\n".join(md))
print("\n".join(md))
