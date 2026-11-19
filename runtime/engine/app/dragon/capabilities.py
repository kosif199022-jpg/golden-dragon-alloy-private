"""Read-only capability inspection and execution planning for Black Dragon.

IMPORTANT: this module never runs an adapter. An installed executable proves only that
an entrypoint can be discovered, not that a task can be completed successfully.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

from . import router

APP = Path(__file__).resolve().parent.parent


def _skill_root() -> Path:
    """The skill folder (with tools/, skills/, scripts/). A launcher copy of app/ (~/.black-dragon/app, /tmp/dragon)
    has no tools/ next to it, so 37 file adapters looked missing; scripts/dragon.py passes DRAGON_SKILL. v10.15."""
    import os
    env = os.environ.get("DRAGON_SKILL", "").strip()
    if env and (Path(env) / "tools").is_dir():
        return Path(env)
    return APP.parent


SKILL = _skill_root()
REGISTRY = APP / "data" / "own_tools.json"

# A deliberately small, auditable registry of local preconditions. Unknown tools are not
# auto-executed and commands from the index are DISPLAY STRINGS, never shell input.
NEEDS: dict[str, tuple[tuple[str, str], ...]] = {
    "dragon-montage": (("program", "ffmpeg"), ("program", "ffprobe")),
    "cinema-film": (("program", "ffmpeg"), ("program", "ffprobe")),
    "talking-head": (("program", "ffmpeg"), ("program", "ffprobe")),
    "web-film": (("program", "node"), ("program", "ffmpeg")),
    "editorial-look": (("program", "node"), ("program", "ffmpeg")),
    "blender-engine": (("program", "blender"),),
    "blender-pro": (("program", "blender"),),
    "voice-studio": (("program", "ffmpeg"),),
    "deep-filter": (("program", "deep-filter"),),
    "demucs": (("module", "demucs"),),
    "whisperx": (("module", "whisperx"),),
    "upscayl": (("program", "upscayl-bin"),),
    "rembg": (("module", "rembg"),),
    "auto-editor": (("program", "auto-editor"),),
    "scenedetect": (("program", "scenedetect"),),
    "v10-video-gate": (("program", "ffmpeg"), ("program", "ffprobe")),
    "v10-pixel-qa": (("program", "ffmpeg"), ("module", "PIL")),
    "v10-media-audit": (("program", "ffprobe"),),
    "phone-play-check": (("program", "ffmpeg"), ("program", "ffprobe")),
    "framecheck": (("program", "ffmpeg"), ("program", "ffprobe")),
    "blind-critic": (("program", "ffmpeg"), ("program", "ffprobe")),
    "media-hunter-615": (("module", "httpx"),),
    # merged from v10.8.1
    "chrome-control": (("module", "playwright"),),
    "cloud-browser": (("module", "playwright"), ("module", "aiohttp")),
    "kosif-downloads": (("module", "httpx"),),
    "lyric-ass": (("program", "ffmpeg"),),
    "psd-studio": (("module", "psd_tools"), ("module", "PIL")),
    # v10.17: merged thinking/analysis skills
    "dragon-genius": (("program", "ffprobe"),),  # media_gate needs ffprobe/ffmpeg; qa is stdlib-only
    # omni-analyst is stdlib-only (no preconditions)
}

ENTRYPOINTS: dict[str, tuple[str, str]] = {
    "dragon-montage": ("engine", "dragon_montage"),
    "cinema-film": ("module", "dragon.cli"),
    "talking-head": ("engine", "talking_head"),
    "image-studio": ("engine", "image_studio"),
    "blender-engine": ("engine", "blender"),
    "blender-pro": ("file", "tools/blender-pro/bridge.py"),
    "absolute-creativity": ("file", "tools/absolute_creativity/bridge.py"),
    "rea-ultra": ("file", "tools/rea_ultra/bridge.py"),
    "visual-forge": ("file", "tools/visual_forge/bridge.py"),
    "physics-math": ("file", "tools/physics_math/bridge.py"),
    "dragon-genius": ("file", "tools/genius/bridge.py"),
    "omni-analyst": ("file", "tools/omni/bridge.py"),
    "hf-free": ("file", "tools/hf_sandbox/free.py"),      # v1990: offline catalogs/templates; prints only
    "hf-trend": ("file", "tools/hf_sandbox/free.py"),
    "hf-blender": ("file", "tools/hf_sandbox/free.py"),
    "pack-registry": ("file", "tools/packs/packs.py"),    # v1990: cards + static scan + safe unpack; never executes a pack
    "framecheck": ("file", "tools/framecheck/framecheck.py"),
    "blind-critic": ("file", "tools/critic/critic.py"),
    "phone-play-check": ("file", "tools/care/care.py"),
    "dragon-status": ("file", "tools/care/care.py"),
    "dragon-last": ("file", "tools/care/care.py"),
    "dragon-resources": ("file", "tools/care/care.py"),
    "keyboard-layout-fix": ("file", "tools/care/layout.py"),
    "media-hunter-615": ("file", "tools/media_hunter_615/mh.py"),
    "repo-fusion": ("file", "tools/repo_fusion/scripts/repo_fusion.py"),
    "media-hunter": ("file", "tools/media_hunter/mh.py"),
    "ultra-mind": ("module", "dragon.v103_ultra"),
    "expert-council": ("module", "dragon.v104_council"),
    "web-film": ("engine", "web_film"),
    "editorial-look": ("engine", "editorial"),
    "shadow-theatre": ("engine", "shadow_theatre"),
    "voice-studio": ("engine", "voice_studio"),
    "reel-hooks": ("engine", "reel_hooks"),
    "kling-director": ("engine", "kling_director"),
    "infinite-matrices": ("engine", "matrices"),
    "method-cards": ("engine", "cards"),
    "fetch-sources": ("file", "tools/fetch/fetch.py"),
    "free-stock": ("file", "tools/stock/free_photos.py"),
    "arena": ("file", "tools/arena/bracket.py"),
    "v10-thinking-checks": ("module", "dragon.v10_cognition"),
    "v10-catalog-audit": ("module", "dragon.v10_catalog"),
    "v10-video-gate": ("module", "dragon.v10_gate"),
    "v10-pixel-qa": ("module", "dragon.v10_color"),
    "v10-kling-pack": ("module", "dragon.v10_kling"),
    "v10-media-audit": ("module", "dragon.v10_media"),
    "v10-reference-links": ("module", "dragon.v10_cli"),
    # merged from v10.8.1
    "chrome-control": ("engine", "chrome"),
    "cloud-browser": ("engine", "cloud_browser"),
    "kosif-downloads": ("engine", "kosif"),
    "lyric-ass": ("file", "tools/lyric_remake/lyric_ass.py"),
    "psd-studio": ("file", "tools/psd_studio/psd.py"),
    "song-map": ("file", "tools/cinema_extras/song_map.py"),
    "contact-sheets": ("file", "tools/cinema_extras/sheets.py"),
    "skill-atlas": ("file", "tools/cinema_extras/skill_atlas.py"),
    # v10.8.1 ids mapped to the tools that do the same job in this line
    "idea-forge": ("file", "tools/absolute_creativity/bridge.py"),
    "arabic-font-lab": ("file", "tools/absolute_creativity/bridge.py"),
    "expert-lessons": ("file", "tools/brain/brain.py"),
    "ultra-mind-think": ("file", "tools/brain/brain.py"),
    "rea-digest": ("file", "tools/rea_ultra/bridge.py"),
    # v10.13 / v10.14
    "superpowers-hub": ("file", "tools/superpowers/sp.py"),
    "atlas-picks": ("file", "tools/atlas/atlas.py"),
    "github-atlas-top1000": ("file", "tools/github_atlas/atlas.py"),
    "re-front-door": ("file", "tools/re/re.py"),
    "dragon-brain": ("file", "tools/brain/brain.py"),
    # v10.15
    "onscreen-check": ("file", "tools/onscreen/onscreen.py"),
    # v10.16
    "paint-studio": ("file", "tools/paint/bridge.py"),
    "grab": ("file", "tools/grab/bridge.py"),
    "toon": ("file", "tools/toon/toon.py"),
    "links": ("file", "tools/links/links.py"),
    # external programs: discoverable = found on PATH (they had no entrypoint, so always "unverified")
    "deep-filter": ("program", "deep-filter"),
    "demucs": ("program", "demucs"),
    "whisperx": ("program", "whisperx"),
    "upscayl": ("program", "upscayl-bin"),
    "rembg": ("program", "rembg"),
    "auto-editor": ("program", "auto-editor"),
    "scenedetect": ("program", "scenedetect"),
}


def _exists(typ: str, name: str) -> bool:
    if typ == "program":
        return shutil.which(name) is not None
    if typ == "module":
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ValueError, ModuleNotFoundError):
            return False
    if typ == "engine":
        return (APP / "engines" / name / "__main__.py").is_file()
    if typ == "file":
        return (SKILL / name).is_file()
    return False


def read_registry(path: Path | None = None) -> list[dict[str, Any]]:
    source = Path(path or REGISTRY)
    raw = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict) or not isinstance(raw.get("tools"), list):
        raise ValueError("invalid own_tools registry")
    ids = set()
    records = []
    for item in raw["tools"]:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in ("id", "cmd", "ar", "en", "what")):
            raise ValueError("malformed tool card")
        if item["id"] in ids:
            raise ValueError(f"duplicate tool ID: {item['id']}")
        ids.add(item["id"])
        records.append(item)
    return records


def inspect_tool(card: dict[str, Any]) -> dict[str, Any]:
    tool_id = card["id"]
    if tool_id in ENTRYPOINTS:
        entry_kind, entry_name = ENTRYPOINTS[tool_id]
        entry_ok = _exists(entry_kind, entry_name)
    else:
        # Unrecognized records cannot turn a command string into an executable adapter.
        entry_kind, entry_name, entry_ok = "unregistered", "", False
    missing = [f"{kind}:{name}" for kind, name in NEEDS.get(tool_id, ()) if not _exists(kind, name)]
    if not entry_ok:
        status = "unverified_entrypoint"
    elif missing:
        status = "missing_dependencies"
    else:
        status = "discoverable"
    return {
        "id": tool_id, "name_ar": card["ar"], "name_en": card["en"],
        "command_example": card["cmd"], "entrypoint": f"{entry_kind}:{entry_name}",
        "entrypoint_found": entry_ok, "missing": missing, "status": status,
        "executed": False,
        "proof_level": "static_inspection_only",  # no 'proven' claims from registration alone
    }


def probe_tools(cards: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Pure inspection; no shell, network, downloads, installations or media changes."""
    rows = [inspect_tool(x) for x in (read_registry() if cards is None else cards)]
    return {
        "kind": "black-dragon/tool-probe", "inspection_only": True,
        "total": len(rows),
        "discoverable": sum(r["status"] == "discoverable" for r in rows),
        "missing_dependencies": sum(r["status"] == "missing_dependencies" for r in rows),
        "unverified_entrypoint": sum(r["status"] == "unverified_entrypoint" for r in rows),
        "tools": rows,
    }


