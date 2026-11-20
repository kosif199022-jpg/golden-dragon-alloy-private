"""Golden Dragon -> locally installed Maven Reels adapter.
Does not redistribute Maven source. Explicit commands; no shell=True.
Set MAVEN_REELS_HOME to a private, authorized installation.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

def home():
    p = Path(os.environ.get("MAVEN_REELS_HOME", "")).expanduser()
    if not os.environ.get("MAVEN_REELS_HOME"):
        raise RuntimeError("Set MAVEN_REELS_HOME to your private Maven Reels installation")
    if not (p / "SKILL.md").is_file() or not (p / "scripts" / "analyze.py").is_file():
        raise RuntimeError("MAVEN_REELS_HOME is not a valid Maven Reels folder")
    return p.resolve()

def execute(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), check=False).returncode

def main():
    p = argparse.ArgumentParser(description="Golden Dragon private Maven Reels bridge")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    a = sub.add_parser("analyze"); a.add_argument("video"); a.add_argument("output")
    n = sub.add_parser("new"); n.add_argument("folder")
    r = sub.add_parser("render"); r.add_argument("html"); r.add_argument("output"); r.add_argument("--voice")
    args = p.parse_args()
    try: root = home()
    except RuntimeError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)); return 2
    if args.command == "doctor":
        status = {"maven_home": str(root), "python": sys.executable,
                  "node": shutil.which("node"), "ffmpeg": shutil.which("ffmpeg"),
                  "render_script": (root / "scripts" / "render.mjs").is_file(),
                  "rights_file": (root / "rights" / "MAVEN-RIGHTS.txt").is_file()}
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if all([status["node"],status["ffmpeg"],status["render_script"],status["rights_file"]]) else 1
    if args.command == "analyze":
        video = Path(args.video).expanduser().resolve()
        if not video.is_file(): p.error("Input video does not exist")
        return execute([sys.executable, str(root/"scripts"/"analyze.py"), str(video), str(Path(args.output).resolve())], root)
    if args.command == "new":
        return execute([sys.executable, str(root/"scripts"/"new.py"), str(Path(args.folder).resolve())], root)
    if args.command == "render":
        html = Path(args.html).expanduser().resolve()
        if not html.is_file(): p.error("HTML file does not exist")
        cmd = ["node", str(root/"scripts"/"render.mjs"), str(html), str(Path(args.output).resolve())]
        if args.voice:
            voice = Path(args.voice).expanduser().resolve()
            if not voice.is_file(): p.error("Voice file does not exist")
            cmd += ["--voice", str(voice)]
        return execute(cmd, root)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
