"""Score one journey run.

Usage:
    python -X utf8 evals/journey/score.py TRANSCRIPT.jsonl
    python -X utf8 evals/journey/score.py --summary evals/journey/results.json

TRANSCRIPT.jsonl holds one event per line:
    {"type":"tool_use","name":"PowerShell","input":{"command":"..."}}
    {"type":"tool_result","is_error":false,"content":"..."}

Output: {tool_calls, cli_errors, source_reads, guessed_params}.
    tool_calls     : number of tool_use events.
    cli_errors     : tool_result events flagged is_error, or whose text shows a
                     traceback or a non-zero exit code.
    source_reads   : tool_use events that read a skill .py file (Read, Get-Content,
                     Select-String, cat, type, Grep) or list the code folder.
    guessed_params : tool_result events that show a parameter-shape error
                     ("not a key=value", "unrecognized arguments", "unknown option").

If no transcript exists the sub-agent self-report is recorded instead and
score.py marks the counts as self-reported (see results.json).
"""
import json
import re
import sys
from collections import Counter

ERR_RE = re.compile(r"Traceback|exit code\s*[1-9]|exit\s*[1-9]\b", re.I)
GUESS_RE = re.compile(r"not a key=value|unrecognized arguments|unknown option|invalid choice", re.I)
SRC_RE = re.compile(r"\.py\b|rose_\w+|\bsrc\b", re.I)
READ_TOOLS = {"Read", "Grep", "Glob", "Get-Content", "cat", "type", "Select-String", "head", "tail", "sed"}


def score(path):
    counts = Counter()
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            ev = json.loads(line)
            kind = ev.get("type")
            if kind == "tool_use":
                counts["tool_calls"] += 1
                name = ev.get("name", "")
                blob = json.dumps(ev.get("input", {}), ensure_ascii=False)
                if (name in READ_TOOLS or name.split(" ")[0] in READ_TOOLS) and SRC_RE.search(blob):
                    counts["source_reads"] += 1
            elif kind == "tool_result":
                text = str(ev.get("content", ""))
                if ev.get("is_error") or ERR_RE.search(text):
                    counts["cli_errors"] += 1
                if GUESS_RE.search(text):
                    counts["guessed_params"] += 1
    return {k: counts.get(k, 0) for k in ("tool_calls", "cli_errors", "source_reads", "guessed_params")}


def summary(path):
    with open(path, encoding="utf-8") as f:
        res = json.load(f)
    outcomes = Counter(j["outcome"] for j in res["jobs"])
    return {"jobs": len(res["jobs"]), "outcomes": dict(outcomes),
            "tool_calls_total": sum(j["tool_calls"] for j in res["jobs"] if isinstance(j["tool_calls"], int))}


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--summary":
        print(json.dumps(summary(sys.argv[2]), ensure_ascii=False, indent=2))
    elif len(sys.argv) == 2:
        print(json.dumps(score(sys.argv[1]), ensure_ascii=False, indent=2))
    else:
        sys.exit(__doc__)
