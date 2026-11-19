"""Is the 8186 limit about the whole -c script, or about one quoted token / one line inside it?"""
import subprocess

REAL = r"C:\Program Files\Git\usr\bin\bash.exe"


def run(script):
    p = subprocess.run([REAL, "--noprofile", "--norc", "-c", script], capture_output=True, timeout=60)
    return p.returncode, (p.stdout.decode().strip() or p.stderr.decode().strip())[-70:]


N = 12000
print("A unquoted single line  :", len(f": {'a'*N}; echo ok"), run(f": {'a'*N}; echo ok"))
many = "; ".join(f"x{i}='{'a'*90}'" for i in range(130)) + "; echo ok"
print("B many short quotes     :", len(many), run(many))
lines = "\n".join(f"x{i}='{'a'*90}'" for i in range(130)) + "\necho ok"
print("C many lines            :", len(lines), run(lines))
heredoc = "cat <<'EOF' | wc -c\n" + "\n".join("a" * 99 for _ in range(120)) + "\nEOF"
print("D quoted heredoc 12k    :", len(heredoc), run(heredoc))
one_dq = 'x="' + "a" * N + '"; echo ${#x}'
print("E one double-quoted 12k :", len(one_dq), run(one_dq))
