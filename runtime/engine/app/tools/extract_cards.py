"""Turn the old generated card programs into DATA (data/cards/*.json) for ONE interpreter (engines/cards).

    python tools/extract_cards.py               # parse the old corpus, write data/cards/<family>.json + _index.json
    python tools/extract_cards.py --write-lib   # also (re)write engines/cards/lib/<module>.py helper packs first

Read-only on the old corpus, parsed with ``ast`` only (nothing in it is imported or executed here):
  runners  kosif-dragon-mind/runners/fam_*.py          @card("ID") functions returning (checks, outputs)
  programs kosif-superpowers/scripts/power_programs/*.py  PROGRAMS = {"ID": fn}, fn(work) -> [(name, ok, observed)]

Every card gets a record: id, family, title, source, fixtures, ffmpeg filter graphs, measurements, checks (name,
expected, structured target/tolerance when the condition is a plain comparison), negative control, engines, status.

A card becomes ``status: "data"`` only when its body is straight-line (assignments + one return; no loop, def,
lambda, if, try, with, import) and every name it uses is a local, a literal module constant, numpy/math/json/re/Path,
the harness (check, fx) or a helper whose AST hash (with all its transitive dependencies) equals the hash of the
same helper in an engines/cards/lib pack. Its program is stored as formula text; engines.cards.formula executes it.
Anything else is ``not_ported`` with the reason, or ``custom`` when engines/cards/custom.py has a hand port.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import collections
import copy
import operator
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = Path(__import__("os").environ.get("KOSIF_SKILLS_OLD") or Path.home() / "kosif-tool" / ".claude" / "skills")
RUNNERS = OLD / "kosif-dragon-mind" / "runners"
PROGRAMS = OLD / "kosif-superpowers" / "scripts" / "power_programs"
POWERS = OLD / "kosif-superpowers" / "data" / "powers"
ADAPTERS = OLD / "kosif-superpowers" / "data" / "black_dragon_adapters_powers_mind.json"
BUILD_REPORT = RUNNERS / "_build_report.json"
LIB = ROOT / "engines" / "cards" / "lib"
OUT = ROOT / "data" / "cards"
sys.path.insert(0, str(ROOT))

# Old modules whose shared helpers are packed into engines/cards/lib (chosen by cards unlocked per KB of helper code).
STD = {"np": "numpy", "math": "math", "json": "json", "re": "re", "Path": "pathlib"}
HARNESS = {"check", "fx", "sha"}
REPO_PATHS = {"REPO", "HERE", "SKILLS", "VEND", "ARC", "PVE", "SCRIPTS", "KM", "SP", "FONTS", "FONT", "SCR", "VENDOR",
              "NODE_MODULES", "PWC", "CHROME", "ROOT", "KIT", "MOTION_KIT", "HF", "TOOLS", "DATA"}
EXTERNAL_FN = {"sh", "py", "node", "node_js", "mk", "browser", "page", "hf", "run", "pysub", "run_py", "render", "vmod",
               "hf_render", "hf_project", "score_mod", "score_render"}
BUILTINS = set(dir(builtins))
ASSET_PATHS = {"FONTS", "FONT"}   # read-only font assets in the old repo: packs hold their resolved absolute path
CHECK_FNS = {"check", "chk", "eq", "truth"}
FIX_WORDS = ("tone", "click", "drum", "kick", "speech", "music_bed", "song", "bed", "fixture", "index_clip", "index_frames",
             "solid", "color_clip", "test_clip", "write_video", "write_wav", "scene", "counter", "cut_video", "texture",
             "plate", "canvas", "noise", "sweep", "chirp", "trim_counts", "loop", "grad")
MEAS_WORDS = ("ebur", "loud", "peak", "dom_freq", "dbfs", "rms", "seg_db", "band", "narrow_db", "onset", "envelope",
              "frames", "probe", "vstream", "astreams", "duration", "nframes", "read_video", "read_wav", "load_any",
              "decode", "frame_index", "luma", "contrast", "ssim", "psnr", "detect_cuts", "cut_frames", "ink_bbox",
              "color_mask", "centroid", "mad", "hist", "rel_lum", "bpm", "tempo", "silence")
FILTER_FLAGS = {"-vf", "-af", "-filter_complex", "-lavfi", "-filter:v", "-filter:a"}


# ------------------------------------------------------------------ corpus
class Mod:
    def __init__(self, path: Path, corpus: str):
        self.path, self.corpus, self.stem = path, corpus, path.stem
        self.src = path.read_text(encoding="utf-8")
        self.tree = ast.parse(self.src)
        self.defs, self.consts, self.nonlit, self.imps, self.imp_nodes = {}, {}, {}, {}, {}
        for n in self.tree.body:
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                self.defs[n.name] = n
            elif isinstance(n, ast.ImportFrom):
                for a in n.names:
                    self.imps[a.asname or a.name] = ("." * n.level + (n.module or ""), a.name)
                    self.imp_nodes[a.asname or a.name] = n
            elif isinstance(n, ast.Import):
                for a in n.names:
                    self.imps[a.asname or a.name.split(".")[0]] = (a.name, None)
                    self.imp_nodes[a.asname or a.name.split(".")[0]] = n
            elif isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None:
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    if isinstance(t, (ast.Tuple, ast.List)) and all(isinstance(e, ast.Name) for e in t.elts):
                        try:
                            vals = ast.literal_eval(n.value)
                            if len(vals) == len(t.elts):
                                self.consts.update({e.id: v for e, v in zip(t.elts, vals)})
                                continue
                        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                            pass
                        for e in t.elts:
                            self.nonlit[e.id] = n
                    if isinstance(t, ast.Name):
                        try:
                            self.consts[t.id] = ast.literal_eval(n.value)
                        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                            self.nonlit[t.id] = n


def load_corpus(paths, corpus):
    return {p.stem: Mod(p, corpus) for p in paths}


def free_names(fn):
    """Loaded names of a function body that are not its own args/locals (decorators excluded)."""
    fn = as_def(fn)
    nodes = [y for st in fn.body for y in ast.walk(st)] + [y for d in fn.args.defaults + fn.args.kw_defaults if d for y in ast.walk(d)]
    local = {a.arg for a in ast.walk(fn.args) if isinstance(a, ast.arg)}
    local |= {x.id for x in nodes if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)}
    local |= {a.arg for x in nodes if isinstance(x, (ast.Lambda, ast.FunctionDef)) for a in ast.walk(x.args) if isinstance(a, ast.arg)}
    local |= {x.name for x in nodes if isinstance(x, (ast.FunctionDef, ast.ClassDef))}
    local |= {a.asname or a.name.split(".")[0] for x in nodes if isinstance(x, (ast.Import, ast.ImportFrom)) for a in x.names}
    local |= {x.name for x in nodes if isinstance(x, ast.ExceptHandler) and x.name}
    return sorted({x.id for x in nodes if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)} - local), local


def expr_frees(node):
    """Free names of an expression (lambda/comprehension variables and builtins excluded)."""
    wrap = ast.FunctionDef(name="_", args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                           body=[ast.Return(node)], decorator_list=[], returns=None, type_params=[], lineno=1, col_offset=0)
    return [n for n in free_names(wrap)[0] if n not in BUILTINS]


def asset_path(m, name, depth=0):
    """Resolve FONTS = SP / "proofs/_shared/fonts" (via HERE/REPO/SP and __file__) to an absolute Path, or None."""
    node = m.nonlit.get(name)
    if node is None or depth > 8:
        return None
    env = {"Path": Path, "__file__": str(m.path)}
    for n in {x.id for x in ast.walk(node.value) if isinstance(x, ast.Name)} - set(env):
        if n in m.consts:
            env[n] = m.consts[n]
        else:
            v = asset_path(m, n, depth + 1)
            if v is None:
                return None
            env[n] = v
    try:
        v = eval(compile(ast.Expression(node.value), "<asset>", "eval"), {"__builtins__": {}}, env)  # noqa: S307 - Path arithmetic of old constants
    except Exception:  # anything beyond Path arithmetic: not an asset
        return None
    return v if isinstance(v, Path) else None


class Hasher:
    """Canonical AST hash of a module-level name with everything it reaches (helpers, constants, imports)."""

    def __init__(self, corpus: dict):
        self.c, self.memo = corpus, {}

    def resolve(self, stem, name):
        m = self.c.get(stem)
        if m is None or name not in m.imps:
            return ("mod", stem, name)
        mod, orig = m.imps[name]
        base = mod.lstrip(".")
        if base in ("_harness", "core") and orig is not None:
            return ("harness", orig, None)
        if orig is not None and base in self.c and base != stem:
            return self.resolve(base, orig) if orig in self.c[base].imps else ("mod", base, orig)
        return ("ext", mod, orig)

    def canon(self, stem, name, stack=()):
        r = self.resolve(stem, name)
        if r[0] == "harness":
            return "H:" + r[1]
        if r[0] == "ext":
            return "X:%s:%s" % (r[1], r[2])
        _, stem, name = r
        key = (stem, name)
        if key in self.memo:
            return self.memo[key]
        if key in stack:
            return "R:" + name
        m = self.c[stem]
        if name in ASSET_PATHS and name in m.nonlit:
            out = "A:" + name
        elif name in m.consts:
            out = "C:" + repr(m.consts[name])
        elif name in m.nonlit:
            node = m.nonlit[name].value
            out = "N:" + ast.dump(node) + "".join(
                "|%s=%s" % (n, self.canon(stem, n, stack + (key,))) for n in sorted(expr_frees(node)))
        elif name in m.defs:
            d = copy.deepcopy(m.defs[name])
            d.decorator_list = []
            d.name = ""
            if d.body and isinstance(d.body[0], ast.Expr) and isinstance(d.body[0].value, ast.Constant) and isinstance(d.body[0].value.value, str):
                d.body = d.body[1:] or [ast.Pass()]
            frees, _ = free_names(m.defs[name]) if isinstance(m.defs[name], ast.FunctionDef) else (
                sorted({x.id for x in ast.walk(m.defs[name]) if isinstance(x, ast.Name)}), set())
            out = "D:" + ast.dump(d) + "".join(
                "|%s=%s" % (n, self.canon(stem, n, stack + (key,))) for n in frees if n not in BUILTINS)
        else:
            out = "U:" + name
        self.memo[key] = out
        return out

    def digest(self, stem, name):
        return hashlib.sha1(self.canon(stem, name).encode("utf-8")).hexdigest()[:16]


def importable(module: str) -> bool:
    """A third-party/stdlib module the packs may import: it must be findable here (not via the old sys.path)."""
    top = module.lstrip(".").split(".")[0]
    try:
        return bool(top) and importlib.util.find_spec(top) is not None
    except (ImportError, ValueError):
        return False


# ------------------------------------------------------------------ helper closure (what a pack must contain)
def closure(old: dict, hasher: Hasher, stem, name, acc: dict) -> bool:
    """Collect (module, name) needed for ``name``; False if it reaches repo paths, scripts, node or a browser."""
    r = hasher.resolve(stem, name)
    if r[0] == "harness":
        return r[1] in HARNESS
    if r[0] == "ext":
        return importable(r[1])
    _, stem, name = r
    key = (stem, name)
    if name in ASSET_PATHS and asset_path(old[stem], name) is not None:
        acc[key] = "asset"
        return True
    if name.startswith("__") or name in EXTERNAL_FN or name in REPO_PATHS:
        return False
    if key in acc:
        return acc[key] is not None
    m = old[stem]
    acc[key] = "pending"
    ok = True
    if name in m.consts:
        pass
    elif name in m.nonlit:
        for n in expr_frees(m.nonlit[name].value):
            ok &= closure(old, hasher, stem, n, acc)
    elif name in m.defs:
        node = m.defs[name]
        frees = free_names(node)[0] if isinstance(node, ast.FunctionDef) else sorted(
            {x.id for x in ast.walk(node) if isinstance(x, ast.Name)})
        for n in frees:
            if n not in BUILTINS:
                ok &= closure(old, hasher, stem, n, acc)
    else:
        ok = name in m.imps
    acc[key] = "ok" if ok else None
    return ok


def write_packs(old: dict, hasher: Hasher, needs: dict):
    """engines/cards/lib/<module>.py: the needed helpers copied verbatim, imports rewritten to the lib layout."""
    LIB.mkdir(parents=True, exist_ok=True)
    for stem, names in sorted(needs.items()):
        m = old[stem]
        def targets(n):
            ts = n.targets if isinstance(n, ast.Assign) else [n.target]
            return [x.id for t in ts for x in ([t] if isinstance(t, ast.Name) else getattr(t, "elts", [])) if isinstance(x, ast.Name)]
        assets = {n: asset_path(m, n) for n in names & ASSET_PATHS if asset_path(m, n) is not None}
        keep = [n for n in m.tree.body if (
            isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names) or (
            isinstance(n, (ast.Assign, ast.AnnAssign)) and set(targets(n)) & (names - set(assets)))]
        used = set()
        for n in keep:
            used |= {x.id for x in ast.walk(n) if isinstance(x, ast.Name)}
        imports, seen = [], set()
        for nm in sorted(used & set(m.imps)):
            mod, orig = m.imps[nm]
            base = mod.lstrip(".")
            alias = "" if (orig or mod.split(".")[0]) == nm else " as " + nm
            if base == "_harness":
                line = "from .core import %s%s" % (orig, alias)
            elif orig is not None and base in old:
                line = "from .%s import %s%s" % (base, orig, alias)
            elif orig is None:
                line = "import %s%s" % (mod, "" if mod == nm else " as " + nm)
            else:
                line = "from %s import %s%s" % (mod, orig, alias)
            if line not in seen:
                seen.add(line)
                imports.append(line)
        body = "\n\n\n".join(ast.get_source_segment(m.src, n) for n in keep)
        if assets:
            if "from pathlib import Path" not in seen:
                imports.append("from pathlib import Path")
            body = "\n".join("%s = Path(%r)  # read-only asset in the old repo" % (k, str(v))
                             for k, v in sorted(assets.items())) + "\n\n\n" + body
        head =('"""Helpers of %s/%s used by data cards, copied verbatim (the extractor binds a card to them only when\n'
                'their AST hash with every dependency equals the original\'s)."""\n'
                'from __future__ import annotations\n\n' % (m.corpus, m.path.name))
        (LIB / (stem + ".py")).write_text(head + "\n".join(imports) + "\n\n\n" + body + "\n", encoding="utf-8")
    init = LIB / "__init__.py"
    init.write_text('"""Helper packs for data cards (written by tools/extract_cards.py --write-lib)."""\n', encoding="utf-8")


