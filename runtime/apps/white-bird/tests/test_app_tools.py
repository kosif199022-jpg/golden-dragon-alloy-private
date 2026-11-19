"""The tools app.py sends to Claude: valid schemas, unique names, and a handler for every tool and every action.

Declared in app.py as TOOLS (via tool()), turned into API_TOOLS (+ the hosted web_search / web_fetch), plus DELEGATE and
COMPUTER_TOOL / BROWSER_TOOL / SYSTEM_TOOL when those switches are on. Dispatched by Session.dispatch (if name == ...);
computer/browser/system go on to Api._control_action -> control.Computer / control.System / the Chrome extension.
"""
import ast
import re

import pytest

from conftest import compared_constants, find_def, mcp_control_tools, read, tree

NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
JSON_TYPES = {"string", "integer", "number", "boolean", "array", "object", "null"}
TOOL_KEYS = {"name", "description", "input_schema", "eager_input_streaming", "cache_control"}
# tools that run programs or change things outside the chat: they must always ask the user first
MUST_ASK = {"run_command", "run_engine", "rea", "retool", "rebuild_app", "deployment_status"}
# system actions the tool description promises will always wait for the user's approval
SYSTEM_MUST_ASK = {"kill", "service_start", "service_stop", "service_restart", "uninstall", "startup_disable", "sleep",
                   "hibernate", "shutdown", "restart", "logoff"}


def schema_problems(s, where):
    if not isinstance(s, dict):
        return [f"{where}: schema is not an object"]
    out = []
    t = s.get("type")
    if t not in JSON_TYPES:
        out.append(f"{where}: type {t!r}")
    if "description" in s and not (isinstance(s["description"], str) and s["description"].strip()):
        out.append(f"{where}: empty description")
    if "enum" in s:
        e = s["enum"]
        if not isinstance(e, list) or not e:
            out.append(f"{where}: empty enum")
        elif len(set(e)) != len(e):
            out.append(f"{where}: duplicate enum values {sorted({x for x in e if e.count(x) > 1})}")
        elif t == "string" and not all(isinstance(x, str) for x in e):
            out.append(f"{where}: non-string enum value")
    if t == "object":
        props = s.get("properties", {})
        if not isinstance(props, dict):
            return out + [f"{where}: properties is not an object"]
        for k, v in props.items():
            out += schema_problems(v, f"{where}.{k}")
        req = s.get("required", [])
        if len(set(req)) != len(req):
            out.append(f"{where}: duplicate required entries")
        if [r for r in req if r not in props]:
            out.append(f"{where}: required {[r for r in req if r not in props]} not in properties")
    if t == "array":
        if "items" not in s:
            out.append(f"{where}: array without items")
        else:
            out += schema_problems(s["items"], f"{where}[]")
    for lo, hi in (("minimum", "maximum"), ("minItems", "maxItems")):
        if lo in s and hi in s and s[lo] > s[hi]:
            out.append(f"{where}: {lo} > {hi}")
    return out


@pytest.fixture(scope="module")
def custom(app):
    """Every client-side tool the model can be given at once (largest combination of switches)."""
    return [t for t in app.API_TOOLS if "type" not in t] + [app.DELEGATE, app.COMPUTER_TOOL, app.BROWSER_TOOL, app.SYSTEM_TOOL]


def test_tool_names_unique(app, custom):
    names = [t["name"] for t in custom] + [t["name"] for t in app.API_TOOLS if "type" in t]
    assert len(names) == len(set(names)), f"duplicate tool names: {sorted({n for n in names if names.count(n) > 1})}"
    assert len(custom) >= 20, f"only {len(custom)} tools: did the TOOLS list get cut?"


def test_tool_shape(custom):
    problems = []
    for t in custom:
        n = t.get("name", "?")
        if not NAME_RE.match(n):
            problems.append(f"{n}: bad name")
        if set(t) - TOOL_KEYS:
            problems.append(f"{n}: unexpected keys {sorted(set(t) - TOOL_KEYS)} (the API rejects them)")
        if not (isinstance(t.get("description"), str) and len(t["description"]) >= 20):
            problems.append(f"{n}: description missing or too short")
        s = t.get("input_schema", {})
        if s.get("type") != "object":
            problems.append(f"{n}: input_schema.type must be object")
        if s.get("additionalProperties") is not False:
            problems.append(f"{n}: input_schema should set additionalProperties: false")
        problems += schema_problems(s, n)
    assert not problems, "\n".join(problems)


