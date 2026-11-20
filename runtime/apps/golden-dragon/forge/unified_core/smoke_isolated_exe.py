"""Start one isolated GoldenDragon.exe and report startup evidence on Windows.

Requires an existing, verified TEMP-located test EXE. Does not install, open
files from the real profile, use API keys, change a shortcut, or touch main.
The child process is always stopped on exit. No GUI clicks or model calls.

python -B smoke_isolated_exe.py --exe "TEMP/../GoldenDragon.exe" --seconds 150
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _window_titles(target_pid: int) -> list[str]:
    if os.name != "nt":
        return []
    u32 = ctypes.windll.user32
    names = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _):
        pid = ctypes.c_ulong(0)
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == target_pid and u32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(hwnd, buf, 256)
            names.append(buf.value[:160])
        return True

    u32.EnumWindows(callback, None)
    return names


def _safe_executable(path: Path) -> Path:
    path = path.expanduser().resolve(strict=True)
    temp = Path(tempfile.gettempdir()).resolve()
    if path.name.lower() != "goldendragon.exe":
        raise ValueError("expected a GoldenDragon.exe test executable")
    if not path.is_relative_to(temp):
        raise ValueError("only executables under TEMP are permitted")
    if not {"isolated-package", "dist"}.issubset(set(path.parts)):
        raise ValueError("executable is not in a verified isolated-package/dist tree")
    return path


def smoke(executable: Path, seconds: int = 150) -> dict:
    if os.name != "nt":
        raise RuntimeError("Windows required for GUI smoke test")
    if not 20 <= seconds <= 300:
        raise ValueError("timeout must be between 20 and 300 seconds")
    executable = _safe_executable(executable)
    sandbox = Path(tempfile.mkdtemp(prefix="golden-dragon-gui-smoke-"))
    env = dict(os.environ)
    for name, folder in (
        ("APPDATA", "roaming"), ("LOCALAPPDATA", "local"),
        ("USERPROFILE", "home"), ("HOME", "home"),
        ("TEMP", "scratch"), ("TMP", "scratch")
    ):
        p = sandbox / folder
        p.mkdir(exist_ok=True)
        env[name] = str(p)
    # Never adopt production app settings, data, chats or model tokens.
    env["GOLDEN_DRAGON_HOME"] = str(executable.parents[3])
    env["BLACK_DRAGON_HOME"] = str(sandbox / "home")
    env["DRAGON_MONTAGE_HOME"] = str(sandbox / "home")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        env.pop(key, None)
    settings = sandbox / "roaming" / "GoldenDragon" / "settings.json"
    settings.parent.mkdir(exist_ok=True)
    settings.write_text(
        json.dumps({"engine": "api", "effort": "high", "gb_mind_v1": True}),
        encoding="utf-8"
    )
    life = settings.parent / "run" / "lifecycle.log"
    p = None
    observations = []
    stdout = (sandbox / "stdout.log").open("wb")
    stderr = (sandbox / "stderr.log").open("wb")
    try:
        start = time.monotonic()
        p = subprocess.Popen([str(executable)], cwd=executable.parent,
                             env=env, stdout=stdout, stderr=stderr, shell=False)
        deadline = start + seconds
        while time.monotonic() < deadline:
            time.sleep(5)
            titles = _window_titles(p.pid)
            log = life.read_text(encoding="utf-8", errors="replace") if life.is_file() else ""
            state = {
                "seconds": round(time.monotonic() - start, 1),
                "running": p.poll() is None,
                "visible_windows": titles,
                "lifecycle_created": bool(log),
                "start_logged": " start" in log,
                "crash_logged": "crashed:" in log,
            }
            observations.append(state)
            print("SMOKE_CHECK", json.dumps(state, ensure_ascii=True), flush=True)
            if titles and state["start_logged"]:
                break
            if p.poll() is not None:
                break
        result = {
            "executable": str(executable), "sandbox": str(sandbox),
            "pid": p.pid, "observations": observations,
            "gui_window_observed": any(x["visible_windows"] for x in observations),
            "app_start_logged": any(x["start_logged"] for x in observations),
            "terminal_returncode_before_cleanup": p.poll(),
            "lifecycle_tail": life.read_text(encoding="utf-8", errors="replace")[-1200:] if life.is_file() else "",
            "stderr_tail": (sandbox / "stderr.log").read_text(encoding="utf-8", errors="replace")[-1000:] if (sandbox / "stderr.log").is_file() else "",
        }
        result["startup_verified"] = bool(result["gui_window_observed"] and result["app_start_logged"])
        return result
    finally:
        if p is not None and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=12)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=12)
        stdout.close()
        stderr.close()
        if p is not None:
            print("TEST_PROCESS_STOPPED", p.pid, p.returncode, flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=150)
    args = parser.parse_args(argv)
    result = smoke(args.exe, args.seconds)
    print("FINAL_SMOKE_REPORT", json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["startup_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