# ------------------------------------------------------------------ card discovery
def static_str(node, consts):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        pass
    if isinstance(node, ast.Name) and isinstance(consts.get(node.id), str):
        return consts[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = static_str(node.left, consts), static_str(node.right, consts)
        if isinstance(a, str) and isinstance(b, str):
            return a + b
    return None


class Unresolved(Exception):
    pass


Ref = collections.namedtuple("Ref", "stem name")      # a module-level helper passed as a value (bound by hash)
UNRESOLVED = object()                                 # a factory local the static registrar could not evaluate
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg,
        ast.UAdd: operator.pos, ast.Not: operator.not_, ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
        ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge, ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b, ast.Is: operator.is_, ast.IsNot: operator.is_not}
_SEVAL_BUILTINS = {k: getattr(builtins, k) for k in ("range", "list", "tuple", "len", "str", "int", "float", "round", "zip",
                                                     "enumerate", "sorted", "dict", "set", "min", "max", "abs", "sum",
                                                     "reversed", "bool")}
_STR_METHODS = {"join", "format", "replace", "lower", "upper", "strip", "split", "title"}
_SKIP = (Unresolved, TypeError, KeyError, IndexError, ValueError, AttributeError, ZeroDivisionError, RecursionError)


def is_card_call(node) -> bool:
    return isinstance(node, ast.Call) and getattr(node.func, "id", "") == "card" and len(node.args) == 1