def test_internal_keys_never_reach_the_api(app):
    for t in app.API_TOOLS:
        assert not [k for k in t if k.startswith("_")], f"{t['name']} sends internal keys to the API"
    assert all("_approval" in t for t in app.TOOLS), "TOOLS entries lost their _approval flag"


def test_hosted_tools(app):
    hosted = [t for t in app.API_TOOLS if "type" in t]
    assert {t["name"] for t in hosted} == {"web_search", "web_fetch"}, hosted
    for t in hosted:
        assert re.match(r"^[a-z_]+_\d{8}$", t["type"]), t


def test_every_tool_has_a_handler(custom):
    handled = compared_constants(find_def(tree("app.py"), "Session", "dispatch"), "name")
    missing = sorted(t["name"] for t in custom if t["name"] not in handled)
    assert not missing, f"declared but not handled by Session.dispatch (would end in 'unknown tool'): {missing}"


def test_dangerous_tools_ask_first(app):
    names = {t["name"] for t in app.TOOLS}
    assert app.NEEDS_APPROVAL <= names
    assert MUST_ASK <= app.NEEDS_APPROVAL, f"no longer asks before running: {sorted(MUST_ASK - app.NEEDS_APPROVAL)}"


def _computer_handled():
    fn = find_def(tree("app.py"), "Api", "_control_action")
    acts = compared_constants(fn, "act")
    prefixes = {n.args[0].value for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "startswith" and getattr(n.func.value, "id", "") == "act" and n.args
                and isinstance(n.args[0], ast.Constant)}
    return acts, prefixes


def test_computer_actions_handled(app):
    acts, prefixes = _computer_handled()
    window_ops = compared_constants(find_def(tree("control.py"), "Computer", "window"), "op")
    renamed = {"window_move": "move", "window_resize": "resize"}       # as mapped in _control_action
    missing = []
    for a in app.COMPUTER_TOOL["input_schema"]["properties"]["action"]["enum"]:
        if a in acts:
            continue
        p = next((p for p in prefixes if a.startswith(p)), None)
        if p is None or renamed.get(a, a[len(p):]) not in window_ops:
            missing.append(a)
    assert not missing, f"computer actions with no handler: {missing}"


def test_system_actions_handled(app):
    handled = compared_constants(find_def(tree("control.py"), "System", "run"), "act")
    enum = app.SYSTEM_TOOL["input_schema"]["properties"]["action"]["enum"]
    assert not set(enum) - handled, f"system actions with no handler in control.System.run: {sorted(set(enum) - handled)}"
    danger = app.control.System.DANGER
    assert SYSTEM_MUST_ASK <= danger, f"no longer ask the user first: {sorted(SYSTEM_MUST_ASK - danger)}"


def test_browser_actions_handled_by_the_extension(app):
    cases = set(re.findall(r"case\s+'([a-z_]+)'\s*:", read("chrome_extension/background.js")))
    enum = app.BROWSER_TOOL["input_schema"]["properties"]["action"]["enum"]
    assert not set(enum) - cases, f"browser actions the Chrome extension doesn't handle: {sorted(set(enum) - cases)}"


def test_subscription_mode_tools_match(app):
    """mcp_control.py offers computer/browser/system to Claude Code (subscription mode); the app runs them through the
    same _control_action, so their schemas must be valid and every action must exist in the app's own tool."""
    own = {"computer": app.COMPUTER_TOOL, "browser": app.BROWSER_TOOL, "system": app.SYSTEM_TOOL}
    for t in mcp_control_tools():
        s = t["inputSchema"]
        assert not schema_problems(s, "mcp:" + t["name"]), schema_problems(s, "mcp:" + t["name"])
        extra = set(s["properties"]["action"]["enum"]) - set(own[t["name"]]["input_schema"]["properties"]["action"]["enum"])
        assert not extra, f"mcp_control {t['name']} offers actions the app tool doesn't: {sorted(extra)}"
