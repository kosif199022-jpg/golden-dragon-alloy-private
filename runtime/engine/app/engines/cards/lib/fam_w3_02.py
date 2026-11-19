"""Helpers of runners/fam_w3_02.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import fx
import json
import re


_C_SRC = (
    '#include <stdio.h>\n'
    'int helper(int x){return x*3+1;}\n'
    'int main(){const char *s="MAGIC_TOKEN_ABC";printf("%s %d\\n",s,helper(7));return 0;}\n'
)


def _cc(wd: Path) -> Path:
    """Compile a tiny ELF (with a build-id note) to analyse statically. gcc is in the base image."""
    src = wd / "t.c"
    src.write_text(_C_SRC, encoding="utf-8")
    out = wd / "t.bin"
    fx.run(["gcc", "-O0", "-g", "-Wl,--build-id", str(src), "-o", str(out)], timeout=30)
    return out


def _so(wd: Path) -> Path:
    """Compile a shared object with one exported (GLOBAL) and one static (local) function."""
    src = wd / "lib.c"
    src.write_text("int exported_add(int a,int b){return a+b;}\n"
                   "static int hidden_impl(int x){return x+1;}\n"
                   "int exported_use(int x){return hidden_impl(x);}\n", encoding="utf-8")
    out = wd / "libt.so"
    fx.run(["gcc", "-shared", "-fPIC", "-O0", str(src), "-o", str(out)], timeout=30)
    return out


def _objdump_d(binary: Path) -> str:
    return fx.run(["objdump", "-d", str(binary)]).stdout


def _func_body(disasm: str, name: str) -> list:
    """Lines of the disassembly for function <name>, up to the next label."""
    lines = disasm.splitlines()
    out, inside = [], False
    for ln in lines:
        if re.match(r"^[0-9a-f]+ <%s>:" % re.escape(name), ln):
            inside = True
            continue
        if inside:
            if re.match(r"^[0-9a-f]+ <.+>:", ln):
                break
            if ln.strip():
                out.append(ln)
    return out


def _jw(path: Path, obj) -> Path:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return path
