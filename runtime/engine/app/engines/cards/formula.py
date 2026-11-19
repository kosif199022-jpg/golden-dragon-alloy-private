"""Formula language of a data card: one whitelisted ``def card(...)`` stored as program text in data/cards/*.json.

Allowed: assignments (with unpacking), expressions, comprehensions, if/else, for/while (every loop body ticks an
iteration counter: at most MAX_ITER iterations and MAX_SECONDS per card), try/except/raise/assert, ``with``, local
def/lambda, return/yield. Refused anywhere in the tree: import, class, global, async, attributes starting with ``_``,
names starting with ``__``, and the builtins exec/eval/open/compile/globals/locals/vars/getattr/setattr/delattr/type/
input/breakpoint. Modules reach a card only through its ``imports`` map, checked against ALLOWED_MODULES;
``subprocess`` is a shim that runs ffmpeg, ffprobe and node only.
"""
import ast
import builtins
import importlib
import shutil
import subprocess as _subprocess
import time
from pathlib import Path

MAX_ITER, MAX_SECONDS = 50_000_000, 900
NODES = (ast.Module, ast.Expression, ast.FunctionDef, ast.Lambda, ast.arguments, ast.arg, ast.Return, ast.Assign,
         ast.AugAssign, ast.AnnAssign, ast.Expr, ast.For, ast.While, ast.If, ast.Break, ast.Continue, ast.Pass, ast.Try,
         ast.ExceptHandler, ast.Raise, ast.Assert, ast.With, ast.withitem, ast.Nonlocal, ast.Delete, ast.NamedExpr,
         ast.Yield, ast.YieldFrom, ast.Constant, ast.Name, ast.Load, ast.Store, ast.Del, ast.List, ast.Tuple, ast.Set,
         ast.Dict, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp, ast.Call, ast.keyword, ast.Attribute,
         ast.Subscript, ast.Slice, ast.Starred, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
         ast.comprehension, ast.JoinedStr, ast.FormattedValue, ast.operator, ast.unaryop, ast.boolop, ast.cmpop,
         ast.expr_context)
FORBIDDEN = {"exec", "eval", "open", "compile", "globals", "locals", "vars", "getattr", "setattr", "delattr", "type",
             "input", "breakpoint", "exit", "quit", "help", "memoryview", "object", "super", "classmethod",
             "staticmethod", "property", "__import__", "__builtins__"}
DENY_ATTR = {"system", "popen", "rmtree", "chmod", "symlink_to", "hardlink_to", "tofile", "fromfile", "memmap", "ctypeslib"}
SAFE_BUILTINS = {k: getattr(builtins, k) for k in dir(builtins)
                 if not k.startswith("_") and k not in FORBIDDEN and k not in ("copyright", "credits", "license")}
SAFE_BUILTINS["__import__"] = builtins.__import__  # numpy's lazy C-level imports need it; formulas cannot name it
ALLOWED_MODULES = {"numpy", "math", "json", "re", "pathlib", "time", "wave", "hashlib", "itertools", "functools",
                   "collections", "statistics", "random", "string", "textwrap", "colorsys", "struct", "zlib", "base64",
                   "bisect", "heapq", "fractions", "decimal", "copy", "datetime", "unicodedata", "difflib", "html",
                   "operator", "dataclasses", "typing", "PIL", "cv2", "subprocess", "xml", "urllib.parse", "calendar",
                   "array", "binascii", "fnmatch", "shlex", "pprint", "uuid", "enum", "numbers", "cmath", "scipy", "sqlite3",
                   "hmac", "yaml", "csv", "zipfile", "gzip", "secrets", "ast", "tokenize", "keyword"}
PROGRAMS_ALLOWED = {"ffmpeg", "ffprobe", "node"}


class FormulaError(ValueError):
    pass


def allowed_module(mod: str) -> bool:
    return mod in ALLOWED_MODULES or mod.split(".")[0] in ALLOWED_MODULES - {"urllib", "xml"} or \
        any(mod == a or mod.startswith(a + ".") for a in ("urllib.parse", "xml.etree"))


