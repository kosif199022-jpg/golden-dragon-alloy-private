"""Offline, opt-in bridge between Golden Dragon and wheresryan22/anatomy.

This module does not download or run anything. It checks for a user-installed
Anatomy Agent Skill and can copy its *existing* kit and examples into a new
workspace folder. Run the upstream Node build only after inspecting the files.
Upstream: https://github.com/wheresryan22/anatomy (MIT; see copied LICENSE).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

UPSTREAM = "https://github.com/wheresryan22/anatomy"
INSTALL = "npx skills add wheresryan22/anatomy -g -a claude-code"
EXAMPLES = {
    "dial-indicator": "SVG: قياس ميكانيكي وعداد حي",
    "desk-computer": "SVG: جهاز تفاعلي بأجزاء دقيقة",
    "arcade-cabinet": "SVG: أجزاء وأسلاك وحركة مجسمة",
    "raptor-engine": "SVG + WebGL: محرك، تفكيك، ودخان",
    "ripple-tank": "SVG + WebGL: فيزياء الموجات والضوء",
    "turning-dial": "3D تجريبي: قرص ومفاصل متحركة",
}
REQUIRED = ("SKILL.md", "LICENSE", "kit/iso-kit.mjs", "scripts/inline-kit.mjs")
MAX_COPY_BYTES = 60 * 1024 * 1024


def skill_home(explicit: str | Path | None = None) -> Path | None:
    """Use an explicit path, then environment, then well-known skill folders."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    elif os.environ.get("GOLDEN_ANATOMY_HOME"):
        candidates.append(Path(os.environ["GOLDEN_ANATOMY_HOME"]).expanduser())
    else:
        h = Path.home()
        candidates.extend((
            h / ".claude" / "skills" / "anatomy",
            h / ".agents" / "skills" / "anatomy",
            h / ".gemini" / "antigravity" / "skills" / "anatomy",
            h / ".config" / "opencode" / "skills" / "anatomy",
            h / ".minimax" / "skills" / "anatomy",
        ))
    for candidate in candidates:
        if candidate.is_dir() and all((candidate / rel).is_file() for rel in REQUIRED):
            return candidate.resolve()
    return None


def _node_version() -> dict:
    node = shutil.which("node")
    if not node:
        return {"available": False, "compatible": False, "reason": "Node.js 20.10+ مطلوب"}
    try:
        result = subprocess.run((node, "--version"), capture_output=True, text=True, timeout=3, check=True)
        version = result.stdout.strip()
        m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version)
        compatible = bool(m and (int(m[1]), int(m[2])) >= (20, 10))
        return {"available": True, "compatible": compatible, "version": version}
    except (OSError, subprocess.SubprocessError):
        return {"available": True, "compatible": False, "reason": "تعذر التحقق من إصدار Node.js"}


def doctor(skill: str | Path | None = None) -> dict:
    home = skill_home(skill)
    node = _node_version()
    return {
        "ok": home is not None and node["compatible"],
        "skill_installed": home is not None,
        "skill_path": str(home) if home else None,
        "node": node,
        "browser_checks": "تحتاج Chrome/Chromium بعد إنشاء الرسم",
        "capabilities": ["isometric-svg", "svg-webgl", "interactive-3d-beta", "geometry-audit"],
        "install_command": None if home else INSTALL,
        "source": UPSTREAM,
        "notice": "لا يتم التنزيل أو تشغيل سكربتات المصدر تلقائيًا",
    }


