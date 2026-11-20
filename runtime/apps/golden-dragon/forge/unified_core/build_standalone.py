"""Standalone Golden Dragon source composer. No White/Golden Bird forge dependency.

Uses the versioned Golden Dragon app as the owned source baseline, overlays
the native unified core and the latest fusion actions, and emits a NEW TEMP
build tree. It does not modify the baseline, installed EXE, Git branches,
Desktop shortcuts or Windows settings.

This is a first-stage dependency separation, not evidence that every indexed
engine is executable or that all sibling code has been absorbed.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import shutil
import tempfile
from pathlib import Path


CORE_MAP = {
    "gd_runtime.py": "runtime.py",
    "capability_ledger.py": "capability_ledger.py",
    "audit_tree.py": "audit_tree.py",
    "native_registry.py": "native_registry.py",
    "blender_engine.py": "blender_engine.py",
}
EVIDENCE_ACTIONS = (
    "audit", "probe_media", "inspect_binary_imports", "transcode_media",
    "native_status", "native_exec",
)


def _literal_assignment(source: str, variable: str) -> str:
    tree = ast.parse(source)
    values = [
        ast.literal_eval(node.value) for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == variable
                for target in node.targets)
    ]
    if len(values) != 1 or not isinstance(values[0], str):
        raise ValueError("expected exactly one string constant: " + variable)
    return values[0]


def _index(source_lines: list[str], line: int, col: int) -> int:
    """AST col_offset uses UTF-8 bytes; text includes Arabic and emoji."""
    return sum(map(len, source_lines[:line - 1])) + len(
        source_lines[line - 1].encode("utf-8")[:col].decode("utf-8")
    )


def _replace_ast_spans(source: str, updates: list[tuple[ast.AST, str]]) -> str:
    lines = source.splitlines(keepends=True)
    changes = []
    for node, replacement in updates:
        start = _index(lines, node.lineno, node.col_offset)
        end = _index(lines, node.end_lineno, node.end_col_offset)
        changes.append((start, end, replacement))
    for start, end, replacement in sorted(changes, reverse=True):
        source = source[:start] + replacement + source[end:]
    return source


def _lazy_anthropic(source: str) -> str:
    # Locate the import structurally, including when it is the first line.
    tree = ast.parse(source)
    imports = [
        node for node in tree.body
        if isinstance(node, ast.Import)
        and any(alias.name == "anthropic" for alias in node.names)
    ]
    if len(imports) != 1 or len(imports[0].names) != 1:
        raise ValueError("cannot safely identify the single Anthropic import")
    proxy = (
        "import importlib as _gd_importlib\n"
        "class _GoldenLazyAnthropic:\n"
        "    def __getattr__(self, name):\n"
        "        real_sdk = _gd_importlib.import_module('anthropic')\n"
        "        globals()['anthropic'] = real_sdk\n"
        "        return getattr(real_sdk, name)\n"
        "anthropic = _GoldenLazyAnthropic()"
    )
    return _replace_ast_spans(source, [(imports[0], proxy)])


def compose_app(baseline: str, forge: str) -> str:
    """Patch precisely one tool call and one dispatch function via Python AST."""
    tool_spec = _literal_assignment(forge, "FUSION_TOOL").strip()
    if not tool_spec.endswith(","):
        raise ValueError("fusion tool declaration is not a list element")
    tool_spec = tool_spec[:-1]
    parse_test = ast.parse("x = [" + tool_spec + "]")
    new_call = parse_test.body[0].value.elts[0]
    if not isinstance(new_call, ast.Call):
        raise ValueError("fusion tool declaration does not parse as a call")
    dispatch = _literal_assignment(forge, "FUSION_DISPATCH").split(
        "\ndef skills_index():", 1
    )[0]
    replacement_tree = ast.parse(dispatch)
    if len(replacement_tree.body) != 1 or not isinstance(
        replacement_tree.body[0], ast.FunctionDef
    ) or replacement_tree.body[0].name != "fusion_dispatch":
        raise ValueError("invalid fusion dispatch definition")

    tree = ast.parse(baseline)
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == "tool"
        and node.args and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "fusion"
    ]
    funcs = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "fusion_dispatch"
    ]
    if len(calls) != 1 or len(funcs) != 1:
        raise ValueError("expected exactly one fusion tool and dispatch function")
    patched = _replace_ast_spans(baseline, [
        (calls[0], tool_spec),
        (funcs[0], dispatch.rstrip()),
    ])
    patched = _lazy_anthropic(patched)
    ast.parse(patched)
    if not all(name in patched for name in EVIDENCE_ACTIONS):
        raise ValueError("generated app missing a native action")
    if "import gd_runtime" not in patched:
        raise ValueError("native unified core was not wired into dispatch")
    return patched


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _safe_destination(path: Path) -> Path:
    path = path.expanduser().resolve()
    temp = Path(tempfile.gettempdir()).resolve()
    if not path.is_relative_to(temp) or path == temp:
        raise ValueError("output must be a new subdirectory of the system TEMP")
    if path.exists():
        raise ValueError("output already exists; refusing to overwrite")
    return path


def build(project_root: Path, destination: Path, *, dry_run: bool = False) -> dict:
    """Portable, non-overwriting composition using only owned app and forge files."""
    project_root = Path(project_root).resolve()
    destination = _safe_destination(Path(destination))
    app = project_root / "app"
    core = project_root / "forge" / "unified_core"
    forge = project_root / "forge" / "make_golden_dragon.py"
    checks = [
        app / "app.py", app / "ui" / "index.html",
        app / "fusion" / "index.json", app / "fusion" / "recipes.json",
        forge, core / "build_isolated.ps1",
    ] + [core / f for f in CORE_MAP.values()]
    if any(not p.is_file() for p in checks):
        raise ValueError("standalone source incomplete: " + ", ".join(
            str(p) for p in checks if not p.is_file()
        ))
    # Block symlink escapes from the versioned source tree.
    if any(p.is_symlink() for p in app.rglob("*")):
        raise ValueError("baseline app contains symlinks; refusing to copy")
    rendered = compose_app(
        (app / "app.py").read_text(encoding="utf-8-sig"),
        forge.read_text(encoding="utf-8-sig"),
    )
    index = json.loads((app / "fusion" / "index.json").read_text(encoding="utf-8-sig"))
    recipes = json.loads((app / "fusion" / "recipes.json").read_text(encoding="utf-8-sig"))
    counts = {
        "catalog_units": len(index.get("units") or []),
        "recipes": len(recipes),
        "source_sha256": _hash(app / "app.py"),
        "native_actions": list(EVIDENCE_ACTIONS),
        "requires_sibling_forges": False,
        "runtime_capabilities_all_verified": False,
    }
    if dry_run:
        return {"dry_run": True, "destination": str(destination), **counts}
    output = destination / "app"
    shutil.copytree(app, output, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".gd_generated.json", "build.ps1", "dist", "build"
    ))
    (output / "app.py").write_text(rendered, encoding="utf-8")
    for dest, name in CORE_MAP.items():
        shutil.copy2(core / name, output / dest)
    # Keep the safe packager in the expected standalone repo layout.
    safe = destination / "forge" / "unified_core"
    safe.mkdir(parents=True, exist_ok=True)
    shutil.copy2(core / "build_isolated.ps1", safe / "build_isolated.ps1")
    for p in output.glob("*.py"):
        ast.parse(p.read_text(encoding="utf-8-sig"), filename=str(p))
    file_hashes = {
        str(p.relative_to(output)).replace("\\", "/"): _hash(p)
        for p in output.rglob("*") if p.is_file()
    }
    # Maintain the previous generated-source integrity contract, but never
    # restore its auto-installing build.ps1. This stamp is deterministic.
    unit_counts = Counter(str(unit.get("kind") or "unknown")
                          for unit in index.get("units") or [])
    stamp = {
        "schema": "golden-dragon.generated-standalone.v1",
        "source": str(app),
        "source_app_sha256": counts["source_sha256"],
        "fusion_counts": dict(unit_counts),
        "recipes": len(recipes),
        "files": dict(file_hashes),
    }
    (output / ".gd_generated.json").write_text(
        json.dumps(stamp, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "schema": "golden-dragon.standalone-source.v1",
        **counts,
        "files": {str(p.relative_to(output)).replace("\\", "/"): _hash(p)
                  for p in output.rglob("*") if p.is_file()},
    }
    (destination / "standalone-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"dry_run": False, "destination": str(destination),
            "files": len(manifest["files"]), **counts}



def verify_standalone_output(destination: Path) -> dict:
    """Independently verify a standalone source snapshot; never mutate it."""
    root = Path(destination).resolve()
    manifest_file = root / "standalone-manifest.json"
    app_root = root / "app"
    if not manifest_file.is_file() or not app_root.is_dir():
        raise ValueError("standalone manifest or app directory is missing")
    record = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
    expected = record.get("files")
    if not isinstance(expected, dict) or not expected:
        raise ValueError("standalone manifest lacks file digests")
    observed = {}
    for p in app_root.rglob("*"):
        if p.is_symlink():
            raise ValueError("generated source contains a symlink")
        if p.is_file():
            observed[str(p.relative_to(app_root)).replace("\\", "/")] = _hash(p)
    if set(observed) != set(expected):
        raise ValueError("generated source file list differs from manifest")
    corrupt = [name for name, digest in expected.items()
               if observed[name] != digest]
    if corrupt:
        raise ValueError("generated source checksum mismatch: " + ", ".join(corrupt[:8]))
    stamp = json.loads((app_root / ".gd_generated.json").read_text(encoding="utf-8-sig"))
    stamped = stamp.get("files")
    if not isinstance(stamped, dict):
        raise ValueError("generated identity stamp is missing file digests")
    for name, digest in stamped.items():
        if observed.get(name) != digest:
            raise ValueError("generated identity checksum mismatch: " + name)
    return {"verified": True, "files": len(expected),
            "catalog_units": record.get("catalog_units"),
            "requires_sibling_forges": record.get("requires_sibling_forges")}



def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", type=Path,
                   default=Path(__file__).resolve().parents[2])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verify", action="store_true", help="read-only check of an existing source bundle")
    args = p.parse_args(argv)
    report = (verify_standalone_output(args.out) if args.verify
              else build(args.project, args.out, dry_run=args.dry_run))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
