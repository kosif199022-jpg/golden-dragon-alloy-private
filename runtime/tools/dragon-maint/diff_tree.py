"""Compare two directory trees by EOL-normalized sha256.
usage: python -X utf8 diff_tree.py A B [--limit N] [--skip dir1,dir2]
"""
import hashlib
import os
import sys

SKIP = {".git", "__pycache__", "node_modules"}


def walk(root):
    out = {}
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for f in files:
            p = os.path.join(d, f)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            try:
                b = open(p, "rb").read()
            except OSError:
                continue
            out[rel] = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()
    return out


def main():
    a, b = sys.argv[1], sys.argv[2]
    limit = 120
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    if "--skip" in sys.argv:
        SKIP.update(sys.argv[sys.argv.index("--skip") + 1].split(","))
    A, B = walk(a), walk(b)
    only_a = sorted(set(A) - set(B))
    only_b = sorted(set(B) - set(A))
    diff = sorted(k for k in set(A) & set(B) if A[k] != B[k])
    print(f"A files {len(A)}  B files {len(B)}")
    print(f"ONLY IN A ({len(only_a)})")
    for x in only_a[:limit]:
        print("  +", x)
    print(f"ONLY IN B ({len(only_b)})")
    for x in only_b[:limit]:
        print("  -", x)
    print(f"DIFFERENT, EOL-normalized ({len(diff)})")
    for x in diff[:limit]:
        print("  ~", x)


if __name__ == "__main__":
    main()
