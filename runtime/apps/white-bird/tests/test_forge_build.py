"""The forge and the build gate it writes at the top of app\\build.ps1."""
import base64
import importlib.util
import json
import os
import subprocess
import sys

import pytest

from conftest import APP, FORGE, TESTS, read, snapshot

PS_PARSE = r'''
$errs = $null; $toks = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($env:WB_PS_FILE, [ref]$toks, [ref]$errs)
$params = @(); if ($ast.ParamBlock) { $params = @($ast.ParamBlock.Parameters | ForEach-Object { $_.Name.VariablePath.UserPath }) }
$msgs = @($errs | ForEach-Object { "line $($_.Extent.StartLineNumber): $($_.Message)" })
ConvertTo-Json -Compress -InputObject @{ errors = $msgs; params = $params }
'''


def load_forge():
    """Import the forge without running it: its top level only defines constants and functions (main() is under __main__)."""
    spec = importlib.util.spec_from_file_location("wb_forge", FORGE / "make_white_bird.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_forge_check_mode():
    src = read("make_white_bird.py", FORGE)
    flag = next((f for f in ("--check", "--dry-run", "--dry") if f'"{f}"' in src), None)
    if not flag:
        pytest.skip("forge has no dry/check mode (only --force and --seed): every run rewrites app\\, so it is not run here")
    before = snapshot(APP)
    r = subprocess.run([sys.executable, "-X", "utf8", "-B", str(FORGE / "make_white_bird.py"), flag], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert snapshot(APP) == before, f"forge {flag} wrote into app\\"


def test_build_ps1_has_the_test_gate():
    t = read("build.ps1")
    first = next(line for line in t.splitlines() if line.strip() and not line.lstrip().startswith("#"))
    assert first.startswith("param(") and "[switch]$SkipTests" in first, f"first statement: {first!r}"
    gate = t.index("run_tests.ps1")
    assert 'Join-Path $PSScriptRoot "..\\tests\\run_tests.ps1"' in t
    assert gate < t.index("Set-Content -Encoding ascii") < t.index("python -m PyInstaller"), "tests must run before anything is built"
    assert t.count("exit 1") >= 2 and "if ($LASTEXITCODE -ne 0)" in t[:t.index("python -m PyInstaller")]
    assert (TESTS / "run_tests.ps1").is_file()


def test_build_ps1_is_what_the_forge_generates():
    """app\\build.ps1 must be the forge's current output (a forge change without regenerating would build without it)."""
    raw = (APP / "build.ps1").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "build.ps1 lost its UTF-8 BOM (PowerShell 5.1 would misread the Arabic in it)"
    forge = load_forge()
    have = raw.decode("utf-8-sig").replace("\r\n", "\n")          # the forge writes it in text mode: CRLF on Windows
    assert have == forge.patch_build(forge.build_ps1()), "app\\build.ps1 is stale: run forge\\make_white_bird.py"


@pytest.mark.parametrize("path", [APP / "build.ps1", TESTS / "run_tests.ps1"], ids=["build.ps1", "run_tests.ps1"])
def test_powershell_scripts_parse(powershell, path):
    enc = base64.b64encode(PS_PARSE.encode("utf-16-le")).decode("ascii")
    r = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-EncodedCommand", enc], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60, env=dict(os.environ, WB_PS_FILE=str(path)))
    assert r.returncode == 0, r.stderr[-1500:]
    data = json.loads(r.stdout.strip().splitlines()[-1])
    errors = data["errors"] if isinstance(data["errors"], list) else [data["errors"]]
    assert not [e for e in errors if e], f"{path.name}: {errors}"
    if path.name == "build.ps1":
        params = data["params"] if isinstance(data["params"], list) else [data["params"]]
        assert "SkipTests" in params, params
