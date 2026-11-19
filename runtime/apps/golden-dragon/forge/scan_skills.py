"""scan_skills.py — static inventory of every installed Claude skill for «التنين الذهبي» (Golden Dragon).

Reads files only; never runs anything from a skill. For each folder of ~/.claude/skills that has a SKILL.md it records:
  frontmatter (name, description, other keys), body size and headings, files by kind, the scripts the SKILL.md
  mentions and whether they exist, MCP servers it names, the language of its description, a family taken from the
  folder-name prefix (blender-*, ig-*, motion-*, video-template-* ...), quality flags, and duplicate groups
  (same body once the `name:` line is ignored).
Folders without a SKILL.md and loose files (zips, backups) are listed as containers / files.

  python -X utf8 scan_skills.py [--skills DIR] [--out PATH]
"""
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".ruff_cache", ".pytest_cache"}
MAX_FILES = 20000
SCRIPT_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".sh", ".ps1", ".bat", ".cmd", ".rb", ".go", ".rs"}
DOC_EXT = {".md", ".txt", ".rst", ".adoc", ".html", ".json", ".yaml", ".yml", ".toml", ".csv"}
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".mp4", ".mov", ".webm", ".wav", ".mp3", ".ttf", ".otf", ".woff2"}
# A path the SKILL.md tells the reader to open or run, relative to the skill folder. v2 (2026-11-15) after checking real
# hits: the match must START at a token boundary (not inside D:/tools/x.py, ${CLAUDE_PLUGIN_ROOT}/scripts/x.sh,
# skills/other-skill/scripts/x.py or dist/packages/engine/x.js) and must take the WHOLE extension (.jsx was read as .js,
# .json as .js). v1 flagged 87 skills, mostly false positives.
REF_RE = re.compile(r"(?<![\w./$}\-:\\])((?:\.\./)*)((?:scripts|bin|tools|engine|references|reference|assets|templates)/[\w./-]+?"
                    r"\.(?:json|jsx|js|mjs|cjs|tsx|ts|sh|ps1|py|md))(?![\w])")


def check_refs(d, body, names):
    """Paths the SKILL.md tells the reader to open/run -> (missing inside the skill, missing shared ../ refs).
    Placeholders (an ALL-CAPS folder like engine/skills/NAME/SKILL.md) are templates, not files, and are skipped."""
    inside, shared = [], []
    for up, rel in sorted(set(REF_RE.findall(body))):
        if any(len(seg) >= 3 and seg.isupper() for seg in rel.split("/")[:-1]):
            continue
        if up:
            base = d
            for _ in range(up.count("../")):
                base = base.parent
            if not (base / rel).exists():
                shared.append(up + rel)
        elif rel not in names and not any(n.endswith("/" + rel) for n in names):
            inside.append(rel)
    return inside, shared
MCP_RE = re.compile(r"\bmcp__([A-Za-z0-9_-]+?)__")