def check_tree(tree):
    for node in ast.walk(tree):
        if not isinstance(node, NODES):
            raise FormulaError("not allowed in a data card: %s" % type(node).__name__)
        if isinstance(node, ast.Attribute) and (node.attr.startswith("_") or node.attr in DENY_ATTR):
            raise FormulaError("attribute not allowed: .%s" % node.attr)
        if isinstance(node, ast.Name) and (node.id.startswith("__") or node.id in FORBIDDEN):
            raise FormulaError("name not allowed: %s" % node.id)
        if isinstance(node, (ast.FunctionDef, ast.arg)) and getattr(node, "name", getattr(node, "arg", "")).startswith("__"):
            raise FormulaError("name not allowed")
    return tree


class _Ticks(ast.NodeTransformer):
    def _tick(self, node):
        self.generic_visit(node)
        node.body.insert(0, ast.Expr(ast.Call(ast.Name("__tick__", ast.Load()), [], [])))
        return node
    visit_For = visit_While = _tick


class _Shim:
    """subprocess for cards: run/Popen/check_output for ffmpeg, ffprobe and node only."""
    PIPE, DEVNULL, STDOUT, CalledProcessError, TimeoutExpired = (_subprocess.PIPE, _subprocess.DEVNULL, _subprocess.STDOUT,
                                                                 _subprocess.CalledProcessError, _subprocess.TimeoutExpired)
    CompletedProcess = _subprocess.CompletedProcess

    @staticmethod
    def _ok(cmd):
        prog = Path(str(cmd[0] if isinstance(cmd, (list, tuple)) else str(cmd).split()[0])).stem.lower()
        if prog not in PROGRAMS_ALLOWED:
            raise PermissionError("a data card may run only %s, not %s" % (sorted(PROGRAMS_ALLOWED), prog))
        if isinstance(cmd, (list, tuple)):
            cmd = [shutil.which(str(cmd[0])) or str(cmd[0])] + list(cmd[1:])
        return cmd

    def run(self, cmd, *a, **k):
        k.pop("shell", None)
        return _subprocess.run(self._ok(cmd), *a, **k)

    def Popen(self, cmd, *a, **k):  # noqa: N802 - mirrors the module
        k.pop("shell", None)
        return _subprocess.Popen(self._ok(cmd), *a, **k)

    def check_output(self, cmd, *a, **k):
        k.pop("shell", None)
        return _subprocess.check_output(self._ok(cmd), *a, **k)

    def check_call(self, cmd, *a, **k):
        k.pop("shell", None)
        return _subprocess.check_call(self._ok(cmd), *a, **k)


def resolve_import(spec: str):
    """'numpy' / 'PIL:Image' / 'pathlib:Path' -> object, only from ALLOWED_MODULES."""
    mod, _, attr = spec.partition(":")
    if not allowed_module(mod):
        raise FormulaError("module not allowed in a data card: " + mod)
    if mod == "subprocess":
        return _Shim() if not attr else getattr(_Shim(), attr)
    m = importlib.import_module(mod)
    if not attr:
        return m
    try:
        return getattr(m, attr)
    except AttributeError:
        return importlib.import_module(mod + "." + attr)


def compile_card(src: str):
    tree = check_tree(ast.parse(src, mode="exec"))
    if not (len(tree.body) == 1 and isinstance(tree.body[0], ast.FunctionDef) and tree.body[0].name == "card"):
        raise FormulaError("a program is exactly one def card(...)")
    tree = ast.fix_missing_locations(_Ticks().visit(tree))
    return compile(tree, "<card>", "exec")


def run_card(src: str, args: list, env: dict):
    """Define ``card`` from ``src`` in a namespace of ``env`` + safe builtins and call it with ``args``."""
    state = {"n": 0, "t0": time.time()}

    def tick():
        state["n"] += 1
        if state["n"] > MAX_ITER or (state["n"] % 10000 == 0 and time.time() - state["t0"] > MAX_SECONDS):
            raise FormulaError("iteration cap reached (%d iterations)" % state["n"])
    g = {"__builtins__": SAFE_BUILTINS, "__tick__": tick, "__name__": "card"}
    g.update(env)
    exec(compile_card(src), g)  # noqa: S102 - whitelisted AST only
    return g["card"](*args)


def run(steps, ret, env):
    """Expression helper (tests, REPL): statements then one expression, through the same whitelist."""
    body = "\n".join("    " + s for s in steps) + "\n    return " + ret
    return run_card("def card():\n" + body, [], env)
