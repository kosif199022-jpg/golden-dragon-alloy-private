"""Turn the reviewed branch verdicts into an exact take-list (paths computed from git, not from prose).

    python -I -X utf8 forge/take_branches.py --src <checkout> --verdicts branches.json --out forge/take.json
            [--laptop-skill ~/.claude/skills/golden-dragon]

Rules (from the branch review, 2026-11-19):
- New files from UNIQUE-BLEND branches are taken whole into branches/<branch>/ (runtime/ stays = main).
- Edits to files that main already has are staged as patches (git diff merge-base..branch), never applied
  silently: applying them is a release step (manifests + selftest + router floor).
- Excluded on purpose: golden_dragon.pyz (rebuild instead), make_golden_dragon.py (conflicts with main),
  verification docs that carry the machine's hostname, and the yt-dlp auto-update patch is staged with a
  warning (it runs `pip install -U` without asking: dragon rule §2).
- claude-app: golden_mcp.py and tests/test_claude_app.py come from the laptop's installed copy when it is
  newer (stdin=DEVNULL fix that exists only there).
"""
import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
from pathlib import Path


def git(src, *a):
    return subprocess.run(["git", "-C", str(src), "-c", "core.quotepath=false", *a], capture_output=True,
                          check=True).stdout.decode("utf-8")


RULES = {
    "claude/sharp-ptolemy-mku5pf": {"patch": [".gitignore"]},
    "codex/golden-dragon-fusion-cli": {
        "take": ["engine/skills/library/motion-reel/presets/golden-dragon-*/preset.jsonc", "apps/golden-dragon/golden_codex.py"],
        "patch": ["engine/skills/library/motion-reel/.claude/skills/motion-reel/engine/type.js",
                  "engine/skills/library/motion-reel/.claude/skills/motion-reel/scripts/beats.py"]},
    "codex/golden-fusion-json-find": {"patch": ["apps/golden-dragon/forge/modules/dragon_fusion.py"]},
    "feat/golden-claude-app": {"take": ["apps/golden-dragon/claude-app/*", "apps/golden-dragon/claude-app/tests/*"],
                               "laptop_newer": ["apps/golden-dragon/claude-app/golden_mcp.py",
                                                "apps/golden-dragon/claude-app/tests/test_claude_app.py"]},
    "feat/golden-dragon-runtime-ledger-20261118": {
        "take": ["apps/golden-dragon/forge/unified_core/runtime.py", "apps/golden-dragon/forge/unified_core/audit_tree.py",
                 "apps/golden-dragon/forge/unified_core/capability_ledger.py",
                 "apps/golden-dragon/forge/unified_core/blender_engine.py",
                 "apps/golden-dragon/forge/unified_core/native_registry.py",
                 "apps/golden-dragon/forge/unified_core/map_dependencies.py",
                 "apps/golden-dragon/forge/unified_core/tests/test_*.py",
                 "apps/golden-dragon/integrations/maven_bridge.py", "apps/golden-dragon/integrations/README.md"]},
    "feature/golden-dragon-fusion-share": {"take": [".agents/skills/golden-dragon-fusion/*",
                                                    ".agents/skills/golden-dragon-fusion/**/*"],
                                           "exclude": ["*.pyz"]},
    "golden-dragon-v3.5.2-stale-review": {
        "patch": ["engine/skills/video-grabber/scripts/grab.py", "engine/skills/video-grabber/tests/grab/test_grab.py",
                  "engine/skills/video-grabber/SKILL.md"],
        "warn": "auto-update runs pip install -U without asking (dragon rule §2): make it opt-in before applying"},
}


def match(path, pats):
    return any(fnmatch.fnmatch(path, p) for p in pats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--laptop-skill", default=str(Path.home() / ".claude" / "skills" / "golden-dragon"))
    a = ap.parse_args()
    verdicts = json.load(open(a.verdicts, encoding="utf-8"))
    out = []
    for v in verdicts:
        name = v["branch"].removeprefix("origin/")
        mb = git(a.src, "merge-base", "origin/main", f"origin/{name}").strip()
        changed = [ln.split("\t") for ln in git(a.src, "diff", "--name-status", mb, f"origin/{name}").splitlines() if ln]
        files = [(st[0], st[-1]) for st in changed]
        r = RULES.get(name, {})
        take, patch, skipped = [], [], []
        in_main = set(git(a.src, "ls-tree", "-r", "--name-only", "origin/main").splitlines())
        for status, path in files:
            if status.startswith("D"):
                skipped.append((path, "deleted on branch"))
            elif match(path, r.get("exclude", [])):
                skipped.append((path, "excluded: rebuild instead (binary)"))
            elif match(path, r.get("patch", [])):
                patch.append(path)
            elif match(path, r.get("take", [])):
                take.append(path)
            else:
                skipped.append((path, f"{v['verdict']}: not in the take rules"))
        overrides = {}
        for p in r.get("laptop_newer", []):
            lp = Path(a.laptop_skill) / p
            if lp.exists():
                b = lp.read_bytes()
                try:
                    bb = subprocess.run(["git", "-C", a.src, "show", f"origin/{name}:{p}"], capture_output=True).stdout
                except Exception:
                    bb = b""
                if hashlib.sha256(b).hexdigest() != hashlib.sha256(bb).hexdigest():
                    overrides[p] = str(lp)
        out.append({"branch": name, "verdict": v["verdict"] if (take or patch) else v["verdict"],
                    "merge_base": mb[:10], "sha": git(a.src, "rev-parse", f"origin/{name}").strip()[:10],
                    "adds": v.get("adds", ""), "evidence": v.get("evidence", ""), "warn": r.get("warn", ""),
                    "take": sorted(take), "patch": sorted(patch), "skipped": skipped, "overrides": overrides,
                    "already_in_main": sorted(p for p in take if p in in_main)})
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for b in out:
        print(f"{b['branch']:<46} {b['verdict']:<18} take={len(b['take']):>2} patch={len(b['patch'])} "
              f"skip={len(b['skipped']):>2} laptop-newer={len(b['overrides'])} in-main={len(b['already_in_main'])}")


if __name__ == "__main__":
    main()
