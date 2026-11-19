"""v1.2 docs gate (lesson docs-commands-exist): every `$D <sub>` and `$D tool <name>` written in SKILL.md and
references/*.md exists in the code, SKILL.md's frontmatter is valid, and every reference SKILL.md names exists.

Scanned: SKILL.md and references/*.md (not references/skills/, not VIDEO_PROTOCOL_V2_ORIGINAL.md), backticked
spans and fenced blocks only. Lines tagged «(PC only)» or «يدوي» are skipped. No media; runs in about a second.
The module skips when the package root (SKILL.md next to app/) is absent, e.g. in a bare /tmp/dragon copy.
"""
import ast, json, os, re, subprocess, sys
from functools import lru_cache
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
PKG = APP.parent
SKILL_MD = PKG / "SKILL.md"
REF = PKG / "references"
LAUNCHER = PKG / "scripts" / "dragon.py"

if not (SKILL_MD.exists() and REF.is_dir() and LAUNCHER.exists()):
    pytest.skip("package root (SKILL.md, references/, scripts/dragon.py) not next to app/", allow_module_level=True)

SKIP_TAGS = ("(PC only)", "يدوي")
NOT_SCANNED = {"VIDEO_PROTOCOL_V2_ORIGINAL.md"}
# files a job writes (not references): SKILL.md may name them without them existing in the package
JOB_FILES = {"PLAN_AR.md", "RIGHTS.md", "PENDING.md", "DELIVERED.md", "LINKS.md", "CREDITS.md", "ATTRIBUTION.md",
             "SKILL.md", "README.md"}
FENCE = re.compile(r"^\s*(```|~~~)")
SPAN = re.compile(r"(`+)(.+?)\1")
SUB = re.compile(r"\$D\s+([a-z][a-z0-9_-]*)")
TOOL = re.compile(r"\$D\s+tool\s+([a-z0-9][a-z0-9_|-]*)")


def docs():
    return [SKILL_MD] + sorted(p for p in REF.glob("*.md") if p.name not in NOT_SCANNED)


def code_chunks(text):
    """(line number, line, [code pieces]) for every line: the whole line inside a fence, else its backtick spans."""
    fenced = False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        yield n, line, ([line] if fenced else [m.group(2) for m in SPAN.finditer(line)])


def commands():
    """[(file, line no, 'sub' or 'tool', name)] for every documented `$D` command outside skipped lines."""
    out = []
    for doc in docs():
        for n, line, chunks in code_chunks(doc.read_text(encoding="utf-8")):
            if any(tag in line for tag in SKIP_TAGS):
                continue
            for chunk in chunks:
                for m in SUB.finditer(chunk):
                    if m.group(1) != "tool":
                        out.append((doc.name, n, "sub", m.group(1)))
                for m in TOOL.finditer(chunk):
                    for name in filter(None, m.group(1).split("|")):
                        out.append((doc.name, n, "tool", name))
    return out


@lru_cache(maxsize=None)
def dragon_subcommands():
    """Subcommands of the dragon CLI, read from `python -m dragon --help` (its parser is built inside main())."""
    env = dict(os.environ, PYTHONPATH=str(APP) + os.pathsep + os.environ.get("PYTHONPATH", ""),
               PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, "-m", "dragon", "--help"], cwd=str(APP), env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr[-2000:]
    m = re.search(r"\{([a-z0-9_,-]+)\}", r.stdout)
    assert m, r.stdout[:500]
    return frozenset(m.group(1).split(","))


@lru_cache(maxsize=None)
def launcher_names():
    """(launcher commands such as where/setup/tool, tool names = TOOLS keys + names main() handles itself)."""
    src = LAUNCHER.read_text(encoding="utf-8")
    tools = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "TOOLS" for t in node.targets):
            tools |= {k.value for k in node.value.keys}
    assert tools, "TOOLS dict not found in scripts/dragon.py"
    tools |= set(re.findall(r'argv\[1\] == "([a-z0-9-]+)"', src))
    cmds = set(re.findall(r'cmd == "([a-z0-9-]+)"', src))
    return frozenset(cmds), frozenset(tools)


