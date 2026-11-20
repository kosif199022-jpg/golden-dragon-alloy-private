r"""Verify a newly built *isolated* Windows GoldenDragon EXE without launching it.

This verifier is deliberately stricter than the legacy verify_bundle.py:
it requires the unified native core modules and the existing runtime assets.

Usage:
    python -B verify_unified_bundle.py "...\isolated-package\dist\GoldenDragon\GoldenDragon.exe"
Never modifies, starts or installs the target.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

NEED_MODULES = (
    "dragon_fusion", "golden_tools", "golden_steer", "control", "brain",
    "gd_runtime", "capability_ledger", "audit_tree", "native_registry", "blender_engine",
)
NEED_DATA = (
    "fusion/index.json", "fusion/recipes.json", "fusion/lessons.json",
    "golden/library.json", "golden/studio.json",
    "ui/index.html", "ui/golden-dragon.ico", "ui/version.txt",
    "chrome_extension/background.js",
)


def verify_inventory(exe: Path, entry_names: set[str], pyz_modules: set[str]) -> dict:
    """Pure metadata validation; does not load executable code."""
    exe = Path(exe)
    internal = exe.parent / "_internal"
    absent = [name for name in NEED_DATA if not (internal / name).is_file()]
    modules_missing = [name for name in NEED_MODULES if name not in pyz_modules]
    data = {
        "exe": str(exe), "bytes": exe.stat().st_size,
        "entry_script": "app" in entry_names,
        "module_count": len(pyz_modules),
        "modules_missing": modules_missing, "data_missing": absent,
        "fusion_units": None, "recipes": None,
        "extension_port_47851": False,
        "success": False, "runtime_behavior_verified": False,
    }
    if "fusion/index.json" not in absent:
        units = json.loads((internal / "fusion" / "index.json").read_text(encoding="utf-8-sig"))
        data["fusion_units"] = len(units.get("units") or [])
    if "fusion/recipes.json" not in absent:
        recipes = json.loads((internal / "fusion" / "recipes.json").read_text(encoding="utf-8-sig"))
        data["recipes"] = len(recipes)
    if "chrome_extension/background.js" not in absent:
        bg = (internal / "chrome_extension" / "background.js").read_text(encoding="utf-8-sig")
        data["extension_port_47851"] = "const PORT = 47851;" in bg
    data["success"] = bool(
        data["entry_script"] and not absent and not modules_missing
        and data["extension_port_47851"] and data["fusion_units"] and data["recipes"]
    )
    return data


def inspect_exe(exe: Path) -> dict:
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader

    car = CArchiveReader(str(exe))
    names = set(car.toc)
    pyz_name = next((name for name in names if name.endswith(".pyz")), None)
    if not pyz_name:
        raise ValueError("PyInstaller PYZ archive missing")
    offset = car._start_offset + car.toc[pyz_name][0]
    archive = ZlibArchiveReader(f"{exe}?{offset}")
    return verify_inventory(exe, names, set(archive.toc))


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("exe", type=Path)
    p.add_argument("--require-temp", action="store_true", help="refuse to inspect a non-TEMP binary")
    args = p.parse_args(argv)
    if not args.exe.is_file():
        p.error("EXE not found")
    if args.require_temp:
        import os
        import tempfile
        actual = args.exe.resolve()
        temp = Path(tempfile.gettempdir()).resolve()
        if not actual.is_relative_to(temp):
            p.error("refusing to verify an EXE outside TEMP")
    try:
        report = inspect_exe(args.exe)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        p.exit(2, f"Unable to validate bundle: {error}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
