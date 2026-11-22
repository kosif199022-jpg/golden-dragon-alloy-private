"""V29 W01: the same `run` lines work in PowerShell 5.1, cmd and Git Bash (Windows only).

Each line is launched exactly as typed:
* PowerShell: powershell.exe -NoProfile -NonInteractive -EncodedCommand <line>
  (the encoded form carries the exact typed text; plain -Command would first pass
  through Windows argv quote stripping, which a person or tool typing into a
  PowerShell session never sees);
* cmd: cmd /d /s /c "<line>";
* Git Bash: bash -c <line> (never the WSL bash in System32).
The passing forms are printed to stdout for the docs item (W10).
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WIRED = 'rose_ext' in (ROOT / 'rose.py').read_text(encoding='utf-8')
ENTRY = (ROOT / ('rose.py' if WIRED else 'rose_run.py')).as_posix()
WORDS = 'الوردة الحمراء'


def _git_bash():
    cands = [shutil.which('bash'), r'C:\Program Files\Git\bin\bash.exe',
             r'C:\Program Files\Git\usr\bin\bash.exe', r'C:\Program Files (x86)\Git\bin\bash.exe']
    for c in cands:
        if c and os.path.isfile(c) and 'system32' not in c.lower():
            return c
    return None


def _shells():
    shells = {}
    ps = shutil.which('powershell.exe') or shutil.which('powershell')
    if ps:
        shells['powershell'] = lambda line: [ps, '-NoProfile', '-NonInteractive', '-EncodedCommand',
                                             base64.b64encode(line.encode('utf-16-le')).decode('ascii')]
    comspec = os.environ.get('COMSPEC') or shutil.which('cmd.exe')
    if comspec:
        shells['cmd'] = lambda line: f'"{comspec}" /d /s /c "{line}"'
    bash = _git_bash()
    if bash:
        shells['bash'] = lambda line: [bash, '-c', line]
    return shells


@unittest.skipUnless(os.name == 'nt', 'Windows shells only')
class TestCrossShell(unittest.TestCase):
    passing = []

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        cls.env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        cls.env.pop('RED_ROSE_DB', None)
        cls.shells = _shells()
        pf = cls.dir / 'params.json'
        pf.write_bytes(json.dumps({'text': WORDS, 'style': 'fade_up', 't': 0.8},
                                  ensure_ascii=False).encode('utf-8'))
        cls.params_file = pf.as_posix()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        if cls.passing:
            print('\nCROSS-SHELL PASSING FORMS (W01, measured):')
            for shell, line in cls.passing:
                print(f'  [{shell}] {line}')

    def _run(self, shell, line):
        argv = self.shells[shell](line)
        r = subprocess.run(argv, capture_output=True, env=self.env, cwd=str(self.dir), timeout=300)
        return r.returncode, r.stdout, r.stderr

    @staticmethod
    def _lines(result):
        return result['result']['result']['result']['lines']

    def test_shells_found(self):
        self.assertIn('powershell', self.shells)
        self.assertIn('cmd', self.shells)

    def test_inline_arabic_key_value(self):
        line = f'python -X utf8 {ENTRY} run text.motion.kinetic_text text="{WORDS}" style=fade_up t=0.8'
        for shell in self.shells:
            with self.subTest(shell=shell):
                code, out, err = self._run(shell, line)
                self.assertEqual(code, 0, err.decode('utf-8', 'replace')[-500:])
                self.assertIn(WORDS.encode('utf-8'), out)
                env = json.loads(out.decode('utf-8'))
                self.assertEqual(env['outcome'], 'ok')
                self.assertEqual(self._lines(env), [WORDS])
                self.passing.append((shell, line))

    def test_save_pair(self):
        for shell in self.shells:
            with self.subTest(shell=shell):
                svg = (self.dir / f'title_{shell}.svg').as_posix()
                line = (f'python -X utf8 {ENTRY} run text.motion.kinetic_text text="{WORDS}" style=fade_up t=0.8 '
                        f'--save svg={svg} --approve-write')
                code, out, err = self._run(shell, line)
                self.assertEqual(code, 0, (out + err).decode('utf-8', 'replace')[-500:])
                data = Path(svg).read_bytes()
                self.assertIn('الوردة'.encode('utf-8'), data)
                self.passing.append((shell, line))

    def test_params_file(self):
        for shell in self.shells:
            with self.subTest(shell=shell):
                out_file = (self.dir / f'step_{shell}.json').as_posix()
                line = (f'python -X utf8 {ENTRY} run text.motion.kinetic_text --params-file {self.params_file} '
                        f'--out {out_file} --approve-write')
                code, out, err = self._run(shell, line)
                self.assertEqual(code, 0, (out + err).decode('utf-8', 'replace')[-500:])
                raw = Path(out_file).read_bytes()
                self.assertFalse(raw.startswith(b'\xef\xbb\xbf'))
                env = json.loads(raw.decode('utf-8'))
                self.assertEqual(self._lines(env), [WORDS])
                self.passing.append((shell, line))


class ArabicUnquotedHintAndExitTable(unittest.TestCase):
    """Arabic typed unquoted in PowerShell 5.1, and the exit-code table (no shell needed)."""

    def setUp(self):
        sys.path.insert(0, str(ROOT))
        import rose_io
        self.rio = rose_io

    def test_unquoted_arabic_hint_names_powershell_and_the_quoted_example(self):
        # PowerShell hands over `text=الوردة` and `الحمراء` as two tokens; the second has no '='.
        with self.assertRaises(self.rio.ParamError) as ctx:
            self.rio.parse_pairs(['text=الوردة', 'الحمراء'])
        hint = ctx.exception.hint
        self.assertIn('not a key=value parameter', str(ctx.exception))
        self.assertIn('PowerShell', hint)
        self.assertIn('not the skill', hint)
        self.assertIn('double quotes', hint)
        self.assertIn('text="الوردة الحمراء"', hint)

    def test_quoted_arabic_pair_parses(self):
        self.assertEqual(self.rio.parse_pairs(['text=الوردة الحمراء']), {'text': 'الوردة الحمراء'})

    def test_exit_table_has_one_code_per_outcome(self):
        rio = self.rio
        self.assertEqual(rio.EXIT_NEEDS_INPUT, 6)
        self.assertEqual(rio.OUTCOME_EXIT, {'ok': 0, 'error': 1, 'approval_required': 3,
                                            'unavailable_here': 4, 'example_only': 5, 'needs_input': 6})
        self.assertEqual(rio.EXIT_USAGE, 2)
        self.assertEqual(set(rio.OUTCOMES), set(rio.OUTCOME_EXIT))

    def test_recipe_run_missing_input_exits_6_through_the_cli(self):
        with tempfile.TemporaryDirectory(prefix='rr-ni-') as tmp:
            res = subprocess.run([sys.executable, '-X', 'utf8', ENTRY, '--db', str(Path(tmp) / 'x.sqlite3'),
                                  'recipe', 'run', 'captions-from-words', '--work', str(Path(tmp) / 'w')],
                                 capture_output=True, text=True, encoding='utf-8', timeout=120,
                                 env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            self.assertEqual(res.returncode, 6, res.stdout[-400:] + res.stderr[-400:])
            doc = json.loads(res.stdout)
            self.assertEqual((doc['outcome'], doc['status']), ('needs_input', 'needs_input'))


if __name__ == '__main__':
    unittest.main()