def ecosystem() -> dict[str, Any]:
    """Check common local Superpowers and Atlas locations, without cloning anything."""
    from .catalog import load_sources, _p
    found = []
    for r in load_sources().get("skill_roots", []):
        root = _p(r["path"])
        found.append({"source": r["source"], "path": str(root), "present": root.is_dir()})
    from .superpowers import survey, pick
    chosen = pick()
    for r in survey():
        found.append({"source": "superpowers-entrypoint", "path": r["path"], "present": r["present"],
                      "chosen": chosen is not None and Path(r["path"]) == chosen})
    return {"local_only": True, "roots": found, "superpowers_root": str(chosen) if chosen else None}


def plan(query: str, mode: str = "smart", limit: int = 6) -> dict[str, Any]:
    """Create a task-dependent plan; all=inspect all registered tools, NOT run all.

    The indexed KOSIF powers and skills remain *ideas* until a runnable adapter is found.
    """
    if not query.strip():
        raise ValueError("provide a task to plan")
    if mode not in ("smart", "full"):
        raise ValueError("mode must be smart or full")
    if not 1 <= limit <= 30:
        raise ValueError("limit must be 1..30")
    cards = read_registry()
    inspection = probe_tools(cards)
    lookup = {r["id"]: r for r in inspection["tools"]}
    matched = router.find(query, limit=limit + 10)
    relevant_ids = [r["name"] for r in matched.get("tool", []) if r.get("source") == "black-dragon" and r["name"] in lookup]
    # Basic Arabic/English fallback also works before a catalog has been rebuilt with own tools.
    from .arabic import tokens
    q_tokens = set(tokens(query))
    if not relevant_ids:
        scored = []
        for c in cards:
            score = len(q_tokens & set(tokens(" ".join([c["id"], c["ar"], c["en"], c["what"]]))))
            if score:
                scored.append((score, c["id"]))
        relevant_ids = [x for _, x in sorted(scored, key=lambda z: (-z[0], z[1]))]
    # Quantitative motion, camera, or editing constraints use numeric calculation first.
    physical_triggers = ("فيزياء", "رياضيات", "احسب", "حساب", "جاذبية", "سقوط", "ارتداد", "فريمات", "تايم كود",
                         "سرعة", "مسافة", "عدسة", "عمق الميدان", "زاوية الرؤية", "انحناء الحركة", "تسارع",
                         "easing", "physics", "math", "bpm", "timecode", "fov", "focal", "bounce", "spring", "dolly")
    if any(t in query.casefold() for t in physical_triggers) and "physics-math" in lookup:
        relevant_ids = ["physics-math"] + [x for x in relevant_ids if x != "physics-math"]
    # Explicit creativity language should route to the installed creative brief/idea bridge.
    # This is only a suggestion for planning: no tool is run by this function.
    q_raw = query.casefold()
    creative_triggers = ("إبداع", "ابداع", "ابتكار", "ابتكر", "كونسبت", "حبكة", "سيناريو",
                         "creative", "creativity", "concept", "brainstorm", "art direction")
    if any(t in q_raw for t in creative_triggers) and "absolute-creativity" in lookup:
        relevant_ids = ["absolute-creativity"] + [x for x in relevant_ids if x != "absolute-creativity"]
    chosen_ids = list(dict.fromkeys(relevant_ids))[:limit]
    for fallback in ("dragon-montage", "cinema-film"):
        if not chosen_ids and any(k in query.lower() for k in ("فيديو", "فديو", "مونتاج", "video", "reel")):
            chosen_ids = [fallback]
            break
    selected = [lookup[x] for x in chosen_ids]
    summary = [{"id": x["id"], "status": x["status"], "missing": x["missing"],
                "command_example": x["command_example"], "proof_level": x["proof_level"]} for x in selected]
    from .superpowers import bridge
    return {
        "kind": "black-dragon/plan", "query": query, "mode": mode,
        "superpowers_bridge": bridge(query, full=mode == "full"),
        "execution_performed": False, "inference_only": True,
        "all_tools_examined": inspection["total"] if mode == "full" else len(selected),
        "selected_tools": summary,
        "full_inspection": inspection if mode == "full" else None,
        "relevant_skills": [{"name": x["name"], "source": x["source"], "path": x["path"],
                              "status": "indexed_only"} for x in matched.get("skill", [])[:limit]],
        "thinking_protocol": [
            "1. Normalize user requirements and explicitly list acceptance criteria",
            "2. Compare hypotheses, sources, counterarguments and at least one simpler alternative",
            "3. Select discoverable adapters; block missing dependencies or unauthorized operations",
            "4. Execute only after relevant approvals, capturing tool-specific logs/evidence",
            "5. Verify output technically and visually; report failures and scope honestly",
        ],
        "approval_gates": ["paid credits", "third-party upload of private files", "installation", "publishing or GitHub push"],
        "notice": "Planning/inspection is not execution. Registered, indexed, or discoverable does not mean tested or proven.",
    }
