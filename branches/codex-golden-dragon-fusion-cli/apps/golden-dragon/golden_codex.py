"""Run a Golden Dragon request through the local Codex CLI."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", help="Golden Dragon request in Arabic or English")
    parser.add_argument("--reel-style", choices=("cinematic", "clay", "documentary", "kinetic-type", "product", "whiteboard"))
    parser.add_argument("--output", type=Path, help="New Motion Reel project directory")
    parser.add_argument("--motion-reel-home", type=Path, help="Installed Motion Reel kit")
    parser.add_argument("--preview", action="store_true", help="Print the brief locally")
    args = parser.parse_args()
    if not args.request.strip():
        parser.error("Enter a non-empty request.")
    if args.reel_style or args.output:
        if not (args.reel_style and args.output) or args.preview:
            parser.error("Use --reel-style and --output together, without --preview.")
        relative = Path("engine/skills/library/motion-reel")
        repo_kit = Path(__file__).resolve().parents[2] / relative
        kit = args.motion_reel_home or repo_kit
        init = Path(".claude/skills/motion-reel/scripts/init.sh")
        if not args.motion_reel_home and not (kit / init).is_file():
            kit = Path.home() / ".claude/skills/golden-dragon" / relative
        preset = repo_kit / "presets" / ("golden-dragon-" + args.reel_style)
        output = args.output.resolve()
        if output.exists() or not (kit / init).is_file() or not (preset / "preset.jsonc").is_file():
            parser.error("A new output directory, installed Motion Reel kit and repository preset are required.")
        import os
        git_bash = Path(os.environ.get("ProgramFiles", "")) / "Git/bin/bash.exe"
        bash = str(git_bash) if os.name == "nt" and git_bash.is_file() else shutil.which("bash")
        if not bash:
            parser.error("Bash is required by Motion Reel.")
        result = subprocess.run([bash, init.as_posix(), output.as_posix(), "--preset", preset.as_posix()], cwd=kit)
        if result.returncode == 0:
            (output / "request.txt").write_text(args.request + "\n", encoding="utf-8")
        return result.returncode
    fusion = Path(__file__).resolve().parent / "app" / "dragon_fusion.py"
    brief = subprocess.run(
        [sys.executable, "-X", "utf8", str(fusion), "brief", args.request],
        stdout=subprocess.PIPE, encoding="utf-8",
    )
    if brief.returncode:
        print(brief.stdout, file=sys.stderr)
        return brief.returncode
    prompt = f"Golden Dragon request:\n{args.request}\n\nLocal planning context:\n{brief.stdout}"
    if args.preview:
        print(prompt)
        return 0
    codex = shutil.which("codex")
    if not codex:
        parser.exit(1, "Codex CLI is required. Use --preview to inspect the brief locally.\n")
    return subprocess.run(
        [codex, "exec", "--sandbox", "read-only", "-"],
        input=prompt.encode("utf-8"),
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
