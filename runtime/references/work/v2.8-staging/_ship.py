"""Ship the INSTALLED red-dragon as one zip on the Desktop, following the `ship` playbook:
  1 secret scan (masked output, stops on a hit)   2 exclude caches / settings / lock
  3 MANIFEST_SHA256.json + SHA256SUMS.txt for 2.8.1   4 zip with one folder inside, testzip, every entry re-hashed vs the manifest
    python -I -X utf8 _ship.py            scan only
    python -I -X utf8 _ship.py --apply    scan + manifest + zip + verify
"""
import datetime, hashlib, json, re, sys, zipfile
from pathlib import Path

INST = Path.home() / ".claude" / "skills" / "red-dragon"
OUT = Path.home() / "OneDrive" / "Desktop" / "red-dragon-v2.8.1.zip"
APPLY = "--apply" in sys.argv
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".ruff_cache", ".pytest_cache", ".mypy_cache", ".venv"}
SKIP_NAMES = {"settings.json", ".env", ".rd-lock.json"}
ROOT_SKIP = {"MANIFEST_SHA256.json", "SHA256SUMS.txt"}  # regenerated below; engine/ and library/ keep their own


def allowed(rel, s):
    """Known non-secrets: a YARA rule that *detects* private keys, and AWS's documented example key id."""
    if rel.endswith(".yar") and s.startswith("-----BEGIN"):
        return True
    return s == "AKIAIOSFODNN7EXAMPLE"
SECRET = re.compile(rb"(sk-ant-[A-Za-z0-9_\-]{20,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}"
                    rb"|bridge_token[\"']?\s*[:=]\s*[\"'][A-Za-z0-9_\-]{12,}|-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----)")


def sha(b):
    return hashlib.sha256(b).hexdigest()


files, skipped = [], []
for f in sorted(INST.rglob("*")):
    if not f.is_file():
        continue
    rel = f.relative_to(INST).as_posix()
    if any(p in SKIP_DIRS for p in f.relative_to(INST).parts) or f.name in SKIP_NAMES or rel in ROOT_SKIP or f.suffix == ".pyc":
        skipped.append(rel)
        continue
    files.append(rel)
hits, allowed_hits = [], []
for rel in files:
    b = (INST / rel).read_bytes()
    for m in SECRET.finditer(b):
        s = m.group(0).decode("latin-1")
        (allowed_hits if allowed(rel, s) else hits).append(f"{rel}: {s[:7]}…({len(s)} chars)")
print(json.dumps({"files": len(files), "skipped": len(skipped), "skipped_sample": [s for s in skipped if "__pycache__" not in s][:20],
                  "secret_hits": hits[:40], "secret_hit_count": len(hits), "allowed_examples": allowed_hits}, ensure_ascii=False, indent=1))
if hits:
    raise SystemExit("secret hits: nothing written")
if not APPLY:
    raise SystemExit(0)
if OUT.exists():
    raise SystemExit(f"{OUT} already exists: not overwritten")
old = json.loads((INST / "MANIFEST_SHA256.json").read_text(encoding="utf-8")) if (INST / "MANIFEST_SHA256.json").is_file() else {}
hashes = {rel: sha((INST / rel).read_bytes()) for rel in files}
man = {**{k: v for k, v in old.items() if k != "files"}, "schema": old.get("schema", "red-dragon.sha256-manifest.v1"), "version": "2.8.1",
       "date": datetime.date.today().isoformat(), "count": len(hashes), "files": hashes}
(INST / "MANIFEST_SHA256.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
(INST / "SHA256SUMS.txt").write_text("".join(f"{h}  {rel}\n" for rel, h in hashes.items()), encoding="utf-8")
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for rel in files + ["MANIFEST_SHA256.json", "SHA256SUMS.txt"]:
        z.write(INST / rel, "red-dragon/" + rel)
bad_entries = []
with zipfile.ZipFile(OUT) as z:
    tz = z.testzip()
    names = set(z.namelist())
    for rel, h in hashes.items():
        if sha(z.read("red-dragon/" + rel)) != h:
            bad_entries.append(rel)
    missing = [rel for rel in hashes if "red-dragon/" + rel not in names]
print(json.dumps({"zip": str(OUT), "mb": round(OUT.stat().st_size / 1e6, 1), "entries": len(names), "sha256": sha(OUT.read_bytes()),
                  "testzip": tz or "ok", "hash_mismatch": bad_entries[:10], "missing": missing[:10], "manifest_version": man["version"]}, ensure_ascii=False, indent=1))