class Registrar:
    """Statically replays a runner module's registrations: @card(...) defs, factories called with literal arguments
    (directly or from loops over literal tables), card(id)(fn) / card(id)(lambda ...) inside factories."""

    def __init__(self, m):
        self.m, self.out, self.gaps, self.depth = m, [], {}, 0

    def seval(self, node, env):
        m = self.m
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id in m.consts:
                return m.consts[node.id]
            if node.id in m.defs:
                return Ref(m.stem, node.id)
            raise Unresolved(node.id)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            vals = [self.seval(e, env) for e in node.elts]
            return {ast.List: list, ast.Tuple: tuple, ast.Set: set}[type(node)](vals)
        if isinstance(node, ast.Dict) and None not in node.keys:
            return {self.seval(k, env): self.seval(v, env) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](self.seval(node.left, env), self.seval(node.right, env))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](self.seval(node.operand, env))
        if isinstance(node, ast.BoolOp):
            vals = [self.seval(v, env) for v in node.values]
            return all(vals) if isinstance(node.op, ast.And) else any(vals)
        if isinstance(node, ast.Compare) and all(type(o) in _OPS for o in node.ops):
            left = self.seval(node.left, env)
            for o, c in zip(node.ops, node.comparators):
                right = self.seval(c, env)
                if not _OPS[type(o)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return self.seval(node.body if self.seval(node.test, env) else node.orelse, env)
        if isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                if isinstance(v, ast.FormattedValue):
                    x = self.seval(v.value, env)
                    x = {115: str, 114: repr, 97: ascii}.get(v.conversion, lambda y: y)(x)
                    parts.append(format(x, self.seval(v.format_spec, env) if v.format_spec else ""))
                else:
                    parts.append(v.value)
            return "".join(parts)
        if isinstance(node, ast.Subscript):
            sl = node.slice
            key = slice(*(self.seval(x, env) if x else None for x in (sl.lower, sl.upper, sl.step))) \
                if isinstance(sl, ast.Slice) else self.seval(sl, env)
            return self.seval(node.value, env)[key]
        if isinstance(node, ast.Call) and not any(isinstance(a, ast.Starred) for a in node.args):
            f = node.func
            args = [self.seval(a, env) for a in node.args]
            kw = {k.arg: self.seval(k.value, env) for k in node.keywords if k.arg}
            if isinstance(f, ast.Name) and f.id in _SEVAL_BUILTINS and f.id not in env:
                return _SEVAL_BUILTINS[f.id](*args, **kw)
            if isinstance(f, ast.Name) and isinstance(m.defs.get(f.id), ast.FunctionDef) and self.depth < 4:
                return self.simple_call(m.defs[f.id], args, kw)
            if isinstance(f, ast.Attribute) and f.attr in _STR_METHODS:
                base = self.seval(f.value, env)
                if isinstance(base, str):
                    return getattr(base, f.attr)(*args, **kw)
        raise Unresolved(type(node).__name__)

    def simple_call(self, fdef, args, kw):
        """A helper like KA(s): return PREFIX + s (single return over its parameters and constants)."""
        body = fdef.body[1:] if ast.get_docstring(fdef) is not None else fdef.body
        if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
            raise Unresolved(fdef.name)
        env = self.bind(fdef, args, kw, {})
        self.depth += 1
        try:
            return self.seval(body[0].value, env)
        finally:
            self.depth -= 1

    def bind(self, fdef, args, kw, denv):
        params = fdef.args.args
        env = dict(zip((p.arg for p in params), args))
        env.update(kw)
        for p, d in zip(params[len(params) - len(fdef.args.defaults):], fdef.args.defaults):
            if p.arg not in env:
                env[p.arg] = self.seval(d, denv)
        return env

    def add(self, cid, fn, env, how):
        if isinstance(cid, str) and fn is not None:
            self.out.append((cid, fn, how, dict(env)))

    def run_block(self, stmts, env, local, top=True):
        m = self.m
        for n in stmts:
            try:
                if isinstance(n, ast.FunctionDef):
                    for d in n.decorator_list:
                        if is_card_call(d):
                            self.add(self.seval(d.args[0], env), n, env, "decorator" if top else "loop")
                    if not top:
                        local[n.name] = (n, dict(env))
                elif isinstance(n, ast.For):
                    for it in list(self.seval(n.iter, env)):
                        e2 = dict(env)
                        self.assign(n.target, it, e2)
                        self.run_block(n.body, e2, dict(local), top=False)
                elif isinstance(n, ast.If) and not top:
                    self.run_block(n.body if self.seval(n.test, env) else n.orelse, env, local, top=False)
                elif isinstance(n, ast.Assign) and not top and len(n.targets) == 1 and not isinstance(n.targets[0], ast.Subscript):
                    self.assign(n.targets[0], self.seval(n.value, env), env)
                elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
                    c = n.value
                    if is_card_call(c.func) and len(c.args) == 1:
                        self.add(self.seval(c.func.args[0], env), self.target(c.args[0], local), env, "call")
                    elif isinstance(c.func, ast.Name):
                        name = c.func.id
                        if name == "_gap" and len(c.args) > 1:
                            self.gaps[self.seval(c.args[0], env)] = str(self.seval(c.args[1], env))[:300]
                            continue
                        fdef, denv = local.get(name, (m.defs.get(name), {}))
                        if isinstance(fdef, ast.FunctionDef) and any(
                                is_card_call(x) or (isinstance(x, ast.Call) and is_card_call(x.func)) for x in ast.walk(fdef)):
                            args = [self.seval(a, env) for a in c.args]
                            kw = {k.arg: self.seval(k.value, env) for k in c.keywords}
                            self.visit_factory(fdef, self.bind(fdef, args, kw, denv))
                    elif ast.unparse(c.func) == "GAPS.update" and c.args:
                        self.gaps.update({k: str(v)[:300] for k, v in self.seval(c.args[0], env).items()})
                elif isinstance(n, (ast.Assign, ast.AnnAssign)):
                    t = n.targets[0] if isinstance(n, ast.Assign) else n.target
                    if getattr(t, "id", "") == "GAPS" and n.value is not None:
                        self.gaps.update({k: str(v)[:300] for k, v in self.seval(n.value, env).items()})
                    elif isinstance(t, ast.Subscript) and getattr(t.value, "id", "") == "GAPS":
                        self.gaps[self.seval(t.slice, env)] = str(self.seval(n.value, env))[:300]
            except _SKIP:
                continue

    def target(self, node, local):
        if isinstance(node, ast.Lambda):
            return node
        if isinstance(node, ast.Name):
            got = local.get(node.id)
            return got[0] if isinstance(got, tuple) else got
        return None

    def assign(self, target, value, env):
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            vals = list(value)
            if len(vals) != len(target.elts):
                raise Unresolved("unpack")
            for t, v in zip(target.elts, vals):
                self.assign(t, v, env)
        else:
            raise Unresolved("target")

    def visit_factory(self, fdef, env):
        env, local = dict(env), {}
        for st in fdef.body:
            try:
                if isinstance(st, ast.FunctionDef):
                    local[st.name] = st
                    for d in st.decorator_list:
                        if is_card_call(d):
                            self.add(self.seval(d.args[0], env), st, env, "template")
                elif isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) and is_card_call(st.value.func) \
                        and len(st.value.args) == 1:
                    self.add(self.seval(st.value.func.args[0], env), self.target(st.value.args[0], local), env, "template")
                elif isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                    try:
                        env[st.targets[0].id] = self.seval(st.value, env)
                    except _SKIP:
                        env[st.targets[0].id] = UNRESOLVED
            except _SKIP:
                continue


