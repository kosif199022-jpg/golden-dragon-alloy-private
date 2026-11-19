"""Private append-only Golden Dragon memory and owner-history snapshots.

This module belongs only in the PRIVATE Golden Dragon Alloy repository.
Nothing is uploaded automatically. Sync requires an explicit --push and
rejects any GitHub repository that is not confirmed private.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "owner-memory"
LIVE = Path(os.environ.get("RED_DRAGON_HOME") or Path.home() / ".red-dragon")
MAX_FILE_BYTES = 40 * 1024 * 1024


def hash_file(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for piece in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(piece)
    return digest.hexdigest()


def records(path: Path):
    if not path.is_file():
        return []
    out = []
    with path.open("r", encoding="utf-8-sig") as stream:
        for line in stream:
            try:
                obj = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(obj, dict):
                out.append(obj)
    return out


def snapshot(live: Path = LIVE, store: Path = STORE):
    """Copy, never move/delete, live memory and plans into private Git-managed storage."""
    source = Path(live).resolve()
    if not source.is_dir():
        return {"ok": False, "reason": "Live owner memory directory does not exist"}
    dest = Path(store)
    dest.mkdir(parents=True, exist_ok=True)
    listing = []
    for source_file in sorted(source.rglob("*")):
        if source_file.is_symlink() or not source_file.is_file():
            continue
        if not source_file.resolve().is_relative_to(source):
            continue
        rel = source_file.relative_to(source)
        if source_file.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Memory file is too large to snapshot: " + str(rel))
        target = dest / "live" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        current_digest = hash_file(source_file)
        if not target.is_file() or hash_file(target) != current_digest:
            temp = target.with_name(target.name + ".copy")
            try:
                shutil.copy2(source_file, temp)
                if hash_file(temp) != current_digest:
                    raise RuntimeError("Memory snapshot content mismatch: " + str(rel))
                temp.replace(target)
            finally:
                temp.unlink(missing_ok=True)
        listing.append({"path": rel.as_posix(), "bytes": source_file.stat().st_size, "sha256": current_digest})
    manifest = {
        "version": 1, "type": "owner-memory-backup", "private_only": True,
        "files": listing, "count": len(listing)
    }
    (dest / "snapshot_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "snapshot_files": len(listing),
            "manifest": str(dest / "snapshot_manifest.json")}


def remember(text, kind="correction", source="owner", store: Path = STORE):
    text = " ".join(str(text).split())
    if len(text) < 8 or len(text) > 15000:
        raise ValueError("Memory text length must be between 8 and 15,000 characters")
    if kind not in ("correction", "fact", "rule", "decision", "outcome"):
        raise ValueError("Memory kind is not supported")
    # Do not accidentally store access tokens as lessons, even in private Git.
    if re.search(r"(?:sk-ant-|sk-[A-Za-z0-9]{24,}|gh[po]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|password\s*[:=]|authorization:\s*bearer)", text, re.I):
        raise ValueError("Memory includes a possible credential; refuse to store raw secrets")
    dest = Path(store)
    dest.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256((kind + "\0" + text.casefold()).encode("utf-8")).hexdigest()[:20]
    path = dest / "journal.jsonl"
    if any(entry.get("id") == digest for entry in records(path)):
        return {"ok": True, "duplicate": True, "id": digest, "path": str(path)}
    obj = {
        "id": digest,
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "kind": kind,
        "source": source,
        "text": text
    }
    with path.open("a", encoding="utf-8", newline="\n") as out:
        out.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return {"ok": True, "duplicate": False, "id": digest, "path": str(path)}


def recall(query, norm, limit=5, store: Path = STORE):
    wanted = set(re.findall(r"\w+", norm(query))) - {"في", "من", "على", "the", "and", "for"}
    if not wanted:
        return []
    journal = records(Path(store) / "journal.jsonl")
    lessons = records(Path(store) / "live" / "lessons.jsonl")
    pool = journal + [{"kind": l.get("kind", "lesson"), "text": l.get("text", ""),
                        "source": "red-dragon-lessons", "id": l.get("id")}
                       for l in lessons]
    dedup = {}
    for item in pool:
        text = item.get("text", "")
        if not text:
            continue
        terms = set(re.findall(r"\w+", norm(text)))
        score = len(wanted & terms) / (len(wanted) ** .5)
        if score > 0:
            k = item.get("id") or text[:80]
            if k not in dedup or score > dedup[k][0]:
                dedup[k] = (score, item)
    ranked = sorted(dedup.values(), key=lambda x: -x[0])[:max(1, min(int(limit), 20))]
    return [{"text": v["text"], "kind": v.get("kind"), "source": v.get("source"),
             "score": round(score, 3)} for score, v in ranked]


def private_remote(repo: Path = ROOT):
    """Fail closed before any transfer; a GitHub repo must be verified PRIVATE."""
    remote = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                            capture_output=True, text=True, check=True).stdout.strip()
    match = re.search(r"github\.com[:/](?P<name>[^/\s]+/[^/\s]+?)(?:\.git)?$", remote, re.I)
    if not match:
        raise ValueError("Only verified private GitHub remotes can receive memory")
    full_name = match.group("name")
    result = subprocess.run(["gh", "repo", "view", full_name, "--json", "isPrivate",
                             "--jq", ".isPrivate"], capture_output=True, text=True, check=True)
    if result.stdout.strip() != "true":
        raise PermissionError("Refusing to upload owner memory to a non-private repository")
    return full_name


def sync(push=False, repo: Path = ROOT):
    private_remote(repo)
    if not push:
        return {"ok": True, "pushed": False, "hint": "Use memory sync --push to explicitly upload changed memory"}
    rel = "owner-memory"
    subprocess.run(["git", "-C", str(repo), "add", "--", rel], check=True)
    staged = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--name-only"],
                            text=True, capture_output=True, check=True).stdout.splitlines()
    if any(not x.startswith(rel + "/") for x in staged):
        raise RuntimeError("Other changes are staged: memory sync will not commit them")
    if not staged:
        return {"ok": True, "pushed": False, "reason": "No new learning to sync"}
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "Update private Golden Dragon continuous learning memory"], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "origin", "HEAD"], check=True)
    return {"ok": True, "pushed": True, "changed_files": len(staged)}
