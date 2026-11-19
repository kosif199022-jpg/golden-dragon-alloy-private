"""Built-in discovery and safe plans for Golden Dragon's Viral Video Analyzer + Replica Skill.

Execution is deliberately delegated to the existing approval-gated run_command tool.
No automatic clone, download, login, or external code execution occurs here.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil

SOURCES = {
    "viral": "https://github.com/udaysrinu/viral-video-analyzer",
    "replica": "https://github.com/Jakeschincariol/replica-skill",
}
REPLICA_STAGES = ("recon", "architect", "design", "build", "backend", "test",
                  "diff", "entrepreneur", "brand", "launch", "deploy")


def _roots(explicit=None):
    if explicit:
        return [Path(explicit).expanduser()]
    home = Path.home()
    roots = [home / "GoldenDragon" / "integrations", home / ".claude" / "skills",
             Path.cwd() / "vendor", Path.cwd()]
    for key in ("GOLDEN_VIRAL_HOME", "GOLDEN_REPLICA_HOME"):
        if os.environ.get(key):
            roots.insert(0, Path(os.environ[key]).expanduser())
    return roots


def _find_viral(roots):
    for root in roots:
        for path in (root, root / "viral-video-analyzer"):
            if (path / "analyze_viral_video.py").is_file() and (path / "requirements.txt").is_file():
                return path.resolve()
    return None


def _find_replica(roots):
    for root in roots:
        for path in (root, root / "replica-skill"):
            if all((path / ("replica-" + stage) / "SKILL.md").is_file() for stage in REPLICA_STAGES):
                return path.resolve()
    return None


def doctor(root=None):
    roots = _roots(root)
    viral = _find_viral(roots)
    replica = _find_replica(roots)
    return {
        "viral": {"installed": bool(viral), "path": str(viral) if viral else None,
                  "ffmpeg": bool(shutil.which("ffmpeg")), "yt_dlp": bool(shutil.which("yt-dlp")),
                  "whisper": bool(shutil.which("whisper")), "source": SOURCES["viral"]},
        "replica": {"installed": bool(replica), "path": str(replica) if replica else None,
                    "stages_found": list(REPLICA_STAGES) if replica else [],
                    "source": SOURCES["replica"]},
        "execution": "No external commands executed; use approved run_command separately.",
    }


def plan(kind, target):
    if kind not in ("viral", "replica"):
        raise ValueError("kind must be viral or replica")
    if not isinstance(target, str) or not target.strip():
        raise ValueError("target is required")
    target = target.strip()
    if kind == "viral":
        return {
            "kind": kind, "target": target, "source": SOURCES[kind],
            "prerequisites": ["Python 3.10+", "ffmpeg", "yt-dlp", "openai-whisper",
                              "video file or publicly accessible URL with permitted access"],
            "stages": ["Check local dependencies and permissions",
                       "Inspect upstream script and pin a reviewed revision",
                       "With approval, run analyze_viral_video.py for the chosen URL",
                       "Inspect metadata, 1fps frames, transcript and timestamped SRT",
                       "Analyze hook, camera, editing, narration, story beats, and transferable patterns",
                       "Report missing or unreliable data rather than inventing virality metrics"],
            "outputs": ["video.mp4", "audio.wav", "transcript.txt", "transcript.srt",
                        "frames/", "video.info.json", "summary.md"],
            "notice": "Upstream summary.md is a template, not an automatic AI-generated final analysis.",
            "requires_approval": True, "executed": False,
        }
    return {
        "kind": kind, "target": target, "source": SOURCES[kind],
        "prerequisites": ["Python 3.8+", "public/authorized sources", "clean-room implementation"],
        "stages": list(REPLICA_STAGES),
        "checks": ["Never copy proprietary source/assets/logos/private APIs",
                   "Respect access controls, licenses and platform terms",
                   "Use original branding and content before deployment",
                   "Run original parity/contrast/review/sweep/listing tests as applicable",
                   "Require explicit approval before install, build, payments or deployment"],
        "notice": "Replica skills are guided workflows, not an automatic one-click app cloner.",
        "requires_approval": True, "executed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("doctor", "plan"))
    parser.add_argument("kind", nargs="?", choices=("viral", "replica"))
    parser.add_argument("target", nargs="*")
    parser.add_argument("--root")
    args = parser.parse_args(argv)
    try:
        if args.action == "doctor":
            result = doctor(args.root)
        else:
            if not args.kind:
                raise ValueError("kind is required for plan")
            result = plan(args.kind, " ".join(args.target))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