def discover_runner(m):
    r = Registrar(m)
    r.run_block(m.tree.body, {}, {})
    return r.out, r.gaps


def discover_programs(m: Mod):
    out = []

    def from_dict(d):
        for k, v in zip(d.keys, d.values):
            cid = static_str(k, m.consts) if k is not None else None
            if cid and isinstance(v, ast.Name) and v.id in m.defs:
                out.append((cid, m.defs[v.id], "programs", None))

    for n in m.tree.body:
        if isinstance(n, (ast.Assign, ast.AnnAssign)) and getattr(n.targets[0] if isinstance(n, ast.Assign) else n.target, "id", "") == "PROGRAMS":
            if isinstance(n.value, ast.Dict):
                from_dict(n.value)
            elif isinstance(n.value, ast.DictComp):
                out.extend(dictcomp_programs(m, n.value))
        elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and ast.unparse(n.value.func) == "PROGRAMS.update" \
                and n.value.args and isinstance(n.value.args[0], ast.Dict):
            from_dict(n.value.args[0])
        elif isinstance(n, ast.FunctionDef):
            for d in n.decorator_list:
                if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "card" and d.args:
                    cid = static_str(d.args[0], m.consts)
                    if cid:
                        out.append((cid, n, "programs", None))
    return out


def dictcomp_programs(m: Mod, dc: ast.DictComp):
    """{f"X-{n:02d}": globals()[f"x_{n:02d}"] for n in range(a, b) if <cond>} evaluated statically."""
    gen = dc.generators[0]
    if not (isinstance(gen.target, ast.Name) and isinstance(gen.iter, ast.Call) and getattr(gen.iter.func, "id", "") == "range"):
        return []
    var = gen.target.id
    rng = range(*[ast.literal_eval(a) for a in gen.iter.args])
    fname_node = dc.value.slice if isinstance(dc.value, ast.Subscript) else None
    out = []
    for i in rng:
        env = {var: i}

        def ev(node):
            return eval(compile(ast.Expression(node), "<comp>", "eval"), {"__builtins__": {}}, env)  # noqa: S307 - f-strings/ints only
        try:
            key = ev(dc.key)
            fname = ev(fname_node) if fname_node is not None else None
            ok = True
            for cond in gen.ifs:
                if isinstance(cond, ast.Compare) and isinstance(cond.comparators[0], ast.Call) and ast.unparse(cond.comparators[0]) == "globals()":
                    ok &= ev(cond.left) in m.defs
                else:
                    ok &= bool(ev(cond))
        except Exception:  # anything beyond f-strings over the loop int: leave it to the inventory reconciliation
            return []
        if ok and fname in m.defs:
            out.append((key, m.defs[fname], "programs", None))
    return out