def read_text(p, limit=2_000_000):
    b = Path(p).read_bytes()[:limit]
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def frontmatter(text):
    """Minimal YAML frontmatter reader: top-level `key: value`, quoted values and `>`/`|` blocks. -> (dict, body)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    head, body = text[3:end].strip("\n"), text[end + 4:]
    meta, key, block = {}, None, []
    for line in head.splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            if key and block:
                meta[key] = " ".join(s.strip() for s in block).strip()
            key, val, block = m.group(1), m.group(2).strip(), []
            if val in (">", "|", ">-", "|-", ">+", "|+"):
                continue
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            meta[key], key = val, (key if val == "" else None)
        elif key is not None:
            block.append(line)
    if key and block:
        meta[key] = " ".join(s.strip() for s in block).strip()
    return meta, body


def lang_of(t):
    t = t or ""
    counts = {
        "ar": len(re.findall(r"[؀-ۿ]", t)),
        "zh": len(re.findall(r"[一-鿿]", t)),
        "ko": len(re.findall(r"[가-힯]", t)),
        "ru": len(re.findall(r"[Ѐ-ӿ]", t)),
        "en": len(re.findall(r"[A-Za-z]", t)) / 3,
    }
    best = max(counts, key=counts.get)
    if best == "ar" and len(re.findall(r"[پچژگ]", t)) >= 2:
        return "fa"
    return best if counts[best] else "?"


def family_of(name, all_names):
    """Family = the folder-name prefix shared with at least one other skill (blender-*, ig-*, trader-*...)."""
    parts = name.split("-")
    for k in range(len(parts), 0, -1):
        pre = "-".join(parts[:k])
        if sum(1 for n in all_names if n == pre or n.startswith(pre + "-")) >= 2:
            return pre
    return name


def walk(root):
    files, truncated, skipped = [], False, []
    for dp, dns, fns in os.walk(root):
        keep = []
        for d in dns:
            (skipped if d in SKIP_DIRS else keep).append(d)
        dns[:] = keep
        for f in fns:
            p = Path(dp) / f
            try:
                files.append((p.relative_to(root).as_posix(), p.stat().st_size))
            except OSError:
                continue
            if len(files) >= MAX_FILES:
                return files, True, sorted(set(skipped))
    return files, truncated, sorted(set(skipped))


def scan_skill(d, all_names):
    sk = d / "SKILL.md"
    text = read_text(sk)
    meta, body = frontmatter(text)
    files, truncated, skipped = walk(d)
    kinds = Counter()
    scripts = []
    for rel, _ in files:
        ext = Path(rel).suffix.lower()
        kind = "script" if ext in SCRIPT_EXT else "doc" if ext in DOC_EXT else "media" if ext in MEDIA_EXT else "other"
        kinds[kind] += 1
        if kind == "script":
            scripts.append(rel)
    names = {rel for rel, _ in files}
    refs = sorted({up + rel for up, rel in REF_RE.findall(body)})
    missing, missing_shared = check_refs(d, body, names)
    lines = body.count("\n") + 1
    desc = meta.get("description", "")
    flags = []
    if not text.startswith("---"):
        flags.append("no-frontmatter")
    if not meta.get("name"):
        flags.append("no-name")
    elif meta["name"] != d.name:
        flags.append("name-differs-from-folder")
    if not desc:
        flags.append("no-description")
    elif len(desc) > 1024:
        flags.append("description-over-1024")
    if lines > 500:
        flags.append("skill-md-over-500-lines")
    if missing:
        flags.append("mentions-missing-files")
    if missing_shared:
        flags.append("missing-shared-refs")
    if truncated:
        flags.append("over-20000-files")
    body_sig = hashlib.sha256(re.sub(r"(?m)^name:.*$", "", text).encode("utf-8", "replace")).hexdigest()
    h1 = next(iter(re.findall(r"(?m)^#\s+(.+)$", body)), "")
    ver = re.search(r"\bv(\d+(?:\.\d+){0,3})", h1) or re.search(r"(?m)^version:\s*['\"]?(\d+(?:\.\d+){0,3})", text)
    return {
        "id": d.name, "name": meta.get("name", ""), "description": desc,
        "title": h1[:160], "version": ver.group(1) if ver else "", "mtime": int(sk.stat().st_mtime),
        "meta_keys": sorted(k for k in meta if k not in ("name", "description")),
        "lang": lang_of(desc), "family": family_of(d.name, all_names),
        "lines": lines, "headings": re.findall(r"(?m)^##\s+(.+)$", body)[:25],
        "files": len(files), "bytes": sum(s for _, s in files), "kinds": dict(kinds),
        "scripts": scripts[:60], "scripts_total": len(scripts), "skipped_dirs": skipped,
        "mentions": refs[:40], "missing": missing[:20], "missing_shared": missing_shared[:20],
        "mcp": sorted(set(MCP_RE.findall(body))),
        "flags": flags, "sig": body_sig, "path": str(d),
    }


def main(argv):
    skills_dir = Path(argv[argv.index("--skills") + 1]) if "--skills" in argv else Path.home() / ".claude" / "skills"
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else Path(__file__).resolve().parent / "data" / "skills.json"
    t0 = time.time()
    dirs = sorted(p for p in skills_dir.iterdir() if p.is_dir())
    with_md = [d for d in dirs if (d / "SKILL.md").is_file()]
    all_names = [d.name for d in with_md]
    skills = []
    for d in with_md:
        try:
            skills.append(scan_skill(d, all_names))
        except Exception as e:                      # one unreadable skill must not stop the inventory
            skills.append({"id": d.name, "error": repr(e), "flags": ["scan-error"], "path": str(d)})
    groups = defaultdict(list)
    for s in skills:
        if s.get("sig"):
            groups[s["sig"]].append(s["id"])
    for ids in groups.values():
        if len(ids) > 1:
            canon = sorted(ids, key=lambda n: (bool(re.search(r"-\d+$", n)), len(n), n))[0]
            for s in skills:
                if s["id"] in ids:
                    s["dup_group"] = sorted(ids)
                    if s["id"] != canon:
                        s["dup_of"] = canon
                        s["flags"].append("duplicate")
    # one family + one title once the version/date is removed = versions of one skill (black-dragon, -2..-5; red-dragon,
    # -2). The description is not the key: the newest copy often has an updated description. Newest version wins.
    def title_key(s):
        t = re.sub(r"\([^)]*\)", "", s.get("title", ""))
        t = re.sub(r"\bv\d+(?:\.\d+)*\b|\d{4}-\d{2}-\d{2}|candidate", "", t)
        return (re.sub(r"-\d+$", "", s["id"]), re.sub(r"[\s—–:-]+", " ", t).strip().lower())
    by_desc = defaultdict(list)
    for s in skills:
        if s.get("title") and s.get("version") and "dup_of" not in s:
            by_desc[title_key(s)].append(s)
    vkey = lambda s: (tuple(int(x) for x in s["version"].split(".")) if s.get("version") else (), s.get("mtime", 0))
    for group in by_desc.values():
        if len(group) < 2 or not all(s.get("version") for s in group):
            continue                                 # same text, no versions (ig-human / li-human): siblings, not versions
        newest = max(group, key=vkey)
        for s in group:
            s["versions"] = sorted(f"{g['id']}@{g['version']}" for g in group)
            if s is not newest:
                s["superseded_by"] = newest["id"]
                s["flags"].append("older-version")
    containers = []
    for d in dirs:
        if d in with_md:
            continue
        nested = [p.parent.relative_to(d).as_posix() for p in d.rglob("SKILL.md")][:200]
        containers.append({"id": d.name, "nested_skills": len(nested), "examples": nested[:10]})
    loose = [{"name": p.name, "bytes": p.stat().st_size} for p in sorted(skills_dir.iterdir()) if p.is_file()]
    fam = Counter(s.get("family") for s in skills)
    data = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "skills_dir": str(skills_dir), "seconds": round(time.time() - t0, 1),
        "count": len(skills), "containers": containers, "loose_files": loose,
        "families": {k: v for k, v in fam.most_common() if v > 1},
        "langs": dict(Counter(s.get("lang") for s in skills)),
        "flags": dict(Counter(f for s in skills for f in s.get("flags", []))),
        "skills": skills,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {len(skills)} skills, {len(containers)} containers, {len(loose)} loose files in {data['seconds']}s -> {out}")
    print("families:", ", ".join(f"{k}×{v}" for k, v in list(data["families"].items())[:30]))
    print("langs:", data["langs"])
    print("flags:", data["flags"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
