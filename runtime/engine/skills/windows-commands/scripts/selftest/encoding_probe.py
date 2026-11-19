"""Measure, in bytes, how a fresh Windows PowerShell 5.1 (-NoProfile) and Python handle Arabic text.
Writes encoding.json / encoding.md."""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(HERE, "gen_enc")
os.makedirs(W, exist_ok=True)
PS = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
AR = "مرحبا"
AR_UTF8 = AR.encode("utf-8")
rows = []


def ps(code, file=None):
    if file:
        return subprocess.run([PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", file], capture_output=True, timeout=60)
    return subprocess.run([PS, "-NoProfile", "-Command", code], capture_output=True, timeout=60)


def head(path, n=12):
    b = open(path, "rb").read()
    return b[:n].hex(" "), len(b)


# 1. .ps1 saved as UTF-8 WITHOUT BOM vs WITH BOM: does PS 5.1 read the Arabic literal correctly?
for bom in (False, True):
    f = os.path.join(W, f"lit_{'bom' if bom else 'nobom'}.ps1")
    with open(f, "w", encoding="utf-8-sig" if bom else "utf-8") as fh:
        fh.write(f"$s = '{AR}'; [Console]::Out.Write($s.Length)\n")
    p = ps(None, f)
    got = p.stdout.decode("ascii", "replace").strip()
    rows.append({"test": f"ps1 {'with' if bom else 'without'} BOM: length of '{AR}' (5 expected)", "result": got, "ok": got == "5"})

# 2. PS 5.1 redirection and cmdlets: which bytes land on disk?
for name, code in [
    ("redirect >", f"'{AR}' > '{W}\\redir.txt'"),
    ("Out-File (default)", f"'{AR}' | Out-File '{W}\\outfile.txt'"),
    ("Set-Content (default)", f"Set-Content -Path '{W}\\setcontent.txt' -Value '{AR}'"),
    ("Set-Content -Encoding UTF8", f"Set-Content -Encoding UTF8 -Path '{W}\\setcontent_utf8.txt' -Value '{AR}'"),
    ("Out-File -Encoding utf8", f"'{AR}' | Out-File -Encoding utf8 '{W}\\outfile_utf8.txt'"),
    ("[IO.File]::WriteAllText (no BOM)", f"[IO.File]::WriteAllText('{W}\\wat.txt', '{AR}')"),
]:
    fn = code.split("'")[-2] if "WriteAllText" not in code else f"{W}\\wat.txt"
    for cand in ("redir", "outfile_utf8", "outfile", "setcontent_utf8", "setcontent", "wat"):
        if f"\\{cand}.txt" in code:
            fn = f"{W}\\{cand}.txt"
            break
    # pass the script via a BOM'd file so the Arabic literal itself is read correctly
    f = os.path.join(W, "w.ps1")
    with open(f, "w", encoding="utf-8-sig") as fh:
        fh.write(code + "\n")
    ps(None, f)
    hx, size = head(fn)
    if hx.startswith("ff fe"):
        kind = "UTF-16LE with BOM"
    elif hx.startswith("ef bb bf"):
        kind = "UTF-8 with BOM"
    elif open(fn, "rb").read().startswith(AR_UTF8):
        kind = "UTF-8 without BOM"
    elif b"?" in open(fn, "rb").read()[:6]:
        kind = "ANSI, Arabic lost as '?'"
    else:
        kind = "other"
    rows.append({"test": f"PS 5.1 {name}", "result": f"{kind} ({hx} ... {size} bytes)", "ok": "UTF-8" in kind})

# 3. Piping Arabic from PS 5.1 to a native program: what bytes arrive on stdin?
f = os.path.join(W, "pipe.ps1")
with open(f, "w", encoding="utf-8-sig") as fh:
    fh.write(f"'{AR}' | & '{sys.executable}' -c \"import sys;print(sys.stdin.buffer.read().hex())\"\n")
got = ps(None, f).stdout.decode("ascii", "replace").strip()
rows.append({"test": "PS 5.1 pipe Arabic -> native stdin (default $OutputEncoding)", "result": got[:40],
             "ok": got.startswith(AR_UTF8.hex())})

# 4. Capturing UTF-8 output of a native program into a PS 5.1 variable (default [Console]::OutputEncoding)
f = os.path.join(W, "capture.ps1")
with open(f, "w", encoding="utf-8-sig") as fh:
    fh.write(f"$o = & '{sys.executable}' -X utf8 -c \"print('{AR}')\"; [Console]::Out.Write(($o.ToCharArray() | % {{ [int]$_ }}) -join ',')\n")
want = ",".join(str(ord(c)) for c in AR)
for cp in (437, 65001):  # result depends on the console code page the shell inherits
    p = subprocess.run(f'cmd.exe /d /c "chcp {cp} >nul & "{PS}" -NoProfile -ExecutionPolicy Bypass -File "{f}""', capture_output=True, timeout=60)
    got = p.stdout.decode("ascii", "replace").strip()
    rows.append({"test": f"PS 5.1 capture python UTF-8 output into a variable (inherited console cp {cp})", "result": got[:60], "ok": got == want})

# 5. Python stdout encodings when output is piped (as an agent tool captures it)
for flags in (["-I"], ["-I", "-X", "utf8"], []):
    p = subprocess.run([sys.executable, *flags, "-c", f"print('{AR}')"], capture_output=True, timeout=30,
                       env={k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")})
    ok = p.returncode == 0 and p.stdout.strip() == AR_UTF8
    err = p.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] if p.returncode else []
    rows.append({"test": f"python {' '.join(flags) or '(no flags, PYTHONUTF8 unset)'} print Arabic to a pipe",
                 "result": ("ok utf-8" if ok else (err[0][:80] if err else p.stdout[:20].hex(" "))), "ok": ok})

json.dump(rows, open(os.path.join(HERE, "encoding.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
md = ["| test | result | ok |", "|---|---|---|"] + [f"| {r['test']} | `{r['result']}` | {'✅' if r['ok'] else '❌'} |" for r in rows]
open(os.path.join(HERE, "encoding.md"), "w", encoding="utf-8").write("\n".join(md))
print("\n".join(md))