# ------------------------------------------------------------------ per-card metadata
def short(node, n=160):
    s = ast.unparse(node)
    return s if len(s) <= n else s[:n - 1] + "…"


def literal_or_text(node):
    try:
        if all(isinstance(x, (ast.Constant, ast.BinOp, ast.UnaryOp, ast.operator, ast.unaryop)) for x in ast.walk(node)):
            v = eval(compile(ast.Expression(node), "<const>", "eval"), {"__builtins__": {}})  # noqa: S307 - numbers only
        else:
            v = ast.literal_eval(node)
        json.dumps(v)
        return v if len(repr(v)) <= 200 else short(node, 80)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return short(node, 80)


def structure(cond):
    """abs(M - K) <= T / M <= K / near(M, K, T) -> {measure, cmp, target, tol}."""
    if isinstance(cond, ast.Call) and getattr(cond.func, "id", "") == "near" and len(cond.args) == 3:
        return {"measure": short(cond.args[0], 100), "cmp": "abs<=", "target": literal_or_text(cond.args[1]),
                "tol": literal_or_text(cond.args[2])}
    if not (isinstance(cond, ast.Compare) and len(cond.ops) == 1):
        return None
    left, op, right = cond.left, type(cond.ops[0]).__name__, cond.comparators[0]
    ops = {"LtE": "<=", "Lt": "<", "GtE": ">=", "Gt": ">", "Eq": "==", "NotEq": "!="}
    if op not in ops:
        return None
    if isinstance(left, ast.Call) and getattr(left.func, "id", "") == "abs" and len(left.args) == 1 \
            and isinstance(left.args[0], ast.BinOp) and isinstance(left.args[0].op, (ast.Sub, ast.Add)) and op in ("LtE", "Lt"):
        b = left.args[0]
        t = literal_or_text(b.right)
        if isinstance(b.op, ast.Add) and isinstance(t, (int, float)):
            t = -t
        return {"measure": short(b.left, 100), "cmp": "abs" + ops[op], "target": t, "tol": literal_or_text(right)}
    return {"measure": short(left, 100), "cmp": ops[op], "target": literal_or_text(right)}


