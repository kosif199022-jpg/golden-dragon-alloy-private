"""Golden Dragon native execution registry — *actual adapters*, not index claims.

This is the stable dispatch boundary for installed, directly executable core
operations. A catalog entry becomes executable only if an explicit adapter is
implemented and its prerequisites are present. No dynamic imports based on
catalog IDs, arbitrary commands, shell, MCP bridges or unreviewed tool paths.

The registry is independent of White Bird / Golden Bird and can be bundled
directly with the Golden Dragon standalone application.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from gd_runtime import GoldenDragonCore

# Entries below are all backed by named, explicit GoldenDragonCore.execute ops.
# "ready" is a passive prerequisite state, never an assertion of test success.
ADAPTERS = {
    "catalog.audit": {
        "description": "Check catalog references and local file presence",
        "requires": ("fusion/index.json", "fusion/recipes.json"),
        "command": None,
        "input": "none", "writes_output": False,
    },
    "source.audit": {
        "description": "Audit the owned application source tree",
        "requires": (), "command": None,
        "input": "none", "writes_output": False,
    },
    "binary.pe_header": {
        "description": "Inspect Windows PE metadata without executing the target",
        "requires": (), "command": None,
        "input": "binary", "writes_output": False,
    },
    "binary.imports": {
        "description": "Inspect PE DLL imports using static REA analysis",
        "requires": (), "command": "rea",
        "input": "binary", "writes_output": False,
    },
    "media.probe": {
        "description": "Probe local audio/video metadata with FFprobe",
        "requires": (), "command": "ffprobe",
        "input": "media", "writes_output": False,
    },
    "media.transcode": {
        "description": "Convert local media with FFmpeg into a new TEMP file",
        "requires": (), "command": "ffmpeg",
        "input": "media", "writes_output": True,
    },
    "blender.render": {
        "description": "Render a reviewed mechanical 3D scene using Blender",
        "requires": (), "command": "blender",
        "input": "scene", "writes_output": True,
    },
    "audit": {
        "description": "Combine non-mutating catalog, source and binary checks",
        "requires": ("fusion/index.json", "fusion/recipes.json"),
        "command": None,
        "input": "none", "writes_output": False,
    },
}


def native_status(app_root: Path) -> dict[str, Any]:
    """Inspect explicit adapters without importing or executing target assets."""
    root = Path(app_root)
    result = []
    for operation, adapter in ADAPTERS.items():
        absent = [r for r in adapter["requires"] if not (root / r).is_file()]
        command = adapter["command"]
        found = bool(shutil.which(command)) if command else True
        # Windows tools may be installed through npm's .cmd shim.
        if command == "rea":
            found = found or bool(shutil.which("rea.cmd"))
        ready = not absent and found
        result.append({
            "operation": operation,
            "description": adapter["description"],
            "input": adapter["input"],
            "writes_output": adapter["writes_output"],
            "prerequisite_available": ready,
            "missing_files": absent,
            "external_command": command,
            "external_command_found": found,
            "runtime_tested_by_this_call": False,
        })
    return {
        "schema": "golden-dragon.native-adapters.v1",
        "adapter_count": len(result),
        "adapters": result,
        "indexed_capabilities_all_executable": False,
        "note": "Prerequisite availability never constitutes a successful execution test",
    }


def native_execute(
    app_root: Path,
    operation: str,
    *,
    local_path: str | None = None,
    profile: str = "mp4-compatible",
    preset: str = "mechanical_gear",
    resolution: int = 512,
    approve_new_file: bool = False,
) -> dict[str, Any]:
    """Invoke only a reviewable allowlisted adapter with fixed typed inputs.

    Conversion makes a new TEMP file, so it requires explicit acknowledgement.
    It cannot accept an arbitrary command line or output directory.
    """
    if operation not in ADAPTERS:
        raise ValueError("unknown native adapter: " + str(operation))
    adapter = ADAPTERS[operation]
    root = Path(app_root)
    expected_input = adapter["input"]
    if expected_input in ("binary", "media"):
        if not isinstance(local_path, str) or not local_path.strip():
            raise ValueError("local path required for adapter: " + operation)
        if "://" in local_path:
            raise ValueError("remote URLs are not accepted by native adapters")
    if adapter["writes_output"] and approve_new_file is not True:
        raise ValueError("explicit approval is required to create a new file")
    info = next(x for x in native_status(root)["adapters"] if x["operation"] == operation)
    if not info["prerequisite_available"]:
        raise ValueError("native adapter prerequisites missing: " + operation)

    index = root / "fusion" / "index.json"
    recipes = root / "fusion" / "recipes.json"
    kwargs: dict[str, Any] = {}
    if expected_input == "binary":
        kwargs["binary"] = Path(local_path)
    elif expected_input == "media":
        kwargs["media"] = Path(local_path)
        kwargs["profile"] = profile
    elif expected_input == "scene":
        kwargs["preset"] = preset
        kwargs["resolution"] = resolution
    if operation in ("catalog.audit", "audit"):
        kwargs["index"], kwargs["recipes"] = index, recipes
    core = GoldenDragonCore(root, **kwargs)
    # Source auditing uses the owned root and never imports target app code.
    return core.execute(operation)


def native_report_json(app_root: Path) -> str:
    return json.dumps(native_status(app_root), ensure_ascii=False, indent=2)
