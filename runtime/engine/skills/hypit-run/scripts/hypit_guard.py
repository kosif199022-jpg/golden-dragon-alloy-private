#!/usr/bin/env python3
"""Fail-closed Hypit plan and CLI inspection gate. No network or paid calls."""
import re
from dataclasses import dataclass

PROVIDER=re.compile(r"^\s*([\w.\-]+)\s*\(([^)]+)\)\s*[·•]\s*(.+?)\s*$")
FREE=re.compile(r"\blocal\s*,\s*no\s+provider\s+charge\b",re.I)
PRICE=re.compile(r"(?:[$€£]\s*\d|\d+(?:\.\d+)?\s*(?:credits?\b|كريدت))",re.I)
ERROR=re.compile(r"(?m)^\s*[×✕✖](?!\d)\s+")
READ_ONLY={"doctor","version","--version","-v","check","plan","inspect","logs","builds","pricing"}

@dataclass
class Gate:
    bad: list
    errors: list
    providers: int
    @property
    def safe(self):
        return not self.bad and not self.errors

def assess_plan(text,code=0):
    bad,errors,count=[],[],0
    for line in text.splitlines():
        match=PROVIDER.match(line)
        if not match: continue
        count+=1
        if not match.group(2).startswith("@"): errors.append("unrecognized provider package")
        if not FREE.search(match.group(3)):
            bad.append(line.strip())
            if not PRICE.search(match.group(3)): errors.append("provider price missing")
    if code: errors.append("plan command failed")
    if not count: errors.append("no provider pricing lines")
    if ERROR.search(text): errors.append("runtime preflight failure")
    return Gate(bad,errors,count)

def cli_is_inspection_only(args):
    return bool(args) and args[0] in READ_ONLY and "--" not in args and not any(
        x in {"--allow-paid","--force","--yes","--publish"} for x in args)