def checks_of(fn):
    rows = []
    for x in ast.walk(fn):
        if isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id in CHECK_FNS and x.args:
            a = x.args
            name = literal_or_text(a[0]) if x.func.id != "eq" or len(a) else None
            row = {"name": str(name)[:160]}
            if x.func.id == "eq" and len(a) >= 3:
                row["structured"] = {"measure": short(a[1], 100), "cmp": "==" if len(a) < 4 else "abs<=",
                                     "target": literal_or_text(a[2]), **({"tol": literal_or_text(a[3])} if len(a) > 3 else {})}
            elif len(a) >= 2:
                st = structure(a[1])
                if st:
                    row["structured"] = st
            if x.func.id == "check" and len(a) >= 4:
                row["expected"] = literal_or_text(a[3])
            rows.append(row)
        elif isinstance(x, ast.Tuple) and len(x.elts) == 3 and isinstance(x.elts[0], ast.Constant) and isinstance(x.elts[0].value, str) \
                and len(x.elts[0].value) > 6 and " " in x.elts[0].value:
            row = {"name": x.elts[0].value[:160]}
            st = structure(x.elts[1])
            if st:
                row["structured"] = st
            rows.append(row)
    for r in rows:
        if r["name"].lower().startswith(("negative control", "negative:", "neg:")) or "negative control" in r["name"].lower():
            r["negative"] = True
    return rows


def metadata(fn, m: Mod):
    calls, filters, sources = set(), [], []
    for x in ast.walk(fn):
        if isinstance(x, ast.Call):
            f = x.func
            if isinstance(f, (ast.Name, ast.Attribute)):
                calls.add(ast.unparse(f))
            args = x.args
            for i in range(1, len(args)):
                prev = args[i - 1]
                if isinstance(prev, ast.Constant) and prev.value in FILTER_FLAGS:
                    v = args[i]
                    if isinstance(v, ast.BinOp) and isinstance(v.op, ast.Mod):
                        v = v.left
                    if isinstance(v, ast.Constant) and isinstance(v.value, str):
                        filters.append(v.value[:300])
                    elif isinstance(v, ast.JoinedStr):
                        filters.append(short(v, 300))
                if isinstance(prev, ast.Constant) and prev.value == "-i" and i >= 3 and isinstance(args[i - 2], ast.Constant) \
                        and args[i - 2].value == "lavfi" and isinstance(args[i], (ast.Constant, ast.JoinedStr, ast.BinOp)):
                    v = args[i].left if isinstance(args[i], ast.BinOp) else args[i]
                    sources.append(v.value if isinstance(v, ast.Constant) else short(v, 120))
    names = {c.split(".")[-1] for c in calls}
    fixtures = sorted({"lavfi:" + str(s).split("=")[0] for s in sources} | {n for n in names if any(w in n.lower() for w in FIX_WORDS)})
    measures = sorted({n for n in names if any(w in n.lower() for w in MEAS_WORDS)})
    src = ast.unparse(fn)
    engines = set()
    if filters or sources or any(k in src for k in ("ffmpeg", "ffprobe", "ff(", "fx.frames", "fx.probe", "ebur")):
        engines.add("ffmpeg")
    if names & {"node", "node_js", "mk"} or "'node'" in src:
        engines.add("node")
    if names & {"browser", "page"} or "playwright" in src or "chromium" in src:
        engines.add("browser")
    if names & {"sh", "py", "vmod", "hf", "hf_render", "score_mod", "score_render"} or any(p in src for p in ("VEND", "KM /", "PVE", "SCR")):
        engines.add("repo-script")
    for lib in ("cv2", "PIL", "Image", "yaml", "librosa", "torch", "ortools", "pulp", "duckdb", "polars"):
        if lib + "." in src or lib + "(" in src:
            engines.add({"Image": "PIL"}.get(lib, lib))
    return {"fixtures": fixtures[:12], "filters": filters[:8], "measures": measures[:12], "engines": sorted(engines)}


# ------------------------------------------------------------------ portability
def as_def(fn):
    if isinstance(fn, ast.Lambda):
        return ast.FunctionDef(name="card", args=fn.args, body=[ast.Return(fn.body)], decorator_list=[], returns=None,
                               type_params=[], lineno=fn.lineno, col_offset=0, end_lineno=fn.end_lineno)
    return fn


def literal_value(v) -> bool:
    try:
        return ast.literal_eval(repr(v)) == v
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return False


class _StripImports(ast.NodeTransformer):
    """In-body imports become the program's ``imports`` map (whitelisted modules only)."""

    def __init__(self, allowed):
        self.allowed, self.imports, self.bad = allowed, {}, []

    def _imp(self, node):
        for a in node.names:
            if isinstance(node, ast.Import):
                mod, local = a.name, a.asname or a.name.split(".")[0]
                spec = mod if a.asname else mod.split(".")[0]
            else:
                mod, local = "." * node.level + (node.module or ""), a.asname or a.name
                spec = "%s:%s" % (mod, a.name)
            if mod.startswith(".") or not self.allowed(mod):
                self.bad.append(mod)
            self.imports[local] = spec
        return ast.Pass()
    visit_Import = visit_ImportFrom = _imp


