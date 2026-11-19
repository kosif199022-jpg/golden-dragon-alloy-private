#!/usr/bin/env python3
"""Maven Reels: install the extra Instagram and video skills that ship in extras/. (c) 2026 Maven.

usage: python install_extras.py [--force] [--skip-remotion]

Installs, for Claude Code, at user level:
  ig-*            13 Instagram skills (Jake Schincariol, MIT)          -> ~/.claude/skills
  skill-creator   Anthropic's Skill Creator (Apache 2.0)                -> ~/.claude/skills
  marketing-skills  53 marketing skills (Corey Haines, MIT)             -> Claude Code plugin
  remocn          Remotion animation components (Remocn, MIT)           -> Claude Code plugin
  remotion-*      Remotion's official skills (downloaded from remotion-dev/skills, not shipped here)

The two plugins keep their skills under a prefix (marketing-skills:video, remocn:video), so their short
names never clash with other skills. Already-installed skills are left alone unless you pass --force.
These are other people's work under their own licences: see extras/README.md.
"""
import argparse
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXTRAS = ROOT / "extras"
SKILLS = pathlib.Path.home() / ".claude" / "skills"


def run(cmd):
    print("  $", " ".join(cmd))
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, shell=sys.platform == "win32")
    except FileNotFoundError:
        return False, "not found"
    out = (p.stdout + p.stderr).strip().splitlines()
    return p.returncode == 0, out[-1] if out else ""


def copy_skill(src, force):
    dest = SKILLS / src.name
    if dest.exists() or dest.is_symlink():
        if not force:
            print(f"  = {src.name} (already installed)")
            return
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"  + {src.name}")


def plugin(folder, marketplace, name):
    if not shutil.which("claude"):
        print(f"  ! Claude Code's `claude` command was not found. In Claude Code, type:\n"
              f"      /plugin marketplace add {folder}\n      /plugin install {name}@{marketplace}")
        return
    ok, msg = run(["claude", "plugin", "marketplace", "add", str(folder)])
    if not ok and "already" not in msg.lower():
        print("  !", msg)
    ok, msg = run(["claude", "plugin", "install", f"{name}@{marketplace}"])
    print("  +" if ok else "  !", msg)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="replace skills that are already installed")
    ap.add_argument("--skip-remotion", action="store_true", help="don't download Remotion's skills")
    a = ap.parse_args()
    SKILLS.mkdir(parents=True, exist_ok=True)

    print("Instagram skills:")
    for s in sorted((EXTRAS / "instagram-agent" / "skills").glob("ig-*")):
        copy_skill(s, a.force)
    print("Skill Creator:")
    copy_skill(EXTRAS / "skill-creator", a.force)
    print("Marketing skills (plugin):")
    plugin(EXTRAS / "marketingskills", "marketingskills", "marketing-skills")
    print("Remocn (plugin):")
    plugin(EXTRAS / "remocn", "remocn", "remocn")
    if not a.skip_remotion:
        print("Remotion skills (downloaded from remotion-dev/skills):")
        if shutil.which("npx"):
            ok, msg = run(["npx", "--yes", "skills", "add", "remotion-dev/skills", "-g", "-a", "claude-code", "-s", "*", "-y"])
            print("  +" if ok else "  !", msg)
        else:
            print("  ! npx not found. Install Node, then run: npx skills add remotion-dev/skills -g -a claude-code")
    print("\nDone. Start a new Claude Code session so the new skills and plugins load.")
    print("The Instagram skills' Python tools need Python 3; on Windows run them with `py -3` if `python3` is missing.")


if __name__ == "__main__":
    main()