def brief(query: str) -> dict:
    """Plan only: do not misrepresent a plan as a rendered simulation."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query required")
    q = query.casefold()
    if any(k in q for k in ("موج", "سائل", "water", "wave", "ripple", "light", "ضوء")):
        example, medium = "ripple-tank", "SVG + WebGL"
    elif any(k in q for k in ("محرك", "صاروخ", "engine", "raptor", "exhaust", "دخان", "fire", "نار")):
        example, medium = "raptor-engine", "SVG + WebGL"
    elif any(k in q for k in ("تفكيك 3d", "3d", "turntable", "دوران حقيقي", "مفصل", "hinge")):
        example, medium = "turning-dial", "3D (beta)"
    elif any(k in q for k in ("كمبيوتر", "حاسوب", "computer", "keyboard", "لوحة مفاتيح")):
        example, medium = "desk-computer", "SVG"
    else:
        example, medium = "dial-indicator", "SVG"
    d = doctor()
    return {
        "ok": True,
        "request": query.strip(),
        "medium": medium,
        "reference_example": example,
        "skill_ready": d["skill_installed"],
        "run_ready": d["ok"],
        "workflow": [
            "اقرأ SKILL.md ومراجع Anatomy قبل كتابة كود جديد",
            "اختر جسمًا حقيقيًا يشرح الفكرة واكتب أجزاءه ودرجات الحرية والقياسات",
            "ابدأ من المثال المماثل وعدّل build.mjs مع إبقاء كل القيم من نموذج واحد",
            "ابنِ HTML/SVG محليًا وافحص الأزرار والحركة والـ readouts",
            "نفّذ audit الهندسي عند دعمه، ثم لقطات Chrome عن قرب وبأكثر من وضع",
            "سلّم الملف الناتج والدليل على عمله؛ لا تدّع دقة فيزيائية بلا تحقق",
        ],
        "checks": ["Node >=20.10", "لا خطوط طافية أو مجسمات شفافة بالخطأ",
                   "لا تداخل أو اختراق بين الأجزاء", "قراءات وحركة من حالة واحدة",
                   "Chrome console بلا أخطاء ولقطات بصرية", "نسخة بدون WebGL مفهومة"],
        "scaffold_example": example,
        "source": UPSTREAM,
    }


def _check_source(root: Path, example: str) -> None:
    if example not in EXAMPLES:
        raise ValueError("Unknown example; choices: " + ", ".join(EXAMPLES))
    items = [root / "kit", root / "scripts", root / "examples" / example, root / "LICENSE", root / "SKILL.md"]
    if not (root / "examples" / example / "build.mjs").is_file():
        raise FileNotFoundError("Example has no build.mjs: " + example)
    total = 0
    for item in items:
        if item.is_symlink():
            raise ValueError("رفض رابط رمزي في المصدر: " + str(item))
        paths = item.rglob("*") if item.is_dir() else [item]
        for f in paths:
            if f.is_symlink():
                raise ValueError("رفض رابط رمزي في المصدر: " + str(f))
            if f.is_file():
                total += f.stat().st_size
                if total > MAX_COPY_BYTES:
                    raise ValueError("حجم الملفات أكبر من الحد الآمن 60 MiB")


def scaffold(destination: str | Path, example: str = "dial-indicator",
             workdir: str | Path | None = None, skill: str | Path | None = None) -> dict:
    """Copy a real upstream sample and kit; never execute code or overwrite files."""
    source = skill_home(skill)
    if not source:
        raise FileNotFoundError("Anatomy skill not found. Install with: " + INSTALL)
    _check_source(source, example)
    project = Path(workdir or Path.cwd()).expanduser().resolve()
    raw = Path(destination)
    if raw.is_absolute() or not str(raw).strip() or str(raw) in (".", ".."):
        raise ValueError("destination must be a NEW relative directory inside the workspace")
    target = (project / raw).resolve()
    if not target.is_relative_to(project) or target == project:
        raise ValueError("destination escapes the workspace")
    if target.exists() or target.is_symlink():
        raise FileExistsError("destination already exists: " + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=False)
    try:
        for folder in ("kit", "scripts"):
            shutil.copytree(source / folder, target / folder)
        shutil.copytree(source / "examples" / example, target / "examples" / example)
        for filename in ("LICENSE", "SKILL.md"):
            shutil.copy2(source / filename, target / filename)
        readme = (
            "# Golden Dragon + Anatomy scaffold\n\n"
            "Copied locally from " + UPSTREAM + " (MIT licensed).\n"
            "This is the ORIGINAL " + example + " reference example, not a finished custom drawing.\n\n"
            "Run after inspecting the code and installing Node 20.10+:\n\n"
            "    node examples/" + example + "/build.mjs --light\n\n"
            "Open the generated HTML in a browser. For supported examples, use --audit.\n"
            "For visual verification use scripts/capture.mjs and scripts/drive.mjs.\n"
            "Keep LICENSE when distributing derivatives and read SKILL.md for craft/verification rules.\n"
            "This scaffolder never runs Node or contacts the network.\n"
        )
        (target / "GOLDEN_ANATOMY_README.md").write_text(readme, encoding="utf-8")
    except Exception:
        shutil.rmtree(target)
        raise
    return {
        "ok": True, "path": str(target), "example": example,
        "entry": str(target / "examples" / example / "build.mjs"),
        "next_command": "node examples/" + example + "/build.mjs --light",
        "executed": False, "copied_license": True, "source": UPSTREAM,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Golden Dragon Anatomy bridge (offline)")
    p.add_argument("--skill", help="Path to an already installed Anatomy skill")
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("doctor")
    b = sub.add_parser("brief")
    b.add_argument("query", nargs="+")
    s = sub.add_parser("scaffold")
    s.add_argument("destination", help="New directory relative to current workspace")
    s.add_argument("--example", choices=list(EXAMPLES), default="dial-indicator")
    args = p.parse_args(argv)
    try:
        if args.action == "doctor":
            result = doctor(args.skill)
        elif args.action == "brief":
            result = brief(" ".join(args.query))
        else:
            result = scaffold(args.destination, args.example, skill=args.skill)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