def program_of(fn, m, old_h, lib_ok, cenv=None):
    """(program, None) when the card is data; (None, reason) otherwise. lib_ok=None is collect mode: bind every
    helper whose closure is self-contained, so --write-lib knows what the packs must hold."""
    from engines.cards.formula import FormulaError, PROGRAMS_ALLOWED, SAFE_BUILTINS, allowed_module, check_tree
    cenv = cenv or {}
    d = copy.deepcopy(as_def(fn))
    d.name, d.decorator_list = "card", []
    if ast.get_docstring(d) is not None:
        d.body = d.body[1:] or [ast.Pass()]
    pos, dflt = d.args.args, d.args.defaults
    n_main = len(pos) - len(dflt)
    extra = {}
    for a, dv in zip(pos[n_main:], dflt):
        try:
            extra[a.arg] = Registrar(m).seval(dv, cenv)
        except _SKIP:
            return None, "closure: a default argument is not static"
    if d.args.vararg or d.args.kwarg or d.args.kwonlyargs or d.args.posonlyargs:
        return None, "closure: unusual signature"
    d.args = ast.arguments(posonlyargs=[], args=pos[:n_main], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[])
    for x in ast.walk(d):  # annotations are evaluated at def time but carry no behaviour: drop them
        if isinstance(x, ast.arg):
            x.annotation = None
        elif isinstance(x, ast.FunctionDef):
            x.returns = None
    strip = _StripImports(allowed_module)
    d = strip.visit(d)
    imports = strip.imports
    if strip.bad:
        return None, "imports a module outside the whitelist: " + ", ".join(sorted(set(strip.bad))[:4])
    try:
        check_tree(ast.Module([d], []))
    except FormulaError as e:
        return None, "bespoke code: " + str(e).replace("not allowed in a data card: ", "")
    for x in ast.walk(d):
        if isinstance(x, ast.Call) and ast.unparse(x.func) in ("subprocess.run", "subprocess.Popen", "subprocess.check_output",
                                                              "subprocess.check_call") and x.args \
                and isinstance(x.args[0], (ast.List, ast.Tuple)) and x.args[0].elts:
            first = x.args[0].elts[0]
            prog = first.value if isinstance(first, ast.Constant) else None
            if prog is None or Path(str(prog)).stem.lower() not in PROGRAMS_ALLOWED:
                return None, "runs a program other than ffmpeg/ffprobe/node: " + (str(prog) if prog else ast.unparse(first))[:60]
    bind, consts, missing = {}, {}, []
    for n in free_names(d)[0]:
        if n in extra or n in cenv:
            v = extra[n] if n in extra else cenv[n]
            if isinstance(v, Ref):
                n_stem, n_name = v
            elif v is UNRESOLVED or not literal_value(v):
                return None, "closure: factory value %s is not a literal" % n
            else:
                consts[n] = repr(v)
                continue
        elif n in imports:
            continue
        elif n in BUILTINS and n not in m.defs and n not in m.consts and n not in m.imps:
            if n not in SAFE_BUILTINS or n.startswith("__"):
                return None, "uses builtin %s" % n
            continue
        else:
            r = old_h.resolve(m.stem, n)
            if r[0] == "harness":
                if r[1] in HARNESS:
                    bind[n] = "core." + r[1]
                    continue
                return None, "uses harness %s" % r[1]
            if r[0] == "ext":
                if r[1].startswith(".") or not allowed_module(r[1]):
                    return None, "uses a module outside the whitelist: %s (%s)" % (n, r[1])
                imports[n] = r[1] if r[2] is None else "%s:%s" % (r[1], r[2])
                continue
            _, n_stem, n_name = r
        if n_name in EXTERNAL_FN or n_name in REPO_PATHS:
            return None, "calls a repo script, node or a browser: " + n_name
        mm = old_h.c[n_stem]
        if n_name in mm.consts and n_stem == m.stem and literal_value(mm.consts[n_name]):
            consts[n] = repr(mm.consts[n_name])
        elif lib_ok is None:
            if closure(old_h.c, old_h, n_stem, n_name, {}):
                bind[n] = "%s.%s" % (n_stem, n_name)
            else:
                missing.append(n)
        elif lib_ok.get((n_stem, n_name)) == old_h.digest(n_stem, n_name):
            bind[n] = "%s.%s" % (n_stem, n_name)
        else:
            missing.append(n)
    if missing:
        return None, "needs helper(s) that reach repo paths/scripts/browsers: " + ", ".join(missing[:6])
    prog = {"args": [a.arg for a in d.args.args], "def": ast.unparse(d)}
    for k, v in (("consts", consts), ("bind", bind), ("imports", imports)):
        if v:
            prog[k] = v
    return prog, None


# ------------------------------------------------------------------ main
def powers_index():
    idx = {}
    for f in sorted(POWERS.glob("*.json")):
        for c in json.loads(f.read_text(encoding="utf-8")):
            idx[c["id"]] = c
    return idx


def family_of(cid, mod, pidx):
    if cid in pidx:
        return pidx[cid]["family"]
    if ":" in cid:
        return cid.split(":", 1)[0] + "s"
    s = mod.removeprefix("fam_")
    for suf in ("_a", "_b"):
        s = s.removesuffix(suf)
    s = s.split("__")[0]
    if s.startswith("skills_part"):
        s = "skills"
    return s.replace("_", "-")


def build_records(old, old_h, pidx, found, lib_ok):
    from engines.cards.custom import CUSTOM
    records = {}
    for cid, fn, how, cenv, m in found:
        if cid in records:
            continue
        corpus = "runner" if m.corpus == "runners" else "program"
        pc = pidx.get(cid, {})
        dfn = as_def(fn)
        doc = (ast.get_docstring(dfn) or "").strip().split("\n")[0] if isinstance(fn, ast.FunctionDef) else ""
        rec = {"id": cid, "family": family_of(cid, m.stem, pidx),
               "title": (pc.get("name_en") or doc or getattr(fn, "name", cid))[:200],
               "source": {"corpus": corpus, "module": m.path.name, "function": getattr(fn, "name", "<lambda>"),
                          "lines": fn.end_lineno - fn.lineno + 1, "registered_by": how}}
        lit = {k: repr(v) for k, v in cenv.items() if literal_value(v) and len(repr(v)) < 300}
        if lit:
            rec["source"]["params"] = lit
        rec.update(metadata(dfn, m))
        rec["checks"] = checks_of(dfn)
        rec["negative_control"] = [c["name"] for c in rec["checks"] if c.get("negative")]
        prog, why = program_of(fn, m, old_h, lib_ok, cenv)
        if prog:
            rec["status"], rec["program"] = "data", prog
        elif cid in CUSTOM:
            rec["status"], rec["reason"] = "custom", "hand port in engines/cards/custom.py (" + why + ")"
        else:
            rec["status"], rec["reason"] = "not_ported", why
        records[cid] = rec
    return records


