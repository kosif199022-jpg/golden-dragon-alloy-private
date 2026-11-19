"""Approval for privileged actions is required regardless of auto mode."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
WEAK = 'if need and not self.auto and not self.ask(cid, name, args):'
SAFE = 'if need and not self.ask(cid, name, args):'


class ApprovalGateTest(unittest.TestCase):
    def test_white_bird_guard(self):
        src = (ROOT / 'apps/white-bird/app/app.py').read_text(encoding='utf-8')
        self.assertIn(SAFE, src)
        self.assertNotIn(WEAK, src)
        self.assertIn('self.auto = bool(api._settings.get("auto_approve", False))', src)

    def test_generator_repairs_or_rejects(self):
        path = ROOT / 'apps/white-bird/forge/make_white_bird.py'
        spec = importlib.util.spec_from_file_location('white_security_forge', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        unsafe = ('self.auto = bool(api._settings.get("auto_approve", True))\n'
                  'if need and not self.auto and not self.ask(cid, name, args):')
        safe = module.enforce_approval_gate(unsafe)
        self.assertIn(SAFE, safe)
        self.assertNotIn(WEAK, safe)
        with self.assertRaises(SystemExit):
            module.enforce_approval_gate('missing approval code')

if __name__ == '__main__':
    unittest.main()
