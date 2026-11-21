"""Performance lens: measure the real wall time of every call to an op.

Each target symbol is wrapped with a timer, then the module's own test suite
runs unchanged; every call the tests make is timed on the real (synthetic)
inputs those tests build. Nothing is written; results are returned as data.
Timings are machine-specific and are evidence of bounded cost, not a benchmark.
"""
from __future__ import annotations

import functools
import importlib
import io
import time
import unittest

# topic owner module -> (test module, {op name: symbol name in module})
IO_TARGETS = {
    'knowledge_v25': 'test_knowledge_v25', 'database_v25': 'test_database_v25',
    'media_analysis_v25': 'test_media_analysis_v25', 'editing_v25': 'test_editing_v25',
    'audio_v25': 'test_audio_v25', 'automation_v25': 'test_automation_v25',
    'release_v26': 'test_release_v26',
}
# Pre-roadmap code whose topics lacked the performance lens.
LEGACY_TARGETS = {
    'scene_edit_v16': ('test_scene_edit_v16', ('analyze_cuts', 'recut')),
    'audio_scene_v17': ('test_audio_scene_v17', ('detect_silences', 'suggest_edit')),
    'lip_sync': ('test_lip_sync_v13', ('levels_from_audio',)),
    'verify_media': ('test_verify_media', ('verify_video',)),
    'capability_runtime': ('test_capability_v15', ('execute',)),
}
DEFAULT_BUDGET_S = 60.0


def _timed(fn, sink, name):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            sink.setdefault(name, []).append(time.perf_counter() - start)
    return wrapper


def measure(module_name, test_module, symbols, *, budget_s=DEFAULT_BUDGET_S):
    """Wrap `symbols` of `module_name`, run `test_module`, return per-symbol timings."""
    if not 0 < budget_s <= 600:
        raise ValueError('budget_s must be in (0, 600]')
    module = importlib.import_module(module_name)
    sink, originals = {}, {}
    ops_table = getattr(module, 'OPS', None)
    for name in symbols:
        fn = getattr(module, name)
        originals[name] = fn
        wrapped = _timed(fn, sink, name)
        setattr(module, name, wrapped)
        if isinstance(ops_table, dict) and name in ops_table:
            ops_table[name] = wrapped
    try:
        # Import the test module only after patching so `from x import y` sees the timers.
        import sys
        sys.modules.pop(test_module, None)
        suite = unittest.defaultTestLoader.loadTestsFromName(test_module)
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    finally:
        for name, fn in originals.items():
            setattr(module, name, fn)
            if isinstance(ops_table, dict) and name in ops_table:
                ops_table[name] = fn
    rows = {}
    for name in symbols:
        calls = sink.get(name, [])
        rows[name] = {'calls': len(calls),
                      'max_s': round(max(calls), 4) if calls else None,
                      'total_s': round(sum(calls), 4) if calls else 0.0,
                      'within_budget': bool(calls) and max(calls) <= budget_s}
    return {'module': module_name, 'test_module': test_module, 'budget_s': budget_s,
            'tests_run': result.testsRun, 'failures': len(result.failures),
            'errors': len(result.errors), 'skipped': len(result.skipped), 'ops': rows,
            'note': 'wall time on this machine for the inputs the module tests build'}


def measure_io_modules(budget_s=DEFAULT_BUDGET_S):
    out = {}
    for module_name, test_module in IO_TARGETS.items():
        module = importlib.import_module(module_name)
        out[module_name] = measure(module_name, test_module, tuple(module.TOPICS.values()), budget_s=budget_s)
    return out


def measure_legacy(budget_s=DEFAULT_BUDGET_S):
    return {m: measure(m, t, syms, budget_s=budget_s) for m, (t, syms) in LEGACY_TARGETS.items()}
