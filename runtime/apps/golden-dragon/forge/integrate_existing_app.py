"""Safely integrate the knowledge bridge into the already-generated Golden Dragon app.

Useful if the full generator cannot run because legacy external inputs are missing.
Backs up originals and updates the generated-file manifest with an explicit integration
record, so the generator's integrity guard remains usable.
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

FORGE = Path(__file__).resolve().parent
BASE = FORGE.parent
APP = BASE / "app"
PATCH_FILE = FORGE / "gd_patches" / "gd_knowledge.py"
STAMP = APP / ".gd_generated.json"
BACKUP = FORGE / "data" / "knowledge-app-integration-backup"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def patch_text(path, fn):
    original = path.read_bytes()
    bom = original.startswith(b"\xef\xbb\xbf")
    text = original.decode("utf-8-sig")
    newlines = "\r\n" if text.count("\r\n") else "\n"
    modified = fn(text.replace("\r\n", "\n"))
    return ((b"\xef\xbb\xbf" if bom else b"") +
            modified.replace("\n", newlines).encode("utf-8"))


def integrate(check_only=False):
    spec = importlib.util.spec_from_file_location("gd_knowledge", PATCH_FILE)
    patcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patcher)
    if not (BASE / "knowledge" / "golden-dragon-runtime.zip").is_file():
        raise FileNotFoundError("Knowledge ZIP has not been bundled into repo")
    existing = {
        "app.py": APP / "app.py", "ui/index.html": APP / "ui/index.html",
        "build.ps1": APP / "build.ps1"
    }
    if not STAMP.is_file():
        raise RuntimeError("No generated manifest; refusing direct patch")
    meta = json.loads(STAMP.read_text(encoding="utf-8"))
    if "knowledge_integration" in meta:
        raise RuntimeError("Knowledge integration already installed; do not patch twice")
    for rel, path in existing.items():
        old = path.read_bytes()
        if digest(old) != meta["files"][rel]:
            raise RuntimeError("Untracked user edits to " + rel + "; refusing overwrite")
    replacements = {
        "app.py": patch_text(existing["app.py"], patcher.patch_app),
        "ui/index.html": patch_text(existing["ui/index.html"], patcher.patch_ui),
        "build.ps1": patch_text(existing["build.ps1"], patcher.patch_build),
        "golden_knowledge_bridge.py": (
            FORGE / "overlay" / "golden_knowledge_bridge.py").read_bytes(),
        "golden_dragon_runtime.py": (
            FORGE / "golden_dragon_runtime.py").read_bytes(),
    }
    # Compile all affected Python code BEFORE writing anything.
    for name in ("app.py", "golden_knowledge_bridge.py", "golden_dragon_runtime.py"):
        compile(replacements[name].decode("utf-8-sig"), name, "exec")
    if b"knowledge_widget" in replacements["ui/index.html"]:
        raise RuntimeError("Unexpected widget source reference")
    if b"id=\"gdkPane\"" not in replacements["ui/index.html"]:
        raise RuntimeError("Knowledge search UI was not installed")
    if check_only:
        return {"checked": True, "patched_files": list(replacements), "source_unchanged": True}
    if BACKUP.exists():
        raise FileExistsError("Integration backup exists: inspect before retry")
    for rel, path in existing.items():
        dest = BACKUP / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    shutil.copy2(STAMP, BACKUP / ".gd_generated.json")
    for rel, data in replacements.items():
        dest = APP / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        meta["files"][rel] = digest(data)
    meta["knowledge_integration"] = {
        "method": "direct patch of generated app while legacy analysis input is missing",
        "bridge": "golden_knowledge_bridge.py",
        "runtime": "golden_dragon_runtime.py",
        "bundle": "apps/golden-dragon/knowledge/golden-dragon-runtime.zip",
        "bundle_sha256": digest((BASE / "knowledge" / "golden-dragon-runtime.zip").read_bytes()),
        "backups_saved": str(BACKUP),
        "rebuild_note": "forge/make_golden_dragon.py also includes this integration for future regeneration"
    }
    STAMP.write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                     encoding="utf-8", newline="\n")
    return {"integrated": True, "files": list(replacements),
            "backup": str(BACKUP), "bundle_sha256": meta["knowledge_integration"]["bundle_sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(integrate(args.check), ensure_ascii=True))
