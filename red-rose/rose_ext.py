"""Red Rose V29 extension loader (W01).

rose.py calls ``rose_ext.load(subparsers)`` once after its own subcommands.
Each extension module exposes ``register(subparsers)`` and gives every parser it
adds ``set_defaults(ext_func=handler)``; ``handler(args) -> int`` prints exactly
one JSON document (or text with --text) and returns the exit code.

A module that is missing or fails to import/register never breaks rose.py: it is
recorded in ``LAST_LOAD['failed']`` (shown by ``rose.py start``) and the other
commands keep working.
"""
from __future__ import annotations

import importlib

EXT_MODULES = ['rose_run', 'rose_catalog', 'rose_env', 'rose_selfcheck', 'rose_fixtures',
               'rose_agent', 'rose_recipes', 'rose_check', 'rose_pack', 'rose_maintenance', 'rose_re_tools', 'rose_golden_deep', 'rose_golden_native', 'rose_white_native', 'rose_mind_v51', 'rose_see_native_v52', 'vn_dua_v47', 'rose_shot_detail', 'rose_motion_capture_v57', 'rose_motion_replay_v58', 'rose_source_preflight_v60', 'studio_fusion_v61', 'rose_skill_corpus_v61', 'rose_media_contract_v61', 'rose_evolution_v64', 'rose_distill_v66', 'rose_knowledge_v67', 'rose_montage_v65', 'rose_metric_v68', 'rose_intake_v69', 'rose_continuity_v69', 'rose_styles_v70', 'rose_borrow_v71', 'rose_direct_v71', 'living_pen']

LAST_LOAD = {'loaded': [], 'failed': [], 'skipped': []}


def _existing_commands(subparsers):
    try:
        return set(subparsers.choices)
    except AttributeError:
        return set()


def load(subparsers, modules=None):
    """Import and register every extension module -> {loaded, failed:[{module, error}], skipped}.

    ``skipped`` lists importable modules that have no register() (helper modules
    such as rose_fixtures). A module whose register() raises is rolled back: the
    commands it added before failing are removed so argparse stays consistent.
    """
    loaded, failed, skipped = [], [], []
    for name in list(EXT_MODULES if modules is None else modules):
        try:
            module = importlib.import_module(name)
        except Exception as exc:  # missing module, syntax error, failed dependency
            failed.append({'module': name, 'error': f'{type(exc).__name__}: {exc}'[:300]})
            continue
        register = getattr(module, 'register', None)
        if not callable(register):
            skipped.append(name)
            continue
        before = _existing_commands(subparsers)
        try:
            register(subparsers)
        except Exception as exc:
            _rollback(subparsers, before)
            failed.append({'module': name, 'error': f'register: {type(exc).__name__}: {exc}'[:300]})
            continue
        loaded.append(name)
    LAST_LOAD.clear()
    LAST_LOAD.update({'loaded': loaded, 'failed': failed, 'skipped': skipped})
    return {'loaded': list(loaded), 'failed': [dict(f) for f in failed], 'skipped': list(skipped)}


def _rollback(subparsers, before):
    try:
        added = set(subparsers.choices) - before
        for cmd in added:
            subparsers.choices.pop(cmd, None)
        subparsers._choices_actions[:] = [a for a in subparsers._choices_actions
                                          if getattr(a, 'dest', None) not in added]
    except AttributeError:
        pass


def status():
    """Copy of the last load result (for `start` / doctor-style reports)."""
    return {'loaded': list(LAST_LOAD.get('loaded', [])),
            'failed': [dict(f) for f in LAST_LOAD.get('failed', [])],
            'skipped': list(LAST_LOAD.get('skipped', []))}
