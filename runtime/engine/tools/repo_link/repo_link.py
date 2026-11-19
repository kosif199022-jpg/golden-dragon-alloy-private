#!/usr/bin/env python3
"""Black Dragon <-> kosif-tool (Superpowers) repository link.

    python scripts/dragon.py tool repo status            # where the repo is, its commit vs the pinned one
    python scripts/dragon.py tool repo sync [--yes]      # dry run by default; --yes runs git clone/pull
    python scripts/dragon.py tool repo fusion find "قص على الدروب"   # repo_fusion.py from the repo (or bundled copy)
    python scripts/dragon.py tool repo paths --json      # key paths inside the repo for the brain and the tools

The skill bundles a copy of the repo-fusion tools (tools/repo_fusion) so it works on claude.ai
without the repository. When a local clone exists, `fusion` prefers the repository copy, so a
`sync` picks up newer capabilities. Nothing is pushed: this link is read/pull only.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/kosif199022-jpg/kosif-tool"
PINNED_COMMIT = "85cb965"  # main after the REA repo-fusion merge (2026-11-10)
HERE = Path(__file__).resolve()
SKILL = HERE.parents[2]
BUNDLED_FUSION = SKILL / "tools" / "repo_fusion" / "scripts" / "repo_fusion.py"
HOME = Path.home()
CANDIDATES = [
    Path(os.environ["KOSIF_TOOL"]) if os.environ.get("KOSIF_TOOL") else None,
    HOME / "kosif-tool",
    HOME / "kosif-own" / "kosif-tool",
    Path("/home/user/kosif-tool"),
    Path("/workspace/kosif-tool"),
    Path.cwd(),
]
PATHS = {
    "superpowers_skill": ".claude/skills/kosif-superpowers",
    "superpowers_hub": ".claude/skills/kosif-superpowers/scripts/hub.py",
    "superpowers_protocol": ".claude/skills/kosif-superpowers/PROTOCOL.md",
    "black_dragon_skill": ".claude/skills/kosif-black-dragon",
    "repo_fusion": ".claude/skills/kosif-black-dragon/scripts/repo_fusion.py",
    "fusion_modules": ".claude/skills/kosif-black-dragon/scripts/fusion",
    "media_hunter": ".claude/skills/kosif-black-dragon/tools/media_hunter/mh.py",
    "video_protocol": ".claude/skills/kosif-black-dragon/scripts/video_protocol.py",
}


def _git(repo: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def find_repo() -> Path | None:
    for c in CANDIDATES:
        if c and (c / ".claude" / "skills" / "kosif-superpowers").is_dir() and (c / ".git").exists():
            return c
    return None


def status() -> dict:
    repo = find_repo()
    info = {"repo_url": REPO_URL, "pinned_commit": PINNED_COMMIT, "local_repo": str(repo) if repo else None,
            "bundled_fusion": BUNDLED_FUSION.is_file()}
    if repo:
        head = _git(repo, "rev-parse", "--short", "HEAD")
        info.update({
            "branch": _git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
            "head": head,
            "has_pinned_commit": _git(repo, "cat-file", "-e", PINNED_COMMIT + "^{commit}") is not None,
            "dirty": bool(_git(repo, "status", "--porcelain")),
            "paths": {k: (repo / v).exists() for k, v in PATHS.items()},
        })
        info["linked"] = info["has_pinned_commit"] and all(info["paths"].values())
    else:
        info["linked"] = False
        info["hint"] = f"no local clone: run `tool repo sync --yes` (git clone {REPO_URL}) or set KOSIF_TOOL; the bundled copy still works"
    return info


def sync(yes: bool) -> int:
    repo = find_repo()
    if repo is None:
        target = Path(os.environ.get("KOSIF_TOOL") or HOME / "kosif-tool")
        cmd = ["git", "clone", "--depth", "50", REPO_URL, str(target)]
    else:
        if _git(repo, "status", "--porcelain"):
            print(f"refusing to pull: {repo} has uncommitted changes", file=sys.stderr)
            return 3
        cmd = ["git", "-C", str(repo), "pull", "--ff-only"]
    print("plan:", " ".join(cmd))
    if not yes:
        print("dry run: add --yes to run it (pull/clone only, never push)")
        return 0
    return subprocess.call(cmd)


def fusion(args: list[str]) -> int:
    repo = find_repo()
    script = repo / PATHS["repo_fusion"] if repo and (repo / PATHS["repo_fusion"]).is_file() else BUNDLED_FUSION
    print(f"[repo-fusion: {'repository' if script != BUNDLED_FUSION else 'bundled'} copy]", file=sys.stderr)
    return subprocess.call([sys.executable, str(script), *args])


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=1))
        return 0
    if cmd == "sync":
        return sync("--yes" in rest)
    if cmd == "fusion":
        return fusion(rest)
    if cmd == "paths":
        repo = find_repo()
        print(json.dumps({k: str(repo / v) if repo else v for k, v in PATHS.items()}, ensure_ascii=False, indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
