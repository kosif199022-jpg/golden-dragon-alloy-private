"""verify_clean_archive.py — independent check of a «.clean» archive before the original is deleted: the clean copy must
contain EXACTLY the original's paths minus the excluded ones (path by path, not just a count), pass an integrity test,
and contain none of the sensitive patterns. Lists names only; never extracts or prints any file content.

  python -X utf8 verify_clean_archive.py ORIGINAL CLEAN
"""
import re
import subprocess
import sys

SEVEN = r"C:\Program Files\7-Zip\7z.exe"
EXCLUDED = re.compile(r"(^|\\)(chrome|sahab)\\profile(\\|$)|(^|\\)sahab\\server\.log$", re.I)
SENSITIVE = re.compile(r"(^|\\)(Cookies|Login Data|Web Data|Local State)(-journal)?$|(^|\\)profile\\|tiktok_cookies|bridge_token", re.I)


def listing(arc):
    out = subprocess.run([SEVEN, "l", "-slt", "-ba", arc], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    files, dirs, path, attrs = set(), set(), None, ""
    for line in out.splitlines() + [""]:
        if line.startswith("Path = "):
            path = line[7:]
        elif line.startswith("Attributes = ") or line.startswith("Folder = "):
            attrs += line
        elif not line.strip() and path is not None:
            (dirs if ("Folder = +" in attrs or attrs.find("D") == 13) else files).add(path)
            path, attrs = None, ""
    return files, dirs


def main(orig, clean):
    of, od = listing(orig)
    cf, cd = listing(clean)
    expected_f = {p for p in of if not EXCLUDED.search(p)}
    expected_d = {p for p in od if not EXCLUDED.search(p)}
    t = subprocess.run([SEVEN, "t", clean], capture_output=True, text=True, encoding="utf-8", errors="replace")
    sens = sorted(p for p in cf | cd if SENSITIVE.search(p))
    res = {
        "original_files": len(of), "original_dirs": len(od), "excluded_files": len(of) - len(expected_f),
        "clean_files": len(cf), "clean_dirs": len(cd),
        "files_equal_expected": cf == expected_f, "dirs_equal_expected": cd == expected_d,
        "missing_from_clean": sorted(expected_f - cf)[:5], "unexpected_in_clean": sorted(cf - expected_f)[:5],
        "sensitive_in_clean": sens[:5], "integrity_7z": "Everything is Ok" in t.stdout,
    }
    for k, v in res.items():
        print(f"{k}: {v}")
    ok = res["files_equal_expected"] and res["dirs_equal_expected"] and not sens and res["integrity_7z"]
    print("VERDICT:", "SAFE TO DELETE ORIGINAL" if ok else "DO NOT DELETE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
