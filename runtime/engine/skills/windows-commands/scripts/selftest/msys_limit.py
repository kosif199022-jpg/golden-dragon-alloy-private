"""Pin the MSYS2 bash argument-length limit and check whether it is per argument or per command line."""
import subprocess

REAL = r"C:\Program Files\Git\usr\bin\bash.exe"


def c_ok(total):
    pad = total - len("x=''; echo ${#x}")
    script = "x='" + "a" * pad + "'; echo ${#x}"
    p = subprocess.run([REAL, "--noprofile", "--norc", "-c", script], capture_output=True, timeout=60)
    return p.returncode == 0 and p.stdout.strip() == str(pad).encode()


lo, hi = 8000, 8400
while hi - lo > 1:
    mid = (lo + hi) // 2
    lo, hi = (mid, hi) if c_ok(mid) else (lo, mid)
print(f"-c script: longest that works = {lo} chars, first that fails = {hi}")

# long POSITIONAL argument with a tiny -c script
for n in (8000, 9000, 20000, 30000):
    p = subprocess.run([REAL, "--noprofile", "--norc", "-c", 'echo ${#1}', "_", "b" * n], capture_output=True, timeout=60)
    print(f"positional arg {n}: rc={p.returncode} got={p.stdout.decode().strip() or p.stderr.decode().strip()[:80]}")

# two -c-sized pieces: total line > 8192 but each argument < 8192
p = subprocess.run([REAL, "--noprofile", "--norc", "-c", 'echo ${#1} ${#2}', "_", "c" * 6000, "d" * 6000], capture_output=True, timeout=60)
print(f"two 6000-char args (line ~12k): rc={p.returncode} got={p.stdout.decode().strip() or p.stderr.decode().strip()[:80]}")

# Arabic payload: is the limit in characters or bytes?
pad = 4100
script = "x='" + "ب" * pad + "'; echo ${#x}"
p = subprocess.run([REAL, "--noprofile", "--norc", "-c", script], capture_output=True, timeout=60, env={"LANG": "C.UTF-8", "SYSTEMROOT": r"C:\Windows"})
print(f"-c with {pad} Arabic letters ({len(script)} chars, ~{len(script.encode())} UTF-8 bytes): rc={p.returncode} got={p.stdout.decode().strip() or p.stderr.decode('utf-8','replace').strip()[:80]}")
