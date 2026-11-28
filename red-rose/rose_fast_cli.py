"""Narrow CLI dispatch. Full rose.main remains unchanged for unsupported commands."""
from __future__ import annotations

import argparse
import importlib
import sys

# Only commands with the same standalone registration and no global DB argument.
# start must load all extensions to report their actual availability.
FAST_COMMANDS = {
    "golden-native": "rose_golden_native", "golden-deep": "rose_golden_deep",
    "white-native": "rose_white_native", "mind": "rose_mind_v51", "see": "rose_see_native_v52",
    "ops": "rose_catalog", "describe": "rose_catalog", "find": "rose_catalog",
    "understand": "rose_agent", "brief": "rose_agent",
    "vn-dua-analyze": "vn_dua_v47",
    "shot-detail": "rose_shot_detail",
    "re-tools": "rose_re_tools",
    "motion-capture": "rose_motion_capture_v57",
    "motion-replay": "rose_motion_replay_v58",
    "source-preflight": "rose_source_preflight_v60",
    "studio-fusion": "studio_fusion_v61",
    "skill-corpus": "rose_skill_corpus_v61",
    "media-contract": "rose_media_contract_v61",
    "evolution": "rose_evolution_v64",
    "distill-skills": "rose_distill_v66",
    "knowledge": "rose_knowledge_v67",
    "montage-code": "rose_montage_v65",
    "metric-reconcile": "rose_metric_v68",
    "intake": "rose_intake_v69",
    "continuity": "rose_continuity_v69",
    "styles": "rose_styles_v70",
    "borrow": "rose_borrow_v71",
    "direct": "rose_direct_v71",
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
