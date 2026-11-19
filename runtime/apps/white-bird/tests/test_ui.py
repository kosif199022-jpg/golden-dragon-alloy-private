"""ui\\index.html and the Chrome extension: scripts parse, referenced element ids and files exist."""
import collections
import json
import re
import subprocess

import pytest

from conftest import APP, read

UI = APP / "ui"
EXT = APP / "chrome_extension"
HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
# Ids the UI references only behind a guard ($('#x')&&...), so a missing element is harmless dead code, not a break.
OPTIONAL_IDS = {
    "ctlState": "guarded by $('#ctlState')&& in renderBridge(); the element is gone upstream too (dead code)",
}


@pytest.fixture(scope="module")
def html():
    return read("ui/index.html")


@pytest.fixture(scope="module")
def scripts(html):
    """[(attrs, body)] of every <script> block."""
    return re.findall(r"<script\b([^>]*)>(.*?)</script>", html, re.S | re.I)


def node_check(node, path):
    r = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 0, f"{path.name}: {r.stderr.strip()[:1500]}"


def test_inline_scripts_parse(node, scripts, tmp_path):
    inline = [body for attrs, body in scripts if "src=" not in attrs]
    assert inline, "no inline <script> in index.html"
    for i, body in enumerate(inline):
        f = tmp_path / f"index_script_{i}.js"
        f.write_text(body, encoding="utf-8")
        node_check(node, f)


def test_external_scripts_exist(scripts):
    for attrs, _ in scripts:
        m = re.search(r"""src\s*=\s*["']([^"']+)""", attrs)
        if m and not re.match(r"^[a-z]+:|^//", m.group(1)):
            assert (UI / m.group(1)).is_file(), m.group(1)


def _defined_ids(html, js):
    ids = set(re.findall(r"""\bid\s*=\s*["']([A-Za-z][\w-]*)["']""", html))         # markup, including JS templates
    ids |= set(re.findall(r"""\.id\s*=\s*["'`]([A-Za-z][\w-]*)["'`]""", js))         # el.id = '...'
    return ids


def _referenced_ids(js):
    """Ids used by getElementById('x') and by any selector string starting with #x: querySelector('#x .y'), the app's
    $('#x') (= document.querySelector) and Spotlight's command list ('#newBtn', clicked through $1(s))."""
    refs = collections.defaultdict(list)
    for m in re.finditer(r"""getElementById\(\s*(['"])([^'"]+)\1\s*\)""", js):
        refs[m.group(2)].append(m.start())
    for m in re.finditer(r"""(['"`])#([A-Za-z][\w-]*)""", js):
        if not HEX_COLOR.match("#" + m.group(2)):
            refs[m.group(2)].append(m.start())
    return refs


def test_static_ids_unique(html):
    static = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    ids = re.findall(r"""\bid\s*=\s*["']([^"']+)["']""", static)
    dups = sorted(k for k, v in collections.Counter(ids).items() if v > 1)
    assert not dups, f"duplicate ids (querySelector only finds the first): {dups}"


def test_referenced_ids_exist(html, scripts):
    js = "\n".join(body for _, body in scripts)
    defined = _defined_ids(html, js)
    refs = _referenced_ids(js)
    assert len(refs) > 100, f"only {len(refs)} id references found: did the selector helper change?"
    missing = sorted(k for k in refs if k not in defined and k not in OPTIONAL_IDS)
    assert not missing, f"ids referenced by the UI script but defined nowhere: {missing}"


def test_optional_ids_stay_guarded(html, scripts):
    js = "\n".join(body for _, body in scripts)
    defined = _defined_ids(html, js)
    for k in OPTIONAL_IDS:
        if k in defined:
            continue                        # came back: fine either way
        unguarded = []
        for m in re.finditer(r"""(['"`])#""" + re.escape(k) + r"""\b""", js):
            call = re.search(r"\$\(\s*$", js[max(0, m.start() - 4):m.start()])          # $('#k') ...
            end = js.index(")", m.end()) + 1
            guarded = call and (js[end:end + 2] == "&&" or js[:m.start()].rstrip("$( ").endswith("&&"))
            if not guarded:
                unguarded.append(js[max(0, m.start() - 30):m.end() + 30])
        assert not unguarded, f"#{k} is missing and now used without a guard: {unguarded}"


def test_local_assets_exist(html):
    static = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    styles = "\n".join(re.findall(r"<style\b[^>]*>(.*?)</style>", html, re.S | re.I))
    markup = re.sub(r"<style\b[^>]*>.*?</style>", "", static, flags=re.S | re.I)
    refs = set(re.findall(r"""\b(?:src|href)\s*=\s*["']([^"'#][^"']*)["']""", markup))
    refs |= set(re.findall(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", styles))
    local = sorted(r for r in refs if not re.match(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", r, re.I))
    assert local, "no local assets found (fonts, icon): parser broken?"
    missing = [r for r in local if not (UI / r.split("?")[0].split("#")[0]).is_file()]
    assert not missing, f"index.html points at files that aren't in ui\\: {missing}"


# ---------------------------------------------------------------- Chrome extension
@pytest.fixture(scope="module")
def manifest():
    return json.loads(read("chrome_extension/manifest.json"))


def test_manifest_shape(manifest):
    assert manifest["manifest_version"] == 3
    for k in ("name", "version", "background", "action"):
        assert k in manifest, k
    assert re.match(r"^\d+(\.\d+){0,3}$", manifest["version"]), manifest["version"]


def _manifest_files(m):
    files = []
    files.append(m.get("background", {}).get("service_worker"))
    action = m.get("action", {})
    files.append(action.get("default_popup"))
    icon = action.get("default_icon")
    files += list(icon.values()) if isinstance(icon, dict) else [icon]
    files += list(m.get("icons", {}).values())
    for cs in m.get("content_scripts", []):
        files += cs.get("js", []) + cs.get("css", [])
    for war in m.get("web_accessible_resources", []):
        files += [r for r in war.get("resources", []) if "*" not in r]
    files.append(m.get("options_page"))
    return sorted({f for f in files if f})


def test_manifest_files_exist(manifest):
    files = _manifest_files(manifest)
    assert "background.js" in files and "popup.html" in files, files
    missing = [f for f in files if not (EXT / f).is_file()]
    assert not missing, f"manifest.json points at missing files: {missing}"


def test_popup_scripts_exist():
    for src in re.findall(r"""<script[^>]+src\s*=\s*["']([^"']+)""", read("chrome_extension/popup.html")):
        assert (EXT / src).is_file(), src


@pytest.mark.parametrize("name", ["background.js", "popup.js"])
def test_extension_scripts_parse(node, name):
    node_check(node, EXT / name)
