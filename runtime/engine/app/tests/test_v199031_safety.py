"""Offline code safety checks: do not import or launch the Windows desktop app."""
from pathlib import Path
import ast
ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app/apps/dragon_desktop/app.py"


def test_desktop_app_syntax_and_safe_default():
    src = APP.read_text(encoding="utf-8")
    ast.parse(src)
    assert 'self.auto = bool(api._settings.get("auto_approve", False))' in src
    assert 'self.auto = bool(api._settings.get("auto_approve", True))' not in src


def test_explicit_approval_cannot_be_bypassed_by_auto_mode():
    src = APP.read_text(encoding="utf-8")
    assert 'if need and not self.ask(cid, name, args):' in src
    assert 'if need and not self.auto and not self.ask' not in src
    for action in ('run_engine', 'run_command', 'rea', 'retool', 'rebuild_app', 'deployment_status'):
        # all six tools remain declared with approval=True
        anchor = src.index(f'tool("{action}"')
        assert 'approval=True' in src[anchor:anchor+1400], action


def test_desktop_control_off_by_default_and_version():
    src = APP.read_text(encoding="utf-8")
    assert 'bool(api._settings.get("control_default"))' in src
    assert 'if act in control.System.DANGER:' in src
    assert '__version__ = "1990.' in (ROOT/'app/dragon/__init__.py').read_text(encoding='utf-8')  # v1990.x series (was pinned to 1990.3.1)


def test_no_installer_or_device_control_in_safety_checks():
    tree = ast.parse(Path(__file__).read_text(encoding='utf-8'))
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not (imported & {'subprocess', 'socket', 'os', 'ctypes', 'urllib'})