def frontmatter():
    text = SKILL_MD.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md has no frontmatter"
    try:
        import yaml
        data = yaml.safe_load(m.group(1))
    except ImportError:  # minimal reader: key: value or key: "double quoted"
        data = {}
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            v = v.strip()
            data[k.strip()] = json.loads(v) if v.startswith('"') else v
    assert isinstance(data, dict)
    return data, text[m.end():]


def test_frontmatter_parses_and_description_is_valid():
    data, _ = frontmatter()
    assert data.get("name") == "black-dragon"
    desc = data.get("description")
    assert isinstance(desc, str) and desc.strip()
    assert len(desc) <= 1024, len(desc)
    assert "<" not in desc and ">" not in desc
    assert set(data) <= {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}


def test_documented_subcommands_exist():
    subs = dragon_subcommands()
    cmds, _ = launcher_names()
    bad = [f"{f}:{n}: $D {name}" for f, n, kind, name in commands() if kind == "sub" and name not in subs | cmds]
    assert not bad, "commands not in `dragon --help` or the launcher:\n" + "\n".join(bad)


def test_documented_tools_exist():
    _, tools = launcher_names()
    bad = [f"{f}:{n}: $D tool {name}" for f, n, kind, name in commands() if kind == "tool" and name not in tools]
    assert not bad, "tools not in scripts/dragon.py TOOLS:\n" + "\n".join(bad)


def test_the_scan_sees_the_v12_commands():
    """Guard the parser itself: SKILL.md §3 must yield the v1.2 commands, or the two tests above prove nothing."""
    seen = {(kind, name) for f, _, kind, name in commands() if f == "SKILL.md"}
    for sub in ("verify", "mux", "patch-black", "align", "lyrics-sheet", "where", "setup"):
        assert ("sub", sub) in seen, sub
    for tool in ("tiktok-post", "styles"):
        assert ("tool", tool) in seen, tool


def test_references_named_in_skill_md_exist():
    _, body = frontmatter()
    missing = []
    for tok in sorted(set(re.findall(r"(?:app/|references/)?(?:skills/)?[A-Za-z0-9_*.-]+\.(?:md|jpg)", body))):
        name = tok.rsplit("/", 1)[-1]
        if tok.startswith(("references/", "app/")):
            path = PKG / tok
        elif tok.startswith("skills/"):
            path = REF / tok
        elif re.fullmatch(r"[A-Z0-9_]+\.md", name) and name not in JOB_FILES:
            path = REF / name
        else:
            continue
        found = list(path.parent.glob(path.name)) if "*" in path.name else ([path] if path.exists() else [])
        if not found:
            missing.append(tok)
    assert not missing, "named in SKILL.md but missing in the package: " + ", ".join(missing)


def test_every_reference_is_reachable_from_skill_md():
    _, body = frontmatter()
    files = sorted(p.name for p in REF.iterdir() if p.is_file() and p.suffix in (".md", ".jpg"))
    unreached = [f for f in files if f not in body]
    assert not unreached, "references not named in SKILL.md: " + ", ".join(unreached)
    if (REF / "skills").is_dir():
        assert "references/skills/*.md" in body or all(p.name in body for p in (REF / "skills").glob("*.md"))


def test_skill_md_shape():
    _, body = frontmatter()
    lines = SKILL_MD.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 320, len(lines)
    sec3 = body.split("## 3.", 1)[1].split("\n## 4.", 1)[0]
    assert sec3.strip().splitlines()[-1].strip() == "كل تسليم بيعدّي على verify؛ أي exit مش صفر يوقف التسليم"
    version = re.search(r'__version__\s*=\s*"(\d+(?:\.\d+)?)', (APP / "dragon" / "__init__.py").read_text(encoding="utf-8"))  # v1990: plain integer
    assert version and f"v{version.group(1)}" in lines[lines.index("---", 1) + 2], "title version != dragon version"
    assert "cinde" not in body, "the owner's personal Windows path must not be in SKILL.md"