def load_lib_ok(old, old_h):
    lib = load_corpus(sorted(p for p in LIB.glob("*.py") if p.name != "__init__.py"), "lib") if LIB.exists() else {}
    lib_h = Hasher(lib)
    ok = {(s, n): lib_h.digest(s, n) for s, m in lib.items() for n in list(m.defs) + list(m.consts) + list(m.nonlit)}
    return {k: h for k, h in ok.items() if k[0] in old and old_h.digest(*k) == h}  # a pack copy must hash as the original


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-lib", action="store_true")
    a = ap.parse_args(argv)
    old = load_corpus(sorted(RUNNERS.glob("*.py")), "runners")
    old.update(load_corpus(sorted(p for p in PROGRAMS.glob("*.py") if p.name != "__init__.py"), "power_programs"))
    old_h = Hasher(old)
    pidx = powers_index()

    found, gaps = [], {}
    for stem, m in old.items():
        if m.corpus == "runners" and stem.startswith("fam_"):
            cards, g = discover_runner(m)
            gaps.update(g)
        elif m.corpus == "power_programs" and not stem.startswith("_"):
            cards = [(cid, fn, how, {}) for cid, fn, how, _ in discover_programs(m)]
        else:
            continue
        found += [(cid, fn, how, cenv, m) for cid, fn, how, cenv in cards]

    if a.write_lib:
        # collect every helper a portable card binds (with its dependencies), then write the packs verbatim
        records = build_records(old, old_h, pidx, found, None)
        from engines.cards.custom import NEEDS
        needs = collections.defaultdict(set)
        refs = list(NEEDS) + [tuple(ref.rsplit(".", 1)) for r in records.values() if r["status"] == "data"
                              for ref in r["program"].get("bind", {}).values() if not ref.startswith("core.")]
        for st, nm in refs:
            acc = {}
            closure(old, old_h, st, nm, acc)
            for (s2, n2), v in acc.items():
                if v:
                    needs[s2].add(n2)
        for f in LIB.glob("*.py"):
            if f.name not in ("__init__.py", "core.py"):
                f.unlink()
        write_packs(old, old_h, needs)
        print("packs written:", len(needs), "modules,", sum(map(len, needs.values())), "helpers")

    records = build_records(old, old_h, pidx, found, load_lib_ok(old, old_h))
    # reconcile with the old build's inventory: registered ids the AST could not resolve, and gaps
    inv = set()
    if ADAPTERS.exists():
        inv |= {k.split(":", 1)[1] if k.startswith("power:") else k
                for k in json.loads(ADAPTERS.read_text(encoding="utf-8"))["adapters"]}
    if BUILD_REPORT.exists():
        rep = json.loads(BUILD_REPORT.read_text(encoding="utf-8"))
        inv |= {r["id"] for r in rep.get("failed", [])}
        gaps.update(rep.get("gaps", {}))
    for cid in sorted(inv - set(records)):
        records[cid] = {"id": cid, "family": family_of(cid, "", pidx), "title": pidx.get(cid, {}).get("name_en", cid),
                        "source": {"corpus": "runner", "module": None, "function": None, "registered_by": "dynamic"},
                        "status": "not_ported", "reason": "registered dynamically by the old runner; not statically resolvable"}
    for cid, why in sorted(gaps.items()):
        if cid not in records:
            records[cid] = {"id": cid, "family": family_of(cid, "", pidx), "title": pidx.get(cid, {}).get("name_en", cid),
                            "source": {"corpus": "runner", "module": None, "function": None, "registered_by": "gap"},
                            "status": "gap", "reason": str(why)[:300]}

    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.json"):
        if not f.name.startswith("_parity"):
            f.unlink()
    by_fam = collections.defaultdict(list)
    for r in records.values():
        by_fam[r["family"]].append(r)
    for fam, rows in by_fam.items():
        rows.sort(key=lambda r: r["id"])
        text = "[\n" + ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows) + "\n]\n"
        (OUT / ("%s.json" % fam.replace(":", "_").replace("/", "_"))).write_text(text, encoding="utf-8")
    idx = stats(records)
    (OUT / "_index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: idx[k] for k in ("cards", "status", "runnable_coverage")}, ensure_ascii=False, indent=1))
    return 0


def stats(records):
    rs = list(records.values())
    st = collections.Counter(r["status"] for r in rs)
    reasons = collections.Counter((r.get("reason") or "").split(":")[0] for r in rs if r["status"] == "not_ported")
    runnable = [r for r in rs if r["status"] != "gap"]
    cnt = lambda key: collections.Counter(x for r in rs for x in r.get(key, []))  # noqa: E731
    return {"cards": len(rs), "status": dict(st),
            "runnable_coverage": {"runnable_cards": len(runnable),
                                  "data_pct": round(100 * st["data"] / max(1, len(runnable)), 1),
                                  "custom_pct": round(100 * st["custom"] / max(1, len(runnable)), 1),
                                  "not_ported_pct": round(100 * st["not_ported"] / max(1, len(runnable)), 1)},
            "by_corpus": dict(collections.Counter(r["source"]["corpus"] for r in rs)),
            "not_ported_reasons": dict(reasons.most_common()),
            "families": {f: dict(collections.Counter(r["status"] for r in rs if r["family"] == f))
                         for f in sorted({r["family"] for r in rs})},
            "distribution": {"fixtures": dict(cnt("fixtures").most_common(40)),
                             "measures": dict(cnt("measures").most_common(40)),
                             "engines": dict(cnt("engines").most_common()),
                             "filters": dict(collections.Counter(
                                 f.split("=")[0].split("[")[-1].split("]")[-1] for r in rs for g in r.get("filters", [])
                                 for f in g.replace(";", ",").split(",") if "=" in f).most_common(40)),
                             "checks_per_card": round(sum(len(r.get("checks", [])) for r in rs) / max(1, len(rs)), 2),
                             "cards_with_negative_control": sum(1 for r in rs if r.get("negative_control"))}}


if __name__ == "__main__":
    sys.exit(main())
