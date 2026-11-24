"""Narrow CLI dispatch. Full rose.main remains unchanged for unsupported commands."""
from __future__ import annotations

import argparse
import importlib
import sys

# Only commands with the same standalone registration and no global DB argument.
# start must load all extensions to report their actual availability.
FAST_COMMANDS = {
    "ops": "rose_catalog", "describe": "rose_catalog", "find": "rose_catalog",
    "understand": "rose_agent", "brief": "rose_agent",
    "vn-dua-analyze": "vn_dua_v47",
}


def dispatch(argv):
    if not argv or argv[0] not in FAST_COMMANDS:
        return None
    name = argv[0]
    module = importlib.import_module(FAST_COMMANDS[name])
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="rose.py")
    subs = parser.add_subparsers(dest="command", required=True)
    module.register(subs)
    # A registration error must not silently execute another handler.
    if name not in subs.choices:
        raise RuntimeError(f"Missing registered command: {name}")
    args = parser.parse_args(argv)
    return args.ext_func(args)
